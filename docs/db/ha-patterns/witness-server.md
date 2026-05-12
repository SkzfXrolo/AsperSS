# Witness server pattern (Pack 48-H Round 5 · #136)

## Problema

En un cluster de **2 nodos** (primary + standby), si el primary se aísla de red pero sigue vivo, ambos pueden creer ser primary → **split-brain**.

## Solución: witness

Un **witness** es un nodo ligero (sin datos PG productivos) que participa en **quorum** de elecciones (Patroni DCS vote) o arbitraje de salud.

- No ejecuta PostgreSQL de producción.
- Corre agente (Patroni/watchdog) o consul/etcd member.

## Patroni

Patroni usa DCS; el witness puede ser **etcd** node pequeño o miembro voter sin data directory grande.

## Repmgr

`repmgr witness` crea nodo que vota en failover de 2-node clusters.

## Cuándo aplica Argus

Sólo si Argus migra a **self-managed HA** (Kubernetes, VMs). En Render: patrón no expuesto; usar features nativas del proveedor.

## Costo

VM tiny + monitoreo; crítico para RTO < 5 min en 2-AZ.

## Referencias

- `docs/db/ha-patterns/patroni.md`
- `docs/db/ha-patterns/repmgr.md`
