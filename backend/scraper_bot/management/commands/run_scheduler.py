import signal
import sys
import time

from django.core.management.base import BaseCommand

from scraper_bot.scheduler import start_scheduler, shutdown_scheduler, sync_jobs_from_db


class Command(BaseCommand):
    help = "Inicia o APScheduler para execução agendada dos bots"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando APScheduler..."))
        scheduler = start_scheduler()
        self.stdout.write(self.style.SUCCESS(f"Scheduler rodando com {len(scheduler.get_jobs())} jobs ativos"))

        def _shutdown(signum, frame):
            self.stdout.write(self.style.WARNING("Encerrando scheduler..."))
            shutdown_scheduler()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        try:
            while True:
                time.sleep(60)
                try:
                    sync_jobs_from_db()
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'Erro ao sincronizar jobs: {e}'
                    ))
                active_jobs = len(scheduler.get_jobs())
                self.stdout.write(f"[heartbeat] {active_jobs} jobs agendados")
        except KeyboardInterrupt:
            shutdown_scheduler()
            self.stdout.write(self.style.SUCCESS("Scheduler parado"))