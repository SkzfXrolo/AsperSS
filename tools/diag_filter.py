"""
Diagnostico: probar el filtro _is_server_false_positive contra los resultados reales
del scan 96 (el ultimo) para ver si el panel los esta descartando.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web_app'))

import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"

# Importamos directo del app.py los filtros
os.environ.setdefault('SECRET_KEY', 'diag')
os.environ.setdefault('DATABASE_URL', DB_URL)

# La importacion de app.py es pesada; en su lugar, copiamos el filtro relevante
# Lo cargamos desde el modulo
from web_app.app import _is_server_false_positive, _scrub_results_for_display

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    c = conn.cursor()

    for scan_id in (96, 95, 94, 93, 92):
        print("=" * 100)
        print(f"  SCAN {scan_id}")
        print("=" * 100)
        c.execute("""
            SELECT id, issue_type, issue_name, issue_path, issue_category,
                   alert_level, confidence, detected_patterns, file_hash,
                   ai_analysis, ai_confidence
            FROM scan_results
            WHERE scan_id = %s
            ORDER BY id ASC
        """, (scan_id,))
        rows = c.fetchall()
        print(f"  Total filas en BD: {len(rows)}")

        results = []
        for r in rows:
            results.append({
                'id': r['id'],
                'issue_type': r['issue_type'],
                'issue_name': r['issue_name'],
                'issue_path': r['issue_path'],
                'issue_category': r['issue_category'],
                'alert_level': r['alert_level'],
                'confidence': r['confidence'],
                'detected_patterns': r['detected_patterns'],
                'file_hash': r['file_hash'],
                'ai_analysis': r['ai_analysis'],
                'ai_confidence': r['ai_confidence'],
            })

        kept = []
        for r in results:
            fp = _is_server_false_positive(r)
            mark = 'FILTRADO' if fp else 'PASA'
            print(f"    [{mark:8}] {r['alert_level']:18} | conf={r['confidence']:.2f} | "
                  f"{(r['issue_type'] or '')[:25]:25} | {(r['issue_name'] or '')[:55]}")
            if not fp:
                kept.append(r)

        scrubbed = _scrub_results_for_display(results)
        print(f"  -> Filtro individual: {len(kept)}/{len(results)} pasan")
        print(f"  -> _scrub_results_for_display devuelve: {len(scrubbed)}/{len(results)}")
        print()

    conn.close()

if __name__ == '__main__':
    main()
