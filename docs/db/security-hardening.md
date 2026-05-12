# DB security hardening (Pack 48-H Round 3 · #108)

## Capas

```
[App] ─TLS─► [PgBouncer] ─TLS─► [Postgres]
                                   │
                                   ├── pg_hba.conf (auth)
                                   ├── roles & GRANT/REVOKE
                                   ├── Row-Level Security
                                   ├── pgaudit (logging)
                                   └── encryption (filesystem + column-level)
```

## 1. `pg_hba.conf` — autenticación

Render maneja `pg_hba.conf` por nosotros. Para self-host/Aurora:

```
# TYPE   DATABASE    USER          ADDRESS           METHOD
hostssl  argus_prod  app           0.0.0.0/0         scram-sha-256
hostssl  argus_prod  monitor_ro    10.0.0.0/8        scram-sha-256
hostssl  replication replicator    10.0.0.5/32       scram-sha-256
local    all         all                              peer
host     all         all           0.0.0.0/0         reject
```

Reglas:

- Sólo `hostssl` (TLS obligatorio).
- `scram-sha-256` (no `md5`, no `password`).
- Restricciones por IP donde sea posible.
- `reject` explícito al final.

## 2. Roles

Diseñar **separación de privilegios**:

| Rol | Privilegios | Uso |
| --- | --- | --- |
| `argus_owner` | OWNER del DB | sólo migrations |
| `app` | SELECT/INSERT/UPDATE/DELETE en tablas público | Flask app |
| `app_ro` | SELECT en tablas público | dashboards read-only |
| `replicator` | REPLICATION | streaming/logical |
| `monitor_ro` | pg_monitor (PG10+), SELECT en pg_stat_* | Grafana |
| `dba` | superuser | DBA on-call |
| `analyst` | SELECT en `dw_*` y `agg_*` | analítica externa |

Setup:

```sql
CREATE ROLE app           LOGIN PASSWORD '...';
CREATE ROLE app_ro        LOGIN PASSWORD '...';
CREATE ROLE replicator    LOGIN REPLICATION PASSWORD '...';
CREATE ROLE monitor_ro    LOGIN PASSWORD '...';
GRANT pg_monitor TO monitor_ro;

GRANT CONNECT ON DATABASE argus_prod TO app, app_ro, monitor_ro, analyst;
GRANT USAGE   ON SCHEMA public TO app, app_ro, monitor_ro;

-- app puede DML
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

-- app_ro sólo SELECT
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_ro;

-- futuras tablas heredan
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO app_ro;
```

## 3. `REVOKE` schema `public`

Por default, `PUBLIC` puede crear objetos en `public`. Esto es inseguro.

```sql
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE argus_prod FROM PUBLIC;
GRANT  CREATE ON SCHEMA public TO argus_owner;
```

## 4. Row-Level Security (RLS) para multi-tenancy

**Hoy**: tenancy se enforce **en la app** (WHERE company_id = current_user_company). Si la app tiene un bug → leak cross-tenant.

**Con RLS**: PG enforce a nivel kernel, imposible bypassear desde la app.

### Setup por tabla

```sql
-- Suponer una variable de sesión 'app.company_id' que la app SET al inicio
-- de cada request.

ALTER TABLE scans ENABLE ROW LEVEL SECURITY;

CREATE POLICY scans_isolation ON scans
    USING (company_id = current_setting('app.company_id', true)::int);

-- Para inserts también:
CREATE POLICY scans_insert ON scans
    FOR INSERT
    WITH CHECK (company_id = current_setting('app.company_id', true)::int);

-- Bypass para admin / migrations:
ALTER TABLE scans FORCE ROW LEVEL SECURITY;
GRANT BYPASS RLS ... (PG no tiene grant directo; usar ALTER ROLE bypassrls).
ALTER ROLE argus_owner BYPASSRLS;
```

### Aplicar en cada request

```python
# en app.py al inicio de cada request
@app.before_request
def set_tenant_context():
    cid = current_user.company_id  # del session/JWT
    with db.session.begin():
        db.session.execute(text("SELECT set_config('app.company_id', :v, false)"), {"v": str(cid)})
```

