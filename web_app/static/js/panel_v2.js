/* Argus Panel v2 — router + secciones.
 * Consume las APIs existentes del panel. El backend no cambia. */
(function () {
  'use strict';

  var view = document.getElementById('view');
  var titleEl = document.getElementById('view-title');
  var subEl = document.getElementById('view-sub');
  var CFG = window.ARGUS_V2 || {};

  /* ---- helpers -------------------------------------------------------- */
  function $(s, r) { return (r || document).querySelector(s); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(n) { return n == null || n === '' ? '–' : Number(n).toLocaleString('es'); }
  function fmtDate(s) {
    if (!s) return '–';
    var d = new Date(String(s).replace(' ', 'T'));
    return isNaN(d) ? esc(s) : d.toLocaleString('es', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  }
  function ago(s) {
    if (!s) return '';
    var d = new Date(String(s).replace(' ', 'T')); if (isNaN(d)) return '';
    var m = Math.floor((Date.now() - d) / 60000);
    if (m < 1) return 'ahora'; if (m < 60) return 'hace ' + m + ' min';
    var h = Math.floor(m / 60); if (h < 24) return 'hace ' + h + ' h';
    return 'hace ' + Math.floor(h / 24) + ' d';
  }
  function skel() { return '<div class="skeleton"><div class="bar"></div><div class="bar"></div><div class="bar"></div></div>'; }
  function emptyBox(txt, icon) { return '<div class="empty"><div class="big">' + (icon || '∅') + '</div>' + esc(txt || 'Sin datos.') + '</div>'; }
  function toast(msg, isErr) {
    var t = document.createElement('div');
    t.className = 'toast' + (isErr ? ' err' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; }, 2600);
    setTimeout(function () { t.remove(); }, 3000);
  }

  var CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';
  async function api(path, opts) {
    opts = opts || {};
    var headers = Object.assign({ 'Accept': 'application/json', 'Content-Type': 'application/json' }, opts.headers || {});
    if (CSRF && opts.method && /^(POST|PUT|PATCH|DELETE)$/i.test(opts.method)) headers['X-CSRFToken'] = CSRF;
    var r = await fetch(path, Object.assign({ credentials: 'same-origin' }, opts, { headers: headers }));
    if (r.status === 401 || r.redirected && /\/login/.test(r.url)) { location.href = '/login'; throw new Error('401'); }
    var ct = r.headers.get('content-type') || '';
    var data = ct.indexOf('json') >= 0 ? await r.json() : await r.text();
    if (!r.ok) throw new Error((data && data.error) || ('HTTP ' + r.status));
    return data;
  }

  function verdictBadge(v, risk) {
    v = String(v || '').toLowerCase();
    if (v === 'hack' || v === 'ban') return '<span class="badge crit">HACK</span>';
    if (v === 'suspicious' || v === 'sospechoso') return '<span class="badge susp">SOSPECHOSO</span>';
    if (v === 'clean' || v === 'limpio' || v === 'legit') return '<span class="badge clean">LIMPIO</span>';
    if (risk != null && risk !== '') {
      if (risk >= 70) return '<span class="badge crit">RIESGO ' + risk + '</span>';
      if (risk >= 30) return '<span class="badge susp">RIESGO ' + risk + '</span>';
      return '<span class="badge clean">RIESGO ' + risk + '</span>';
    }
    return '<span class="badge pend">PENDIENTE</span>';
  }
  function alertBadge(lvl) {
    lvl = String(lvl || '').toUpperCase();
    if (lvl === 'CRITICAL') return '<span class="badge crit">CRÍTICO</span>';
    if (lvl === 'SUSPICIOUS' || lvl === 'SOSPECHOSO' || lvl === 'HACKS') return '<span class="badge susp">SOSPECHOSO</span>';
    if (lvl === 'POCO_SOSPECHOSO' || lvl === 'LOW') return '<span class="badge plain pend">BAJO</span>';
    return '<span class="badge plain pend">' + esc(lvl || 'INFO') + '</span>';
  }

  function scanTable(rows, opts) {
    opts = opts || {};
    if (!rows || !rows.length) return emptyBox('Sin escaneos.', '≣');
    return '<div class="table-wrap"><table class="tbl"><thead><tr>' +
      '<th>Máquina</th><th>Usuario MC</th><th>Veredicto</th><th>Hallazgos</th>' +
      (opts.dur ? '<th>Duración</th>' : '') + '<th>Fecha</th></tr></thead><tbody>' +
      rows.map(function (s) {
        return '<tr data-scan="' + esc(s.id) + '">' +
          '<td class="strong">' + esc(s.machine_name || s.machine_id || '–') + '</td>' +
          '<td>' + esc(s.minecraft_username || s.mc_username || '–') + '</td>' +
          '<td>' + verdictBadge(s.verdict, s.risk_score) + '</td>' +
          '<td>' + num(s.issues_found) + '</td>' +
          (opts.dur ? '<td class="muted">' + (s.scan_duration ? Math.round(s.scan_duration) + 's' : '–') + '</td>' : '') +
          '<td class="muted" title="' + esc(fmtDate(s.started_at || s.created_at)) + '">' + esc(ago(s.started_at || s.created_at) || fmtDate(s.started_at)) + '</td>' +
        '</tr>';
      }).join('') + '</tbody></table></div>';
  }

  /* ================================================================== *
   *  INICIO
   * ================================================================== */
  async function renderInicio() {
    titleEl.textContent = 'Inicio'; subEl.textContent = 'resumen operativo';
    view.innerHTML = '<div class="kpi-grid">' + Array(6).fill('<div class="kpi">' + skel() + '</div>').join('') + '</div>';
    var st = {}, ext = {};
    try { st = await api('/api/statistics'); } catch (e) {}
    try { ext = await api('/api/dashboard/extended'); } catch (e) {}

    var v = ext.verdicts || {};
    var kpis = [
      ['Escaneos totales', num(st.total_scans), 'good', ''],
      ['En curso ahora', num(st.active_scans), '', ''],
      ['Detecciones críticas', num(st.severe_detections), 'alert', ''],
      ['Máquinas únicas', num(st.unique_machines), '', ''],
      ['Veredictos hack', num(v.hack), 'alert', num(v.pending) + ' sin revisar'],
      ['Baneos registrados', num(st.total_bans), '', ext.avg_duration ? 'scan ~' + Math.round(ext.avg_duration) + 's' : '']
    ];
    view.innerHTML =
      '<div class="kpi-grid">' + kpis.map(function (k) {
        return '<div class="kpi ' + k[2] + '"><div class="k-label">' + k[0] + '</div>' +
          '<div class="k-value">' + k[1] + '</div>' +
          (k[3] ? '<div class="k-sub">' + k[3] + '</div>' : '') + '</div>';
      }).join('') + '</div>' +
      (Array.isArray(ext.top_issues) && ext.top_issues.length ?
        '<div class="panel-card"><header>Hacks más vistos</header><div class="body pad">' +
        ext.top_issues.map(function (t) {
          return '<div class="row" style="justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-soft)">' +
            '<span>' + esc(t.name) + '</span><span class="mono muted">' + num(t.count) + '</span></div>';
        }).join('') + '</div></div>' : '') +
      '<div class="panel-card"><header>Escaneos recientes <span class="grow"></span>' +
        '<a class="btn sm" href="#/revision">Ver todos →</a></header>' +
        '<div class="body" id="recent">' + skel() + '</div></div>';

    try {
      var d = await api('/api/scans?limit=8');
      $('#recent').innerHTML = scanTable(d.scans || d.results || d || []);
    } catch (e) { $('#recent').innerHTML = emptyBox('No se pudo cargar.', '⚠'); }
  }

  /* ================================================================== *
   *  REVISIÓN — lista + detalle
   * ================================================================== */
  var rev = { search: '', verdict: '', limit: 40, offset: 0 };

  async function renderRevision() {
    titleEl.textContent = 'Revisión'; subEl.textContent = 'escaneos y veredictos';
    view.innerHTML =
      '<div class="toolbar">' +
        '<input class="input" id="rv-q" placeholder="Buscar máquina, usuario o IP…" value="' + esc(rev.search) + '" style="min-width:280px">' +
        '<select class="select" id="rv-v">' +
          ['', 'hack', 'suspicious', 'clean', 'pending'].map(function (o) {
            return '<option value="' + o + '"' + (o === rev.verdict ? ' selected' : '') + '>' +
              ({ '': 'Todos los veredictos', hack: 'Hack', suspicious: 'Sospechoso', clean: 'Limpio', pending: 'Pendiente' })[o] + '</option>';
          }).join('') +
        '</select>' +
        '<button class="btn primary" id="rv-go">Filtrar</button>' +
        '<span class="grow"></span>' +
        '<button class="btn sm" id="rv-prev">←</button><button class="btn sm" id="rv-next">→</button>' +
      '</div>' +
      '<div class="panel-card"><div class="body" id="rv-body">' + skel() + '</div></div>';
    $('#rv-go').onclick = function () {
      rev.search = $('#rv-q').value.trim(); rev.verdict = $('#rv-v').value; rev.offset = 0; loadRevision();
    };
    $('#rv-q').addEventListener('keydown', function (e) { if (e.key === 'Enter') $('#rv-go').click(); });
    $('#rv-prev').onclick = function () { rev.offset = Math.max(0, rev.offset - rev.limit); loadRevision(); };
    $('#rv-next').onclick = function () { rev.offset += rev.limit; loadRevision(); };
    loadRevision();
  }
  async function loadRevision() {
    var q = new URLSearchParams({ limit: rev.limit, offset: rev.offset });
    if (rev.search) q.set('search', rev.search);
    if (rev.verdict) q.set('verdict', rev.verdict);
    $('#rv-body').innerHTML = skel();
    try {
      var d = await api('/api/scans?' + q);
      $('#rv-body').innerHTML = scanTable(d.scans || d.results || d || [], { dur: true });
    } catch (e) { $('#rv-body').innerHTML = emptyBox('Error: ' + e.message, '⚠'); }
  }

  async function renderScan(id) {
    titleEl.textContent = 'Scan #' + id; subEl.textContent = '';
    view.innerHTML = '<a class="btn sm ghost" href="#/revision">← volver</a><div class="panel-card" style="margin-top:14px"><div class="body pad">' + skel() + '</div></div>';
    var s;
    try { s = await api('/api/scans/' + id); }
    catch (e) { view.innerHTML = emptyBox('No se pudo cargar el scan: ' + e.message, '⚠'); return; }

    var results = s.results || s.issues || [];
    var meta = [
      ['Usuario MC', s.minecraft_username], ['Máquina', s.machine_name],
      ['IP', s.ip_address], ['País', s.country], ['SO', s.os_name || s.os],
      ['Archivos escaneados', num(s.total_files_scanned)],
      ['Duración', s.scan_duration ? Math.round(s.scan_duration) + 's' : '–'],
      ['Inicio', fmtDate(s.started_at)]
    ];
    view.innerHTML =
      '<a class="btn sm ghost" href="#/revision">← volver a Revisión</a>' +
      '<div class="row" style="margin:16px 0 20px;gap:14px">' +
        '<h1 style="font-size:24px">' + esc(s.machine_name || ('Scan #' + id)) + '</h1>' +
        verdictBadge(s.verdict, s.risk_score) +
      '</div>' +
      '<div class="grid-2">' +
        '<div class="panel-card"><header>Detalle</header><div class="body pad"><div class="stack">' +
          meta.map(function (m) {
            return '<div class="row" style="justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border-soft)">' +
              '<span class="muted">' + m[0] + '</span><span>' + esc(m[1] == null || m[1] === '' ? '–' : m[1]) + '</span></div>';
          }).join('') +
        '</div></div></div>' +
        '<div class="panel-card"><header>Veredicto' +
          (s.verdict ? ' <span class="grow"></span>' + verdictBadge(s.verdict, s.risk_score) : '') +
          '</header><div class="body pad">' +
          '<div class="stack" style="gap:10px">' +
            '<textarea class="input" id="vd-reason" rows="2" placeholder="Motivo (opcional)">' + esc(s.verdict_reason || '') + '</textarea>' +
            '<div class="row" style="gap:8px;flex-wrap:wrap">' +
              ['hack', 'clean', 'pending'].map(function (vv) {
                return '<button class="btn sm vd" data-v="' + vv + '">' +
                  ({ hack: '⛔ Hack', clean: '✔ Limpio', pending: '↺ Pendiente' })[vv] + '</button>';
              }).join('') +
            '</div>' +
            '<div id="vd-status" class="muted" style="font-size:13px"></div>' +
          '</div>' +
        '</div></div>' +
      '</div>' +
      '<div class="panel-card"><header>Hallazgos <span class="grow"></span><span class="muted">' + results.length + '</span></header>' +
        '<div class="body">' + (results.length ?
          '<div class="table-wrap"><table class="tbl"><thead><tr><th>Nivel</th><th>Hallazgo</th><th>Ruta</th><th>Conf.</th><th>Patrones</th></tr></thead><tbody>' +
          results.map(function (r) {
            return '<tr style="cursor:default">' +
              '<td>' + alertBadge(r.alert_level) + '</td>' +
              '<td class="strong">' + esc(r.issue_name || r.name || '–') + '</td>' +
              '<td class="muted mono" style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(r.issue_path || '') + '</td>' +
              '<td>' + (r.confidence != null ? Math.round(r.confidence * (r.confidence <= 1 ? 100 : 1)) + '%' : '–') + '</td>' +
              '<td class="muted">' + esc((r.detected_patterns || []).join(', ')) + '</td>' +
            '</tr>';
          }).join('') + '</tbody></table></div>' : emptyBox('Sin hallazgos — scan limpio.', '✔')) +
        '</div></div>' +
      '<div class="panel-card"><header>Notas del staff</header><div class="body pad" id="notes">' + skel() + '</div></div>';

    // veredicto
    view.querySelectorAll('.vd').forEach(function (b) {
      b.onclick = async function () {
        var vv = b.dataset.v;
        var reason = $('#vd-reason').value.trim();
        $('#vd-status').textContent = 'Guardando…';
        try {
          await api('/api/scans/' + id + '/verdict', {
            method: 'POST',
            body: JSON.stringify({ verdict: vv, reason: reason })
          });
          toast('Veredicto guardado: ' + vv);
          $('#vd-status').innerHTML = 'Guardado ' + verdictBadge(vv) + ' · ' + esc(reason);
          var hdr = view.querySelector('.grid-2 .panel-card header');
          if (hdr && !hdr.querySelector('.badge')) hdr.insertAdjacentHTML('beforeend', '<span class="grow"></span>' + verdictBadge(vv));
        } catch (e) { $('#vd-status').textContent = 'Error: ' + e.message; toast('No se pudo guardar', true); }
      };
    });
    // notas
    try {
      var nd = await api('/api/scans/' + id + '/notes');
      var notes = nd.notes || [];
      $('#notes').innerHTML = (notes.length ? notes.map(function (n) {
        return '<div style="padding:8px 0;border-bottom:1px solid var(--border-soft)">' +
          '<div class="muted" style="font-size:12.5px">' + esc(n.author || '?') + ' · ' + fmtDate(n.created_at) + '</div>' +
          '<div>' + esc(n.body) + '</div></div>';
      }).join('') : '<div class="muted" style="font-size:13px;margin-bottom:10px">Sin notas.</div>') +
        '<div class="row" style="margin-top:12px"><input class="input" id="note-in" placeholder="Agregar nota…" style="flex:1">' +
        '<button class="btn primary sm" id="note-add">Agregar</button></div>';
      var add = $('#note-add');
      if (add) add.onclick = async function () {
        var body = $('#note-in').value.trim(); if (!body) return;
        try {
          await api('/api/scans/' + id + '/notes', { method: 'POST', body: JSON.stringify({ body: body }) });
          renderScan(id);
        } catch (e) { toast('No se pudo agregar la nota', true); }
      };
    } catch (e) { $('#notes').innerHTML = emptyBox('Notas no disponibles.'); }
  }

  /* ================================================================== *
   *  SERVIDORES — tokens de escaneo (SS) + versión del scanner
   * ================================================================== */
  async function renderServidores() {
    titleEl.textContent = 'Servidores'; subEl.textContent = 'tokens de Screen Share';
    view.innerHTML =
      '<div class="toolbar">' +
        '<button class="btn primary" id="sv-new">+ Generar token SS</button>' +
        '<span class="grow"></span>' +
        '<span class="pill" id="sv-ver">scanner …</span>' +
      '</div>' +
      '<div id="sv-fresh"></div>' +
      '<div class="panel-card"><header>Tokens activos <span class="grow"></span>' +
        '<button class="btn sm" id="sv-reload">↻</button></header>' +
        '<div class="body" id="sv-body">' + skel() + '</div></div>';
    $('#sv-reload').onclick = loadServidores;
    $('#sv-new').onclick = async function () {
      $('#sv-new').disabled = true; $('#sv-new').textContent = 'Generando…';
      try {
        var r = await api('/api/tokens', { method: 'POST' });
        $('#sv-fresh').innerHTML =
          '<div class="panel-card" style="border-color:var(--accent)"><div class="body pad">' +
            '<div class="muted" style="font-size:12.5px">Nuevo token · dáselo al jugador · expira en 30 min</div>' +
            '<div class="row" style="gap:14px;margin-top:8px;align-items:baseline">' +
              '<span style="font-size:28px;font-weight:700;letter-spacing:.15em" class="mono">' + esc(r.short_code || '——') + '</span>' +
              '<span class="muted mono" style="font-size:12px">' + esc(r.token || '') + '</span>' +
            '</div></div></div>';
        toast('Token generado: ' + (r.short_code || ''));
        loadServidores();
      } catch (e) { toast('No se pudo generar: ' + e.message, true); }
      $('#sv-new').disabled = false; $('#sv-new').textContent = '+ Generar token SS';
    };
    try { var v = await api('/api/scanner/version'); $('#sv-ver').textContent = 'scanner ' + (v.version || v.latest || CFG.scannerVersion || '?'); } catch (e) {}
    loadServidores();
  }
  async function loadServidores() {
    $('#sv-body').innerHTML = skel();
    try {
      var d = await api('/api/tokens');
      var rows = (d.tokens || []).filter(function (t) { return t.is_active; });
      if (!rows.length) { $('#sv-body').innerHTML = emptyBox('Sin tokens activos. Generá uno arriba.', '⬡'); return; }
      $('#sv-body').innerHTML = '<div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>Código</th><th>Token</th><th>Usos</th><th>Creado por</th><th>Expira</th><th></th></tr></thead><tbody>' +
        rows.map(function (t) {
          return '<tr style="cursor:default">' +
            '<td class="strong mono">' + esc(t.short_code || '—') + '</td>' +
            '<td class="muted mono" style="max-width:220px;overflow:hidden;text-overflow:ellipsis">' + esc(t.token) + '</td>' +
            '<td>' + esc(t.used_count || 0) + '/' + (t.max_uses === -1 ? '∞' : esc(t.max_uses)) + '</td>' +
            '<td class="muted">' + esc(t.created_by || '—') + '</td>' +
            '<td class="muted">' + esc(fmtDate(t.expires_at)) + '</td>' +
            '<td><button class="btn sm danger" data-deltoken="' + esc(t.id) + '">borrar</button></td>' +
          '</tr>';
        }).join('') + '</tbody></table></div>';
      $('#sv-body').querySelectorAll('[data-deltoken]').forEach(function (b) {
        b.onclick = async function () {
          try { await api('/api/tokens/' + b.dataset.deltoken, { method: 'DELETE' }); toast('Token borrado'); loadServidores(); }
          catch (e) { toast('No se pudo borrar: ' + e.message, true); }
        };
      });
    } catch (e) { $('#sv-body').innerHTML = emptyBox('Error: ' + e.message, '⚠'); }
  }

  /* ================================================================== *
   *  EQUIPO — staff + invitaciones
   * ================================================================== */
  async function renderEquipo() {
    titleEl.textContent = 'Equipo'; subEl.textContent = 'staff y accesos';
    view.innerHTML =
      '<div class="panel-card"><header>Staff <span class="grow"></span>' +
        '<button class="btn sm" id="eq-ureload">↻</button></header>' +
        '<div class="body" id="eq-users">' + skel() + '</div></div>' +
      '<div class="panel-card"><header>Invitaciones (tokens de registro) <span class="grow"></span>' +
        '<button class="btn primary sm" id="eq-invite">+ Nueva invitación</button></header>' +
        '<div class="body pad" id="eq-inv-form" hidden>' +
          '<div class="row" style="gap:9px;flex-wrap:wrap">' +
            '<input class="input" id="eq-desc" placeholder="Para quién / nota" style="flex:1;min-width:200px">' +
            '<select class="select" id="eq-hours"><option value="24">24 h</option><option value="72">3 días</option><option value="168">7 días</option></select>' +
            '<label class="row muted" style="font-size:13px;gap:6px"><input type="checkbox" id="eq-admin"> admin</label>' +
            '<button class="btn primary" id="eq-inv-go">Crear</button>' +
          '</div>' +
        '</div>' +
        '<div class="body" id="eq-inv">' + skel() + '</div></div>';
    $('#eq-ureload').onclick = loadEquipoUsers;
    $('#eq-invite').onclick = function () { $('#eq-inv-form').hidden = !$('#eq-inv-form').hidden; };
    $('#eq-inv-go').onclick = async function () {
      try {
        var r = await api('/api/company/registration-tokens', {
          method: 'POST',
          body: JSON.stringify({
            description: $('#eq-desc').value.trim(),
            expires_hours: parseInt($('#eq-hours').value, 10),
            is_admin_token: $('#eq-admin').checked
          })
        });
        toast('Invitación creada');
        $('#eq-desc').value = ''; $('#eq-inv-form').hidden = true;
        loadEquipoInv();
      } catch (e) { toast('No se pudo crear: ' + e.message, true); }
    };
    loadEquipoUsers();
    loadEquipoInv();
  }
  async function loadEquipoUsers() {
    $('#eq-users').innerHTML = skel();
    try {
      var d = await api('/api/company/users');
      var rows = d.users || [];
      if (!rows.length) { $('#eq-users').innerHTML = emptyBox('Sin usuarios.', '◔'); return; }
      $('#eq-users').innerHTML = '<div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>Usuario</th><th>Roles</th><th>Estado</th><th>Último acceso</th><th></th></tr></thead><tbody>' +
        rows.map(function (u) {
          var roles = Array.isArray(u.roles) ? u.roles.join(', ') : esc(u.roles || u.role || '');
          var active = u.is_active !== false && u.is_active !== 0;
          return '<tr style="cursor:default">' +
            '<td class="strong">' + esc(u.username) + '</td>' +
            '<td class="muted">' + esc(roles) + '</td>' +
            '<td>' + (active ? '<span class="badge clean plain">activo</span>' : '<span class="badge pend plain">inactivo</span>') + '</td>' +
            '<td class="muted">' + esc(fmtDate(u.last_login)) + '</td>' +
            '<td class="row" style="gap:6px">' +
              (active
                ? '<button class="btn sm" data-deact="' + esc(u.id) + '">desactivar</button>'
                : '<button class="btn sm" data-act="' + esc(u.id) + '">activar</button>') +
              '<button class="btn sm danger" data-deluser="' + esc(u.id) + '">×</button>' +
            '</td></tr>';
        }).join('') + '</tbody></table></div>';
      var wire = function (sel, path, method, msg) {
        $('#eq-users').querySelectorAll(sel).forEach(function (b) {
          b.onclick = async function () {
            var id = b.getAttribute(sel.replace(/[[\]]/g, ''));
            if (sel.indexOf('deluser') >= 0 && !confirm('¿Eliminar este usuario?')) return;
            try { await api(path.replace('{id}', id), { method: method }); toast(msg); loadEquipoUsers(); }
            catch (e) { toast('Error: ' + e.message, true); }
          };
        });
      };
      wire('[data-deact]', '/api/company/users/{id}/deactivate', 'POST', 'Usuario desactivado');
      wire('[data-act]', '/api/company/users/{id}/activate', 'POST', 'Usuario activado');
      wire('[data-deluser]', '/api/company/users/{id}/delete', 'DELETE', 'Usuario eliminado');
    } catch (e) { $('#eq-users').innerHTML = emptyBox('Error: ' + e.message, '⚠'); }
  }
  async function loadEquipoInv() {
    $('#eq-inv').innerHTML = skel();
    try {
      var d = await api('/api/company/registration-tokens');
      var rows = d.tokens || d.registration_tokens || [];
      if (!rows.length) { $('#eq-inv').innerHTML = emptyBox('Sin invitaciones pendientes.'); return; }
      $('#eq-inv').innerHTML = '<div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>Token</th><th>Nota</th><th>Admin</th><th>Expira</th><th>Estado</th></tr></thead><tbody>' +
        rows.map(function (t) {
          return '<tr style="cursor:default">' +
            '<td class="mono" style="max-width:200px;overflow:hidden;text-overflow:ellipsis">' + esc(t.token) + '</td>' +
            '<td>' + esc(t.description || '—') + '</td>' +
            '<td>' + (t.is_admin_token ? 'sí' : '—') + '</td>' +
            '<td class="muted">' + esc(fmtDate(t.expires_at)) + '</td>' +
            '<td>' + (t.is_used || t.used_at ? '<span class="badge pend plain">usado</span>' : '<span class="badge clean plain">pendiente</span>') + '</td>' +
          '</tr>';
        }).join('') + '</tbody></table></div>';
    } catch (e) { $('#eq-inv').innerHTML = emptyBox('Error: ' + e.message, '⚠'); }
  }

  /* ================================================================== *
   *  ANTICHEAT — violaciones del plugin
   * ================================================================== */
  async function renderAnticheat() {
    titleEl.textContent = 'Anticheat'; subEl.textContent = 'violaciones del plugin (24 h)';
    view.innerHTML = '<div class="kpi-grid" id="ac-lvls">' + Array(4).fill('<div class="kpi">' + skel() + '</div>').join('') + '</div>' +
      '<div class="grid-2">' +
        '<div class="panel-card"><header>Checks más disparados</header><div class="body" id="ac-checks">' + skel() + '</div></div>' +
        '<div class="panel-card"><header>Jugadores con más flags</header><div class="body" id="ac-players">' + skel() + '</div></div>' +
      '</div>';
    try {
      var d = await api('/api/plugin/violations/stats');
      var bl = d.by_level || {};
      var order = [['CRITICAL', 'alert'], ['HIGH', 'alert'], ['MID', ''], ['LOW', '']];
      $('#ac-lvls').innerHTML = order.map(function (o) {
        return '<div class="kpi ' + o[1] + '"><div class="k-label">' + o[0] + '</div><div class="k-value">' + num(bl[o[0]] || 0) + '</div></div>';
      }).join('');
      var listBox = function (rows, key) {
        return rows && rows.length
          ? '<div class="body pad">' + rows.map(function (r) {
              return '<div class="row" style="justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-soft)">' +
                '<span>' + esc(r[key]) + '</span><span class="mono muted">' + num(r.c) + '</span></div>';
            }).join('') + '</div>'
          : emptyBox('Sin violaciones en 24 h.', '◈');
      };
      $('#ac-checks').innerHTML = listBox(d.top_checks, 'check_name');
      $('#ac-players').innerHTML = listBox(d.top_players, 'player_name');
    } catch (e) {
      view.innerHTML = '<div class="wip-note">No se pudo cargar estadísticas de violaciones: ' + esc(e.message) +
        '. (El plugin sube violaciones vía <span class="mono">/api/plugin/violations</span> — si no hay servidor conectado, está vacío.)</div>';
    }
  }

  /* ================================================================== *
   *  ARGUS AI — scores de jugadores + acuerdo con el staff
   * ================================================================== */
  async function renderIA() {
    titleEl.textContent = 'Argus AI'; subEl.textContent = 'oráculo y acuerdo con el staff';
    view.innerHTML = '<div class="kpi-grid" id="ia-kpi">' + Array(3).fill('<div class="kpi">' + skel() + '</div>').join('') + '</div>' +
      '<div class="panel-card"><header>Jugadores evaluados por la IA</header><div class="body" id="ia-players">' + skel() + '</div></div>';
    try {
      var ar = await api('/api/ai/agreement-rate').catch(function () { return {}; });
      $('#ia-kpi').innerHTML =
        '<div class="kpi good"><div class="k-label">Acuerdo IA ↔ staff</div><div class="k-value">' + (ar.agreement_rate != null ? Math.round(ar.agreement_rate) + '%' : '–') + '</div>' +
          '<div class="k-sub">' + num(ar.sample_size) + ' veredictos</div></div>' +
        '<div class="kpi"><div class="k-label">IA correcta (confirmada)</div><div class="k-value">' + num(ar.confirmed_correct) + '</div></div>' +
        '<div class="kpi alert"><div class="k-label">IA equivocada</div><div class="k-value">' + num(ar.confirmed_wrong) + '</div></div>';
    } catch (e) { $('#ia-kpi').innerHTML = ''; }
    try {
      var d = await api('/api/ai/scores');
      var rows = d.scores || [];
      $('#ia-players').innerHTML = rows.length ? '<div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>Jugador</th><th>Score</th><th>Confianza</th><th>Acción sugerida</th><th>Evaluaciones</th><th>Última</th></tr></thead><tbody>' +
        rows.map(function (r) {
          var s = Math.round(r.score || 0);
          var col = s >= 70 ? 'crit' : s >= 40 ? 'susp' : 'clean';
          return '<tr style="cursor:default">' +
            '<td class="strong">' + esc(r.player_name || r.player_uuid) + '</td>' +
            '<td><span class="badge ' + col + ' plain">' + s + '</span></td>' +
            '<td class="muted">' + (r.confidence != null ? Math.round(r.confidence * 100) + '%' : '–') + '</td>' +
            '<td class="muted">' + esc(r.last_action || 'none') + '</td>' +
            '<td class="muted">' + num(r.evaluations_count) + '</td>' +
            '<td class="muted">' + esc(fmtDate(r.last_evaluated_at)) + '</td>' +
          '</tr>';
        }).join('') + '</tbody></table></div>' : emptyBox('La IA todavía no evaluó jugadores.', '✦');
    } catch (e) { $('#ia-players').innerHTML = emptyBox('Error: ' + e.message, '⚠'); }
  }

  /* ================================================================== *
   *  ADMINISTRACIÓN — empresas + métricas globales
   * ================================================================== */
  async function renderAdmin() {
    titleEl.textContent = 'Administración'; subEl.textContent = 'empresas y plataforma';
    view.innerHTML = '<div class="kpi-grid" id="ad-kpi">' + Array(4).fill('<div class="kpi">' + skel() + '</div>').join('') + '</div>' +
      '<div class="panel-card"><header>Empresas</header><div class="body" id="ad-comp">' + skel() + '</div></div>';
    try {
      var st = await api('/api/statistics');
      $('#ad-kpi').innerHTML = [
        ['Escaneos', num(st.total_scans)], ['Máquinas', num(st.unique_machines)],
        ['Detecciones críticas', num(st.severe_detections)], ['Baneos', num(st.total_bans)]
      ].map(function (k) { return '<div class="kpi"><div class="k-label">' + k[0] + '</div><div class="k-value">' + k[1] + '</div></div>'; }).join('');
    } catch (e) { $('#ad-kpi').innerHTML = ''; }
    try {
      var d = await api('/api/admin/companies');
      var rows = d.companies || [];
      $('#ad-comp').innerHTML = rows.length ? '<div class="table-wrap"><table class="tbl"><thead><tr>' +
        '<th>Empresa</th><th>Usuarios</th><th>Admins</th><th>Plan</th><th>Estado</th><th>Vence</th></tr></thead><tbody>' +
        rows.map(function (co) {
          return '<tr style="cursor:default">' +
            '<td class="strong">' + esc(co.name) + '</td>' +
            '<td>' + num(co.current_users) + '/' + num(co.max_users) + '</td>' +
            '<td>' + num(co.current_admins) + '/' + num(co.max_admins) + '</td>' +
            '<td class="muted">' + esc(co.subscription_type || '—') + '</td>' +
            '<td>' + (co.is_active ? '<span class="badge clean plain">activa</span>' : '<span class="badge pend plain">inactiva</span>') + '</td>' +
            '<td class="muted">' + esc(fmtDate(co.subscription_end_date)) + '</td>' +
          '</tr>';
        }).join('') + '</tbody></table></div>' : emptyBox('Sin empresas.', '⚙');
    } catch (e) {
      $('#ad-comp').innerHTML = '<div class="wip-note">Requiere rol de administrador de plataforma. ' + esc(e.message) + '</div>';
    }
  }

  /* ================================================================== *
   *  Router
   * ================================================================== */
  var routes = {
    '/inicio': renderInicio,
    '/revision': renderRevision,
    '/anticheat': renderAnticheat,
    '/ia': renderIA,
    '/servidores': renderServidores,
    '/equipo': renderEquipo,
    '/admin': renderAdmin
  };

  function route() {
    var h = location.hash.replace(/^#/, '') || '/inicio';
    var mScan = h.match(/^\/scan\/(\d+)$/) || h.match(/^scan-(\d+)$/);
    document.querySelectorAll('.nav-item').forEach(function (a) {
      a.classList.toggle('active', a.getAttribute('href') === '#' + (mScan ? '/revision' : h));
    });
    window.scrollTo(0, 0);
    if (mScan) return renderScan(mScan[1]);
    (routes[h] || renderInicio)();
  }

  view.addEventListener('click', function (e) {
    var tr = e.target.closest('tr[data-scan]');
    if (tr) location.hash = '/scan/' + tr.dataset.scan;
  });

  // sidebar: mostrar items admin según rol
  (function () {
    var role = String(CFG.staffRole || '').toLowerCase();
    var isAdmin = CFG.isOwner || /owner|admin|superadmin/.test(role);
    if (isAdmin) document.querySelectorAll('[data-admin]').forEach(function (el) { el.hidden = false; });
    var u = CFG.user || {};
    var name = u.username || u.name || 'staff';
    $('#foot-user').textContent = name;
    $('#foot-role').textContent = role || 'staff';
    $('#foot-avatar').textContent = (name[0] || '?').toUpperCase();
  })();

  window.addEventListener('hashchange', route);
  route();
})();
