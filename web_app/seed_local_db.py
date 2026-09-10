"""Crea una SQLite de PRUEBA (scanner_db.local.sqlite) con el esquema actual y
datos dummy, para desarrollar el panel v2 sin tocar prod ni Render.

Uso:
    python seed_local_db.py                 # crea/reemplaza scanner_db.local.sqlite
    ARGUS_DB_PATH=scanner_db.local.sqlite python app.py   # levanta el panel local

Login de prueba:  owner / owner123
"""
import os
import json
import random
import sqlite3
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "scanner_db.local.sqlite")

SCHEMA = """
CREATE TABLE companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  contact_email TEXT, contact_phone TEXT,
  subscription_type TEXT DEFAULT 'enterprise',
  subscription_status TEXT DEFAULT 'active',
  subscription_start_date TEXT DEFAULT CURRENT_TIMESTAMP,
  subscription_end_date TEXT,
  subscription_price REAL DEFAULT 13.0,
  max_users INTEGER DEFAULT 8, max_admins INTEGER DEFAULT 3,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, created_by INTEGER,
  is_active INTEGER DEFAULT 1, notes TEXT
);
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL, email TEXT UNIQUE,
  password_hash TEXT NOT NULL, roles TEXT DEFAULT '["user"]',
  company_id INTEGER, is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_login TEXT,
  created_by TEXT, deleted_at TEXT, avatar_url TEXT DEFAULT ''
);
CREATE TABLE scan_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT UNIQUE NOT NULL, short_code TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT,
  used_count INTEGER DEFAULT 0, max_uses INTEGER DEFAULT -1,
  is_active INTEGER DEFAULT 1, created_by TEXT, description TEXT,
  allowed_mods TEXT, company_id INTEGER
);
CREATE TABLE scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_id INTEGER, scan_token TEXT,
  started_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT,
  status TEXT DEFAULT 'running',
  total_files_scanned INTEGER DEFAULT 0, total_dirs_scanned INTEGER DEFAULT 0,
  issues_found INTEGER DEFAULT 0, issues_critical INTEGER DEFAULT 0,
  scan_duration REAL, scan_duration_ms INTEGER,
  machine_id TEXT, machine_name TEXT, ip_address TEXT, country TEXT,
  minecraft_username TEXT, minecraft_target TEXT,
  company_id INTEGER, verdict TEXT, verdict_reason TEXT,
  verdict_by TEXT, verdict_at TEXT,
  risk_score INTEGER, ensemble_data TEXT,
  os TEXT, scanner_version TEXT,
  screenshot TEXT, mc_info TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, deleted_at TEXT
);
CREATE TABLE scan_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id INTEGER, issue_type TEXT, issue_name TEXT, issue_path TEXT,
  issue_category TEXT, alert_level TEXT, confidence REAL,
  detected_patterns TEXT, obfuscation_detected INTEGER DEFAULT 0,
  file_hash TEXT, ai_analysis TEXT, ai_confidence REAL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  feedback_status TEXT, extra TEXT
);
CREATE TABLE ban_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  machine_id TEXT, minecraft_username TEXT, ip_address TEXT,
  ban_reason TEXT, hack_type TEXT,
  banned_at TEXT DEFAULT CURRENT_TIMESTAMP, scan_id INTEGER
);
CREATE TABLE staff_feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  result_id INTEGER NOT NULL, scan_id INTEGER,
  staff_verification TEXT NOT NULL, staff_notes TEXT,
  verified_by TEXT, verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
  file_hash TEXT, issue_name TEXT, issue_path TEXT,
  extracted_patterns TEXT, extracted_features TEXT
);
CREATE TABLE scan_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id INTEGER NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE verdict_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scan_id INTEGER NOT NULL, verdict TEXT NOT NULL, reason TEXT,
  changed_by TEXT NOT NULL, changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE registration_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token TEXT UNIQUE NOT NULL, company_id INTEGER, created_by INTEGER NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, expires_at TEXT, used_at TEXT,
  is_used INTEGER DEFAULT 0, used_by INTEGER, max_uses INTEGER DEFAULT 1,
  description TEXT, is_admin_token INTEGER DEFAULT 0
);
CREATE TABLE app_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT UNIQUE NOT NULL,
  release_date TEXT DEFAULT CURRENT_TIMESTAMP, download_url TEXT, changelog TEXT,
  is_active INTEGER DEFAULT 1, file_size INTEGER, file_hash TEXT, min_required_version TEXT
);
CREATE TABLE configurations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL,
  value TEXT, description TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE statistics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT DEFAULT CURRENT_DATE,
  total_scans INTEGER DEFAULT 0, total_issues_found INTEGER DEFAULT 0,
  unique_machines INTEGER DEFAULT 0, avg_scan_duration REAL
);
CREATE TABLE download_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL,
  filename TEXT NOT NULL, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT, max_downloads INTEGER DEFAULT 1, download_count INTEGER DEFAULT 0,
  is_active INTEGER DEFAULT 1, description TEXT
);
CREATE TABLE hack_hashes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sha256 TEXT NOT NULL UNIQUE,
  hack_name TEXT, added_by TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP,
  confirmed_count INTEGER DEFAULT 1
);
CREATE TABLE mod_whitelist (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sha256 TEXT NOT NULL UNIQUE,
  mod_name TEXT NOT NULL, added_by TEXT, added_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE type_confidence_thresholds (
  id INTEGER PRIMARY KEY AUTOINCREMENT, issue_type TEXT NOT NULL UNIQUE,
  min_confidence INTEGER NOT NULL DEFAULT 30, auto_bumps INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE plugin_violations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, plugin_key_id INTEGER, company_id INTEGER,
  player_uuid TEXT, player_name TEXT, check_name TEXT, level TEXT, details TEXT,
  server_label TEXT, related_token_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE staff_trust (
  user_id INTEGER PRIMARY KEY, verdicts_total INTEGER DEFAULT 0, agreements INTEGER DEFAULT 0,
  disagreements INTEGER DEFAULT 0, overturns_to_clean INTEGER DEFAULT 0, overturns_to_hack INTEGER DEFAULT 0,
  confirmed_correct INTEGER DEFAULT 0, confirmed_wrong INTEGER DEFAULT 0, last_verdict_at TEXT,
  trust_score REAL DEFAULT 50.0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE company_fp_cooldown (
  company_id INTEGER PRIMARY KEY, fp_count_24h INTEGER DEFAULT 0, overturn_count_24h INTEGER DEFAULT 0,
  threshold_bump INTEGER DEFAULT 0, cooldown_until TEXT, last_event_at TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE ai_player_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL, player_uuid TEXT NOT NULL,
  player_name TEXT, score REAL DEFAULT 0, confidence REAL DEFAULT 0,
  last_action TEXT DEFAULT 'none', last_reasoning TEXT, last_evidence_json TEXT,
  evaluations_count INTEGER DEFAULT 0, last_evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_scans_started ON scans(started_at);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_results_scan ON scan_results(scan_id);
CREATE INDEX idx_results_alert ON scan_results(alert_level);
"""

