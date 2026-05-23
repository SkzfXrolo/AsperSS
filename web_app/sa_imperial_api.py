"""
Control Imperial v2 — API Super Admin (planes, regalos, tokens sorteo, migraciones).
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from flask import jsonify, request

_imperial_cache: dict = {}
_imperial_cache_ts: dict = {}


def _cache_get(key: str, ttl: int = 60):
    import time
    if key in _imperial_cache and (time.time() - _imperial_cache_ts.get(key, 0)) < ttl:
        return _imperial_cache[key]
    return None


def _cache_set(key: str, val):
    import time
    _imperial_cache[key] = val
    _imperial_cache_ts[key] = time.time()


def _cache_bust(*keys):
    if not keys:
        _imperial_cache.clear()
        _imperial_cache_ts.clear()
        return
    for k in keys:
        _imperial_cache.pop(k, None)
        _imperial_cache_ts.pop(k, None)


def _scalar(cur, sql, params=(), row_get=None):
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        return 0
    if row_get:
        return row_get(row, 0, 0) or 0
    return row[0] if not hasattr(row, 'keys') else list(row.values())[0]


def imperial_dashboard_stats(get_api_db_cursor, row_get) -> dict:
    cached = _cache_get('dashboard')
    if cached is not None:
        return cached
    stats = {
        'companies': 0, 'users': 0, 'individuals': 0,
        'misassigned': 0, 'revenue_mrr': 0.0, 'tokens_individual_open': 0,
    }
    try:
        with get_api_db_cursor() as cur:
            stats['companies'] = int(_scalar(cur, 'SELECT COUNT(*) FROM companies', row_get=row_get))
            stats['users'] = int(_scalar(cur, 'SELECT COUNT(*) FROM users', row_get=row_get))
            stats['individuals'] = int(_scalar(
                cur, 'SELECT COUNT(*) FROM users WHERE company_id IS NULL', row_get=row_get,
            ))
            stats['revenue_mrr'] = float(_scalar(
                cur,
                "SELECT COALESCE(SUM(subscription_price), 0) FROM companies "
                "WHERE LOWER(COALESCE(subscription_status, '')) = 'active'",
                row_get=row_get,
            ))
            stats['misassigned'] = int(_scalar(
                cur,
                """
                SELECT COUNT(*) FROM users u
                WHERE (
                    u.company_id IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = u.company_id)
                ) OR (
                    u.company_id IS NULL AND (
                        COALESCE(u.roles, '') LIKE '%empresa%'
                        OR COALESCE(u.roles, '') LIKE '%staff%'
                        OR COALESCE(u.roles, '') LIKE '%administrador%'
                        OR COALESCE(u.roles, '') LIKE '%helper%'
                        OR COALESCE(u.roles, '') LIKE '%moderador%'
                    )
                )
                """,
                row_get=row_get,
            ))
            try:
                stats['tokens_individual_open'] = int(_scalar(
                    cur,
                    'SELECT COUNT(*) FROM registration_tokens '
                    'WHERE is_used = FALSE AND (company_id IS NULL OR company_id = 0)',
                    row_get=row_get,
                ))
            except Exception:
                pass
    except Exception:
        pass
    stats['revenue_mrr'] = round(float(stats['revenue_mrr']), 2)
    _cache_set('dashboard', stats)
    return stats


def _parse_roles(raw):
    if not raw:
        return ['user']
    if isinstance(raw, list):
        return raw
    try:
        r = json.loads(raw)
        return r if isinstance(r, list) else [str(r)]
    except Exception:
        return [str(raw)]


DEFAULT_PLANS = [
    {
        'id': 'ind_basic', 'name': 'Individual Básico', 'type': 'individual',
        'price': 5.0, 'months': 1, 'roles': ['user'], 'color': '#60A5FA',
        'desc': 'Usuario individual de pago estándar.',
    },
    {
        'id': 'ind_gift', 'name': 'Regalo Individual', 'type': 'individual',
        'price': 0.0, 'months': 1, 'roles': ['user'], 'gift': True, 'color': '#34D399',
        'desc': 'Cuenta individual gratuita — ideal regalo o prueba.',
    },
    {
        'id': 'ind_pro', 'name': 'Individual Pro', 'type': 'individual',
        'price': 9.0, 'months': 1, 'roles': ['user'], 'color': '#A78BFA',
        'desc': 'Individual con acceso extendido.',
    },
    {
        'id': 'ent_starter', 'name': 'Empresa Starter', 'type': 'enterprise',
        'price': 13.0, 'months': 1, 'max_users': 8, 'max_admins': 3, 'color': '#D4AF37',
        'desc': 'Plan entrada para servidores pequeños.',
    },
    {
        'id': 'ent_pro', 'name': 'Empresa Pro', 'type': 'enterprise',
        'price': 25.0, 'months': 1, 'max_users': 15, 'max_admins': 5, 'color': '#F59E0B',
        'desc': 'Más staff y volumen de scans.',
    },
    {
        'id': 'ent_enterprise', 'name': 'Enterprise', 'type': 'enterprise',
        'price': 49.0, 'months': 1, 'max_users': 30, 'max_admins': 8, 'color': '#C41E3A',
        'desc': 'Redes grandes — límites amplios.',
    },
    {
        'id': 'ent_trial', 'name': 'Trial 14 días', 'type': 'enterprise',
        'price': 0.0, 'months': 0, 'trial_days': 14, 'max_users': 5, 'max_admins': 2,
        'color': '#94A3B8', 'desc': 'Prueba empresarial sin cargo.',
    },
]


def _is_server_db() -> bool:
    try:
        from auth import USE_POSTGRESQL, USE_MYSQL
        if USE_POSTGRESQL or USE_MYSQL:
            return True
    except Exception:
        pass
    url = (os.environ.get('DATABASE_URL') or '').lower()
    return url.startswith('postgres') or 'mysql' in url


def ensure_imperial_tables(cursor, use_pg=None):
    if use_pg is None:
        use_pg = _is_server_db()
    if use_pg:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_subscription_plans (
                plan_id      VARCHAR(48) PRIMARY KEY,
                payload      TEXT NOT NULL,
                updated_at   TIMESTAMP DEFAULT NOW()
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_gift_tokens_batch (
                id           SERIAL PRIMARY KEY,
                batch_label  VARCHAR(120) NOT NULL,
                token_count  INTEGER NOT NULL DEFAULT 0,
                created_at   TIMESTAMP DEFAULT NOW(),
                detail       TEXT
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_subscription_plans (
                plan_id      TEXT PRIMARY KEY,
                payload      TEXT NOT NULL,
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sa_gift_tokens_batch (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_label  TEXT NOT NULL,
                token_count  INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT DEFAULT (datetime('now')),
                detail       TEXT
            )
        ''')


def _log(cur, action, detail='', target_type=None, target_id=None, ip=None):
    try:
        import sa_permissions as sap
        sap.log_imperial_action(cur, action, target_type=target_type, target_id=target_id, detail=detail, ip=ip)
    except Exception:
        pass


def get_plans_catalog(cursor) -> list:
    ensure_imperial_tables(cursor)
    merged = {p['id']: dict(p) for p in DEFAULT_PLANS}
    try:
        cursor.execute('SELECT plan_id, payload FROM sa_subscription_plans')
        for row in cursor.fetchall() or []:
            pid = row[0] if not hasattr(row, 'keys') else row['plan_id']
            raw = row[1] if not hasattr(row, 'keys') else row['payload']
            try:
                merged[pid] = json.loads(raw)
            except Exception:
                pass
    except Exception:
        pass
    return list(merged.values())


def save_plan(cursor, plan: dict) -> dict:
    ensure_imperial_tables(cursor)
    pid = (plan.get('id') or '').strip()
    if not pid:
        raise ValueError('plan.id requerido')
    payload = json.dumps(plan)
    try:
        cursor.execute(
            'INSERT INTO sa_subscription_plans (plan_id, payload, updated_at) VALUES (%s, %s, NOW()) '
            'ON CONFLICT (plan_id) DO UPDATE SET payload = EXCLUDED.payload, updated_at = NOW()',
            (pid, payload),
        )
    except Exception:
        cursor.execute(
            'INSERT OR REPLACE INTO sa_subscription_plans (plan_id, payload, updated_at) VALUES (?, ?, datetime("now"))',
            (pid, payload),
        )
    return plan


def find_misassigned_users(users, companies):
    cmap = {c.get('id'): c for c in companies}
    out = []
    for u in users:
        roles = u.get('roles') or []
        cid = u.get('company_id')
        reasons = []
        if cid and cid not in cmap:
            reasons.append('company_id inválido')
        if any(r in roles for r in ('empresa', 'staff', 'administrador', 'helper', 'moderador')) and not cid:
            reasons.append('rol staff/empresa sin company_id')
        if 'empresa' in roles and not cid:
            reasons.append('rol empresa sin empresa')
        if reasons:
            out.append({**u, 'misassign_reasons': reasons})
    return out


def attach_user_to_company(cursor, user_id, company_id, *, force=False, fix_roles=True):
    from auth import get_company_by_id, get_user_by_id, _auth_cursor, _ph
    import json as _json
    company = get_company_by_id(company_id)
    if not company:
        raise ValueError(f'Empresa #{company_id} no existe')
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError('Usuario no encontrado')
    if user.get('company_id') == company_id:
        return {'ok': True, 'already': True, 'user_id': user_id, 'company_id': company_id}
    if user.get('company_id') and not force:
        raise ValueError(
            f'Usuario ya está en empresa #{user.get("company_id")}. '
            'Usá force=true para moverlo.'
        )
    roles = list(user.get('roles') or [])
    if fix_roles:
        if 'user' in roles and 'empresa' not in roles:
            roles = [r for r in roles if r != 'user']
        if 'empresa' not in roles:
            roles.append('empresa')
        if not any(r in roles for r in ('staff', 'helper', 'moderador', 'administrador')):
            if 'staff' not in roles:
                roles.append('staff')
    ph = _ph()
    with _auth_cursor() as ac:
        if not force:
            max_u = int(company.get('max_users') or 8)
            ac.execute(
                f'SELECT COUNT(*) FROM users WHERE company_id = {ph} AND is_active = TRUE',
                (company_id,),
            )
            row = ac.fetchone()
            cnt = row[0] if not hasattr(row, 'keys') else list(row.values())[0]
            if int(cnt or 0) >= max_u:
                raise ValueError(f'Empresa llena ({max_u} usuarios). Usá force=true como Super Admin.')
        ac.execute(
            f'UPDATE users SET company_id = {ph}, roles = {ph} WHERE id = {ph}',
            (company_id, _json.dumps(roles), user_id),
        )
    return {'ok': True, 'user_id': user_id, 'company_id': company_id, 'roles': roles}


def register_sa_imperial_routes(app, *, get_api_db_cursor, row_get, sa_required_fn, get_user_by_id_fn=None):
    """Registra rutas /aspers-sa/api/v2/*."""

    def _uid():
        return get_user_by_id_fn

    @app.route('/aspers-sa/api/v2/dashboard', methods=['GET'])
    @sa_required_fn
    def sa_v2_dashboard():
        return jsonify(imperial_dashboard_stats(get_api_db_cursor, row_get)), 200

    @app.route('/aspers-sa/api/v2/plans', methods=['GET', 'POST'])
    @sa_required_fn
    def sa_v2_plans():
        with get_api_db_cursor() as cur:
            if request.method == 'GET':
                return jsonify({'plans': get_plans_catalog(cur)}), 200
            data = request.get_json(silent=True) or {}
            plan = save_plan(cur, data)
            _log(cur, 'plan.save', detail=plan.get('id', ''), ip=request.remote_addr)
        return jsonify({'ok': True, 'plan': plan}), 200

    @app.route('/aspers-sa/api/v2/plans/<plan_id>/apply', methods=['POST'])
    @sa_required_fn
    def sa_v2_apply_plan(plan_id):
        from auth import create_company, update_company, create_user, hash_password
        data = request.get_json(silent=True) or {}
        with get_api_db_cursor() as cur:
            plans = {p['id']: p for p in get_plans_catalog(cur)}
        plan = plans.get(plan_id)
        if not plan:
            return jsonify({'error': 'Plan no encontrado'}), 404
        months = int(data.get('months') or plan.get('months') or 1)
        trial_days = int(plan.get('trial_days') or 0)
        if plan.get('type') == 'enterprise':
            name = (data.get('company_name') or plan.get('name') + ' — nueva').strip()
            end = None
            if trial_days:
                end = (datetime.now(timezone.utc) + timedelta(days=trial_days)).isoformat()
            elif months:
                end = (datetime.now(timezone.utc) + timedelta(days=months * 30)).isoformat()
            r = create_company(
                name=name,
                contact_email=data.get('email'),
                subscription_type='enterprise',
                subscription_status='active',
                subscription_price=float(plan.get('price') or 0),
                max_users=int(plan.get('max_users') or 8),
                max_admins=int(plan.get('max_admins') or 3),
                notes=f'Plan {plan_id}',
            )
            if not r.get('success'):
                return jsonify({'error': r.get('error')}), 400
            if end:
                update_company(company_id=r['company_id'], subscription_end_date=end)
            with get_api_db_cursor() as cur:
                _log(cur, 'plan.apply_enterprise', target_type='company', target_id=r['company_id'], detail=plan_id, ip=request.remote_addr)
            return jsonify({'ok': True, 'company_id': r['company_id'], 'plan': plan_id}), 201
        # individual gift / paid
        username = (data.get('username') or '').strip()
        if not username:
            return jsonify({'error': 'username requerido'}), 400
        pwd = (data.get('password') or '').strip() or secrets.token_urlsafe(10)
        r = create_user(
            username=username,
            password=pwd,
            email=data.get('email'),
            roles=plan.get('roles') or ['user'],
            company_id=None,
            created_by='imperial_plan',
        )
        if not r.get('success'):
            return jsonify({'error': r.get('error')}), 400
        with get_api_db_cursor() as cur:
            _log(cur, 'plan.apply_individual', target_type='user', target_id=r.get('user_id'), detail=plan_id, ip=request.remote_addr)
        return jsonify({
            'ok': True, 'user_id': r.get('user_id'), 'username': username,
            'temp_password': pwd if not data.get('password') else None, 'plan': plan_id,
        }), 201

    @app.route('/aspers-sa/api/v2/gift-user', methods=['POST'])
    @sa_required_fn
    def sa_v2_gift_user():
        from auth import create_user
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        if not username:
            return jsonify({'error': 'username requerido'}), 400
        pwd = secrets.token_urlsafe(10)
        r = create_user(
            username=username,
            password=pwd,
            email=data.get('email'),
            roles=data.get('roles') or ['user'],
            company_id=None,
            created_by='imperial_gift',
        )
        if not r.get('success'):
            return jsonify({'error': r.get('error')}), 400
        with get_api_db_cursor() as cur:
            _log(cur, 'gift.user', target_type='user', target_id=r.get('user_id'), detail=username, ip=request.remote_addr)
        return jsonify({
            'ok': True, 'user_id': r.get('user_id'), 'username': username, 'password': pwd,
            'message': 'Usuario regalo creado — entregá estas credenciales al destinatario.',
        }), 201

    @app.route('/aspers-sa/api/v2/tokens/individual', methods=['GET', 'POST'])
    @sa_required_fn
    def sa_v2_tokens_individual():
        from auth import create_registration_token, list_registration_tokens
        if request.method == 'GET':
            all_t = list_registration_tokens(include_used=True)
            ind = [t for t in all_t if not t.get('company_id')]
            unused = [t for t in ind if not t.get('is_used')]
            return jsonify({'tokens': ind, 'count': len(ind), 'unused': len(unused)}), 200
        data = request.get_json(silent=True) or {}
        count = max(1, min(50, int(data.get('count') or 1)))
        hours = max(1, min(8760, int(data.get('expires_hours') or 168)))
        label = (data.get('label') or 'Sorteo Imperial').strip()[:120]
        created = []
        base_url = request.url_root.rstrip('/')
        for i in range(count):
            desc = f'{label} #{i+1}/{count}'
            r = create_registration_token(
                created_by='imperial_sa',
                company_id=None,
                expires_hours=hours,
                description=desc,
                is_admin_token=False,
            )
            if r.get('success'):
                tok = r['token']
                created.append({
                    'token': tok,
                    'register_url': f'{base_url}/register?token={tok}',
                    'expires_at': str(r.get('expires_at') or ''),
                    'description': desc,
                })
        with get_api_db_cursor() as cur:
            ensure_imperial_tables(cur)
            try:
                cur.execute(
                    'INSERT INTO sa_gift_tokens_batch (batch_label, token_count, detail) VALUES (%s, %s, %s)',
                    (label, len(created), json.dumps({'hours': hours})[:500]),
                )
            except Exception:
                cur.execute(
                    'INSERT INTO sa_gift_tokens_batch (batch_label, token_count, detail) VALUES (?, ?, ?)',
                    (label, len(created), json.dumps({'hours': hours})[:500]),
                )
            _log(cur, 'tokens.individual_batch', detail=f'{label} x{len(created)}', ip=request.remote_addr)
        return jsonify({'ok': True, 'created': created, 'count': len(created), 'label': label}), 201

    @app.route('/aspers-sa/api/v2/tokens/company', methods=['POST'])
    @sa_required_fn
    def sa_v2_tokens_company():
        from auth import create_registration_token
        data = request.get_json(silent=True) or {}
        cid = data.get('company_id')
        if not cid:
            return jsonify({'error': 'company_id requerido'}), 400
        r = create_registration_token(
            created_by='imperial_sa',
            company_id=int(cid),
            expires_hours=int(data.get('expires_hours') or 72),
            description=(data.get('description') or 'Token SA')[:200],
            is_admin_token=bool(data.get('is_admin_token')),
        )
        if not r.get('success'):
            return jsonify({'error': r.get('error')}), 400
        base = request.url_root.rstrip('/')
        tok = r['token']
        with get_api_db_cursor() as cur:
            _log(cur, 'tokens.company', target_type='company', target_id=cid, ip=request.remote_addr)
        return jsonify({
            'ok': True, 'token': tok,
            'register_url': f'{base}/register?token={tok}',
        }), 201

    @app.route('/aspers-sa/api/v2/users/misassigned', methods=['GET'])
    @sa_required_fn
    def sa_v2_misassigned():
        from auth import list_companies
        mis_rows = []
        valid_ids = set()
        try:
            with get_api_db_cursor() as cur:
                cur.execute('SELECT id FROM companies')
                for r in cur.fetchall() or []:
                    valid_ids.add(row_get(r, 0, 'id'))
                cur.execute(
                    """
                    SELECT u.id, u.username, u.email, u.roles, u.is_active,
                           u.created_at, u.last_login, u.company_id
                    FROM users u
                    WHERE (
                        u.company_id IS NOT NULL
                        AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.id = u.company_id)
                    ) OR (
                        u.company_id IS NULL AND (
                            COALESCE(u.roles, '') LIKE '%empresa%'
                            OR COALESCE(u.roles, '') LIKE '%staff%'
                            OR COALESCE(u.roles, '') LIKE '%administrador%'
                            OR COALESCE(u.roles, '') LIKE '%helper%'
                            OR COALESCE(u.roles, '') LIKE '%moderador%'
                        )
                    )
                    ORDER BY u.created_at DESC
                    LIMIT 300
                    """
                )
                for row in cur.fetchall() or []:
                    if hasattr(row, 'keys'):
                        u = {
                            'id': row['id'], 'username': row['username'], 'email': row['email'],
                            'roles': _parse_roles(row['roles']),
                            'is_active': bool(row['is_active']),
                            'created_at': str(row['created_at']),
                            'last_login': str(row['last_login']) if row.get('last_login') else None,
                            'company_id': row['company_id'],
                        }
                    else:
                        u = {
                            'id': row[0], 'username': row[1], 'email': row[2],
                            'roles': _parse_roles(row[3]),
                            'is_active': bool(row[4]),
                            'created_at': str(row[5]),
                            'last_login': str(row[6]) if row[6] else None,
                            'company_id': row[7],
                        }
                    mis_rows.append(u)
        except Exception:
            from auth import list_users
            companies = list_companies() or []
            mis_rows = find_misassigned_users(list_users() or [], companies)
            return jsonify({
                'users': mis_rows,
                'count': len(mis_rows),
                'companies': [{'id': c['id'], 'name': c.get('name')} for c in companies],
            }), 200

        for u in mis_rows:
            roles = u.get('roles') or []
            cid = u.get('company_id')
            reasons = []
            if cid and cid not in valid_ids:
                reasons.append('company_id inválido')
            if any(r in roles for r in ('empresa', 'staff', 'administrador', 'helper', 'moderador')) and not cid:
                reasons.append('rol staff/empresa sin company_id')
            if 'empresa' in roles and not cid:
                reasons.append('rol empresa sin empresa')
            u['misassign_reasons'] = reasons or ['revisar asignación']

        cached_cos = _cache_get('companies_light')
        if cached_cos is not None:
            companies = cached_cos
        else:
            companies = list_companies() or []
            _cache_set('companies_light', companies)
        return jsonify({
            'users': mis_rows,
            'count': len(mis_rows),
            'companies': [{'id': c['id'], 'name': c.get('name')} for c in companies],
        }), 200

    @app.route('/aspers-sa/api/v2/users/<int:uid>/attach-company', methods=['POST'])
    @sa_required_fn
    def sa_v2_attach_company(uid):
        data = request.get_json(silent=True) or {}
        cid = data.get('company_id')
        if cid is None:
            return jsonify({'error': 'company_id requerido'}), 400
        force = bool(data.get('force', True))
        try:
            with get_api_db_cursor() as cur:
                r = attach_user_to_company(cur, uid, int(cid), force=force)
                _log(cur, 'user.attach_company', target_type='user', target_id=uid, detail=str(cid), ip=request.remote_addr)
            _cache_bust('dashboard', 'companies_light')
            return jsonify(r), 200
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/aspers-sa/api/v2/users/bulk-attach', methods=['POST'])
    @sa_required_fn
    def sa_v2_bulk_attach():
        data = request.get_json(silent=True) or {}
        ids = data.get('user_ids') or []
        cid = data.get('company_id')
        if not ids or cid is None:
            return jsonify({'error': 'user_ids y company_id requeridos'}), 400
        force = bool(data.get('force', True))
        ok, err = [], []
        with get_api_db_cursor() as cur:
            for uid in ids:
                try:
                    attach_user_to_company(cur, int(uid), int(cid), force=force)
                    ok.append(int(uid))
                except Exception as ex:
                    err.append({'user_id': uid, 'error': str(ex)})
            _log(cur, 'user.bulk_attach', detail=f'company={cid} ok={len(ok)}', ip=request.remote_addr)
        _cache_bust('dashboard', 'companies_light')
        return jsonify({'ok': True, 'attached': ok, 'errors': err}), 200

    @app.route('/aspers-sa/api/v2/users/<int:uid>/detach', methods=['POST'])
    @sa_required_fn
    def sa_v2_detach(uid):
        from auth import _auth_cursor, _ph
        import json as _json
        ph = _ph()
        with _auth_cursor() as ac:
            ac.execute(f'UPDATE users SET company_id = NULL WHERE id = {ph}', (uid,))
        with get_api_db_cursor() as cur:
            _log(cur, 'user.detach', target_type='user', target_id=uid, ip=request.remote_addr)
        return jsonify({'ok': True}), 200

    @app.route('/aspers-sa/api/v2/companies/<int:cid>/extend', methods=['POST'])
    @sa_required_fn
    def sa_v2_extend_company(cid):
        from auth import update_company, get_company_by_id
        if not get_company_by_id(cid):
            return jsonify({'error': 'Empresa no encontrada'}), 404
        data = request.get_json(silent=True) or {}
        days = int(data.get('days') or 30)
        months = int(data.get('months') or 0)
        delta = timedelta(days=days + months * 30)
        end = datetime.now(timezone.utc) + delta
        update_company(company_id=cid, subscription_end_date=end.isoformat(), subscription_status='active')
        with get_api_db_cursor() as cur:
            _log(cur, 'company.extend', target_type='company', target_id=cid, detail=f'+{days}d', ip=request.remote_addr)
        return jsonify({'ok': True, 'end_date': end.isoformat()}), 200

    @app.route('/aspers-sa/api/v2/companies/<int:cid>/apply-plan', methods=['POST'])
    @sa_required_fn
    def sa_v2_company_apply_plan(cid):
        from auth import update_company, get_company_by_id
        if not get_company_by_id(cid):
            return jsonify({'error': 'Empresa no encontrada'}), 404
        data = request.get_json(silent=True) or {}
        plan_id = data.get('plan_id')
        with get_api_db_cursor() as cur:
            plans = {p['id']: p for p in get_plans_catalog(cur)}
        plan = plans.get(plan_id)
        if not plan or plan.get('type') != 'enterprise':
            return jsonify({'error': 'Plan empresarial inválido'}), 400
        kwargs = {
            'subscription_price': float(plan.get('price') or 0),
            'max_users': int(plan.get('max_users') or 8),
            'max_admins': int(plan.get('max_admins') or 3),
            'subscription_status': 'active',
        }
        months = int(data.get('months') or plan.get('months') or 1)
        if months:
            kwargs['subscription_end_date'] = (datetime.now(timezone.utc) + timedelta(days=months * 30)).isoformat()
        update_company(company_id=cid, **kwargs)
        with get_api_db_cursor() as cur:
            _log(cur, 'company.apply_plan', target_type='company', target_id=cid, detail=plan_id, ip=request.remote_addr)
        return jsonify({'ok': True, 'plan': plan_id}), 200

    @app.route('/aspers-sa/api/v2/users/<int:uid>/reset-password', methods=['POST'])
    @sa_required_fn
    def sa_v2_reset_password(uid):
        from auth import hash_password, _auth_cursor, _ph
        pwd = secrets.token_urlsafe(10)
        ph = _ph()
        with _auth_cursor() as ac:
            ac.execute(f'UPDATE users SET password_hash = {ph} WHERE id = {ph}', (hash_password(pwd), uid))
        with get_api_db_cursor() as cur:
            _log(cur, 'user.reset_password', target_type='user', target_id=uid, ip=request.remote_addr)
        return jsonify({'ok': True, 'password': pwd}), 200

    @app.route('/aspers-sa/api/v2/companies/<int:cid>/clone-from', methods=['POST'])
    @sa_required_fn
    def sa_v2_clone_settings(cid):
        from auth import update_company, get_company_by_id
        data = request.get_json(silent=True) or {}
        src = int(data.get('source_company_id') or 0)
        src_c = get_company_by_id(src)
        tgt_c = get_company_by_id(cid)
        if not src_c or not tgt_c:
            return jsonify({'error': 'Empresa origen o destino no encontrada'}), 404
        update_company(
            company_id=cid,
            subscription_price=src_c.get('subscription_price'),
            max_users=src_c.get('max_users'),
            max_admins=src_c.get('max_admins'),
            subscription_status=src_c.get('subscription_status'),
        )
        with get_api_db_cursor() as cur:
            _log(cur, 'company.clone_settings', target_type='company', target_id=cid, detail=f'from={src}', ip=request.remote_addr)
        return jsonify({'ok': True}), 200

    @app.route('/aspers-sa/api/v2/revenue/summary', methods=['GET'])
    @sa_required_fn
    def sa_v2_revenue():
        from auth import list_companies
        companies = list_companies() or []
        paying = [c for c in companies if float(c.get('subscription_price') or 0) > 0 and (c.get('subscription_status') or '').lower() == 'active']
        free = len(companies) - len(paying)
        mrr = sum(float(c.get('subscription_price') or 0) for c in paying)
        by_tier = {}
        for c in paying:
            p = float(c.get('subscription_price') or 0)
            by_tier[p] = by_tier.get(p, 0) + 1
        return jsonify({
            'mrr': round(mrr, 2),
            'paying': len(paying),
            'free_active': free,
            'by_price': [{'price': k, 'count': v} for k, v in sorted(by_tier.items(), reverse=True)],
        }), 200

    @app.route('/aspers-sa/api/v2/companies/<int:cid>/suspend', methods=['POST'])
    @sa_required_fn
    def sa_v2_suspend_company(cid):
        from auth import update_company, get_company_by_id
        if not get_company_by_id(cid):
            return jsonify({'error': 'Empresa no encontrada'}), 404
        data = request.get_json(silent=True) or {}
        status = (data.get('status') or 'suspended').strip()
        update_company(company_id=cid, subscription_status=status)
        with get_api_db_cursor() as cur:
            _log(cur, 'company.suspend', target_type='company', target_id=cid, detail=status, ip=request.remote_addr)
        return jsonify({'ok': True, 'status': status}), 200

    @app.route('/aspers-sa/api/v2/tokens/individual/<token>/revoke', methods=['POST'])
    @sa_required_fn
    def sa_v2_revoke_token(token):
        from auth import _auth_cursor, _ph
        ph = _ph()
        with _auth_cursor() as ac:
            try:
                ac.execute(
                    f'UPDATE registration_tokens SET is_used = TRUE, used_at = NOW() WHERE token = {ph}',
                    (token,),
                )
            except Exception:
                ac.execute(
                    f"UPDATE registration_tokens SET is_used = 1, used_at = datetime('now') WHERE token = {ph}",
                    (token,),
                )
        with get_api_db_cursor() as cur:
            _log(cur, 'tokens.revoke', detail=token[:12], ip=request.remote_addr)
        return jsonify({'ok': True}), 200

    @app.route('/aspers-sa/api/v2/users/<int:uid>/promote-individual', methods=['POST'])
    @sa_required_fn
    def sa_v2_promote_to_enterprise(uid):
        """Convierte usuario individual en admin de empresa nueva o existente."""
        from auth import create_company, get_user_by_id
        data = request.get_json(silent=True) or {}
        user = get_user_by_id(uid)
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        cid = data.get('company_id')
        if cid:
            with get_api_db_cursor() as cur:
                r = attach_user_to_company(cur, uid, int(cid), force=True)
                _log(cur, 'user.promote_existing', target_type='user', target_id=uid, detail=str(cid), ip=request.remote_addr)
            return jsonify(r), 200
        name = (data.get('company_name') or user.get('username') + ' Corp').strip()
        r = create_company(
            name=name,
            contact_email=user.get('email'),
            subscription_type='enterprise',
            subscription_status='active',
            subscription_price=float(data.get('price') or 13),
            max_users=int(data.get('max_users') or 8),
            max_admins=int(data.get('max_admins') or 3),
            notes=f'Promovido desde user #{uid}',
        )
        if not r.get('success'):
            return jsonify({'error': r.get('error')}), 400
        with get_api_db_cursor() as cur:
            attach_user_to_company(cur, uid, r['company_id'], force=True)
            _log(cur, 'user.promote_new_company', target_type='user', target_id=uid, detail=str(r['company_id']), ip=request.remote_addr)
        return jsonify({'ok': True, 'company_id': r['company_id']}), 201

    @app.route('/aspers-sa/api/v2/plans/<plan_id>/duplicate', methods=['POST'])
    @sa_required_fn
    def sa_v2_duplicate_plan(plan_id):
        with get_api_db_cursor() as cur:
            plans = {p['id']: p for p in get_plans_catalog(cur)}
        src = plans.get(plan_id)
        if not src:
            return jsonify({'error': 'Plan no encontrado'}), 404
        data = request.get_json(silent=True) or {}
        new_id = (data.get('id') or (plan_id + '_copy')).strip()[:48]
        copy = dict(src)
        copy['id'] = new_id
        copy['name'] = data.get('name') or (src.get('name') + ' (copia)')
        if data.get('price') is not None:
            copy['price'] = float(data['price'])
        plan = save_plan(cur, copy)
        _log(cur, 'plan.duplicate', detail=f'{plan_id}->{new_id}', ip=request.remote_addr)
        return jsonify({'ok': True, 'plan': plan}), 201

    @app.route('/aspers-sa/api/v2/users/directory', methods=['GET'])
    @sa_required_fn
    def sa_v2_users_directory():
        """Listado global con filtros en SQL (sin cargar todos los usuarios)."""
        from auth import _ph
        q = (request.args.get('q') or '').strip().lower()
        tipo = (request.args.get('type') or 'all').strip().lower()
        ph = _ph()
        rows = []
        try:
            with get_api_db_cursor() as cur:
                sql = (
                    f'SELECT u.id, u.username, u.email, u.roles, u.is_active, u.company_id, '
                    f'u.created_at, c.name AS company_name FROM users u '
                    f'LEFT JOIN companies c ON c.id = u.company_id WHERE 1=1'
                )
                params = []
                if tipo == 'individual':
                    sql += ' AND u.company_id IS NULL'
                elif tipo == 'empresa':
                    sql += ' AND u.company_id IS NOT NULL'
                if q:
                    like = f'%{q}%'
                    sql += (
                        f' AND (LOWER(u.username) LIKE LOWER({ph})'
                        f' OR LOWER(COALESCE(u.email, \'\')) LIKE LOWER({ph})'
                        f' OR CAST(u.id AS TEXT) = {ph}'
                        f' OR LOWER(COALESCE(c.name, \'\')) LIKE LOWER({ph}))'
                    )
                    params.extend([like, like, q, like])
                sql += ' ORDER BY u.created_at DESC LIMIT 400'
                cur.execute(sql, tuple(params))
                for row in cur.fetchall() or []:
                    if hasattr(row, 'keys'):
                        cid = row['company_id']
                        rows.append({
                            'id': row['id'],
                            'username': row['username'],
                            'email': row['email'],
                            'roles': _parse_roles(row['roles']),
                            'is_active': bool(row['is_active']),
                            'company_id': cid,
                            'company_name': row.get('company_name'),
                            'segment': 'individual' if not cid else 'empresa',
                            'created_at': str(row['created_at'] or '')[:10],
                        })
                    else:
                        cid = row[5]
                        rows.append({
                            'id': row[0], 'username': row[1], 'email': row[2],
                            'roles': _parse_roles(row[3]),
                            'is_active': bool(row[4]),
                            'company_id': cid,
                            'company_name': row[7],
                            'segment': 'individual' if not cid else 'empresa',
                            'created_at': str(row[6] or '')[:10],
                        })
        except Exception:
            from auth import list_users, list_companies
            companies = list_companies() or []
            cmap = {c.get('id'): c for c in companies}
            for u in list_users() or []:
                cid = u.get('company_id')
                is_individual = not cid
                if tipo == 'individual' and not is_individual:
                    continue
                if tipo == 'empresa' and is_individual:
                    continue
                un = (u.get('username') or '').lower()
                em = (u.get('email') or '').lower()
                if q and q not in un and q not in em and q != str(u.get('id', '')):
                    co = cmap.get(cid) or {}
                    if q not in (co.get('name') or '').lower():
                        continue
                co = cmap.get(cid) if cid else None
                rows.append({
                    'id': u.get('id'),
                    'username': u.get('username'),
                    'email': u.get('email'),
                    'roles': u.get('roles') or [],
                    'is_active': u.get('is_active', True),
                    'company_id': cid,
                    'company_name': co.get('name') if co else None,
                    'segment': 'individual' if is_individual else 'empresa',
                    'created_at': str(u.get('created_at') or '')[:10],
                })
        ind = sum(1 for r in rows if r['segment'] == 'individual')
        emp = sum(1 for r in rows if r['segment'] == 'empresa')
        return jsonify({
            'users': rows,
            'count': len(rows),
            'individuals': ind,
            'enterprise_users': emp,
        }), 200

    @app.route('/aspers-sa/api/v2/revenue/detailed', methods=['GET'])
    @sa_required_fn
    def sa_v2_revenue_detailed():
        from auth import list_companies
        companies = _cache_get('companies_light')
        if companies is None:
            companies = list_companies() or []
            _cache_set('companies_light', companies)
        paying = []
        free_co = []
        for c in companies:
            price = float(c.get('subscription_price') or 0)
            st = (c.get('subscription_status') or '').lower()
            entry = {
                'id': c.get('id'),
                'name': c.get('name'),
                'price': price,
                'status': st,
                'users': c.get('current_users') or 0,
                'max_users': c.get('max_users') or 8,
                'end_date': str(c.get('subscription_end_date') or '')[:10],
            }
            if st == 'active' and price > 0:
                paying.append(entry)
            elif st == 'active':
                free_co.append(entry)
        mrr = sum(p['price'] for p in paying)
        individuals_total = 0
        individuals_active = 0
        try:
            with get_api_db_cursor() as cur:
                individuals_total = int(_scalar(
                    cur, 'SELECT COUNT(*) FROM users WHERE company_id IS NULL', row_get=row_get,
                ))
                individuals_active = int(_scalar(
                    cur,
                    'SELECT COUNT(*) FROM users WHERE company_id IS NULL AND is_active = TRUE',
                    row_get=row_get,
                ))
        except Exception:
            pass
        by_price = {}
        for p in paying:
            by_price[p['price']] = by_price.get(p['price'], 0) + 1
        return jsonify({
            'mrr': round(mrr, 2),
            'paying': len(paying),
            'free_active': len(free_co),
            'individuals_total': individuals_total,
            'individuals_active': individuals_active,
            'by_price': [{'price': k, 'count': v} for k, v in sorted(by_price.items(), reverse=True)],
            'companies_paying': sorted(paying, key=lambda x: -x['price']),
            'companies_free': free_co[:20],
        }), 200

    @app.route('/aspers-sa/api/v2/companies', methods=['GET'])
    @sa_required_fn
    def sa_v2_companies():
        from auth import list_companies
        companies = _cache_get('companies_light')
        if companies is None:
            companies = list_companies() or []
            _cache_set('companies_light', companies)
        for c in companies:
            if c.get('subscription_price') is not None:
                try:
                    c['subscription_price'] = float(c['subscription_price'])
                except Exception:
                    c['subscription_price'] = 0.0
        return jsonify({'companies': companies, 'count': len(companies)}), 200

    @app.route('/aspers-sa/api/v2/quick-search', methods=['GET'])
    @sa_required_fn
    def sa_v2_search():
        from auth import _ph
        q = (request.args.get('q') or '').strip().lower()
        if len(q) < 2:
            return jsonify({'results': []}), 200
        ph = _ph()
        like = f'%{q}%'
        results = []
        try:
            with get_api_db_cursor() as cur:
                cur.execute(
                    f'SELECT id, name FROM companies WHERE LOWER(name) LIKE LOWER({ph}) ORDER BY name LIMIT 8',
                    (like,),
                )
                for row in cur.fetchall() or []:
                    cid = row_get(row, 0, 'id')
                    name = row_get(row, 1, 'name')
                    results.append({'type': 'company', 'id': cid, 'label': name, 'view': 'cartera'})
                cur.execute(
                    f'SELECT id, username, email, company_id FROM users WHERE '
                    f'LOWER(username) LIKE LOWER({ph}) OR LOWER(COALESCE(email, \'\')) LIKE LOWER({ph}) '
                    f'OR CAST(id AS TEXT) = {ph} ORDER BY username LIMIT 12',
                    (like, like, q),
                )
                for row in cur.fetchall() or []:
                    uid = row_get(row, 0, 'id')
                    uname = row_get(row, 1, 'username')
                    email = row_get(row, 2, 'email')
                    coid = row_get(row, 3, 'company_id')
                    results.append({
                        'type': 'user',
                        'id': uid,
                        'label': uname,
                        'sub': email or ('empresa #' + str(coid) if coid else 'individual'),
                        'view': 'migraciones' if not coid else 'cartera',
                    })
        except Exception:
            from auth import list_users, list_companies
            for c in list_companies() or []:
                if q in (c.get('name') or '').lower():
                    results.append({'type': 'company', 'id': c['id'], 'label': c.get('name'), 'view': 'cartera'})
            for u in list_users() or []:
                un = (u.get('username') or '').lower()
                em = (u.get('email') or '').lower()
                if q in un or q in em or q == str(u.get('id', '')):
                    results.append({
                        'type': 'user',
                        'id': u['id'],
                        'label': u.get('username'),
                        'sub': u.get('email') or ('empresa #' + str(u.get('company_id')) if u.get('company_id') else 'individual'),
                        'view': 'migraciones' if not u.get('company_id') else 'cartera',
                    })
        return jsonify({'results': results[:25]}), 200
