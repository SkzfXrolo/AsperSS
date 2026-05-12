# Failback procedure (Pack 48-H Round 6 · #154)

## Definición

**Failback** = volver tráfico al **primary original** (o reincorporar como réplica) tras recuperar el nodo caído.

## Riesgos

- Datos divergentes si ambos aceptaron escrituras (split-brain mal mitigado).
- Necesidad de **rebuild** completo del nodo viejo.

## Patrón seguro

1. Confirmar nodo viejo apagado limpio.
2. `pg_rewind` (mismo major) o **rebuild from base backup** del nuevo primary.
3. Reanudar como **standby** del nuevo primary.
4. Esperar catch-up.
5. Opcional: ventana planeada para nuevo failover si políticamente se requiere "primary en A".

## Argus

Mantener "primary follows latest" salvo razones operativas (latencia geográfica, tier asimétrico).

## Referencias

- `docs/db/ha-patterns/witness-server.md`
