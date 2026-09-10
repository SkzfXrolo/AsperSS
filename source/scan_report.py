"""Resumen de escaneo para Discord / staff (v1.8)."""
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
    mode = getattr(app, 'scan_mode', None) or (getattr(app, 'config', {}) or {}).get('scan_mode') or 'standard'

    verdict = getattr(app, 'ss_verdict', None) or {}
    v_label = verdict.get('verdict') or '—'
    v_score = verdict.get('risk_score')
    if v_score is None:
        v_score = '—'
    v_action = verdict.get('staff_action') or ''
    v_reasons = verdict.get('reasons') or []
    timeline = verdict.get('timeline') or []
    kill_chain = verdict.get('kill_chain') or []

    lines = [
        '```',
        'ARGUS SCANNER — Resumen SS',
        f'Fecha: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'Modo: {mode}',
        f'Staff: {staff}' + (f' · {company}' if company else ''),
        f'Jugador/MC: {mc}' + (f' · {country}' if country else ''),
        '—' * 32,
        f'VERDICTO: {v_label}  |  Risk: {v_score}/100',
    ]
    if v_action:
        lines.append(f'Acción: {v_action}')
    flags = []
    tipos = {(i.get('tipo') or '') for i in issues}
    if tipos & {'remote_access_active', 'rdp_session_active'}:
        flags.append('REMOTE')
    if 'recycle_hash_match' in tipos:
        flags.append('HASH_PAPELERA')
    if any(i.get('combination_penalty') for i in issues):
        flags.append('COMBO')
    if tipos & {'browser_hack_cookie', 'wininet_hack_cookie'}:
        flags.append('COOKIE')
    if 'prefetch_referenced_hack' in tipos:
        flags.append('PREF_REF')
    if 'lnk_xaml_hijack' in tipos:
        flags.append('LNK_HIJACK')
    if flags:
        lines.append('Flags: ' + ' · '.join(flags))
    if v_reasons:
        lines.append('Razones:')
        for r in v_reasons[:5]:
            lines.append(f'  · {r[:72]}')
    if kill_chain:
        lines.append('Kill-chain:')
        for step in kill_chain[:5]:
            lines.append(f"  > [{step.get('phase', '?')}] {str(step.get('detail', ''))[:60]}")
    if timeline:
        lines.append('Timeline:')
        for ev in timeline[:5]:
            ts = ev.get('timestamp') or '—'
            lines.append(f"  {ts} · {str(ev.get('detail', ''))[:56]}")
    lines.append('—' * 32)
    lines.append(
        f'CRITICAL: {len(crit)} | SOSPECHOSO: {len(susp)} | Total: {len(issues)}'
    )
    lines.append(f'Mouse: {len(mouse)} | Pack módulos: {pack_n}')
    top = verdict.get('top_findings') or []
    if not top:
        pool = [i for i in (crit or susp) if (i.get('tipo') or '') != 'ss_verdict']
        top = pool[:5]
    if top:
        lines.append('— Top evidencia —')
        for i in top[:5]:
            if (i.get('tipo') or '') == 'ss_verdict':
                continue
            name = (i.get('nombre') or '?')[:52]
            h = (i.get('file_hash') or i.get('sha256') or '')[:12]
            ts = (i.get('timestamp') or i.get('last_executed') or '')[:19]
            rel = 0
            try:
                rel = int((i.get('extra') or {}).get('related_count') or i.get('related_count') or 0)
            except Exception:
                rel = 0
            combo = i.get('combination_penalty') or (i.get('extra') or {}).get(
                'combination_penalty'
            )
            bits = [name]
            if h:
                bits.append(f'hash={h}')
            if ts:
                bits.append(f't={ts}')
            if rel:
                bits.append(f'related={rel}')
            if combo:
                bits.append(f'combo={combo}')
            lines.append('• ' + ' · '.join(bits))
    elif crit:
        lines.append('— Top CRITICAL —')
        for i in crit[:6]:
            if (i.get('tipo') or '') == 'ss_verdict':
                continue
            lines.append(f'• {i.get("nombre", "?")[:70]}')
    else:
        lines.append('Sin hallazgos CRITICAL/SOSPECHOSO en este scan.')

    timings = getattr(app, 'pipeline_timings', None) or {}
    if timings:
        bits = [f'{k}:{float(v):.0f}s' for k, v in list(timings.items())[:6]]
        lines.append('Perf: ' + ' | '.join(bits))
    fstats = getattr(app, 'last_filter_stats', None) or {}
    if fstats:
        dropped = [
            f'{k}={v}' for k, v in sorted(fstats.items(), key=lambda x: -int(x[1] or 0))
            if not str(k).startswith('_')
        ][:4]
        if dropped:
            lines.append('Filter: ' + ', '.join(dropped)
                         + f" (kept {fstats.get('_kept', '?')}/{fstats.get('_input', '?')})")
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
