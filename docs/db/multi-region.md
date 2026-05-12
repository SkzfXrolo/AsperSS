# Multi-region DB strategy (Pack 48-H Round 3 · #98)

## Motivación

Argus tiene clientes en LATAM, EU, NA y APAC. Hoy:

- DB y app corren en **una sola region** Render (típicamente US-East).
- Plugins MC desde APAC tienen RTT 200-300ms por scan → notable en endpoints síncronos.
- DR isolation: una caída de la region significa caída total del SaaS.

## Casos de uso a resolver

1. **Latencia de lectura** para paneles staff (EU, APAC).
2. **DR isolation**: failover a otra region si primario muere.
3. **Compliance regional** (GDPR data residency): clientes EU exigen que sus datos no salgan de EU.

## Patrones

### A) **Active-passive** (read replica en otra region)

Réplica streaming hacia región B. Reads en B (panel, oracle eval). Writes siempre en A.
Failover: promoción manual o automática de B.

| Pros | Cons |
| --- | --- |
| Simple, soportado nativo | Lag depende del link (50-300ms WAN) |
| Costo controlado (1 réplica extra) | Failover no es transparente (DNS swap) |
| Sin conflict resolution | Writes siempre en region A |

**Recomendado para Argus Pack 48-60.**

### B) **Active-active** (multi-master con resolver)

Cada region acepta writes; sync entre regions (BDR, pglogical, Citus, Yugabyte).
Conflict resolution: last-write-wins / app-level / CRDT.

| Pros | Cons |
| --- | --- |
| Lowest write latency global | Conflict storms (mismo player editado en 2 regions) |
| HA total | Complexidad operativa enorme |
| | Vendors: $$$ |

**No recomendado hasta que Argus tenga >100k MAU global.**

### C) **Sharded by region** (cada region = shard propio)

`scans` de empresas EU viven en PG-EU; LATAM en PG-LATAM. Cross-region queries hacen fan-out.

| Pros | Cons |
| --- | --- |
| Data residency natural | Querys cross-region son lentas |
| Failover regional aislado | Operatoria: 3-4 clústers |

**Candidato si crece la presión de compliance.**

### D) **Edge cache / CDN read-through**

Capa de cache (Cloudflare, Fastly, Redis edge) sirve respuestas precomputed.
No reemplaza la DB, sólo enmascara latencia para queries cacheables (sí en oracle eval, no en writes).

**Complementario, NO sustituye una estrategia DB**.

## Recomendación Argus

**Etapa 1 (Pack 48-50)**: nada (la DB ya está bien dimensionada para el tráfico actual).
**Etapa 2 (Pack 50-55)**: Read replica en EU para servir panel staff EU.
   - Latencia panel EU: 300ms → 30ms.
   - DR: si US-East cae, podemos promover EU a primario (RTO 30min).
**Etapa 3 (Pack 60+)**: Sharding por region si entran clientes EU con cláusula de residency.
**Etapa 4 (futuro)**: evaluar active-active sólo si métricas justifican.

## Conflict resolution (cuando aplique)

| Tipo de conflicto | Estrategia |
| --- | --- |
| Insert con misma PK | Cada region genera PK con prefijo region (`'us-' || nextval('id_seq')`) o usar UUID v7. |
| Update del mismo registro | Last-Write-Wins por `updated_at`. |
| Delete vs Update | Tombstones + reconcile worker. |
| Counters (e.g. scan_count) | CRDT (`counters_us`, `counters_eu`) → SUM. |

## Costo aproximado

Render PG Standard "Pro" $90/mes por instancia.
- 1 primary US: $90
- + 1 read replica EU: $90 (más egress)
- + observabilidad multi-region (Datadog): $30-50

Total ~$210-250/mes para "Etapa 2", vs. $90 single region.

## Métricas para detonar la decisión

- p95 latency staff EU >500ms sostenido 1 semana.
- Bug/incident en panel EU bloquea >2 customer.
- Cliente EU pide cláusula GDPR residency (hard requirement).

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| WAN flap → lag de réplica grande | Slot retiene WAL → vigilancia + alerta a 5GB. |
| Promoción accidental (split-brain) | Fencing: `pg_promote` sólo via runbook + revocar replication slot al ex-primario. |
| App cache asume single region | Feature flag por cliente para usar replica regional. |
| Costos out-of-budget | Tier-down si tráfico baja; auto-scale storage. |

## Runbook resumido — failover (etapa 2)

1. Confirmar que US-East primario está realmente caído (no glitch DNS).
2. `pg_promote` en EU.
3. Cambiar `DATABASE_URL` a EU primary; rolling deploy de app.
4. Comunicar incident; eventualmente reverse-replicate cuando US-East vuelva.
5. Después de incident: postmortem.

Ver `disaster-playbook.md`.
