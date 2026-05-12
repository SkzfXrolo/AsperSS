# Disaster scenarios playbook (Pack 48-H Round 3 · #104)

Operacional para incidentes **P0**: tareas, contactos, decision tree, comunicación.

> Distintos de `edge-cases-playbook.md` (problemas P1/P2 contenidos a un servidor); estos escenarios son **catastróficos**.

---

## Roles durante un incidente

| Rol | Quién | Responsabilidad |
| --- | --- | --- |
| **Incident Commander (IC)** | DBA on-call o Tech Lead | Decide acciones, sincroniza, comunica |
| **Operator** | DBA / SRE | Ejecuta comandos, no decide |
| **Comms** | Producto / Founder | Habla con clientes, estado page |
| **Scribe** | cualquiera disponible | Timeline en doc compartido |

---

## Escenario 1 — "DB deleted by accident"

### Síntoma

`SELECT * FROM scans LIMIT 1` → `ERROR: relation "scans" does not exist`
o el panel devuelve 5xx generalizado.

### Causas típicas

- `DROP DATABASE` ejecutado en consola equivocada.
- `pg_restore` parcial mal escrito (`-c` que dropea + restore que falla).
- Render auto-deleted (poco probable; cuenta suspendida).

### Acción inmediata (T+0 a T+15min)

1. **Confirmar**: ¿realmente está borrado o sólo desconectado?
   ```sql
   SELECT datname FROM pg_database;
   \dt
   ```
2. **Stop writes**: bajar la app (Render → suspend services) para evitar inserts en DB recién creada vacía que confundan el restore.
3. **Identificar último backup bueno**: ver `scripts/db/backup-automation.sh` schedule; típicamente 1h atrás.
4. **Estimar pérdida**: RPO = ventana entre último backup y borrado.

### Restore (T+15min a T+1h)

```bash
# 1. crear DB destino (si fue DROP DATABASE)
psql -h $PGHOST -U postgres -c "CREATE DATABASE argus_restored;"

# 2. restore backup
gpg --decrypt < argus-YYYYMMDD.dump.gpg | pg_restore -h $PGHOST -d argus_restored -j 4

# 3. validar counts
psql -d argus_restored -c "SELECT 'scans' AS t, COUNT(*) FROM scans
UNION ALL SELECT 'companies', COUNT(*) FROM companies;"
```

### Cutover (T+1h a T+1h15min)

1. Renombrar DB: `ALTER DATABASE argus_prod RENAME TO argus_dead;` y `ALTER DATABASE argus_restored RENAME TO argus_prod;`.
2. Levantar app, smoke test (login + scan list + 1 nueva scan).
3. Notificar.

### Post

- Postmortem (template en `on-call-playbook.md`).
- Revisar permisos: por qué tenía acceso esa cuenta a `DROP DATABASE`.
- Implementar `REVOKE DROP` para roles app (ver `security-hardening.md`).

### Comunicación con clientes

```
Estamos investigando un incidente que afecta el panel de Argus.
Los plugins MC siguen recolectando data localmente. ETA: 1h.
```

---

## Escenario 2 — "Corrupt page in critical table"

### Síntoma

```
ERROR: invalid page in block 12345 of relation base/16384/12345
```
o crashes intermitentes en queries específicas.

### Acción (T+0)

1. **Identificar** la relación afectada: el OID en el mensaje.
   ```sql
   SELECT relname, relkind FROM pg_class WHERE oid = 12345;
   ```
2. **Aislar**: si es una tabla, marcarla read-only a nivel app (feature flag).
3. **Dump** filas no afectadas:
   ```sql
   SET zero_damaged_pages = on;
   COPY (SELECT * FROM scans WHERE id < AFFECTED_BLOCK_RANGE) TO '/tmp/good.csv';
   ```

### Restore (decisión)

| Cuánto se perdió | Acción |
| --- | --- |
| <1% de las filas y reproducibles | TRUNCATE filas afectadas, re-derivar |
| 1-10% | Restore de backup, replay WAL hasta antes del corrupt |
| >10% o tabla central | Restore completo del DB (escenario 1) |

### Post

- Validar hardware (Render: ticket de soporte).
- `data_checksums = on` (si no estaba; en Render viene por default).
- Backup integrity check (`pg_dump --schema-only | grep -c CREATE TABLE` debe coincidir con golden).

---

## Escenario 3 — "WAL filled disk"

### Síntoma

```
ERROR: could not extend file ... No space left on device
LOG: server reached max_wal_size
```

### Acción (T+0)

