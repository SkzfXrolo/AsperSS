#!/usr/bin/env python3
"""Genera source/docs/staff_roadmap_presentacion.html desde las mega-listas."""
from __future__ import annotations

import html
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "source" / "docs" / "staff_roadmap_presentacion.html"

IMPROVE = [
    ("scanner", "Más señales forenses / detección real de cheats sin inventar ruido."),
    ("deteccion", "Más señales forenses / detección real de cheats sin inventar ruido."),
    ("detección", "Más señales forenses / detección real de cheats sin inventar ruido."),
    ("filtro", "Menos falsos positivos → staff confía en CRITICAL y pierde menos tiempo."),
    ("anti-fp", "Menos falsos positivos → staff confía en CRITICAL y pierde menos tiempo."),
    ("anti-false", "Menos falsos positivos → staff confía en CRITICAL y pierde menos tiempo."),
    ("fp", "Menos falsos positivos → staff confía en CRITICAL y pierde menos tiempo."),
    ("visual", "Staff decide más rápido: veredicto, timeline, panel claro."),
    ("ui", "Staff decide más rápido: veredicto, timeline, panel claro."),
    ("ux", "Staff decide más rápido: veredicto, timeline, panel claro."),
    ("ia", "Score/veredicto más calibrado; menos grises sin explicación."),
    ("ml", "Score/veredicto más calibrado; menos grises sin explicación."),
    ("machine", "Score/veredicto más calibrado; menos grises sin explicación."),
    ("oracle", "Asistente / juez AI que acelera review y documenta el porqué."),
    ("plugin", "SS en servidor: freeze, token, anticheat en vivo junto al scanner."),
    ("android", "Cobertura Bedrock / mobile cuando el cheat no está solo en Windows."),
    ("linux", "Paridad fuera de Windows (build/distribución / scanners)."),
    ("doble", "Corroboración móvil+desktop / segundo canal de evidencia."),
    ("plataforma", "Empaquetado, update, firmas, ops — el producto llega al staff."),
    ("performance", "SS más rápido y predecible (ETA reales)."),
    ("scoring", "Mejor ranking de hallazgos → Top evidencia primero."),
]
DEFAULT_IMPROVE = "Mejora incremental del producto SS / panel / ecosistema Argus."


def improve_for(sector: str, title: str) -> str:
    blob = f"{sector} {title}".lower()
    for key, val in IMPROVE:
        if key in blob:
            return val
    return DEFAULT_IMPROVE


def normalize_status(raw: str) -> str:
    s = (raw or "").strip().upper()
    if s in ("X", "DONE", "[X]", "[DONE]"):
        return "hecho"
    if s in ("-", "DEFERRED", "[-]"):
        return "deferred"
    if s in ("WIP", "[WIP]"):
        return "wip"
    if s in ("REVIEW", "[REVIEW]"):
        return "review"
    return "pendiente"


items: list[dict] = []


def add(source, sector, status, num, title, detail="", prio="", horizon=""):
    title = re.sub(r"\s+", " ", title).strip(" -–—.")
    if not title or len(title) < 8:
        return
    items.append(
        {
            "source": source,
            "sector": sector,
            "status": normalize_status(status),
            "num": str(num),
            "title": title[:220],
            "detail": detail[:400],
            "prio": prio or "P2",
            "horizon": horizon,
            "improve": improve_for(sector, title),
        }
    )


def parse_pack48():
    sector = "General"
    path = ROOT / "MEJORAS_PACK48.txt"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*SECTOR\s+(\d+)/9\s*[—\-]+\s*(.+)", line)
        if m:
            sector = re.sub(r"\s+\d+\s*ítems?\s*$", "", m.group(2).strip(), flags=re.I)
            continue
        m = re.match(
            r"\[([ X\-]|WIP|REVIEW|DONE)\]\s+(\d+)\.\s*(?:\(([^)]+)\)\s*)?(.+)",
            line,
            re.I,
        )
        if not m:
            continue
        st, num, meta, rest = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        prio = ""
        pm = re.search(r"P(\d)", meta)
        if pm:
            prio = "P" + pm.group(1)
        title = rest.split(" DONE:")[0].split(" — ")[0].strip()
        detail = ""
        if " — " in rest:
            detail = rest.split(" — ", 1)[1].split(" DONE:")[0].strip()
        add("PACK48", sector, st, num, title, detail, prio, "Q+")


