# Argus MC — Tuning Guide

## TL;DR

1. **Empezá en `observer`**: `anticheat.enforce: false`. Sólo logs y
   alerts; nadie es kickeado. Mirá `/argus admin stats` y los logs por
   ~24 horas.
2. Identifica qué checks tienen **muchos** flags vs. players sanos
   conocidos. Esos checks necesitan tuning.
3. **Bajá la severidad o subí el threshold** del check problemático,
   no lo desactives.
4. Cuando estés cómodo, `enforce: true`.

## Estructura de los thresholds

Cada check vive en `anticheat.checks.<name>`. Ejemplos típicos:

- `enabled: true|false` — kill switch.
- `min_X / max_X` — umbral numérico (m, ms, bps, °).
- `consec_mid: N` — N violations seguidos para escalar a MID.
- `consec_high: M` — M violations seguidos para escalar a HIGH.
- `force_level: <LOW|MID|HIGH|CRITICAL>` — fuerza un nivel.
- `max_action: <alert|kick|force_ss|ban>` — limita la acción aunque
  el nivel suba.

## Lag compensation (round 3)

Si tu server tiene TPS variable (server pesado, mods), activá:

```yaml
tuning:
  lag_compensation:
    enabled: true
    min_tps: 18.5         # bajo esto, suprime movement checks
    max_ping_ms: 250
```

**Importante**: `killaura_*`, `block_reach`, `scaffold_*`, `block_glitch`,
`autoclicker_advanced` NO se suprimen por lag (son detecciones discretas
que el lag no produce). Editar `tuning.lag_compensation.checks` para
adjustar la lista.

## Warmup grace period

5 segundos por defecto post-join, 2s post-teleport. Reducí si te molesta
en tu loadout, pero te vas a comer FPs por chunk-loading.

```yaml
tuning:
  warmup:
    enabled: true
    join_grace_ms: 5000
    teleport_grace_ms: 2000
```

## Client whitelist (opt-in, **spoofable**)

Reconoce brands legit (Lunar, Badlion) y aplica un multiplier sobre
thresholds:

```yaml
tuning:
  client_whitelist:
    enabled: true
    relaxation_multiplier: 1.10   # 10% más tolerancia
```

**Advertencia**: el brand del cliente se puede spoofear. Solo lo usamos
como "boost suave", nunca para bypass total. Recomendado para servers
con muchos players de Lunar/Badlion.

## False positive logger

Si activás `logging.fp_verbose: true`, cada violation cancelado por
lag/warmup/etc. queda en el log a level FINE. Útil para entender qué
está cancelando el plugin y por qué.

Ver via:
```
java -Djava.util.logging.config.file=logging.properties ...
```

## Checks típicamente "calientes" en servers reales

| Check                | Síntoma típico                  | Knob                       |
|----------------------|---------------------------------|----------------------------|
| `speed_packet`       | Lag spikes flageando ráfaga     | `min_tps` lag-comp ↑       |
| `velocity_packet`    | Spam tras knockback             | `consec_high` ↑            |
| `phase_packet`       | Doors / trapdoors               | `min_solidity` ↑           |
| `aim_snap_packet`    | Snap legítimo (head shot)       | `consec_high` ↑            |
| `noslowsneak`        | Players con permissions sneak   | desactivar para grupo X    |
| `tracers`            | Players cazando invis. legit    | bajar level a LOW          |

## Por-check enforcement override

```yaml
anticheat:
  checks:
    speed_packet:
      enabled: true
      force_level: MID        # nunca llegará a HIGH
      max_action: alert       # solo alert, nunca kick
      report_to_backend: false # no spam al backend en tuning
      discord: false           # no spam Discord
```

Esto te permite tener un check ACTIVO en "modo observer" mientras los
demás están en enforce.

## Trust score & Oracle

Si activás el Oracle ML (ver `ORACLE_INTEGRATION.md`), los checks
heredan automáticamente weighting por player. Útil para servers donde
algunos veteranos siempre flagean.

## Métricas / Prometheus

Activá `web.enabled: true` (round 2) y scrapeá `/metrics`. Métricas
relevantes:

- `argus_violations_total{check,level}` — counter por check.
- `argus_packets_received_total` — rate de packets, para sanity.

Si una check produce > 100/min en un server con < 50 players, es muy
probable un FP. Bajalo a `force_level: LOW` y mirá los logs.

## ¿Cuál es el "mejor" balance?

- Servers PvP competitivos (HCF, anchor): activá TODO HIGH+CRITICAL,
  weight Oracle weight 1.5 (agresivo), `enforce: true`.
- Servers casuales / SMP: dejá CRITICAL → kick, todo demás → alert.
- Servers anarchy: el plugin no sirve, los players ESPERAN cheats.

## Workflow recomendado

```
1. Día 1: observer mode, 24h log.
2. Día 2: identificar top-3 noisy checks; tune cada uno (force_level: LOW).
3. Día 3: enforce=true para CRITICAL only.
4. Semana 2: enforce=true para HIGH también.
5. Semana 3+: Oracle ML opt-in, calibrar pesos via dashboard.
```
