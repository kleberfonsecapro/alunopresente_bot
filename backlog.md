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
- [x] Consulta individual por unidade escolar via Telegram (`/unidades`, `/unidade <nome>`, `/unidade_id <id>`)
- [x] Campo `school_unit_ids` no BotConfig para filtrar unidades na extração
- [x] Método `list_school_units()` no AlunoPresenteExtractor (endpoint `/unidades/todas`)
- [x] Método `extract_single_unit()` no AlunoPresenteExtractor (filtra por `unidade_id`)
- [x] Extração suporta `unit_ids` para filtrar unidades específicas na agregação
- [x] Endpoint `GET /api/school-unities/` lista todas as unidades disponíveis
- [x] Schema `SchoolUnitOutput` para resposta da API
- [x] Migration `0007_add_school_unit_ids_to_botconfig`
- [x] Filtro de período por unidade escolar (cache via API de turmas)
- [x] Modelo `UnitPeriod` (unit_id, period, unit_name) com migration `0008`
- [x] Command `sync_unit_periods` — sincroniza períodos via POST `/api/turmas/filtrar`
- [x] `_fetch_api_data()` filtra por período usando `UnitPeriod` do banco
- [x] Comando `/periodos` no Telegram — lista períodos disponíveis
- [x] Comando `/unidades <período>` — filtra escolas por período (MATUTINO, VESPERTINO, INTEGRAL, NOTURNO)
- [x] Schema `BotExecutionInput.period` para suporte a filtro via API

## Correções Críticas (Bugfixes)

