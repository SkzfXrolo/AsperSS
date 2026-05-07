"""
Diagnostico: replicar exactamente la query del endpoint GET /api/scans/<id>
para ver que retornaria al frontend.
"""
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"

def diag(scan_id):
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, token_id, scan_token, started_at, completed_at, status,
               total_files_scanned, issues_found, scan_duration,
               machine_id, machine_name, ip_address, country, minecraft_username
        FROM scans
        WHERE id = %s
    """, (scan_id,))
    row = cur.fetchone()
    if not row:
        print(f"!! scan {scan_id} no existe")
        return

    scan = dict(row)
    print(f"=== scan {scan_id} BASE ===")
    print(f"  status={scan['status']}")
    print(f"  total_files_scanned={scan['total_files_scanned']}")
    print(f"  issues_found={scan['issues_found']}")

    # Columnas opcionales
    try:
        cur.execute("""
            SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                   screenshot, mc_info, risk_score, ensemble_data
            FROM scans WHERE id = %s
        """, (scan_id,))
        vrow = cur.fetchone()
        if vrow:
            scan['risk_score'] = vrow['risk_score'] or 0
            scan['total_dirs_scanned'] = vrow['total_dirs_scanned'] or 0
    except Exception as e:
        print(f"  err opt cols: {e}")

    # Resultados
    cur.execute("""
        SELECT id, issue_type, issue_name, issue_path, issue_category,
               alert_level, confidence, detected_patterns, obfuscation_detected,
               file_hash, ai_analysis, ai_confidence, feedback_status, extra
        FROM scan_results
        WHERE scan_id = %s
    """, (scan_id,))
    rows = cur.fetchall()
    print(f"  scan_results encontrados en BD: {len(rows)}")

    results = []
    for r in rows:
        raw_patterns = r['detected_patterns']
        results.append({
            'id': r['id'],
            'issue_type': r['issue_type'],
            'issue_name': r['issue_name'],
            'issue_path': r['issue_path'],
            'issue_category': r['issue_category'],
            'alert_level': r['alert_level'],
            'confidence': float(r['confidence'] or 0),
            'detected_patterns': json.loads(raw_patterns) if raw_patterns else [],
            'obfuscation_detected': bool(r['obfuscation_detected']),
            'file_hash': r['file_hash'],
            'ai_analysis': r['ai_analysis'],
            'ai_confidence': r['ai_confidence'],
            'feedback_status': r['feedback_status'],
            'extra': r['extra'],
        })

    # Aplicar filtro server-side (replica de _scrub_results_for_display)
    print(f"  resultados procesados (sin filtro): {len(results)}")
    print()
    print("  --- payload que iria al panel: ---")
    print(f"    results count: {len(results)}")
    for r in results[:6]:
        print(f"      [{r['alert_level']:18}] conf={r['confidence']:.2f} | "
              f"{r['issue_type']:30} | {(r['issue_name'] or '')[:50]}")

    conn.close()
    return scan, results


if __name__ == '__main__':
    for sid in (96, 95, 94):
        diag(sid)
        print()
