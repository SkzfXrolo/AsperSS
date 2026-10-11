# Argus MC — Checks Index

Lista completa de checks anti-cheat con su nivel de severidad por defecto
y descripción corta. Para tuning fino, ver `TUNING_GUIDE.md`.

Total: **63 checks activos** (5 base Pack 47 + 12 packet base + 17 Round 2 + 20 Round 3 + 13 Round 4 — algunos solapan funcionalmente con variantes "advanced").

## Movement

| Check                 | Nivel | Notas                                                           |
|-----------------------|-------|-----------------------------------------------------------------|
| `timer_packet`        | HIGH  | Tasa de movement packets > cap                                   |
| `timer_jitter`        | HIGH  | Stddev de intervalos anómalo (timer alternado)                   |
| `phase_packet`        | HIGH  | Delta de posición atraviesa bloque sólido                        |
| `phaseclip_packet`    | CRIT  | Se mueve dentro de bloque sólido (arena/grava que cae no cuenta)  |
| `nofall_packet`       | HIGH  | onGround=true bajando sin bloque bajo los pies (suelo falso)      |
| `vclip_packet`        | HIGH  | Delta Y impossible en un packet                                  |
| `step_packet`         | MID   | Subida sin curva de salto                                         |
| `speed_packet`        | HIGH  | Velocidad horizontal > cap del modo                              |
| `velocity_packet`     | MID   | Cliente ignora velocity asignada                                  |
| `jetpack_packet`      | HIGH  | DeltaY positivo sostenido sin flight legítimo                    |
| `spider_packet`       | HIGH  | Subiendo pegado a pared sin climbable                            |
| `boat_fly_packet`     | HIGH  | Boat en aire sostenido sin gravedad                              |
| `boat_fly_advanced`   | HIGH  | Variante con sustained-horizontal-bps                            |
| `liquidwalk_packet`   | MID   | OnGround sobre agua/lava sin Frost Walker                         |
| `liquidjesus_packet`  | HIGH  | Caminando suspendido sobre liquido (delta-y ~ 0)                  |
| `noslowsneak_packet`  | HIGH  | Velocidad sneak > cap (~1.5 b/s)                                  |

## Combat

| Check                       | Nivel | Notas                                          |
|-----------------------------|-------|------------------------------------------------|
| `reach_packet`              | MID   | Distancia eye→target > cap                      |
| `reach3d_packet`            | HIGH  | Reach considerando AABB del target              |
| `killaura_swing_packet`     | MID   | Swing duplicado / no swing                       |
| `killaura_aim_packet`       | HIGH  | Rotation frozen antes del hit                    |
| `killaura_blocking_packet`  | HIGH  | Hit mientras blocking con shield                 |
| `killaura_rotation_packet`  | HIGH  | Snap yaw > 170° entre 2 packets                  |
| `killaura_noswing_packet`   | HIGH  | Attack sin animación swing reciente              |
| `killaura_thruwall_packet`  | HIGH  | Hit a través de bloques sólidos                  |
| `hitbox_packet`             | HIGH  | Hit fuera del AABB normal del target             |
| `backstab_packet`           | HIGH  | Hit con FOV > maxFov                             |
| `melee_fly_packet`          | HIGH  | Attacks hovering en el aire                      |
| `crit_packet`               | MID   | Crit con player onGround / no falling            |
| `aimbot_packet`             | HIGH  | Hit a target lejano salteando más cercanos       |

## Combat — projectile

| Check                   | Nivel | Notas                                              |
|-------------------------|-------|----------------------------------------------------|
| `projectile_aim_packet` | HIGH  | Proyectil con ángulo perfecto a target lejano      |
| `bow_aim_packet`        | HIGH  | Aim snap inmediatamente antes de release           |
| `fastbow_packet`        | HIGH  | Full-draw < 900ms (vanilla 1000)                    |
| `tracers_packet`        | MID   | Aim a player invisible durante N packets           |

## Use-item / consumption

| Check               | Nivel | Notas                                                |
|---------------------|-------|------------------------------------------------------|
| `fasteat_packet`    | HIGH  | Eat completo < 1500ms (vanilla 1610)                  |
| `autoeat_packet`    | HIGH  | Patrón attack→eat con N hits consecutivos             |
| `noslowdown_packet` | HIGH  | Mueve > 4 b/s mientras usa item                       |
| `autopotion_packet` | HIGH  | Pot drink < 200ms post-hit                             |

## Block interaction

| Check                       | Nivel | Notas                                          |
|-----------------------------|-------|------------------------------------------------|
| `fast_place_packet`         | MID   | > N placements/seg                              |
| `fast_break_packet`         | HIGH  | Break tiempo < hardness mínimo                  |
| `nuker_packet`              | HIGH  | Múltiples breaks mismo tick                      |
| `block_reach_packet`        | HIGH  | Block-interact > 5.5 m                           |
| `block_glitch_packet`       | HIGH  | Place/break a través de muros (raycast)         |
| `scaffold_rotation_packet`  | HIGH  | Pitch > 80° con placement bajo player           |
| `scaffold_tower_packet`     | HIGH  | Columna vertical perfecta                       |
| `scaffold_aim_packet`       | HIGH  | Coloca en un punto que no tiene en la mira      |

## Anti-bot / world