def _pw(p):
    """Réplica exacta de auth.hash_password (PBKDF2-SHA256, 260k iteraciones)."""
    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", p.encode("utf-8"), salt.encode("utf-8"), 260000)
    return f"pbkdf2:sha256:260000:{salt}:{dk.hex()}"

MACHINES = ["DESKTOP-4F2A9C", "LAPTOP-KAREN", "PC-GAMER-01", "MSI-BRAVO-15",
            "ROG-STRIX-J", "HP-PAVILION-7", "DESKTOP-QX12", "ACER-NITRO-5",
            "LEGION-5-PRO", "DELL-G15-5530", "DESKTOP-M8K2", "TUF-A15-77"]
USERS_MC = ["xShadowPvP", "karen_mc", "notacheater", "pro_builder", "Dream_fan99",
            "sweaty_kid", "legit_gamer", "AimGod_", "casual_steve", "TryhardTom",
            "blockmaster", "sniper_wolf", "iFrostByte", "creeper_hugs"]
COUNTRIES = ["Argentina", "España", "México", "Chile", "Colombia", "Perú", "Uruguay"]
HACKS = [("KillAura", "CRITICAL"), ("Reach", "CRITICAL"), ("AutoClicker", "SUSPICIOUS"),
         ("XRay ResourcePack", "CRITICAL"), ("Scaffold", "SUSPICIOUS"),
         ("Vape V4 (prefetch)", "CRITICAL"), ("FullBright", "SUSPICIOUS"),
         ("Baritone", "SUSPICIOUS"), ("Mod desconocido en /mods", "LOW")]
