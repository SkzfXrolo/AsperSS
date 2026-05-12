# Covering indexes (INCLUDE) (Pack 48-H Round 6 · #155)

## Definición

`INCLUDE` agrega columnas al **leaf** del índice sin formar parte de la clave: permite **index-only scans**.

```sql
CREATE INDEX idx_scans_panel
  ON scans (company_id, created_at DESC)
  INCLUDE (risk_score, status);
```

## Beneficio

- Plan `Index Only Scan`: evita visitar heap si visibility map permite.
- Latencia menor en lecturas que retornan pocas columnas.

## Costos

- Índice más grande.
- VACUUM más frecuente para mantener visibility map (`vacuum_index_cleanup`).

## Argus

- Panel queries muestran `id`, `risk_score`, `created_at` → covering ayuda.
- Medir `idx_blks_hit` y `Heap Fetches` post-deploy.

## Referencias

- `docs/db/performance/index-strategies.md`
