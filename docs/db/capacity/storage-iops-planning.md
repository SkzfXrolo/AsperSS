# Storage & IOPS planning (Pack 48-H Round 6 · #161)

## Inputs

- Reads/s estimados.
- Writes/s estimados.
- WAL bytes/s.
- Backup window load.

## Disco

- SSD NVMe vs SSD genérico: latencia decimales ms vs >1ms.
- Tier Render mapea a IOPS dadas; no overprovision libre.

## WAL throughput

- Pico TPS × bytes/tx → bytes/s WAL.
- Reservar ~3x para autovacuum + checkpoint bursts.

## Argus

- Pico actual estimado: documentar tras benchmark `scripts/db/bench/run-bench.sh` en staging.
- Si Render tier toca IOPS techo → upgradar o agregar replica.

## Referencias

- `docs/db/cost-forecast.md`
