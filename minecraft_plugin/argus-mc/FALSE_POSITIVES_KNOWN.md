# Argus MC — Known False Positives

Lista curada de FPs reproducibles, con causa raíz y cómo whitelistear /
mitigar. Si encontrás un FP nuevo no listado acá, abrí un issue con
log + repro steps.

## Mitigación general

### Permiso `argus.ac.bypass`

Cualquier player con este permiso queda **completamente excluido** de
todos los checks. Útil para staff con creative que se moverá raro.

```
luckperms group admin permission set argus.ac.bypass true
```

### Permiso por player

Si solo querés excluir a un player específico:

```
luckperms user PlayerName permission set argus.ac.bypass true
```

---

## FPs conocidos por check

### `speed_packet` / `velocity_packet`

**Causa**: Lag-spike server-side (TPS < 18). El cliente sigue enviando
movement packets a 20Hz pero el server piensa que el delta es "demás"
porque su clock es lento.

**Mitigación**:
- Activá `tuning.lag_compensation` (default ON, threshold TPS 18.5).
- Si tu server tiene mods pesados, baja `min_tps` a 15.0.

---

### `velocity_packet` tras knockback fuerte

**Causa**: Players con `Slowness` o `Resistance` reciben KB diferente
al esperado.

**Mitigación**:
- Subí `consec_high` de 4 a 6 en `velocity_packet`.
- Considerá `force_level: MID` para que nunca escale a HIGH/kick.

---

### `phase_packet` con puertas / trapdoors / fence-gates

**Causa**: Los packets de movimiento atraviesan brevemente bloques
"open" (puertas abiertas). El check chequea el material pero no el
estado open/closed.

**Mitigación**:
- Subí `consec_high` a 5.
- Considerá `report_to_backend: false` para no spam backend.

---

### `aim_snap_packet` con head-shot legítimo

**Causa**: Players experimentados hacen flick aim de 90° en < 100ms,
lo cual el check confunde con bot.

**Mitigación**:
- Subí `consec_high` de 3 a 5.
- Usá `killaura_aim_packet` que es más estricto (requiere rotation
  frozen + attack).

---

### `killaura_blocking_packet` con shield + jump-hit

**Causa**: Algunos plugins de PvP (PotPvP, FactionsX) permiten attack
mientras shield raised. El check lo flagea como cheat.

**Mitigación**:
- Si tu server tiene plugins que permiten esto:
  `anticheat.checks.killaura_blocking.enabled: false`.

---

### `liquidwalk_packet` / `liquidjesus_packet` con boats

**Causa**: Player montado en boat sobre water — el `onGround=true` se
dispara para la collision del boat.

**Mitigación**:
- El check ya tiene un guard `isInsideVehicle()`. Si igual flagea,
  es bug. Reportar.

---

### `noslowsneak_packet` con players bunny-hopping

**Causa**: Lunar / Badlion clients tienen "auto-sprint while sneak"
en algunas configs.

**Mitigación**:
- `tuning.client_whitelist.enabled: true` con relaxation 1.15.
- O bajar el check a `force_level: LOW`.

---

### `step_packet` con jump-boost / efectos

**Causa**: Stairs + jump boost III te dan un step de 1.5 blocks.

**Mitigación**:
- El check usa `MovementContext.jumpBoostAmp`. Si flagea, probablemente
  el `min_dy` está demasiado bajo. Subilo a 1.5.

---

### `regen_packet` post-totem / post-pot

**Causa**: Totem de la muerte regenera 1.0HP inmediatamente. Pot de
healing instantáneo I = 4.0HP en 1 tick.

**Mitigación**:
- El check tiene un guard `lastDamageTakenMs` que excluye recovery
  post-damage durante 1s. Si flagea fuera de eso, subir `max_hp_per_sec`
  a 1.0.

---

### `autoarmor_packet` con `/equip` plugin

**Causa**: Algunos servers tienen `/equip` que swappea armor sin
animation.

**Mitigación**:
- Desactivar el check o `force_level: LOW`.
- Idealmente, plugin `/equip` debería respetar `argus.ac.bypass` para
  el caller, pero no es estándar.

---

### `tracers_packet` con players invisibles legítimos

**Causa**: Spectator / vanish plugins. El check ve al "invisible" pero
en realidad no es target legítimo de aim.

**Mitigación**:
- El check ya tiene level MID (no HIGH). Si te molesta, desactivar.
- Mejor solución: el invisible debería tener `argus.ac.bypass`.

---

## ¿Cuándo whitelistear un check completo?

Si más del **5%** de tus players online están flageando el mismo check
sin razón aparente, **desactivá el check**. Es mejor un check muerto que
un mod que pierdes a manos del staff que kickea legit players.

Workflow:

```
/argus admin stats     # mirar top-violators
/argus admin debug X   # ver violations history de X
# si X es trusted, considerar bypass o tuning.
```