(No tocar app code en este Round; sólo dejar la spec.)

### Tablas con `company_id` para activar RLS (post-F-001)

- scans (depende de F-001)
- scan_results, scan_tokens, plugin_violations (via scan)
- ai_decisions_log, ai_player_profiles, ai_feedback
- ban_history, chat_logs, plugin_servers
- company_plugin_keys
- staff_audit_log (selectivo)
- notifications

**No** habilitar RLS en tablas globales (companies, ai_model_versions).

## 5. `pgaudit` — audit logging

```sql
CREATE EXTENSION IF NOT EXISTS pgaudit;
ALTER SYSTEM SET pgaudit.log = 'ddl, role, write';
SELECT pg_reload_conf();
```

Genera log line por cada DDL, GRANT, INSERT/UPDATE/DELETE. Cost: aumenta logs.

Forward logs → SIEM via syslog. Retención >365d para compliance.

## 6. Encryption

### At rest

- Render PG: ya cifrado (LUKS).
- Self-host: LUKS o `cryptsetup` en filesystem; PG TDE (Crunchy fork) sólo si compliance hard requirement.

### In transit

- `sslmode=verify-full` desde la app.
- `client_min_messages = warning` para no leak query SQL en error.

### Column-level

Ver `encryption-strategy.md`. Resumen:

- `users.last_ip` → encryptar con `pgcrypto` + KMS key.
- `chat_logs.content` → encryptar a nivel app antes de INSERT.
- `oauth_tokens.access_token` → ya debería ser sólo hash, nunca plaintext.

## 7. Passwords

- `password_hash` debe ser bcrypt (cost ≥12) o Argon2id.
- Rotación obligatoria para `app`, `replicator`, `dba` cada 90 días.
- No incluir password en `DATABASE_URL` versionado; usar Render env vars + Vault.

## 8. Backup encryption

Ver `backup-strategy.md`. Backups GPG-encrypted con public key del Founder.

## 9. Network

- DB **no debe** estar expuesta a Internet (sólo VPC interno).
- Render permite private networking entre services.
- Si necesitamos acceso externo (DBA), levantar bastion + SSH tunnel.
- Firewall: deny by default, allow desde IPs específicas para `dba`.

## 10. Auditoría periódica

Mensual:

- `\du` → lista de roles, ¿alguno nuevo no autorizado?
- `\dp scans` → permisos correctos?
- `SELECT * FROM pg_settings WHERE name LIKE 'ssl%';` → SSL on?
- Grep app.py por SQL hardcoded sin tenant filter (riesgo de leak).

Trimestral:

- Revisión de findings de `tenant-isolation-checks.sql`.
- Pen test sobre endpoints API.

Anual:

- Audit externo (SOC2 / ISO27001 si entramos a compliance).

## Checklist de hardening — estado actual vs target

| Item | Estado actual | Target Pack 48-50 |
| --- | --- | --- |
| `hostssl` only | ✅ (Render) | ✅ |
| `scram-sha-256` | ✅ (PG13+) | ✅ |
| TLS app↔DB | ⚠️ verificar `sslmode=require` | `verify-full` |
| Roles segregados | ❌ (app == owner) | ✅ |
| REVOKE schema public | ❌ | ✅ |
| RLS habilitado | ❌ | ✅ post-F-001 |
| pgaudit | ❌ | parcial (DDL, role) |
| Column encryption PII | ❌ | columnas críticas |
| Backups encrypted | ⚠️ depende del setup | ✅ (script entregado) |
| Password rotation | ❌ | proceso 90d |
| Network: DB en VPC privado | ⚠️ revisar | ✅ |

## Compliance roadmap (cuando aplique)

| Stage | Acciones DB |
| --- | --- |
| SOC2 Type I | RLS + pgaudit + DR drills documentados |
| SOC2 Type II | + monitoreo continuo + reviews trimestrales |
| GDPR | + data classification + right-to-be-forgotten flows |
| HIPAA | column encryption full + signed BAA con cloud |
| PCI | tokenización + RLS estricto |

## Referencias internas

- `encryption-strategy.md`
- `data-classification.md`
- `backup-strategy.md`
- `disaster-playbook.md`
