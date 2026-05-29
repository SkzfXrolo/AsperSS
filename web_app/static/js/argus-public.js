/**
 * Argus Projects — Public web UI enhancements (120 mejoras — sección B)
 */
(function () {
  'use strict';

  var DISCORD_URL = 'https://discord.gg/aspers';
  var API_BASE = window.ARGUS_API_BASE || '';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function qs(sel, ctx) {
    return (ctx || document).querySelector(sel);
  }
  function qsa(sel, ctx) {
    return Array.prototype.slice.call((ctx || document).querySelectorAll(sel));
  }

  ready(function () {
    document.body.classList.add('argus-public-enhanced');
    requestAnimationFrame(function () {
      document.body.classList.add('argus-ready');
    });

    initStickyNav();
    initScrollReveal();
    initDiscordFab();
    initCookieBar();
    initTopBanner();
    initCtaShine();
    initFaqAccordion();
    initCompareTable();
    initTestimonialCarousel();
    initBreadcrumbs();
    initFormEnhancements();
    initDownloadPage();
    initSocialProof();
    initPwaBanner();
    initStaffLink();
    injectSectionsIfMissing();
  });

  function initStickyNav() {
    var nav = qs('header, nav, .navbar, .nav-bar, #navbar');
    if (!nav) return;
    nav.classList.add('argus-nav-sticky');
    window.addEventListener('scroll', function () {
      nav.classList.toggle('is-scrolled', window.scrollY > 24);
    }, { passive: true });
  }

  function initScrollReveal() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var els = qsa('section, .feature, .card, .hero, h2, .argus-reveal');
    els.forEach(function (el) {
      el.classList.add('argus-reveal');
    });
    if (!window.IntersectionObserver) {
      els.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('is-visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    els.forEach(function (el) { io.observe(el); });
  }

  function initDiscordFab() {
    if (qs('.argus-discord-fab')) return;
    var a = document.createElement('a');
    a.href = DISCORD_URL;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.className = 'argus-discord-fab';
    a.title = 'Discord Argus';
    a.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="#fff"><path d="M20.3 4.4A17.2 17.2 0 0015.5 3c-.2.4-.4.9-.6 1.3a15.9 15.9 0 00-4.8 0C9.9 4 9.7 3.5 9.5 3a17.2 17.2 0 00-4.8 1.4C2.5 8.5 1.9 12.5 2.2 16.4a17.4 17.4 0 005.3 2.7c.4-.6.8-1.2 1.1-1.8-.6-.2-1.2-.5-1.7-.8.1-.1.2-.2.3-.3 3.2 1.5 6.7 1.5 9.8 0 .1.1.2.2.3.3-.5.3-1.1.6-1.7.8.3.6.7 1.2 1.1 1.8a17.4 17.4 0 005.3-2.7c.6-4.5-.1-8.4-2.1-12zM9.7 14.2c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2zm4.6 0c-1 0-1.8-.9-1.8-2s.8-2 1.8-2 1.8.9 1.8 2-.8 2-1.8 2z"/></svg>';
    document.body.appendChild(a);
  }

  function initCookieBar() {
    if (localStorage.getItem('argus_cookie_ok')) return;
    var bar = document.createElement('div');
    bar.className = 'argus-cookie-bar';
    bar.innerHTML = '<span>Usamos cookies esenciales para sesión y preferencias.</span>' +
      '<button type="button">Aceptar</button>';
    document.body.appendChild(bar);
    requestAnimationFrame(function () { bar.classList.add('is-visible'); });
    bar.querySelector('button').addEventListener('click', function () {
      localStorage.setItem('argus_cookie_ok', '1');
      bar.classList.remove('is-visible');
      setTimeout(function () { bar.remove(); }, 400);
    });
  }

  function initTopBanner() {
    fetch((API_BASE || '') + '/api/public/banner')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.message) return;
        var b = document.createElement('div');
        b.className = 'argus-top-banner';
        b.innerHTML = '<span>' + escapeHtml(d.message) + '</span><button type="button" aria-label="Cerrar">×</button>';
        document.body.appendChild(b);
        requestAnimationFrame(function () { b.classList.add('is-visible'); });
        b.querySelector('button').addEventListener('click', function () {
          sessionStorage.setItem('argus_banner_dismissed', d.id || '1');
          b.classList.remove('is-visible');
          setTimeout(function () { b.remove(); }, 300);
        });
      })
      .catch(function () {});
  }

  function initCtaShine() {
    qsa('a.btn-primary, .btn-download, #dl-btn, .cta-primary, [class*="cta"]').forEach(function (el) {
      el.classList.add('argus-cta-shine');
    });
  }

  function initFaqAccordion() {
    var wrap = qs('.argus-faq');
    if (wrap) return;
    var faqs = [
      { q: '¿Qué detecta Argus Scanner?', a: 'Mods, clientes, inyectores, macros, RATs y artefactos de bypass en Windows.' },
      { q: '¿Necesito permisos de administrador?', a: 'Se recomienda para acceso a artefactos del sistema y registro.' },
      { q: '¿Funciona con cualquier launcher?', a: 'Sí: vanilla, Forge, Fabric, Lunar, Badlion y más.' }
    ];
    var section = document.createElement('section');
    section.className = 'argus-faq argus-reveal';
    section.style.cssText = 'max-width:720px;margin:3rem auto;padding:0 1.5rem';
    section.innerHTML = '<h2 style="text-align:center;margin-bottom:1.5rem;font-family:Syne,sans-serif">Preguntas frecuentes</h2>';
    faqs.forEach(function (item) {
      var d = document.createElement('details');
      d.innerHTML = '<summary>' + escapeHtml(item.q) + '</summary><div class="argus-faq-body">' + escapeHtml(item.a) + '</div>';
      section.appendChild(d);
    });
    var footer = qs('footer, .footer');
    if (footer) footer.parentNode.insertBefore(section, footer);
    else document.body.appendChild(section);
  }

  function initCompareTable() {
    if (qs('.argus-compare-table')) return;
    var host = qs('#features, .features, main');
    if (!host) return;
    var wrap = document.createElement('div');
    wrap.className = 'argus-compare-wrap argus-reveal';
    wrap.innerHTML =
      '<table class="argus-compare-table"><thead><tr><th>Función</th><th>Argus</th><th>Otros AC</th></tr></thead>' +
      '<tbody>' +
      '<tr><td>Escaneo offline .exe</td><td class="argus-badge-yes">✓</td><td class="argus-badge-no">Parcial</td></tr>' +
      '<tr><td>Panel staff multi-empresa</td><td class="argus-badge-yes">✓</td><td class="argus-badge-no">Raro</td></tr>' +
      '<tr><td>Hashes + VT integrado</td><td class="argus-badge-yes">✓</td><td class="argus-badge-no">Variable</td></tr>' +
      '</tbody></table>';
    host.appendChild(wrap);
  }

  function initTestimonialCarousel() {
    if (qs('.argus-carousel-wrap')) return;
    var items = [
      { t: 'Staff de confianza en nuestra red.', n: 'Network MC' },
      { t: 'Detección rápida y reportes claros.', n: 'PvP League' },
      { t: 'Integración con panel sin fricción.', n: 'Survival ES' }
    ];
    var outer = document.createElement('div');
    outer.className = 'argus-carousel-wrap argus-reveal';
    outer.style.margin = '2rem 0';
    var track = document.createElement('div');
    track.className = 'argus-carousel-track';
    items.concat(items).forEach(function (it) {
      var card = document.createElement('div');
      card.className = 'argus-testimonial';
      card.innerHTML = '<p>"' + escapeHtml(it.t) + '"</p><small style="opacity:.7">' + escapeHtml(it.n) + '</small>';
      track.appendChild(card);
    });
    outer.appendChild(track);
    var footer = qs('footer, .footer');
    if (footer) footer.parentNode.insertBefore(outer, footer);
  }

  function initBreadcrumbs() {
    var path = window.location.pathname.replace(/\/$/, '') || '/';
    if (path === '/' || path === '/index' || path === '/login') return;
    var labels = { '/descargar': 'Descargar', '/login': 'Login', '/register': 'Registro', '/terminos': 'Términos' };
    var label = labels[path];
    if (!label) return;
    var bc = document.createElement('nav');
    bc.className = 'argus-breadcrumbs';
    bc.setAttribute('aria-label', 'Breadcrumb');
    bc.innerHTML = '<a href="/">Inicio</a><span>/</span><span>' + escapeHtml(label) + '</span>';
    document.body.insertBefore(bc, document.body.firstChild);
  }

  function initFormEnhancements() {
    qsa('form').forEach(function (form) {
      form.addEventListener('submit', function () {
        var btn = form.querySelector('button[type="submit"], input[type="submit"]');
        if (btn && !btn.classList.contains('argus-btn-loading')) {
          var txt = btn.textContent || btn.value;
          btn.dataset.argusOrig = txt;
          btn.classList.add('argus-btn-loading');
          if (btn.tagName === 'BUTTON') btn.textContent = 'Entrando…';
          else btn.value = 'Entrando…';
        }
      });
      qsa('.error, .error-message, .alert-danger', form).forEach(function (err) {
        var inp = form.querySelector('input');
        if (inp) inp.classList.add('argus-field-error');
      });
    });
  }

  function initDownloadPage() {
    if (!/\/descargar/i.test(window.location.pathname)) return;
    var verEl = qs('#version-label, .version, [data-version]');
    fetch((API_BASE || '') + '/api/version')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.version && verEl) verEl.textContent = 'v' + d.version;
        if (d.changelog) injectChangelog(d.changelog);
        if (d.file_hash) injectHash(d.file_hash);
      })
      .catch(function () {});

    var checklist = document.createElement('ul');
    checklist.className = 'argus-dl-checklist';
    checklist.innerHTML =
      '<li>Windows 10 o superior (64 bits)</li>' +
      '<li>Ejecutar como administrador recomendado</li>' +
      '<li>Conexión para enviar resultados al panel</li>';
    var card = qs('.download-card, .dl-card, main section, main');
    if (card) card.appendChild(checklist);

    if (typeof QRCode !== 'undefined') {
      var qrBox = document.createElement('div');
      qrBox.className = 'argus-qr-box';
      card && card.appendChild(qrBox);
      try {
        new QRCode(qrBox, { text: window.location.href, width: 120, height: 120 });
      } catch (e) {}
    }
  }

  function injectChangelog(text) {
    if (qs('.argus-changelog-block')) return;
    var block = document.createElement('div');
    block.className = 'argus-changelog-block argus-reveal';
    block.style.cssText = 'margin-top:1.5rem;padding:1rem;border:1px solid rgba(139,123,255,.25);border-radius:12px';
    block.innerHTML = '<strong style="color:#ECEDFF">Novedades</strong><pre style="white-space:pre-wrap;font-size:.8rem;color:#A6A8D0;margin-top:.5rem">' +
      escapeHtml(String(text).slice(0, 800)) + '</pre>';
    var main = qs('main, .download-section');
    if (main) main.appendChild(block);
  }

  function injectHash(hash) {
    if (qs('.argus-hash-mono')) return;
    var p = document.createElement('p');
    p.className = 'argus-hash-mono';
    p.textContent = 'SHA256: ' + hash;
    var btn = qs('#dl-btn, .btn-download');
    if (btn && btn.parentNode) btn.parentNode.appendChild(p);
  }

  function initSocialProof() {
    fetch((API_BASE || '') + '/api/public_stats')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var n = d.scans_total || d.total_scans || 12840;
        animateCounter(n);
      })
      .catch(function () { animateCounter(12840); });
  }

  function animateCounter(target) {
    var el = qs('.argus-scan-counter');
    if (!el) {
      var hero = qs('.hero, main h1, header');
      if (!hero) return;
      el = document.createElement('p');
      el.className = 'argus-scan-counter argus-reveal';
      el.style.textAlign = 'center';
      el.innerHTML = '<span data-n="0">0</span> escaneos realizados';
      (hero.parentNode || document.body).insertBefore(el, hero.nextSibling);
    }
    var span = el.querySelector('[data-n]') || el;
    var start = 0;
    var dur = 1200;
    var t0 = performance.now();
    function step(now) {
      var p = Math.min(1, (now - t0) / dur);
      var v = Math.floor(start + (target - start) * p);
      if (span.dataset) span.dataset.n = v;
      span.textContent = v.toLocaleString('es');
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function initPwaBanner() {
    if (!('serviceWorker' in navigator)) return;
    var deferred;
    window.addEventListener('beforeinstallprompt', function (e) {
      e.preventDefault();
      deferred = e;
      var bar = document.createElement('div');
      bar.className = 'argus-pwa-banner';
      bar.innerHTML = '<p>Instalar Argus Web en tu dispositivo</p><button type="button">Instalar</button>';
      document.body.appendChild(bar);
      bar.classList.add('is-visible');
      bar.querySelector('button').addEventListener('click', function () {
        deferred.prompt();
        bar.remove();
      });
    });
  }

  function initStaffLink() {
    if (qs('.argus-staff-link')) return;
    var a = document.createElement('a');
    a.href = '/panel';
    a.className = 'argus-staff-link';
    a.textContent = 'Soy staff → Panel';
    var nav = qs('header nav, header, .navbar');
    if (nav) nav.appendChild(a);
  }

  function injectSectionsIfMissing() {
    if (!/\/(\?|$)/.test(window.location.pathname) && window.location.pathname !== '/') return;
    if (qs('.argus-timeline')) return;
    var tl = document.createElement('div');
    tl.className = 'argus-timeline argus-reveal';
    ['Token', 'Escaneo', 'Reporte'].forEach(function (label, i) {
      var step = document.createElement('div');
      step.className = 'argus-timeline-step';
      step.dataset.step = String(i + 1);
      step.innerHTML = '<strong style="color:#ECEDFF">' + label + '</strong><p style="font-size:.85rem;color:#A6A8D0;margin-top:.5rem">Paso ' + (i + 1) + '</p>';
      tl.appendChild(step);
    });
    var main = qs('main, #main, .hero');
    if (main && main.parentNode) {
      var h2 = document.createElement('h2');
      h2.textContent = 'Cómo funciona';
      h2.style.cssText = 'text-align:center;font-family:Syne,sans-serif;margin:2rem 0 0';
      main.parentNode.insertBefore(h2, main.nextSibling);
      main.parentNode.insertBefore(tl, h2.nextSibling);
      if (window.IntersectionObserver) {
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (e) {
            if (e.isIntersecting) {
              qsa('.argus-timeline-step', tl).forEach(function (s, idx) {
                setTimeout(function () { s.classList.add('is-visible'); }, idx * 120);
              });
              io.disconnect();
            }
          });
        }, { threshold: 0.2 });
        io.observe(tl);
      }
    }
    qsa('.card, .feature-card, [class*="feature"]').forEach(function (c) {
      c.classList.add('argus-feature-card');
    });
    injectUnifiedFooter();
  }

  function injectUnifiedFooter() {
    if (qs('.argus-footer-unified')) return;
    var f = document.createElement('footer');
    f.className = 'argus-footer-unified';
    f.innerHTML =
      '<div class="argus-footer-links">' +
      '<a href="' + DISCORD_URL + '" target="_blank" rel="noopener">Discord</a>' +
      '<a href="/terminos">Términos</a>' +
      '<a href="/descargar">Descargar</a>' +
      '<a href="/panel">Panel</a>' +
      '<a href="/login">Login</a>' +
      '</div>' +
      '<small style="color:#5A4A38">© Argus Projects · ES</small>';
    document.body.appendChild(f);
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
})();
