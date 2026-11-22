#!/bin/sh
set -eu

: "${BACKUP_DIR:?Set BACKUP_DIR to an off-server mounted directory}"
: "${BACKUP_PASSPHRASE_FILE:?Set BACKUP_PASSPHRASE_FILE to a readable secret file}"

case "$BACKUP_DIR" in
    /|"") echo "BACKUP_DIR must be a dedicated directory" >&2; exit 1 ;;
esac

compose_file=${COMPOSE_FILE:-compose.vps.yaml}
retention_days=${BACKUP_RETENTION_DAYS:-30}
case "$retention_days" in
    *[!0-9]*|"") echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2; exit 1 ;;
esac

umask 077
mkdir -p "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_DIR/medication-$timestamp.dump.enc"
temporary="$target.tmp"
trap 'rm -f "$temporary"' EXIT

docker compose -f "$compose_file" exec -T postgres \
    pg_dump -U medication -d medication --format=custom \
    | openssl enc -aes-256-cbc -pbkdf2 -salt \
        -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$temporary"

openssl enc -d -aes-256-cbc -pbkdf2 \
    -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$temporary" \
    | docker compose -f "$compose_file" exec -T postgres pg_restore --list >/dev/null

mv "$temporary" "$target"
trap - EXIT
find "$BACKUP_DIR" -type f -name 'medication-*.dump.enc' \
    -mtime "+$retention_days" -delete
echo "$target"
