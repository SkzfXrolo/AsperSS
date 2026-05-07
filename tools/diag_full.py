"""Replicar completamente la logica de get_scan() de app.py para verificar el JSON output."""
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # 1. Tipos de columnas en scan_results
    print("=" * 80)
    print("  Columnas de scan_results")
    print("=" * 80)
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='scan_results'
        ORDER BY ordinal_position
    """)
    for r in cur.fetchall():
        print(f"  {r['column_name']:30} -> {r['data_type']}")

    # 2. Verificar tipos reales de los valores devueltos
    print()
    print("=" * 80)
    print("  Tipos REALES de valores en scan 96")
    print("=" * 80)
    cur.execute("""
        SELECT id, issue_type, issue_name, alert_level, confidence,
               detected_patterns, obfuscation_detected, file_hash,
               feedback_status, extra
        FROM scan_results
        WHERE scan_id = 96
        LIMIT 3
    """)
    for r in cur.fetchall():
        print(f"\n  result id={r['id']}:")
        for k, v in r.items():
            print(f"    {k:25} = {type(v).__name__:15} | {repr(v)[:80]}")

    # 3. Existe la columna 'extra'?
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='scan_results' AND column_name='extra'
    """)
    has_extra = cur.fetchone() is not None
    print(f"\n  extra column exists: {has_extra}")

    # 4. Verificar columnas de scans
    print()
    print("=" * 80)
    print("  Columnas de scans (relevantes)")
    print("=" * 80)
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='scans' AND column_name IN
              ('total_dirs_scanned', 'verdict', 'screenshot', 'mc_info',
               'risk_score', 'ensemble_data', 'plugin_key_id',
               'minecraft_staff', 'minecraft_target', 'source')
        ORDER BY ordinal_position
    """)
    for r in cur.fetchall():
        print(f"  {r['column_name']:30} -> {r['data_type']}")

    # 5. Replicar get_scan
    print()
    print("=" * 80)
    print("  REPLICA del endpoint get_scan(96)")
    print("=" * 80)

    cur.execute("""
        SELECT id, token_id, scan_token, started_at, completed_at, status,
               total_files_scanned, issues_found, scan_duration,
               machine_id, machine_name, ip_address, country, minecraft_username
        FROM scans WHERE id = 96
    """)
    row = cur.fetchone()
    scan = dict(row)
    print(f"  scan base ok: keys={list(scan.keys())[:5]}...")

    # extra cols
    try:
        cur.execute("""
            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                   screenshot, mc_info, risk_score, ensemble_data
            FROM scans WHERE id = 96
        """)
        vrow = cur.fetchone()
        print(f"  vrow extra cols ok")
    except Exception as e:
        print(f"  ERROR extra cols: {e}")
        return

    # results con extra
    try:
        cur.execute("""
            SELECT id, issue_type, issue_name, issue_path, issue_category,
                   alert_level, confidence, detected_patterns, obfuscation_detected,
                   file_hash, ai_analysis, ai_confidence, feedback_status, extra
            FROM scan_results WHERE scan_id = 96
        """)
        rows = cur.fetchall()
        print(f"  results raw rows: {len(rows)}")
    except Exception as e:
        print(f"  ERROR select results with extra: {e}")
        return

    results = []
    for r in rows:
        raw_patterns = r['detected_patterns']
        raw_extra = r['extra']
        # Replica
        extra_obj = {}
        if raw_extra:
            try:
                extra_obj = json.loads(raw_extra) if isinstance(raw_extra, str) else (raw_extra or {})
                if not isinstance(extra_obj, dict):
                    extra_obj = {}
            except (TypeError, ValueError):
                extra_obj = {}

        try:
            patterns_parsed = json.loads(raw_patterns) if raw_patterns else []
        except Exception as e:
            print(f"    !!! json.loads(detected_patterns) FALLO: {e} | type={type(raw_patterns).__name__} | raw={repr(raw_patterns)[:50]}")
            patterns_parsed = []

        results.append({
            'id': r['id'],
            'issue_type': r['issue_type'],
            'issue_name': r['issue_name'],
            'issue_path': r['issue_path'],
            'issue_category': r['issue_category'],
            'alert_level': r['alert_level'],
            'confidence': r['confidence'],
            'detected_patterns': patterns_parsed,
            'obfuscation_detected': bool(r['obfuscation_detected']),
            'file_hash': r['file_hash'],
            'ai_analysis': r['ai_analysis'],
            'ai_confidence': r['ai_confidence'],
            'feedback_status': r['feedback_status'],
            'extra': extra_obj,
        })

    print(f"  results procesados: {len(results)}")
    print()
    print("  PAYLOAD RESUMIDO:")
    for r in results:
        print(f"    {r['alert_level']:18} | conf={r['confidence']} | {r['issue_type']:30} | {(r['issue_name'] or '')[:50]}")

    # JSON serialization test
    payload = dict(scan)
    payload['results'] = results
    try:
        s = json.dumps(payload, default=str)
        print(f"\n  json.dumps OK (length={len(s)})")
    except Exception as e:
        print(f"\n  ERROR json.dumps: {e}")

    conn.close()

if __name__ == '__main__':
    main()