CLEAN_ITEMS = [("OptiFine detectado", "LOW"), ("Lunar Client", "LOW"),
               ("Badlion Client", "LOW"), ("Múltiples versiones MC", "LOW")]


def main():
    for ext in ("", "-wal", "-shm", "-journal"):
        p = DB + ext
        if os.path.exists(p):
            os.remove(p)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)

    now = dt.datetime.now()
    c.execute("INSERT INTO companies (id,name,notes) VALUES (1,'arefy','Empresa demo local')")
    c.execute("INSERT INTO companies (id,name,notes) VALUES (2,'nova-network','Segundo cliente demo')")

    users = [
        ("owner", "owner123", '["superadmin","owner","admin","moderator"]', 1),
        ("admin_arefy", "admin123", '["admin"]', 1),
        ("helper_juan", "helper123", '["helper"]', 1),
        ("mod_nova", "mod123", '["moderator"]', 2),
    ]
    for u, p, roles, cid in users:
        c.execute("INSERT INTO users (username,email,password_hash,roles,company_id,is_active) "
                  "VALUES (?,?,?,?,?,1)", (u, f"{u}@demo.local", _pw(p), roles, cid))

    for i in range(6):
        c.execute("INSERT INTO scan_tokens (token,short_code,created_by,description,company_id,used_count) "
                  "VALUES (?,?,?,?,?,?)",
                  (f"tok_{'%02d'%i}_{random.randint(10000,99999)}", f"AR{1000+i}",
                   "owner", f"Token servidor {i+1}", 1 if i < 4 else 2, random.randint(0, 40)))

    verdicts = ["hack", "clean", "suspicious", None]
    for i in range(48):
        started = now - dt.timedelta(hours=random.randint(0, 480), minutes=random.randint(0, 59))
        dur = round(random.uniform(45, 400), 1)
        v = random.choices(verdicts, weights=[3, 5, 2, 3])[0]
        risk = {"hack": random.randint(72, 98), "suspicious": random.randint(32, 68),
                "clean": random.randint(0, 18), None: random.randint(0, 60)}[v]
        status = "completed" if i > 2 else "running"
        n_issues = random.randint(0, 6) if v != "clean" else random.randint(0, 1)
        cur = c.execute(
            "INSERT INTO scans (token_id,scan_token,started_at,completed_at,status,"
            "total_files_scanned,total_dirs_scanned,issues_found,issues_critical,"
            "scan_duration,machine_id,machine_name,ip_address,country,minecraft_username,"
            "company_id,verdict,risk_score,os,scanner_version) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (random.randint(1, 6), f"tok_{random.randint(0,5):02d}",
             started.isoformat(sep=' ', timespec='seconds'),
             (started + dt.timedelta(seconds=dur)).isoformat(sep=' ', timespec='seconds') if status == "completed" else None,
             status, random.randint(8000, 60000), random.randint(400, 3000),
             n_issues, sum(1 for _ in range(n_issues) if random.random() < .4),
             dur, f"MID-{random.randint(1000,9999)}", random.choice(MACHINES),
             f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
             random.choice(COUNTRIES), random.choice(USERS_MC),
             1 if random.random() < .8 else 2, v, risk,
             random.choice(["Windows 10", "Windows 11"]), "1.8.0"))
        sid = cur.lastrowid
        pool = HACKS if v in ("hack", "suspicious") else CLEAN_ITEMS
        for _ in range(n_issues):
            name, lvl = random.choice(pool)
            c.execute(
                "INSERT INTO scan_results (scan_id,issue_type,issue_name,issue_path,"
                "issue_category,alert_level,confidence,detected_patterns) VALUES (?,?,?,?,?,?,?,?)",
                (sid, "file", name, f"C:\\Users\\x\\AppData\\...\\{name.split()[0].lower()}",
                 "HACKS", lvl, round(random.uniform(.4, .98), 2),
                 json.dumps(["boundary_match", "prefetch"])))
        if v == "hack" and random.random() < .6:
            c.execute("INSERT INTO ban_history (machine_id,minecraft_username,ban_reason,hack_type,scan_id) "
                      "VALUES (?,?,?,?,?)", (f"MID-{random.randint(1000,9999)}",
                      random.choice(USERS_MC), "Cheat confirmado en SS", "KillAura", sid))
        if random.random() < .3:
            c.execute("INSERT INTO scan_notes (scan_id,author,body) VALUES (?,?,?)",
                      (sid, random.choice(["owner", "helper_juan"]),
                       "Revisado en directo, comportamiento sospechoso en PvP."))

    c.execute("INSERT INTO app_versions (version,download_url,changelog,is_active) "
              "VALUES ('1.8.0','/downloads/ArgusScanner.exe','Pack forense + bundle offline',1)")

    # Violaciones del plugin anticheat (para la sección Anticheat del panel)
    _CHECKS = ["killaura_no_swing", "reach", "speed", "fly", "scaffold", "aimbot",
               "autoclicker", "nofall", "fasteat", "jesus"]
    _LVLS = ["LOW", "MID", "HIGH", "CRITICAL"]
    for _ in range(140):
        cv = now - dt.timedelta(hours=random.randint(0, 72), minutes=random.randint(0, 59))
        c.execute("INSERT INTO plugin_violations (company_id,player_name,player_uuid,check_name,level,details,server_label,created_at) "
                  "VALUES (?,?,?,?,?,?,?,?)",
                  (random.choice([1, 1, 1, 2]), random.choice(USERS_MC),
                   f"{random.randint(10000000,99999999):08x}-0000-0000-0000-000000000000",
                   random.choice(_CHECKS), random.choices(_LVLS, weights=[5, 3, 2, 1])[0],
                   "bps=8.1 cap=7.8 streak=5", random.choice(["survival-1", "practice", "hcf"]),
                   cv.isoformat(sep=' ', timespec='seconds')))
    for u in USERS_MC[:8]:
        sc = round(random.uniform(0, 95), 1)
        c.execute("INSERT INTO ai_player_scores (company_id,player_uuid,player_name,score,confidence,last_action,evaluations_count) "
                  "VALUES (1,?,?,?,?,?,?)",
                  (f"{random.randint(1,9999999):07d}", u, sc, round(random.uniform(.4, .95), 2),
                   "ban" if sc > 80 else "ss_issued" if sc > 55 else "watch" if sc > 30 else "none",
                   random.randint(1, 40)))
    for uid in (1, 3, 4):
        vt = random.randint(20, 200)
        ag = int(vt * random.uniform(.7, .97))
        c.execute("INSERT INTO staff_trust (user_id,verdicts_total,agreements,disagreements,confirmed_correct,confirmed_wrong,trust_score) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (uid, vt, ag, vt - ag, int(ag * .9), int((vt - ag) * .4),
                   round(50 + random.uniform(-8, 42), 1)))
    c.commit()
    _patch_missing_columns(c)
    c.commit()
    n = lambda t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"OK  {DB}")
    print(f"    companies={n('companies')} users={n('users')} tokens={n('scan_tokens')} "
          f"scans={n('scans')} results={n('scan_results')} bans={n('ban_history')}")
    print("    login demo:  owner / owner123")
    c.close()


