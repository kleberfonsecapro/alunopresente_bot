<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Django-5.0%2B-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 5.0+"/>
  <img src="https://img.shields.io/badge/Django%20Ninja-1.1%2B-FF6600?style=for-the-badge&logo=fastapi&logoColor=white" alt="Django Ninja"/>
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL 15"/>
  <img src="https://img.shields.io/badge/Playwright-1.42%2B-45BA4B?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright"/>
  <img src="https://img.shields.io/badge/Pydantic-2.6%2B-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/Nginx-1.25-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="Nginx"/>
  <img src="https://img.shields.io/badge/httpx-0.27%2B-FF6633?style=for-the-badge&logo=python&logoColor=white" alt="httpx"/>
  <img src="https://img.shields.io/badge/Jinja2-3.1%2B-B41717?style=for-the-badge&logo=jinja&logoColor=white" alt="Jinja2"/>
  <img src="https://img.shields.io/badge/Rate%20Limiting-Enabled-00AA00?style=for-the-badge" alt="Rate Limiting"/>
</p>

# Aluno Presente Bot

**Bot de raspagem agêntico, headless e spec-driven** — extrai dados de plataformas educacionais via API interna ou Playwright e dispara mensagens no Telegram com relatórios consolidados.

---

## Índice

- [Arquitetura](#arquitetura)
- [Stack Tecnológica](#stack-tecnológica)
- [Funcionalidades](#funcionalidades)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Executar](#como-executar)
- [Configuração](#configuração)
- [API](#api)
- [Skills de Automação](#skills-de-automação)
- [Segurança](#segurança)
- [Testes](#testes)

---

## Arquitetura

O sistema segue uma arquitetura **headless** (backend e frontend totalmente desacoplados) com **spec-driven development** — contratos Pydantic definem entradas e saídas antes da implementação. Um **agente orquestrador** coordena skills isoladas de automação (Playwright) para executar o pipeline completo.

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Frontend   │────▶│   Django     │────▶│   PostgreSQL     │
│  (HTML/CSS)  │     │   Ninja API  │     │   (ORM Django)   │
└─────────────┘     └──────┬───────┘     └──────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Skills       │
                    │  (Playwright) │
                    │  + httpx API  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Site Alvo    │
                    │  (Educacional)│
                    └──────────────┘
```

### Fluxo de Execução

1. **Scheduler** verifica a cada minuto se há configurações pendentes
2. **BotOrchestrator** coordena a execução
3. **AuthenticationSkill** faz login no site alvo (com persistência de sessão)
4. **ExtractionSkill** coleta dados via API interna ou Playwright (fallback)
5. **MessagingSkill** aplica template Jinja2 e dispara via Telegram
6. **ExecutionLog** registra resultado completo no banco

---

## Stack Tecnológica

| Categoria | Tecnologia | Versão | Finalidade |
|-----------|-----------|--------|------------|
| **Linguagem** | Python | 3.11+ | Runtime principal |
| **Framework Web** | Django | 5.0+ | ORM, Admin, Sessões, Segurança |
| **API REST** | Django Ninja | 1.1+ | Spec-driven, validação Pydantic |
| **Validação** | Pydantic | 2.6+ | Contratos de dados, schemas |
| **Banco** | PostgreSQL | 15 | Persistência principal |
| **Automação** | Playwright | 1.42+ | Navegação headless (Chromium) |
| **HTTP Client** | httpx | 0.27+ | Chamadas assíncronas à API interna |
| **Templates** | Jinja2 | 3.1+ | Renderização de mensagens dinâmicas |
| **Proxy** | Nginx | Alpine | Reverse proxy, headers de segurança |
| **Container** | Docker + Compose | — | Orquestração dos serviços |
| **Rate Limit** | django-ratelimit | 4.1+ | Proteção contra brute force |

---

## Funcionalidades

### Raspagem e Extração
- ✅ Extração via **API interna do site alvo** (3 endpoints em paralelo)
- ✅ Cálculo de ausentes usando `expectativaPresenca`
- ✅ Fallback automático para **Playwright headless** quando API falha
- ✅ Re-login automático quando token expira (401 → reautentica)
- ✅ Timeout configurável (60s) com retry + re-login

### Relatórios
- ✅ Presentes, ausentes, alimentados, não alimentados, com/sem foto
- ✅ Porcentagens em todas as métricas
- ✅ Formatação pt-BR (ponto milhar, vírgula decimal)
- ✅ Top 10 unidades por presença
- ✅ Período do dia (manhã/tarde/noite) nos relatórios

### Agendamento
- ✅ **Scheduler preciso** com polling a cada minuto (sem drift)
- ✅ Agendamento flexível por dia da semana e horário
- ✅ **Catch-up automático**: recupera execuções perdidas (até 3h)
- ✅ Duração configurável (dias) para campanhas
- ✅ Modo preview (extração sem envio)

### Disparo
- ✅ **Telegram** com suporte a Markdown
- ✅ Templates dinâmicos com Jinja2 (`{{variavel}}`)
- ✅ Múltiplos destinatários por execução
- ✅ Comandos: `/relatorio_completo`, `/resumo_secretaria`, `/resumo_diario`
- ✅ Menu de comandos registrado automaticamente

### Painel de Controle
- ✅ CRUD de configurações (BotConfig)
- ✅ CRUD de templates de mensagem
- ✅ CRUD de destinatários
- ✅ Histórico de execuções com duração e status
- ✅ Estatísticas (taxa de sucesso, médias, últimos 7 dias)
- ✅ Integração com Django Admin

### Segurança
- ✅ Autenticação por sessão Django (cookies `HttpOnly` + `SameSite`)
- ✅ **Rate limiting**: 10 tentativas/minuto no login
- ✅ **Timeout de sessão**: 8h, expira ao fechar navegador
- ✅ **DEBUG=False** em produção
- ✅ **Security headers** no Nginx (X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
- ✅ Senha do superusuário via variável de ambiente (fallback aleatório seguro)
- ✅ `ALLOWED_HOSTS` sanitizado

---

## Estrutura do Projeto

```
├── docker-compose.yml          # Orquestração Docker
├── Dockerfile                  # Build da imagem backend
├── entrypoint.sh               # Script de inicialização
├── nginx.conf                  # Configuração do proxy reverso
├── requirements.txt            # Dependências Python
├── .env.example                # Template de variáveis de ambiente
│
├── backend/
│   ├── manage.py
│   ├── core/                   # Configurações Django
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── views.py
│   │
│   ├── api/                    # API REST (Django Ninja)
│   │   ├── api.py              # Instância NinjaAPI
│   │   ├── auth.py             # Endpoints de autenticação
│   │   ├── endpoints.py        # Endpoints protegidos
│   │   └── urls.py
│   │
│   ├── scraper_bot/            # App principal
│   │   ├── models.py           # BotConfig, MessageTemplate, Recipient, ExecutionLog
│   │   ├── schemas.py          # Contratos Pydantic
│   │   ├── services.py         # Orquestração (BotOrchestrator)
│   │   ├── admin.py            # Registro no Django Admin
│   │   │
│   │   ├── skills/             # Módulos de automação
│   │   │   ├── auth.py         # AuthenticationSkill (login no site alvo)
│   │   │   ├── auth_skill.py   # Persistência de sessão (storage_state)
│   │   │   ├── extract_skill.py# ExtractionSkill (API + Playwright)
│   │   │   ├── navigation_skill.py # NavigationSkill (navegação DOM)
│   │   │   └── messaging_skill.py  # MessagingSkill (Telegram)
│   │   │
│   │   ├── management/commands/
│   │   │   ├── scheduler.py    # Agendador preciso
│   │   │   ├── listen_telegram.py # Listener Telegram
│   │   │   └── run_bot.py      # Execução manual
│   │   │
│   │   └── tests/
│   │       └── test_security.py # Testes de segurança
│   │
│   └── frontend/               # Frontend estático
│       ├── templates/
│       │   ├── login.html
│       │   ├── dashboard.html
│       │   └── logout.html
│       └── static/
│
└── playwright_state/           # Volume Docker (sessão do navegador)
```

---

## Como Executar

### Pré-requisitos

- Docker + Docker Compose
- Git

### Passo a passo

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/aluno-presente-bot.git
cd aluno-presente-bot

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais

# Construa e inicie os serviços
docker compose up -d

# Acesse:
# - Painel:   http://localhost:8080
# - Admin:    http://localhost:8080/admin/
# - API Docs: http://localhost:8080/api/docs
```

### Serviços

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| **Nginx** | `8080` | Proxy reverso + arquivos estáticos |
| **Backend** | `8000` | Django + API Ninja (interno) |
| **PostgreSQL** | `5432` | Banco de dados (interno) |

### Comandos úteis

```bash
# Logs do scheduler
docker logs scraper_backend | grep -E "\[2026"

# Executar o bot manualmente
docker exec scraper_backend python manage.py run_bot --config-id 1

# Ver execuções recentes
docker exec scraper_backend python -c "
import django, os
os.environ['DJANGO_SETTINGS_MODULE']='core.settings'
django.setup()
from scraper_bot.models import ExecutionLog
for log in ExecutionLog.objects.all().order_by('-started_at')[:5]:
    print(log.id, log.trigger, log.success, log.started_at, log.sent_count)
"

# Testes
docker exec scraper_backend python manage.py test scraper_bot.tests
```

---

## Configuração

### Variáveis de Ambiente (`.env`)

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `POSTGRES_DB` | Nome do banco | `scraper_bot` |
| `POSTGRES_USER` | Usuário do banco | `postgres` |
| `POSTGRES_PASSWORD` | Senha do banco | `senha_segura` |
| `DJANGO_SECRET_KEY` | Chave secreta Django | `gerar-uma-chave-aleatoria` |
| `DJANGO_SUPERUSER_PASSWORD` | Senha do admin | `senha_forte` |
| `DEBUG` | Modo debug | `False` |
| `ALLOWED_HOSTS` | Hosts permitidos | `localhost,127.0.0.1` |
| `TARGET_SITE_URL` | URL do site alvo | `https://site.exemplo.com/login` |
| `TARGET_SITE_USER` | Usuário no site alvo | `seu_email` |
| `TARGET_SITE_PASSWORD` | Senha no site alvo | `sua_senha` |
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram | `123456:ABC-DEF` |

### Modelos de Dados

#### BotConfig
Define **o quê**, **quando** e **como** extrair:
- `name` — Nome da configuração
- `target_url` — URL do site alvo
- `extraction_fields` — Campos a extrair
- `send_times` — Horários de disparo (ex: `["08:00", "14:00"]`)
- `send_days_of_week` — Dias da semana (0=segunda, 6=domingo)
- `send_duration_days` — Duração em dias (null = indeterminado)
- `template` — Template de mensagem vinculado

#### MessageTemplate
Armazena o **texto** da mensagem com variáveis Jinja2:
```jinja2
📊 *Visão Secretaria - Aluno Presente*
📅 {{data_envio}} — {{periodo|upper}}

✅ *Presentes:* {{presentes}} ({{presentes_pct}}%)
❌ *Ausentes:* {{ausentes}} ({{ausentes_pct}}%)
```

#### Recipient
Destinatário dos disparos:
- `name` — Nome de exibição
- `identifier` — ID do chat (Telegram)
- `platform` — Plataforma (`telegram`)
- `is_active` — Ativo/inativo

---

## API

A API segue o padrão **RESTful** com documentação automática via Swagger.

### Autenticação

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/auth/login/` | Login (rate limited: 10/min) |
| `POST` | `/api/auth/logout/` | Logout |
| `GET` | `/api/auth/me/` | Sessão atual |

### Configurações

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/configs/` | Listar configurações |
| `POST` | `/api/configs/` | Criar configuração |
| `PATCH` | `/api/configs/{id}/` | Atualizar configuração |
| `DELETE` | `/api/configs/{id}/` | Excluir configuração |

### Execução

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/execute/` | Executar bot (preview ou envio real) |

### Templates e Destinatários

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET/POST` | `/api/templates/` | Listar/criar templates |
| `PATCH/DELETE` | `/api/templates/{id}/` | Atualizar/excluir template |
| `GET/POST` | `/api/recipients/` | Listar/criar destinatários |
| `PATCH/DELETE` | `/api/recipients/{id}/` | Atualizar/excluir destinatário |

### Histórico e Estatísticas

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/logs/` | Últimas 50 execuções |
| `GET` | `/api/stats/` | Estatísticas consolidadas |

### Skills Individuais

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/auth/login-site/` | Login no site alvo |
| `POST` | `/api/auth/relogin/` | Re-login automático |
| `POST` | `/api/extract/` | Extração de dados |
| `POST` | `/api/navigate/` | Navegação Playwright |
| `POST` | `/api/send/` | Envio de mensagem |

---

## Skills de Automação

O sistema utiliza uma arquitetura de **skills isoladas**, cada uma com responsabilidade única:

### AuthenticationSkill
- Login no site alvo via Playwright
- Persistência de sessão em volume Docker (`storage_state.json`)
- Reutilização de cookies entre execuções
- Re-login automático em caso de expiração

### NavigationSkill
- Navegação headless com Playwright
- Espera por seletores DOM
- Scroll até o fim da página

### ExtractionSkill
- Extração via **API interna** (3 endpoints em paralelo com httpx)
- Fallback para **Playwright** quando API não está disponível
- Re-login automático em 401
- **Retry automático** (2 tentativas com renovação de sessão)
- Cálculo de métricas: presentes, ausentes, alimentados, fotos

### MessagingSkill
- Renderização de templates Jinja2 com dados extraídos
- Disparo em lote para múltiplos destinatários
- Suporte a plataformas (Telegram)
- Contagem de sucessos e falhas

### BotOrchestrator
- Coordena as skills na ordem correta
- Verifica agendamento (dia, horário, duração)
- Cria e atualiza logs de execução
- Suporta modo preview e envio real

---

## Segurança

### Autenticação
- Sessão Django com cookies `HttpOnly` + `SameSite=Lax`
- Login com **rate limiting** (10 tentativas/minuto por IP)
- Timeout de sessão: **10 minutos** (configurável via `SESSION_COOKIE_AGE`)
- Sessão expira ao fechar o navegador

### Infraestrutura
- `DEBUG=False` em produção
- `ALLOWED_HOSTS` sanitizado (sem wildcards)
- Nginx com security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy` restritivo

### Credenciais
- Senha do superusuário Django via variável de ambiente (`DJANGO_SUPERUSER_PASSWORD`)
- Fallback para senha aleatória segura (`secrets.token_urlsafe`)
- Credenciais do site alvo armazenadas em `.env` (não versionado)
- Token do Telegram armazenado em `.env` (não versionado)

### Sessão do Navegador
- Sessão Playwright persistida em volume Docker dedicado
- Re-login automático quando token expira

---

## Testes

```bash
# Executar todos os testes
docker exec scraper_backend python manage.py test scraper_bot.tests

# Testes específicos
docker exec scraper_backend python manage.py test scraper_bot.tests.test_security
```

### Cobertura

| Categoria | Testes | O que verificam |
|-----------|--------|-----------------|
| **Configurações** | 6 | Timeout de sessão, DEBUG, ALLOWED_HOSTS, CSRF |
| **Autenticação** | 6 | Login, logout, sessão, credenciais inválidas |
| **Rate Limiting** | 2 | Bloqueio após 10 tentativas, login válido não bloqueado |
| **Código morto** | 1 | NINJA_JWT removido |

---

## Licença

Este projeto é de uso interno. Distribuição e modificação sujeitas à autorização.

---

<p align="center">
  <sub>Feito com Python, Django, Playwright e muito café</sub>
</p>
