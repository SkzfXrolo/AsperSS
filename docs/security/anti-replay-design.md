# Anti-Replay Protocol Design (Plugin/Scanner -> Web API)

## Objetivo

Evitar replay attacks en requests autenticadas desde:

- ArgusMC Plugin -> `web_app`
- ArgusScanner (desktop/linux/android) -> `web_app`

## Especificación del protocolo

Cada request firmada debe incluir:

- `X-Argus-Nonce`: UUIDv4 único por request
- `X-Argus-Timestamp`: epoch en milisegundos UTC
- `X-Argus-Signature`: HMAC-SHA256 (hex o base64; se recomienda hex)

## Canonical string to sign

```text
<METHOD>\n
<PATH>\n
<NONCE>\n
<TIMESTAMP_MS>\n
<BODY_SHA256_HEX>
```

Donde:

- `METHOD`: `GET|POST|PUT|DELETE` en mayúsculas
- `PATH`: solo path+query normalizada (sin esquema/host)
- `BODY_SHA256_HEX`: SHA-256 del body raw (vacío permitido para GET)

Firma:

```text
signature = HMAC_SHA256(secret, canonical_string)
```

## Server-side verification flow

1. Verificar presencia de headers.
2. Validar formato nonce UUIDv4.
3. Validar timestamp: tolerancia `±60s` respecto al reloj servidor.
4. Recalcular `BODY_SHA256_HEX` del request recibido.
5. Recalcular firma y comparar con `hmac.compare_digest`.
6. Verificar nonce no usado previamente para ese `client_id`.
7. Registrar nonce en cache anti-replay TTL=5 minutos.
8. Solo entonces procesar la request.

## Nonce cache

## Opción A (recomendada): Redis

- key: `argus:replay:<client_id>:<nonce>`
- value: `1`
- TTL: 300s
- operación atómica: `SET key 1 NX EX 300`

## Opción B: in-memory LRU/TTL

- usar estructura tipo `OrderedDict` + limpieza periódica
- apto para instancia única
- no apto multi-worker/multi-replica sin sincronización

## Clock skew y resiliencia

- ventana recomendada: `60s`
- en clientes con drift frecuente, permitir `90s` temporalmente por feature flag
- respuesta de error sugerida:
  - `401 invalid_signature`
  - `401 timestamp_out_of_window`
  - `409 nonce_reused`

## Compatibilidad gradual

1. fase `report-only`: validar y loguear sin bloquear.
2. fase `enforce` por endpoint sensible (`/api/plugin/*`, `/api/scans*`).
3. fase global para todos los clientes machine-to-machine.

## Ejemplo de pseudocódigo servidor (Python)

```python
import hashlib, hmac, time

def verify(req, secret, nonce_store):
    nonce = req.headers["X-Argus-Nonce"]
    ts = int(req.headers["X-Argus-Timestamp"])
    sig = req.headers["X-Argus-Signature"]

    now = int(time.time() * 1000)
    if abs(now - ts) > 60_000:
        return False, "timestamp_out_of_window"

    body = req.get_data() or b""
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"{req.method}\n{req.full_path}\n{nonce}\n{ts}\n{body_hash}"
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "invalid_signature"

    if not nonce_store.put_if_absent(nonce, ttl=300):
        return False, "nonce_reused"
    return True, "ok"
```

## Test vectors (HMAC-SHA256)

Usar estos vectores para validar implementación cruzada:

- `secret`: `argus_test_secret_123`
- `method`: `POST`
- `path`: `/api/plugin/issue-token`
- `nonce`: `550e8400-e29b-41d4-a716-446655440000`
- `timestamp`: `1760000000000`
- `body`:
  ```json
  {"staff":"ModA","target":"PlayerX","reason":"check"}
  ```
- `body_sha256_hex`:
  `4f9ab5b66a37d5445ec3f8d0f0d83c5e7c0677a1c67a08438f53d4f711b5f3b5`
- `canonical`:
  ```text
  POST
  /api/plugin/issue-token
  550e8400-e29b-41d4-a716-446655440000
  1760000000000
  4f9ab5b66a37d5445ec3f8d0f0d83c5e7c0677a1c67a08438f53d4f711b5f3b5
  ```

Nota: la firma final depende exactamente de saltos de línea y serialización del body raw. D debe congelar canonicalización y agregar tests unitarios golden.
