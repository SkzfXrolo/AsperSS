# repmgr alternative (Pack 48-H Round 5 · #136)

## Qué es repmgr

Herramienta 2ndQuadrant/EDB para **replicación streaming** + **failover** + **witness** + CLI `repmgr standby promote`.

## Comparación rápida Patroni vs repmgr

| Aspecto | Patroni | repmgr |
| --- | --- | --- |
| DCS integrado | Sí (requiere etcd/consul/k8s) | Menos opinion; puede usar voting + witness |
| Ecosistema K8s | Muy fuerte | Medio |
| Complejidad | Alta pero estándar cloud-native | Media en setups pequeños |
| Reconfig automática | Muy completa | Buena con repmgrd |

## Cuándo elegir repmgr

- Clusters pequeños on-prem sin deseo de operar etcd grande.
- Equipo ya familiarizado con repmgr.

## Argus

No aplica Render managed. Útil si self-host en VM.

## Comandos ilustrativos (no ejecutar aquí)

```bash
repmgr standby register
repmgr cluster show
repmgr standby promote --siblings-follow
```

## Referencias

- repmgr docs
- `docs/db/ha-patterns/patroni.md`
