# Data classification (Pack 48-H Round 3 · #102)

## Esquema de tiers

| Tier | Definición | Ejemplo | Tratamiento |
| --- | --- | --- | --- |
| **PII-H** (high) | Identifica a una persona y compromete cuenta si se filtra | password hash, session token, IP, email + IP combo | encryption at rest + in transit, no log, hash en DW |
| **PII-M** (medium) | Identifica directa o indirectamente | email, minecraft username, machine_id | encryption in transit, anonimizar en DW |
| **PII-L** (low) | Pseudonimizada o agregada | UUID, hash, scan_id | log normal |
| **INT-B** (internal-business) | Lógica de producto, no PII | risk_score, verdict, AI weights, plugin version | acceso role-based |
| **INT-O** (internal-ops) | Métricas, salud, ops | counts, p95, lag, error_msg | acceso DBA |
| **PUB** (public) | Versionado, docs públicos | release notes, plugin version list | repo público |

Cada tier define **controles** mínimos en `encryption-strategy.md` + `security-hardening.md`.

## Clasificación por tabla

| Tabla | Tier predominante | Notas |
| --- | --- | --- |
| `users` | PII-H | password_hash, email, last_ip |
| `companies` | PII-M | razón social, billing_email |
| `user_sessions` | PII-H | session_token, ip |
| `oauth_tokens` | PII-H | access_token, refresh_token |
| `scan_tokens` | PII-M | token expira, asociado a player |
| `scans` | PII-M | minecraft_username, machine_id |
| `scan_results` | INT-B | json output del scanner |
| `plugin_violations` | INT-B | tipo de cheat detectado |
| `ai_decisions_log` | INT-B + PII-M | player_uuid, decision |
| `ai_player_profiles` | PII-M | username, comportamiento |
| `ai_feedback` | INT-B | feedback humano |
| `ai_model_versions` | INT-B | metadata del modelo |
| `ban_history` | PII-M | quien banneó a quien |
| `staff_audit_log` | INT-O + PII-M | acción de staff |
| `company_plugin_keys` | PII-H | key secreta |
| `plugin_servers` | PII-M | server name, IP |
| `chat_logs` | PII-M | contenido chat MC |
| `rate_limit_buckets` | INT-O | counters por IP |
| `notifications` | PII-M | email destino |
| `mv_*` (matviews) | INT-O | agregados |
| `etl_runs`, `mv_refresh_log` | INT-O | metadata |

> Tabla completa actualizada en `er-diagram.md` con leyenda visual.

## Controles por tier

### PII-H

- **At rest**: cifrado a nivel filesystem (Render lo provee). Para máxima paranoia, application-level encryption con KMS (ver `encryption-strategy.md`).
- **In transit**: TLS estricto (`sslmode=verify-full`).
- **Logs**: nunca incluir el valor crudo (sanitizar en logger).
- **Backups**: GPG encrypted (ver `scripts/db/backup-automation.sh`).
- **Acceso DBA**: requiere ticket de soporte; auditado.
- **Retention**: borrar al `DELETE user` o al expirar token.

### PII-M

- **At rest**: cifrado filesystem.
- **In transit**: TLS.
- **DW export**: anonimizar (hash o tokenizar).
- **Logs**: enmascarar (`email = "j***@example.com"`).
- **Retention**: alineado con `cleanup-policy-pack48.sql`.

### PII-L

- **At rest**: estándar.
- **In transit**: TLS.
- **Logs**: permitido.
- **Retention**: indefinida si está derivada de PII ya expirada.

### INT-B

- Acceso por rol (admin, staff, analyst).
- Backups normales.
- Versionado (ai_model_versions) inmutable.

### INT-O

- Acceso DBA / SRE.
- Retention corta (90d default).

### PUB

- Repo público. Cero control.

## Tabla de columnas críticas (subset)

| Tabla.columna | Tier | Acción recomendada |
| --- | --- | --- |
| `users.password_hash` | PII-H | bcrypt cost ≥12; NO log |
| `users.email` | PII-M | sanitizar logs, hash en DW |
| `users.last_ip` | PII-H | almacenar /24 truncated o hash |
| `user_sessions.token` | PII-H | rotación + secure cookie |
| `oauth_tokens.access_token` | PII-H | enviar a Vault si posible |
| `scan_tokens.token` | PII-H | short-lived (15min) |
| `scans.minecraft_username` | PII-M | normalizar lowercase |
| `scans.machine_id` | PII-M | hash en DW |
| `plugin_servers.ip` | PII-M | almacenar host + /24, NO ip pública completa si no fue necesaria |
| `chat_logs.content` | PII-M | retención corta (30d), filtrar slurs antes |
| `company_plugin_keys.key_value` | PII-H | only show last 4 en UI |

## GDPR / "right to be forgotten"

`DELETE FROM users WHERE id=$1` debe cascadear correctamente a tablas con PII-H/M ligadas:

- user_sessions
- oauth_tokens
- notifications
- staff_audit_log (¿borrar? legalmente requerido conservar audit. Solución: tokenizar `user_id → hash` en lugar de borrar fila).

`docs/db/findings-pack48.md` ya marcó cascades faltantes (F-005, F-006). Resolver antes de prometer "right to be forgotten".

## Auditoría periódica

Cada Pack:
- Re-validar esta tabla contra schema actual.
- Detectar columnas nuevas no clasificadas (script futuro: `column_classification_diff.py`).
- Revisar reportes/dashboards: ¿exponen PII innecesariamente?
