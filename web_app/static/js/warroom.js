/* ============================================================
   ARGUS WAR ROOM — lógica en tiempo real
   Reusa el Socket.IO existente (evento 'notification') + API
   /api/warroom/overview y /api/warroom/summary.
   ============================================================ */
(function () {
  'use strict';

  // ---- Coordenadas por país (lat, lng — orden Leaflet). Capitales / hubs. ----
  var COUNTRY_COORDS = {
    'argentina': [-34.6, -58.4], 'ar': [-34.6, -58.4],
    'mexico': [19.4, -99.1], 'méxico': [19.4, -99.1], 'mx': [19.4, -99.1],
    'españa': [40.4, -3.7], 'espana': [40.4, -3.7], 'spain': [40.4, -3.7], 'es': [40.4, -3.7],
    'colombia': [4.7, -74.1], 'co': [4.7, -74.1],
    'chile': [-33.4, -70.6], 'cl': [-33.4, -70.6],
    'peru': [-12.0, -77.0], 'perú': [-12.0, -77.0], 'pe': [-12.0, -77.0],
    'venezuela': [10.5, -66.9], 've': [10.5, -66.9],
    'ecuador': [-0.2, -78.5], 'ec': [-0.2, -78.5],
    'bolivia': [-16.5, -68.1], 'bo': [-16.5, -68.1],
    'paraguay': [-25.3, -57.6], 'py': [-25.3, -57.6],
    'uruguay': [-34.9, -56.2], 'uy': [-34.9, -56.2],
    'brasil': [-15.8, -47.9], 'brazil': [-15.8, -47.9], 'br': [-15.8, -47.9],
    'estados unidos': [37.1, -95.7], 'united states': [37.1, -95.7], 'usa': [37.1, -95.7], 'us': [37.1, -95.7],
    'guatemala': [15.8, -90.2], 'gt': [15.8, -90.2],
    'honduras': [15.2, -86.2], 'hn': [15.2, -86.2],
    'el salvador': [13.8, -88.9], 'sv': [13.8, -88.9],
    'nicaragua': [12.9, -85.2], 'ni': [12.9, -85.2],
    'costa rica': [9.7, -83.8], 'cr': [9.7, -83.8],
    'panama': [8.5, -80.8], 'panamá': [8.5, -80.8], 'pa': [8.5, -80.8],
    'republica dominicana': [18.7, -70.2], 'dominican republic': [18.7, -70.2], 'do': [18.7, -70.2],
    'cuba': [21.5, -77.8], 'cu': [21.5, -77.8],
    'puerto rico': [18.2, -66.5], 'pr': [18.2, -66.5],
    'canada': [56.1, -106.3], 'canadá': [56.1, -106.3], 'ca': [56.1, -106.3],
    'francia': [46.6, 2.2], 'france': [46.6, 2.2], 'fr': [46.6, 2.2],
    'alemania': [51.1, 10.4], 'germany': [51.1, 10.4], 'de': [51.1, 10.4],
    'italia': [41.9, 12.6], 'italy': [41.9, 12.6], 'it': [41.9, 12.6],
    'portugal': [39.4, -8.2], 'pt': [39.4, -8.2],
    'reino unido': [55.4, -3.4], 'united kingdom': [55.4, -3.4], 'gb': [55.4, -3.4], 'uk': [55.4, -3.4]
  };

  function countryKey(country) {
    if (!country) return '';
    return String(country).trim().toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function coordsFor(country) {
    var key = countryKey(country);
    if (!key || key === 'desconocido' || key === 'unknown') return null;
    if (COUNTRY_COORDS[key]) return COUNTRY_COORDS[key];
    return null;
  }

  // ---- Estado ----
  var map = null, markersLayer = null;
  var charts = { h24: null, countries: null, verdicts: null };
  var activeScans = {};   // scan_id -> { who, country, started, el }
  var feedCount = 0;

  // ---- Clock ----
  function tickClock() {
    var el = document.getElementById('wr-clock');
    if (el) {
      var d = new Date();
      el.textContent = String(d.getHours()).padStart(2, '0') + ':' +
        String(d.getMinutes()).padStart(2, '0') + ':' +
        String(d.getSeconds()).padStart(2, '0');
    }
  }
  setInterval(tickClock, 1000); tickClock();

  // ---- Map ----
  function initMap() {
    if (typeof L === 'undefined') return;
    map = L.map('wr-map', {
      center: [10, -55], zoom: 3, minZoom: 2, maxZoom: 8,
      worldCopyJump: true, attributionControl: true, zoomControl: true
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap · © CARTO', subdomains: 'abcd', maxZoom: 19
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
    function fitMap() {
      try { map.invalidateSize(); } catch (e) {}
    }
    setTimeout(fitMap, 80);
    window.addEventListener('resize', fitMap);
  }

  function makePulseIcon(hit) {
    return L.divIcon({
      className: '', html: '<div class="wr-pulse' + (hit ? ' hit' : '') + '"></div>',
      iconSize: [14, 14], iconAnchor: [7, 7], popupAnchor: [0, -8]
    });
  }

  function renderMapPoints(points) {
    if (!map || !markersLayer) return;
    markersLayer.clearLayers();
    var plotted = 0;
    (points || []).forEach(function (p) {
      var c = coordsFor(p.country);
      if (!c) return;
      var hit = (p.hits || 0) > 0;
      L.marker(c, { icon: makePulseIcon(hit) })
        .bindPopup('<b>' + escapeHtml(p.country) + '</b><br>' + p.count + ' scan(s)' +
          (hit ? '<br><span style="color:#F4506E">⚠ ' + p.hits + ' detección(es)</span>' : ''))
        .addTo(markersLayer);
      plotted++;
    });
    var sub = document.getElementById('wr-map-sub');
    if (sub) sub.textContent = plotted ? (plotted + ' zonas activas') : 'esperando actividad…';
  }

  function flashMapPoint(country, hit) {
    if (!map || !markersLayer) return;
    var c = coordsFor(country);
    if (!c) return;
    var m = L.marker(c, { icon: makePulseIcon(hit) }).addTo(markersLayer);
    try { map.flyTo(c, Math.max(map.getZoom(), 4), { duration: 0.8 }); } catch (e) {}
    m.bindPopup('<b>' + escapeHtml(country || 'Desconocido') + '</b><br>SS en vivo').openPopup();
  }

  // ---- Feed ----
  function addFeed(opts) {
    var feed = document.getElementById('wr-feed');
    var empty = document.getElementById('wr-feed-empty');
    if (!feed) return;
    if (empty) empty.style.display = 'none';
    var item = document.createElement('div');
    item.className = 'wr-feed-item' + (opts.cls ? ' ' + opts.cls : '');
    var now = new Date();
    var t = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0') + ':' + String(now.getSeconds()).padStart(2, '0');
    item.innerHTML =
      '<div class="wr-fi-ico">' + (opts.ico || '🛰️') + '</div>' +
      '<div class="wr-fi-body">' +
        '<div class="wr-fi-title">' + escapeHtml(opts.title || '') + '</div>' +
        '<div class="wr-fi-meta">' + escapeHtml(opts.meta || '') + '</div>' +
      '</div>' +
      '<div class="wr-fi-time">' + t + '</div>';
    feed.insertBefore(item, feed.firstChild);
    feedCount++;
    while (feed.children.length > 60) feed.removeChild(feed.lastChild);
  }

  // ---- Active scans ----
  function addActive(scanId, who, country, startedIso) {
    if (!scanId) scanId = 'tmp-' + Date.now();
    if (activeScans[scanId]) return;
    var grid = document.getElementById('wr-active-grid');
    var empty = document.getElementById('wr-active-empty');
    if (empty) empty.style.display = 'none';
    var el = document.createElement('div');
    el.className = 'wr-as';
    el.innerHTML =
      '<div class="wr-as-who">' + escapeHtml(who || 'PC') + '</div>' +
      '<div class="wr-as-meta">' + escapeHtml(country || 'Desconocido') + ' · #' + scanId + '</div>' +
      '<div class="wr-as-timer" data-start="' + (startedIso || new Date().toISOString()) + '">00:00</div>';
    grid.appendChild(el);
    activeScans[scanId] = { who: who, country: country, started: startedIso || new Date().toISOString(), el: el };
    updateActiveSub();
  }

  function removeActive(scanId) {
    var a = activeScans[scanId];
    if (!a) return;
    if (a.el && a.el.parentNode) a.el.parentNode.removeChild(a.el);
    delete activeScans[scanId];
    var grid = document.getElementById('wr-active-grid');
    var empty = document.getElementById('wr-active-empty');
    if (empty && grid && grid.querySelectorAll('.wr-as').length === 0) empty.style.display = '';
    updateActiveSub();
  }

  function updateActiveSub() {
    var n = Object.keys(activeScans).length;
    var sub = document.getElementById('wr-active-sub');
    if (sub) sub.textContent = n + ' en curso';
    var kpi = document.getElementById('kpi-active');
    if (kpi) kpi.textContent = n;
  }

  function tickTimers() {
    document.querySelectorAll('.wr-as-timer').forEach(function (t) {
      var start = new Date(t.getAttribute('data-start')).getTime();
      if (isNaN(start)) return;
      var s = Math.max(0, Math.floor((Date.now() - start) / 1000));
      var mm = String(Math.floor(s / 60)).padStart(2, '0');
      var ss = String(s % 60).padStart(2, '0');
      t.textContent = mm + ':' + ss;
    });
    // auto-expirar activos viejos (> 20 min sin completar)
    Object.keys(activeScans).forEach(function (id) {
      var st = new Date(activeScans[id].started).getTime();
      if (Date.now() - st > 20 * 60 * 1000) removeActive(id);
    });
  }
  setInterval(tickTimers, 1000);

  // ---- KPIs ----
  function setKpis(k) {
    if (!k) return;
    setText('kpi-today', k.today_total);
    setText('kpi-det', k.today_detections);
    var risk = document.getElementById('kpi-risk');
    if (risk) risk.innerHTML = (k.avg_risk || 0) + '<small>/100</small>';
    updateActiveSub();
  }

  function flashKpi(id) {
    var el = document.querySelector('.wr-kpi[data-k="' + id + '"]');
    if (!el) return;
    el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
  }

  // ---- Charts ----
  function initCharts(data) {
    if (typeof Chart === 'undefined') return;
    Chart.defaults.color = '#A6A8D0';
    Chart.defaults.font.family = "'Inter', sans-serif";
    var accent = '#8b7bff', accentL = '#b9a7ff';

    var labels24 = [];
    for (var i = 23; i >= 0; i--) labels24.push('-' + i + 'h');
    charts.h24 = new Chart(document.getElementById('wr-chart-24h'), {
      type: 'line',
      data: { labels: labels24, datasets: [{
        data: data.hours_24 || [], borderColor: accent, backgroundColor: 'rgba(139,123,255,.15)',
        fill: true, tension: 0.35, pointRadius: 0, borderWidth: 2
      }] },
      options: baseOpts({ yBeginZero: true })
    });

    charts.countries = new Chart(document.getElementById('wr-chart-countries'), {
      type: 'bar',
      data: {
        labels: (data.top_countries || []).map(function (c) { return c.country; }),
        datasets: [{ data: (data.top_countries || []).map(function (c) { return c.count; }),
          backgroundColor: accent, borderRadius: 6 }]
      },
      options: baseOpts({ yBeginZero: true, indexAxis: 'y' })
    });

    var v = data.verdicts || {};
    charts.verdicts = new Chart(document.getElementById('wr-chart-verdicts'), {
      type: 'doughnut',
      data: {
        labels: ['Limpio', 'Sospechoso', 'Hack', 'Pendiente'],
        datasets: [{ data: [v.clean || 0, v.suspicious || 0, v.hack || 0, v.pending || 0],
          backgroundColor: ['#34D399', '#F59E0B', '#F4506E', '#6B5A45'], borderWidth: 0 }]
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: '62%',
        plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } } } }
    });
  }

  function baseOpts(o) {
    o = o || {};
    var opt = {
      responsive: true, maintainAspectRatio: false,
      indexAxis: o.indexAxis || 'x',
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(139,123,255,.08)' }, ticks: { font: { size: 10 } } },
        y: { grid: { color: 'rgba(139,123,255,.08)' }, beginAtZero: !!o.yBeginZero, ticks: { font: { size: 10 }, precision: 0 } }
      }
    };
    return opt;
  }

  function updateCharts(data) {
    if (charts.h24) { charts.h24.data.datasets[0].data = data.hours_24 || []; charts.h24.update('none'); }
    if (charts.countries) {
      charts.countries.data.labels = (data.top_countries || []).map(function (c) { return c.country; });
      charts.countries.data.datasets[0].data = (data.top_countries || []).map(function (c) { return c.count; });
      charts.countries.update('none');
    }
    if (charts.verdicts) {
      var v = data.verdicts || {};
      charts.verdicts.data.datasets[0].data = [v.clean || 0, v.suspicious || 0, v.hack || 0, v.pending || 0];
      charts.verdicts.update('none');
    }
  }

  // ---- Overview fetch ----
  function loadOverview(first) {
    fetch('/api/warroom/overview', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.success) return;
        setKpis(d.kpis);
        renderMapPoints(d.map_points);
        if (first) {
          initCharts(d);
          // sembrar feed reciente
          (d.recent || []).slice(0, 8).reverse().forEach(function (s) {
            var hit = s.verdict === 'hack' || s.risk >= 70;
            addFeed({ ico: hit ? '⚠️' : '🛰️', cls: hit ? 'hit' : '',
              title: s.who + (hit ? ' · riesgo ' + s.risk : ''),
              meta: s.country + ' · veredicto ' + (s.verdict || 'pendiente') });
          });
          // activos iniciales
          (d.active || []).forEach(function (a) { addActive(a.scan_id, a.who, a.country, a.started_at); });
        } else {
          updateCharts(d);
        }
      })
      .catch(function () {});
  }

  // ---- AI summary ----
  function loadSummary() {
    var el = document.getElementById('wr-ai-text');
    if (el) { el.classList.add('loading'); el.textContent = 'Generando resumen…'; }
    fetch('/api/warroom/summary', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (el && d && d.summary) { el.classList.remove('loading'); el.textContent = d.summary; }
      })
      .catch(function () { if (el) { el.classList.remove('loading'); el.textContent = 'No se pudo generar el resumen.'; } });
  }

  // ---- Socket.IO ----
  function initSocket() {
    if (typeof io === 'undefined') { setConn('off', 'Sin socket'); return; }
    var s = io({ transports: ['websocket', 'polling'] });
    s.on('connect', function () { setConn('ok', 'En vivo'); });
    s.on('disconnect', function () { setConn('off', 'Desconectado'); });
    s.on('connect_error', function () { setConn('off', 'Error conexión'); });
    s.on('notification', function (data) { handleNotification(data || {}); });
  }

  function handleNotification(data) {
    var kind = String(data.kind || '').toLowerCase();
    if (kind === 'scan_started') {
      var who = data.minecraft_username || data.machine_name || 'PC sin nombre';
      addFeed({ ico: '🛰️', title: 'SS iniciado · ' + who,
        meta: (data.country || 'Desconocido') + (data.launcher ? ' · ' + data.launcher : '') + ' · #' + (data.scan_id || '?') });
      addActive(data.scan_id, who, data.country, data.started_at);
      flashMapPoint(data.country, false);
      flashKpi('active');
      bumpKpi('kpi-today');
      ping();
      toast('🛰️ ' + who + ' empezó un SS');
    } else if (kind === 'scan_completed' || kind === 'scan_done') {
      removeActive(data.scan_id);
      addFeed({ ico: '✅', cls: 'done', title: 'SS finalizado · ' + (data.minecraft_username || data.machine_name || 'PC'),
        meta: 'scan #' + (data.scan_id || '?') });
      loadOverview(false);
    } else if (kind === 'security_alert' || kind === 'detection' || kind === 'hack') {
      addFeed({ ico: '⚠️', cls: 'hit', title: data.message || 'Detección de riesgo',
        meta: (data.minecraft_username || '') + ' · ' + (data.country || '') });
      flashMapPoint(data.country, true);
      bumpKpi('kpi-det'); flashKpi('det');
      ping();
    }
  }

  // ---- Helpers ----
  function setConn(state, txt) {
    var c = document.getElementById('wr-conn');
    var t = document.getElementById('wr-conn-txt');
    if (c) c.className = 'wr-conn ' + state;
    if (t) t.textContent = txt;
  }
  function setText(id, v) { var e = document.getElementById(id); if (e) e.textContent = (v == null ? 0 : v); }
  function bumpKpi(id) { var e = document.getElementById(id); if (e) { var n = parseInt(e.textContent, 10) || 0; e.textContent = n + 1; } }
  function escapeHtml(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  var _toastT = null;
  function toast(msg) {
    var el = document.querySelector('.wr-toast');
    if (!el) { el = document.createElement('div'); el.className = 'wr-toast'; document.body.appendChild(el); }
    el.textContent = msg; el.classList.add('show');
    clearTimeout(_toastT); _toastT = setTimeout(function () { el.classList.remove('show'); }, 3200);
  }

  function ping() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'sine'; o.frequency.value = 880;
      g.gain.setValueAtTime(0.0001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
      o.start(); o.stop(ctx.currentTime + 0.36);
    } catch (e) {}
  }

  // ---- Init ----
  function init() {
    initMap();
    initSocket();
    loadOverview(true);
    loadSummary();
    setInterval(function () { loadOverview(false); }, 30000);
    setInterval(loadSummary, 5 * 60 * 1000);

    var clear = document.getElementById('wr-feed-clear');
    if (clear) clear.addEventListener('click', function () {
      var feed = document.getElementById('wr-feed');
      if (feed) feed.innerHTML = '<div class="wr-feed-empty" id="wr-feed-empty">Feed limpio. Esperando nuevos eventos…</div>';
    });
    var air = document.getElementById('wr-ai-refresh');
    if (air) air.addEventListener('click', loadSummary);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
