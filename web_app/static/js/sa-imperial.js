/**
 * Control Imperial v2 — SPA Super Admin (mejorado)
 */
(function () {
  'use strict';

  var API_V2 = '/aspers-sa/api/v2';
  var API_V1 = '/aspers-sa/api';
  var state = {
    view: 'inicio',
    companies: window._IMP_COMPANIES || [],
    plans: [],
    migUsers: [],
    carteraFilter: '',
  };

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
    setTimeout(function () { t.classList.add('imp-toast-out'); }, 3800);
    setTimeout(function () { t.remove(); }, 4300);
  }

  function copyText(text, okMsg) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(function () {
      toast(okMsg || 'Copiado al portapapeles', 'ok');
    }).catch(function () {
      toast('No se pudo copiar', 'err');
    });
  }

  function copyFromBtn(btn) {
    copyText(btn.getAttribute('data-copy'));
  }

  function revokeFromBtn(btn) {
    revokeToken(btn.getAttribute('data-token'));
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
      if (r.status === 401) {
        location.href = '/aspers-sa';
        throw new Error('Sesión expirada');
      }
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        return d;
      });
    });
  }

  function setLoading(el, on) {
    if (!el) return;
    if (on) el.classList.add('imp-loading');
    else el.classList.remove('imp-loading');
  }

  function refreshCompanies() {
    return api('/companies').then(function (d) {
      state.companies = d.companies || [];
      window._IMP_COMPANIES = state.companies;
      return state.companies;
    });
  }

  function companyOptions(selectedId) {
    return state.companies.map(function (c) {
      var sel = selectedId && String(c.id) === String(selectedId) ? ' selected' : '';
      return '<option value="' + c.id + '"' + sel + '>' + esc(c.name) + ' #' + c.id + '</option>';
    }).join('');
  }

  /* ── Modal ── */
  function openModal(title, bodyHtml, footerHtml) {
    var root = $('imp-modal-root');
    if (!root) return;
    root.innerHTML =
      '<div class="imp-modal-backdrop" data-close="1"></div>' +
      '<div class="imp-modal" role="dialog">' +
      '<div class="imp-modal-head"><h3>' + title + '</h3><button type="button" class="imp-modal-close" data-close="1">✕</button></div>' +
      '<div class="imp-modal-body">' + bodyHtml + '</div>' +
      (footerHtml ? '<div class="imp-modal-foot">' + footerHtml + '</div>' : '') +
      '</div>';
    root.classList.add('open');
    root.querySelectorAll('[data-close]').forEach(function (el) {
      el.addEventListener('click', closeModal);
    });
  }

  function closeModal() {
    var root = $('imp-modal-root');
    if (root) {
      root.classList.remove('open');
      root.innerHTML = '';
    }
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
    inteligencia: ['Inteligencia', 'IA, trust, mantenimiento y ops'],
  };

  function setPageTitle(view) {
    var t = VIEW_TITLES[view] || [view, ''];
    var titleEl = $('imp-page-title');
    var parts = t[0].split(' ');
    if (parts.length === 1) {
      titleEl.textContent = t[0];
    } else {
      titleEl.innerHTML = esc(parts[0]) + ' <em>' + esc(parts.slice(1).join(' ')) + '</em>';
    }
    $('imp-page-sub').textContent = t[1] || '';
  }

  function navigate(view) {
    state.view = view;
    document.querySelectorAll('.imp-nav-item').forEach(function (b) {
      b.classList.toggle('active', b.dataset.view === view);
    });
    document.querySelectorAll('.imp-view').forEach(function (v) {
      v.classList.toggle('active', v.id === 'view-' + view);
    });
    setPageTitle(view);
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

  function formatDate(iso) {
    if (!iso) return '—';
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso).slice(0, 10);
      return d.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch (e) {
      return String(iso).slice(0, 10);
    }
  }

  function statusBadge(st) {
    var s = (st || '').toLowerCase();
    if (s === 'active') return 'imp-badge-ok';
    if (s === 'suspended' || s === 'expired') return 'imp-badge-err';
    return 'imp-badge-warn';
  }

  /* ── Inicio ── */
  function loadInicio() {
    var stats = $('inicio-stats');
    setLoading(stats, true);
    Promise.all([
      api('/dashboard'),
      api('/overview', {}, API_V1),
    ]).then(function (arr) {
      var d = arr[0];
      var ov = arr[1];
      $('kpi-companies').textContent = d.companies;
      $('kpi-users').textContent = d.users;
      $('kpi-mrr').textContent = '$' + (d.revenue_mrr || 0);
      $('kpi-mis').textContent = d.misassigned;
      $('kpi-tokens').textContent = d.tokens_individual_open;
      var indEl = $('kpi-individuals');
      if (indEl) indEl.textContent = d.individuals != null ? d.individuals : '—';
      var cosSub = $('kpi-companies-sub');
      if (cosSub && ov.companies_active != null) {
        cosSub.textContent = (ov.companies_active || 0) + ' activas · ' + (ov.companies_expired || 0) + ' vencidas';
      }
      var badge = $('nav-badge-mis');
      if (badge) {
        badge.textContent = d.misassigned || '0';
        badge.style.display = d.misassigned ? 'inline' : 'none';
      }
      if (d.misassigned > 0) {
        $('inicio-alert').innerHTML =
          '<div class="imp-alert imp-alert-warn">⚠ ' + d.misassigned +
          ' usuario(s) mal asignados — <a href="#" class="imp-link" data-nav="migraciones">Ir a Migraciones</a></div>';
        var navLink = $('inicio-alert').querySelector('[data-nav]');
        if (navLink) {
          navLink.addEventListener('click', function (e) {
            e.preventDefault();
            navigate('migraciones');
          });
        }
      } else {
        $('inicio-alert').innerHTML =
          '<div class="imp-alert imp-alert-ok">✓ Cartera al día — sin usuarios huérfanos detectados</div>';
      }
      stats.innerHTML =
        '<div class="imp-intel-stat"><span>Scans últimas 24h</span><span>' + (ov.scans_24h || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Scans últimos 7 días</span><span>' + (ov.scans_7d || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Veredictos pendientes</span><span class="rose">' + (ov.pending_total || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Hacks confirmados (30d)</span><span>' + (ov.hacks_30d || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Tasa falsos positivos (30d)</span><span>' +
        (ov.fp_rate_30d != null ? (ov.fp_rate_30d * 100).toFixed(1) + '%' : '—') + '</span></div>';
      setLoading(stats, false);
    }).catch(function (e) {
      setLoading(stats, false);
      toast(e.message, 'err');
    });
  }

  /* ── Cartera ── */
  function renderCartera() {
    var tb = $('cartera-tbody');
    var q = (state.carteraFilter || '').toLowerCase();
    var cos = state.companies.filter(function (c) {
      if (!q) return true;
      return (c.name || '').toLowerCase().indexOf(q) >= 0 ||
        String(c.id).indexOf(q) >= 0 ||
        (c.subscription_status || '').toLowerCase().indexOf(q) >= 0;
    });
    $('cartera-count').textContent = cos.length + ' mostradas · ' + state.companies.length + ' total';
    if (!cos.length) {
      tb.innerHTML = '<tr><td colspan="5" class="imp-empty">Sin resultados con ese filtro</td></tr>';
      return;
    }
    tb.innerHTML = cos.map(function (c) {
      var st = (c.subscription_status || '').toLowerCase();
      var pct = c.max_users ? Math.min(100, Math.round((c.current_users || 0) / c.max_users * 100)) : 0;
      var email = c.contact_email || c.email || '';
      return '<tr data-cid="' + c.id + '">' +
        '<td><div class="imp-cell-stack"><strong>' + esc(c.name) + '</strong>' +
        '<div class="imp-row-sub mono">ID ' + c.id + (email ? ' · ' + esc(email) : '') + '</div></div></td>' +
        '<td><span class="imp-badge ' + statusBadge(st) + '">' + esc(st || '—') + '</span>' +
        '<div class="imp-row-sub mono">$' + (c.subscription_price || 0) + '/mes</div></td>' +
        '<td><div class="mono">' + (c.current_users || 0) + ' de ' + (c.max_users || 8) + ' staff</div>' +
        '<div class="imp-bar"><span style="width:' + pct + '%"></span></div></td>' +
        '<td class="imp-cell-muted">' + esc(formatDate(c.subscription_end_date)) + '</td>' +
        '<td class="imp-col-actions"><div class="imp-action-group">' +
        '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.openCompanyMenu(' + c.id + ')">Gestionar</button>' +
        '</div></td></tr>';
    }).join('');
  }

  function loadCartera() {
    var tb = $('cartera-tbody');
    setLoading(tb.closest('.imp-card'), true);
    refreshCompanies().then(function () {
      renderCartera();
      setLoading(tb.closest('.imp-card'), false);
    }).catch(function (e) {
      setLoading(tb.closest('.imp-card'), false);
      toast(e.message, 'err');
      renderCartera();
    });
  }

  /* ── Planes ── */
  function loadPlanes() {
    var grid = $('planes-grid');
    setLoading(grid, true);
    api('/plans').then(function (d) {
      state.plans = d.plans || [];
      grid.innerHTML = state.plans.map(function (p) {
        var specs = [];
        if (p.type === 'enterprise') {
          specs.push('Hasta ' + (p.max_users || 8) + ' usuarios');
          specs.push((p.max_admins || 3) + ' admins');
          if (p.trial_days) specs.push(p.trial_days + ' días de prueba');
        } else {
          specs.push(p.gift ? 'Sin cargo · regalo' : 'Cuenta individual');
          specs.push('Rol: ' + ((p.roles || ['user']).join(', ')));
        }
        if (p.months) specs.push(p.months + ' mes(es) de ciclo');
        return '<div class="imp-plan" style="--plan-color:' + esc(p.color || '#E8C547') + '">' +
          '<div class="imp-plan-type">' + esc(p.type === 'enterprise' ? 'Empresa' : 'Individual') + '</div>' +
          '<div class="imp-plan-id">' + esc(p.id) + '</div>' +
          '<div class="imp-plan-name">' + esc(p.name) + '</div>' +
          '<div class="imp-plan-price">' + (p.price > 0 ? '$' + p.price : 'Gratis') + '<span>/mes</span></div>' +
          '<p class="imp-plan-desc">' + esc(p.desc || '') + '</p>' +
          '<ul class="imp-plan-specs">' + specs.map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>' +
          '<div class="imp-plan-actions">' +
          '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.openApplyPlan(\'' + esc(p.id) + '\')">Dar de alta</button>' +
          '</div></div>';
      }).join('');
      setLoading(grid, false);
    }).catch(function (e) {
      setLoading(grid, false);
      toast(e.message, 'err');
    });
  }

  function openApplyPlan(planId) {
    var p = state.plans.find(function (x) { return x.id === planId; });
    if (!p) return;
    if (p.type === 'enterprise') {
      openModal('Alta empresa · ' + esc(p.name),
        '<div class="imp-field"><label>Nombre de la empresa</label><span class="imp-field-hint">Como aparecerá en el panel</span><input id="modal-company-name" class="imp-input" value="' + esc(p.name + ' — Cliente') + '"></div>' +
        '<div class="imp-field"><label>Email de contacto</label><span class="imp-field-hint">Opcional</span><input id="modal-company-email" class="imp-input" type="email" placeholder="admin@servidor.com"></div>',
        '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cancelar</button>' +
        '<button type="button" class="imp-btn imp-btn-gold" id="modal-apply-plan-btn">Crear empresa</button>');
      $('modal-apply-plan-btn').onclick = function () {
        api('/plans/' + planId + '/apply', {
          method: 'POST',
          body: JSON.stringify({
            company_name: $('modal-company-name').value.trim(),
            email: $('modal-company-email').value.trim() || null,
          }),
        }).then(function (d) {
          closeModal();
          toast('Empresa #' + d.company_id + ' creada', 'ok');
          refreshCompanies().then(renderCartera);
        }).catch(function (e) { toast(e.message, 'err'); });
      };
    } else {
      openModal('Alta individual · ' + esc(p.name),
        '<div class="imp-field"><label>Usuario</label><span class="imp-field-hint">Sin espacios</span><input id="modal-username" class="imp-input" placeholder="nombre_usuario"></div>' +
        '<div class="imp-field"><label>Email</label><span class="imp-field-hint">Opcional</span><input id="modal-user-email" class="imp-input" type="email"></div>',
        '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cancelar</button>' +
        '<button type="button" class="imp-btn imp-btn-gold" id="modal-apply-plan-btn">Crear usuario</button>');
      $('modal-apply-plan-btn').onclick = function () {
        var user = $('modal-username').value.trim();
        if (!user) { toast('Username requerido', 'err'); return; }
        api('/plans/' + planId + '/apply', {
          method: 'POST',
          body: JSON.stringify({ username: user, email: $('modal-user-email').value.trim() || null }),
        }).then(function (d) {
          closeModal();
          var msg = 'Usuario ' + d.username + ' creado';
          if (d.temp_password) {
            openModal('Credenciales', '<p>Usuario: <strong>' + esc(d.username) + '</strong></p><p>Contraseña: <code>' + esc(d.temp_password) + '</code></p>',
              '<button type="button" class="imp-btn imp-btn-gold" data-copy="' + esc(d.temp_password) + '" onclick="Imp.copyFromBtn(this);Imp.closeModal()">Copiar pass</button>');
          } else {
            toast(msg, 'ok');
          }
        }).catch(function (e) { toast(e.message, 'err'); });
      };
    }
  }

  function openPlanPicker(cid) {
    var opts = state.plans.filter(function (p) { return p.type === 'enterprise'; })
      .map(function (p) {
        return '<option value="' + esc(p.id) + '">' + esc(p.name) + ' ($' + p.price + ')</option>';
      }).join('');
    openModal('Cambiar plan · empresa #' + cid,
      '<div class="imp-field"><label>Plan empresarial</label><select id="modal-plan-id" class="imp-select">' + opts + '</select></div>' +
      '<div class="imp-field"><label>Extender vigencia (meses)</label><span class="imp-field-hint">0 = solo actualizar límites y precio</span><input id="modal-plan-months" class="imp-input" type="number" value="1" min="0"></div>',
      '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cancelar</button>' +
      '<button type="button" class="imp-btn imp-btn-gold" id="modal-pick-plan-btn">Aplicar</button>');
    $('modal-pick-plan-btn').onclick = function () {
      api('/companies/' + cid + '/apply-plan', {
        method: 'POST',
        body: JSON.stringify({
          plan_id: $('modal-plan-id').value,
          months: parseInt($('modal-plan-months').value, 10) || 1,
        }),
      }).then(function () {
        closeModal();
        toast('Plan aplicado', 'ok');
        loadCartera();
      }).catch(function (e) { toast(e.message, 'err'); });
    };
  }

  /* ── Regalos ── */
  function loadRegalos() {}

  function suggestGiftUsername() {
    var base = 'regalo_' + Math.random().toString(36).slice(2, 8);
    $('gift-username').value = base;
  }

  function createGiftUser() {
    var u = $('gift-username').value.trim();
    var e = $('gift-email').value.trim();
    if (!u) { toast('Username requerido', 'err'); return; }
    api('/gift-user', { method: 'POST', body: JSON.stringify({ username: u, email: e || null }) })
      .then(function (d) {
        $('gift-result').innerHTML =
          '<div class="imp-cred-box">' +
          '<div><span>Usuario</span><strong>' + esc(d.username) + '</strong> ' +
          '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" data-copy="' + esc(d.username) + '" onclick="Imp.copyFromBtn(this)">Copiar</button></div>' +
          '<div><span>Contraseña</span><code>' + esc(d.password) + '</code> ' +
          '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" data-copy="' + esc(d.password) + '" onclick="Imp.copyFromBtn(this)">Copiar</button></div>' +
          '<small>Guardala — no se vuelve a mostrar.</small></div>';
        toast('Regalo creado', 'ok');
      }).catch(function (err) { toast(err.message, 'err'); });
  }

  /* ── Sorteos ── */
  function loadSorteos() {
    var tb = $('sorteos-tbody');
    setLoading(tb.closest('.imp-card'), true);
    api('/tokens/individual').then(function (d) {
      var rows = d.tokens || [];
      $('sorteo-stats').textContent = (d.unused || 0) + ' disponibles de ' + (d.count || 0);
      if (!rows.length) {
        tb.innerHTML = '<tr><td colspan="4" class="imp-empty">Aún no hay tokens — generá un lote arriba</td></tr>';
      } else {
        tb.innerHTML = rows.slice(0, 80).map(function (t) {
          var url = location.origin + '/register?token=' + encodeURIComponent(t.token);
          return '<tr><td><div class="imp-cell-stack"><strong>' + esc((t.description || 'Sin nombre').slice(0, 56)) + '</strong>' +
            '<div class="imp-row-sub mono">' + esc((t.token || '').slice(0, 12)) + '…</div></div></td>' +
            '<td>' + (t.is_used ? '<span class="imp-badge imp-badge-muted">Usado</span>' : '<span class="imp-badge imp-badge-ok">Disponible</span>') + '</td>' +
            '<td class="imp-cell-muted">' + esc(formatDate(t.expires_at)) + '</td>' +
            '<td class="imp-col-actions"><div class="imp-action-group">' +
            '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" data-copy="' + esc(url) + '" onclick="Imp.copyFromBtn(this)">Link</button>' +
            (!t.is_used ? '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" data-token="' + esc(t.token) + '" onclick="Imp.revokeFromBtn(this)">Revocar</button>' : '') +
            '</div></td></tr>';
        }).join('');
      }
      setLoading(tb.closest('.imp-card'), false);
    }).catch(function (e) {
      setLoading(tb.closest('.imp-card'), false);
      toast(e.message, 'err');
    });
  }

  function createSorteoTokens() {
    var n = parseInt($('sorteo-count').value, 10) || 5;
    var h = parseInt($('sorteo-hours').value, 10) || 168;
    var lbl = $('sorteo-label').value.trim() || 'Sorteo Imperial';
    api('/tokens/individual', {
      method: 'POST',
      body: JSON.stringify({ count: n, expires_hours: h, label: lbl }),
    }).then(function (d) {
      var links = (d.created || []).map(function (t) { return t.register_url; });
      $('sorteo-result').innerHTML =
        '<div class="imp-alert imp-alert-ok">' + d.count + ' tokens creados</div>' +
        '<div class="imp-token-actions">' +
        '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.copyText(' + JSON.stringify(links.join('\n')) + ',\'Links copiados\')">Copiar todos los links</button>' +
        '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.downloadLines(' + JSON.stringify(links) + ',\'sorteo-tokens.txt\')">Descargar .txt</button></div>' +
        (d.created || []).map(function (t) {
          return '<div class="imp-token-box">' + esc(t.register_url) + '</div>';
        }).join('');
      toast('Batch sorteo listo', 'ok');
      loadSorteos();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function revokeToken(token) {
    if (!confirm('¿Revocar este token?')) return;
    api('/tokens/individual/' + encodeURIComponent(token) + '/revoke', { method: 'POST', body: '{}' })
      .then(function () { toast('Token revocado', 'ok'); loadSorteos(); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function downloadLines(lines, filename) {
    var blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename || 'export.txt';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /* ── Migraciones ── */
  function loadMigraciones() {
    var tb = $('mig-tbody');
    setLoading(tb.closest('.imp-card'), true);
    Promise.all([api('/users/misassigned'), refreshCompanies()]).then(function (arr) {
      var d = arr[0];
      state.migUsers = d.users || [];
      var sel = $('mig-company-select');
      sel.innerHTML = '<option value="">Seleccionar empresa…</option>' + companyOptions();
      var summary = $('mig-summary');
      if (summary) {
        summary.innerHTML = state.migUsers.length
          ? '<strong>' + state.migUsers.length + '</strong> usuario(s) por corregir. Podés elegir empresa en cada fila o usar el selector de arriba para varios.'
          : 'Todo en orden: no hay usuarios con rol empresa/staff sin empresa asignada.';
      }
      if (!state.migUsers.length) {
        tb.innerHTML = '<tr><td colspan="5" class="imp-empty">Nada que corregir por ahora</td></tr>';
      } else {
        tb.innerHTML = state.migUsers.map(function (u) {
          var roles = (u.roles || []).slice(0, 3).join(', ');
          return '<tr data-uid="' + u.id + '">' +
            '<td><input type="checkbox" class="mig-check" value="' + u.id + '"></td>' +
            '<td><div class="imp-cell-stack"><strong>' + esc(u.username) + '</strong>' +
            '<div class="imp-row-sub mono">ID ' + u.id + (u.email ? ' · ' + esc(u.email) : '') + '</div></div></td>' +
            '<td><div class="imp-problem">' + esc((u.misassign_reasons || []).join(' ')) + '</div>' +
            '<div class="imp-row-sub">Roles: ' + esc(roles) + '</div></td>' +
            '<td><select class="mig-row-company imp-select imp-select-sm"><option value="">Elegir…</option>' +
            companyOptions() + '</select></td>' +
            '<td class="imp-col-actions"><div class="imp-action-group">' +
            '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" onclick="Imp.attachOne(' + u.id + ')">Mover</button>' +
            '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.openUserMenu(' + u.id + ')">Más</button>' +
            '</div></td></tr>';
        }).join('');
      }
      setLoading(tb.closest('.imp-card'), false);
    }).catch(function (e) {
      setLoading(tb.closest('.imp-card'), false);
      toast(e.message, 'err');
    });
  }

  function getAttachCompanyId(uid) {
    var row = document.querySelector('tr[data-uid="' + uid + '"]');
    if (row) {
      var sel = row.querySelector('.mig-row-company');
      if (sel && sel.value) return sel.value;
    }
    return $('mig-company-select').value;
  }

  function attachOne(uid) {
    var cid = getAttachCompanyId(uid);
    if (!cid) { toast('Elegí empresa destino', 'err'); return; }
    api('/users/' + uid + '/attach-company', {
      method: 'POST',
      body: JSON.stringify({ company_id: parseInt(cid, 10), force: true }),
    }).then(function () {
      toast('Usuario #' + uid + ' → empresa #' + cid, 'ok');
      loadMigraciones();
      loadInicio();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function bulkAttach() {
    var cid = $('mig-company-select').value;
    if (!cid) { toast('Elegí empresa destino global', 'err'); return; }
    var ids = [];
    document.querySelectorAll('.mig-check:checked').forEach(function (c) {
      ids.push(parseInt(c.value, 10));
    });
    if (!ids.length) { toast('Marcá usuarios', 'err'); return; }
    api('/users/bulk-attach', {
      method: 'POST',
      body: JSON.stringify({ user_ids: ids, company_id: parseInt(cid, 10), force: true }),
    }).then(function (d) {
      var n = (d.attached || []).length;
      var errN = (d.errors || []).length;
      toast('Migrados: ' + n + (errN ? ' · errores: ' + errN : ''), errN ? 'err' : 'ok');
      loadMigraciones();
      loadInicio();
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function toggleMigSelectAll(checked) {
    document.querySelectorAll('.mig-check').forEach(function (c) { c.checked = checked; });
  }

  function promoteUser(uid) {
    var u = state.migUsers.find(function (x) { return x.id === uid; });
    var defName = u ? (u.username + ' Corp') : 'Nueva empresa';
    openModal('Promover a empresa · user #' + uid,
      '<div class="imp-field"><label>Nombre nueva empresa</label><input id="modal-promote-name" value="' + esc(defName) + '"></div>' +
      '<p class="imp-hint">Crea empresa y asigna al usuario como admin/staff.</p>',
      '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cancelar</button>' +
      '<button type="button" class="imp-btn imp-btn-gold" id="modal-promote-btn">Crear y asignar</button>');
    $('modal-promote-btn').onclick = function () {
      api('/users/' + uid + '/promote-individual', {
        method: 'POST',
        body: JSON.stringify({ company_name: $('modal-promote-name').value.trim() }),
      }).then(function (d) {
        closeModal();
        toast('Empresa #' + d.company_id + ' creada', 'ok');
        refreshCompanies();
        loadMigraciones();
      }).catch(function (e) { toast(e.message, 'err'); });
    };
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
      var rows = d.by_price || [];
      var total = d.mrr || 0;
      tb.innerHTML = rows.map(function (r) {
        var sub = r.price * r.count;
        var pct = total ? Math.round(sub / total * 100) : 0;
        return '<tr><td class="mono">$' + r.price + '</td><td>' + r.count + ' empresas</td>' +
          '<td class="mono">$' + sub.toFixed(0) + '/mes</td><td><div class="imp-bar"><span style="width:' + pct + '%"></span></div></td></tr>';
      }).join('') || '<tr><td colspan="4" class="imp-empty">Sin datos</td></tr>';
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function loadInteligencia() {
    var body = $('intel-body');
    setLoading(body, true);
    Promise.all([
      api('/overview', {}, API_V1),
      api('/ai-health', {}, API_V1).catch(function () { return {}; }),
      api('/orphan-staff', {}, API_V1).catch(function () { return { orphans: [] }; }),
    ]).then(function (arr) {
      var ov = arr[0];
      var ai = arr[1];
      var orphan = arr[2];
      var orphans = orphan.orphans || orphan.users || [];
      var aiOk = ai && ai.status === 'ok';
      body.innerHTML =
        '<div class="imp-intel-grid">' +
        '<div class="imp-card"><div class="imp-card-head"><span class="imp-card-title">Motor IA</span></div><div class="imp-card-body">' +
        '<div class="imp-intel-stat"><span>Patrones autolearn activos</span><span>' + (ov.autolearn_active || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Cooldowns activos</span><span>' + (ov.cooldowns_active || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Staff con trust score</span><span>' + (ov.staff_with_trust || 0) + '</span></div>' +
        '<div class="imp-intel-stat"><span>Estado IA</span><span>' + (aiOk ? 'OK' : (ai.status || '—')) + '</span></div>' +
        '</div></div>' +
        '<div class="imp-card"><div class="imp-card-head"><span class="imp-card-title">Staff sin empresa</span>' +
        '<span class="imp-badge ' + (orphans.length ? 'imp-badge-warn' : 'imp-badge-ok') + '">' + orphans.length + '</span></div>' +
        '<div class="imp-card-body">' +
        (orphans.length ? orphans.slice(0, 6).map(function (o) {
          return '<div class="imp-list-item"><strong>' + esc(o.username) + '</strong> <span class="mono">#' + o.id + '</span> · ' + esc((o.roles || []).join(', ')) + '</div>';
        }).join('') : '<p class="imp-cell-muted">Nadie pendiente</p>') +
        (orphans.length ? '<button type="button" class="imp-btn imp-btn-gold imp-btn-sm" style="margin-top:14px" onclick="Imp.navigate(\'migraciones\')">Corregir en migraciones</button>' : '') +
        '</div></div>' +
        '<div class="imp-card"><div class="imp-card-head"><span class="imp-card-title">Mantenimiento</span></div><div class="imp-card-body">' +
        '<p class="imp-cell-muted" style="margin-bottom:12px">Simula limpieza de datos sin aplicar cambios.</p>' +
        '<button type="button" class="imp-btn imp-btn-ghost imp-btn-sm" onclick="Imp.runMaintenanceDry()">Ejecutar dry-run</button></div></div>' +
        '</div>';
      setLoading(body, false);
    }).catch(function (e) {
      setLoading(body, false);
      toast(e.message, 'err');
    });
  }

  function runMaintenanceDry() {
    api('/maintenance/dryrun', {}, API_V1).then(function (d) {
      openModal('Mantenimiento (dry-run)', '<pre class="imp-pre">' + esc(JSON.stringify(d, null, 2)) + '</pre>',
        '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cerrar</button>');
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function extendCompany(cid) {
    api('/companies/' + cid + '/extend', { method: 'POST', body: JSON.stringify({ days: 30 }) })
      .then(function () { toast('+' + 30 + ' días aplicados', 'ok'); loadCartera(); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function toggleSuspend(cid, current) {
    var next = (current === 'active') ? 'suspended' : 'active';
    if (!confirm('¿Cambiar estado a ' + next + '?')) return;
    api('/companies/' + cid + '/suspend', { method: 'POST', body: JSON.stringify({ status: next }) })
      .then(function () { toast('Estado: ' + next, 'ok'); loadCartera(); })
      .catch(function (e) { toast(e.message, 'err'); });
  }

  function openCompanyMenu(cid) {
    var c = state.companies.find(function (x) { return x.id === cid; });
    var name = c ? c.name : ('Empresa #' + cid);
    var st = c ? (c.subscription_status || '').toLowerCase() : '';
    openModal('Gestionar empresa',
      '<p class="imp-cell-muted" style="margin-bottom:16px"><strong>' + esc(name) + '</strong> · ID ' + cid + '</p>' +
      '<div class="imp-form-actions" style="flex-direction:column;align-items:stretch">' +
      '<button type="button" class="imp-btn imp-btn-ghost" onclick="Imp.closeModal();Imp.extendCompany(' + cid + ')">Extender 30 días</button>' +
      '<button type="button" class="imp-btn imp-btn-ghost" onclick="Imp.closeModal();Imp.openPlanPicker(' + cid + ')">Cambiar plan</button>' +
      '<button type="button" class="imp-btn imp-btn-ghost" onclick="Imp.closeModal();Imp.companyToken(' + cid + ')">Generar token registro</button>' +
      '<button type="button" class="imp-btn imp-btn-rose" onclick="Imp.closeModal();Imp.toggleSuspend(' + cid + ',' + JSON.stringify(st) + ')">' +
      (st === 'active' ? 'Suspender cuenta' : 'Reactivar cuenta') + '</button></div>',
      '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cerrar</button>');
  }

  function openUserMenu(uid) {
    var u = state.migUsers.find(function (x) { return x.id === uid; });
    var label = u ? u.username : ('#' + uid);
    openModal('Usuario · ' + esc(label),
      '<p class="imp-cell-muted">ID ' + uid + (u && u.email ? ' · ' + esc(u.email) : '') + '</p>',
      '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cerrar</button>' +
      '<button type="button" class="imp-btn imp-btn-ghost" id="modal-user-reset">Reset contraseña</button>' +
      '<button type="button" class="imp-btn imp-btn-gold" id="modal-user-promote">Crear empresa nueva</button>');
    $('modal-user-reset').onclick = function () { closeModal(); resetPw(uid); };
    $('modal-user-promote').onclick = function () { closeModal(); promoteUser(uid); };
  }

  function companyToken(cid) {
    api('/tokens/company', {
      method: 'POST',
      body: JSON.stringify({ company_id: cid, expires_hours: 72, description: 'Token SA empresa #' + cid }),
    }).then(function (d) {
      openModal('Token empresa #' + cid,
        '<p class="imp-hint">Link de registro staff:</p><div class="imp-token-box">' + esc(d.register_url) + '</div>',
        '<button type="button" class="imp-btn imp-btn-gold" data-copy="' + esc(d.register_url) + '" onclick="Imp.copyFromBtn(this)">Copiar link</button>');
    }).catch(function (e) { toast(e.message, 'err'); });
  }

  function resetPw(uid) {
    openModal('Reset contraseña · #' + uid,
      '<p>Se generará una contraseña nueva y temporal.</p>',
      '<button type="button" class="imp-btn imp-btn-ghost" data-close="1">Cancelar</button>' +
      '<button type="button" class="imp-btn imp-btn-rose" id="modal-reset-btn">Generar</button>');
    $('modal-reset-btn').onclick = function () {
      api('/users/' + uid + '/reset-password', { method: 'POST', body: '{}' })
        .then(function (d) {
          closeModal();
          openModal('Nueva contraseña',
            '<code style="font-size:18px">' + esc(d.password) + '</code>',
            '<button type="button" class="imp-btn imp-btn-gold" data-copy="' + esc(d.password) + '" onclick="Imp.copyFromBtn(this)">Copiar</button>');
        }).catch(function (e) { toast(e.message, 'err'); });
    };
  }

  /* ── Búsqueda global ── */
  function initSearch() {
    var inp = $('imp-search-input');
    var drop = $('imp-search-results');
    if (!inp || !drop) return;
    var timer;
    var activeIdx = -1;

    function hideDrop() {
      drop.classList.remove('open');
      drop.innerHTML = '';
      activeIdx = -1;
    }

    function renderResults(results) {
      if (!results.length) {
        drop.innerHTML = '<div class="imp-search-empty">Sin resultados</div>';
        drop.classList.add('open');
        return;
      }
      drop.innerHTML = results.map(function (r, i) {
        return '<button type="button" class="imp-search-item" data-i="' + i + '" data-view="' + esc(r.view) + '">' +
          '<span class="imp-search-type">' + esc(r.type) + '</span>' +
          '<span class="imp-search-label">' + esc(r.label) + '</span>' +
          (r.sub ? '<span class="imp-search-sub">' + esc(r.sub) + '</span>' : '') +
          '</button>';
      }).join('');
      drop.classList.add('open');
      drop.querySelectorAll('.imp-search-item').forEach(function (btn) {
        btn.addEventListener('click', function () {
          navigate(btn.dataset.view);
          hideDrop();
          inp.value = '';
        });
      });
    }

    inp.addEventListener('input', function () {
      clearTimeout(timer);
      var q = inp.value.trim();
      if (q.length < 2) { hideDrop(); return; }
      timer = setTimeout(function () {
        api('/quick-search?q=' + encodeURIComponent(q)).then(function (d) {
          renderResults(d.results || []);
        });
      }, 220);
    });

    inp.addEventListener('keydown', function (e) {
      var items = drop.querySelectorAll('.imp-search-item');
      if (e.key === 'Escape') { hideDrop(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIdx = Math.min(activeIdx + 1, items.length - 1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIdx = Math.max(activeIdx - 1, 0);
      } else if (e.key === 'Enter' && activeIdx >= 0 && items[activeIdx]) {
        e.preventDefault();
        items[activeIdx].click();
        return;
      } else return;
      items.forEach(function (el, i) { el.classList.toggle('active', i === activeIdx); });
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.imp-search-wrap')) hideDrop();
    });

    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inp.focus();
      }
    });
  }

  function initMobile() {
    var menuBtn = $('imp-menu-btn');
    if (menuBtn) {
      menuBtn.addEventListener('click', function () {
        document.body.classList.toggle('imp-mobile-open');
      });
    }
    var overlay = $('imp-sidebar-overlay');
    if (overlay) {
      overlay.addEventListener('click', function () {
        document.body.classList.remove('imp-mobile-open');
      });
    }
  }

  function initCarteraFilter() {
    var inp = $('cartera-filter');
    if (!inp) return;
    inp.addEventListener('input', function () {
      state.carteraFilter = inp.value.trim();
      renderCartera();
    });
  }

  window.Imp = {
    navigate: navigate,
    toast: toast,
    copyText: copyText,
    copyFromBtn: copyFromBtn,
    revokeFromBtn: revokeFromBtn,
    closeModal: closeModal,
    attachOne: attachOne,
    bulkAttach: bulkAttach,
    toggleMigSelectAll: toggleMigSelectAll,
    createGiftUser: createGiftUser,
    suggestGiftUsername: suggestGiftUsername,
    createSorteoTokens: createSorteoTokens,
    revokeToken: revokeToken,
    downloadLines: downloadLines,
    openApplyPlan: openApplyPlan,
    openPlanPicker: openPlanPicker,
    extendCompany: extendCompany,
    toggleSuspend: toggleSuspend,
    openCompanyMenu: openCompanyMenu,
    openUserMenu: openUserMenu,
    companyToken: companyToken,
    resetPw: resetPw,
    promoteUser: promoteUser,
    runMaintenanceDry: runMaintenanceDry,
    refreshAll: function () {
      refreshCompanies().then(function () {
        loadView(state.view);
        toast('Datos actualizados', 'ok');
      });
    },
  };

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.imp-nav-item').forEach(function (btn) {
      btn.addEventListener('click', function () { navigate(btn.dataset.view); });
    });
    document.querySelectorAll('[data-quick]').forEach(function (btn) {
      btn.addEventListener('click', function () { navigate(btn.dataset.quick); });
    });
    initSearch();
    initMobile();
    initCarteraFilter();
    var hash = (location.hash || '').replace('#', '');
    navigate(hash && VIEW_TITLES[hash] ? hash : 'inicio');
  });
})();
