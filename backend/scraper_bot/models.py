from django.db import models

from scraper_bot.skills.extractors import list_site_choices


class BotConfig(models.Model):
    name = models.CharField(max_length=255)
    site_type = models.CharField(
        max_length=50,
        choices=list_site_choices,
        default='aluno_presente',
        help_text="Tipo do site alvo para selecionar o extrator apropriado"
    )
    target_url = models.URLField()
    extraction_fields = models.JSONField(
        default=list,
        help_text="Lista de campos que o agente deve extrair. Ex: ['titulo', 'preco', 'descricao']"
    )
    send_times = models.JSONField(
        default=list,
        help_text='Horários de disparo. Ex: ["08:00", "14:00", "20:00"]'
    )
    send_days_of_week = models.JSONField(
        default=list, blank=True,
        help_text="Dias da semana para disparo. 0=segunda, 6=domingo. Vazio = todos os dias."
    )
    send_duration_days = models.IntegerField(
        null=True, blank=True,
        help_text="Duração em dias para enviar mensagens. Null = indeterminado."
    )
    template = models.ForeignKey(
        'MessageTemplate', null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Template de mensagem usado no disparo automático"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Configuração do Bot"
        verbose_name_plural = "Configurações do Bot"


class MessageTemplate(models.Model):
    name = models.CharField(max_length=255)
    body = models.TextField(
        help_text="Template com variáveis dinâmicas. Ex: 'Resultado: {{dado_raspado}}'"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Template de Mensagem"
        verbose_name_plural = "Templates de Mensagem"


class Recipient(models.Model):
    CHAT_PLATFORMS = [
        ('whatsapp', 'WhatsApp'),
        ('telegram', 'Telegram'),
        ('email', 'E-mail'),
        ('sms', 'SMS'),
    ]

    name = models.CharField(max_length=255)
    identifier = models.CharField(
        max_length=255,
        help_text="Número de telefone, ID de chat ou e-mail do destinatário"
    )
    platform = models.CharField(max_length=50, choices=CHAT_PLATFORMS)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.platform}: {self.identifier})"

    class Meta:
        verbose_name = "Destinatário"
        verbose_name_plural = "Destinatários"


class ExecutionLog(models.Model):
    TRIGGER_CHOICES = [
        ('scheduler', 'Agendador'),
        ('manual', 'Manual'),
        ('telegram', 'Telegram'),
    ]

    config = models.ForeignKey(BotConfig, on_delete=models.SET_NULL, null=True, blank=True)
    template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='manual')
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    success = models.BooleanField(default=False)
    error = models.TextField(null=True, blank=True)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    extraction_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.id}] {self.config.name if self.config else '?'} - {self.started_at.strftime('%d/%m/%Y %H:%M')} - {'OK' if self.success else 'FALHA'}"

    class Meta:
        verbose_name = "Histórico de Execução"
        verbose_name_plural = "Históricos de Execução"
        ordering = ['-started_at']
