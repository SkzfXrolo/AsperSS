# Pack48-G Bench Results (local, synthetic)

## Metodología

- Entorno local Windows (no producción).
- Dataset sintético (`argus_ai_trainer._synth_*`).
- Benchmarks standalone en `scripts/bench/`.
- Formato CSV-friendly en salida de scripts.

## Resultados medidos

### 1) `bench_oracle_evaluate.py` (1000 evaluaciones hybrid)

- `avg_ms`: **8.708**
- `p50_ms`: **7.480**
- `p95_ms`: **14.132**
- `p99_ms`: **20.829**
- `max_ms`: **50.882**

### 2) `bench_ml_training.py` (escalado 1k/10k/100k)

| samples | build_ms | train_ms | total_ms | est_data_mb | accuracy |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 25.757 | 68.074 | 93.832 | 0.435 | 1.0000 |
| 10,000 | 278.768 | 806.698 | 1085.466 | 4.349 | 1.0000 |
| 100,000 | 4009.029 | 8907.815 | 12916.844 | 43.488 | 1.0000 |

> `est_data_mb` es estimado teórico de footprint de dataset numérico (no RSS real del proceso).

### 3) `bench_features_extraction.py` (10,000 extracciones)

- `avg_ms`: **0.0291**
- `p50_ms`: **0.0239**
- `p95_ms`: **0.0502**
- `p99_ms`: **0.1131**
- `ops_per_sec`: **34,316.83**

### 4) `bench_assistant_intent.py` (10,000 clasificaciones)

- `avg_ms`: **0.0172**
- `p50_ms`: **0.0141**
- `p95_ms`: **0.0329**
- `p99_ms`: **0.0712**
- `ops_per_sec`: **58,189.47**

## Comparación con baseline objetivo

- Objetivo razonable sugerido para `evaluate_hybrid`: **p95 < 50 ms**.
  - Resultado Pack48-G: **14.13 ms p95** (cumple holgadamente).
- Objetivo para extracción de features: **< 1 ms promedio**.
  - Resultado: **0.029 ms** (cumple).
- Objetivo para clasificación de intent: **< 2 ms promedio**.
  - Resultado: **0.017 ms** (cumple).
- Objetivo entrenamiento 100k (modo batch simple): **< 30s total**.
  - Resultado: **12.9s total** (cumple).

## Lectura de performance

- El problema actual no es CPU puro de lógica AI aislada; los cuellos reales están más en:
  - I/O de scanner.
  - Query design + índices.
  - Polling frontend.
  - hot path packet plugin.