_ALIASES = {'s': 'scans', 'st': 'scan_tokens', 'sr': 'scan_results', 'u': 'users',
            'sf': 'staff_feedback', 'c': 'companies', 'r': 'scan_results'}


def _patch_missing_columns(conn):
    """Escanea app.py/auth.py por refs `tabla.columna` y agrega como TEXT las que
    falten. Cubre el drift del esquema sin tener que adivinar columna por columna.
    Solo para la BD de prueba local."""
    import re
    src = ""
    for f in ("app.py", "auth.py"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            src += open(p, encoding="utf-8", errors="ignore").read()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    have = {t: {r[1] for r in conn.execute(f"PRAGMA table_info({t})")} for t in tables}
    KEYWORDS = {'execute', 'fetchone', 'fetchall', 'get', 'keys', 'items', 'append',
                'strip', 'lower', 'upper', 'format', 'join', 'split', 'replace'}
    added = 0
    for alias, col in re.findall(r'\b([a-z_]{1,20})\.([a-z_]{2,40})\b', src):
        tbl = _ALIASES.get(alias, alias)
        if tbl not in have or col in KEYWORDS:
            continue
        if col not in have[tbl]:
            try:
                conn.execute(f'ALTER TABLE {tbl} ADD COLUMN {col} TEXT')
                have[tbl].add(col)
                added += 1
            except Exception:
                pass
    if added:
        print(f"    +{added} columnas faltantes parcheadas (dev)")


if __name__ == "__main__":
    main()
