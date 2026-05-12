#!/usr/bin/env bash
# scripts/db/bench/run-bench.sh · Pack 48-H #128
# Orquesta benchmarks de DB (insert/select/concurrent).
#
# Requisitos:
#   - psql en PATH
#   - DATABASE_URL apuntando a DB NON-PROD (script aborta si parece prod)
#   - seed-data.sql aplicado para select-latency
#
# Uso:
#   DATABASE_URL=... ./run-bench.sh [insert|select|concurrent|all]

set -euo pipefail

DB_URL="${DATABASE_URL:-}"
SCENARIO="${1:-all}"
WORKERS="${WORKERS:-4}"
ROWS="${ROWS:-10000}"
BATCH="${BATCH:-500}"
ITERS="${ITERS:-200}"

if [[ -z "$DB_URL" ]]; then
  echo "ERROR: set DATABASE_URL" >&2; exit 2
fi

# Safety check: refuse to run against prod
if echo "$DB_URL" | grep -qiE 'render\.com|argusproyect|prod'; then
  echo "ABORT: DATABASE_URL parece producción. Use NON-PROD DB." >&2; exit 3
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RESULTS_DIR="${SCRIPT_DIR}/results/${TS}"
mkdir -p "$RESULTS_DIR"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
psqlx() { psql "$DB_URL" -v ON_ERROR_STOP=1 -q "$@"; }

run_insert() {
  log "=== INSERT throughput · rows=$ROWS batch=$BATCH ==="
  psqlx -v rows="$ROWS" -v batch="$BATCH" -v "table=scans" \
    -f "$SCRIPT_DIR/insert-throughput.sql" \
    | tee "$RESULTS_DIR/insert.txt"
}

run_select() {
  log "=== SELECT latency · iters=$ITERS ==="
  psqlx -v iters="$ITERS" \
    -f "$SCRIPT_DIR/select-latency.sql" \
    | tee "$RESULTS_DIR/select.txt"
}

run_concurrent() {
  log "=== CONCURRENT write · workers=$WORKERS iters=$ITERS ==="
  pids=()
  for w in $(seq 1 "$WORKERS"); do
    (psqlx -v iters="$ITERS" -v worker="$w" \
       -f "$SCRIPT_DIR/concurrent-write.sql" \
       > "$RESULTS_DIR/concurrent-w$w.txt" 2>&1) &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid" || true; done
  log "Concurrent workers done. Reporting aggregated..."
  psqlx <<SQL | tee "$RESULTS_DIR/concurrent-summary.txt"
SELECT
  worker_id, count(*) AS n,
  round(percentile_disc(0.50) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p50_us,
  round(percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p95_us,
  round(percentile_disc(0.99) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p99_us
FROM bench_concurrent_results
WHERE captured_at >= NOW() - INTERVAL '10 minutes'
GROUP BY worker_id
ORDER BY worker_id;
SQL
}

cleanup_temp_results() {
  log "Cleaning bench_* tables (older than 1 day)..."
  psqlx -c "DELETE FROM bench_runs WHERE started_at < NOW() - INTERVAL '1 day';" || true
  psqlx -c "DELETE FROM bench_latencies WHERE captured_at < NOW() - INTERVAL '1 day';" || true
  psqlx -c "DELETE FROM bench_concurrent_results WHERE captured_at < NOW() - INTERVAL '1 day';" || true
}

case "$SCENARIO" in
  insert)     run_insert ;;
  select)     run_select ;;
  concurrent) run_concurrent ;;
  all)
    run_insert
    run_select
    run_concurrent
    ;;
  cleanup)    cleanup_temp_results ;;
  *)
    echo "Usage: $0 [insert|select|concurrent|all|cleanup]"; exit 1 ;;
esac

log "Results saved to: $RESULTS_DIR"
log "Done."
