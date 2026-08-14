import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events
from django.conf import settings
from django.utils import timezone

from scraper_bot.services import BotOrchestrator
from scraper_bot.models import BotConfig, ExecutionLog, Recipient
from scraper_bot.skills.messaging_skill import MessagingSkill

logger = logging.getLogger(__name__)

_scheduler = None
_last_signature: str | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        _scheduler.add_jobstore(DjangoJobStore(), "default")
        register_events(_scheduler)
    return _scheduler


def schedule_job_for_config(config: BotConfig) -> list[str]:
    """Cria jobs APScheduler para um BotConfig. Retorna lista de job_ids."""
    scheduler = get_scheduler()
    job_ids = []

    if not config.template or not config.send_times:
        return job_ids

    orchestrator = BotOrchestrator()

    for send_time in config.send_times:
        try:
            hour, minute = map(int, send_time.split(":"))
        except ValueError:
            continue

        days = config.send_days_of_week or list(range(7))
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        cron_days = ",".join(day_names[d] for d in days if 0 <= d <= 6)

        job_id = f"botconfig_{config.id}_{send_time.replace(':', '')}"

        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=cron_days,
            timezone=settings.TIME_ZONE,
        )

        scheduler.add_job(
            execute_scheduled_job,
            trigger=trigger,
            id=job_id,
            args=[config.id],
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        job_ids.append(job_id)

    return job_ids


def execute_scheduled_job(config_id: int) -> None:
    """Job executado pelo APScheduler - roda em thread separada."""
    from asgiref.sync import async_to_sync

    orchestrator = BotOrchestrator()
    try:
        config = BotConfig.objects.select_related("template").get(id=config_id, is_active=True)
        if not config.template:
            _record_scheduler_failure(
                config_id, "Nenhum template vinculado a esta configuração"
            )
            _notify_failure(config_id, "Nenhum template vinculado a esta configuração", config.name)
            return

        input_data = orchestrator._build_input(config)
        result = async_to_sync(orchestrator.execute)(input_data)

        if not result.success:
            logger.error(
                'Execução agendada falhou para config %s: %s', config_id, result.error
            )
            _notify_failure(config_id, result.error or "Erro desconhecido", config.name)
        elif (
            result.messaging
            and result.messaging.failed_count > 0
            and result.messaging.sent_count == 0
        ):
            msg = f"Nenhuma mensagem entregue: {result.messaging.failed_count} falha(s)"
            logger.error('Envio agendado zerado para config %s: %s', config_id, msg)
            _notify_failure(config_id, msg, config.name)
    except BotConfig.DoesNotExist:
        logger.warning('Config %s não encontrada ou inativa no job agendado', config_id)
    except Exception as e:
        logger.exception('Erro inesperado no job agendado para config %s', config_id)
        _notify_failure(config_id, str(e), None)


def _record_scheduler_failure(config_id: int, error: str) -> None:
    try:
        now = timezone.localtime(timezone.now())
        ExecutionLog.objects.create(
            config_id=config_id,
            trigger='scheduler',
            started_at=now,
            finished_at=now,
            success=False,
            error=error,
        )
    except Exception:
        logger.exception('Falha ao registrar erro de agendamento para config %s', config_id)


def _notify_failure(config_id: int, error: str, config_name: str | None) -> None:
    from asgiref.sync import async_to_sync

    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        return

    try:
        admin_chat = os.environ.get('TELEGRAM_ADMIN_CHAT_ID')
        if admin_chat:
            targets = [admin_chat]
        else:
            targets = list(
                Recipient.objects.filter(is_active=True, platform='telegram')
                .values_list('identifier', flat=True)
            )
        if not targets:
            return

        label = config_name or f"#{config_id}"
        text = (
            "🚨 *Falha na execução agendada*\n\n"
            f"⚙️ Config: {label}\n"
            f"🕐 {timezone.localtime().strftime('%d/%m/%Y %H:%M')}\n\n"
            f"❌ Erro: {error[:300]}"
        )
        skill = MessagingSkill()

        async def _send() -> None:
            for target in targets:
                await skill.send_telegram(str(target), text)
            await skill.close()

        async_to_sync(_send)()
    except Exception:
        logger.exception('Falha ao enviar alerta de erro agendado para config %s', config_id)


def remove_jobs_for_config(config_id: int) -> None:
    scheduler = get_scheduler()
    prefix = f"botconfig_{config_id}_"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            scheduler.remove_job(job.id)


def start_scheduler() -> BackgroundScheduler:
    global _last_signature
    scheduler = get_scheduler()
    if not scheduler.running:
        _load_all_active_configs()
        _last_signature = _compute_config_signature()
        scheduler.start()
    return scheduler


def _load_all_active_configs() -> None:
    for config in BotConfig.objects.filter(is_active=True).select_related("template"):
        schedule_job_for_config(config)


def _compute_config_signature() -> str:
    """Assinatura leve das configs ativas. Se mudar, os jobs precisam ser re-sincronizados."""
    configs = (
        BotConfig.objects.filter(is_active=True)
        .select_related("template")
        .order_by("id")
    )
    parts = []
    for config in configs:
        times = tuple(sorted(config.send_times or []))
        days = tuple(sorted(config.send_days_of_week or list(range(7))))
        parts.append(f"{config.id}|{bool(config.template)}|{times}|{days}")
    return ";".join(parts)


def sync_jobs_from_db() -> bool:
    """Reconcilia os jobs agendados com o estado atual das configs no banco.

    Corre a falha de o sinal post_save do BotConfig rodar apenas no container
    backend, deixando o container scheduler com jobs obsoletos após uma edição
    (horário, dias, template ou desativação). Jobs cujo id não está no conjunto
    esperado são removidos.
    Retorna True quando algo foi re-sincronizado.
    """
    global _last_signature
    signature = _compute_config_signature()
    if signature == _last_signature:
        return False
    _last_signature = signature

    scheduler = get_scheduler()
    expected_ids: set[str] = set()
    for config in BotConfig.objects.filter(is_active=True).select_related("template"):
        job_ids = schedule_job_for_config(config)
        expected_ids.update(job_ids)

    for job in scheduler.get_jobs():
        if job.id.startswith("botconfig_") and job.id not in expected_ids:
            scheduler.remove_job(job.id)

    logger.info('Jobs do scheduler re-sincronizados com o banco')
    return True


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None