from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from scraper_bot.models import BotConfig
from scraper_bot.scheduler import schedule_job_for_config, remove_jobs_for_config


@receiver(post_save, sender=BotConfig)
def botconfig_post_save(sender, instance: BotConfig, **kwargs):
    if instance.is_active:
        schedule_job_for_config(instance)
    else:
        remove_jobs_for_config(instance.id)


@receiver(post_delete, sender=BotConfig)
def botconfig_post_delete(sender, instance: BotConfig, **kwargs):
    remove_jobs_for_config(instance.id)