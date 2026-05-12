# DBA on-call playbook (Pack 48-H Round 3 · #106)

## Roster

| Slot | Quién | Backup |
| --- | --- | --- |
| Primary | DBA on duty (rota semanal) | Tech Lead |
| Secondary | DBA backup | Founder (sólo P0 fuera de horario) |

Define rotación en PagerDuty / Slack /opsgenie.

## Severidades

| Sev | Definición | SLA respuesta |
| --- | --- | --- |
| **P0** | DB caída, data perdida, security incident | 5 min, 24/7 |
| **P1** | Replication lag, disco >90%, high CPU sostenido | 15 min, 24/7 |
| **P2** | Slow queries, bloat, índice missing | 4 h, business hours |
| **P3** | Mejora, refactor, deprecación | 2 días |

## Pages frecuentes — diagnóstico rápido

### "High CPU > 80% por 5min"

```sql
SELECT pid, state, application_name, query_start,
       NOW() - query_start AS age, LEFT(query, 80) AS q
FROM pg_stat_activity
WHERE state='active'
ORDER BY age DESC NULLS LAST LIMIT 20;

-- top queries por tiempo
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 10;
```

**Acciones**:
1. ¿Una query domina? Matarla con `pg_cancel_backend` y avisar al owner.
2. ¿Spike de tráfico? Activar rate limiting capa app.
3. ¿Falta índice? Crear con `CONCURRENTLY` después del incidente.

---

### "Low cache hit ratio < 95%"

```sql
SELECT relname, heap_blks_hit, heap_blks_read,
       ROUND(100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read,0), 2) AS hit_pct
FROM pg_statio_user_tables
ORDER BY heap_blks_read DESC LIMIT 20;
```

**Acciones**:
1. Identificar tabla ofensora.
2. ¿Falta índice? Lleva a seq scan.
3. ¿Working set > RAM? Considerar tier upgrade o partitioning.

---

### "Replication lag > 60s"

```sql
SELECT application_name, replay_lag, write_lag, flush_lag, sync_state
FROM pg_stat_replication;
```

**Acciones**:
1. Si replica saturada en CPU: pausar reportes que la usen.
2. Si red lenta: revisar Render network status.
3. Si slot inactivo: ver `edge-cases-playbook.md` §6.

---

### "Disk usage > 85%"

```sql
SELECT pg_size_pretty(pg_database_size('argus_prod'));
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;
```

**Acciones**:
1. Detectar tablas que crecen rápido (logs sin retention).
2. Aplicar `cleanup-policy-pack48.sql` para tablas con retention definida.
3. Considerar archive a S3 + DROP.
4. Si urgente: upgrade tier.

---

### "Slow query alert"

```sql
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC LIMIT 20;
```

**Acciones**:
1. Pedir EXPLAIN ANALYZE al owner.
2. Verificar si está en `additional-indexes.sql` el índice faltante.
3. Si es analytics query: mover a read replica.

---

## Comandos prohibidos sin segundo par de ojos

- `DROP TABLE` (incluso particiones)
- `DROP DATABASE`
- `TRUNCATE` en tablas core (scans, users, companies)
- `ALTER TABLE ... DROP COLUMN`
- `pg_promote()`
- `pg_terminate_backend(<pid_de_walsender>)`

Para cualquiera de los anteriores: 2 personas confirmando + ticket + tag de la línea de comando.

## Escalation matrix

| Sev | Acción inicial | Si no resuelto en | Escalar a |
| --- | --- | --- | --- |
| P0 | DBA on-call | 15 min | Tech Lead + Founder |
| P1 | DBA on-call | 1 h | Tech Lead |
| P2 | DBA on-call | 1 día | Tech Lead (mensual review) |

## Comunicación durante incident

1. Crear canal `#inc-YYYYMMDD-<corto>` en Slack (template).
2. IC abre incident doc (template Google Docs).
3. Updates cada 15 min mientras dure P0.
4. StatusPage update si afecta >5% usuarios.

## Postmortem template

```markdown
# Postmortem — <título corto>

- Date: YYYY-MM-DD
- Severity: P?
- Duration: HHmm
- IC: <name>

## Resumen ejecutivo
2-3 oraciones.

## Timeline (UTC)
- HH:MM detected
- HH:MM IC asignado
- HH:MM mitigación X aplicada
- HH:MM servicio restaurado

## Impacto
- Customers afectados
- Data perdida / corrupta (cantidad, ventana)
- Revenue lost (estimado)

## Causa raíz
Por qué pasó. NO buscar culpables.

## Detección
Cómo nos enteramos. ¿Hay forma de detectarlo antes?

## Mitigación
Qué hicimos durante.

## Acciones (con dueño y fecha)
- [ ] Owner @x: action item 1 (due YYYY-MM-DD)

## Lecciones
Qué aprendimos.

## Hallazgos positivos
Qué funcionó bien.
```

## Documentación a mano durante turno

- `edge-cases-playbook.md` — problemas técnicos comunes.
- `disaster-playbook.md` — escenarios P0.
- `dba-runbook.md` — procedures cotidianas.
- `dashboards-spec.md` — paneles para diagnosticar.
- `monitoring-queries.sql` — queries listas.
- `migration-runbook.md` — cómo aplicar migrations sin incident.

## Skills checklist DBA on-call

- [ ] `psql` confiable.
- [ ] Sabe leer `EXPLAIN ANALYZE`.
- [ ] Sabe usar `pg_stat_*` views.
- [ ] Sabe diagnosticar locks.
- [ ] Sabe rollback de migration.
- [ ] Sabe restore desde backup.
- [ ] Sabe terminar query trabada sin bajar todo.
- [ ] Conoce dónde están los runbooks (este folder).

## Mejora continua

- Mensual: review de pages → ¿cuáles fueron innecesarias? (tunear alertas).
- Trimestral: drill DR.
- Anual: rotar quién es on-call backup.