def parse_180():
    sector = "Scanner (detección)"
    path = ROOT / "MEJORAS_180.txt"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        up = line.upper()
        if "PARTE 1" in line and "SCANNER" in up:
            sector = "Scanner (detección)"
            continue
        if "PARTE 2" in line and "FILTRO" in up:
            sector = "Filtro / Anti-FP"
            continue
        if "PARTE 3" in line and "VISUAL" in up:
            sector = "Visual / UI"
            continue
        if "LINUX" in up and ("PARTE" in up or "PLATAFORMA" in up or "15" in line):
            sector = "Plataforma Linux"
            continue
        if "ANDROID" in up and ("PARTE" in up or "PLATAFORMA" in up or "15" in line):
            sector = "Plataforma Android"
            continue
        m = re.match(r"\[([Xx\-]|WIP|DONE| )\]\s*(\d+)\.\s*(.+)", line)
        if not m:
            continue
        st = m.group(1).strip() or " "
        rest = m.group(3).strip()
        title = rest.split(" DEFERRED")[0].split(" DONE")[0]
        title = re.sub(r"\s+", " ", title)[:200]
        add("MEJORAS_180", sector, st, m.group(2), title, "", "", "Q1-Q2")


def parse_scanner():
    sector = "Detección MC"
    path = ROOT / "MEJORAS_SCANNER.txt"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "PARTE 1" in line:
            sector = "Detección MC"
            continue
        if "PARTE 2" in line or "FALSOS" in line.upper():
            sector = "Filtro FP"
            continue
        if "PARTE 3" in line:
            sector = "Scoring / IA"
            continue
        m = re.match(r"(\d+)\.\s+([A-ZÁÉÍÓÚÑ0-9].+)", line)
        if not m:
            continue
        t = m.group(2).strip()
        if t.isupper() or (len(t) < 90 and not t.endswith(".")):
            title = t.title() if t.isupper() else t
            add("MEJORAS_SCANNER", sector, " ", m.group(1), title, "", "P1", "Q1")


def parse_todo_sesion():
    sector = "Sesión / deuda"
    path = ROOT / "TODO_PROXIMA_SESION.txt"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("═") or line.startswith("─"):
            continue
        m = re.match(
            r"\[(DONE|WIP|TODO| |X|\-|PENDING)\]\s*(\d+)\.\s*(.+)",
            line,
            re.I,
        )
        if not m:
            continue
        add("TODO_SESION", sector, m.group(1), m.group(2), m.group(3).strip(), "", "P2", "Q1")


def assign_horizons(it: dict) -> None:
    if it["status"] == "hecho":
        it["horizon"] = "Hecho"
    elif it["status"] == "deferred":
        it["horizon"] = "Mes 4–6+ / deferred"
    elif it["prio"] == "P0":
        it["horizon"] = "Mes 1"
    elif it["prio"] == "P1":
        it["horizon"] = "Mes 1–2"
    elif it["source"] == "MEJORAS_SCANNER":
        it["horizon"] = "Mes 1–3"
    elif "Linux" in it["sector"] or "Android" in it["sector"]:
        it["horizon"] = "Mes 4–6+"
    elif any(x in it["sector"] for x in ("IA", "ML", "Oracle", "Machine")):
        it["horizon"] = "Mes 2–4"
    elif "Plugin" in it["sector"]:
        it["horizon"] = "Mes 2–4"
    elif it["prio"] == "P3":
        it["horizon"] = "Mes 3–6"
    else:
        it["horizon"] = "Mes 2–4"


