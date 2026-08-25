import asyncio
import os
import time
from pathlib import Path

import httpx
from django.core.management.base import BaseCommand

from aluno_presente_sme.models import BotConfig, ExecutionLog, Recipient, validate_cpf
from aluno_presente_sme.schemas import BotExecutionInput
from aluno_presente_sme.services import BotOrchestrator

TELEGRAM_API = 'https://api.telegram.org/bot{token}/{method}'
POLL_TIMEOUT = 30
MAX_SEND_ATTEMPTS = 3
OFFSET_FILE = Path('/app/playwright_state/telegram_offset.txt')
MSG_NAO_CADASTRADO = 'Usuário não cadastrado, entrar em contato com SAME para devida autorização.'


class Command(BaseCommand):
    help = 'Escuta mensagens do Telegram e registra novos usuários'

    def handle(self, *args, **options):
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            self.stdout.write(self.style.ERROR('TELEGRAM_BOT_TOKEN não configurado'))
            return

        self._set_commands(token)

        offset = self._load_offset()
        self.stdout.write(self.style.SUCCESS(
            f'Escutando Telegram (resumindo do offset {offset})...'
        ))

        while True:
            try:
                resp = httpx.get(
                    TELEGRAM_API.format(token=token, method='getUpdates'),
                    params={'offset': offset, 'timeout': POLL_TIMEOUT},
                    timeout=POLL_TIMEOUT + 10,
                )
                resp.raise_for_status()
                data = resp.json()

                if not data.get('ok'):
                    self.stdout.write(self.style.WARNING(
                        f'getUpdates falhou: {data.get("description", "erro desconhecido")}'
                    ))
                    time.sleep(5)
                    continue

                for update in data['result']:
                    offset = update['update_id'] + 1
                    try:
                        self._handle_update(token, update)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Erro ao processar update {update.get("update_id")}: {e}'
                        ))
                    finally:
                        self._save_offset(offset)

            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Erro: {e}'))
                time.sleep(5)

    def _handle_update(self, token: str, update: dict):
        msg = update.get('message')
        if not msg:
            return

        chat = msg.get('chat', {})
        chat_id = str(chat.get('id'))
        text = msg.get('text') or ''
        if not text:
            return

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
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            self._send_status(token, chat_id, 'Gerando relatório completo...')
            self._run_report(token, chat_id, template_id=4)
        elif cmd in ('/resumo_secretaria',):
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            self._send_status(token, chat_id, 'Gerando resumo...')
            self._run_report(token, chat_id, template_id=1)
        elif cmd in ('/resumo_diario', '/diario'):
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            self._send_status(token, chat_id, 'Gerando resumo diário...')
            self._run_report(token, chat_id, template_id=3)
        elif cmd in ('/relatorio',):
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            self._send_status(token, chat_id, 'Gerando relatório...')
            tid = BotConfig.objects.filter(is_active=True).first()
            tid = tid.template_id if tid else None
            self._run_report(token, chat_id, template_id=tid)
        elif cmd == '/unidades':
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            args = text.split(maxsplit=1)
            period = args[1].upper() if len(args) > 1 else None
            self._list_school_units(token, chat_id, period=period)
        elif cmd == '/unidade':
            if not self._has_access(chat_id):
                self._send_telegram(token, chat_id, MSG_NAO_CADASTRADO)
                return
            args = text.split(maxsplit=1)
            query = args[1] if len(args) > 1 else ''
            self._query_school_unit(token, chat_id, query)

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

    def _has_access(self, chat_id: str) -> bool:
        """Verifica se o destinatário tem CPF ou matrícula cadastrada."""
        try:
            recipient = Recipient.objects.get(identifier=chat_id, platform='telegram')
            return recipient.has_access
        except Recipient.DoesNotExist:
            return False

    def _handle_cadastrar(self, token: str, chat_id: str, args: list):
        """Processa o comando /cadastrar CPF XXX.XXX.XXX-XX ou /cadastrar MATRICULA 123456."""
        if len(args) < 3:
            self._send_telegram(
                token, chat_id,
                'Uso correto:\n'
                '/cadastrar CPF XXX.XXX.XXX-XX\n'
                '/cadastrar MATRICULA 123456'
            )
            return

        tipo = args[1].upper()
        valor = args[2].strip()

        try:
            recipient = Recipient.objects.get(identifier=chat_id, platform='telegram')
        except Recipient.DoesNotExist:
            self._send_telegram(
                token, chat_id,
                'Usuário não encontrado. Envie /start primeiro para se registrar.'
            )
            return

        if tipo == 'CPF':
            cpf_digits = ''.join(filter(str.isdigit, valor))
            if not validate_cpf(cpf_digits):
                self._send_telegram(token, chat_id, 'CPF inválido. Verifique e tente novamente.')
                return
            formatted = f'{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}'
            recipient.cpf = formatted
            recipient.save()
            self._send_telegram(token, chat_id, f'CPF {formatted} cadastrado com sucesso!')
        elif tipo == 'MATRICULA':
            if not valor:
                self._send_telegram(token, chat_id, 'Informe o número da matrícula.')
                return
            recipient.matricula_funcional = valor
            recipient.save()
            self._send_telegram(token, chat_id, f'Matrícula {valor} cadastrada com sucesso!')
        else:
            self._send_telegram(
                token, chat_id,
                'Tipo inválido. Use:\n'
                '/cadastrar CPF XXX.XXX.XXX-XX\n'
                '/cadastrar MATRICULA 123456'
            )

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
            '🏫 */unidades* — Listar todas as escolas\n'
            '🏫 */unidades matutino* — Filtrar por período\n'
            '🔍 */unidade <nome>* — Consultar escola por nome\n'
            'ℹ️ */status* — Status do bot\n'
            '⚙️ */configuracoes* — Configurações ativas\n'
            '📝 */ultima_execucao* — Última execução\n'
            '❌ */stop* — Cancelar recebimento automático\n\n'
            'Envie */help* a qualquer momento para ver esta mensagem.'
        )
        if not self._send_telegram(token, chat_id, text):
            self.stdout.write(self.style.ERROR(
                f'Falha ao enviar boas-vindas para {chat_id}'
            ))

    def _send_goodbye(self, token: str, chat_id: str):
        text = 'Você não receberá mais os relatórios. Use /start para reativar.'
        self._send_telegram(token, chat_id, text)

    def _send_telegram(self, token: str, chat_id: str, text: str) -> bool:
        url = TELEGRAM_API.format(token=token, method='sendMessage')
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}

        for attempt in range(MAX_SEND_ATTEMPTS):
            try:
                resp = httpx.post(url, json=payload, timeout=10)
                data = resp.json()
                if resp.status_code == 200 and data.get('ok'):
                    return True

                description = data.get('description', '') if isinstance(data, dict) else ''
                self.stdout.write(self.style.WARNING(
                    f'Telegram recusou envio para {chat_id}: '
                    f'HTTP {resp.status_code} - {description}'
                ))
                if (
                    resp.status_code == 400
                    and 'parse' in description.lower()
                    and payload.get('parse_mode')
                ):
                    payload = {k: v for k, v in payload.items() if k != 'parse_mode'}
                    continue
                return False
            except httpx.HTTPError as e:
                self.stdout.write(self.style.WARNING(
                    f'Falha de rede ao enviar para {chat_id} '
                    f'(tentativa {attempt + 1}/{MAX_SEND_ATTEMPTS}): {e}'
                ))
                time.sleep(2 * (attempt + 1))
        return False

    def _send_status(self, token: str, chat_id: str, text: str):
        self._send_telegram(token, chat_id, text)

    def _send_help(self, token: str, chat_id: str):
        text = (
            '🤖 *Aluno Presente Bot — Comandos*\n\n'
            '📊 */relatorio_completo* — Relatório completo da Visão Secretaria\n'
            '📋 */resumo_secretaria* — Resumo da Secretaria\n'
            '📅 */resumo_diario* — Resumo diário\n'
            '🏫 */unidades* — Listar todas as escolas disponíveis\n'
            '🔍 */unidade <nome>* — Consultar dados de uma escola por nome\n'
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
            {'command': 'relatorio_completo', 'description': 'Relatório Completo'},
            {'command': 'resumo_secretaria', 'description': 'Resumo da Secretaria'},
            {'command': 'resumo_diario', 'description': 'Resumo Diário'},
            {'command': 'unidades', 'description': 'Listar escolas (filtro: /unidades matutino)'},
            {'command': 'unidade', 'description': 'Consultar escola por nome'},
            {'command': 'status', 'description': 'Status do bot'},
            {'command': 'configuracoes', 'description': 'Configurações ativas'},
            {'command': 'ultima_execucao', 'description': 'Última execução'},
            {'command': 'help', 'description': 'Lista de comandos'},
            {'command': 'stop', 'description': 'Cancelar automático'},
        ]
        try:
            resp = httpx.post(
                TELEGRAM_API.format(token=token, method='setMyCommands'),
                json={'commands': commands},
                timeout=10,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get('ok'):
                self.stdout.write(self.style.SUCCESS('Comandos registrados no Telegram'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'Falha ao registrar comandos: HTTP {resp.status_code} '
                    f'- {data.get("description", "")}'
                ))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Erro ao registrar comandos: {e}'))

    def _run_report(self, token: str, chat_id: str, template_id: int | None = None, unit_id: int | None = None):
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
            unit_id=unit_id,
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

    def _list_school_units(self, token: str, chat_id: str, period: str | None = None):
        from aluno_presente_sme.models import UnitPeriod
        from aluno_presente_sme.skills.extractors.aluno_presente import AlunoPresenteExtractor

        extractor = AlunoPresenteExtractor()
        t = extractor.get_token()
        if not t:
            self._send_telegram(token, chat_id, 'Sessão expirada. Use /relogin para renovar.')
            return

        try:
            units = asyncio.run(extractor.list_school_units(t))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.stdout.write('Token expirado ao listar unidades, fazendo re-login...')
                try:
                    asyncio.run(extractor.relogin())
                    t = extractor.get_token()
                    if not t:
                        self._send_telegram(token, chat_id, 'Sessão expirada. Use /relogin para renovar.')
                        return
                    units = asyncio.run(extractor.list_school_units(t))
                except Exception as re_err:
                    self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {re_err}')
                    return
            else:
                self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {e}')
                return
        except Exception as e:
            self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {e}')
            return

        if period:
            valid = {'MATUTINO', 'VESPERTINO', 'INTEGRAL', 'NOTURNO'}
            if period not in valid:
                self._send_telegram(token, chat_id, f'Período inválido. Opções: {", ".join(sorted(valid))}')
                return
            period_unit_ids = set(
                UnitPeriod.objects.filter(period=period).values_list('unit_id', flat=True)
            )
            units = [u for u in units if u['id'] in period_unit_ids]
            title = f'Escolas — {period} ({len(units)} total)'
        else:
            title = f'Escolas Disponíveis ({len(units)} total)'

        lines = [f'*{title}*\n']
        for u in units:
            lines.append(f'• `{u["id"]}` — {u["nome"]}')

        text = '\n'.join(lines)
        if len(text) > 4000:
            text = text[:3997] + '...'

        self._send_telegram(token, chat_id, text)

    def _query_school_unit(self, token: str, chat_id: str, query: str):
        if not query.strip():
            self._send_telegram(token, chat_id, 'Uso: /unidade <nome da escola>')
            return

        from aluno_presente_sme.skills.extractors.aluno_presente import AlunoPresenteExtractor

        extractor = AlunoPresenteExtractor()
        t = extractor.get_token()
        if not t:
            self._send_telegram(token, chat_id, 'Sessão expirada. Use /relogin para renovar.')
            return

        try:
            units = asyncio.run(extractor.list_school_units(t))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.stdout.write('Token expirado ao buscar unidade, fazendo re-login...')
                try:
                    asyncio.run(extractor.relogin())
                    t = extractor.get_token()
                    if not t:
                        self._send_telegram(token, chat_id, 'Sessão expirada. Use /relogin para renovar.')
                        return
                    units = asyncio.run(extractor.list_school_units(t))
                except Exception as re_err:
                    self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {re_err}')
                    return
            else:
                self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {e}')
                return
        except Exception as e:
            self._send_telegram(token, chat_id, f'Erro ao buscar unidades: {e}')
            return

        query_lower = query.lower()
        matches = [u for u in units if query_lower in u['nome'].lower()]

        if not matches:
            self._send_telegram(token, chat_id, f'Nenhuma escola encontrada com "{query}".')
            return

        if len(matches) == 1:
            unit_id = matches[0]['id']
            self._send_status(token, chat_id, f'Consultando {matches[0]["nome"]}...')
            self._run_report(token, chat_id, template_id=7, unit_id=unit_id)
            return

        lines = [f'*{len(matches)} escolas encontradas para "{query}":*\n']
        for u in matches[:20]:
            lines.append(f'• `{u["id"]}` — {u["nome"]}')
        if len(matches) > 20:
            lines.append(f'\n... e mais {len(matches) - 20} escolas.')

        self._send_telegram(token, chat_id, '\n'.join(lines))

    def _load_offset(self) -> int:
        try:
            if OFFSET_FILE.exists():
                return int(OFFSET_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
        return 0

    def _save_offset(self, offset: int) -> None:
        try:
            OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
            OFFSET_FILE.write_text(str(offset))
        except OSError as e:
            self.stdout.write(self.style.WARNING(f'Não foi possível salvar offset: {e}'))
