from django.contrib import admin

from scraper_bot.models import BotConfig, ExecutionLog, MessageTemplate, Recipient


@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'site_type', 'is_active', 'send_times', 'send_days_of_week', 'template', 'created_at')
    list_filter = ('site_type', 'is_active')
    search_fields = ('name',)


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ('name', 'identifier', 'platform', 'is_active', 'created_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('name', 'identifier')


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'config', 'trigger', 'success', 'sent_count', 'started_at', 'finished_at')
    list_filter = ('success', 'trigger', 'config')
    readonly_fields = ('started_at', 'finished_at', 'sent_count', 'failed_count', 'error', 'extraction_data')
