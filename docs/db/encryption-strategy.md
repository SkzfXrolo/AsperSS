# Argus Projects — Encryption strategy (DB + app) — Pack 48-H Round 2

## At rest

### Render PostgreSQL (producción actual)

- Los discos gestionados por Render **cifran en reposo** según su documentación de compliance (AES-256 típico en capa storage).
- **Acción:** confirmar en el panel de Render la línea "Encryption at rest: enabled" y exportar captura a evidencia de auditoría.

### Self-host / VM propia

| Opción | Pros | Contras |
| --- | --- | --- |
| **LUKS** full-disk | Transparente para PG | Requiere passphrase en boot (KMS / TPM) |
| **cloud volume encrypted** (EBS, GCE PD) | Sin cambios PG | Depende del cloud |
| **PostgreSQL TDE** (enterprise extensions) | Cifrado página-a-página | No en PG community open-source; coste licencia |

**Recomendación Argus:** permanecer en Render managed **o** LUKS + backups cifrados (ver `backup-strategy.md`).

## In transit

1. **Forzar SSL/TLS** entre app y Postgres:
   - Connection string: `sslmode=require` (o `verify-full` con CA corporativa).
2. **Validar en código:** `psycopg2.connect(DATABASE_URL, sslmode='require')` si la URL no lo trae.
3. **Render:** las URLs internas suelen ser TLS; verificar `sslmode` explícito evita downgrade.

**Red flag:** `sslmode=disable` en cualquier entorno que no sea dev local deliberado.

## Column-level encryption (PII sensible)

**Candidatos Argus:** `users.email`, `push_subscriptions.endpoint`, columnas `ip_address`, payloads JSON en `discord_queue.data`, `scan_results.extra` si contiene rutas de usuario.

| Enfoque | Pros | Contras |
| --- | --- | --- |
| **pgcrypto** (`pgp_sym_encrypt` / `pgp_pub_encrypt`) | Centralizado en DB; backups cifrados si clave separada | CPU en DB; rotación de claves compleja |
| **Application-level** (Fernet / AES-GCM en Python antes de INSERT) | Rotación y KMS más simple en app | Doble código PG/SQLite; búsquedas full-text difíciles |

**Recomendación:** **application-level** para email y tokens largos; **pgcrypto** opcional para columnas que deben quedar cifradas incluso en `SELECT *` accidental en psql.

### Lista mínima sugerida para `pgcrypto` (si se adopta)

1. `users.email` — reversible con `pgp_pub_decrypt` staff-only.
2. `push_subscriptions.p256dh` / `auth` — secretos de push.
3. `registration_tokens.token` — alta entropía pero defensa en profundidad.

**No** cifrar: `scans.id`, `verdict`, `plugin_violations.check_name` (necesitan indexación y agregación).

## Key management (orden de preferencia)

1. **AWS KMS / GCP KMS** — envuelve DEK (data encryption key).
2. **HashiCorp Vault** — dynamic secrets + audit log.
3. **Render encrypted env vars** — aceptable para clave simétrica rotada trimestralmente.
4. **Plain .env en repo** — **prohibido**.

## Checklist compliance (GDPR-ish)

- [ ] DPA con Render firmado.
- [ ] Retención documentada (`cleanup-policy-pack48.sql`).
- [ ] Derecho al olvido: script de anonimización (`dw-export-design.md` sección erase).
