"""Argus · Scan Inspector CLI
============================

Herramienta de línea de comandos para que el agente IA pueda revisar
scans del proyecto sin necesidad de loguearse al panel.

CREDENCIALES (modo de conexión, en orden de preferencia):
  1) DATABASE_URL → conexión directa a PostgreSQL (más rápido)
  2) API_BASE_URL + API_KEY → conexión vía HTTP (header X-API-Key)
  3) API_BASE_URL + SESSION_COOKIE → conexión vía HTTP (cookie 'session')

Las credenciales se guardan en tools/.argus_creds.json (gitignored)
o se leen de variables de entorno.

USO:
  python tools/inspect_scan.py setup              # configura credenciales (interactivo)
  python tools/inspect_scan.py latest             # último scan completo
  python tools/inspect_scan.py list [N=20]        # lista últimos N scans
  python tools/inspect_scan.py show <id>          # detalle de un scan
  python tools/inspect_scan.py stats              # agregados rápidos
  python tools/inspect_scan.py find <texto>       # busca scans por nombre/ip/user
  python tools/inspect_scan.py fp_audit [N=50]    # audita falsos positivos en últimos N

Diseñado para output optimizado en terminal: ANSI color + jerarquía visual.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# UTF-8 stdout en Windows (evita UnicodeEncodeError con cp1252)
try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

# ── Constantes ───────────────────────────────────────────────────────────────
TOOL_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = TOOL_DIR.parent
CREDS_FILE  = TOOL_DIR / '.argus_creds.json'
CONFIG_PATH = PROJECT_DIR / 'config.json'

# ── ANSI colors ──────────────────────────────────────────────────────────────
NO_COLOR = os.environ.get('NO_COLOR') or not sys.stdout.isatty()
class C:
    R   = '' if NO_COLOR else '\033[0m'
    B   = '' if NO_COLOR else '\033[1m'
    DIM = '' if NO_COLOR else '\033[2m'
    UND = '' if NO_COLOR else '\033[4m'
    RED = '' if NO_COLOR else '\033[91m'
    GRN = '' if NO_COLOR else '\033[92m'
    YEL = '' if NO_COLOR else '\033[93m'
    BLU = '' if NO_COLOR else '\033[94m'
    MAG = '' if NO_COLOR else '\033[95m'
    CYN = '' if NO_COLOR else '\033[96m'
    GRY = '' if NO_COLOR else '\033[90m'
    BG_RED = '' if NO_COLOR else '\033[41m'
    BG_GRN = '' if NO_COLOR else '\033[42m'

ALERT_COLORS = {
    'CRITICAL':         C.BG_RED + C.B + ' CRITICAL ' + C.R,
    'MUY_SOSPECHOSO':   C.RED   + ' MUY_SOSPECHOSO ' + C.R,
    'SOSPECHOSO':       C.YEL   + ' SOSPECHOSO ' + C.R,
    'POCO_SOSPECHOSO':  C.GRY   + ' POCO_SOSPECHOSO ' + C.R,
    'PAGINA_SOSPECHOSA':C.MAG   + ' WEB ' + C.R,
    'CLEAN':            C.GRN   + ' CLEAN ' + C.R,
    'NORMAL':           C.GRY   + ' NORMAL ' + C.R,
}

def alert_label(level: str) -> str:
    return ALERT_COLORS.get((level or '').upper(), C.GRY + ' ? ' + C.R)


# ── Credenciales / setup ─────────────────────────────────────────────────────
def load_creds() -> dict:
    """Lee credenciales desde env > .argus_creds.json > config.json."""
    creds: dict = {}
    if CREDS_FILE.exists():
        try:
            creds.update(json.loads(CREDS_FILE.read_text(encoding='utf-8')))
        except Exception:
            pass
    # Env vars override file
    for k in ('DATABASE_URL', 'API_BASE_URL', 'API_KEY', 'SESSION_COOKIE', 'API_URL'):
        v = os.environ.get(k)
        if v:
            creds[k] = v
    if 'API_BASE_URL' not in creds and 'API_URL' in creds:
        creds['API_BASE_URL'] = creds['API_URL']
    # Fallback: leer api_url de config.json del scanner
    if 'API_BASE_URL' not in creds and CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            api_url = cfg.get('api_url') or cfg.get('web_url')
            if api_url:
                creds['API_BASE_URL'] = api_url
        except Exception:
            pass
    return creds


def save_creds(creds: dict) -> None:
    CREDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CREDS_FILE.write_text(json.dumps(creds, indent=2), encoding='utf-8')
    print(f"{C.GRN}✓ Credenciales guardadas en {CREDS_FILE}{C.R}")


def cmd_setup() -> None:
    """Setup interactivo de credenciales."""
    print(f"\n{C.B}{C.CYN}━━━ Argus Inspector · Setup ━━━{C.R}\n")
    print("Elige el modo de conexión:")
    print(f"  {C.B}1{C.R}) PostgreSQL directo (recomendado, más rápido)")
    print(f"  {C.B}2{C.R}) HTTP API + API_KEY")
    print(f"  {C.B}3{C.R}) HTTP API + cookie de sesión (login del panel)")
    print()
    choice = input(f"Modo [1/2/3]: ").strip() or '1'
    creds = load_creds()
    if choice == '1':
        url = input(f"DATABASE_URL (postgresql://...): ").strip()
        if url:
            creds['DATABASE_URL'] = url
    elif choice == '2':
        base = input(f"API_BASE_URL [{creds.get('API_BASE_URL', 'https://asperss.onrender.com')}]: ").strip()
        if base:
            creds['API_BASE_URL'] = base
        elif 'API_BASE_URL' not in creds:
            creds['API_BASE_URL'] = 'https://asperss.onrender.com'
        key = input(f"API_KEY: ").strip()
        if key:
            creds['API_KEY'] = key
    elif choice == '3':
        base = input(f"API_BASE_URL [{creds.get('API_BASE_URL', 'https://asperss.onrender.com')}]: ").strip()
        if base:
            creds['API_BASE_URL'] = base
        elif 'API_BASE_URL' not in creds:
            creds['API_BASE_URL'] = 'https://asperss.onrender.com'
        print("Pega el valor de la cookie 'session' (login en panel y copia desde DevTools):")
        cookie = input(f"SESSION_COOKIE: ").strip()
        if cookie:
            creds['SESSION_COOKIE'] = cookie
    else:
        print(f"{C.RED}Opción inválida{C.R}")
        sys.exit(1)
    save_creds(creds)
    print(f"\n{C.GRN}Listo. Probando conexión…{C.R}\n")
    backend = get_backend()
    try:
        scans = backend.list_scans(limit=1)
        print(f"{C.GRN}✓ Conexión OK · {len(scans)} scan(s) accesible(s){C.R}")
    except Exception as e:
        print(f"{C.RED}✗ Error: {e}{C.R}")


# ── Backends de acceso a datos ───────────────────────────────────────────────
class Backend:
    """Interfaz común: list_scans / get_scan / stats."""
    name = 'base'

    def list_scans(self, limit: int = 20) -> list[dict]:
        raise NotImplementedError

    def get_scan(self, scan_id: int) -> Optional[dict]:
        raise NotImplementedError

    def find_scans(self, q: str, limit: int = 20) -> list[dict]:
        raise NotImplementedError


class PgBackend(Backend):
    name = 'postgres'

    def __init__(self, url: str):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise RuntimeError(
                "psycopg2 no está instalado. Ejecuta: pip install psycopg2-binary"
            )
        self.conn = psycopg2.connect(url)
        self._RealDictCursor = RealDictCursor

    def _cur(self):
        return self.conn.cursor(cursor_factory=self._RealDictCursor)

    def list_scans(self, limit: int = 20) -> list[dict]:
        with self._cur() as cur:
            cur.execute(
                """SELECT id, machine_name, minecraft_username, ip_address, country,
                          status, started_at, completed_at, total_files_scanned,
                          issues_found, scan_duration, risk_score, verdict
                     FROM scans
                    ORDER BY id DESC LIMIT %s""",
                (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def find_scans(self, q: str, limit: int = 20) -> list[dict]:
        like = f"%{q}%"
        with self._cur() as cur:
            cur.execute(
                """SELECT id, machine_name, minecraft_username, ip_address, country,
                          status, started_at, completed_at, total_files_scanned,
                          issues_found, scan_duration, risk_score, verdict
                     FROM scans
                    WHERE COALESCE(machine_name,'')        ILIKE %s
                       OR COALESCE(minecraft_username,'')  ILIKE %s
                       OR COALESCE(ip_address,'')          ILIKE %s
                    ORDER BY id DESC LIMIT %s""",
                (like, like, like, limit)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_scan(self, scan_id: int) -> Optional[dict]:
        with self._cur() as cur:
            cur.execute("SELECT * FROM scans WHERE id = %s", (scan_id,))
            scan = cur.fetchone()
            if not scan:
                return None
            scan = dict(scan)
            cur.execute(
                """SELECT id, issue_type, issue_name, issue_path, issue_category,
                          alert_level, confidence, detected_patterns,
                          obfuscation_detected, file_hash, ai_analysis,
                          ai_confidence, feedback_status
                     FROM scan_results WHERE scan_id = %s
                    ORDER BY CASE alert_level
                        WHEN 'CRITICAL' THEN 0
                        WHEN 'MUY_SOSPECHOSO' THEN 1
                        WHEN 'SOSPECHOSO' THEN 2
                        WHEN 'PAGINA_SOSPECHOSA' THEN 3
                        WHEN 'POCO_SOSPECHOSO' THEN 4
                        ELSE 9 END,
                        confidence DESC""",
                (scan_id,)
            )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                if isinstance(d.get('detected_patterns'), str):
                    try:
                        d['detected_patterns'] = json.loads(d['detected_patterns'])
                    except Exception:
                        pass
                results.append(d)
            scan['results'] = results
            return scan


class HttpBackend(Backend):
    name = 'http'

    def __init__(self, base_url: str, api_key: Optional[str] = None,
                 session_cookie: Optional[str] = None):
        try:
            import requests
        except ImportError:
            raise RuntimeError("requests no está instalado. pip install requests")
        self.requests = requests
        self.base_url = base_url.rstrip('/')
        self.headers: dict = {}
        if api_key:
            self.headers['X-API-Key'] = api_key
        self.cookies: dict = {}
        if session_cookie:
            self.cookies['session'] = session_cookie

    def _get(self, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        r = self.requests.get(url, headers=self.headers, cookies=self.cookies,
                              timeout=30, **kwargs)
        if r.status_code == 401 or r.status_code == 403:
            raise RuntimeError(
                f"Auth rechazada ({r.status_code}). Revisa API_KEY o cookie.")
        r.raise_for_status()
        return r.json()

    def list_scans(self, limit: int = 20) -> list[dict]:
        data = self._get(f"/api/scans?limit={limit}")
        return data.get('scans', data) if isinstance(data, dict) else data

    def find_scans(self, q: str, limit: int = 20) -> list[dict]:
        scans = self.list_scans(limit=200)
        ql = q.lower()
        return [s for s in scans if ql in (
            (s.get('machine_name') or '') +
            (s.get('minecraft_username') or '') +
            (s.get('ip_address') or '')).lower()][:limit]

    def get_scan(self, scan_id: int) -> Optional[dict]:
        try:
            return self._get(f"/api/scans/{scan_id}")
        except Exception:
            return None


def get_backend() -> Backend:
    creds = load_creds()
    if creds.get('DATABASE_URL'):
        try:
            return PgBackend(creds['DATABASE_URL'])
        except Exception as e:
            print(f"{C.YEL}⚠ PostgreSQL no disponible ({e}), probando HTTP…{C.R}",
                  file=sys.stderr)
    if creds.get('API_BASE_URL') and (creds.get('API_KEY') or creds.get('SESSION_COOKIE')):
        return HttpBackend(
            creds['API_BASE_URL'],
            api_key=creds.get('API_KEY'),
            session_cookie=creds.get('SESSION_COOKIE'),
        )
    print(f"{C.RED}✗ No hay credenciales configuradas.{C.R}", file=sys.stderr)
    print(f"  Ejecuta: {C.B}python tools/inspect_scan.py setup{C.R}", file=sys.stderr)
    sys.exit(2)


# ── Formato / pretty print ───────────────────────────────────────────────────
def fmt_dur(seconds: Any) -> str:
    try:
        s = int(float(seconds or 0))
    except (TypeError, ValueError):
        return '?'
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}m{s%60}s"
    return f"{s//3600}h{(s%3600)//60}m"


def fmt_dt(v: Any) -> str:
    if not v:
        return '—'
    s = str(v)
    if len(s) >= 16:
        return s[:16].replace('T', ' ')
    return s


def fmt_risk(score: Any) -> str:
    try:
        s = int(score or 0)
    except (TypeError, ValueError):
        return f"{C.GRY}—{C.R}"
    if s >= 80: col = C.RED + C.B
    elif s >= 50: col = C.YEL
    elif s >= 25: col = C.BLU
    else:        col = C.GRN
    return f"{col}{s:>3}{C.R}"


def fmt_verdict(v: Any) -> str:
    if not v:
        return f"{C.GRY}pendiente{C.R}"
    v = str(v).lower()
    if 'ban' in v or 'hack' in v: return f"{C.RED}{v}{C.R}"
    if 'limp' in v or 'clean' in v: return f"{C.GRN}{v}{C.R}"
    return f"{C.YEL}{v}{C.R}"


def cmd_list(limit: int = 20) -> None:
    backend = get_backend()
    scans = backend.list_scans(limit=limit)
    if not scans:
        print(f"{C.GRY}Sin scans.{C.R}")
        return
    print(f"\n{C.B}Últimos {len(scans)} scans · backend={backend.name}{C.R}\n")
    print(f"{C.DIM}{'ID':>5}  {'Máquina':<22} {'Usuario':<16} {'IP':<15} "
          f"{'Risk':>4}  {'Issues':>6}  {'Dur':<7} {'Estado':<10} {'Veredicto'}{C.R}")
    print(f"{C.DIM}{'─'*5}  {'─'*22} {'─'*16} {'─'*15} {'─'*4}  {'─'*6}  "
          f"{'─'*7} {'─'*10} {'─'*16}{C.R}")
    for s in scans:
        machine = (s.get('machine_name') or '')[:22]
        user    = (s.get('minecraft_username') or '')[:16]
        ip      = (s.get('ip_address') or '')[:15]
        risk    = fmt_risk(s.get('risk_score'))
        issues  = s.get('issues_found') or 0
        dur     = fmt_dur(s.get('scan_duration'))
        status  = (s.get('status') or '?')[:10]
        verdict = fmt_verdict(s.get('verdict'))
        print(f"{s.get('id',0):>5}  {machine:<22} {user:<16} {ip:<15} "
              f"{risk}  {issues:>6}  {dur:<7} {status:<10} {verdict}")
    print()


def cmd_show(scan_id: int) -> None:
    backend = get_backend()
    scan = backend.get_scan(scan_id)
    if not scan:
        print(f"{C.RED}Scan {scan_id} no encontrado.{C.R}")
        sys.exit(1)
    _render_scan(scan)


def cmd_latest() -> None:
    backend = get_backend()
    scans = backend.list_scans(limit=1)
    if not scans:
        print(f"{C.GRY}Sin scans.{C.R}")
        return
    last_id = scans[0]['id']
    full = backend.get_scan(int(last_id))
    if full:
        _render_scan(full)


def cmd_find(query: str, limit: int = 20) -> None:
    backend = get_backend()
    scans = backend.find_scans(query, limit=limit)
    if not scans:
        print(f"{C.GRY}Sin coincidencias para '{query}'.{C.R}")
        return
    print(f"\n{C.B}Resultados ({len(scans)}) para '{query}'{C.R}\n")
    for s in scans:
        print(f"  #{s['id']:>5} · {s.get('machine_name','?'):<22} · "
              f"risk={fmt_risk(s.get('risk_score'))} · "
              f"issues={s.get('issues_found',0)} · "
              f"{fmt_dt(s.get('completed_at'))}")
    print()


def _render_scan(scan: dict) -> None:
    """Imprime un scan completo formateado."""
    sid = scan.get('id', '?')
    print(f"\n{C.B}{C.CYN}╔{'═'*78}╗{C.R}")
    print(f"{C.B}{C.CYN}║  SCAN #{sid}{' '*(70-len(str(sid)))}║{C.R}")
    print(f"{C.B}{C.CYN}╚{'═'*78}╝{C.R}\n")

    # Metadata
    rows = [
        ('Máquina',     scan.get('machine_name')),
        ('Machine ID',  scan.get('machine_id')),
        ('Usuario MC',  scan.get('minecraft_username')),
        ('IP',          scan.get('ip_address')),
        ('País',        scan.get('country')),
        ('Estado',      scan.get('status')),
        ('Iniciado',    fmt_dt(scan.get('started_at'))),
        ('Completado',  fmt_dt(scan.get('completed_at'))),
        ('Archivos',    scan.get('total_files_scanned')),
        ('Duración',    fmt_dur(scan.get('scan_duration'))),
        ('Risk Score',  fmt_risk(scan.get('risk_score')) + f" / 100"),
        ('Issues',      scan.get('issues_found')),
        ('Veredicto',   fmt_verdict(scan.get('verdict'))),
        ('Razón',       scan.get('verdict_reason')),
        ('Por',         scan.get('verdict_by')),
    ]
    for k, v in rows:
        if v in (None, ''):
            continue
        print(f"  {C.DIM}{k:<13}{C.R} {v}")

    # Ensemble verdict
    ens_raw = scan.get('ensemble_data')
    ens = None
    if ens_raw:
        try:
            ens = ens_raw if isinstance(ens_raw, dict) else json.loads(ens_raw)
        except Exception:
            ens = None
    if ens:
        print(f"\n  {C.B}Ensemble{C.R}")
        for k in ('verdict', 'sanctionable', 'score', 'gate_capped', 'reasons'):
            if k in ens:
                v = ens[k]
                if isinstance(v, list):
                    v = ', '.join(map(str, v[:5]))
                print(f"    {C.DIM}{k:<14}{C.R} {v}")

    # MC info
    mc = scan.get('mc_info')
    if isinstance(mc, str):
        try: mc = json.loads(mc)
        except Exception: mc = None
    if mc:
        print(f"\n  {C.B}Minecraft{C.R}")
        print(f"    {C.DIM}Versión       {C.R} {mc.get('version', '—')}")
        print(f"    {C.DIM}Launcher      {C.R} {mc.get('launcher', '—')}")
        mods = mc.get('mods') or []
        if mods:
            print(f"    {C.DIM}Mods ({len(mods):>3})    {C.R} "
                  f"{', '.join(mods[:6])}{' …' if len(mods) > 6 else ''}")
        agents = mc.get('java_agents') or []
        if agents:
            print(f"    {C.DIM}Java agents   {C.R} {', '.join(map(str, agents))}")

    # Findings
    results = scan.get('results') or []
    if not results:
        print(f"\n  {C.GRN}Sin hallazgos.{C.R}\n")
        return

    print(f"\n  {C.B}Hallazgos ({len(results)}){C.R}")
    print(f"  {C.DIM}{'─'*78}{C.R}")
    by_cat: dict[str, list] = {}
    for r in results:
        by_cat.setdefault(r.get('issue_category') or 'OTRO', []).append(r)

    for cat in sorted(by_cat.keys()):
        items = by_cat[cat]
        print(f"\n  {C.B}{C.MAG}▎ {cat}{C.R} {C.DIM}({len(items)}){C.R}")
        for r in items:
            level = (r.get('alert_level') or '').upper()
            conf  = r.get('confidence')
            try:
                conf_f = float(conf or 0)
                if conf_f <= 1.0:
                    conf_pct = f"{int(conf_f * 100):>3}%"
                else:
                    conf_pct = f"{int(conf_f):>3}%"
            except (TypeError, ValueError):
                conf_pct = '  ?%'
            badge = alert_label(level)
            name  = (r.get('issue_name') or '').strip() or '(sin nombre)'
            path  = (r.get('issue_path') or '').strip()
            type_ = r.get('issue_type') or ''
            patterns = r.get('detected_patterns') or []
            ai_an = (r.get('ai_analysis') or '').strip()
            fb    = r.get('feedback_status')

            print(f"    {badge} {C.B}{name[:60]}{C.R} {C.DIM}({conf_pct}, {type_}){C.R}")
            if path:
                wrapped = textwrap.shorten(path, width=72, placeholder='…')
                print(f"      {C.GRY}↳ {wrapped}{C.R}")
            if patterns:
                ps = patterns if isinstance(patterns, list) else [patterns]
                ps_str = ', '.join(map(str, ps[:6]))
                print(f"      {C.GRY}patrones:{C.R} {ps_str}")
            if r.get('file_hash'):
                print(f"      {C.GRY}hash:{C.R} {r['file_hash'][:24]}…")
            if ai_an:
                print(f"      {C.CYN}IA:{C.R} {textwrap.shorten(ai_an, 200)}")
            if fb:
                fb_col = C.RED if 'hack' in str(fb).lower() else C.GRN if 'limp' in str(fb).lower() else C.YEL
                print(f"      {fb_col}staff feedback:{C.R} {fb}")
    print()


def cmd_stats() -> None:
    backend = get_backend()
    scans = backend.list_scans(limit=200)
    if not scans:
        print(f"{C.GRY}Sin scans.{C.R}")
        return
    n_total = len(scans)
    by_status: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    risks = []
    issues_total = 0
    for s in scans:
        by_status[s.get('status') or '?']    = by_status.get(s.get('status') or '?', 0) + 1
        by_verdict[s.get('verdict') or '—']  = by_verdict.get(s.get('verdict') or '—', 0) + 1
        try: risks.append(int(s.get('risk_score') or 0))
        except (TypeError, ValueError): pass
        try: issues_total += int(s.get('issues_found') or 0)
        except (TypeError, ValueError): pass
    avg_risk = sum(risks) / len(risks) if risks else 0
    crit = sum(1 for r in risks if r >= 80)
    print(f"\n{C.B}Stats últimos {n_total} scans{C.R}\n")
    print(f"  {C.DIM}Risk score promedio:{C.R} {fmt_risk(int(avg_risk))}")
    print(f"  {C.DIM}Críticos (≥80):     {C.R} {C.RED}{crit}{C.R}")
    print(f"  {C.DIM}Issues totales:     {C.R} {issues_total}")
    print(f"  {C.DIM}Por status:         {C.R}")
    for k, v in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"    {k:<14} {v}")
    print(f"  {C.DIM}Por veredicto:      {C.R}")
    for k, v in sorted(by_verdict.items(), key=lambda x: -x[1])[:6]:
        print(f"    {k:<14} {v}")
    print()


def cmd_fp_audit(limit: int = 50) -> None:
    """Audita los últimos N scans buscando patrones que sigan pareciendo FPs."""
    backend = get_backend()
    scans = backend.list_scans(limit=limit)
    suspect_fps: list[tuple] = []
    for s in scans:
        full = backend.get_scan(int(s['id']))
        if not full:
            continue
        for r in full.get('results', []):
            name = (r.get('issue_name') or '').lower()
            path = (r.get('issue_path') or '').lower()
            combined = name + '|' + path
            for marker in ('windows\\system32', 'webview2runtime', 'svchost',
                           'site-packages', 'lunar client', 'feathermc',
                           'badlion', 'easyanticheat', 'steam\\steamapps',
                           'github.com', 'modrinth.com'):
                if marker in combined:
                    suspect_fps.append((s['id'], r.get('issue_name'),
                                        r.get('issue_path'), marker))
                    break
    if not suspect_fps:
        print(f"{C.GRN}✓ Ninguno de los últimos {limit} scans tiene FPs evidentes.{C.R}")
        return
    print(f"\n{C.YEL}⚠ Posibles FPs en últimos {limit} scans ({len(suspect_fps)} hallazgos){C.R}\n")
    for sid, name, path, why in suspect_fps[:60]:
        print(f"  scan #{sid:>4} · {C.RED}{(name or '')[:35]:<35}{C.R} · {C.GRY}{why}{C.R}")
        if path:
            print(f"           {C.GRY}↳ {textwrap.shorten(path, 90)}{C.R}")
    if len(suspect_fps) > 60:
        print(f"\n  {C.DIM}…y {len(suspect_fps) - 60} más.{C.R}")
    print()


# ── CLI router ───────────────────────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    cmd = args[0]
    rest = args[1:]
    try:
        if cmd == 'setup':
            cmd_setup()
        elif cmd == 'list':
            n = int(rest[0]) if rest else 20
            cmd_list(limit=n)
        elif cmd == 'latest':
            cmd_latest()
        elif cmd == 'show':
            if not rest:
                print(f"{C.RED}Falta el id del scan{C.R}")
                return 1
            cmd_show(int(rest[0]))
        elif cmd == 'stats':
            cmd_stats()
        elif cmd == 'find':
            if not rest:
                print(f"{C.RED}Falta el texto a buscar{C.R}")
                return 1
            cmd_find(' '.join(rest))
        elif cmd == 'fp_audit':
            n = int(rest[0]) if rest else 50
            cmd_fp_audit(limit=n)
        elif cmd == 'creds':
            print(json.dumps(load_creds(), indent=2))
        else:
            print(f"{C.RED}Comando desconocido: {cmd}{C.R}")
            print(__doc__)
            return 1
    except KeyboardInterrupt:
        print(f"\n{C.YEL}Cancelado.{C.R}")
        return 130
    except Exception as e:
        print(f"\n{C.RED}Error: {e}{C.R}")
        import traceback as _tb
        _tb.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
