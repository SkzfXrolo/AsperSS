/**
 * SuperAdmin — Imperial UI enhancements
 */
(function () {
  'use strict';

  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  }

  ready(function () {
    injectToastHost();
    injectSessionBar();
    injectCmdK();
    injectHelpOverlay();
    initSidebarCollapse();
    initMobileNav();
    initUtcClock();
    initVersionFooter();
    initTableSeverity();
    initFilterChips();
    wrapFetchToasts();
    initKeyboardShortcuts();
    enhanceExportButtons();
    patchLoginRateLimit();
  });

  window.saToast = function (msg, type) {
    var host = document.getElementById('sa-toast-host');
    if (!host) return;
    var t = document.createElement('div');
    t.className = 'sa-toast sa-toast--' + (type === 'err' ? 'err' : 'ok');
    t.textContent = msg;
    host.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  };

  function injectToastHost() {
    if (document.getElementById('sa-toast-host')) return;
    var h = document.createElement('div');
    h.id = 'sa-toast-host';
    h.className = 'sa-toast-host';
    document.body.appendChild(h);
  }

  function injectSessionBar() {
    var bar = document.createElement('div');
    bar.className = 'sa-session-bar';
    bar.id = 'sa-session-bar';
    document.body.appendChild(bar);
    var mins = 60;
    var start = Date.now();
    setInterval(function () {
      var elapsed = (Date.now() - start) / 60000;
      var pct = Math.max(0, 100 - (elapsed / mins) * 100);
      bar.style.setProperty('--sa-session-pct', pct + '%');
    }, 30000);
  }

  function injectCmdK() {
    var overlay = document.createElement('div');
    overlay.className = 'sa-cmdk-overlay';
    overlay.id = 'sa-cmdk';
    overlay.innerHTML =
      '<div class="sa-cmdk-box">' +
      '<input class="sa-cmdk-input" type="text" placeholder="Buscar empresa, usuario, scan… (Esc para cerrar)" autocomplete="off">' +
      '<div class="sa-cmdk-results"></div></div>';
    document.body.appendChild(overlay);
    var input = overlay.querySelector('.sa-cmdk-input');
    var results = overlay.querySelector('.sa-cmdk-results');

    function open() {
      overlay.classList.add('is-open');
      input.value = '';
      results.innerHTML = '';
      input.focus();
      loadSuggestions('');
    }
    function close() {
      overlay.classList.remove('is-open');
    }

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
    });
    input.addEventListener('input', function () {
      loadSuggestions(input.value.trim());
    });

    function loadSuggestions(q) {
      results.innerHTML = '<div class="sa-cmdk-item">Escribe para buscar…</div>';
      if (!q) return;
      fetch('/api/sa/search?q=' + encodeURIComponent(q))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          results.innerHTML = '';
          var items = (d.results || d.items || []).slice(0, 12);
          if (!items.length) {
            results.innerHTML = '<div class="sa-cmdk-item">Sin resultados</div>';
            return;
          }
          items.forEach(function (it) {
            var row = document.createElement('div');
            row.className = 'sa-cmdk-item';
            row.textContent = (it.label || it.name || it.id) + (it.type ? ' · ' + it.type : '');
            row.addEventListener('click', function () {
              if (it.url) window.location.href = it.url;
              else if (it.section) showSection(it.section);
              else if (it.user_id && typeof saOpenUserEditor === 'function') {
                showSection('poder');
                setTimeout(function () { saOpenUserEditor(it.user_id); }, 400);
              }
              close();
            });
            results.appendChild(row);
          });
        })
        .catch(function () {
          results.innerHTML = '<div class="sa-cmdk-item">Buscar en tablas visibles…</div>';
          document.querySelectorAll('table tbody tr').forEach(function (tr) {
            if (tr.textContent.toLowerCase().indexOf(q.toLowerCase()) >= 0) {
              var row = document.createElement('div');
              row.className = 'sa-cmdk-item';
              row.textContent = tr.textContent.slice(0, 80);
              row.addEventListener('click', function () { tr.scrollIntoView({ behavior: 'smooth' }); close(); });
              results.appendChild(row);
            }
          });
        });
    }

    window.saOpenCmdK = open;
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        open();
      }
    });
  }

  function showSection(id) {
    if (typeof switchTab === 'function') {
      switchTab(id);
      return;
    }
    var btn = document.querySelector('[data-tab="' + id + '"], [data-section="' + id + '"]');
    if (btn) btn.click();
  }

  function injectHelpOverlay() {
    var o = document.createElement('div');
    o.className = 'sa-help-overlay';
    o.id = 'sa-help';
    o.innerHTML =
      '<div class="sa-help-card">' +
      '<h3 style="margin-bottom:1rem;color:var(--text)">Atajos SuperAdmin</h3>' +
      '<p><kbd>Ctrl</kbd>+<kbd>K</kbd> Búsqueda global</p>' +
      '<p style="margin-top:.5rem"><kbd>Ctrl</kbd>+<kbd>K</kbd> → escribí un usuario → editor de permisos</p>' +
      '<p style="margin-top:.5rem">Tab <strong>Poder Imperial</strong> → God Mode + matriz + impersonar</p>' +
      '<p style="margin-top:.5rem"><kbd>?</kbd> Esta ayuda</p>' +
      '<p style="margin-top:.5rem"><kbd>Esc</kbd> Cerrar modales</p>' +
      '<button type="button" style="margin-top:1.5rem;padding:.5rem 1rem;background:var(--red);border:none;border-radius:8px;color:#fff;cursor:pointer">Cerrar</button>' +
      '</div>';
    document.body.appendChild(o);
    o.querySelector('button').addEventListener('click', function () { o.classList.remove('is-open'); });
    o.addEventListener('click', function (e) { if (e.target === o) o.classList.remove('open'); });
  }

  function initKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
      if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        var tag = (document.activeElement || {}).tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA') return;
        e.preventDefault();
        document.getElementById('sa-help').classList.toggle('is-open');
      }
    });
  }

  function initSidebarCollapse() {
    var sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sa-collapse-btn';
    btn.title = 'Colapsar sidebar';
    btn.textContent = '‹';
    sidebar.style.position = 'relative';
    sidebar.appendChild(btn);
    btn.addEventListener('click', function () {
      document.body.classList.toggle('sa-sidebar-collapsed');
      btn.textContent = document.body.classList.contains('sa-sidebar-collapsed') ? '›' : '‹';
    });
  }

  function initMobileNav() {
    if (window.innerWidth > 1023) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sa-hamburger';
    btn.innerHTML = '☰';
    btn.setAttribute('aria-label', 'Menú');
    document.body.appendChild(btn);
    btn.addEventListener('click', function () {
      document.body.classList.toggle('sa-mobile-open');
    });
  }

  function initUtcClock() {
    var header = document.querySelector('.topbar, .header-bar, header');
    if (!header) return;
    var clock = document.createElement('span');
    clock.style.cssText = 'font-family:JetBrains Mono,monospace;font-size:.75rem;color:var(--text-m);margin-left:auto';
    function tick() {
      var d = new Date();
      clock.textContent = 'UTC ' + d.toISOString().slice(11, 19);
    }
    tick();
    setInterval(tick, 1000);
    header.appendChild(clock);
  }

  function initVersionFooter() {
    fetch('/api/version')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var foot = document.querySelector('.sidebar-footer, .sidebar');
        if (!foot || !d.version) return;
        var el = document.createElement('div');
        el.className = 'sidebar-footer-text';
        el.style.cssText = 'font-size:.7rem;color:var(--text-d);padding:.5rem';
        el.textContent = 'Scanner v' + d.version;
        foot.appendChild(el);
      })
      .catch(function () {});
  }

  function initTableSeverity() {
    document.querySelectorAll('table tbody tr').forEach(function (tr) {
      var t = tr.textContent.toUpperCase();
      if (t.indexOf('CRIT') >= 0) tr.classList.add('sa-row-crit');
      else if (t.indexOf('SOSP') >= 0) tr.classList.add('sa-row-sosp');
    });
  }

  function initFilterChips() {
    var tables = document.querySelectorAll('[data-sa-filterable]');
    if (!tables.length) return;
    tables.forEach(function (wrap) {
      var chips = document.createElement('div');
      chips.className = 'sa-filter-chips';
      ['Todas', 'Activas', 'Trial', 'Expiradas'].forEach(function (label, i) {
        var c = document.createElement('button');
        c.type = 'button';
        c.className = 'sa-filter-chip' + (i === 0 ? ' is-active' : '');
        c.textContent = label;
        c.addEventListener('click', function () {
          chips.querySelectorAll('.sa-filter-chip').forEach(function (x) { x.classList.remove('is-active'); });
          c.classList.add('is-active');
          saToast('Filtro: ' + label, 'ok');
        });
        chips.appendChild(c);
      });
      wrap.parentNode.insertBefore(chips, wrap);
    });
  }

  function wrapFetchToasts() {
    var orig = window.fetch;
    window.fetch = function () {
      return orig.apply(this, arguments).then(function (res) {
        if (res.ok && arguments[0] && String(arguments[0]).indexOf('/api/') >= 0) {
          var m = String(arguments[1] && arguments[1].method || 'GET').toUpperCase();
          if (m === 'POST' || m === 'PUT' || m === 'DELETE') {
            /* optional: saToast on success — too noisy, skip */
          }
        }
        return res;
      });
    };
  }

  function enhanceExportButtons() {
    document.querySelectorAll('button, a').forEach(function (el) {
      var txt = (el.textContent || '').toLowerCase();
      if (txt.indexOf('csv') >= 0 || txt.indexOf('export') >= 0) {
        el.addEventListener('click', function () {
          var orig = el.textContent;
          el.textContent = 'Generando…';
          el.disabled = true;
          setTimeout(function () {
            el.textContent = orig;
            el.disabled = false;
            saToast('Exportación lista', 'ok');
          }, 1500);
        });
      }
    });
  }

  function patchLoginRateLimit() {
    var err = document.querySelector('.error-message, .sa-login-error');
    if (!err) return;
    var m = err.textContent.match(/(\d+)\s*s/i);
    if (m) {
      err.classList.add('sa-rate-limit');
      var sec = parseInt(m[1], 10);
      var iv = setInterval(function () {
        sec--;
        if (sec <= 0) { clearInterval(iv); return; }
        err.textContent = 'Demasiados intentos — espera ' + sec + 's';
      }, 1000);
    }
  }
})();
