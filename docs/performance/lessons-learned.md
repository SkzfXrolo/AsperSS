# Performance Lessons Learned (Pack48-G)

## Incidentes tipo (hipotéticos)

1. Outage Render por saturación worker  
   - Causa: polling + query pesada  
   - Fix: cache + index + backoff  
   - Prevención: budget de p95 y synthetic tests

2. Slow query growth  
   - Causa: tabla grande sin índice compuesto  
   - Fix: índice + rewrite  
   - Prevención: revisión mensual pg_stat_statements

3. Memory leak scanner  
   - Causa: lectura completa de archivos grandes  
   - Fix: chunked read  
   - Prevención: memory benchmark CI

4. Cache stampede  
   - Causa: expiración simultánea  
   - Fix: jitter TTL + refresh-ahead  
   - Prevención: patrones de invalidación definidos
