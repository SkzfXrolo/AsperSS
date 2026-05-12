# Argus MC — Checks Index

Lista completa de checks anti-cheat con su nivel de severidad por defecto
y descripción corta. Para tuning fino, ver `TUNING_GUIDE.md`.

Total: **48 checks activos** (5 base Pack 47 + 12 packet base + 17 Round 2 + 20 Round 3 — algunos solapan funcionalmente con variantes "advanced").

## Movement

| Check                 | Nivel | Notas                                                           |
|-----------------------|-------|-----------------------------------------------------------------|
| `timer_packet`        | HIGH  | Tasa de movement packets > cap                                   |
| `timer_jitter`        | HIGH  | Stddev de intervalos anómalo (timer alternado)                   |
| `phase_packet`        | HIGH  | Delta de posición atraviesa bloque sólido                        |
| `phaseclip_packet`    | CRIT  | Player permanece dentro de bloque sólido                         |
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

---

Cada check puede:
- Desactivarse: `anticheat.checks.<name>.enabled: false`
- Cambiar nivel: `anticheat.checks.<name>.force_level: LOW|MID|HIGH|CRITICAL`
- Limitar acción: `anticheat.checks.<name>.max_action: alert|kick|force_ss|ban`
- Excluirse del backend: `anticheat.checks.<name>.report_to_backend: false`
- Excluirse de Discord: `anticheat.checks.<name>.discord: false`
- Excluirse del Oracle: `anticheat.checks.<name>.ai_oracle: false`

Ver ejemplos en `config.yml`.
