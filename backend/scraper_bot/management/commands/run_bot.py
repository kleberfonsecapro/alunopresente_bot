from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand
from django.utils import timezone

from scraper_bot.models import BotConfig
from scraper_bot.services import BotOrchestrator


class Command(BaseCommand):
    help = "Executa as configurações do bot que estão dentro do período e horário agendados"

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        orchestrator = BotOrchestrator()
        configs = BotConfig.objects.filter(is_active=True)

        executed = 0
        skipped = 0
        errors = 0

        for config in configs:
            ok, reason = orchestrator.should_execute(config, now)
            if not ok:
                self.stdout.write(f"  [{config.id}] {config.name}: pulando — {reason}")
                skipped += 1
                continue

            self.stdout.write(f"  [{config.id}] {config.name}: executando...")
            result = async_to_sync(orchestrator.execute_due)(config.id)

            if result.success:
                executed += 1
                sent = result.messaging.sent_count if result.messaging else 0
                self.stdout.write(self.style.SUCCESS(
                    f"    ✓ OK — {sent} mensagens enviadas"
                ))
            else:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"    ✗ Falha: {result.error}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"\nConcluído: {executed} executados, {skipped} pulados, {errors} erros"
        ))
