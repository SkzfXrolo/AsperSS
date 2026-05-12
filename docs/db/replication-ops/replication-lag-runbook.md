# Replication lag runbook (Pack 48-H Round 6 · #154)

## Síntomas

- Alerta lag > umbral.
- Lectores en réplica ven datos viejos.
- Slot WAL retenido crece.

## Triage (5 min)

1. `SELECT * FROM pg_stat_replication` en primary.
2. `SELECT now() - pg_last_xact_replay_timestamp()` en réplica.
3. CPU / IO réplica (¿bottleneck apply?).
4. Red entre primary y réplica (latencia, packet loss).

## Causas comunes y mitigaciones

| Causa | Mitigación |
| --- | --- |
| Carga sostenida primary (mucho WAL) | tunear queries; reducir bursts |
| Réplica CPU al máximo | upgradar tier réplica |
| Vacuum agresivo primary | tunear autovacuum (`autovacuum-tuning.md`) |
| Long-running query en réplica | bloquea apply (hot_standby_feedback off) → kill |
| Red WAN saturada | revisar QoS / cross-AZ |

## Decisiones operativas

- Si lag > SLA: redirigir lectores **a primary** temporalmente (flag app).
- Si slot peligroso: considerar **drop slot** + reseed (data loss potencial).

## Argus

Aplicar `dba-runbook.md` + `on-call-playbook.md`.

## Referencias

- `docs/db/observability/alert-thresholds.md`
