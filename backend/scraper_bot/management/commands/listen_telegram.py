import asyncio
import os
import time

import httpx
from django.core.management.base import BaseCommand

from scraper_bot.models import BotConfig, ExecutionLog, Recipient
from scraper_bot.schemas import BotExecutionInput
from scraper_bot.services import BotOrchestrator

TELEGRAM_API = 'https://api.telegram.org/bot{token}/{method}'
POLL_TIMEOUT = 30


class Command(BaseCommand):
    help = 'Escuta mensagens do Telegram e registra novos usuários'

    def handle(self, *args, **options):
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            self.stdout.write(self.style.ERROR('TELEGRAM_BOT_TOKEN não configurado'))
            return

        self._set_commands(token)

        offset = 0
        self.stdout.write(self.style.SUCCESS('Escutando Telegram...'))

        while True:
            try:
                resp = httpx.get(
                    TELEGRAM_API.format(token=token, method='getUpdates'),
                    params={'offset': offset, 'timeout': POLL_TIMEOUT},
                    timeout=POLL_TIMEOUT + 5,
                )
                data = resp.json()
                if not data.get('ok'):
                    continue

                for update in data['result']:
                    offset = update['update_id'] + 1
                    msg = update.get('message')
                    if not msg:
                        continue

                    chat = msg.get('chat', {})
                    chat_id = str(chat.get('id'))
                    text = msg.get('text', '')

                    cmd = text.split()[0].lower()

                    if cmd == '/start':
                        first_name = chat.get('first_name', 'Usuário')
                        self._register_user(chat_id, first_name)
                        self._send_welcome(token, chat_id)
                    elif cmd == '/stop':
                        self._deactivate_user(chat_id)
                        self._send_goodbye(token, chat_id)
                    elif cmd in ('/help', '/ajuda', '/comandos'):
                        self._send_help(token, chat_id)
                    elif cmd == '/status':
                        self._send_status_info(token, chat_id)
                    elif cmd == '/configuracoes':
                        self._send_configs(token, chat_id)
                    elif cmd == '/ultima_execucao':
                        self._send_last_execution(token, chat_id)
                    elif cmd in ('/relatorio_completo', '/completo'):
                        self._send_status(token, chat_id, 'Gerando relatório completo...')
                        self._run_report(token, chat_id, template_id=4)
                    elif cmd in ('/resumo_secretaria',):
                        self._send_status(token, chat_id, 'Gerando resumo...')
                        self._run_report(token, chat_id, template_id=1)
                    elif cmd in ('/resumo_diario', '/diario'):
                        self._send_status(token, chat_id, 'Gerando resumo diário...')
                        self._run_report(token, chat_id, template_id=3)
                    elif cmd in ('/relatorio',):
                        self._send_status(token, chat_id, 'Gerando relatório...')
                        tid = BotConfig.objects.filter(is_active=True).first()
                        tid = tid.template_id if tid else None
                        self._run_report(token, chat_id, template_id=tid)

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Erro: {e}'))
                time.sleep(5)

    def _register_user(self, chat_id: str, name: str):
        obj, created = Recipient.objects.get_or_create(
            identifier=chat_id, platform='telegram',
            defaults={'name': name, 'is_active': True},
        )
        if not created:
            obj.name = name
            obj.is_active = True
            obj.save()
        action = 'Registrado' if created else 'Reativado'
        self.stdout.write(self.style.SUCCESS(
            f'{action}: {name} ({chat_id})'
        ))

    def _deactivate_user(self, chat_id: str):
        updated = Recipient.objects.filter(
            identifier=chat_id, platform='telegram'
        ).update(is_active=False)
        if updated:
            self.stdout.write(self.style.SUCCESS(
                f'Usuário {chat_id} desativado'
            ))

    def _send_welcome(self, token: str, chat_id: str):
        text = (
            '🤖 *Bem-vindo ao Aluno Presente Bot!*\n\n'
            'Você receberá automaticamente os relatórios diários do Projeto Aluno Presente '
            'da Secretaria Municipal de Educação de Cuiaba.\n\n'
            'Comandos disponíveis:\n\n'
            '📊 */relatorio_completo* — Relatório completo\n'
            '📋 */resumo_secretaria* — Resumo da Secretaria\n'
            '📅 */resumo_diario* — Resumo Diário\n'
            'ℹ️ */status* — Status do bot\n'
            '⚙️ */configuracoes* — Configurações ativas\n'
            '📝 */ultima_execucao* — Última execução\n'
            '❌ */stop* — Cancelar recebimento automático\n\n'
            'Envie */help* a qualquer momento para ver esta mensagem.'
        )
        self._send_telegram(token, chat_id, text)

    def _send_goodbye(self, token: str, chat_id: str):
        text = 'Você não receberá mais os relatórios. Use /start para reativar.'
        self._send_telegram(token, chat_id, text)

    def _send_telegram(self, token: str, chat_id: str, text: str):
        httpx.post(
            TELEGRAM_API.format(token=token, method='sendMessage'),
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'},
            timeout=10,
        )

    def _send_status(self, token: str, chat_id: str, text: str):
        self._send_telegram(token, chat_id, text)

    def _send_help(self, token: str, chat_id: str):
        text = (
            '🤖 *Aluno Presente Bot — Comandos*\n\n'
            '📊 */relatorio_completo* — Relatório completo da Visão Secretaria\n'
            '📋 */resumo_secretaria* — Resumo da Secretaria\n'
            '📅 */resumo_diario* — Resumo diário\n'
            'ℹ️ */status* — Status do bot (configs ativas, usuários, últimas execuções)\n'
            '⚙️ */configuracoes* — Lista as configurações ativas com horários\n'
            '📝 */ultima_execucao* — Detalhes da execução mais recente\n'
            '❌ */stop* — Cancelar recebimento automático\n\n'
            '💡 Você recebe automaticamente os relatórios nos horários agendados.'
        )
        self._send_telegram(token, chat_id, text)

    def _send_status_info(self, token: str, chat_id: str):
        from django.utils import timezone
        config_count = BotConfig.objects.filter(is_active=True).count()
        user_count = Recipient.objects.filter(is_active=True, platform='telegram').count()
        last = ExecutionLog.objects.filter(success=True).order_by('-started_at').first()
        failed = ExecutionLog.objects.filter(success=False).order_by('-started_at').first()

        lines = ['🤖 *Status do Bot*\n']
        fmt = '%d/%m/%Y %H:%M'
        lines.append(f'✅ Configurações ativas: *{config_count}*')
        lines.append(f'👥 Usuários Telegram ativos: *{user_count}*')
        lines.append('')

        if last:
            dur = round((last.finished_at - last.started_at).total_seconds(), 1) if last.finished_at else '—'
            lines.append(f'✅ *Última execução com sucesso:*')
            lines.append(f'  📅 {last.started_at.strftime(fmt)}')
            lines.append(f'  ⏱ {dur}s | 📨 {last.sent_count} enviados')
        else:
            lines.append('ℹ️ Nenhuma execução bem-sucedida ainda.')

        if failed:
            lines.append('')
            lines.append(f'❌ *Última falha:*')
            lines.append(f'  📅 {failed.started_at.strftime(fmt)}')
            if failed.error:
                lines.append(f'  ⚠️ {failed.error[:100]}')

        lines.append('')
        now = timezone.localtime(timezone.now())
        lines.append(f'🕐 Servidor: {now.strftime(fmt)}')

        self._send_telegram(token, chat_id, '\n'.join(lines))

    def _send_configs(self, token: str, chat_id: str):
        configs = BotConfig.objects.filter(is_active=True).select_related('template')
        if not configs:
            self._send_telegram(token, chat_id, 'Nenhuma configuração ativa no momento.')
            return

        lines = ['⚙️ *Configurações Ativas*\n']
        dias_map = {0: 'seg', 1: 'ter', 2: 'qua', 3: 'qui', 4: 'sex', 5: 'sáb', 6: 'dom'}

        for c in configs:
            lines.append(f'*{c.name}*')
            times = ', '.join(c.send_times) if c.send_times else '—'
            lines.append(f'  🕐 Horários: {times}')
            if c.send_days_of_week:
                days = ', '.join(dias_map.get(d, str(d)) for d in c.send_days_of_week)
                lines.append(f'  📆 Dias: {days}')
            else:
                lines.append(f'  📆 Dias: todos')
            if c.template:
                lines.append(f'  📝 Template: {c.template.name}')
            lines.append('')

        self._send_telegram(token, chat_id, '\n'.join(lines))

    def _send_last_execution(self, token: str, chat_id: str):
        last = ExecutionLog.objects.select_related('config').order_by('-started_at').first()
        if not last:
            self._send_telegram(token, chat_id, 'Nenhuma execução registrada ainda.')
            return

        dur = round((last.finished_at - last.started_at).total_seconds(), 1) if last.finished_at else '—'
        status = '✅ Sucesso' if last.success else '❌ Falha'
        config_name = last.config.name if last.config else '—'
        trigger_map = {'scheduler': 'Agendador', 'manual': 'Manual', 'telegram': 'Telegram'}
        trigger = trigger_map.get(last.trigger, last.trigger)

        fmt = '%d/%m/%Y %H:%M'
        text = (
            f'📝 *Última Execução*\n\n'
            f'📅 Data: {last.started_at.strftime(fmt)}\n'
            f'⚙️ Config: {config_name}\n'
            f'🔀 Trigger: {trigger}\n'
            f'{status}\n'
            f'⏱ Duração: {dur}s\n'
            f'📨 Enviados: {last.sent_count}\n'
            f'❌ Falhas: {last.failed_count}'
        )
        if last.error:
            text += f'\n⚠️ Erro: {last.error[:200]}'

        self._send_telegram(token, chat_id, text)

    def _set_commands(self, token: str):
        commands = [
            {'command': 'relatorio_completo', 'description': 'Relatório Completo - Visão Secretaria'},
            {'command': 'resumo_secretaria', 'description': 'Resumo da Visão Secretaria'},
            {'command': 'resumo_diario', 'description': 'Resumo Diário'},
            {'command': 'status', 'description': 'Status do bot e saúde do sistema'},
            {'command': 'configuracoes', 'description': 'Listar configurações ativas'},
            {'command': 'ultima_execucao', 'description': 'Mostrar última execução'},
            {'command': 'help', 'description': 'Lista completa de comandos'},
            {'command': 'stop', 'description': 'Cancelar recebimento automático'},
        ]
        try:
            httpx.post(
                TELEGRAM_API.format(token=token, method='setMyCommands'),
                json={'commands': commands},
                timeout=10,
            )
            self.stdout.write(self.style.SUCCESS('Comandos registrados no Telegram'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Erro ao registrar comandos: {e}'))

    def _run_report(self, token: str, chat_id: str, template_id: int | None = None):
        config = BotConfig.objects.filter(is_active=True).first()
        if not config:
            self._send_status(token, chat_id, 'Nenhuma configuração ativa encontrada.')
            return

        tid = template_id or config.template_id
        if not tid:
            self._send_status(token, chat_id, 'Nenhum template configurado.')
            return

        recipient, _ = Recipient.objects.get_or_create(
            identifier=chat_id, platform='telegram',
            defaults={'name': 'Usuário', 'is_active': True},
        )

        input_data = BotExecutionInput(
            config_id=config.id,
            template_id=tid,
            recipient_ids=[recipient.id],
            skip_time_check=True,
            trigger='telegram',
        )

        async def _exec():
            return await BotOrchestrator().execute(input_data)

        try:
            result = asyncio.run(_exec())

            if not result.success:
                msg = f'Erro ao gerar relatório: {result.error}'
                self._send_status(token, chat_id, msg)
            else:
                sent = result.messaging.sent_count if result.messaging else 0
                self._send_status(token, chat_id, f'Relatório enviado! ({sent} destinatário(s))')
        except Exception as e:
            self._send_status(token, chat_id, f'Erro ao gerar relatório: {e}')
            self.stdout.write(self.style.ERROR(f'Erro no relatório: {e}'))
