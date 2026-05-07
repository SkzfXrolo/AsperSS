"""
Diagnostico: ver ultimos scans en la BD de produccion y sus resultados.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"

def main():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    c = conn.cursor()

    print("=" * 90)
    print("  ULTIMOS 15 SCANS")
    print("=" * 90)
    c.execute("""
        SELECT id, status, total_files_scanned, issues_found,
               started_at, completed_at, machine_name, minecraft_username, risk_score
        FROM scans
        ORDER BY id DESC
        LIMIT 15
    """)
    for r in c.fetchall():
        print(f"  scan {r['id']:4} | {str(r['started_at'])[:19]} | status={r['status']:10} "
              f"| files={r['total_files_scanned']:6} issues={r['issues_found']:3} "
              f"risk={r['risk_score']:3} | {r['machine_name']} / {r['minecraft_username']}")

    print()
    print("=" * 90)
    print("  RESULTADOS POR SCAN (ultimos 15)")
    print("=" * 90)
    c.execute("""
        SELECT scan_id, COUNT(*) as cnt, MIN(id) as min_id, MAX(id) as max_id
        FROM scan_results
        WHERE scan_id IN (SELECT id FROM scans ORDER BY id DESC LIMIT 15)
        GROUP BY scan_id
        ORDER BY scan_id DESC
    """)
    for r in c.fetchall():
        print(f"  scan_id={r['scan_id']:4} | rows={r['cnt']:4} | result_ids={r['min_id']}..{r['max_id']}")

    print()
    print("=" * 90)
    print("  TOTAL FILAS scan_results:")
    print("=" * 90)
    c.execute("SELECT COUNT(*) as cnt FROM scan_results")
    print(f"  TOTAL = {c.fetchone()['cnt']}")

    print()
    print("=" * 90)
    print("  ULTIMOS 5 RESULTADOS INSERTADOS (cualquier scan)")
    print("=" * 90)
    c.execute("""
        SELECT id, scan_id, issue_type, issue_name, alert_level, confidence
        FROM scan_results
        ORDER BY id DESC
        LIMIT 5
    """)
    for r in c.fetchall():
        print(f"  result {r['id']:5} | scan={r['scan_id']:4} | {r['alert_level']:15} "
              f"| conf={r['confidence']:.2f} | {r['issue_type']} :: {(r['issue_name'] or '')[:60]}")

    conn.close()

if __name__ == '__main__':
    main()