- [x] **BUG #1**: `_catch_up()` em `scheduler.py:47` skipava todos os horários começando com '0' (incluindo "09:00") via `send_time.startswith('0')` → **Corrigido migrando para APScheduler**
- [x] **BUG #2**: Scheduler rodava como processo `&` no mesmo container sem supervisão → **Corrigido: scheduler agora é serviço Docker separado (`run_scheduler`)**
- [x] **BUG #3**: `messaging_skill.send_bulk()` sem timeout e sem concorrência → **Corrigido: httpx.AsyncClient com timeout 10s + asyncio.gather + semaphore (10 concorrentes)**
- [x] **BUG #4**: `extract_skill` propagava exceção do relogin em vez de fazer fallback para Playwright → **Corrigido: try/except no relogin com fallback garantido**
- [x] **BUG #5**: Agendamento custom com drift e sem persistência → **Corrigido: APScheduler + DjangoJobStore (persistente, sem drift, misfire_grace_time=300s)**
- [x] **BUG #6**: Boas-vindas do `/start` não aparecia → **Causas: dois listeners concorrentes no mesmo token (backend + scheduler via entrypoint `&`), update marcado como lido antes do processamento (`offset` avançado antes do envio) e rede instável com `sendMessage` silencioso. Corrigido: serviço Docker dedicado (`aluno_presente_listener`) com um único poller, processamento isolado por update, offset persistido em volume (`telegram_offset.txt`), `sendMessage` com verificação de resposta + 3 retries com backoff e fallback sem Markdown.**
- [x] **BUG #7**: Fallback Playwright produzia **dados inúteis com `success=True`** → **Sintoma: sem `storage_state.json` (sessão ausente/expirou), `get_token()` retornava `None`, o caminho da API era pulado e o fallback Playwright gravava `page.url` como valor de TODOS os campos (52 campos = URL da tela de login), registrando sucesso. Corrigido em 3 frentes: (1) `ExtractSkill.extract` agora tenta `relogin()` inicial quando não há token e o site define `login_url`, obtendo token antes de cair no fallback; (2) `SiteExtractor` ganhou helpers `_ensure_authenticated_page`/`_is_login_page` que detectam redirect para login, relogam e recriam a página (falha explícita com `RuntimeError` se o login persistir); (3) campo sem selector agora **levanta erro claro** em vez de retornar `page.url` (genérico retorna `None` honesto). +9 testes unitários (total 61). Validação real: preview passou a extrair métricas corretas após re-login automático.**
- [x] **BUG #8**: Comandos Telegram `/unidades` e `/unidade <nome>` falhavam com **401 Unauthorized** ao buscar `/api/dashboard-secretario/unidades/todas` → **Causa: `_list_school_units()` e `_query_school_unit()` em `listen_telegram.py` chamavam `list_school_units(token)` diretamente — quando o JWT expira (~24h), `get_token()` retorna a string não-vazia do token expirado, a requisição HTTP retorna 401, e o `except Exception` genérico repassava o erro sem tentar re-login. O caminho da `ExtractionSkill` já tratava 401 com re-login, mas o Telegram listener bypassava completamente essa lógica. Corrigido: catch específico para `httpx.HTTPStatusError` com status 401 em ambos os métodos — chama `extractor.relogin()`, obtém novo token via `get_token()`, e retenta `list_school_units()`. Se re-login falhar, informa o usuário. Padrão idêntico ao já existente em `ExtractionSkill.extract()` (`extract_skill.py:46-62`).**
- [x] **BUG #9**: `extract_single_unit()` e `_fetch_api_data()` em `aluno_presente.py` recalculavam métricas manualmente **ignorando campos pré-calculados da API** → **Sintoma: dados divergentes entre bot e website (ex: bot mostrava ausentes=166 ao invés de 172, nao_alimentados=43 ao invés de 39). A API Aluno Presente retorna `alunos_ausentes`, `percentual_ausencia`, `nao_alimentados` e `percentual_nao_alimentados` pré-calculados, mas o código recalculava tudo manualmente: `ausentes = expectativaPresenca - alunos_presentes` (diferente do cálculo da API que considera ausências justificadas), `nao_alimentados = alunos_presentes - alunos_alimentados`, e porcentagens derivadas desses valores incorretos. Corrigido em 2 métodos: (1) `extract_single_unit()` agora usa `unit.get('alunos_ausentes', fallback)`, `unit.get('percentual_ausencia', fallback)`, `unit.get('nao_alimentados', fallback)`, `unit.get('percentual_nao_alimentados', fallback)`; (2) `_fetch_api_data()` agora soma `alunos_ausentes`, `nao_alimentados` e `alunos_sem_foto` diretamente da API em vez de subtrair. Validação real: unit 75 agora mostra ausentes=172 (antes 166), nao_alimentados=39 (antes 43), percentuais alinhados com a API.**
- [x] **BUG #10**: Cálculo de AUSENTES divergia do website (54 vs 47 para unit 75) → **Causa: o campo `alunos_ausentes` da API é `total_alunos - presentes` (conta alunos não esperados), mas o website calcula AUSENTES como `expectativaPresenca - presentes` (apenas alunos ausentes que deveriam estar presentes). Para unit 75: API retornava `alunos_ausentes=54` (359-305) mas website mostrava 47 (352-305). Resultado: bot mostrava 54 ausentes (15,0%) enquanto website mostrava 47 (13,4%). Corrigido: `extract_single_unit()` agora calcula `ausentes = expectativaPresenca - presentes` e `ausentes_pct` proporcionalmente; `_fetch_api_data()` soma `expectativaPresenca - presentes` por unidade. Validação: unit 75 agora mostra 47 ausentes (13,4%), idêntico ao website.**

## Pendentes

- [x] Testes automatizados (Django test runner) para scheduler, extractors, messaging, services
- [ ] CI/CD pipeline (lint, typecheck, test no GitHub Actions)
- [ ] Monitoramento: health check endpoint + métricas Prometheus
- [x] Documentação de API (Swagger/OpenAPI via Django Ninja em `/api/docs`)

## Análise de Código — 14/08/2026

### Verificado (já resolvido / confirmado)

