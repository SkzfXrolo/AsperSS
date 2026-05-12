# Argus MC — Oracle ML Integration

A partir de Pack 48 round 3 el plugin puede consultar un endpoint ML
externo (el "Argus Oracle") para ponderar cada violation antes de
aplicar enforcement. Útil para:

- Reducir false positives (Oracle dice "lag, no cheat" → no se kicka).
- Subir severidad cuando el modelo está MUY seguro (Oracle dice
  "alto riesgo" → MID se vuelve HIGH y se ejecuta kick automático).
- Telemetría: el backend ve violations agregadas y puede mejorar el
  modelo en lote.

## Estado por defecto

**OFF.** No requiere ninguna config para que el plugin funcione. El
Oracle es **opt-in**.

## Cómo activarlo

1. Levantá el endpoint en tu backend Argus (o usá el oficial).
   El endpoint espera un POST JSON:

   ```json
   {
     "player_uuid": "uuid",
     "player_name": "Tester",
     "check": "speed_packet",
     "level": "MID",
     "details": "bps=8.2",
     "trust_score": 50.0
   }
   ```

   y devuelve:

   ```json
   { "weight": 1.3, "label": "likely_cheat" }
   ```

2. En `config.yml`:

   ```yaml
   oracle:
     enabled: true
     url: "https://argus.example.com/api/oracle/evaluate-mc-violation"
     api_key: "REEMPLAZA_UN_SECRETO_LARGO"
     timeout_ms: 1500
     cache_ttl_ms: 30000
     weight_floor: 0.6
     weight_ceiling: 1.5
     heartbeat_url: "https://argus.example.com/api/oracle/heartbeat-mc"
     applier:
       upgrade_above: 1.2     # > → sube de nivel
       downgrade_below: 0.7   # < → baja de nivel
       suppress_below: 0.4    # < → ignora el violation
   ```

3. `/argus admin reload`.
4. Confirmá con `/argus admin menu` → Oracle Stats → debería decir ON.

## Cómo se aplica el weight

| Weight       | Acción                          |
|--------------|---------------------------------|
| >= 1.2       | Sube un escalón (MID→HIGH...)   |
| 0.7–1.2      | Sin cambio                      |
| 0.4–0.7      | Baja un escalón                 |
| < 0.4        | **Suprime** el violation        |

CRITICAL no puede subir más; LOW no puede bajar más.

## Cache

Cada `(player UUID, check)` se cachea durante `cache_ttl_ms` (default
30s). Una llamada por minuto por player-check es lo habitual, NO una
por violation — esto evita matar el backend.

## Heartbeat

Cada `heartbeat_interval_s` segundos el plugin manda un beat con
metadata del server (uptime, online players, TPS, mc version).
Permite al backend ver instalaciones Argus activas y enriquecer las
evaluations futuras.

Si `heartbeat_url` está vacío, el heartbeat queda dormido.

## Fail-open

Si el endpoint está caído / lento / devuelve no-2xx:

- weight neutro 1.0 (sin cambio en severidad).
- Log a level FINE (no INFO).
- El enforcement local sigue normal — el Oracle es **opcional**.

## Por-check override

Si querés que el Oracle no influya en un check (ej: Killaura no necesita
ML, es discreto), poné:

```yaml
anticheat:
  checks:
    killaura_aim:
      ai_oracle: false
```

## Privacidad

Solo se manda el UUID + nombre + check + details. NO se mandan
coordenadas, inventario ni chat. Si tu backend está OFF de red pública
(o no usás Oracle) ningún dato del player sale del server.
