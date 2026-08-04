from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore, register_events, register_job
from django.conf import settings

from scraper_bot.services import BotOrchestrator
from scraper_bot.models import BotConfig


_scheduler = None


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
            return
        input_data = orchestrator._build_input(config)
        async_to_sync(orchestrator.execute)(input_data)
    except BotConfig.DoesNotExist:
        pass
    except Exception:
        pass


def remove_jobs_for_config(config_id: int) -> None:
    scheduler = get_scheduler()
    prefix = f"botconfig_{config_id}_"
    for job in scheduler.get_jobs():
        if job.id.startswith(prefix):
            scheduler.remove_job(job.id)


def start_scheduler() -> BackgroundScheduler:
    scheduler = get_scheduler()
    if not scheduler.running:
        _load_all_active_configs()
        scheduler.start()
    return scheduler


def _load_all_active_configs() -> None:
    for config in BotConfig.objects.filter(is_active=True).select_related("template"):
        schedule_job_for_config(config)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None