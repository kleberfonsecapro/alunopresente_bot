#!/usr/bin/env bash
# ==============================================================================
# DISASTER RECOVERY - SCRIPT DE BACKUP
# Stack: PostgreSQL (Dump) + Borg Backup + Rclone + Telegram Alerts
# ==============================================================================
# Este script obedece estritamente às regras do agents.md:
# 1. Consistência: Dump lógico antes do snapshot.
# 2. Segurança: Segredos lidos de variáveis de ambiente (sem hardcode).
# 3. Retenção: Borg Prune configurado.
# 4. Resiliência: Sincronização offsite com Rclone e retry.
# 5. Observabilidade: Notificações no Telegram via trap de erros.
# ==============================================================================

# Força a parada do script em caso de falhas e variáveis não declaradas
set -euo pipefail

# ------------------------------------------------------------------------------
# CONFIGURAÇÕES E VARIÁVEIS (Recomendado carregar via .env)
# ------------------------------------------------------------------------------
# source /home/kleber/scripts/.env_backup

# Variáveis do Projeto (Exemplo configurado para o sistema de chamados)
PROJECT_NAME="chamados_sme"
DB_CONTAINER_NAME="${PROJECT_NAME}_db_1"
DB_USER="postgres"
DB_NAME="chamados_db"

# Diretórios
BACKUP_BASE_DIR="/home/kleber/backups"
DUMP_DIR="${BACKUP_BASE_DIR}/dumps"
BORG_REPO="${BACKUP_BASE_DIR}/borg_repo"

# Variáveis Borg (Devem vir do ambiente no mundo real)
export BORG_PASSPHRASE="${BORG_PASSPHRASE:-SuaSenhaForteAqui}"
export BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=no

# Variáveis Rclone
RCLONE_REMOTE="gdrive:backups/${PROJECT_NAME}"

# Variáveis Telegram
TG_BOT_TOKEN="${TG_BOT_TOKEN:-}"
TG_CHAT_ID="${TG_CHAT_ID:-}"

# Timestamp para o nome do arquivo e do repositório
DATE=$(date +%Y-%m-%d_%H-%M-%S)
DUMP_FILE="${DUMP_DIR}/${PROJECT_NAME}_${DATE}.sql"

# ------------------------------------------------------------------------------
# FUNÇÕES DE OBSERVABILIDADE E ALERTAS (TELEGRAM)
# ------------------------------------------------------------------------------
send_telegram_alert() {
    local message="$1"
    if [[ -n "${TG_BOT_TOKEN}" ]] && [[ -n "${TG_CHAT_ID}" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage"             -d chat_id="${TG_CHAT_ID}"             -d text="${message}"             -d parse_mode="HTML" > /dev/null
    else
        echo "Aviso: Credenciais do Telegram não configuradas. Alerta não enviado."
    fi
}

# Trap para capturar falhas inesperadas (Caminho Triste)
handle_error() {
    local exit_code=$?
    local line_no=$1
    local msg="🚨 <b>FALHA CRÍTICA NO BACKUP</b> 🚨%0A%0A"
    msg+="<b>Servidor:</b> $(hostname)%0A"
    msg+="<b>Projeto:</b> ${PROJECT_NAME}%0A"
    msg+="<b>Erro na linha:</b> ${line_no}%0A"
    msg+="<b>Exit Code:</b> ${exit_code}%0A%0A"
    msg+="Verifique os logs imediatamente! @admin"
    
    send_telegram_alert "${msg}"
    exit "${exit_code}"
}
trap 'handle_error ${LINENO}' ERR

# ------------------------------------------------------------------------------
# EXECUÇÃO DA ROTINA
# ------------------------------------------------------------------------------
mkdir -p "${DUMP_DIR}"

echo "[1/4] Iniciando Dump Lógico do Banco de Dados (${DB_NAME})..."
# Utiliza docker exec para rodar o pg_dump dentro do container sem expor a porta
docker exec "${DB_CONTAINER_NAME}" pg_dump -U "${DB_USER}" -F c "${DB_NAME}" > "${DUMP_FILE}"
echo "Dump concluído com sucesso."

echo "[2/4] Executando Borg Backup (Snapshot & Deduplicação)..."
# Inicializa o repositório se ele não existir (repokey)
if ! borg info "${BORG_REPO}" > /dev/null 2>&1; then
    echo "Repositório Borg não encontrado. Inicializando..."
    borg init -e repokey "${BORG_REPO}"
fi

borg create     --verbose     --filter AME     --list     --stats     --show-rc     --compression lz4     "${BORG_REPO}::${PROJECT_NAME}-${DATE}"     "${DUMP_DIR}"

echo "[3/4] Aplicando Política de Retenção (Borg Prune)..."
borg prune     --list     --prefix "${PROJECT_NAME}-"     --show-rc     --keep-daily=7     --keep-weekly=4     --keep-monthly=6     "${BORG_REPO}"

echo "[4/4] Sincronizando repositório para Offsite (Rclone)..."
rclone sync "${BORG_REPO}" "${RCLONE_REMOTE}" --retries 3 --verbose

# Coletando informações finais para o relatório
BORG_STATS=$(borg info "${BORG_REPO}::${PROJECT_NAME}-${DATE}" | grep "This archive" || true)

# ------------------------------------------------------------------------------
# SUCESSO (Caminho Feliz)
# ------------------------------------------------------------------------------
SUCCESS_MSG="✅ <b>BACKUP CONCLUÍDO</b> ✅%0A%0A"
SUCCESS_MSG+="<b>Servidor:</b> $(hostname)%0A"
SUCCESS_MSG+="<b>Projeto:</b> ${PROJECT_NAME}%0A"
SUCCESS_MSG+="<b>Data:</b> ${DATE}%0A%0A"
SUCCESS_MSG+="<b>Status:</b> Dump Lógico, Borg Snapshot e Rclone Offsite executados com sucesso.%0A"

send_telegram_alert "${SUCCESS_MSG}"

# Limpeza local do dump para economizar disco (os dados já estão no Borg)
rm -f "${DUMP_FILE}"

echo "Rotina de backup finalizada com sucesso."
