/**
 * Control Imperial — permisos totales + God Mode UI
 */
(function () {
  'use strict';

  var _catalog = null;
  var _editUserId = null;
  var _editOverrides = {};
  var _editRoles = [];

  function api(path, opts) {
    opts = opts || {};
    return fetch('/aspers-sa/api' + path, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      method: opts.method || 'GET',
      body: opts.body || undefined,
    }).then(function (r) {
      if (r.status === 401) {
        location.href = '/aspers-sa';
        throw new Error('401');
      }
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
        return d;
      });
    });
  }

  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function toast(msg, type) {
    if (typeof showToast === 'function') showToast(msg, type || 'ok');
    else if (window.saToast) window.saToast(msg, type === 'err' ? 'err' : 'ok');
    else alert(msg);
  }

  function roleClass(r) {
    if (r === 'admin' || r === 'administrador') return 'admin';
    if (r === 'owner') return 'owner';
    return '';
  }

  window.loadPoder = async function loadPoder() {
    try {
      if (!_catalog) _catalog = await api('/permissions/catalog');
      var usersData = await api('/permissions/users');
      renderPowerCards(usersData.users || []);
      renderMatrix(_catalog);
      await loadGodMode();
      await loadImperialAudit();
    } catch (e) {
      console.error(e);
      toast('Error cargando Poder Imperial: ' + e.message, 'err');
    }
  };

  function renderPowerCards(users) {
    var grid = document.getElementById('sa-power-grid');
    if (!grid) return;
    if (!users.length) {
      grid.innerHTML = '<div class="empty">Sin usuarios</div>';
      return;
    }
    grid.innerHTML = users.slice(0, 48).map(function (u) {
      var roles = (u.roles || []).map(function (r) {
        return '<span class="sa-role-chip ' + roleClass(r) + '">' + esc(r) + '</span>';
      }).join('');
      return [
        '<div class="sa-power-card', (u.is_active ? '' : ' inactive'), '" onclick="saOpenUserEditor(', u.id, ')">',
        '<div class="sa-power-card-head">',
        '<div><div class="sa-power-name">', esc(u.username), '</div>',
        '<div class="sa-power-meta">', esc(u.company_name || 'Individual'), '</div></div>',
        '<span class="mono" style="font-size:11px;color:var(--gold-l)">#', u.id, '</span></div>',
        '<div class="sa-power-bar"><div class="sa-power-bar-fill" style="width:', u.power_level, '%"></div></div>',
        '<div style="font-size:10px;color:var(--text-d);margin-bottom:8px">', u.permission_count, ' permisos · power ', u.power_level, '</div>',
        '<div class="sa-power-roles">', roles, '</div></div>',
      ].join('');
    }).join('');
  }

  function renderMatrix(cat) {
    var tb = document.getElementById('sa-matrix-body');
    if (!tb || !cat) return;
    var lastCat = '';
    var html = '';
    (cat.matrix || []).forEach(function (row) {
      if (row.category !== lastCat) {
        lastCat = row.category;
        html += '<tr class="cat-row"><td colspan="' + (1 + (cat.roles || []).length) + '">' + esc(row.category) + '</td></tr>';
      }
      html += '<tr><td>' + esc(row.label) + '</td>';
      (cat.roles || []).forEach(function (role) {
        var yes = row.roles && row.roles[role.key];
        var perm = (cat.permissions || []).find(function (p) { return p.key === row.key; });
        var cls = yes ? (perm && perm.danger ? 'sa-cell-danger sa-cell-yes' : 'sa-cell-yes') : 'sa-cell-no';
        html += '<td class="' + cls + '">' + (yes ? '●' : '·') + '</td>';
      });
      html += '</tr>';
    });
    tb.innerHTML = html;
    var head = document.getElementById('sa-matrix-head');
    if (head) {
      head.innerHTML = '<tr><th>Permiso</th>' + (cat.roles || []).map(function (r) {
        return '<th>' + esc(r.label) + '</th>';
      }).join('') + '</tr>';
    }
  }

  window.loadGodMode = async function loadGodMode() {
    var d = await api('/god-mode/flags');
    var grid = document.getElementById('sa-god-grid');
    if (!grid) return;
    grid.innerHTML = (d.definitions || []).map(function (def) {
      var val = (d.flags || {})[def.key];
      var isText = def.type === 'text';
      var isOn = isText ? !!(val && String(val).trim()) : !!val;
      if (isText) {
        return [
          '<div class="sa-god-toggle', (isOn ? ' is-on' : ''), '" style="grid-column:1/-1">',
          '<span class="sa-god-icon">', def.icon, '</span>',
          '<div class="sa-god-body">',
          '<div class="sa-god-label">', esc(def.label), '</div>',
          '<p class="sa-god-desc">', esc(def.desc), '</p>',
          '<input type="text" class="sa-god-text-input" data-flag="', def.key, '" placeholder="Mensaje para todo el panel…" value="', esc(val || ''), '">',
          '</div></div>',
        ].join('');
      }
      return [
        '<div class="sa-god-toggle', (isOn ? ' is-on' : ''), (def.danger ? ' danger' : ''), '">',
        '<span class="sa-god-icon">', def.icon, '</span>',
        '<div class="sa-god-body">',
        '<div class="sa-god-label">', esc(def.label), '</div>',
        '<p class="sa-god-desc">', esc(def.desc), '</p></div>',
        '<label class="sa-switch"><input type="checkbox" data-flag="', def.key, '"', (isOn ? ' checked' : ''), '><span class="sa-switch-slider"></span></label>',
        '</div>',
      ].join('');
    }).join('');
  };

  window.saSaveGodMode = async function saSaveGodMode() {
    var flags = {};
    document.querySelectorAll('#sa-god-grid [data-flag]').forEach(function (el) {
      var k = el.getAttribute('data-flag');
      if (el.type === 'checkbox') flags[k] = el.checked;
      else flags[k] = el.value;
    });
    try {
      await api('/god-mode/flags', { method: 'PUT', body: JSON.stringify({ flags: flags }) });
      toast('God Mode actualizado — efecto inmediato', 'ok');
      await loadGodMode();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  async function loadImperialAudit() {
    var tb = document.getElementById('sa-imperial-audit-body');
    if (!tb) return;
    try {
      var d = await api('/imperial-audit?limit=30');
      if (!d.rows || !d.rows.length) {
        tb.innerHTML = '<tr><td colspan="4" class="empty">Sin acciones imperiales aún</td></tr>';
        return;
      }
      tb.innerHTML = d.rows.map(function (r) {
        return '<tr><td class="mono">' + esc((r.created_at || '').slice(0, 19)) + '</td>' +
          '<td><span class="badge badge-info">' + esc(r.action) + '</span></td>' +
          '<td class="mono">' + esc(r.target_type || '') + ' ' + esc(r.target_id || '') + '</td>' +
          '<td class="mono">' + esc(r.detail || '') + '</td></tr>';
      }).join('');
    } catch (e) {
      tb.innerHTML = '<tr><td colspan="4" class="empty">' + esc(e.message) + '</td></tr>';
    }
  }

  function renderUserEditor(d) {
    var u = d.user;
    var perms = d.permissions || {};
    _editRoles = (perms.roles || []).slice();
    _editOverrides = Object.assign({}, perms.overrides || {});
    var assignable = (_catalog && _catalog.assignable_roles) || [];
    var rolePicker = assignable.map(function (r) {
      var on = _editRoles.indexOf(r) >= 0;
      return '<button type="button" class="sa-role-pick' + (on ? ' is-on' : '') + '" data-role="' + r + '" onclick="saToggleRole(\'' + r + '\')">' + r + '</button>';
    }).join('');
    var permList = (_catalog.permissions || []).map(function (p) {
      var has = (perms.effective || []).indexOf(p.key) >= 0;
      var ov = _editOverrides[p.key];
      var cls = ov === 'deny' ? 'denied' : (ov === 'grant' ? 'granted' : (has ? 'has' : ''));
      return '<div class="sa-perm-item ' + cls + '" data-pk="' + p.key + '" onclick="saCycleOverride(\'' + p.key + '\')">' +
        '<span>' + (has ? '✓' : '·') + '</span> ' + esc(p.label) + '</div>';
    }).join('');
    var companies = (d.companies || []).map(function (c) {
      var sel = u.company_id === c.id ? ' selected' : '';
      return '<option value="' + c.id + '"' + sel + '>' + esc(c.name) + '</option>';
    }).join('');
    document.getElementById('poder-user-title').textContent = u.username + ' · Power ' + (perms.power_level || 0);
    document.getElementById('poder-user-body').innerHTML =
      '<div class="sa-role-picker">' + rolePicker + '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">' +
      '<label style="font-size:12px">Email<input id="poder-email" type="email" value="' + esc(u.email || '') + '" style="width:100%;margin-top:4px;padding:8px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text)"></label>' +
      '<label style="font-size:12px">Empresa<select id="poder-company" style="width:100%;margin-top:4px;padding:8px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text)"><option value="">— Individual —</option>' + companies + '</select></label>' +
      '</div>' +
      '<label style="font-size:12px;display:block;margin-bottom:14px">Nueva contraseña (opcional)<input id="poder-pass" type="password" placeholder="Dejar vacío = no cambiar" style="width:100%;margin-top:4px;padding:8px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;color:var(--text)"></label>' +
      '<div style="font-family:JetBrains Mono,monospace;font-size:9px;letter-spacing:1.2px;color:var(--text-d);margin-bottom:8px">PERMISOS · click para grant/deny override</div>' +
      '<div class="sa-perm-list" id="poder-perm-list">' + permList + '</div>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px">' +
      '<button type="button" class="btn btn-red btn-sm" onclick="saSaveUserPoder()">Guardar cambios</button>' +
      '<button type="button" class="btn btn-outline btn-sm" onclick="saToggleUserActive(' + !u.is_active + ')">' + (u.is_active ? 'Desactivar' : 'Activar') + '</button>' +
      '<button type="button" class="btn btn-amber btn-sm" onclick="saImpersonateUser()">👁 Ver como este user</button>' +
      '</div>';
  }

  window.saToggleRole = function (role) {
    var i = _editRoles.indexOf(role);
    if (i >= 0) _editRoles.splice(i, 1);
    else _editRoles.push(role);
    document.querySelectorAll('.sa-role-pick[data-role="' + role + '"]').forEach(function (b) {
      b.classList.toggle('is-on', _editRoles.indexOf(role) >= 0);
    });
  };

  window.saCycleOverride = function (pk) {
    var cur = _editOverrides[pk];
    if (!cur) _editOverrides[pk] = 'grant';
    else if (cur === 'grant') _editOverrides[pk] = 'deny';
    else delete _editOverrides[pk];
    saOpenUserEditor(_editUserId);
  };

  window.saOpenUserEditor = async function saOpenUserEditor(uid) {
    _editUserId = uid;
    var modal = document.getElementById('modal-poder-user');
    if (!modal) return;
    modal.classList.add('open');
    document.getElementById('poder-user-body').innerHTML = '<div class="empty">Cargando…</div>';
    try {
      if (!_catalog) _catalog = await api('/permissions/catalog');
      var d = await api('/permissions/users/' + uid);
      renderUserEditor(d);
    } catch (e) {
      document.getElementById('poder-user-body').innerHTML = '<div class="alert-box red">' + esc(e.message) + '</div>';
    }
  };

  window.saSaveUserPoder = async function saSaveUserPoder() {
    if (!_editUserId) return;
    try {
      await api('/permissions/users/' + _editUserId + '/roles', {
        method: 'PUT',
        body: JSON.stringify({ roles: _editRoles }),
      });
      await api('/permissions/users/' + _editUserId + '/overrides', {
        method: 'PUT',
        body: JSON.stringify({ overrides: _editOverrides }),
      });
      var patch = {
        email: document.getElementById('poder-email').value,
        company_id: document.getElementById('poder-company').value || null,
      };
      var pass = document.getElementById('poder-pass').value;
      if (pass) patch.password = pass;
      await api('/permissions/users/' + _editUserId, { method: 'PATCH', body: JSON.stringify(patch) });
      toast('Usuario actualizado', 'ok');
      document.getElementById('modal-poder-user').classList.remove('open');
      loadPoder();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  window.saToggleUserActive = async function saToggleUserActive(active) {
    try {
      await api('/permissions/users/' + _editUserId, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !!active }),
      });
      toast(active ? 'Usuario activado' : 'Usuario desactivado', 'ok');
      saOpenUserEditor(_editUserId);
      loadPoder();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  window.saImpersonateUser = async function saImpersonateUser() {
    if (!_editUserId) return;
    if (!confirm('¿Abrir sesión en /panel como este usuario? (5 min, queda auditado)')) return;
    try {
      var d = await api('/permissions/users/' + _editUserId + '/impersonate', { method: 'POST', body: '{}' });
      window.open(d.url, '_blank');
      toast('Impersonación: ' + d.username, 'info');
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  window.saCreateUserQuick = async function saCreateUserQuick() {
    var username = prompt('Username nuevo:');
    if (!username) return;
    var password = prompt('Contraseña (mín 6):');
    if (!password || password.length < 6) { toast('Contraseña inválida', 'err'); return; }
    var roles = prompt('Roles separados por coma (ej: staff,helper):', 'user');
    try {
      await api('/permissions/users/create', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), password: password, roles: (roles || 'user').split(',').map(function (s) { return s.trim(); }) }),
      });
      toast('Usuario ' + username + ' creado', 'ok');
      loadPoder();
    } catch (e) {
      toast(e.message, 'err');
    }
  };

  window.saClosePoderModal = function () {
    var m = document.getElementById('modal-poder-user');
    if (m) m.classList.remove('open');
  };
})();
