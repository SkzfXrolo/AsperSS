#!/usr/bin/env bash
# ============================================================================
# Argus Projects — Pack 48-H Round 4 · #110
# run-analysis.sh
# ----------------------------------------------------------------------------
# Orquesta una corrida de pgbadger sobre los logs de Postgres.
# Soporta modo "full" (todo el log) y modo "incremental" (chunks horarios).
#
# Uso:
#   ./run-analysis.sh                       # default: full report HTML
#   ./run-analysis.sh --incremental
#   ./run-analysis.sh --since "2026-05-11"  # filtro temporal
#   ./run-analysis.sh --format json --output /tmp/r.json
#
# Requisitos:
#   - pgbadger >= 12 en PATH
#   - Logs Postgres en formato stderr con prefix %t [%p] %u@%d/%a
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.conf"
# shellcheck disable=SC1090
source "${CONFIG_FILE}"

MODE="full"
FORMAT="${PGBADGER_FORMAT}"
OUTPUT="${PGBADGER_OUTPUT}"
SINCE=""
UNTIL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --incremental) MODE="incremental"; shift ;;
        --format)      FORMAT="$2"; shift 2 ;;
        --output)      OUTPUT="$2"; shift 2 ;;
        --since)       SINCE="$2"; shift 2 ;;
        --until)       UNTIL="$2"; shift 2 ;;
        -h|--help)
            grep -E '^# ' "$0" | sed 's/^# //'; exit 0 ;;
        *) echo "Unknown flag: $1" >&2; exit 2 ;;
    esac
done

if ! command -v pgbadger >/dev/null; then
    echo "ERROR: pgbadger not in PATH (apt-get install pgbadger)" >&2
    exit 2
fi

if [[ ! -d "$PGBADGER_INPUT_DIR" ]]; then
    echo "ERROR: PGBADGER_INPUT_DIR no existe: $PGBADGER_INPUT_DIR" >&2
    exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"

CMD=(pgbadger
    -j "$PGBADGER_JOBS"
    -f "$PGBADGER_PARSER_FORMAT"
    -T "Argus DB"
    -t 20
    --timezone "$PGBADGER_TIMEZONE"
    --min-duration "$PGBADGER_MIN_DURATION"
    --exclude-query "$PGBADGER_EXCLUDE_QUERY"
    --quiet
)

if [[ "$PGBADGER_ANONYMIZE" == "1" ]]; then
    CMD+=(--anonymize)
fi

if [[ -n "$SINCE" ]]; then CMD+=(-b "$SINCE"); fi
if [[ -n "$UNTIL" ]]; then CMD+=(-e "$UNTIL"); fi

CMD+=(-X)                              # generar charts JS
CMD+=(--format "$FORMAT")
CMD+=(-o "$OUTPUT")

if [[ "$MODE" == "incremental" ]]; then
    mkdir -p "$PGBADGER_INCREMENTAL_DIR"
    CMD+=(-I -O "$PGBADGER_INCREMENTAL_DIR")
fi

INPUT_FILES=("$PGBADGER_INPUT_DIR"/$PGBADGER_GLOB)
if [[ ! -e "${INPUT_FILES[0]}" ]]; then
    echo "ERROR: no logs matching $PGBADGER_INPUT_DIR/$PGBADGER_GLOB" >&2
    exit 2
fi

echo "[1/3] Running pgbadger over ${#INPUT_FILES[@]} log file(s)..."
"${CMD[@]}" "${INPUT_FILES[@]}"

echo "[2/3] Sizing..."
du -h "$OUTPUT" 2>/dev/null || true

echo "[3/3] Done. Report at: $OUTPUT"

# Opcional: subir a S3
if [[ -n "${REPORT_S3_BUCKET:-}" ]]; then
    aws s3 cp "$OUTPUT" "${REPORT_S3_BUCKET}/$(basename "$OUTPUT")" \
        --storage-class STANDARD_IA
    echo "Uploaded to ${REPORT_S3_BUCKET}/"
fi
