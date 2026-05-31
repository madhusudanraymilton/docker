#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Odoo 19 Custom Entrypoint (FIXED VERSION)
# =============================================================================

: "${HOST:=db}"
: "${USER:=odoo}"
: "${PASSWORD:?POSTGRES PASSWORD REQUIRED}"
: "${POSTGRES_DB:=postgres}"
: "${ODOO_DB_NAME:=odoo}"
: "${ODOO_CONF:=/etc/odoo/odoo.conf}"
: "${ODOO_BOOTSTRAP_MODULES:=base,web,base_setup,mail,hr}"

export PGPASSWORD="$PASSWORD"

log() {
    echo "[entrypoint] $*"
}

# -----------------------------------------------------------------------------
# Wait for PostgreSQL
# -----------------------------------------------------------------------------
wait_for_db() {
    log "Waiting for Postgres at ${HOST}:5432 (user=${USER})..."
    until pg_isready -h "$HOST" -U "$USER" -d "$POSTGRES_DB" -q; do
        sleep 2
    done
    log "Postgres is ready."
}

# -----------------------------------------------------------------------------
# Check DB exists
# -----------------------------------------------------------------------------
db_exists() {
    psql -h "$HOST" -U "$USER" -d "$POSTGRES_DB" -tAc \
        "SELECT 1 FROM pg_database WHERE datname='${ODOO_DB_NAME}'" | grep -q 1
}

# -----------------------------------------------------------------------------
# Check Odoo schema exists
# -----------------------------------------------------------------------------
odoo_schema_exists() {
    db_exists || return 1

    psql -h "$HOST" -U "$USER" -d "$ODOO_DB_NAME" -tAc \
        "SELECT to_regclass('public.ir_module_module') IS NOT NULL;" \
        | grep -q t
}

# -----------------------------------------------------------------------------
# Bootstrap DB (ONLY ON FIRST RUN)
# -----------------------------------------------------------------------------
bootstrap_db() {
    log "Bootstrapping database '${ODOO_DB_NAME}'..."

    odoo \
        -c "$ODOO_CONF" \
        -d "$ODOO_DB_NAME" \
        -i "$ODOO_BOOTSTRAP_MODULES" \
        --without-demo=all \
        --stop-after-init \
        --no-http

    log "Bootstrap complete."
}

# -----------------------------------------------------------------------------
# Render lock SQL
# -----------------------------------------------------------------------------
render_lock_sql() {
    local whitelist_file="/opt/odoo-whitelist.txt"
    local template="/opt/lock_modules.sql"

    if [ ! -f "$whitelist_file" ]; then
        log "ERROR: whitelist missing"
        exit 1
    fi

    if [ ! -f "$template" ]; then
        log "ERROR: SQL template missing"
        exit 1
    fi

    local quoted
    quoted=$(
        {
            cat "$whitelist_file"
            find /mnt/extra-addons -mindepth 2 -maxdepth 2 \
                \( -name "__manifest__.py" -o -name "__openerp__.py" \) \
                -printf '%h\n' 2>/dev/null | xargs -r -n1 basename
        } \
        | awk 'NF && !seen[$0]++ { printf "%s'\''%s'\''", (n++?",":""), $0 }'
    )

    local out="/tmp/lock_modules.sql"
    sed "s/__WHITELIST_PLACEHOLDER__/${quoted}/g" "$template" > "$out"

    echo "$out"
}

# -----------------------------------------------------------------------------
# Lock unwanted modules (safe to run every boot)
# -----------------------------------------------------------------------------
lock_modules() {
    if ! odoo_schema_exists; then
        log "Skipping lock (Odoo schema not initialized yet)"
        return
    fi

    local sql
    sql=$(render_lock_sql)

    log "Applying module lock..."
    psql -h "$HOST" -U "$USER" -d "$ODOO_DB_NAME" -v ON_ERROR_STOP=1 -f "$sql"

    rm -f "$sql"
    log "Module lock applied."
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
wait_for_db

if ! db_exists; then
    bootstrap_db
elif ! odoo_schema_exists; then
    log "Database exists but Odoo schema is missing. Bootstrapping now."
    bootstrap_db
else
    log "Database and Odoo schema already exist. Skipping bootstrap."
fi

lock_modules

log "Starting Odoo server..."

# =============================================================================
# IMPORTANT FIX:
# NO MORE -u base, NO MORE LOOPING COMMANDS
# THIS MUST BE LONG-RUNNING PROCESS
# =============================================================================
exec odoo -c "$ODOO_CONF"
