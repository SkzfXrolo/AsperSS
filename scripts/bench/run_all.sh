#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCH_DIR="$ROOT_DIR/scripts/bench"
OUT_DIR="$BENCH_DIR/out"
mkdir -p "$OUT_DIR"

echo "[bench] Running Python synthetic benchmarks..."
python "$BENCH_DIR/bench_features_extraction.py" | tee "$OUT_DIR/features.csv"
python "$BENCH_DIR/bench_assistant_intent.py"    | tee "$OUT_DIR/assistant.csv"
python "$BENCH_DIR/bench_oracle_evaluate.py"     | tee "$OUT_DIR/oracle.csv"
python "$BENCH_DIR/bench_ml_training.py"         | tee "$OUT_DIR/ml_training.csv"

echo "[bench] Completed. Outputs in $OUT_DIR"
