/**
 * Control Imperial v2 — SPA Super Admin
 */
(function () {
  'use strict';

  var API_V2 = '/aspers-sa/api/v2';
  var API_V1 = '/aspers-sa/api';
  var state = { view: 'inicio', companies: [], plans: [] };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function toast(msg, type) {
    var host = $('imp-toast-host');
    if (!host) return;
    var t = document.createElement('div');
    t.className = 'imp-toast imp-toast-' + (type === 'err' ? 'err' : 'ok');
    t.textContent = msg;
    host.appendChild(t);
    setTimeout(function () { t.remove(); }, 4500);
  }

  function api(path, opts, base) {
    opts = opts || {};
    base = base || API_V2;
    return fetch(base + path, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      method: opts.method || 'GET',
      body: opts.body || undefined,
    }).then(function (r) {
      if (r.status === 401) { location.href = '/aspers-sa'; throw new Error('401'); }
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        return d;
      });
    });
  }

  var VIEW_TITLES = {
    inicio: ['Inicio', 'Visión general de la plataforma'],
    cartera: ['Cartera', 'Empresas y suscripciones'],
    planes: ['Planes', 'Catálogo y alta rápida'],
    regalos: ['Regalos', 'Usuarios individuales de regalo'],
    sorteos: ['Tokens sorteo', 'Links de registro para individuales'],
    migraciones: ['Migraciones', 'Usuarios mal asignados → empresa'],
    poder: ['Poder Imperial', 'Permisos, God Mode, impersonación'],
    ingresos: ['Ingresos', 'MRR y desglose'],
    inteligencia: ['Inteligencia', 'IA, trust, mantenimiento'],
  };

  function navigate(view) {
    state.view = view;
    document.querySelectorAll('.imp-nav-item').forEach(function (b) {
      b.classList.toggle('active', b.dataset.view === view);
    });
    document.querySelectorAll('.imp-view').forEach(function (v) {
      v.classList.toggle('active', v.id === 'view-' + view);
    });
    var t = VIEW_TITLES[view] || [view, ''];
    $('imp-page-title').innerHTML = t[0].replace(/ /g, ' <em>') + (t[0].indexOf(' ') > -1 ? '</em>' : '');
    if (t[0].indexOf(' ') === -1) $('imp-page-title').textContent = t[0];
    else {
      var parts = t[0].split(' ');
      $('imp-page-title').innerHTML = parts[0] + ' <em>' + parts.slice(1).join(' ') + '</em>';
    }
    $('imp-page-sub').textContent = t[1] || '';
    if (history.replaceState) history.replaceState(null, '', '#' + view);
    loadView(view);
    document.body.classList.remove('imp-mobile-open');
  }

  function loadView(view) {
    var loaders = {
      inicio: loadInicio,
      cartera: loadCartera,
      planes: loadPlanes,
      regalos: loadRegalos,
      sorteos: loadSorteos,
      migraciones: loadMigraciones,
      poder: loadPoderView,
      ingresos: loadIngresos,
      inteligencia: loadInteligencia,
    };
    if (loaders[view]) loaders[view]();
  }

  function loadInicio() {
    api('/dashboard').then(function (d) {
      $('kpi-companies').textContent = d.companies;
      $('kpi-users').textContent = d.users;
      $('kpi-mrr').textContent = '$' + (d.revenue_mrr || 0);
      $('kpi-mis').textContent = d.misassigned;
      $('kpi-tokens').textContent = d.tokens_individual_open;
      var badge = $('nav-badge-mis');
      if (badge) {
        badge.textContent = d.misassigned || '0';
        badge.style.display = d.misassigned ? 'inline' : 'none';
      }
      if (d.misassigned > 0) {
        $('inicio-alert').innerHTML = '<div class="imp-alert imp-alert-warn">⚠ ' + d.misassigned + ' usuario(s) mal asignados — revisá <a href="#" onclick="Imp.navigate(\'migraciones\');return false" style="color:var(--imp-gold)">Migraciones</a></div>';
      } else {
        $('inicio-alert').innerHTML = '';
      }
    }).catch(function (e) { toast(e.message, 'err'); });
    api('/overview', {}, API_V1).then(function (d) {
      var el = $('inicio-stats');
      if (!el) return;
      el.innerHTML =
        '<div class="imp-kpi-row">' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Scans 24h</div><div class="imp-kpi-val green">' + (d.scans_24h || 0) + '</div></div>' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Pendientes</div><div class="imp-kpi-val rose">' + (d.pending_total || 0) + '</div></div>' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Hacks 30d</div><div class="imp-kpi-val">' + (d.hacks_30d || 0) + '</div></div>' +
        '<div class="imp-kpi"><div class="imp-kpi-label">FP rate</div><div class="imp-kpi-val">' + (d.fp_rate_30d != null ? (d.fp_rate_30d * 100).toFixed(1) + '%' : '—') + '</div></div>' +
        '</div>';
    }).catch(function () {});
  }

  function loadCartera() {
    api('/overview', {}, API_V1).then(function () {});
    fetch('/aspers-sa', { credentials: 'same-origin' }).then(function () {
      /* companies from embedded or refetch via v1 - use window._IMP_COMPANIES */
      var cos = window._IMP_COMPANIES || [];
      var tb = $('cartera-tbody');
      if (!cos.length) { tb.innerHTML = '<tr><td colspan="6" class="imp-empty">Sin empresas</td></tr>'; return; }
      tb.innerHTML = cos.map(function (c) {
        var st = (c.subscription_status || '').toLowerCase();
        var badge = st === 'active' ? 'imp-badge-ok' : 'imp-badge-err';
        return '<tr><td><strong>' + esc(c.name) + '</strong></td>' +
          '<td><span class="imp-badge ' + badge + '">' + esc(st) + '</span></td>' +
          '<td class="mono">$' + (c.subscription_price || 0) + '</td>' +
          '<td class="mono">' + (c.current_users || 0) + '/' + (c.max_users || 8) + '</td>' +
          '<td class="mono">' + esc(c.subscription_end_date || '—') + '</td>' +
          '<td><button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.extendCompany(' + c.id + ')">+30d</button> ' +
          '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.applyPlanToCompany(' + c.id + ')">Plan</button></td></tr>';
      }).join('');
    });
  }

  function loadPlanes() {
    api('/plans').then(function (d) {
      state.plans = d.plans || [];
      var grid = $('planes-grid');
      grid.innerHTML = state.plans.map(function (p) {
        return '<div class="imp-plan" style="--plan-color:' + esc(p.color || '#E8C547') + '">' +
          '<div class="imp-plan-type">' + esc(p.type) + '</div>' +
          '<div class="imp-plan-name">' + esc(p.name) + '</div>' +
          '<div class="imp-plan-price">' + (p.price > 0 ? '$' + p.price : 'Gratis') + '<span style="font-size:12px;color:var(--imp-muted)">/mes</span></div>' +
          '<p class="imp-plan-desc">' + esc(p.desc || '') + '</p>' +
          '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.applyPlanModal(\'' + esc(p.id) + '\')">Activar plan</button></div>';
      }).join('');
    });
  }

  function loadRegalos() {}

  function loadSorteos() {
    api('/tokens/individual').then(function (d) {
      var tb = $('sorteos-tbody');
      var rows = (d.tokens || []).slice(0, 40);
      if (!rows.length) { tb.innerHTML = '<tr><td colspan="5" class="imp-empty">Sin tokens individuales</td></tr>'; return; }
      tb.innerHTML = rows.map(function (t) {
        var url = location.origin + '/register?token=' + encodeURIComponent(t.token);
        return '<tr><td class="mono">' + esc((t.description || '').slice(0, 40)) + '</td>' +
          '<td>' + (t.is_used ? '<span class="imp-badge imp-badge-muted">usado</span>' : '<span class="imp-badge imp-badge-ok">libre</span>') + '</td>' +
          '<td class="mono">' + esc(t.expires_at || '') + '</td>' +
          '<td class="mono"><a href="' + esc(url) + '" target="_blank" style="color:var(--imp-gold)">link</a></td>' +
          '<td><button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="navigator.clipboard.writeText(\'' + esc(t.token) + '\');Imp.toast(\'Copiado\')">Copiar</button></td></tr>';
      }).join('');
    });
  }

  function loadMigraciones() {
    api('/users/misassigned').then(function (d) {
      state.companies = d.companies || [];
      var sel = $('mig-company-select');
      sel.innerHTML = '<option value="">— Elegir empresa destino —</option>' +
        state.companies.map(function (c) {
          return '<option value="' + c.id + '">' + esc(c.name) + ' #' + c.id + '</option>';
        }).join('');
      var users = d.users || [];
      var tb = $('mig-tbody');
      if (!users.length) {
        tb.innerHTML = '<tr><td colspan="6" class="imp-empty">✓ No hay usuarios mal asignados</td></tr>';
        return;
      }
      tb.innerHTML = users.map(function (u) {
        return '<tr><td><input type="checkbox" class="mig-check" value="' + u.id + '"></td>' +
          '<td><strong>' + esc(u.username) + '</strong> <span class="mono">#' + u.id + '</span></td>' +
          '<td>' + (u.roles || []).map(function (r) { return '<span class="imp-badge imp-badge-muted">' + esc(r) + '</span>'; }).join(' ') + '</td>' +
          '<td class="mono">' + esc((u.misassign_reasons || []).join('; ')) + '</td>' +
          '<td><button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.attachOne(' + u.id + ')">Mover →</button></td>' +
          '<td><button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.resetPw(' + u.id + ')">Reset pass</button></td></tr>';
      }).join('');
    });
  }

  function loadPoderView() {
    if (typeof loadPoder === 'function') loadPoder();
  }

  function loadIngresos() {
    api('/revenue/summary').then(function (d) {
      $('ing-mrr').textContent = '$' + (d.mrr || 0);
      $('ing-paying').textContent = d.paying || 0;
      $('ing-free').textContent = d.free_active || 0;
      var tb = $('ing-tbody');
      tb.innerHTML = (d.by_price || []).map(function (r) {
        return '<tr><td class="mono">$' + r.price + '</td><td>' + r.count + ' empresas</td><td class="mono">$' + (r.price * r.count).toFixed(0) + '/mes</td></tr>';
      }).join('') || '<tr><td colspan="3" class="imp-empty">Sin datos</td></tr>';
    });
  }

  function loadInteligencia() {
    api('/overview', {}, API_V1).then(function (d) {
      $('intel-body').innerHTML =
        '<div class="imp-kpi-row">' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Patterns IA</div><div class="imp-kpi-val">' + (d.autolearn_active || 0) + '</div></div>' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Cooldowns</div><div class="imp-kpi-val">' + (d.cooldowns_active || 0) + '</div></div>' +
        '<div class="imp-kpi"><div class="imp-kpi-label">Staff trust</div><div class="imp-kpi-val">' + (d.staff_with_trust || 0) + '</div></div>' +
        '</div>' +
        '<p style="color:var(--imp-muted);font-size:13px;margin-top:12px">API legacy: <code>/aspers-sa/api/ai-health</code>, trust, maintenance — disponibles vía Cmd+K buscar "IA".</p>';
    });
  }

  function attachOne(uid) {
    var cid = $('mig-company-select').value;
    if (!cid) { toast('Elegí empresa destino arriba', 'err'); return; }
    api('/users/' + uid + '/attach-company', {
      method: 'POST',
      body: JSON.stringify({ company_id: parseInt(cid, 10), force: true }),
    }).then(function () {
      toast('Usuario movido a empresa #' + cid, 'ok');
      loadMigraciones();
      loadInicio();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function bulkAttach() {
    var cid = $('mig-company-select').value;
    if (!cid) { toast('Elegí empresa', 'err'); return; }
    var ids = [];
    document.querySelectorAll('.mig-check:checked').forEach(function (c) { ids.push(parseInt(c.value, 10)); });
    if (!ids.length) { toast('Marcá usuarios', 'err'); return; }
    api('/users/bulk-attach', {
      method: 'POST',
      body: JSON.stringify({ user_ids: ids, company_id: parseInt(cid, 10), force: true }),
    }).then(function (d) {
      toast('Migrados: ' + (d.attached || []).length, 'ok');
      loadMigraciones();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function createGiftUser() {
    var u = $('gift-username').value.trim();
    var e = $('gift-email').value.trim();
    if (!u) { toast('Username requerido', 'err'); return; }
    api('/gift-user', { method: 'POST', body: JSON.stringify({ username: u, email: e || null }) })
      .then(function (d) {
        $('gift-result').innerHTML = '<div class="imp-alert imp-alert-warn"><strong>' + esc(d.username) + '</strong><br>Contraseña: <code>' + esc(d.password) + '</code><br><small>Guardala — no se vuelve a mostrar.</small></div>';
        toast('Regalo creado', 'ok');
      }).catch(function (err) { toast(err.message, 'err'); });
  }

  function createSorteoTokens() {
    var n = parseInt($('sorteo-count').value, 10) || 5;
    var h = parseInt($('sorteo-hours').value, 10) || 168;
    var lbl = $('sorteo-label').value.trim() || 'Sorteo Imperial';
    api('/tokens/individual', {
      method: 'POST',
      body: JSON.stringify({ count: n, expires_hours: h, label: lbl }),
    }).then(function (d) {
      var html = (d.created || []).map(function (t) {
        return '<div class="imp-token-box">' + esc(t.register_url) + '</div>';
      }).join('');
      $('sorteo-result').innerHTML = '<p style="margin-bottom:8px;color:var(--imp-green)">' + d.count + ' tokens creados</p>' + html;
      toast('Batch sorteo listo', 'ok');
      loadSorteos();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function applyPlanModal(planId) {
    var p = state.plans.find(function (x) { return x.id === planId; });
    if (!p) return;
    if (p.type === 'enterprise') {
      var name = prompt('Nombre de la nueva empresa:', p.name + ' — Cliente');
      if (!name) return;
      api('/plans/' + planId + '/apply', {
        method: 'POST',
        body: JSON.stringify({ company_name: name }),
      }).then(function (d) {
        toast('Empresa #' + d.company_id + ' creada', 'ok');
      }).catch(function (e) { toast(e.message, 'err'); });
    } else {
      var user = prompt('Username individual:');
      if (!user) return;
      api('/plans/' + planId + '/apply', {
        method: 'POST',
        body: JSON.stringify({ username: user }),
      }).then(function (d) {
        var msg = 'Usuario ' + d.username + ' creado';
        if (d.temp_password) msg += ' — pass: ' + d.temp_password;
        toast(msg, 'ok');
        alert(msg);
      }).catch(function (e) { toast(e.message, 'err'); });
    }
  }

  function extendCompany(cid) {
    api('/companies/' + cid + '/extend', { method: 'POST', body: JSON.stringify({ days: 30 }) })
      .then(function () { toast('Empresa extendida +30d', 'ok'); loadCartera(); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function applyPlanToCompany(cid) {
    var pid = prompt('Plan ID (ent_starter, ent_pro, ent_trial...):', 'ent_starter');
    if (!pid) return;
    api('/companies/' + cid + '/apply-plan', { method: 'POST', body: JSON.stringify({ plan_id: pid }) })
      .then(function () { toast('Plan aplicado', 'ok'); loadCartera(); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function resetPw(uid) {
    if (!confirm('¿Generar nueva contraseña para user #' + uid + '?')) return;
    api('/users/' + uid + '/reset-password', { method: 'POST', body: '{}' })
      .then(function (d) { alert('Nueva contraseña: ' + d.password); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function initSearch() {
    var inp = $('imp-search-input');
    if (!inp) return;
    var timer;
    inp.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var q = inp.value.trim();
        if (q.length < 2) return;
        api('/quick-search?q=' + encodeURIComponent(q)).then(function (d) {
          /* future dropdown */
        });
      }, 300);
    });
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inp.focus();
      }
    });
  }

  window.Imp = {
    navigate: navigate,
    toast: toast,
    attachOne: attachOne,
    bulkAttach: bulkAttach,
    createGiftUser: createGiftUser,
    createSorteoTokens: createSorteoTokens,
    applyPlanModal: applyPlanModal,
    extendCompany: extendCompany,
    applyPlanToCompany: applyPlanToCompany,
    resetPw: resetPw,
  };

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.imp-nav-item').forEach(function (btn) {
      btn.addEventListener('click', function () { navigate(btn.dataset.view); });
    });
    $('imp-menu-btn') && $('imp-menu-btn').addEventListener('click', function () {
      document.body.classList.toggle('imp-mobile-open');
    });
    initSearch();
    var hash = (location.hash || '').replace('#', '');
    navigate(hash && VIEW_TITLES[hash] ? hash : 'inicio');
  });
})();
