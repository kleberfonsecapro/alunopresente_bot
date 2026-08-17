import asyncio
import logging
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from scraper_bot.models import BotConfig, ExecutionLog, MessageTemplate, Recipient
from scraper_bot.schemas import (
    BotExecutionInput,
    BotExecutionOutput,
    ExtractionContract,
    ExtractionOutput,
    MessageOutput,
)
from scraper_bot.skills.navigation_skill import NavigationSkill
from scraper_bot.skills.extract_skill import ExtractionSkill
from scraper_bot.skills.messaging_skill import MessagingSkill

logger = logging.getLogger(__name__)


class BotOrchestrator:

    def __init__(self, max_retries: int = 2, retry_backoff_sec: int = 5):
        self.max_retries = max(1, max_retries)
        self.retry_backoff_sec = max(0, retry_backoff_sec)
        self.navigation = NavigationSkill()
        self.extraction = ExtractionSkill()
        self.messaging = MessagingSkill()

    def should_execute(self, config: BotConfig, now: datetime | None = None) -> tuple[bool, str]:
        now = now or timezone.localtime(timezone.now())

        if not config.is_active:
            return False, "Configuração inativa"

        if config.send_duration_days is not None:
            expires_at = config.created_at + timedelta(days=config.send_duration_days)
            if now > expires_at:
                return False, f"Prazo expirado em {expires_at.date()}"

        if config.send_days_of_week:
            current_weekday = now.weekday()
            if current_weekday not in config.send_days_of_week:
                dias = {0: "segunda", 1: "terça", 2: "quarta", 3: "quinta", 4: "sexta", 5: "sábado", 6: "domingo"}
                return False, f"Dia {dias.get(current_weekday, str(current_weekday))} não está nos dias configurados"

        if config.send_times:
            current_time = now.strftime("%H:%M")
            if current_time not in config.send_times:
                return False, f"Horário {current_time} não está nos horários configurados: {config.send_times}"

        return True, ""

    async def execute(self, input_data: BotExecutionInput) -> BotExecutionOutput:
        if not input_data.preview and not input_data.template_id:
            return BotExecutionOutput(success=False, error="template_id é obrigatório quando preview=False")

        started_at = timezone.localtime(timezone.now())
        try:
            log = await sync_to_async(ExecutionLog.objects.create)(
                config_id=input_data.config_id,
                template_id=input_data.template_id,
                trigger=input_data.trigger,
                started_at=started_at,
                success=False,
            )
        except Exception as e:
            return BotExecutionOutput(success=False, error=f"Erro ao criar log: {e}")

        try:
            _get_config = sync_to_async(BotConfig.objects.get)
            _get_template = sync_to_async(MessageTemplate.objects.get)
            _get_recipients = sync_to_async(
                lambda: list(Recipient.objects.filter(
                    id__in=input_data.recipient_ids,
                    is_active=True
                ))
            )

            config = await _get_config(id=input_data.config_id)
            recipients = await _get_recipients()

            if not input_data.skip_time_check:
                ok, msg = self.should_execute(config)
                if not ok:
                    log.error = msg
                    log.finished_at = timezone.localtime(timezone.now())
                    await sync_to_async(log.save)()
                    return BotExecutionOutput(success=False, error=msg, log_id=log.id)

            fields = []
            for f in config.extraction_fields:
                if isinstance(f, dict):
                    fields.append(ExtractionContract(**f))
                else:
                    fields.append(ExtractionContract(field_name=str(f)))

            extraction_result = await self._extract_with_retry(
                config=config,
                fields=fields,
                unit_id=input_data.unit_id,
            )

            now = timezone.localtime(timezone.now())
            hora = now.hour
            if 6 <= hora < 12:
                periodo = "manhã"
            elif 12 <= hora < 18:
                periodo = "tarde"
            else:
                periodo = "noite"

            extraction_result['data']['data_envio'] = now.strftime('%d/%m/%Y')
            extraction_result['data']['periodo'] = periodo

            extraction = ExtractionOutput(
                url=extraction_result['url'],
                data=extraction_result['data'],
            )

            if input_data.preview:
                log.success = True
                log.extraction_data = extraction.data
                log.finished_at = timezone.localtime(timezone.now())
                await sync_to_async(log.save)()
                return BotExecutionOutput(
                    success=True,
                    extraction=extraction,
                    log_id=log.id,
                )

            template = await _get_template(id=input_data.template_id)

            recipients_data = [
                {'platform': r.platform, 'identifier': r.identifier}
                for r in recipients
            ]

            messaging_result = await self.messaging.send_bulk(
                template_body=template.body,
                extracted_data=extraction.data,
                recipients=recipients_data
            )

            log.success = True
            log.sent_count = messaging_result['sent_count']
            log.failed_count = messaging_result['failed_count']
            log.extraction_data = extraction.data
            log.finished_at = timezone.localtime(timezone.now())
            await sync_to_async(log.save)()

            return BotExecutionOutput(
                success=True,
                extraction=extraction,
                messaging=MessageOutput(**messaging_result),
                log_id=log.id,
            )

        except Exception as e:
            log.error = str(e)
            log.finished_at = timezone.localtime(timezone.now())
            await sync_to_async(log.save)()
            return BotExecutionOutput(
                success=False,
                error=str(e),
                log_id=log.id,
            )

    async def _extract_with_retry(self, config: BotConfig, fields: list[ExtractionContract], unit_id: int | None = None) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await self.extraction.extract(
                    url=config.target_url,
                    fields=fields,
                    site_type=config.site_type,
                    unit_id=unit_id,
                    unit_ids=config.school_unit_ids or None,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    'Extração falhou para config %s (tentativa %d/%d): %s',
                    config.id, attempt, self.max_retries, e,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff_sec * attempt)
        if last_error is None:
            raise RuntimeError('Nenhuma tentativa de extração foi executada')
        raise last_error

    def _build_input(self, config: BotConfig) -> BotExecutionInput:
        recipients = list(Recipient.objects.filter(is_active=True).values_list('id', flat=True))
        return BotExecutionInput(
            config_id=config.id,
            template_id=config.template.id,
            recipient_ids=recipients,
            skip_time_check=True,
            trigger='scheduler',
        )

    async def execute_due(self, config_id: int) -> BotExecutionOutput:
        _get_config = sync_to_async(BotConfig.objects.select_related('template').get)

        config = await _get_config(id=config_id)
        if not config.template:
            started_at = timezone.localtime(timezone.now())
            try:
                await sync_to_async(ExecutionLog.objects.create)(
                    config_id=config_id, trigger='scheduler',
                    started_at=started_at, finished_at=started_at,
                    success=False, error="Nenhum template vinculado a esta configuração",
                )
            except Exception:
                pass
            return BotExecutionOutput(success=False, error="Nenhum template vinculado a esta configuração")

        input_data = self._build_input(config)
        return await self.execute(input_data)