| Check                        | Nivel | Notas                                          |
|------------------------------|-------|------------------------------------------------|
| `chat_macro_packet`          | MID   | Mensajes idénticos con stddev baja             |
| `named_item_spam_packet`     | MID   | Rename rápido item en mano                      |
| `autoclicker_advanced_packet`| HIGH  | CPS analysis con varianza ≈ 0                   |
| `cps_packet`                 | MID   | CPS > cap                                       |
| `inv_move_packet`            | MID   | Movimiento mientras inventory abierto           |
| `invalid_rotation`           | MID   | Pitch fuera de [-90,90]                          |
| `item_pickup_packet`         | MID   | Pickup a > 1.5 m                                 |
| `inv_teleport_packet`        | HIGH  | Pos delta grande con inventory abierto           |
| `auto_totem_packet`          | MID   | Swap totem a offhand inmediato post-hit          |
| `auto_armor_packet`          | HIGH  | Armor change en combate < 300ms                  |
| `regen_packet`               | HIGH  | HP/seg > vanilla rate                            |
| `antikb_packet`              | HIGH  | Movimiento horizontal < KB esperado              |

## Misc / advanced

| Check              | Nivel | Notas                                                |
|--------------------|-------|------------------------------------------------------|
| `ping_spoof`       | MID   | KeepAlive RTT inflado artificialmente                 |
| `multi_velocity`   | HIGH  | Cliente ignora N velocities consecutivos              |
| `aim_snap_packet`  | MID   | Delta rotation entre packets > cap                    |

## Round 4 — módulos de clientes de hacks (probados contra bots que imitan Flux)

| Check                    | Nivel     | Notas                                                                 |
|--------------------------|-----------|-----------------------------------------------------------------------|
| `criticals_packet`       | MID/HIGH  | Mini-salto falso (<0.40) pegado a un ataque, 3/6 en 10s                |
| `strafe_packet`          | MID/HIGH  | Gira en el aire sin perder velocidad (v·0.91 + 0.026 máx)              |
| `safewalk_packet`        | MID/HIGH  | Frena justo en el borde sin agacharse, 3/6 en 15s                      |
| `scaffold_snap_packet`   | MID/HIGH  | Giro >90° en un tick pegado a colocar bajo los pies                    |
| `autoclicker_ticks_packet` | MID/HIGH | Macro externa: 40 clicks ≥9 CPS siempre en 2 intervalos de tick       |
| `airplace_packet`        | MID/HIGH  | Coloca contra un bloque que en el server es aire                       |
| `antiafk_packet`         | LOW/MID   | Rotación idéntica 40 ticks / saltos a intervalo fijo                   |
| `nuker_fov_packet`       | MID/HIGH  | Rompe bloques fuera de la mira (>50°), sin mirar velocidad (prisiones) |
| `antikb_packet`          | MID/HIGH  | Reescrito: desplazamiento EN la dirección del knockback durante ping+400ms |
| `speed_packet` (promedio) | MID/HIGH | Promedio de 1s según contexto: piso 6.3, saltando 7.9, con techo bajo 9.3 bps |
| `fast_place_packet` (ritmo) | MID/HIGH | 10 colocaciones a intervalo fijo más rápido que vanilla (200ms)      |
| `fastbow_packet` (cadencia) | MID/HIGH | ≥6 flechas/s (Paper cuenta la carga en ticks reales)                 |
| `bow_aimbot_packet`      | MID/HIGH  | Cargando el arco, la mira sigue a un objetivo en movimiento con desvío <0.8° (humano 1–5°); HIGH con 3 tiros en 60s |

## Round 5 — los que faltaban (probados con bots: hack detectado + versión legit limpia)

| Check | Nivel | Señal |
|-------|-------|-------|
| `inventory_macro_packet` | MID/HIGH  | ChestStealer/InvCleaner: 8 clicks a ritmo fijo (desvío <12ms), 4+ clicks en un tick, o click antes de ping+50ms al abrir un cofre (3 en 60s) |
| `autosoup_packet`        | MID/HIGH  | Cambiar al slot de sopa/poción, usarla y volver en <60ms, 3/6 en 10s     |
| `omnisprint_packet`      | MID/HIGH  | Sprint en el piso hacia atrás/costado (>100°) 8/20 ticks                 |
| `triggerbot_packet`      | MID/HIGH  | Reacción mediana ≤1 tick al entrar la mira + <10% de swings al aire (10 golpes) |
| `aim_gcd_packet`         | MID/HIGH  | ≥60% de los giros de pitch en pelea no son pasos enteros del mouse (aprende la sensibilidad del jugador). Un aim assist que redondea a la sensibilidad lo evade. |

## Pruebas (replay)

Cada alerta MID+ guarda `plugins/ArgusMC/evidence/<jugador>/<fecha>_<hack>.html`:
replay 3D autocontenido de 15s antes a 5s después (posiciones, giros, golpes con
distancia real, bloques de alrededor) con cámara cine/POV/libre y botón para
descargar video 1280×720 con el HUD. `#t=<seg>` en la URL abre ese instante.
Con `enforcement: true`, ningún kick/ban se aplica hasta que la prueba esté en
disco, y el ban exige 2 hacks distintos en HIGH+ (o 2 CRITICAL); el motivo del
ban incluye la ruta de la prueba.

---

Cada check puede:
- Desactivarse: `anticheat.checks.<name>.enabled: false`
- Cambiar nivel: `anticheat.checks.<name>.force_level: LOW|MID|HIGH|CRITICAL`
- Limitar acción: `anticheat.checks.<name>.max_action: alert|kick|force_ss|ban`
- Excluirse del backend: `anticheat.checks.<name>.report_to_backend: false`
- Excluirse de Discord: `anticheat.checks.<name>.discord: false`
- Excluirse del Oracle: `anticheat.checks.<name>.ai_oracle: false`

Ver ejemplos en `config.yml`.
