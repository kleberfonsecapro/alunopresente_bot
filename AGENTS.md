# Contexto do Projeto: Bot de Raspagem Agêntico (Headless & Spec-Driven)

## 1. Identidade e Comportamento da IA
Você é um Engenheiro de Software Sênior especialista em Python, Django, Segurança (OAuth2), Clean Code, e arquiteturas baseadas em Agentes de IA.
Sua missão é desenvolver e manter um bot de raspagem de dados e disparo de mensagens.
Regra Zero: Você NUNCA deve inventar bibliotecas, quebrar as regras de segurança descritas ou mudar a stack tecnológica sem permissão explícita. Siga estritamente os contratos Pydantic.

## 2. Stack Tecnológica Obrigatória
*   **Backend:** Python 3.11+, Django, Django Ninja (para API RESTful e Spec-Driven).
*   **Banco de Dados:** PostgreSQL (ORM do Django).
*   **Raspagem/Automação:** Playwright (modo headless) com persistência de sessão.
*   **Validação e Contratos:** Pydantic (tipagem estrita e outputs do Agente LLM).
*   **Frontend:** HTML5, CSS e JS vanilla/moderno (totalmente desacoplado, Headless).
*   **Infraestrutura:** Docker e Docker Compose (isolamento total).

## 3. Regras de Segurança e Autenticação (CRÍTICO)
*   **Acesso ao Sistema (OAuth2):** Implementar o padrão BFF (Backend For Frontend). Todo o fluxo OAuth2 ocorre no Django. O frontend recebe a sessão APENAS via cookies marcados como `HttpOnly`, `Secure` e `SameSite=Lax/Strict`. É EXPRESSAMENTE PROIBIDO armazenar tokens de acesso no `localStorage` ou `sessionStorage` do frontend.
*   **Credenciais do Site Alvo:** O login e a senha do site que será raspado NUNCA devem ser inseridos no código (hardcoded). Devem ser gerenciados via variáveis de ambiente (`.env`) ou armazenados em campos criptografados no banco de dados.
*   **Sessão do Playwright:** A `AuthenticationSkill` deve salvar o estado do navegador (cookies do site alvo) em um volume Docker, reutilizando a sessão para evitar múltiplos logins e bloqueios.

## 4. Modelagem e Parametrização (Painel de Controle)
O backend deve fornecer APIs para o frontend configurar o comportamento do bot, incluindo os seguintes modelos no banco:
*   `BotConfig`: Define quais campos de informação o Agente deve extrair na execução atual.
*   `MessageTemplate`: Armazena o texto padrão com variáveis dinâmicas (ex: "Resultado: {{dado_raspado}}").
*   `Recipient`: Lista de números, identificadores (como IDs de chat de plataformas de mensagens) ou contatos que receberão os disparos.

## 5. Arquitetura de Skills (Playwright & Clean Code)
Os scripts de automação são isolados por responsabilidade:
*   `AuthenticationSkill`: Lida apenas com o login seguro no site alvo e salva a sessão.
*   `NavigationSkill`: Roteamento, scroll e espera por elementos da DOM.
*   `ExtractionSkill`: Extração cognitiva, devolvendo os dados em conformidade estrita com o Schema Pydantic.
*   `MessagingSkill`: Aplica os dados extraídos no `MessageTemplate` e realiza o disparo para os contatos cadastrados no `Recipient`.

## 6. Ordem de Execução (Workflow Padrão)
1.  Definir o Schema Pydantic do Contrato (Entrada/Saída).
2.  Criar a rota protegida no Django Ninja.
3.  Escrever as `Skills` isoladas para a funcionalidade.
4.  Configurar o Agente de IA para operar as Skills respeitando o Contrato.
5.  Testar a parametrização a partir do painel (Frontend).

## 7. Estrutura de Diretórios Esperada
/
├── docker-compose.yml
├── Dockerfile
├── .env.example              # Para credenciais do site alvo e chaves
├── requirements.txt
├── backend/                  
│   ├── core/                 # Configurações Django, Middleware JWT/Cookie
│   ├── api/                  # Endpoints Django Ninja (Protegidos)
│   ├── aluno_presente_sme/          
│   │   ├── models.py         # Schemas Postgres (Config, Templates, Recipients)
│   │   ├── schemas.py        # Contratos Pydantic
│   │   ├── services.py       # Orquestração do Agente e mensageria
│   │   └── skills/           # Módulos Playwright
│   │       ├── auth_skill.py
│   │       ├── extract_skill.py
│   │       └── messaging_skill.py
└── frontend/                 
    ├── index.html            # Tela de Login (OAuth2)
    └── dashboard.html        # Painel de parametrização

## 8. Estrutura Real Implementada (14/08/2026)

