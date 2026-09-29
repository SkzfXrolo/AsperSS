"""Corre un escaneo COMPLETO en esta PC con las mejoras actuales y abre un
reporte HTML local. NO sube nada a la API / panel.

Uso:   python run_local_scan.py
"""
import os
import sys
import time
import html
import functools
import webbrowser
import datetime as dt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["ARGUS_LOCAL_SCAN"] = "1"          # sin token / sin API / sin subida
os.environ["ARGUS_TQDM"] = "0"
os.environ.setdefault("ARGUS_SCAN_MODE", "standard")  # fast | standard | paranoid
try:
    sys.stdout.reconfigure(line_buffering=True, errors="replace")
    sys.stderr.reconfigure(line_buffering=True, errors="replace")
except Exception:
    pass

import main  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "argus_report_local.html")


def run_scan():
    import tkinter as tk

    # Evitar que el flujo normal dispare full_scan_with_discord (que sube a la API).
    main.ArgusApp._finish_ui_and_scan = lambda self: None
    # Anular cualquier subida por las dudas.
    for _m in ("upload_results", "_submit_scan_results", "send_results_to_api",
               "_upload_scan_results", "report_to_api"):
        if hasattr(main.ArgusApp, _m):
            setattr(main.ArgusApp, _m, lambda self, *a, **k: None)

    root = tk.Tk()
    root.withdraw()
    app = main.ArgusApp(root)
    app._headless_mode = True

    # Esperar a que el motor async termine de inicializar (DB, hashes, forense…).
    print("[init] preparando motor…")
    for _ in range(1200):                  # hasta ~2 min
        try:
            root.update()
        except Exception:
            break
        if getattr(app, "_engine_ready", False) and hasattr(app, "scanning"):
            break
        time.sleep(0.1)
    if not hasattr(app, "scanning"):
        app.scanning = False
    if getattr(app, "_startup_error", None):
        print(f"[init] warning: {app._startup_error}")

    print("\n=== Argus · escaneo local (con mejoras) ===")
    t0 = time.time()
    try:
        app.execute_full_scan_silent()     # scan completo + filtros (sin subir)
    except BaseException as e:
        import traceback
        traceback.print_exc()
        print(f"[scan] terminó con excepción (se reporta lo que haya): {e}")

    try:
        for _ in range(80):
            root.update()
            if not getattr(app, "scanning", False):
                break
            time.sleep(0.25)
    except Exception:
        pass

    issues = list(getattr(app, "issues_found", []) or [])
    verdict = dict(getattr(app, "ss_verdict", None) or {})
    files = getattr(app, "total_files_scanned", 0)
    dirs = getattr(app, "total_dirs_scanned", 0)
    print(f"[scan] capturados {len(issues)} hallazgos, verdict={verdict.get('verdict')}, "
          f"{files} archivos, {round(time.time()-t0)}s")
    try:
        root.destroy()
    except Exception:
        pass
    print(f"[scan] {len(issues)} hallazgos · {files} archivos · {round(time.time()-t0)}s")
    return issues, verdict, files, dirs


_LEVEL_ORDER = {"CRITICAL": 0, "MUY_SOSPECHOSO": 1, "SOSPECHOSO": 2, "POCO_SOSPECHOSO": 3, "NORMAL": 4, "": 5}
_LEVEL_ES = {"CRITICAL": "Crítico", "MUY_SOSPECHOSO": "Muy sospechoso", "SOSPECHOSO": "Sospechoso",
             "POCO_SOSPECHOSO": "Poco sospechoso", "NORMAL": "Informativo"}
_LEVEL_COLOR = {"CRITICAL": "#f0655f", "MUY_SOSPECHOSO": "#f0655f", "SOSPECHOSO": "#f6bd52",
                "POCO_SOSPECHOSO": "#6ba4ff", "NORMAL": "#727a87"}


def _e(x):
    return html.escape(str(x if x is not None else ""))