def main():
    parse_pack48()
    parse_180()
    parse_scanner()
    parse_todo_sesion()

    seen: set[str] = set()
    uniq: list[dict] = []
    for it in items:
        key = re.sub(r"[^a-z0-9]+", "", it["title"].lower())[:80]
        if key in seen or len(key) < 6:
            continue
        seen.add(key)
        assign_horizons(it)
        uniq.append(it)

    by_status: dict[str, int] = defaultdict(int)
    by_sector: dict[str, int] = defaultdict(int)
    by_horizon: dict[str, int] = defaultdict(int)
    for it in uniq:
        by_status[it["status"]] += 1
        by_sector[it["sector"]] += 1
        by_horizon[it["horizon"]] += 1

    sectors = sorted(by_sector.keys())
    horizons = [
        "Mes 1",
        "Mes 1–2",
        "Mes 1–3",
        "Mes 2–4",
        "Mes 3–6",
        "Mes 4–6+",
        "Mes 4–6+ / deferred",
        "Hecho",
    ]
    for h in by_horizon:
        if h not in horizons:
            horizons.append(h)

    rows_html = []
    for i, it in enumerate(uniq, 1):
        detail_html = ""
        if it["detail"]:
            detail_html = f'<div class="d">{html.escape(it["detail"])}</div>'
        rows_html.append(
            "<tr"
            f' data-status="{html.escape(it["status"])}"'
            f' data-sector="{html.escape(it["sector"])}"'
            f' data-horizon="{html.escape(it["horizon"])}"'
            f' data-prio="{html.escape(it["prio"])}"'
            f' data-source="{html.escape(it["source"])}">'
            f'<td class="n">{i}</td>'
            f'<td><span class="st st-{html.escape(it["status"])}">{html.escape(it["status"])}</span></td>'
            f'<td class="prio">{html.escape(it["prio"])}</td>'
            f'<td class="hz">{html.escape(it["horizon"])}</td>'
            f'<td class="sec">{html.escape(it["sector"])}</td>'
            f'<td><div class="t">{html.escape(it["title"])}</div>'
            f"{detail_html}"
            f'<div class="imp">→ {html.escape(it["improve"])}</div></td>'
            f'<td class="src">{html.escape(it["source"])}</td>'
            "</tr>"
        )

    sec_opts = "".join(
        f'<option value="{html.escape(s)}">{html.escape(s)} ({by_sector[s]})</option>'
        for s in sectors
    )
    hz_opts = "".join(
        f'<option value="{html.escape(h)}">{html.escape(h)} ({by_horizon.get(h, 0)})</option>'
        for h in horizons
        if by_horizon.get(h, 0)
    )

    page = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Argus — Backlog completo de planificación</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