- [x] Scheduler como serviço Docker dedicado (`aluno_presente_scheduler`) com APScheduler + `DjangoJobStore` persistente
- [x] Reconciliação de jobs: `sync_jobs_from_db()` no `run_scheduler` corrige configs editadas/desativadas sem depender só do sinal
- [x] Alertas de falha do agendamento via Telegram (`_notify_failure` → `TELEGRAM_ADMIN_CHAT_ID` ou destinatários ativos)
- [x] Arquitetura de extratores por plugin (registry): `aluno_presente` e `generic`, com fallback Playwright
- [x] `list_site_types` exposto na API (`/api/site-types/`)
- [x] Testes presentes: `test_scheduler`, `test_messaging`, `test_services`, `test_extractors`, `test_security` (rodar com `manage.py test`)
- [x] Re-login automático no 401 com fallback garantido para Playwright
- [x] Offset do listener Telegram persistido em volume (`telegram_offset.txt`), um único poller
- [x] **BUG #7 corrigido**: fallback Playwright garante sessão autenticada (`_ensure_authenticated_page`), relogin inicial para obter token e erro claro em campo sem selector (sem `page.url` silencioso)
- [x] Validação ao vivo em 14/08/2026: preview (`/api/execute/`) passou a extrair métricas reais (presentes/ausentes/alimentados) após re-login automático; `storage_state.json` regenerado com `aluno-presente-token`
- [x] 61/61 testes passando (18 de segurança), `manage.py check` sem issues
- [x] **BUG #8 corrigido (18/08/2026)**: Telegram listener (`/unidades`, `/unidade`) agora trata 401 com re-login automático, replicando o padrão da `ExtractionSkill`
- [x] **BUG #9 corrigido (18/08/2026)**: `extract_single_unit()` e `_fetch_api_data()` agora usam campos pré-calculados da API (`alunos_ausentes`, `percentual_ausencia`, `nao_alimentados`, `percentual_nao_alimentados`) em vez de recalcular manualmente — dados agora alinhados com o website
- [x] **BUG #10 corrigido (18/08/2026)**: AUSENTES calculado como `expectativaPresenca - presentes` em vez de usar campo `alunos_ausentes` da API (que é `total_alunos - presentes`) — bot agora mostra mesmos valores que o website (ex: unit 75 = 47 ausentes, 13,4%)

### Investigação da API Aluno Presente — 17/08/2026

#### Endpoints Descobertos

| Endpoint | Método | Dados |
|----------|--------|-------|
| `/api/dashboard-secretario/unidades/todas` | GET | Lista simples `[{id, nome}]` — 185 unidades |
| `/api/dashboard-secretario/buscar-unidades-escolares-disponiveis` | GET | Detalhes completos — 185 unidades (id, nome, inep, endereco, regiao, etc.) |
| `/api/dashboard-secretario/buscar-lista-unidades-escolares?data=...&condicao=ATIVO&page=0&size=1000` | GET | Dados de attendance — 143 unidades ativas (unidade_id, alunos_presentes, etc.) |
| `/api/dashboard-secretario/buscar-dados-cards-principais` | GET | Cards totais (totalUnidadesEscolares, totalTurmas, etc.) |
| `/api/dashboard-secretario/buscar-dados-subcards` | GET | Sub-cards (alunos matutinos, vespertinos, integral) |
| `/api/dashboard-secretario/buscar-regioes-disponiveis` | GET | `["Região Leste", "Região Norte", "Região Oeste", "Região Sul"]` |
| `/api/dashboard-secretario/buscar-periodos-disponiveis` | GET | Períodos (MATUTINO, VESPERTINO, INTEGRAL) |

#### Descobertas Importantes

1. Campo `unidade_id` existe na resposta da API — não era usado no código anterior
2. Não existe endpoint individual por unidade — necessário filtrar da lista completa
3. Filtro por query string (`?unidade_id=103`) é ignorado pela API
4. 143 unidades ativas / 185 total (ativas + inativas)
5. 4 regiões: Leste, Norte, Oeste, Sul
6. API requer autenticação via Bearer token JWT (obtido via Playwright localStorage)
7. Token expira em ~24h; re-login automático já implementado

### Implementação: Consulta por Unidade Escolar Individual — 17/08/2026

#### Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `aluno_presente_sme/skills/extractors/aluno_presente.py` | Adicionados `list_school_units()`, `extract_single_unit()`, parâmetro `unit_ids` em `_fetch_api_data()` e `extract_via_api()` |
| `aluno_presente_sme/models.py` | Campo `school_unit_ids = JSONField(default=list)` no BotConfig |
| `aluno_presente_sme/migrations/0007_...py` | Migration para novo campo |
| `aluno_presente_sme/schemas.py` | `BotExecutionInput.unit_id`, `BotConfigInput/Update/Output.school_unit_ids`, `SchoolUnitOutput` |
| `aluno_presente_sme/skills/extract_skill.py` | Parâmetros `unit_id` e `unit_ids` em `extract()` |
| `aluno_presente_sme/services.py` | `_extract_with_retry()` passa `unit_id` e `unit_ids` para extração |
| `api/endpoints.py` | Endpoint `GET /school-unities/`, `_config_to_dict` com `school_unit_ids` |
| `aluno_presente_sme/management/commands/listen_telegram.py` | Comandos `/unidades`, `/unidade <nome>`, `/unidade_id <id>` |
| `aluno_presente_sme/tests/test_services.py` | Mocks atualizados com parâmetros `unit_id`/`unit_ids` |