1. `df -h` (Render: dashboard de tier).
2. **NO** ejecutar `VACUUM FULL` (necesita 2× espacio).
3. Identificar:
   ```sql
   SELECT pg_size_pretty(pg_database_size('argus_prod'));
   SELECT pg_size_pretty(sum(size)) FROM pg_ls_waldir();
   ```

### Mitigación

1. Si `archive_command` está activo: verificar que el archivado va al storage externo (`pg_stat_archiver`). Si está roto:
   - Fixear el `archive_command`.
   - Ejecutar `pg_ctl reload`.
   - Cuando archive empiece a vaciar el directorio WAL, se libera espacio.
2. Aumentar disco (Render: upgrade tier).
3. Reducir `wal_keep_size` temporalmente.
4. Drop slots inactivos:
   ```sql
   SELECT slot_name FROM pg_replication_slots WHERE NOT active;
   -- evaluar y SELECT pg_drop_replication_slot('nombre');
   ```

### Prevención

- Monitor archive lag.
- Alerta a 70% disco.
- WAL archive a S3 (pgbackrest/wal-g).

---

## Escenario 4 — "Replication lag > 1h"

### Síntoma

```sql
-- en primario
SELECT pid, application_name,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```
o consulta en replica devuelve data muy antigua.

### Diagnóstico rápido

| Posible causa | Cómo confirmar |
| --- | --- |
| Red WAN flap | ping/MTR primary↔replica |
| CPU saturada en replica | `top` en replica, `pg_stat_activity` |
| Conflict recovery | `select * from pg_stat_database_conflicts` |
| Slot inactivo | `pg_replication_slots.active=false` |

### Mitigación

1. **No** matar replicación directamente. Primero diagnosticar.
2. Si es conflict recovery: aumentar `max_standby_streaming_delay` o pausar reads en replica.
3. Si la replica está muy atrás (>5GB WAL behind): considerar rebuild con `pg_basebackup`.
4. Aumentar `max_replication_slots` si están al tope: en `postgresql.conf` + restart (planear ventana).

### Prevención

- Monitoring continuo de lag (Grafana, ver `dashboards-spec.md`).
- Auto-failback si la replica se cae: alertas a DBA, no auto-restart.

---

## Escenario 5 — "Brute-force / data exfil sospechoso"

### Síntoma

- Spike de `pg_stat_activity` con queries `SELECT * FROM users` masivas.
- Bandwidth out anormal.
- Logs muestran logins inválidos.

### Acción inmediata

1. `pg_terminate_backend(pid)` de queries sospechosas.
2. `REVOKE` rol comprometido:
   ```sql
   ALTER ROLE app NOLOGIN;
   ```
3. Rotar credenciales (app, replicador, DBA).
4. Capturar logs (`pg_log/` + Render logs export).
5. Backup forense del estado actual (snapshot point-in-time si está disponible).

### Comunicación

Si confirma exfiltración de PII: notificación a clientes en ≤72h (GDPR). Ver `security-hardening.md`.

---

## Escenario 6 — "Promovimos accidentalmente una replica"

### Síntoma

Dos primarios escribiendo (split-brain). Conflictos al re-sincronizar.

### Acción

1. Identificar cuál tiene "verdad" (más writes recientes, más clientes).
2. Bajar el menos-importante (ALTER SYSTEM SET default_transaction_read_only=on + reboot).
3. Manualmente reconciliar:
   - Datos sólo en B → exportar, importar a A.
4. Reconstruir replica desde A.

### Prevención

- `pg_promote()` requiere ticket de aprobación.
- Fencing automático (cluster manager: Patroni).

---

## Escenario 7 — "Render account suspended / facturación"

### Acción

- Founder/dueño paga inmediato.
- Mientras: levantar instancia paralela en otra cloud usando backup más reciente (escenario 1, en otra región).
- Cambiar DNS / app URL.

### Prevención

- Pago automático con backup card.
- Multi-cloud DR plan (futuro).

---

## Checklist genérico post-incidente

- [ ] Servicio restaurado y verificado (smoke).
- [ ] Backups íntegros (no se rompió el sistema de backups).
- [ ] Postmortem programado en ≤48h.
- [ ] Customer comms enviadas.
- [ ] Action items en MEJORAS_PACK48.txt.
- [ ] Métricas: tiempo de detect → mitigate → resolve.

## Drills

Trimestral: simular escenario 1 en staging con backup real (no notificar al equipo).
Anual: simular escenario 5 (security incident) con consultor externo.

Ver `dr-drill-plan.md`.
