# Relatório Técnico — Aluno Presente SME

**Automação de Coleta de Dados e Disparo de Relatórios Educacionais**

---

## 1. Visão Geral

A ferramenta **Aluno Presente SME** é uma automação agêntica, headless e spec-driven, desenvolvida para a Secretaria Municipal de Educação de Cuiabá. Seu objetivo é coletar automaticamente dados de frequência alimentar e escolar a partir da plataforma Aluno Presente, consolidar métricas e disparar relatórios periódicos via Telegram para gestores e secretários de educação.

A automação elimina o processo manual de acesso ao dashboard, extração de dados e envio de relatórios, reduzindo tempo de trabalho, erros humanos e garantindo entregas consistentes nos horários definidos.

---

## 2. Funcionalidades

### 2.1 Coleta de Dados

| Funcionalidade | Descrição |
|----------------|-----------|
| **Extração via API interna** | Acessa 3 endpoints da plataforma Aluno Presente em paralelo (httpx assíncrono), obtendo dados de 143 unidades escolares ativas |
| **Fallback Playwright** | Quando a API indisponível, o sistema navega headless no dashboard via Chromium, extraindo dados diretamente do DOM |
| **Re-login automático** | Ao detectar expiração de token (HTTP 401), a automação reautentica automaticamente sem intervenção humana |
| **Persistência de sessão** | Cookies do navegador são salvos em volume Docker, evitando logins repetidos e bloqueios |
| **Cálculo de métricas** | Presentes, ausentes, alimentados, não alimentados, com/sem foto — todas com porcentagens |
| **Filtro por período** | Suporte a turnos: Matutino, Vespertino, Integral, Noturno |
| **Consulta por unidade** | Extração individual de qualquer escola por ID ou nome (busca fuzzy) |

### 2.2 Relatórios

| Relatório | Conteúdo |
|-----------|----------|
| **Relatório Completo** | Visão geral da rede: totais, Top 10 unidades, métricas consolidadas |
| **Resumo Secretaria** | Visão consolidada para a Secretaria de Educação |
| **Resumo Diário** | Métricas do dia corrente |
| **Consulta Unidade** | Dados individuais de uma escola específica |

Todos os relatórios incluem formatação pt-BR (vírgula decimal, ponto milhar) e período do dia.

### 2.3 Agendamento

| Recurso | Detalhe |
|---------|---------|
| **Scheduler preciso** | APScheduler com DjangoJobStore persistente, sem drift |
| **Horários configuráveis** | Múltiplos horários por configuração (ex: 09:00 e 15:00) |
| **Dias da semana** | Seleção quais dias executar (segunda a domingo) |
| **Catch-up automático** | Recupera execuções perdidas em caso de indisponibilidade (janela de 3 horas) |
| **Duração configurável** | Limite de dias para campanhas temporárias |
| **Modo preview** | Executa coleta sem enviar mensagens (validação) |

### 2.4 Disparo de Mensagens

| Recurso | Detalhe |
|---------|---------|
| **Plataforma** | Telegram (API nativa) |
| **Templates dinâmicos** | Variáveis Jinja2 renderizadas com os dados coletados |
| **Múltiplos destinatários** | Um relatório pode ser enviado para vários contatos simultaneamente |
| **Comandos interativos** | `/relatorio_completo`, `/resumo_secretaria`, `/resumo_diario`, `/unidades`, `/unidade <nome>`, `/status`, `/configuracoes`, `/help` |
| **Registro automático** | Usuários se cadastram automaticamente ao enviar `/start` |
| **Retry com backoff** | Até 3 tentativas de envio com verificação de resposta |

### 2.5 Painel de Controle

| Recurso | Detalhe |
|---------|---------|
| **Dashboard web** | Interface para configurar a automação, templates e destinatários |
| **CRUD completo** | Configurações, templates de mensagem e destinatários |
| **Histórico de execuções** | Log detalhado com status, duração, erros e dados extraídos |
| **Estatísticas** | Taxa de sucesso, médias de duração, gráfico dos últimos 7 dias |
| **Django Admin** | Painel administrativo integrado para gerenciamento avançado |
| **API REST** | Documentação automática via Swagger em `/api/docs` |

### 2.6 Comandos Telegram

| Comando | Ação |
|---------|------|
| `/start` | Registra o usuário e ativa recebimento automático |
| `/stop` | Cancela recebimento automático |
| `/relatorio_completo` | Gera relatório completo da rede |
| `/resumo_secretaria` | Gera resumo para a Secretaria |
| `/resumo_diario` | Gera resumo do dia |
| `/unidades` | Lista todas as 185 unidades escolares |
| `/unidades matutino` | Filtra escolas por período |
| `/unidade <nome>` | Consulta escola específica por nome |
| `/status` | Status da automação (configs, usuários, últimas execuções) |
| `/configuracoes` | Lista configurações ativas com horários |
| `/help` | Lista de comandos disponíveis |