#### Comandos Telegram Novos

| Comando | Ação |
|---------|------|
| `/unidades` | Lista todas as 185 unidades (ID + nome) |
| `/unidade <nome>` | Busca fuzzy por nome; se 1 resultado, gera relatório da unidade; se múltiplos, lista correspondências |
| `/unidade_id <id>` | Consulta unidade por ID numérico e gera relatório |

#### Fluxo de Extração por Unidade

```
/unidade EMEB ADELINA
  → list_school_units() via API /unidades/todas
  → fuzzy match no nome
  → se 1 match: extract_single_unit(unit_id=123)
    → busca /buscar-lista-unidades-escolares (143 unidades)
    → filtra por unidade_id == 123
    → formata métricas individuais (presentes, ausentes, alimentados, fotos)
    → renderiza template com dados da unidade
    → envia para o destinatário que solicitou
```

#### Template Individual — Sem Rede/Top10

- Criado **Template 7: "Consulta Unidade Individual"** — exclusivo para buscas por unidade
- Remove seções `🏫 Rede` e `🏆 Top 10 Unidades` que só fazem sentido no relatório completo da rede
- Comandos `/unidade` e `/unidade_id` usam `template_id=7` (hardcoded)
- Alias `/unidadeid` (sem underscore) adicionado para conveniência no celular
- `extract_single_unit()` sempre inclui metadados (`unidade_id`, `unidade_nome`, `inep`, `regiao`) independentemente dos `extraction_fields` configurados
- `_fetch_api_data()` com `unit_ids` exclui campos de rede: `total_unidades`, `total_turmas`, `unidades_ativas`, `alunos_matutinos/vespertinos/integral`, `alunos_especiais`, `alunos_com_foto` e `top1..10_*`

#### Formato da Resposta Individual

```
📊 EMEB ADELINA PEREIRA VENTURA
📅 17/08/2026 — MANHÃ
🆔 ID: 132 | INEP: 35012345 | Região: NORTE

✅ Presenças
Presentes: 45 (85,0%)
Ausentes: 8 (15,0%)

🍽 Alimentação
Alimentados: 40 (88,9%)
Não Alimentados: 5 (11,1%)

📸 Fotos
Com Foto: 42 (84,0%)
Sem Foto: 8 (16,0%)
```

### Novos itens para o backlog (pendências encontradas na análise)

- [ ] **BUG**: IDs de template hardcoded no listener (`listen_telegram.py:97,100,103`) — quebra se o seed mudar; buscar pelo nome (`MessageTemplate.objects.get(name=...)`)
- [ ] **SEGURANÇA**: `verify=False` no `httpx.AsyncClient` de `extractors/aluno_presente.py:56` — desativa verificação TLS; substituir por CA confiável ou `ssl` context custom
- [ ] **CONTRATO**: `BotConfigOutput.extraction_fields` tipado como `list[str]`, mas o model/schema aceita dicts (`{"field_name", "selector"}`) — alinhar contrato Pydantic
- [ ] **PERF**: `/api/stats/` calcula agregações em Python (loop) — migrar para aggregates do ORM (`Avg`, `Sum`, `TruncDate`)
- [ ] **REFAC**: duplicação de `list_configs` e `_config_to_dict` em `endpoints.py` — unificar
- [ ] **OPS**: `CSRF_TRUSTED_ORIGINS` só em `settings.py` com IP fixo `10.62.30.165`; mover para `.env`/`.env.example` com nota de porta
- [ ] **ROBUSTEZ**: `_detect_site_type` em `extract_skill.py` usa substring `'alunopresente'` — usar `matches_url()` do registry para novos sites
- [ ] **QUALIDADE**: rodar testes via `manage.py test aluno_presente_sme.tests` no CI; avaliar migração para pytest + cobertura (coverage.py)
- [ ] **OBS**: `extract_via_api` formata métricas como strings pt-BR já renderizadas; manter contratos tipados (int/float) e formatar só no template