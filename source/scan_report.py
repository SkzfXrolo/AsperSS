"""Resumen de escaneo para Discord / staff (v1.7)."""
from datetime import datetime


def build_discord_summary(app):
    """Texto listo para pegar en Discord tras un SS."""
    issues = getattr(app, 'issues_found', []) or []
    mc = getattr(app, 'detected_minecraft_username', None) or '—'
    staff = (getattr(app, 'config', {}) or {}).get('staff_name') or 'Staff'
    company = (getattr(app, 'config', {}) or {}).get('company_name') or ''
    country = ''
    try:
        if getattr(app, 'db_integration', None) and app.db_integration.user_info:
            country = app.db_integration.user_info.get('country') or ''
    except Exception:
        pass

    crit = [i for i in issues if (i.get('alerta') or '').upper() == 'CRITICAL']
    susp = [i for i in issues if (i.get('alerta') or '').upper() == 'SOSPECHOSO']
    mouse = getattr(app, 'mouse_findings', []) or []
    pack_n = sum(1 for i in issues if (i.get('categoria') or '') in ('EXTENDED', 'MINING_AUTOMATION'))

    lines = [
        '```',
        'ARGUS SCANNER v1.7 — Resumen SS',
        f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'Staff: {staff}' + (f' · {company}' if company else ''),
        f'Jugador/MC: {mc}' + (f' · {country}' if country else ''),
        '—' * 32,
        f'CRITICAL: {len(crit)} | SOSPECHOSO: {len(susp)} | Total: {len(issues)}',
        f'Mouse (silencioso): {len(mouse)} | Pack módulos: {pack_n}',
    ]
    if crit:
        lines.append('— Top CRITICAL —')
        for i in crit[:8]:
            lines.append(f'• {i.get("nombre", "?")[:70]}')
    elif susp:
        lines.append('— Top SOSPECHOSO —')
        for i in susp[:6]:
            lines.append(f'• {i.get("nombre", "?")[:70]}')
    else:
        lines.append('Sin hallazgos CRITICAL/SOSPECHOSO en este scan.')
    lines.append('```')
    return '\n'.join(lines)


def copy_to_clipboard(root, text):
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        return True
    except Exception:
        return False
