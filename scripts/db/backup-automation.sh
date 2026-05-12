#!/usr/bin/env bash
# ============================================================================
# Argus Projects — Pack 48-H Round 2
# backup-automation.sh
# ----------------------------------------------------------------------------
# pg_dump custom → gzip opcional → GPG encrypt → upload S3-compatible
#
# Requisitos: pg_dump, gpg, aws-cli (o rclone para B2/Wasabi)
# Variables de entorno (ejemplo):
#   DATABASE_URL=postgresql://...
#   BACKUP_S3_BUCKET=s3://argus-db-backups
#   AWS_ACCESS_KEY_ID=...
#   AWS_SECRET_ACCESS_KEY=...
#   AWS_DEFAULT_REGION=us-east-1
#   GPG_RECIPIENT=owner@aspers.gg
#   RETENTION_DAYS=7   (opcional; lifecycle S3 recomendado en su lugar)
#
# NO ejecutar en CI sin secrets — uso: cron en bastion o GitHub Actions OIDC.
# ============================================================================
set -euo pipefail

TS="$(date -u +%Y%m%dT%H%M%SZ)"
WORKDIR="${TMPDIR:-/tmp}/argus-backup-${TS}"
mkdir -p "$WORKDIR"

cleanup() {
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

: "${DATABASE_URL:?Set DATABASE_URL}"
: "${GPG_RECIPIENT:?Set GPG_RECIPIENT (public key id/email)}"

RAW="${WORKDIR}/argus-${TS}.dump"
ENC="${WORKDIR}/argus-${TS}.dump.gpg"
SHA="${WORKDIR}/argus-${TS}.SHA256"

echo "[1/5] pg_dump (custom format)..."
pg_dump --no-owner --no-acl --format=custom \
  --file="$RAW" \
  "$DATABASE_URL"

echo "[2/5] sha256..."
sha256sum "$RAW" | tee "$SHA"

echo "[3/5] gpg encrypt..."
gpg --batch --yes --encrypt \
  --recipient "$GPG_RECIPIENT" \
  --output "$ENC" \
  "$RAW"

echo "[4/5] optional upload..."
if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
  : "${AWS_ACCESS_KEY_ID:?}"
  : "${AWS_SECRET_ACCESS_KEY:?}"
  aws s3 cp "$ENC" "${BACKUP_S3_BUCKET}/daily/argus-${TS}.dump.gpg" --storage-class STANDARD_IA
  aws s3 cp "$SHA" "${BACKUP_S3_BUCKET}/daily/argus-${TS}.SHA256" --storage-class STANDARD_IA
  echo "Uploaded to ${BACKUP_S3_BUCKET}/daily/"
else
  echo "BACKUP_S3_BUCKET not set — leaving files in $WORKDIR (will delete on exit — copy first!)"
  # For debugging: copy ENC to a persistent path before process ends
  # cp "$ENC" /var/backups/
fi

echo "[5/5] done."