<style>
:root {{
  --bg:#0e0f12; --surf:#17181d; --line:#2c2f38; --text:#eee; --muted:#8e929c;
  --accent:#e8a54b; --done:#5cb87a; --pend:#e8a54b; --def:#888; --wip:#6b9fd4;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"IBM Plex Sans",system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.45;padding:1.5rem 1rem 3rem}}
.wrap{{max-width:1200px;margin:0 auto}}
h1{{font-size:1.55rem;font-weight:700;margin:.35rem 0 .5rem}}
.tag{{font-family:"IBM Plex Mono",monospace;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}}
.intro{{color:var(--muted);font-size:.92rem;max-width:58em;margin-bottom:1rem}}
.intro strong{{color:var(--text)}}
.stats{{display:flex;flex-wrap:wrap;gap:.45rem;margin:1rem 0 1.25rem}}
.pill{{font-family:"IBM Plex Mono",monospace;font-size:.7rem;padding:.28rem .55rem;border:1px solid var(--line);border-radius:4px;color:var(--muted)}}
.pill b{{color:var(--text)}}
.filters{{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;background:var(--surf);border:1px solid var(--line);padding:.75rem .9rem;margin-bottom:1rem;position:sticky;top:0;z-index:5}}
.filters label{{font-size:.72rem;color:var(--muted);font-family:"IBM Plex Mono",monospace;display:flex;flex-direction:column;gap:.2rem}}
.filters select,.filters input{{background:#0e0f12;color:var(--text);border:1px solid var(--line);padding:.35rem .5rem;font-size:.8rem;border-radius:4px}}
.filters input{{min-width:180px}}
#count{{font-family:"IBM Plex Mono",monospace;font-size:.75rem;color:var(--accent);margin-left:auto}}
.note{{border-left:3px solid var(--accent);background:var(--surf);padding:.7rem .9rem;font-size:.85rem;color:var(--muted);margin-bottom:1rem}}
table{{width:100%;border-collapse:collapse;font-size:.82rem;background:var(--surf);border:1px solid var(--line)}}
th,td{{padding:.55rem .6rem;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}}
th{{font-family:"IBM Plex Mono",monospace;font-size:.62rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);background:#121318;position:sticky;top:58px;z-index:4}}
.n,.prio,.src{{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--muted);white-space:nowrap}}
.t{{font-weight:600;margin-bottom:.2rem}}
.d{{color:var(--muted);font-size:.78rem;margin-bottom:.25rem}}
.imp{{color:#9bb89f;font-size:.76rem}}
.st{{font-family:"IBM Plex Mono",monospace;font-size:.65rem;font-weight:600;text-transform:uppercase}}
.st-hecho{{color:var(--done)}} .st-pendiente{{color:var(--pend)}} .st-deferred{{color:var(--def)}}
.st-wip{{color:var(--wip)}} .st-review{{color:var(--wip)}}
.hz,.sec{{font-size:.75rem;color:var(--muted)}}
tr.hidden{{display:none}}
h2{{font-family:"IBM Plex Mono",monospace;font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:1.75rem 0 .6rem}}
.order{{display:grid;gap:.5rem}}
@media(min-width:800px){{.order{{grid-template-columns:1fr 1fr}}}}
.card{{background:var(--surf);border:1px solid var(--line);padding:.85rem .95rem}}
.card h3{{font-size:.92rem;margin-bottom:.35rem}}
.card p{{font-size:.82rem;color:var(--muted)}}
footer{{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);font-family:"IBM Plex Mono",monospace;font-size:.7rem;color:var(--muted)}}
</style>
</head>
<body>
<div class="wrap">
  <p class="tag">Planificación interna · sprint ahora · upgrade el mes que viene</p>
  <h1>Argus — cola real de mejoras ({len(uniq)} ítems)</h1>
  <p class="intro">
    Generado desde <strong>MEJORAS_PACK48</strong> (720), <strong>MEJORAS_180</strong> (210),
    <strong>MEJORAS_SCANNER</strong> (80) y <strong>TODO_PROXIMA_SESION</strong>.
    <strong>No es “para dentro de 2 meses”</strong>: se ataca todo lo posible ya;
    el <strong>Upgrade de producto</strong> (versión + .exe) sale el <strong>mes que viene</strong>.
    Los “Mes 1 / Mes 2–4” son <strong>prioridad de cola</strong>, no fechas de espera.
    Cada fila tiene <strong>en qué mejora</strong>. Deduplicado por título.
  </p>
  <div class="stats">
    <span class="pill">Total <b>{len(uniq)}</b></span>
    <span class="pill">Pendiente <b>{by_status.get("pendiente", 0)}</b></span>
    <span class="pill">Hecho <b>{by_status.get("hecho", 0)}</b></span>
    <span class="pill">Deferred <b>{by_status.get("deferred", 0)}</b></span>
    <span class="pill">WIP/Review <b>{by_status.get("wip", 0) + by_status.get("review", 0)}</b></span>
    <span class="pill">Sectores <b>{len(by_sector)}</b></span>
  </div>

  <div class="note">
    <strong>Cómo usarlo:</strong> filtrá por prioridad/horizonte o sector. Hoy: P0/P1
    (FP + evidencia + detección alto valor). El ship 1.9 es el mes próximo — no bumpear
    versión hasta ese día. Deferred = futuro con razón técnica, no cancelado.
    Regenerar: <code>python source/scripts/build_backlog_html.py</code>.
  </div>

  <h2>Orden de ataque (prioridad, no “esperar meses”)</h2>
  <div class="order">
    <div class="card"><h3>Ahora — Precisión &amp; decisión</h3><p>FP boundary, kill-chain, veredicto/Top5, validación SS, panel evidencia. Fast ≤4 min útil.</p></div>
    <div class="card"><h3>Ahora / upgrade — Detección alto valor</h3><p>P1 MEJORAS_SCANNER / Pack48: JVM agents, ghost, recycle, UserAssist, macros HID, firmas.</p></div>
    <div class="card"><h3>Siguiente ola — IA + plugin + Oracle</h3><p>Calibración ML, explainability, freeze/plugin SS, asistente staff.</p></div>
    <div class="card"><h3>Cola larga — Plataforma</h3><p>Linux/Android, dual-scan, signing, polish UI masivo. Deferred técnicos entran acá.</p></div>
  </div>

  <h2>Backlog filtrable</h2>
  <div class="filters">
    <label>Estado
      <select id="fStatus">
        <option value="">todos</option>
        <option value="pendiente" selected>pendiente</option>
        <option value="wip">wip</option>
        <option value="review">review</option>
        <option value="hecho">hecho</option>
        <option value="deferred">deferred</option>
      </select>
    </label>
    <label>Horizonte
      <select id="fHorizon"><option value="">todos</option>{hz_opts}</select>
    </label>
    <label>Sector
      <select id="fSector"><option value="">todos</option>{sec_opts}</select>
    </label>
    <label>Prio
      <select id="fPrio">
        <option value="">todas</option>
        <option value="P0">P0</option>
        <option value="P1">P1</option>
        <option value="P2">P2</option>
        <option value="P3">P3</option>
      </select>
    </label>
    <label>Buscar <input id="fQ" type="search" placeholder="vape, prefetch, panel…" /></label>
    <span id="count"></span>
  </div>

  <table>
    <thead>
      <tr>
        <th>#</th><th>Estado</th><th>Prio</th><th>Horizonte</th><th>Sector</th><th>Mejora + impacto</th><th>Fuente</th>
      </tr>
    </thead>
    <tbody id="tb">
      {"".join(rows_html)}
    </tbody>
  </table>

  <footer>
    Fuentes: MEJORAS_PACK48.txt · MEJORAS_180.txt · MEJORAS_SCANNER.txt · TODO_PROXIMA_SESION.txt<br/>
    Regenerar: python source/scripts/build_backlog_html.py
  </footer>
</div>
<script>
const rows = [...document.querySelectorAll("#tb tr")];
function $(id) {{ return document.getElementById(id); }}
function apply() {{
  const st = $("fStatus").value, hz = $("fHorizon").value, sec = $("fSector").value, pr = $("fPrio").value;
  const q = ($("fQ").value || "").toLowerCase().trim();
  let n = 0;
  for (const r of rows) {{
    const ok =
      (!st || r.dataset.status === st) &&
      (!hz || r.dataset.horizon === hz) &&
      (!sec || r.dataset.sector === sec) &&
      (!pr || r.dataset.prio === pr) &&
      (!q || r.textContent.toLowerCase().includes(q));
    r.classList.toggle("hidden", !ok);
    if (ok) n++;
  }}
  $("count").textContent = n + " visibles / " + rows.length;
}}
["fStatus", "fHorizon", "fSector", "fPrio", "fQ"].forEach((id) => $(id).addEventListener("input", apply));
apply();
</script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT} ({len(uniq)} items, {OUT.stat().st_size} bytes)")
    print("Status:", dict(by_status))


if __name__ == "__main__":
    main()
