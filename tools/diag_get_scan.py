"""
Replica EXACTAMENTE la logica de get_scan() incluyendo el jsonify final.
Encuentra donde rompe en produccion (estamos viendo 500's en /api/scans/96).
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web_app'))

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"
os.environ['DATABASE_URL'] = DB_URL
os.environ['SECRET_KEY'] = 'diag'

# Importar Flask app y funciones reales
from flask import jsonify
from web_app.app import (
    app, get_api_db_cursor, _PH, _row_get,
    _scrub_results_for_display, _stats_cache, _stats_cache_time,
)

def diag_get_scan(scan_id):
    print(f"\n{'='*80}\n  DIAG GET /api/scans/{scan_id}\n{'='*80}")
    try:
        with get_api_db_cursor() as cursor:
            cursor.execute(f'''
                SELECT id, token_id, scan_token, started_at, completed_at, status,
                       total_files_scanned, issues_found, scan_duration,
                       machine_id, machine_name, ip_address, country, minecraft_username
                FROM scans WHERE id = {_PH}
            ''', (scan_id,))
            row = cursor.fetchone()
            if not row:
                print("  -> 404 not found")
                return

            scan = {
                'id': _row_get(row, 0, 'id'),
                'token_id': _row_get(row, 1, 'token_id'),
                'scan_token': _row_get(row, 2, 'scan_token'),
                'started_at': str(_row_get(row, 3, 'started_at') or ''),
                'completed_at': str(_row_get(row, 4, 'completed_at') or ''),
                'status': _row_get(row, 5, 'status'),
                'total_files_scanned': _row_get(row, 6, 'total_files_scanned') or 0,
                'total_dirs_scanned': 0,
                'issues_found': _row_get(row, 7, 'issues_found') or 0,
                'scan_duration': _row_get(row, 8, 'scan_duration') or 0,
                'machine_id': _row_get(row, 9, 'machine_id'),
                'machine_name': _row_get(row, 10, 'machine_name'),
                'ip_address': _row_get(row, 11, 'ip_address'),
                'country': _row_get(row, 12, 'country'),
                'minecraft_username': _row_get(row, 13, 'minecraft_username'),
                'verdict': None, 'verdict_reason': None,
                'verdict_by': None, 'verdict_at': '',
            }
            print("  step1 select_scans_base OK")

            scan['screenshot'] = None
            scan['mc_info'] = None
            scan['risk_score'] = 0
            scan['ensemble_data'] = None
            try:
                cursor.execute('SAVEPOINT opt_cols')
                cursor.execute(f'''
                    SELECT total_dirs_scanned, verdict, verdict_reason, verdict_by, verdict_at,
                           screenshot, mc_info, risk_score, ensemble_data
                    FROM scans WHERE id = {_PH}
                ''', (scan_id,))
                vrow = cursor.fetchone()
                if vrow:
                    scan['total_dirs_scanned'] = _row_get(vrow, 0, 'total_dirs_scanned') or 0
                    scan['verdict']        = _row_get(vrow, 1, 'verdict')
                    scan['verdict_reason'] = _row_get(vrow, 2, 'verdict_reason')
                    scan['verdict_by']     = _row_get(vrow, 3, 'verdict_by')
                    scan['verdict_at']     = str(_row_get(vrow, 4, 'verdict_at') or '')
                    scan['screenshot']     = _row_get(vrow, 5, 'screenshot')
                    raw_mc_info = _row_get(vrow, 6, 'mc_info')
                    if raw_mc_info:
                        try:
                            scan['mc_info'] = json.loads(raw_mc_info)
                        except Exception:
                            scan['mc_info'] = None
                    scan['risk_score'] = int(_row_get(vrow, 7, 'risk_score') or 0)
                    raw_ens = _row_get(vrow, 8, 'ensemble_data')
                    if raw_ens:
                        try:
                            scan['ensemble_data'] = json.loads(raw_ens)
                        except Exception:
                            scan['ensemble_data'] = None
                cursor.execute('RELEASE SAVEPOINT opt_cols')
                print("  step2 opt_cols OK")
            except Exception as e:
                print(f"  step2 opt_cols FAIL: {type(e).__name__}: {e}")
                try: cursor.execute('ROLLBACK TO SAVEPOINT opt_cols')
                except Exception: pass

            try:
                cursor.execute(f'''
                    SELECT st.created_by FROM scans s
                    LEFT JOIN scan_tokens st ON s.token_id = st.id
                    WHERE s.id = {_PH}
                ''', (scan_id,))
                srow = cursor.fetchone()
                scan['scanned_by'] = srow[0] if srow and srow[0] else None
                print(f"  step3 scanned_by OK: {scan['scanned_by']}")
            except Exception as e:
                print(f"  step3 scanned_by FAIL: {type(e).__name__}: {e}")
                scan['scanned_by'] = None

            _has_extra_col = True
            try:
                cursor.execute('SAVEPOINT extra_select')
                cursor.execute(f'''
                    SELECT id, issue_type, issue_name, issue_path, issue_category,
                           alert_level, confidence, detected_patterns, obfuscation_detected,
                           file_hash, ai_analysis, ai_confidence, feedback_status, extra
                    FROM scan_results WHERE scan_id = {_PH}
                ''', (scan_id,))
                cursor.execute('RELEASE SAVEPOINT extra_select')
                print("  step4 select_results_with_extra OK")
            except Exception as e:
                print(f"  step4 select_results_with_extra FAIL: {type(e).__name__}: {e}")
                try: cursor.execute('ROLLBACK TO SAVEPOINT extra_select')
                except Exception: pass
                _has_extra_col = False
                cursor.execute(f'''
                    SELECT id, issue_type, issue_name, issue_path, issue_category,
                           alert_level, confidence, detected_patterns, obfuscation_detected,
                           file_hash, ai_analysis, ai_confidence, feedback_status
                    FROM scan_results WHERE scan_id = {_PH}
                ''', (scan_id,))

            results = []
            for r in cursor.fetchall():
                raw_patterns = _row_get(r, 7, 'detected_patterns')
                extra_obj = {}
                if _has_extra_col:
                    raw_extra = _row_get(r, 13, 'extra')
                    if raw_extra:
                        try:
                            extra_obj = json.loads(raw_extra) if isinstance(raw_extra, str) else (raw_extra or {})
                            if not isinstance(extra_obj, dict):
                                extra_obj = {}
                        except (TypeError, ValueError):
                            extra_obj = {}
                results.append({
                    'id': _row_get(r, 0, 'id'),
                    'issue_type': _row_get(r, 1, 'issue_type'),
                    'issue_name': _row_get(r, 2, 'issue_name'),
                    'issue_path': _row_get(r, 3, 'issue_path'),
                    'issue_category': _row_get(r, 4, 'issue_category'),
                    'alert_level': _row_get(r, 5, 'alert_level'),
                    'confidence': _row_get(r, 6, 'confidence'),
                    'detected_patterns': json.loads(raw_patterns) if raw_patterns else [],
                    'obfuscation_detected': bool(_row_get(r, 8, 'obfuscation_detected')),
                    'file_hash': _row_get(r, 9, 'file_hash'),
                    'ai_analysis': _row_get(r, 10, 'ai_analysis'),
                    'ai_confidence': _row_get(r, 11, 'ai_confidence'),
                    'feedback_status': _row_get(r, 12, 'feedback_status'),
                    'extra': extra_obj,
                })
            print(f"  step5 process_results OK ({len(results)} rows)")

            try:
                results = _scrub_results_for_display(results)
                print(f"  step6 scrub_results OK ({len(results)} rows)")
            except Exception as e:
                print(f"  step6 scrub_results FAIL: {type(e).__name__}: {e}")

            scan['results'] = results

            # AHORA EL CRITICO: jsonify
            try:
                with app.app_context(), app.test_request_context():
                    resp = jsonify(scan)
                    body = resp.get_data(as_text=True)
                    print(f"  step7 jsonify(scan) OK length={len(body)}")
            except Exception as e:
                import traceback as _tb
                print(f"  step7 jsonify(scan) FAIL: {type(e).__name__}: {e}")
                print(_tb.format_exc())

    except Exception as e:
        import traceback as _tb
        print(f"  OUTER FAIL: {type(e).__name__}: {e}")
        print(_tb.format_exc())


if __name__ == '__main__':
    for sid in (96, 95, 94):
        diag_get_scan(sid)
