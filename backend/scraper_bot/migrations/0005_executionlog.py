from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('scraper_bot', '0004_botconfig_send_days_of_week'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExecutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger', models.CharField(choices=[('scheduler', 'Agendador'), ('manual', 'Manual'), ('telegram', 'Telegram')], default='manual', max_length=20)),
                ('started_at', models.DateTimeField()),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('success', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True, null=True)),
                ('sent_count', models.IntegerField(default=0)),
                ('failed_count', models.IntegerField(default=0)),
                ('extraction_data', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('config', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='scraper_bot.botconfig')),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='scraper_bot.messagetemplate')),
            ],
            options={
                'verbose_name': 'Histórico de Execução',
                'verbose_name_plural': 'Históricos de Execução',
                'ordering': ['-started_at'],
            },
        ),
    ]
