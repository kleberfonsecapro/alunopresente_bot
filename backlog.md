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

## Pendentes

- [x] Agendamento flexível por config (dias da semana por BotConfig)
- [x] Histórico de execuções
- [x] Estatísticas de envio
- [x] Mais comandos no listener Telegram
- [x] Testar extração sem envio (modo preview)
- [x] Persistir token de autenticação em volume Docker (playwright_session)
