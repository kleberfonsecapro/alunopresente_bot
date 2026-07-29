import time
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand
from django.utils import timezone

from scraper_bot.models import BotConfig, ExecutionLog
from scraper_bot.services import BotOrchestrator


class Command(BaseCommand):
    help = "Agendador preciso do bot — executa a cada minuto na virada do segundo, sem drift"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            "Agendador iniciado — verificando a cada minuto na virada do segundo"
        ))
        self._catch_up()
        while True:
            try:
                self._tick()
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"[{self._ts()}] Erro no tick: {e}"
                ))

            now = timezone.localtime(timezone.now())
            next_run = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_sec = (next_run - timezone.localtime(timezone.now())).total_seconds()
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def _ts(self):
        return timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')

    def _catch_up(self):
        now = timezone.localtime(timezone.now())
        catch_up_window = now - timedelta(hours=3)
        orchestrator = BotOrchestrator()
        configs = BotConfig.objects.filter(is_active=True).select_related('template')

        for config in configs:
            if not config.template:
                continue
            for send_time in config.send_times:
                if send_time.startswith('0'):
                    continue
                hour, minute = send_time.split(':')
                scheduled = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                if catch_up_window <= scheduled < now:
                    already_ran = ExecutionLog.objects.filter(
                        config_id=config.id,
                        trigger='scheduler',
                        started_at__gte=scheduled - timedelta(seconds=30),
                        started_at__lte=scheduled + timedelta(minutes=2),
                    ).exists()
                    if already_ran:
                        continue
                    self.stdout.write(self.style.WARNING(
                        f"[{self._ts()}] [{config.id}] {config.name}: "
                        f"catch-up para horário perdido {send_time}..."
                    ))
                    input_data = orchestrator._build_input(config)
                    result = async_to_sync(orchestrator.execute)(input_data)
                    if result.success:
                        self.stdout.write(self.style.SUCCESS(
                            f"[{self._ts()}]   ✓ Catch-up OK — {result.messaging.sent_count if result.messaging else 0} mensagens"
                        ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f"[{self._ts()}]   ✗ Catch-up falhou: {result.error}"
                        ))

    def _tick(self):
        now = timezone.localtime(timezone.now())
        orchestrator = BotOrchestrator()
        configs = BotConfig.objects.filter(is_active=True)

        executed = 0
        skipped = 0
        errors = 0

        for config in configs:
            ok, reason = orchestrator.should_execute(config, now)
            if not ok:
                self.stdout.write(
                    f"[{self._ts()}] [{config.id}] {config.name}: pulando — {reason}"
                )
                skipped += 1
                continue

            self.stdout.write(f"[{self._ts()}] [{config.id}] {config.name}: executando...")
            result = async_to_sync(orchestrator.execute_due)(config.id)

            if result.success:
                executed += 1
                sent = result.messaging.sent_count if result.messaging else 0
                self.stdout.write(self.style.SUCCESS(
                    f"[{self._ts()}]   ✓ OK — {sent} mensagens enviadas"
                ))
            else:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"[{self._ts()}]   ✗ Falha: {result.error}"
                ))

        if executed or errors:
            self.stdout.write(
                f"[{self._ts()}] Resumo: {executed} executados, {skipped} pulados, {errors} erros"
            )
