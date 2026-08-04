from django.apps import AppConfig


class ScraperBotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scraper_bot'
    verbose_name = 'Scraper Bot'

    def ready(self):
        import scraper_bot.signals  # noqa: F401
