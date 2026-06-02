"""Convierte salida de source/scanners/*.py al formato issues_found."""
from __future__ import annotations

import os

_CHEAT_URL = (
    'vape', 'liquidbounce', 'wurst', 'sigma', 'flux', 'astolfo', 'cheat',
    'hack', 'inject', 'baritone', 'mineflayer', 'autoclick', 'ghost',
    'killaura', 'reach', 'xray', 'forgehax', 'meteor', 'rusherhack',
)


def _issue(nombre, ruta='', alerta='SOSPECHOSO', tipo='novel_scanner', conf=0.68, **kw):
    return {
        'tipo': tipo,
        'nombre': nombre,
        'ruta': ruta or '',
        'archivo': os.path.basename(ruta) if ruta else '',
        'detalle': kw.get('detalle', ruta or nombre),
        'alerta': alerta,
        'categoria': kw.get('categoria', 'NOVEL'),
        'confidence': conf,
        'detected_patterns': kw.get('detected_patterns', [tipo]),
        'explicacion': kw.get('explicacion', nombre),
    }


def convert_scanner_output(scanner_id: str, data) -> list:
    """Traduce cualquier estructura devuelta por scanners/ a hallazgos."""
    if data is None:
        return []
    out = []

    if isinstance(data, dict) and 'findings' in data:
        for f in (data.get('findings') or [])[:25]:
            if not isinstance(f, dict):
                continue
            pat = f.get('pattern', f.get('type', scanner_id))
            path = f.get('path', '')
            out.append(_issue(
                f'[{scanner_id}] Patrón en clipboard: {pat}',
                path, 'SOSPECHOSO', f'novel_{scanner_id}', 0.75,
                categoria='CLIPBOARD',
            ))
        items = data.get('items') or []
        if len(items) > 50 and not out:
            out.append(_issue(
                f'[{scanner_id}] Historial clipboard voluminoso ({len(items)} entradas)',
                items[0] if items else '', 'POCO_SOSPECHOSO', f'novel_{scanner_id}', 0.45,
            ))
        return out[:20]

    if isinstance(data, dict):
        for conn in (data.get('suspicious_connections') or [])[:15]:
            entry = conn.get('entry', conn) if isinstance(conn, dict) else conn
            out.append(_issue(
                f'[{scanner_id}] Conexión de red sospechosa',
                str(entry)[:200], 'CRITICAL', f'novel_{scanner_id}', 0.82,
                categoria='NETWORK',
            ))
        for entry in (data.get('hosts_entries') or [])[:15]:
            low = str(entry).lower()
            if any(k in low for k in ('minecraft', 'mojang', 'hypixel', 'vape')):
                out.append(_issue(
                    f'[{scanner_id}] Hosts: {str(entry)[:90]}',
                    r'C:\Windows\System32\drivers\etc\hosts', 'CRITICAL', f'novel_{scanner_id}', 0.88,
                    categoria='NETWORK',
                ))
        for browser, rows in data.items():
            if not isinstance(rows, list):
                continue
            for row in rows[:40]:
                if not isinstance(row, dict):
                    continue
                url = (row.get('url') or '').lower()
                title = (row.get('title') or '').lower()
                if any(c in url or c in title for c in _CHEAT_URL):
                    out.append(_issue(
                        f'[{scanner_id}] Historial web: {url[:80]}',
                        url[:200], 'SOSPECHOSO', f'novel_{scanner_id}', 0.72,
                        categoria='BROWSER',
                    ))
        filt = (data.get('filters') or '').strip() if isinstance(data.get('filters'), str) else ''
        if filt or (data.get('consumers') or '').strip():
            out.append(_issue(
                f'[{scanner_id}] Persistencia WMI (EventFilter/Consumer)',
                'WMI:\\root\\subscription', 'SOSPECHOSO', f'novel_{scanner_id}', 0.74,
                categoria='PERSISTENCE',
            ))
        if out:
            return out[:25]

    if isinstance(data, list):
        for row in data[:35]:
            if not isinstance(row, dict):
                continue
            if row.get('suspicious') is True or (row.get('score') or 0) >= 3:
                cmd = ' '.join(str(x) for x in (row.get('command') or []))[:180]
                path = row.get('task', row.get('path', row.get('location', cmd)))
                out.append(_issue(
                    f'[{scanner_id}] Entrada sospechosa: {row.get("name", os.path.basename(str(path)))}',
                    str(path)[:220], 'SOSPECHOSO', f'novel_{scanner_id}', 0.7,
                ))
                continue
            reason = row.get('reason', row.get('type', ''))
            if reason in ('hack_client_reference', 'eventlog_cleared_security_1102',
                          'eventlog_cleared_system_104', 'timestomp_suspected'):
                alerta = 'CRITICAL' if 'hack' in reason or 'eventlog' in reason else 'SOSPECHOSO'
                out.append(_issue(
                    f'[{scanner_id}] {reason}: {row.get("name", row.get("key", ""))}',
                    str(row.get('key', row.get('path', '')))[:220], alerta, f'novel_{scanner_id}',
                    0.85 if alerta == 'CRITICAL' else 0.65,
                ))
                continue
            name = (row.get('name') or row.get('type') or '').lower()
            exe = row.get('exe', row.get('path', ''))
            cpu = row.get('cpu', 0)
            if any(m in name for m in ('xmrig', 'miner', 'cpuminer', 'ethminer')) or (cpu and float(cpu) >= 75):
                out.append(_issue(
                    f'[{scanner_id}] Proceso tipo minería: {name} CPU={cpu}',
                    str(exe)[:200], 'CRITICAL', f'novel_{scanner_id}', 0.9,
                    categoria='MINING',
                ))
                continue
            key = row.get('key', '')
            val = str(row.get('value', ''))[:120]
            if key and any(c in val.lower() for c in _CHEAT_URL):
                out.append(_issue(
                    f'[{scanner_id}] Registro: {row.get("name", "")} → {val[:60]}',
                    key[:220], 'CRITICAL', f'novel_{scanner_id}', 0.86,
                    categoria='REGISTRY',
                ))
                continue
            if row.get('type') and 'vault' not in str(row.get('type')).lower():
                out.append(_issue(
                    f'[{scanner_id}] {row.get("type")}',
                    str(row.get('path', exe))[:200], 'POCO_SOSPECHOSO', f'novel_{scanner_id}', 0.5,
                ))
        return out[:25]

    return out
