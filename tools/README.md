# Argus · Tools

Herramientas auxiliares de desarrollo y análisis.

## `inspect_scan.py`

CLI para revisar scans del proyecto sin necesidad de loguearse al panel web.
Pensado para que el agente IA pueda analizar el último scan cuando se le pida.

### Setup (una sola vez)

```bash
python tools/inspect_scan.py setup
```

Modos de conexión disponibles (en orden de preferencia):

1. **PostgreSQL directo** — más rápido. Pide la `DATABASE_URL` de Render.
2. **HTTP API + API_KEY** — requiere haber configurado la env var `API_KEY` en Render.
3. **HTTP API + cookie de sesión** — pegas el valor de la cookie `session`
   tras loguearte en el panel (DevTools → Application → Cookies).

Las credenciales se guardan en `tools/.argus_creds.json` (gitignored).

También se pueden pasar por env vars:

```bash
DATABASE_URL=postgresql://... python tools/inspect_scan.py latest
API_BASE_URL=https://... API_KEY=... python tools/inspect_scan.py latest
```

### Uso

```bash
# Listar últimos scans
python tools/inspect_scan.py list           # 20 por defecto
python tools/inspect_scan.py list 50

# Ver el último scan completo (con todos los hallazgos)
python tools/inspect_scan.py latest

# Ver un scan específico por id
python tools/inspect_scan.py show 1234

# Buscar scans por nombre / usuario MC / IP
python tools/inspect_scan.py find robin
python tools/inspect_scan.py find 192.168

# Stats agregadas de los últimos 200 scans
python tools/inspect_scan.py stats

# Auditar falsos positivos en los últimos N scans
python tools/inspect_scan.py fp_audit 100
```

### Output

Salida con colores ANSI. Si rediriges a un archivo o ejecutas en CI:

```bash
NO_COLOR=1 python tools/inspect_scan.py latest > scan.txt
```

### Dependencias

* PostgreSQL: `pip install psycopg2-binary`
* HTTP: `pip install requests`

(Ambas suelen estar ya instaladas si tienes el `web_app` corriendo.)