---

## 3. Arquitetura

### 3.1 Stack Tecnológica

| Camada | Tecnologia | Função |
|--------|-----------|--------|
| Runtime | Python 3.11+ | Linguagem principal |
| Framework | Django 5.0+ | ORM, admin, sessões, segurança |
| API | Django Ninja | REST spec-driven com validação Pydantic |
| Banco | PostgreSQL 15 | Persistência de dados |
| Automação | Playwright (Chromium) | Navegação headless no site alvo |
| HTTP | httpx | Chamadas assíncronas à API interna |
| Templates | Jinja2 | Renderização de mensagens dinâmicas |
| Proxy | Nginx | Reverse proxy e headers de segurança |
| Orquestração | Docker Compose | Isolamento e gerenciamento de serviços |
| Agendamento | APScheduler | Execução agendada com persistência |

### 3.2 Serviços

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │   Nginx  │  │ Backend  │  │Scheduler │  │Listener │ │
│  │  :8080   │→ │  :8000   │  │ (crontab)│  │Telegram │ │
│  │  Proxy   │  │  Django  │  │          │  │  Poller │ │
│  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│                      │             │              │      │
│                ┌─────▼─────────────▼──────────────▼──┐  │
│                │          PostgreSQL :5432             │  │
│                │    (configs, templates, logs)        │  │
│                └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

| Serviço | Container | Função |
|---------|-----------|--------|
| **Nginx** | `aluno_presente_nginx` | Proxy reverso, arquivos estáticos, security headers |
| **Backend** | `aluno_presente_backend` | API Django Ninja, dashboard, admin |
| **Scheduler** | `aluno_presente_scheduler` | Execução agendada das automações |
| **Listener** | `aluno_presente_listener` | Polling do Telegram para comandos interativos |
| **Database** | `aluno_presente_db` | PostgreSQL com healthcheck |

### 3.3 Pipeline de Execução

```
Scheduler (cron)
    │
    ▼
BotOrchestrator.execute()
    │
    ├─→ ExtractionSkill.extract()
    │       │
    │       ├─→ API interna (3 endpoints paralelos)
    │       │
    │       └─→ Fallback: Playwright headless
    │               │
    │               └─→ Re-login se 401
    │
    ├─→ MessagingSkill.send_bulk()
    │       │
    │       ├─→ Renderiza template Jinja2
    │       │
    │       └─→ Envia para destinatários Telegram
    │
    └─→ ExecutionLog (banco)
```

### 3.4 Arquitetura de Skills (Plugin Registry)

| Skill | Responsabilidade |
|-------|-----------------|
| **AuthenticationSkill** | Login no site alvo, persistência de sessão |
| **NavigationSkill** | Navegação DOM, scroll, espera por seletores |
| **ExtractionSkill** | Coleta de dados (API + Playwright), cálculo de métricas |
| **MessagingSkill** | Renderização Jinja2, disparo em lote |
| **BotOrchestrator** | Coordenação, agendamento, logs |

O sistema de **Plugin Registry** permite adicionar novos sites alvos criando um extrator que herda de `SiteExtractor` e se registra com `@register`. Atualmente suporta:
- **Aluno Presente** (API interna + fallback Playwright)
- **Genérico** (Playwright puro para qualquer site)

---

## 4. Benefícios

### 4.1 Eficiência Operacional

| Antes (Manual) | Depois (Automação) |
|----------------|-------------------|
| Acesso manual ao dashboard diariamente | Coleta automática nos horários configurados |
| Extração manual de dados de 143 escolas | Extração em paralelo de todas as unidades |
| Cálculo manual de métricas | Métricas calculadas automaticamente |
| Envio manual de relatórios por Telegram | Disparo automático para múltiplos destinatários |
| Tempo estimado: 30-60 min/dia | Tempo de execução: 30-90 segundos |

### 4.2 Redução de Erros

- **Eliminação de erros de cálculo**: Métricas (ausentes, alimentados, fotos) são calculadas pela API ou pelo sistema, não manualmente
- **Formatação consistente**: Todos os relatórios seguem o padrão pt-BR com casas decimais e milhar corretas
- **Dados alinhados com a plataforma**: Após correção dos BUGs #9 e #10, os valores exibidos são idênticos ao dashboard oficial

### 4.3 Confiabilidade

- **Re-login automático**: Não há interrupção quando o token expira (renovação transparente)
- **Retry com backoff**: Falhas de rede são tratadas com até 3 tentativas
- **Catch-up automático**: Execuções perdidas (manutenção, queda de rede) são recuperadas em até 3 horas
- **Health checks**: Containers são monitorados e reiniciados automaticamente (`restart: unless-stopped`)
- **Logs de execução**: Histórico completo permite auditoria e diagnóstico

