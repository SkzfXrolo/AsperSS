# Failover strategies (Pack 48-H Round 5 · #136)

## Tipos

| Estrategia | Descripción | RTO típico |
| --- | --- | --- |
| Manual | DBA `promote` tras verificación | 15–60 min |
| Semi-auto | Orchestrator sugiere; humano confirma | 5–15 min |
| Full-auto | Patroni/repmgr + consul/etcd | 30 s–5 min |

## Checklist pre-failover

1. Confirmar primary **realmente** down (evitar split-brain).
2. Verificar lag de replicas < SLA.
3. Congelar escrituras en app (maintenance flag) si hay duda.
4. Promover la **mejor** replica (menor lag, más saludable).
5. Actualizar DNS / service discovery / connection pooler.
6. Reconfigurar replicas restantes para seguir al nuevo primary.
7. Post-mortem + validar backups.

## Split-brain prevention

- **Quorum** en DCS (etcd/Zookeeper/consul) Patroni.
- **fencing**: STONITH IPMI / API cloud para aislar nodo zombie.
- **witness** para clusters 2 nodos.

## Connection string

Usar endpoint **VIP** o PgBouncer que Patroni reconfigura tras switchover.

## Argus

En Render: failover suele ser **product feature** o **recrear instancia**; no Patroni usuario. Documentar RTO/RPO real del proveedor.

## Referencias

- `docs/db/ha-patterns/patroni.md`
- `docs/db/disaster-playbook.md`