```
bot-alunop/
├── docker-compose.yml        # Serviços: db, backend, scheduler, listener, nginx
├── Dockerfile
├── entrypoint.sh
├── nginx.conf                # Proxy reverso :8080 + security headers
├── requirements.txt
├── .env.example              # Credenciais do site alvo e chaves
├── backlog.md                # Backlog do projeto (tarefas concluídas e pendentes)
│
├── backend/
│   ├── manage.py
│   ├── core/
│   │   ├── settings.py       # TIME_ZONE='America/Cuiaba', sessão 10min, HttpOnly+SameSite=Lax
│   │   ├── urls.py
│   │   └── views.py          # login/dashboard/logout (templates server-side)
│   │
│   ├── api/                  # Django Ninja (SessionAuth em endpoints.py)
│   │   ├── api.py            # Instância NinjaAPI
│   │   ├── auth.py           # POST /auth/login/ (rate limited), /logout/, /me/
│   │   ├── endpoints.py      # CRUD configs/templates/recipients + /execute/ + skills
│   │   └── urls.py
│   │
│   ├── aluno_presente_sme/
│   │   ├── models.py         # BotConfig, MessageTemplate, Recipient, ExecutionLog
│   │   ├── schemas.py        # Contratos Pydantic (input/output/execute/stats)
│   │   ├── services.py       # BotOrchestrator (execução, retry, preview, log)
│   │   ├── scheduler.py      # APScheduler + DjangoJobStore + sync_jobs_from_db
│   │   ├── signals.py        # post_save/post_delete → agenda/remove jobs
│   │   ├── admin.py
│   │   │
│   │   ├── skills/
│   │   │   ├── auth.py               # AuthenticationSkill (login no site alvo)
│   │   │   ├── auth_skill.py         # persistência/leitura do storage_state.json
│   │   │   ├── extract_skill.py      # ExtractionSkill (escolhe extrator por site_type)
│   │   │   ├── messaging_skill.py    # MessagingSkill (Jinja2 + Telegram, 10 concorrentes)
│   │   │   ├── navigation_skill.py   # NavigationSkill (Playwright)
│   │   │   └── extractors/           # PLUGIN REGISTRY (adicionar novo site aqui)
│   │   │       ├── base.py           # SiteExtractor + helpers de sessão (_ensure_authenticated_page, _is_login_page, _extract_dom_value)
│   │   │       ├── registry.py       # @register / get_extractor / list_site_choices
│   │   │       ├── aluno_presente.py # Aluno Presente (API interna 3 endpoints paralelos)
│   │   │       └── generic.py        # Genérico (Playwright)
│   │   │
│   │   ├── management/commands/
│   │   │   ├── run_scheduler.py      # serviço aluno_presente_scheduler (heartbeat 60s)
│   │   │   ├── listen_telegram.py    # serviço aluno_presente_listener (poller único + offset)
│   │   │   └── run_bot.py            # execução manual
│   │   │
│   │   └── tests/
│   │       ├── test_scheduler.py
│   │       ├── test_messaging.py
│   │       ├── test_services.py
│   │       ├── test_extractors.py
│   │       └── test_security.py
│   │
│   ├── frontend/             # templates/ (login, dashboard, logout) + static/ (admin copiado)
│   └── scripts/              # explore_page.py, find_analise_api.py (análise do site alvo)
│
└── playwright_state/         # volume Docker (storage_state.json, telegram_offset.txt)
```

## 9. Comandos e Fluxos

*   **Rodar tudo:** `docker compose up -d` → Painel `:8080`, Admin `:8080/admin/`, Docs `:8080/api/docs`.
*   **Serviços:** `aluno_presente_backend` (runserver :8000), `aluno_presente_scheduler` (run_scheduler), `aluno_presente_listener` (listen_telegram), `aluno_presente_nginx` (:8080), `aluno_presente_db` (postgres:15-alpine).
*   **Execução manual:** `docker exec aluno_presente_backend python manage.py run_bot --config-id 1`.
*   **Testes:** `docker exec aluno_presente_backend python manage.py test aluno_presente_sme.tests`.
*   **Pipeline de execução:** Scheduler → `execute_scheduled_job` → `BotOrchestrator.execute` → `ExtractionSkill` (API → fallback Playwright) → `MessagingSkill.send_bulk` → `ExecutionLog`.
*   **Adicionar novo site alvo:** 1) criar `extractors/meu_site.py` com `@register` e `site_type`; 2) herdar `SiteExtractor`; 3) expor no `site_type` do `BotConfig`; 4) atualizar `_detect_site_type` ou usar `matches_url()`.

## 10. Regras e Cuidados ao Alterar Código

*   **NUNCA hardcodear IDs de template no listener** (`listen_telegram.py` usa 1, 3, 4) — buscar por nome estável.
*   **NUNCA desabilitar verificação TLS** (`verify=False` em `aluno_presente.py`) sem substituir por CA confiável.
*   **Fallback Playwright é seguro por construção:** use `_ensure_authenticated_page` (relogin automático + erro claro se o login persistir). **NUNCA retorne `page.url` como valor de campo** — campo sem selector deve levantar erro (Aluno Presente) ou virar `None` (Genérico), nunca virar a URL da página.
*   **`ExtractionSkill.extract`** já tenta `relogin()` inicial quando não há token e o site define `login_url`. Novos extratores com login devem definir `login_url` e implementar `relogin()`; sites públicos (sem login) devem deixar `login_url` vazio para não disparar re-login.
*   **Não quebrar os contratos Pydantic** em `schemas.py`; qualquer mudança exige atualizar o schema e a doc gerada em `/api/docs`.
*   **Async:** skills e `BotOrchestrator` são async; ORM síncrono só via `sync_to_async` (padrão já usado em `services.py`).
*   **Scheduler:** edições em `BotConfig` no container backend só afetam os jobs no container scheduler após o próximo `sync_jobs_from_db()` (heartbeat de 60s). Testes que mexem em jobs devem resetar `sched_mod._last_signature = None`.
*   **Formatos de saída:** `aluno_presente.py` já entrega métricas formatadas em pt-BR (string). Ao criar extratores novos, manter a saída tipada e formatar no template.
*   **Migrations:** o `site_type` do `BotConfig` usa choices dinâmicas do registry; novos sites não exigem migration.
*   **Testes existentes rodam com `manage.py test`** (Django TestCase), não pytest.