### 4.4 Flexibilidade

- **Agendamento personalizado**: Horários e dias da semana configuráveis por automação
- **Múltiplos templates**: Diferentes formatos de relatório para diferentes públicos
- **Consulta pontual**: Comandos Telegram permitem consultar escolas individuais sob demanda
- **Modo preview**: Validar dados antes de enviar sem comprometer destinatários
- **Extensível**: Novos sites alvos podem ser adicionados via Plugin Registry sem modificar código existente

### 4.5 Segurança

- **Credenciais isoladas**: Senhas e tokens em variáveis de ambiente, nunca no código
- **Sessão protegida**: Cookies HttpOnly + SameSite, timeout de 10 minutos
- **Rate limiting**: Proteção contra brute force no login (10 tentativas/min)
- **Security headers**: Nginx configura X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **DEBUG=False**: Modo produção sem exposição de detalhes internos

### 4.6 Observabilidade

- **Dashboard de estatísticas**: Taxa de sucesso, médias de duração, evolução dos últimos 7 dias
- **Histórico de execuções**: Cada execução registra trigger, duração, erros e dados extraídos
- **Alertas no Telegram**: Falhas de agendamento notificam administradores automaticamente
- **Heartbeat do scheduler**: Log periódico confirma que a automação está operacional

### 4.7 Escalabilidade

- **143 unidades escolares** processadas em paralelo via API
- **Múltiplos destinatários** por execução
- **Docker Compose**: Serviços escaláveis horizontalmente (backend, scheduler, listener)
- **Banco persistente**: Dados sobrevivem a restarts dos containers

### 4.8 Manutenibilidade

- **Arquitetura modular**: Skills isoladas com responsabilidade única
- **Contratos Pydantic**: Tipagem estrita garante integridade dos dados
- **Testes automatizados**: 61 testes (18 de segurança) validam o sistema
- **API documentada**: Swagger/OpenAPI automatizado em `/api/docs`
- **Django Admin**: Gerenciamento de modelos sem código adicional

---

## 5. Métricas de Impacto

| Métrica | Valor |
|---------|-------|
| Unidades escolares monitoradas | 143 ativas / 185 total |
| Períodos suportados | Matutino, Vespertino, Integral, Noturno |
| Relatórios disponíveis | 4 tipos (completo, secretaria, diário, individual) |
| Tempo médio de execução | 30-90 segundos |
| Testes automatizados | 61 (18 de segurança) |
| Serviços Docker | 5 (nginx, backend, scheduler, listener, db) |
| Endpoints da API | 20+ (REST com documentação Swagger) |
| Comandos Telegram | 10 interativos |

---

## 6. Correções Críticas Implementadas

Ao longo do desenvolvimento, 10 bugs críticos foram identificados e corrigidos, demonstrando a maturidade e robustez do sistema:

| Bug | Problema | Solução |
|-----|----------|---------|
| #1 | Catch-up pulava horários começando com '0' | Migração para APScheduler |
| #2 | Scheduler rodava sem supervisão | Serviço Docker dedicado |
| #3 | Envio sem timeout/concorrência | httpx com timeout + asyncio.gather |
| #4 | Exceção propagada no relogin | try/except com fallback garantido |
| #5 | Agendamento com drift e sem persistência | APScheduler + DjangoJobStore |
| #6 | Boas-vindas /start não aparecia | Serviço dedicado, offset persistido, retry |
| #7 | Fallback Playwright retornava URL como dado | Sessão autenticada garantida, erro claro |
| #8 | Comandos /unidades retornavam 401 | Re-login automático no listener Telegram |
| #9 | Métricas divergiam do website | Uso de campos pré-calculados da API |
| #10 | Ausentes calculados incorretamente | Cálculo via expectativaPresenca |

---

## 7. Conclusão

A automação **Aluno Presente SME** representa uma solução completa para a coleta, consolidação e disseminação de dados educacionais. Ao automatizar processos que antes demandavam tempo manual significativo, a ferramenta promove:

- **Agilidade**: Relatórios entregues automaticamente nos horários definidos
- **Precisão**: Dados idênticos ao dashboard oficial da plataforma
- **Confiabilidade**: Tratamento de falhas, re-login automático e recuperação de execuções perdidas
- **Segurança**: Credenciais isoladas, sessões protegidas e monitoramento contínuo
- **Escalabilidade**: Arquitetura modular pronta para novos sites alvos via Plugin Registry

A ferramenta está em produção ativa, processando dados de 143 unidades escolares e entregando relatórios para gestores da Secretaria Municipal de Educação de Cuiabá.