def render_html(issues, verdict, files, dirs):
    issues = [i for i in issues if isinstance(i, dict)]
    issues.sort(key=lambda i: (_LEVEL_ORDER.get((i.get("alerta") or "").upper(), 5),
                               -float(i.get("confidence", 0) or 0)))
    v = (verdict.get("verdict") or "sin veredicto")
    risk = verdict.get("risk_score")
    summary = verdict.get("summary_es") or verdict.get("summary") or ""
    reasons = verdict.get("reasons") or []
    counts = {}
    for i in issues:
        k = (i.get("alerta") or "NORMAL").upper()
        counts[k] = counts.get(k, 0) + 1

    vcolor = "#f0655f" if v.lower() in ("hack", "ban") else "#f6bd52" if "sosp" in v.lower() or v.lower() == "suspicious" else "#3ddc84"

    rows = []
    for i in issues:
        lvl = (i.get("alerta") or "NORMAL").upper()
        col = _LEVEL_COLOR.get(lvl, "#727a87")
        conf = i.get("confidence", 0) or 0
        conf_pct = round(conf * 100) if conf <= 1 else round(conf)
        pats = ", ".join(str(p) for p in (i.get("detected_patterns") or []))
        rows.append(f"""
      <tr>
        <td><span class="pill" style="color:{col};border-color:{col}55;background:{col}18">{_e(_LEVEL_ES.get(lvl, lvl))}</span></td>
        <td class="nm">{_e(i.get('nombre') or i.get('archivo') or '—')}</td>
        <td class="pa mono">{_e(i.get('ruta') or i.get('archivo') or '')}</td>
        <td class="ce">{conf_pct}%</td>
        <td class="ty mono">{_e(i.get('tipo') or '')}</td>
      </tr>
      <tr class="exp"><td></td><td colspan="4">
        <div class="why">{_e(i.get('explicacion') or i.get('explanation') or '')}</div>
        {f'<div class="pat mono">patrones: {_e(pats)}</div>' if pats else ''}
      </td></tr>""")

    chips = "".join(
        f'<span class="chip" style="--c:{_LEVEL_COLOR.get(k,"#727a87")}">{counts[k]} {_e(_LEVEL_ES.get(k,k))}</span>'
        for k in sorted(counts, key=lambda x: _LEVEL_ORDER.get(x, 5))
    )
    reasons_html = "".join(f"<li>{_e(r)}</li>" for r in reasons[:12])

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Argus · Reporte local</title>
<style>
:root{{--bg:#0b0d11;--c1:#12151b;--c2:#161a21;--tx:#eef0f3;--dim:#aeb6c2;--mut:#727a87;--bd:#232a34;--ac:#3ddc84}}
*{{box-sizing:border-box;margin:0}}body{{background:var(--bg);color:var(--tx);font:15px/1.55 "Segoe UI",system-ui,sans-serif;padding:28px}}
.wrap{{max-width:1100px;margin:0 auto}}
h1{{font-size:22px;font-weight:650;letter-spacing:-.01em}}.sub{{color:var(--mut);font-size:13px;margin-top:2px}}
.verdict{{display:flex;align-items:center;gap:18px;margin:22px 0;padding:20px 22px;background:var(--c2);border:1px solid var(--bd);border-radius:14px}}
.vbig{{font-size:30px;font-weight:700;text-transform:uppercase;letter-spacing:.02em}}
.risk{{font-size:13px;color:var(--dim)}}.risk b{{font-size:26px;color:var(--tx);font-weight:650}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 6px}}
.chip{{font-size:12px;font-weight:600;padding:4px 10px;border-radius:999px;color:var(--c);border:1px solid color-mix(in srgb,var(--c) 40%,transparent);background:color-mix(in srgb,var(--c) 12%,transparent)}}
.card{{background:var(--c2);border:1px solid var(--bd);border-radius:14px;margin:18px 0;overflow:hidden}}
.card h2{{font-size:14px;font-weight:600;padding:14px 18px;border-bottom:1px solid var(--bd)}}
ul{{padding:12px 18px 14px 34px}}li{{margin:3px 0;color:var(--dim);font-size:14px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);padding:11px 18px;border-bottom:1px solid var(--bd)}}
td{{padding:9px 18px;border-bottom:1px solid #1a2029;vertical-align:top}}
tr.exp td{{padding-top:0;border-bottom:1px solid var(--bd)}}
.why{{color:var(--dim);font-size:13px}}.pat{{color:var(--mut);font-size:11.5px;margin-top:3px}}
.nm{{font-weight:500}}.pa{{color:var(--mut);font-size:12px;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ty{{color:var(--mut);font-size:12px}}.ce{{color:var(--dim)}}
.pill{{font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid;white-space:nowrap}}
.mono{{font-family:"Consolas",ui-monospace,monospace}}
.empty{{padding:36px;text-align:center;color:var(--mut)}}
.foot{{color:var(--mut);font-size:12px;margin-top:24px;text-align:center}}
</style></head><body><div class="wrap">
<h1>Argus · Reporte de escaneo local</h1>
<div class="sub">{dt.datetime.now().strftime('%d/%m/%Y %H:%M')} · {files} archivos · {dirs} carpetas · esta PC · NO subido al panel</div>

<div class="verdict">
  <div class="vbig" style="color:{vcolor}">{_e(v)}</div>
  <div class="risk">riesgo<br><b>{_e(risk if risk is not None else '–')}</b><span style="color:var(--mut)">/100</span></div>
  <div style="flex:1;color:var(--dim);font-size:14px">{_e(summary)}</div>
</div>

<div class="chips">{chips or '<span class="chip" style="--c:#3ddc84">sin hallazgos</span>'}</div>

{f'<div class="card"><h2>Por qué este veredicto</h2><ul>{reasons_html}</ul></div>' if reasons_html else ''}

<div class="card">
  <h2>Hallazgos ({len(issues)})</h2>
  {'<table><thead><tr><th>Nivel</th><th>Hallazgo</th><th>Ruta</th><th>Conf.</th><th>Tipo</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' if issues else '<div class="empty">✓ Sin hallazgos. Escaneo limpio.</div>'}
</div>

<div class="foot">Generado por run_local_scan.py · Argus Scanner v{getattr(main, 'SCANNER_VERSION', '?')}</div>
</div></body></html>"""


def main_():
    issues, verdict, files, dirs = [], {}, 0, 0
    try:
        issues, verdict, files, dirs = run_scan()
    except BaseException:
        import traceback
        traceback.print_exc()
    try:
        htmltxt = render_html(issues, verdict, files, dirs)
    except Exception:
        import traceback
        traceback.print_exc()
        htmltxt = "<h1>Argus · reporte</h1><pre>" + _e(repr(issues[:50])) + "</pre>"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(htmltxt)
    print(f"\n[reporte] {OUT}  ({len(issues)} hallazgos)")
    try:
        webbrowser.open("file:///" + OUT.replace("\\", "/"))
    except Exception:
        pass


if __name__ == "__main__":
    main_()
