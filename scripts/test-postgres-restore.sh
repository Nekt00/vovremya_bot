#!/bin/sh
set -eu

: "${1:?Usage: test-postgres-restore.sh BACKUP_FILE}"
: "${BACKUP_PASSPHRASE_FILE:?Set BACKUP_PASSPHRASE_FILE to a readable secret file}"

backup_file=$1
compose_file=${COMPOSE_FILE:-compose.vps.yaml}
database="medication_restore_test_$(date -u +%Y%m%d%H%M%S)_$$"

docker compose -f "$compose_file" exec -T postgres \
    createdb -U medication "$database"
trap 'docker compose -f "$compose_file" exec -T postgres dropdb --if-exists -U medication "$database" >/dev/null' EXIT

openssl enc -d -aes-256-cbc -pbkdf2 \
    -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$backup_file" \
    | docker compose -f "$compose_file" exec -T postgres \
        pg_restore -U medication -d "$database"

docker compose -f "$compose_file" exec -T postgres \
    psql -U medication -d "$database" -v ON_ERROR_STOP=1 \
        -c 'SELECT count(*) FROM users;' >/dev/null

echo "Restore check passed"
