# AI Inference Performance Deep (Pack48-G)

## Perfil de `evaluate()` vs `evaluate_hybrid()`

- `evaluate()` (heurístico) es mayormente O(v) por cantidad de violations y multiplicadores.
- `evaluate_hybrid()` agrega costo de:
  - extracción de features/secuencia,
  - `ensemble_predict`,
  - KNN similarity contra ejemplos (componente más sensible al crecimiento).

## Hotspots esperables

1. KNN scoring lineal en número de ejemplos activos.
2. Normalización/cálculo repetido de features en evaluaciones individuales.
3. Carga fría de estados de modelo en primer request tras deploy.

## Cold start vs warm

- **Cold start:** parse de modelo + inicialización de caches + primer query de estado.
- **Warm:** latencia dominada por inferencia y KNN.
- Recomendado: lazy load explícito con warm-up job post-deploy.

## Optimizaciones propuestas

1. Batch evaluation para múltiples jugadores/eventos.
2. Vectorización numérica (NumPy) en features y distancias.
3. Limitar KNN window (top recientes por tenant) para bound de costo.
4. Quantization de parámetros si se exporta modelo fuera de Python.
5. Export ONNX para serving optimizado (si se separa servicio).

## Memory footprint

- Medir por componente:
  - LR state (bajo),
  - KNN examples (alto, crecimiento lineal),
  - temporal model (medio).
- Baseline sugerido: registrar memoria por `n_examples` y por tenant.

## Serving strategy

- **In-process (actual):** simple, menos hop de red, riesgo de jitter CPU en web workers.
- **Servicio separado (BentoML/Triton):** mejor aislamiento y escalado independiente; mayor complejidad operativa.

## Recomendación Argus

- Corto plazo: in-process + límites/caches.
- Mediano plazo: extraer inferencia a servicio dedicado para cargas altas multi-tenant.
