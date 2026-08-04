# Backlog - Aluno Presente Bot

## Concluídos

- [x] Extração via API interna do Aluno Presente (3 endpoints em paralelo)
- [x] Cálculo correto de ausentes usando `expectativaPresenca`
- [x] Re-login automático quando token expira (401 → reautentica)
- [x] Timeout da API aumentado de 15s para 30s
- [x] Porcentagens em todas as métricas (ausentes, não alimentados, com/sem foto)
- [x] Formatação pt-BR (ponto milhar, vírgula decimal)
- [x] Comandos Telegram: /relatorio_completo, /resumo_secretaria, /resumo_diario
- [x] Menu de comandos no bot Telegram (setMyCommands)
- [x] Sidebar no dashboard com link para Admin Django
- [x] Models registrados no admin (BotConfig, MessageTemplate, Recipient)
- [x] STATIC_URL corrigido para `/static/` (CSS do admin funcionando)
- [x] CSRF_TRUSTED_ORIGINS com porta :8080 no .env
- [x] Senha do admin Django resetada
- [x] Página de logout /logout/ com confirmação
- [x] Logout do painel desloga também do admin Django
- [x] restart: unless-stopped em todos os serviços docker-compose
- [x] Agendamento flexível por config (dias da semana por BotConfig)
- [x] Histórico de execuções
- [x] Estatísticas de envio
- [x] Mais comandos no listener Telegram
- [x] Testar extração sem envio (modo preview)
- [x] Persistir token de autenticação em volume Docker (playwright_session)

## Correções Críticas (Bugfixes)

- [x] **BUG #1**: `_catch_up()` em `scheduler.py:47` skipava todos os horários começando com '0' (incluindo "09:00") via `send_time.startswith('0')` → **Corrigido migrando para APScheduler**
- [x] **BUG #2**: Scheduler rodava como processo `&` no mesmo container sem supervisão → **Corrigido: scheduler agora é serviço Docker separado (`run_scheduler`)**
- [x] **BUG #3**: `messaging_skill.send_bulk()` sem timeout e sem concorrência → **Corrigido: httpx.AsyncClient com timeout 10s + asyncio.gather + semaphore (10 concorrentes)**
- [x] **BUG #4**: `extract_skill` propagava exceção do relogin em vez de fazer fallback para Playwright → **Corrigido: try/except no relogin com fallback garantido**
- [x] **BUG #5**: Agendamento custom com drift e sem persistência → **Corrigido: APScheduler + DjangoJobStore (persistente, sem drift, misfire_grace_time=300s)**
- [x] **BUG #6**: Boas-vindas do `/start` não aparecia → **Causas: dois listeners concorrentes no mesmo token (backend + scheduler via entrypoint `&`), update marcado como lido antes do processamento (`offset` avançado antes do envio) e rede instável com `sendMessage` silencioso. Corrigido: serviço Docker dedicado (`scraper_listener`) com um único poller, processamento isolado por update, offset persistido em volume (`telegram_offset.txt`), `sendMessage` com verificação de resposta + 3 retries com backoff e fallback sem Markdown.**

## Pendentes

- [ ] Testes automatizados (pytest) para scheduler, extractors, messaging
- [ ] CI/CD pipeline (lint, typecheck, test no GitHub Actions)
- [ ] Monitoramento: health check endpoint + métricas Prometheus
- [ ] Documentação de API (Swagger/OpenAPI via Django Ninja)