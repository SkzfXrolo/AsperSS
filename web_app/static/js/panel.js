/**
 * Panel del Staff - ASPERS Projects
 * Sistema de gestión y aprendizaje progresivo
 */

const _csrfMeta = document.querySelector('meta[name="csrf-token"]');
const _csrfToken = _csrfMeta ? _csrfMeta.getAttribute('content') : '';
const _origFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => {
    const cfg = { ...init };
    const method = String(cfg.method || 'GET').toUpperCase();
    if (_csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        const headers = new Headers(cfg.headers || {});
        if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', _csrfToken);
        cfg.headers = headers;
    }
    return _origFetch(input, cfg);
};

// Estado global
let currentScanId = null;
let currentResultId = null;
let currentIssuesList = [];
let currentIssuesPage = 0;
const ISSUES_PER_PAGE = 30;
let _issuesFilter = 'all'; // filtro de categoría activo
let _issuesSearchText = '';  // buscador in-scan
let _issuesSeverity = '';    // filtro severidad in-scan
let _currentScanData = null;
let _argusSocket = null;
let _argusSocketConnected = false;
let _argusSocketPendingResolve = null;

function initArgusSocket() {
    if (typeof io !== 'function') return;
    if (_argusSocket) return;
    _argusSocket = io({
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 500,
        reconnectionDelayMax: 10000,
        randomizationFactor: 0.5,
        timeout: 8000
    });
    _argusSocket.on('connect', () => { _argusSocketConnected = true; });
    _argusSocket.on('disconnect', () => { _argusSocketConnected = false; });
    _argusSocket.on('reconnect_attempt', () => {
        if (typeof showToast === 'function') showToast('Reconectando canal en tiempo real...', 'info');
    });
    _argusSocket.on('oracle_response', (payload) => {
        if (typeof _argusSocketPendingResolve === 'function') {
            _argusSocketPendingResolve(payload || {});
            _argusSocketPendingResolve = null;
        }
    });
    _argusSocket.on('notification', (payload) => {
        const txt = payload && payload.message ? payload.message : 'Nueva notificación en tiempo real';
        if (typeof showToast === 'function') showToast(txt, 'info');
    });
}

setTimeout(() => {
    try { initArgusSocket(); } catch (_) {}
}, 120);

// ── Paleta de colores ──────────────────────────────────────────────────────
const ARGUS_PALETTES = {
    copper: { label:'Cobre',   swatch:'#B87333', accent:'#B87333', d:'#7A4824', bg:'rgba(184,115,51,0.08)', glow:'rgba(184,115,51,0.22)', border:'rgba(184,115,51,0.12)', borderM:'rgba(184,115,51,0.28)', borderH:'rgba(184,115,51,0.55)' },
    purple: { label:'Morado',  swatch:'#8B5CF6', accent:'#8B5CF6', d:'#6D28D9', bg:'rgba(139,92,246,0.08)', glow:'rgba(139,92,246,0.22)', border:'rgba(139,92,246,0.12)', borderM:'rgba(139,92,246,0.28)', borderH:'rgba(139,92,246,0.55)' },
    blue:   { label:'Azul',    swatch:'#3B82F6', accent:'#3B82F6', d:'#1D4ED8', bg:'rgba(59,130,246,0.08)',  glow:'rgba(59,130,246,0.22)',  border:'rgba(59,130,246,0.12)',  borderM:'rgba(59,130,246,0.28)',  borderH:'rgba(59,130,246,0.55)'  },
    green:  { label:'Verde',   swatch:'#10B981', accent:'#10B981', d:'#059669', bg:'rgba(16,185,129,0.08)',  glow:'rgba(16,185,129,0.22)',  border:'rgba(16,185,129,0.12)',  borderM:'rgba(16,185,129,0.28)',  borderH:'rgba(16,185,129,0.55)'  },
    orange: { label:'Naranja', swatch:'#F59E0B', accent:'#F59E0B', d:'#D97706', bg:'rgba(245,158,11,0.08)',  glow:'rgba(245,158,11,0.22)',  border:'rgba(245,158,11,0.12)',  borderM:'rgba(245,158,11,0.28)',  borderH:'rgba(245,158,11,0.55)'  },
    red:    { label:'Rojo',    swatch:'#EF4444', accent:'#EF4444', d:'#DC2626', bg:'rgba(239,68,68,0.08)',   glow:'rgba(239,68,68,0.22)',   border:'rgba(239,68,68,0.12)',   borderM:'rgba(239,68,68,0.28)',   borderH:'rgba(239,68,68,0.55)'   },
    pink:   { label:'Rosa',    swatch:'#EC4899', accent:'#EC4899', d:'#DB2777', bg:'rgba(236,72,153,0.08)',  glow:'rgba(236,72,153,0.22)',  border:'rgba(236,72,153,0.12)',  borderM:'rgba(236,72,153,0.28)',  borderH:'rgba(236,72,153,0.55)'  },
    cyan:   { label:'Cyan',    swatch:'#06B6D4', accent:'#06B6D4', d:'#0891B2', bg:'rgba(6,182,212,0.08)',   glow:'rgba(6,182,212,0.22)',   border:'rgba(6,182,212,0.12)',   borderM:'rgba(6,182,212,0.28)',   borderH:'rgba(6,182,212,0.55)'   },
    white:  { label:'Blanco',  swatch:'#E2E8F7', accent:'#E2E8F7', d:'#C4CFDF', bg:'rgba(226,232,247,0.08)', glow:'rgba(226,232,247,0.15)', border:'rgba(226,232,247,0.10)', borderM:'rgba(226,232,247,0.22)', borderH:'rgba(226,232,247,0.45)' },
};
let _currentPalette = 'copper';

function applyPalette(name) {
    const p = ARGUS_PALETTES[name];
    if (!p) return;
    _currentPalette = name;
    const r = document.documentElement;
    r.style.setProperty('--accent',   p.accent);
    r.style.setProperty('--accent-d', p.d);
    r.style.setProperty('--accent-bg',  p.bg);
    r.style.setProperty('--accent-glow',p.glow);
    r.style.setProperty('--border',   p.border);
    r.style.setProperty('--border-m', p.borderM);
    r.style.setProperty('--border-h', p.borderH);
    localStorage.setItem('argus_palette', name);
    // Highlight active swatch
    document.querySelectorAll('.palette-swatch').forEach(el => {
        el.style.outline = el.dataset.palette === name ? '3px solid #fff' : 'none';
    });
}

function _buildPaletteSwatches() {
    const wrap = document.getElementById('palette-swatches');
    if (!wrap) return;
    wrap.innerHTML = Object.entries(ARGUS_PALETTES).map(([k, p]) =>
        `<button class="palette-swatch" data-palette="${k}" onclick="applyPalette('${k}');document.getElementById('palette-panel').style.display='none';"
            title="${p.label}" style="
            width:32px;height:32px;border-radius:50%;border:2px solid rgba(255,255,255,0.15);
            background:${p.swatch};cursor:pointer;transition:transform 0.15s;
            outline:${k === _currentPalette ? '3px solid #fff' : 'none'};outline-offset:2px;"
            onmouseover="this.style.transform='scale(1.2)'"
            onmouseout="this.style.transform='scale(1)'"></button>`
    ).join('');
}

function togglePalettePanel(e) {
    if (e) e.stopPropagation();
    const panel = document.getElementById('palette-panel');
    if (!panel) return;
    const isOpen = panel.style.display !== 'none';
    panel.style.display = isOpen ? 'none' : 'block';
    if (!isOpen) { _buildPaletteSwatches(); setTimeout(_initCustomColorPicker, 50); }
}

// P5 #16 — Web Push subscription toggle
let _pushSubscription = null;
async function togglePushSubscription(btn) {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        showToast('Tu navegador no soporta notificaciones push', 'error');
        return;
    }
    try {
        if (_pushSubscription) {
            // Unsubscribe
            await _pushSubscription.unsubscribe();
            await fetch('/api/push/unsubscribe', {
                method: 'POST', headers: {'Content-Type':'application/json'},
                body: JSON.stringify({endpoint: _pushSubscription.endpoint})
            });
            _pushSubscription = null;
            btn.style.color = 'var(--text-d)';
            btn.title = 'Activar notificaciones push';
            showToast('Notificaciones desactivadas', 'info');
            return;
        }
        // Get VAPID key
        const keyRes = await fetch('/api/push/vapid-public-key');
        if (!keyRes.ok) { showToast('Notificaciones push no configuradas en el servidor', 'info'); return; }
        const {public_key} = await keyRes.json();

        // Request permission
        const perm = await Notification.requestPermission();
        if (perm !== 'granted') { showToast('Permiso de notificaciones denegado', 'error'); return; }

        // Subscribe
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: _urlBase64ToUint8Array(public_key)
        });
        await fetch('/api/push/subscribe', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify(sub.toJSON())
        });
        _pushSubscription = sub;
        btn.style.color = '#10b981';
        btn.title = 'Desactivar notificaciones push';
        showToast('✅ Notificaciones activadas', 'success');
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}
function _urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

async function _initPushState() {
    const btn = document.getElementById('push-notif-btn');
    if (!btn || !('serviceWorker' in navigator) || !('PushManager' in window)) return;
    try {
        const reg = await navigator.serviceWorker.ready;
        const sub = await reg.pushManager.getSubscription();
        if (sub) {
            _pushSubscription = sub;
            btn.style.color = '#10b981';
            btn.title = 'Desactivar notificaciones push';
        }
    } catch(_) {}
}

function _loadSavedPalette() {
    let bgCfg = {};
    try { bgCfg = JSON.parse(localStorage.getItem('argus_bg') || '{}'); } catch(_) {}
    if (bgCfg && bgCfg.preset && bgCfg.preset !== 'default') {
        return;
    }
    const saved = localStorage.getItem('argus_palette');
    if (saved && ARGUS_PALETTES[saved]) applyPalette(saved);
}

// ── P5 #29 — Multi-server selector ────────────────────────────────────────
let _serverListLoaded = false;

async function _initServerSelector() {
    try {
        const res = await fetch('/api/servers');
        if (!res.ok) return;
        const data = await res.json();
        const servers = data.servers || [];
        if (servers.length <= 1) return; // hide for single-server setups
        const wrap = document.getElementById('server-selector-wrap');
        const nameEl = document.getElementById('active-server-name');
        if (!wrap) return;
        wrap.style.display = 'flex';
        const active = servers.find(s => s.id === data.active_server_id);
        if (active && nameEl) nameEl.textContent = active.name;
    } catch(_) {}
}

function toggleServerSelector(e) {
    if (e) e.stopPropagation();
    const dropdown = document.getElementById('server-dropdown');
    if (!dropdown) return;
    const isOpen = dropdown.style.display !== 'none';
    dropdown.style.display = isOpen ? 'none' : 'block';
    if (!isOpen && !_serverListLoaded) _loadServerList();
}

async function _loadServerList() {
    const listEl = document.getElementById('server-list');
    if (!listEl) return;
    try {
        const res = await fetch('/api/servers');
        if (!res.ok) return;
        const data = await res.json();
        const servers = data.servers || [];
        _serverListLoaded = true;
        listEl.innerHTML = servers.map(s => `
            <div onclick="selectServer(${s.id}, ${JSON.stringify(s.name)})"
                 style="padding:8px 12px;cursor:pointer;border-radius:6px;
                        ${s.id === data.active_server_id ? 'background:var(--accent-bg);color:var(--accent);font-weight:600;' : 'color:var(--text);'}
                        transition:background 0.15s;"
                 onmouseover="this.style.background='var(--accent-bg)'"
                 onmouseout="this.style.background='${s.id === data.active_server_id ? 'var(--accent-bg)' : 'transparent'}'">
                🖥 ${s.name}
            </div>`).join('');
    } catch(_) {
        if (listEl) listEl.innerHTML = '<div style="padding:8px;color:var(--text-d)">Error cargando servidores</div>';
    }
}

async function selectServer(serverId, serverName) {
    try {
        const res = await fetch('/api/servers/select', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({server_id: serverId})
        });
        if (!res.ok) { showToast('Error al cambiar de servidor', 'error'); return; }
        const nameEl = document.getElementById('active-server-name');
        if (nameEl) nameEl.textContent = serverName;
        document.getElementById('server-dropdown').style.display = 'none';
        _serverListLoaded = false;
        showToast(`Servidor: ${serverName}`, 'success');
        // Reload data for new server context
        loadDashboard();
        loadScans();
    } catch(e) {
        showToast('Error al cambiar de servidor', 'error');
    }
}

// Inicialización - OPTIMIZADO: Cargar datos críticos primero, el resto en background
document.addEventListener('DOMContentLoaded', function() {
    _loadSavedPalette();
    initializeNavigation();
    setupEventListeners();
    setupAdminListeners();
    setupCompanyListeners();
    // Cerrar palette panel y server dropdown al hacer click fuera
    document.addEventListener('click', e => {
        const panel = document.getElementById('palette-panel');
        const btn   = document.getElementById('palette-toggle');
        if (panel && btn && !panel.contains(e.target) && !btn.contains(e.target)) {
            panel.style.display = 'none';
        }
        const sWrap = document.getElementById('server-selector-wrap');
        const sDrop = document.getElementById('server-dropdown');
        if (sWrap && sDrop && !sWrap.contains(e.target)) {
            sDrop.style.display = 'none';
        }
    });

    // Cargar datos críticos primero
    loadDashboard();
    _initServerSelector();

    // Cargar el resto en background (no bloquea la UI)
    setTimeout(() => {
        loadTokens();
        loadScans();
    }, 100);

    // Cargar estadísticas de aprendizaje en background (menos crítico)
    setTimeout(() => {
        loadLearningStats();
    }, 500);

    // Cargar presets de filtros guardados
    _renderPresetOptions();

    // Aplicar restricciones de permisos según rol
    applyPermissionGuards();

    // Auto-refresh: arrancar polling 3 segundos después de la carga
    setTimeout(startScanPolling, 3000);

    // P5 #16 — Restore push subscription state on page load
    setTimeout(_initPushState, 800);
});

// ============================================================
// AUTO-REFRESH / POLLING
// ============================================================

let _lastKnownScanId = null;
let _newScansCount   = 0;
const POLL_INTERVAL         = 15000; // 15 s — detecta scans rápidos (<30s)
const POLL_RUNNING_INTERVAL = 5000;  // 5 s — re-chequea running scans
// Scans en progreso detectados — {id → machine_name} — vigilados hasta completarse
const _pendingRunning = new Map();

async function startScanPolling() {
    try {
        const res  = await fetch('/api/scans?limit=1');
        const data = await res.json();
        if (data.scans && data.scans.length > 0) {
            _lastKnownScanId = data.scans[0].id;
        }
    } catch (_) {}

    setInterval(pollForNewScans, POLL_INTERVAL);
    // Intervalo rápido para vigilar running scans que terminan antes del poll normal
    setInterval(_checkPendingRunning, POLL_RUNNING_INTERVAL);
}

async function pollForNewScans() {
    try {
        const res  = await fetch('/api/scans?limit=10');
        const data = await res.json();
        if (!data.scans || data.scans.length === 0) return;

        const latest = data.scans[0];

        if (_lastKnownScanId !== null && latest.id > _lastKnownScanId) {
            const newScans  = data.scans.filter(s => s.id > _lastKnownScanId);
            const completed = newScans.filter(s => s.status === 'completed');
            const running   = newScans.filter(s => s.status === 'running');

            // Guardar running para notificar cuando terminen
            running.forEach(s => _pendingRunning.set(s.id, s.machine_name || 'desconocido'));

            if (completed.length > 0) {
                _newScansCount += completed.length;
                showNewScansBadge(_newScansCount);
                // V70: play critical sound if risk > 75
                const highRisk = completed.find(s => (s.risk_score || 0) > 75);
                if (highRisk) {
                    playCriticalSound();
                    // V68: Critical alert banner
                    _showCriticalBanner(highRisk.machine_name || 'desconocido', highRisk.id);
                } else {
                    showToast(`Nuevo scan de ${completed[0].machine_name || 'desconocido'}`, 'info', completed[0].id);
                    playNotificationSound();
                }
                const activeSection = document.querySelector('.panel-section.active');
                if (activeSection && activeSection.id === 'dashboard-section') loadDashboard();
                // V15: Flash new rows in scan list
                setTimeout(() => {
                    completed.forEach(s => {
                        const tr = document.querySelector(`tr[data-scan-id="${s.id}"]`);
                        if (tr) tr.classList.add('tr-new-scan');
                    });
                }, 200);
                // V69: Add to notification center
                completed.forEach(s => _addNotification({
                    icon: (s.risk_score || 0) > 75 ? '🔴' : 'ℹ️',
                    text: `Nuevo scan: ${s.machine_name || 'desconocido'}`,
                    scanId: s.id,
                    time: new Date(),
                }));
            }
        }

        _checkPendingRunningWithData(data.scans);
        _lastKnownScanId = latest.id;
    } catch (_) {}
}

async function _checkPendingRunning() {
    if (_pendingRunning.size === 0) return;
    try {
        const res  = await fetch(`/api/scans?limit=20`);
        const data = await res.json();
        if (!data.scans) return;
        _checkPendingRunningWithData(data.scans);
    } catch (_) {}
}

function _checkPendingRunningWithData(scans) {
    for (const [id, name] of _pendingRunning.entries()) {
        const scan = scans.find(s => s.id === id);
        if (scan && scan.status === 'completed') {
            _pendingRunning.delete(id);
            _newScansCount++;
            showNewScansBadge(_newScansCount);
            const rs = scan.risk_score || 0;
            if (rs > 75) {
                _showCriticalBanner(name, id);
            } else {
                showToast(`Scan completado: ${name}`, 'success', id);
                playNotificationSound();
            }
            _addNotification({ icon: rs > 75 ? '🔴' : '✅', text: `Scan completado: ${name}`, scanId: id, time: new Date() });
            const activeSection = document.querySelector('.panel-section.active');
            if (activeSection && activeSection.id === 'dashboard-section') loadDashboard();
        } else if (!scan) {
            _pendingRunning.delete(id);
        }
    }
}

function showNewScansBadge(count) {
    const badge = document.getElementById('new-scans-badge');
    if (!badge) return;
    badge.textContent = count > 99 ? '99+' : count;
    badge.style.display = 'inline-block';
}

function clearNewScansBadge() {
    _newScansCount = 0;
    const badge = document.getElementById('new-scans-badge');
    if (badge) badge.style.display = 'none';
}

let _toastContainer = null;
const _TOAST_MAX = 4;

function _dismissToast(toast) {
    if (toast._dismissed) return;
    toast._dismissed = true;
    toast.style.transition = 'opacity .3s, transform .3s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(() => { try { toast.remove(); } catch(_) {} }, 320);
}

// showToast(message, type, scanIdOrOpts)
// scanIdOrOpts: number → click opens that scan; object → {duration, scanId, onClick}
function showToast(message, type = 'info', scanIdOrOpts = null) {
    if (!_toastContainer) {
        _toastContainer = document.createElement('div');
        _toastContainer.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column-reverse;gap:8px;pointer-events:none;max-height:calc(100vh - 80px);overflow:hidden;';
        document.body.appendChild(_toastContainer);
    }

    // Evict oldest if queue at max
    const existing = _toastContainer.querySelectorAll('.argus-toast');
    if (existing.length >= _TOAST_MAX) _dismissToast(existing[0]);

    const opts   = (scanIdOrOpts && typeof scanIdOrOpts === 'object') ? scanIdOrOpts : {};
    const scanId = (typeof scanIdOrOpts === 'number') ? scanIdOrOpts : (opts.scanId || null);
    const duration = opts.duration || 5000;
    const onClick  = opts.onClick || null;

    const cfg = {
        info:    { color: '#B87333', bg: 'rgba(184,115,51,0.12)', icon: '◆' },
        success: { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  icon: '✓' },
        error:   { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   icon: '✗' },
        warning: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)',  icon: '⚠' },
    };
    const c = cfg[type] || cfg.info;
    const toast = document.createElement('div');
    toast.className = 'argus-toast';
    toast._dismissed = false;
    const clickable = !!(scanId || onClick);
    toast.style.cssText = `
        background:var(--bg-card,#1e1e2e);
        border:1px solid ${c.color}55;
        border-left:3px solid ${c.color};
        border-radius:10px;padding:11px 15px 11px 12px;
        font-size:13px;color:var(--text,#e2e8f0);
        box-shadow:0 8px 32px rgba(0,0,0,0.35);
        pointer-events:all;cursor:${clickable?'pointer':'default'};
        max-width:310px;min-width:220px;
        animation:slideInRight .22s cubic-bezier(0.4,0,0.2,1);
        display:flex;gap:10px;align-items:flex-start;
        position:relative;overflow:hidden;`;
    toast.innerHTML = `
        <span style="font-size:14px;font-weight:700;color:${c.color};flex-shrink:0;margin-top:1px;">${c.icon}</span>
        <div style="flex:1;min-width:0;">
            <div style="font-weight:600;margin-bottom:2px;font-size:12px;color:${c.color};">Argus Projects</div>
            <div style="color:var(--text-m,#94a3b8);font-size:12.5px;line-height:1.4;">${message}</div>
        </div>
        <button onclick="event.stopPropagation()" style="background:none;border:none;color:var(--text-d,#666);cursor:pointer;font-size:16px;line-height:1;padding:0 0 0 4px;flex-shrink:0;opacity:0.7;" title="Cerrar">×</button>
        <div style="position:absolute;bottom:0;left:0;height:2px;background:${c.color};opacity:0.5;width:100%;transform-origin:left;animation:toast-drain ${duration}ms linear forwards;"></div>`;

    const closeBtn = toast.querySelector('button');
    closeBtn.addEventListener('click', () => _dismissToast(toast));

    toast.addEventListener('click', () => {
        if (scanId && typeof viewScanDetails === 'function') viewScanDetails(scanId);
        else if (onClick) onClick();
        _dismissToast(toast);
    });

    _toastContainer.appendChild(toast);
    const tid = setTimeout(() => _dismissToast(toast), duration);
    toast._tid = tid;
}

let _soundEnabled = localStorage.getItem('notif-sound') !== 'false';
function playNotificationSound() {
    if (!_soundEnabled) return;
    // Visual #44 — usar el ding sofisticado de argusUI cuando esté disponible
    // (2 notas E5->A5, perfil exponencial, más agradable que el beep antiguo).
    if (window.argusUI && typeof window.argusUI.playScanDing === 'function') {
        window.argusUI.playScanDing(true);
        return;
    }
    try {
        const ctx  = new (window.AudioContext || window.webkitAudioContext)();
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.type = 'sine'; osc.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.4);
    } catch(_) {}
}

function toggleNotifSound() {
    _soundEnabled = !_soundEnabled;
    localStorage.setItem('notif-sound', _soundEnabled ? 'true' : 'false');
    showToast(_soundEnabled ? 'Sonido de notificaciones activado' : 'Sonido de notificaciones desactivado');
}

// ============================================================
// NAVEGACIÓN
// ============================================================

function toggleMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const btn = document.getElementById('hamburger-btn');
    sidebar.classList.toggle('mobile-open');
    overlay.classList.toggle('active');
    btn.classList.toggle('open');
}

function closeMobileSidebar() {
    document.querySelector('.sidebar').classList.remove('mobile-open');
    document.getElementById('sidebar-overlay').classList.remove('active');
    document.getElementById('hamburger-btn').classList.remove('open');
}

function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-section]');
    console.log('Inicializando navegación, elementos encontrados:', navItems.length);

    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const section = this.getAttribute('data-section');
            console.log('Click en navegación, sección:', section);
            if (section) {
                showSection(section);
                closeMobileSidebar();
            } else {
                console.error('No se encontró atributo data-section en:', this);
            }
        });
    });
    
    // También manejar navegación por hash (si se accede directamente)
    if (window.location.hash) {
        const hash = window.location.hash.substring(1);
        const sectionMap = {
            'dashboard': 'dashboard',
            'generar-app': 'generar-app',
            'tokens': 'tokens',
            'resultados': 'resultados',
            'aprendizaje': 'aprendizaje',
            'administracion': 'administracion',
            'mi-empresa': 'equipo',
            'staff': 'equipo',
            'equipo': 'equipo',
        };
        if (sectionMap[hash]) {
            showSection(sectionMap[hash]);
        }
    }

    // Visual #29: deep-link a un scan específico via ?scan=<id>.
    // Si la URL trae el param, abrir el detalle de ese scan automáticamente.
    try {
        const usp = new URLSearchParams(window.location.search);
        const wantScan = parseInt(usp.get('scan') || '', 10);
        if (Number.isFinite(wantScan) && wantScan > 0 && typeof viewScanDetails === 'function') {
            // Pequeño delay para que la sección 'resultados' esté lista
            setTimeout(() => {
                showSection('resultados');
                viewScanDetails(wantScan);
            }, 250);
        }
    } catch (_) {}
}

/**
 * Visual #29: copiar enlace permalink al escaneo actual.
 * Usa Clipboard API moderna con fallback a textarea hidden.
 * Muestra toast verde de confirmación o rojo si falla.
 */
/**
 * Visual #28 + #30 — Modal "Compartir veredicto":
 *  - Genera tarjeta PNG del veredicto (canvas vanilla — sin html2canvas)
 *    con avatar, jugador, veredicto, risk score, top categorías, branding.
 *  - Incluye QR code del enlace al scan (api.qrserver.com, sin libs).
 *  - Permite descargar como PNG y/o copiar el enlace.
 */
async function openShareVerdictModal(scanId) {
    if (!scanId) {
        if (window.showToast) showToast('No hay escaneo abierto.', 'warning');
        return;
    }

    document.getElementById('argus-share-modal')?.remove();

    // Snapshot del DOM actual del scan abierto (mucho más rápido que volver a fetchear)
    const machine = document.getElementById('scan-machine-name')?.textContent?.trim() || '—';
    const player  = document.getElementById('detail-mc-username')?.textContent?.trim()
                 || document.getElementById('scan-mc-username')?.textContent?.trim() || '—';
    const verdictRaw = document.querySelector('#current-verdict-banner span')?.textContent?.trim() || '';
    const verdictMatch = verdictRaw.match(/Veredicto:\s*([^—]+)/i);
    const verdictLabel = (verdictMatch ? verdictMatch[1].trim() : 'PENDIENTE').toUpperCase();
    const verdictKind = verdictLabel.includes('LIMP') ? 'clean'
                     : verdictLabel.includes('HACK') ? 'hack'
                     : 'pending';
    const riskTxt = document.getElementById('risk-score-value')?.textContent?.trim() || '';
    const risk = parseInt(riskTxt, 10);
    const country = document.getElementById('scan-country')?.textContent?.trim() || '';
    const startedTxt = document.getElementById('scan-started-at')?.textContent?.trim() || '';

    // Counters de severidad — leemos directo del DOM o de currentIssuesList si existe
    let nCrit = 0, nSusp = 0;
    if (Array.isArray(window.currentIssuesList)) {
        for (const r of window.currentIssuesList) {
            if (r.alert_level === 'CRITICAL') nCrit++;
            else if (r.alert_level === 'SOSPECHOSO' || r.alert_level === 'HACKS') nSusp++;
        }
    }

    const url = `${window.location.origin}${window.location.pathname}?scan=${scanId}`;
    const qrUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=8&color=EAD8C0&bgcolor=15110A&data=' + encodeURIComponent(url);

    // Construir canvas de la tarjeta (1080x600 — buena ratio para Discord/WhatsApp)
    const W = 1080, H = 600;
    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');

    const palette = verdictKind === 'clean'
        ? { bg: '#0E2A1E', accent: '#10b981', accentSoft: 'rgba(16,185,129,0.16)', stripe: '#34d399', text: '#EAD8C0' }
        : verdictKind === 'hack'
        ? { bg: '#2A0E10', accent: '#ef4444', accentSoft: 'rgba(239,68,68,0.16)', stripe: '#fca5a5', text: '#EAD8C0' }
        : { bg: '#1A140C', accent: '#B87333', accentSoft: 'rgba(184,115,51,0.18)', stripe: '#D4915A', text: '#EAD8C0' };

    // Background con gradiente diagonal
    const grd = ctx.createLinearGradient(0, 0, W, H);
    grd.addColorStop(0,   palette.bg);
    grd.addColorStop(0.6, '#15110A');
    grd.addColorStop(1,   palette.bg);
    ctx.fillStyle = grd;
    ctx.fillRect(0, 0, W, H);

    // Stripe lateral izquierda
    ctx.fillStyle = palette.accent;
    ctx.fillRect(0, 0, 8, H);

    // Branding header
    ctx.fillStyle = '#B87333';
    ctx.font = 'bold 16px "JetBrains Mono", monospace';
    ctx.textBaseline = 'top';
    ctx.fillText('ARGUS · ALL-SEEING', 40, 36);
    ctx.fillStyle = 'rgba(234,216,192,0.50)';
    ctx.font = '12px "JetBrains Mono", monospace';
    ctx.fillText('argusprojects.com', 40, 58);

    // Scan ID arriba derecha
    ctx.fillStyle = 'rgba(234,216,192,0.45)';
    ctx.font = '13px "JetBrains Mono", monospace';
    const scanLabel = `SCAN #${scanId}`;
    const scanLabelW = ctx.measureText(scanLabel).width;
    ctx.fillText(scanLabel, W - 40 - scanLabelW, 38);

    // Verdict big label
    ctx.fillStyle = palette.text;
    ctx.font = 'bold 60px "Inter", system-ui, sans-serif';
    ctx.fillText('Veredicto', 40, 110);
    ctx.fillStyle = palette.accent;
    ctx.font = 'bold 96px "Inter", system-ui, sans-serif';
    ctx.fillText(verdictLabel, 40, 175);

    // Risk score badge (derecha)
    if (!isNaN(risk)) {
        const cx = W - 180, cy = 230, rad = 86;
        ctx.beginPath();
        ctx.arc(cx, cy, rad, 0, Math.PI * 2);
        ctx.fillStyle = palette.accentSoft;
        ctx.fill();
        ctx.lineWidth = 5;
        ctx.strokeStyle = palette.accent;
        ctx.stroke();

        ctx.fillStyle = palette.text;
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('RISK SCORE', cx, cy - 38);
        ctx.fillStyle = palette.accent;
        ctx.font = 'bold 56px "Inter", system-ui, sans-serif';
        ctx.fillText(String(risk), cx, cy - 20);
        ctx.fillStyle = 'rgba(234,216,192,0.55)';
        ctx.font = '12px "Inter", system-ui, sans-serif';
        ctx.fillText('/ 100', cx, cy + 38);
        ctx.textAlign = 'left';
    }

    // Líneas de info: jugador, máquina, hallazgos, fecha
    const infoY0 = 320;
    const lineH = 36;
    const drawInfo = (i, label, value) => {
        const y = infoY0 + i * lineH;
        ctx.fillStyle = 'rgba(234,216,192,0.45)';
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        ctx.fillText(label.toUpperCase(), 40, y);
        ctx.fillStyle = palette.text;
        ctx.font = '20px "Inter", system-ui, sans-serif';
        const v = value && String(value).length > 38 ? String(value).slice(0, 36) + '…' : (value || '—');
        ctx.fillText(v, 40, y + 14);
    };
    drawInfo(0, 'Jugador',  player);
    drawInfo(1, 'Máquina',  machine);
    drawInfo(2, 'Hallazgos', `${nCrit} críticos · ${nSusp} sospechosos`);
    drawInfo(3, 'Fecha',    startedTxt + (country ? ` · ${country}` : ''));

    // Footer brand
    ctx.fillStyle = 'rgba(234,216,192,0.30)';
    ctx.font = '11px "JetBrains Mono", monospace';
    ctx.fillText('Generado por Argus Projects · ' + new Date().toLocaleString(), 40, H - 32);

    // Espacio reservado para el QR (lo cargamos asíncrono y reemplazamos)
    const qrPad = ctx.createLinearGradient(W - 240, H - 240, W, H);
    qrPad.addColorStop(0, 'rgba(184,115,51,0.10)');
    qrPad.addColorStop(1, 'rgba(184,115,51,0.04)');
    ctx.fillStyle = qrPad;
    ctx.fillRect(W - 240, H - 240, 200, 200);
    ctx.strokeStyle = palette.accent;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(W - 240, H - 240, 200, 200);
    ctx.fillStyle = 'rgba(234,216,192,0.5)';
    ctx.font = '11px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Generando QR…', W - 140, H - 130);
    ctx.textAlign = 'left';

    // Imagen PNG inicial (sin QR todavía)
    const initialPng = canvas.toDataURL('image/png');

    // Modal
    const root = document.createElement('div');
    root.id = 'argus-share-modal';
    root.style.cssText = 'position:fixed;inset:0;z-index:99996;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(8,6,4,0.62);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);animation:argusConfirmFadeIn 180ms ease;';
    root.innerHTML = `
        <div role="dialog" aria-modal="true" aria-labelledby="argus-share-title"
             style="background:var(--bg-2,#15110A);color:var(--text,#EAD8C0);
                    border:1px solid var(--border-m,rgba(184,115,51,0.28));
                    border-radius:14px;width:min(720px,94vw);max-height:92vh;overflow:auto;
                    box-shadow:0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) inset;
                    animation:argusConfirmPop 220ms cubic-bezier(0.22,1,0.36,1);">
            <div style="padding:18px 22px 10px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--border);">
                <h2 id="argus-share-title" style="margin:0;font-size:15px;font-weight:700;">Compartir veredicto del scan #${scanId}</h2>
                <button id="argus-share-close" type="button" aria-label="Cerrar"
                    style="background:transparent;border:1px solid var(--border-m);color:var(--text-m);width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:18px;line-height:1;">×</button>
            </div>
            <div style="padding:18px 22px;display:flex;flex-direction:column;gap:14px;">
                <img id="argus-share-preview" src="${initialPng}" alt="Tarjeta de veredicto"
                     style="width:100%;border-radius:10px;border:1px solid var(--border-m);box-shadow:0 10px 30px rgba(0,0,0,0.4);background:#000;" />
                <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
                    <button id="argus-share-download" type="button"
                        style="font-size:12.5px;font-weight:700;padding:9px 16px;border-radius:8px;border:none;cursor:pointer;
                               color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-d));
                               box-shadow:0 6px 18px -6px rgba(184,115,51,0.4);">⬇ Descargar PNG</button>
                    <button id="argus-share-copy-link" type="button"
                        style="font-size:12.5px;font-weight:600;padding:9px 16px;border-radius:8px;cursor:pointer;
                               background:transparent;color:var(--text-m);border:1px solid var(--border-m);">🔗 Copiar enlace</button>
                    <span style="font-size:11.5px;color:var(--text-d);font-family:'JetBrains Mono',monospace;flex:1;min-width:200px;text-align:right;">
                        ${url.length > 60 ? url.slice(0, 58) + '…' : url}
                    </span>
                </div>
                <div style="font-size:11.5px;color:var(--text-d);line-height:1.5;">
                    El QR del enlace se genera vía api.qrserver.com (sin tracking). La imagen incluye solo
                    datos no sensibles del scan: jugador (Minecraft username), máquina, veredicto y conteo
                    de hallazgos. La IP no se incluye.
                </div>
            </div>
        </div>`;
    document.body.appendChild(root);

    const closeBtn = root.querySelector('#argus-share-close');
    const close = () => {
        document.removeEventListener('keydown', onKey, true);
        root.style.animation = 'argusConfirmFadeOut 140ms ease';
        setTimeout(() => root.remove(), 130);
    };
    const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close(); } };
    document.addEventListener('keydown', onKey, true);
    closeBtn.addEventListener('click', close);
    root.addEventListener('click', (e) => { if (e.target === root) close(); });

    // Cargar QR async y redibujar
    const qrImg = new Image();
    qrImg.crossOrigin = 'anonymous';
    qrImg.onload = () => {
        try {
            // Limpiar el placeholder y dibujar el QR real (con borde claro)
            ctx.fillStyle = '#15110A';
            ctx.fillRect(W - 240, H - 240, 200, 200);
            ctx.drawImage(qrImg, W - 230, H - 230, 180, 180);
            ctx.strokeStyle = palette.accent;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(W - 240, H - 240, 200, 200);
            // Label "ESCANEAR" arriba del QR
            ctx.fillStyle = 'rgba(234,216,192,0.55)';
            ctx.font = 'bold 10px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText('ESCANEÁ PARA ABRIR', W - 140, H - 252);
            ctx.textAlign = 'left';

            const finalPng = canvas.toDataURL('image/png');
            const previewEl = document.getElementById('argus-share-preview');
            if (previewEl) previewEl.src = finalPng;
            // Setea el href del download al PNG final
            const dlBtn = document.getElementById('argus-share-download');
            if (dlBtn) dlBtn._finalPng = finalPng;
        } catch (_e) { /* el QR no es crítico */ }
    };
    qrImg.onerror = () => {
        // Sin red / bloqueo CORS — dejar placeholder
        const dlBtn = document.getElementById('argus-share-download');
        if (dlBtn) dlBtn._finalPng = initialPng;
    };
    qrImg.src = qrUrl;

    // Botones de acción
    root.querySelector('#argus-share-download').addEventListener('click', (e) => {
        const png = e.currentTarget._finalPng || initialPng;
        const a = document.createElement('a');
        a.href = png;
        a.download = `argus-scan-${scanId}-${verdictKind}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        if (window.showToast) showToast('Imagen descargada', 'success', { duration: 2200 });
    });
    root.querySelector('#argus-share-copy-link').addEventListener('click', () => {
        copyScanLink(scanId);
    });
}
window.openShareVerdictModal = openShareVerdictModal;


/**
 * Visual #11 — Heatmap GitHub-style de actividad del staff loggeado.
 * Endpoint: /api/staff/my-activity-heatmap?days=365
 * Renderiza una grilla 7×N donde cada celda es un día (un cuadrado bronce
 * cuya intensidad escala con el número de acciones). Hover muestra tooltip
 * con la fecha y el conteo. Stats arriba: total, días activos, streak actual,
 * mejor streak.
 */
async function openMyActivityHeatmap() {
    document.getElementById('argus-activity-modal')?.remove();
    const root = document.createElement('div');
    root.id = 'argus-activity-modal';
    root.style.cssText = 'position:fixed;inset:0;z-index:99996;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(8,6,4,0.62);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);animation:argusConfirmFadeIn 180ms ease;';
    root.innerHTML = `
        <div role="dialog" aria-modal="true" aria-labelledby="argus-activity-title"
             style="background:var(--bg-2,#15110A);color:var(--text,#EAD8C0);
                    border:1px solid var(--border-m,rgba(184,115,51,0.28));
                    border-radius:14px;width:min(900px,96vw);max-height:92vh;overflow:auto;
                    box-shadow:0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) inset;
                    animation:argusConfirmPop 220ms cubic-bezier(0.22,1,0.36,1);">
            <div style="padding:18px 22px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--border);">
                <div>
                    <span class="argus-eyebrow">Tu actividad</span>
                    <h2 id="argus-activity-title" class="section-title" style="margin:6px 0 0;">Mi panel personal</h2>
                </div>
                <button id="argus-activity-close" type="button" aria-label="Cerrar"
                    style="background:transparent;border:1px solid var(--border-m);color:var(--text-m);width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:18px;line-height:1;flex-shrink:0;">×</button>
            </div>
            <div class="argus-chip-tabs" role="tablist" aria-label="Secciones de mi actividad" style="display:flex;gap:6px;padding:14px 22px 0;border-bottom:1px solid var(--border);flex-wrap:wrap;">
                <button class="argus-chip-tab" role="tab" aria-selected="true" tabindex="0" data-myact-tab="heatmap" style="padding:8px 14px;border-radius:8px;border:1px solid var(--border-m,rgba(184,115,51,0.28));background:rgba(180,138,98,0.18);color:var(--text);font-weight:700;font-size:12.5px;cursor:pointer;letter-spacing:0.3px;">Heatmap</button>
                <button class="argus-chip-tab" role="tab" aria-selected="false" tabindex="-1" data-myact-tab="risk" style="padding:8px 14px;border-radius:8px;border:1px solid var(--border-m,rgba(184,115,51,0.28));background:transparent;color:var(--text-m);font-weight:700;font-size:12.5px;cursor:pointer;letter-spacing:0.3px;">Risk score</button>
                <button class="argus-chip-tab" role="tab" aria-selected="false" tabindex="-1" data-myact-tab="achievements" style="padding:8px 14px;border-radius:8px;border:1px solid var(--border-m,rgba(184,115,51,0.28));background:transparent;color:var(--text-m);font-weight:700;font-size:12.5px;cursor:pointer;letter-spacing:0.3px;">Logros</button>
            </div>
            <div id="argus-activity-body" style="padding:22px;">
                <div style="display:flex;align-items:center;justify-content:center;padding:60px 0;color:var(--text-d);font-size:13px;">Cargando actividad…</div>
            </div>
        </div>`;
    document.body.appendChild(root);

    const close = () => {
        document.removeEventListener('keydown', onKey, true);
        root.style.animation = 'argusConfirmFadeOut 140ms ease';
        setTimeout(() => root.remove(), 130);
    };
    const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close(); } };
    document.addEventListener('keydown', onKey, true);
    root.querySelector('#argus-activity-close').addEventListener('click', close);
    root.addEventListener('click', (e) => { if (e.target === root) close(); });

    // Cargar ambos endpoints en paralelo
    const body = root.querySelector('#argus-activity-body');
    const [heatmapRes, statsRes] = await Promise.allSettled([
        fetch('/api/staff/my-activity-heatmap?days=365').then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))),
        fetch('/api/staff/my-stats').then(r => r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))),
    ]);
    const heatmapData = heatmapRes.status === 'fulfilled' ? heatmapRes.value : null;
    const statsData   = statsRes.status   === 'fulfilled' ? statsRes.value   : {};

    if (!heatmapData) {
        const errMsg = heatmapRes.reason && heatmapRes.reason.message;
        body.innerHTML = `<div style="color:#f87171;text-align:center;padding:40px;font-size:13px;">No se pudo cargar la actividad: ${errMsg || 'error'}</div>`;
        return;
    }

    // Renderizar tab inicial: heatmap
    function renderTab(tab) {
        if (tab === 'heatmap') {
            _renderActivityHeatmap(body, heatmapData);
        } else if (tab === 'risk') {
            _renderRiskTab(body, statsData);
        } else if (tab === 'achievements') {
            // Mergear datos de heatmap (streak, days_active) con stats
            const merged = Object.assign({}, statsData, {
                streak:       heatmapData.streak       || statsData.streak || 0,
                best_streak:  heatmapData.best_streak  || statsData.best_streak || 0,
                days_active:  Math.max(heatmapData.days_active || 0, statsData.days_active || 0),
                scans_total:  heatmapData.total_count || 0,
            });
            _renderAchievementsTab(body, merged);
        }
    }
    renderTab('heatmap');

    // Tab switching
    root.querySelectorAll('[data-myact-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.getAttribute('data-myact-tab');
            root.querySelectorAll('[data-myact-tab]').forEach(b => {
                const isActive = b === btn;
                b.setAttribute('aria-selected', isActive ? 'true' : 'false');
                b.setAttribute('tabindex', isActive ? '0' : '-1');
                b.style.background = isActive ? 'rgba(180,138,98,0.18)' : 'transparent';
                b.style.color = isActive ? 'var(--text)' : 'var(--text-m)';
            });
            renderTab(tab);
        });
    });
}

function _renderRiskTab(container, stats) {
    const history = (stats && stats.history) || [];
    const avg30 = stats && stats.avg_risk_30d || 0;
    const total = stats && stats.verdicts_total || 0;
    const clean = stats && stats.clean_count || 0;
    const hack  = stats && stats.hack_count  || 0;
    const sus   = stats && stats.sus_count   || 0;
    container.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:18px;">
            <div style="padding:14px;border-radius:10px;border:1px solid var(--border-m);background:rgba(255,255,255,0.02);">
                <div style="font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.6px;">Veredictos</div>
                <div style="font-size:24px;font-weight:800;color:var(--text);font-feature-settings:'tnum';">${total}</div>
            </div>
            <div style="padding:14px;border-radius:10px;border:1px solid var(--border-m);background:rgba(91,193,128,0.06);">
                <div style="font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.6px;">Limpios</div>
                <div style="font-size:24px;font-weight:800;color:#5BC180;font-feature-settings:'tnum';">${clean}</div>
            </div>
            <div style="padding:14px;border-radius:10px;border:1px solid var(--border-m);background:rgba(255,184,107,0.06);">
                <div style="font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.6px;">Sospechosos</div>
                <div style="font-size:24px;font-weight:800;color:#FFB86B;font-feature-settings:'tnum';">${sus}</div>
            </div>
            <div style="padding:14px;border-radius:10px;border:1px solid var(--border-m);background:rgba(255,107,107,0.06);">
                <div style="font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.6px;">Hacks</div>
                <div style="font-size:24px;font-weight:800;color:#FF6B6B;font-feature-settings:'tnum';">${hack}</div>
            </div>
            <div style="padding:14px;border-radius:10px;border:1px solid var(--border-m);background:rgba(255,255,255,0.02);">
                <div style="font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.6px;">Risk avg 30d</div>
                <div style="font-size:24px;font-weight:800;color:var(--text);font-feature-settings:'tnum';">${avg30}</div>
            </div>
        </div>
        <div style="border:1px solid var(--border-m);border-radius:12px;padding:16px;background:rgba(255,255,255,0.02);">
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;">
                <span class="argus-eyebrow">Histórico · 30 días</span>
                <span style="font-size:11px;color:var(--text-d);">Risk score promedio diario</span>
            </div>
            <div id="argus-myact-chart" style="min-height:200px;"></div>
        </div>
    `;
    if (history.length && window.argusUI && argusUI.renderLineChart) {
        argusUI.renderLineChart('#argus-myact-chart', history);
    } else {
        const chart = container.querySelector('#argus-myact-chart');
        if (chart) {
            argusUI.renderEmptyState(chart, {
                icon: 'chart',
                title: 'Aún no hay histórico',
                description: 'Tras confirmar veredictos, vas a ver tu evolución acá.',
            });
        }
    }
}

function _renderAchievementsTab(container, mergedStats) {
    container.innerHTML = `<div id="argus-myact-achievements"></div>`;
    if (window.argusUI && argusUI.renderAchievements) {
        argusUI.renderAchievements('#argus-myact-achievements', mergedStats);
    }
}
window.openMyActivityHeatmap = openMyActivityHeatmap;


/**
 * Visual #46 — Comparador lado-a-lado: scan actual vs scan anterior
 * del mismo MC user / misma máquina. Muestra diff de risk score,
 * verdict, conteo de issues y archivos escaneados, con flechas ↗↘=
 * y porcentaje de cambio para cada métrica.
 */
async function openCompareScansModal(scanId) {
    if (!scanId) {
        if (window.showToast) showToast('No hay escaneo abierto.', 'warning');
        return;
    }
    document.getElementById('argus-compare-modal')?.remove();

    const root = document.createElement('div');
    root.id = 'argus-compare-modal';
    root.style.cssText = 'position:fixed;inset:0;z-index:99996;display:flex;align-items:center;justify-content:center;padding:24px;background:rgba(8,6,4,0.62);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);animation:argusConfirmFadeIn 180ms ease;';
    root.innerHTML = `
        <div role="dialog" aria-modal="true" aria-labelledby="argus-compare-title"
             style="background:var(--bg-2,#15110A);color:var(--text,#EAD8C0);
                    border:1px solid var(--border-m,rgba(184,115,51,0.28));
                    border-radius:14px;width:min(960px,96vw);max-height:92vh;overflow:auto;
                    box-shadow:0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) inset;
                    animation:argusConfirmPop 220ms cubic-bezier(0.22,1,0.36,1);">
            <div style="padding:18px 22px 12px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid var(--border);">
                <div>
                    <span class="argus-eyebrow">Comparador</span>
                    <h2 id="argus-compare-title" class="section-title" style="margin:6px 0 0;">Scan #${scanId} vs anteriores</h2>
                </div>
                <button id="argus-compare-close" type="button" aria-label="Cerrar"
                    style="background:transparent;border:1px solid var(--border-m);color:var(--text-m);width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:18px;line-height:1;flex-shrink:0;">×</button>
            </div>
            <div id="argus-compare-body" style="padding:22px;">
                <div style="display:flex;align-items:center;justify-content:center;padding:60px 0;color:var(--text-d);font-size:13px;">
                    <span class="argus-pulse-dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--accent);margin-right:10px;animation:argusPulse 1.4s ease infinite;"></span>
                    Buscando scans del mismo jugador…
                </div>
            </div>
        </div>`;
    document.body.appendChild(root);

    const close = () => {
        document.removeEventListener('keydown', onKey, true);
        root.style.animation = 'argusConfirmFadeOut 140ms ease';
        setTimeout(() => root.remove(), 130);
    };
    const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); close(); } };
    document.addEventListener('keydown', onKey, true);
    root.querySelector('#argus-compare-close').addEventListener('click', close);
    root.addEventListener('click', (e) => { if (e.target === root) close(); });

    let related;
    try {
        const r = await fetch(`/api/scans/${scanId}/related?limit=8`);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        related = await r.json();
    } catch (e) {
        const body = root.querySelector('#argus-compare-body');
        if (body) body.innerHTML = `<div style="color:#f87171;text-align:center;padding:40px;font-size:13px;">No se pudieron cargar scans relacionados: ${e.message || e}</div>`;
        return;
    }

    const others = Array.isArray(related?.scans) ? related.scans : [];
    const anchorUser = related?.anchor_user || '';

    if (!others.length) {
        const body = root.querySelector('#argus-compare-body');
        if (body) {
            body.innerHTML = `
                <div style="text-align:center;padding:60px 20px;">
                    <div style="font-size:54px;margin-bottom:14px;opacity:0.55;">🔍</div>
                    <div style="font-size:15px;font-weight:700;color:var(--text-h);margin-bottom:8px;">No hay scans previos</div>
                    <div style="font-size:13px;color:var(--text-m);max-width:420px;margin:0 auto;line-height:1.6;">
                        Este es el primer scan registrado para
                        <b>${anchorUser ? _qsEscapeSafe(anchorUser) : 'este jugador'}</b>
                        en tu empresa. Cuando vuelva a scanearse, podrás comparar la evolución del risk score, veredicto y hallazgos lado-a-lado.
                    </div>
                </div>`;
        }
        return;
    }

    // El "current" lo armamos a partir de _currentScanData (ya cargado en
    // viewScanDetails) — evita un segundo fetch.
    const cur = window._currentScanData || {};
    const current = {
        id:              scanId,
        minecraft_user:  cur.minecraft_username || cur.minecraft_user || anchorUser || '—',
        machine_name:    cur.machine_name || '—',
        started_at:      cur.started_at || cur.created_at || '',
        risk_score:      cur.risk_score,
        verdict:         cur.verdict || '',
        country:         cur.country || '',
        issues_found:    cur.issues_found || (cur.results ? cur.results.length : 0),
        issues_critical: (cur.results || []).filter(x => x.alert_level === 'CRITICAL').length || cur.issues_critical || 0,
        total_files_scanned: cur.total_files_scanned || 0,
    };

    _renderCompareScansBody(root.querySelector('#argus-compare-body'), current, others);
}
window.openCompareScansModal = openCompareScansModal;

function _qsEscapeSafe(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;',
    })[c]);
}

function _verdictChip(v) {
    const t = String(v || '').toLowerCase();
    if (t.includes('limp') || t === 'clean')
        return '<span style="display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:0.5px;padding:2px 8px;border-radius:999px;background:rgba(16,185,129,0.14);color:#34d399;border:1px solid rgba(16,185,129,0.32);">CLEAN</span>';
    if (t.includes('hack'))
        return '<span style="display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:0.5px;padding:2px 8px;border-radius:999px;background:rgba(239,68,68,0.14);color:#f87171;border:1px solid rgba(239,68,68,0.32);">HACK</span>';
    return '<span style="display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:0.5px;padding:2px 8px;border-radius:999px;background:rgba(184,115,51,0.10);color:var(--text-m);border:1px solid var(--border-m);">PENDIENTE</span>';
}

function _renderCompareScansBody(container, current, others) {
    if (!container) return;

    // Selector dropdown si hay >1
    const opts = others.map((o, i) =>
        `<option value="${o.id}" ${i === 0 ? 'selected' : ''}>#${o.id} — ${(o.started_at || '').slice(0, 16)} · risk ${o.risk_score == null ? '—' : o.risk_score}</option>`
    ).join('');

    const headerHtml = `
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px;">
            <div style="font-size:12px;color:var(--text-m);">Comparando contra:</div>
            <select id="argus-compare-pick"
                style="background:var(--bg-3);color:var(--text);border:1px solid var(--border-m);
                       border-radius:6px;padding:6px 10px;font-size:12px;font-family:'JetBrains Mono', monospace;
                       cursor:pointer;">
                ${opts}
            </select>
            <span style="font-size:11.5px;color:var(--text-d);">${others.length} scan(s) anteriores encontrados</span>
        </div>
        <div id="argus-compare-grid"></div>`;
    container.innerHTML = headerHtml;

    const grid = container.querySelector('#argus-compare-grid');
    const select = container.querySelector('#argus-compare-pick');
    const draw = () => {
        const id = parseInt(select.value, 10);
        const other = others.find(o => o.id === id) || others[0];
        grid.innerHTML = _buildCompareGridHtml(current, other);
    };
    select.addEventListener('change', draw);
    draw();
}

function _buildCompareGridHtml(a, b) {
    // a = scan actual, b = scan previo
    const fmt = (v) => v == null || v === '' ? '—' : v;
    const num = (v) => typeof v === 'number' ? v : (parseInt(v, 10) || 0);
    const arrow = (delta, invert = false) => {
        // invert=true: aumentar es bueno (ej: total_files_scanned).
        // Para risk_score / issues, BAJAR es bueno → flecha hacia abajo verde.
        if (delta === 0) return '<span style="color:var(--text-d);">=</span>';
        const up = delta > 0;
        const good = invert ? up : !up;
        const color = good ? '#10b981' : '#ef4444';
        const sym = up ? '↗' : '↘';
        return `<span style="color:${color};font-weight:800;font-size:14px;">${sym} ${Math.abs(delta)}</span>`;
    };
    const pctDelta = (curV, prevV) => {
        const c = num(curV), p = num(prevV);
        if (!p) return c ? '+∞' : '0%';
        return ((c - p) / p * 100).toFixed(0) + '%';
    };

    const card = (title, value, subtitle = '', accent = 'var(--text)') => `
        <div style="padding:14px 16px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;flex:1;min-width:140px;">
            <div style="font-size:10.5px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-d);">${title}</div>
            <div style="font-size:22px;font-weight:800;color:${accent};margin-top:4px;font-feature-settings:'tnum' 1;">${value}</div>
            ${subtitle ? `<div style="font-size:11.5px;color:var(--text-m);margin-top:3px;">${subtitle}</div>` : ''}
        </div>`;

    const colCss = `display:grid;grid-template-columns:1fr 1fr;gap:12px;`;
    const colHeaderCss = `padding:10px 14px;border-radius:8px;font-size:13px;font-weight:700;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;`;
    const aHeader = `<div style="${colHeaderCss}background:rgba(184,115,51,0.10);border:1px solid rgba(184,115,51,0.30);color:var(--accent);">
        <span>Actual · #${a.id}</span><span style="font-size:11px;color:var(--text-d);font-family:JetBrains Mono,monospace;">${(a.started_at || '').slice(0, 16)}</span>
    </div>`;
    const bHeader = `<div style="${colHeaderCss}background:rgba(96,165,250,0.10);border:1px solid rgba(96,165,250,0.32);color:#60a5fa;">
        <span>Anterior · #${b.id}</span><span style="font-size:11px;color:var(--text-d);font-family:JetBrains Mono,monospace;">${(b.started_at || '').slice(0, 16)}</span>
    </div>`;

    // Risk score con coloración por umbral
    const riskA = num(a.risk_score), riskB = num(b.risk_score);
    const riskColor = (s) => s >= 70 ? '#ef4444' : s >= 30 ? '#fbbf24' : '#10b981';

    // Diffs row
    const diffRiskCard = `
        <div style="padding:14px 16px;background:linear-gradient(135deg, rgba(184,115,51,0.06), rgba(96,165,250,0.06));border:1px dashed var(--border-m);border-radius:10px;flex:1;min-width:160px;">
            <div style="font-size:10.5px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-d);">Δ Risk Score</div>
            <div style="font-size:22px;font-weight:800;margin-top:4px;display:flex;align-items:center;gap:10px;">
                ${arrow(riskA - riskB)}
                <span style="font-size:13px;color:var(--text-m);font-weight:600;">${pctDelta(riskA, riskB)}</span>
            </div>
            <div style="font-size:11.5px;color:var(--text-m);margin-top:3px;">${riskA - riskB === 0 ? 'Mismo score' : (riskA - riskB > 0 ? 'Empeoró' : 'Mejoró')}</div>
        </div>`;

    const issA = num(a.issues_found), issB = num(b.issues_found);
    const critA = num(a.issues_critical), critB = num(b.issues_critical);
    const filesA = num(a.total_files_scanned), filesB = num(b.total_files_scanned);
    const diffIssuesCard = `
        <div style="padding:14px 16px;background:linear-gradient(135deg, rgba(184,115,51,0.06), rgba(96,165,250,0.06));border:1px dashed var(--border-m);border-radius:10px;flex:1;min-width:160px;">
            <div style="font-size:10.5px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-d);">Δ Issues</div>
            <div style="font-size:22px;font-weight:800;margin-top:4px;display:flex;align-items:center;gap:10px;">${arrow(issA - issB)}</div>
            <div style="font-size:11.5px;color:var(--text-m);margin-top:3px;">Críticos: ${arrow(critA - critB)}</div>
        </div>`;
    const diffFilesCard = `
        <div style="padding:14px 16px;background:linear-gradient(135deg, rgba(184,115,51,0.06), rgba(96,165,250,0.06));border:1px dashed var(--border-m);border-radius:10px;flex:1;min-width:160px;">
            <div style="font-size:10.5px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-d);">Δ Archivos escaneados</div>
            <div style="font-size:22px;font-weight:800;margin-top:4px;display:flex;align-items:center;gap:10px;">${arrow(filesA - filesB, true)}</div>
            <div style="font-size:11.5px;color:var(--text-m);margin-top:3px;">${pctDelta(filesA, filesB)} variación</div>
        </div>`;

    return `
        <div style="${colCss}">
            ${aHeader}
            ${bHeader}
        </div>
        <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;">
            ${card('Risk score', `<span style="color:${riskColor(riskA)}">${fmt(a.risk_score)}</span>`, _verdictChip(a.verdict))}
            ${card('Risk score', `<span style="color:${riskColor(riskB)}">${fmt(b.risk_score)}</span>`, _verdictChip(b.verdict))}
        </div>
        <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;">
            ${card('Hallazgos', `${fmt(a.issues_found)}`, `${fmt(a.issues_critical)} críticos`)}
            ${card('Hallazgos', `${fmt(b.issues_found)}`, `${fmt(b.issues_critical)} críticos`)}
        </div>
        <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;">
            ${card('Archivos escaneados', filesA.toLocaleString(), '')}
            ${card('Archivos escaneados', filesB.toLocaleString(), '')}
        </div>
        <div style="display:flex;gap:12px;margin-top:12px;flex-wrap:wrap;">
            ${card('Máquina', _qsEscapeSafe(fmt(a.machine_name)), `${_qsEscapeSafe(fmt(a.country))}`)}
            ${card('Máquina', _qsEscapeSafe(fmt(b.machine_name)), `${_qsEscapeSafe(fmt(b.country))}`)}
        </div>

        <div style="margin-top:22px;padding-top:16px;border-top:1px solid var(--border);">
            <div style="font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:var(--text-d);margin-bottom:10px;">Resumen del cambio</div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;">
                ${diffRiskCard}
                ${diffIssuesCard}
                ${diffFilesCard}
            </div>
        </div>

        <div style="margin-top:18px;display:flex;gap:8px;flex-wrap:wrap;">
            <button onclick="viewScanDetails(${b.id});document.getElementById('argus-compare-modal')?.remove();"
                style="font-size:12px;padding:8px 14px;border-radius:8px;cursor:pointer;border:1px solid rgba(96,165,250,0.4);background:rgba(96,165,250,0.06);color:#60a5fa;">
                Abrir scan anterior →
            </button>
            <button onclick="copyScanLink(${b.id})"
                style="font-size:12px;padding:8px 14px;border-radius:8px;cursor:pointer;border:1px solid var(--border-m);background:transparent;color:var(--text-m);">
                Copiar enlace al anterior
            </button>
        </div>`;
}

function _renderActivityHeatmap(container, data) {
    if (!container) return;
    const days = Array.isArray(data?.days) ? data.days : [];
    const today = data?.today ? new Date(data.today + 'T00:00:00') : new Date();
    const daysBack = data?.days_back || 365;
    const total  = data?.total_count || 0;
    const active = data?.days_active || 0;
    const streak = data?.streak || 0;
    const best   = data?.best_streak || 0;

    // Index para lookups O(1)
    const counts = {};
    let maxCount = 0;
    for (const d of days) {
        counts[d.date] = d.count;
        if (d.count > maxCount) maxCount = d.count;
    }

    // Generar la grilla: empezamos desde un domingo `daysBack-1` días atrás
    const start = new Date(today);
    start.setDate(start.getDate() - (daysBack - 1));
    // Alinear al domingo previo (domingo = 0)
    const startDow = start.getDay();
    start.setDate(start.getDate() - startDow);

    // Total de semanas a renderizar
    const totalDays = Math.ceil((today.getTime() - start.getTime()) / (24*3600*1000)) + 1;
    const weeks = Math.ceil(totalDays / 7);

    // Helper: intensidad 0-4 según count vs maxCount (escala log)
    const intensity = (c) => {
        if (!c) return 0;
        if (!maxCount) return 0;
        const ratio = Math.log(c + 1) / Math.log(maxCount + 1);
        if (ratio < 0.25) return 1;
        if (ratio < 0.50) return 2;
        if (ratio < 0.75) return 3;
        return 4;
    };
    const colors = [
        'rgba(255,255,255,0.04)',
        'rgba(184,115,51,0.22)',
        'rgba(184,115,51,0.45)',
        'rgba(212,145,90,0.72)',
        '#D4915A',
    ];

    // Stats top row
    const statsHtml = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px;">
            <div style="padding:14px 16px;background:rgba(184,115,51,0.06);border:1px solid var(--border);border-radius:10px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--text-d);">Acciones totales</div>
                <div style="font-size:24px;font-weight:800;color:var(--accent);font-feature-settings:'tnum' 1;margin-top:4px;">${total}</div>
            </div>
            <div style="padding:14px 16px;background:rgba(184,115,51,0.06);border:1px solid var(--border);border-radius:10px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--text-d);">Días activos</div>
                <div style="font-size:24px;font-weight:800;color:var(--text);font-feature-settings:'tnum' 1;margin-top:4px;">${active} <span style="font-size:13px;font-weight:500;color:var(--text-d);">/ ${daysBack}</span></div>
            </div>
            <div style="padding:14px 16px;background:rgba(184,115,51,0.06);border:1px solid var(--border);border-radius:10px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--text-d);">Racha actual</div>
                <div style="font-size:24px;font-weight:800;color:${streak >= 7 ? '#fbbf24' : 'var(--text)'};font-feature-settings:'tnum' 1;margin-top:4px;">${streak} <span style="font-size:13px;font-weight:500;color:var(--text-d);">${streak === 1 ? 'día' : 'días'}</span></div>
            </div>
            <div style="padding:14px 16px;background:rgba(184,115,51,0.06);border:1px solid var(--border);border-radius:10px;">
                <div style="font-size:11px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:var(--text-d);">Mejor racha</div>
                <div style="font-size:24px;font-weight:800;color:var(--text);font-feature-settings:'tnum' 1;margin-top:4px;">${best} <span style="font-size:13px;font-weight:500;color:var(--text-d);">${best === 1 ? 'día' : 'días'}</span></div>
            </div>
        </div>`;

    // Grid construction
    const cellSize = 13;
    const cellGap  = 3;
    const gridW = weeks * (cellSize + cellGap) - cellGap;
    const gridH = 7   * (cellSize + cellGap) - cellGap;

    let cells = '';
    let monthLabels = '';
    let lastMonth = -1;

    for (let w = 0; w < weeks; w++) {
        // Tag del mes (sobre la primera columna de cada mes)
        const colDate = new Date(start);
        colDate.setDate(colDate.getDate() + w * 7);
        if (colDate.getMonth() !== lastMonth) {
            const monthName = ['ENE','FEB','MAR','ABR','MAY','JUN','JUL','AGO','SEP','OCT','NOV','DIC'][colDate.getMonth()];
            monthLabels += `<text x="${w * (cellSize + cellGap)}" y="9" font-size="9.5" font-family="JetBrains Mono, monospace" fill="rgba(234,216,192,0.45)" font-weight="700" letter-spacing="0.5">${monthName}</text>`;
            lastMonth = colDate.getMonth();
        }

        for (let d = 0; d < 7; d++) {
            const cellDate = new Date(start);
            cellDate.setDate(cellDate.getDate() + w * 7 + d);
            if (cellDate > today) continue;
            const dateStr = cellDate.toISOString().slice(0, 10);
            const c = counts[dateStr] || 0;
            const lvl = intensity(c);
            const fill = colors[lvl];
            const isToday = (cellDate.toDateString() === today.toDateString());
            const stroke = isToday ? '#fbbf24' : (lvl > 0 ? 'rgba(184,115,51,0.32)' : 'rgba(184,115,51,0.10)');
            const tooltip = c > 0
                ? `${c} ${c === 1 ? 'acción' : 'acciones'} · ${dateStr}`
                : `Sin actividad · ${dateStr}`;
            cells += `<rect x="${w * (cellSize + cellGap)}" y="${d * (cellSize + cellGap) + 14}" width="${cellSize}" height="${cellSize}" rx="2.5" ry="2.5"
                fill="${fill}" stroke="${stroke}" stroke-width="${isToday ? 1.5 : 0.8}"
                data-tip="${tooltip}"
                style="transition:transform 120ms ease, filter 120ms ease;cursor:default;"
                onmouseover="this.style.filter='brightness(1.35)';this.style.transform='scale(1.18)';this.style.transformOrigin='${w * (cellSize + cellGap) + cellSize/2}px ${d * (cellSize + cellGap) + 14 + cellSize/2}px';"
                onmouseout="this.style.filter='';this.style.transform='';"></rect>`;
        }
    }

    // Day-of-week labels (col izquierda)
    const dowLabels = ['','Lun','','Mié','','Vie',''];
    let dowSvg = '';
    for (let i = 0; i < 7; i++) {
        if (!dowLabels[i]) continue;
        dowSvg += `<text x="-4" y="${i * (cellSize + cellGap) + 14 + cellSize - 3}" font-size="9" text-anchor="end" font-family="JetBrains Mono, monospace" fill="rgba(234,216,192,0.45)">${dowLabels[i]}</text>`;
    }

    // Legend (derecha)
    const legendHtml = `
        <div style="display:flex;align-items:center;gap:10px;margin-top:14px;font-size:11px;color:var(--text-d);font-family:'JetBrains Mono', monospace;">
            <span style="opacity:0.7;">Menos</span>
            <span style="display:inline-block;width:13px;height:13px;border-radius:2.5px;background:${colors[0]};border:1px solid rgba(184,115,51,0.10);"></span>
            <span style="display:inline-block;width:13px;height:13px;border-radius:2.5px;background:${colors[1]};"></span>
            <span style="display:inline-block;width:13px;height:13px;border-radius:2.5px;background:${colors[2]};"></span>
            <span style="display:inline-block;width:13px;height:13px;border-radius:2.5px;background:${colors[3]};"></span>
            <span style="display:inline-block;width:13px;height:13px;border-radius:2.5px;background:${colors[4]};"></span>
            <span style="opacity:0.7;">Más</span>
            <span style="margin-left:auto;color:var(--text-m);">Hoy resaltado en amarillo · Pasá el cursor por una celda para ver el conteo.</span>
        </div>`;

    const heatmapHtml = `
        <div style="overflow-x:auto;padding:6px 4px 6px 28px;">
            <svg id="argus-activity-svg" width="${gridW + 6}" height="${gridH + 22}" viewBox="0 0 ${gridW + 6} ${gridH + 22}" style="display:block;">
                ${monthLabels}
                <g transform="translate(0,0)">${dowSvg}</g>
                ${cells}
            </svg>
        </div>
        ${legendHtml}`;

    container.innerHTML = statsHtml + heatmapHtml;

    // Tooltip simple sobre las celdas (data-tip)
    const svg = container.querySelector('#argus-activity-svg');
    if (svg) {
        let tip = null;
        svg.addEventListener('mousemove', (e) => {
            const t = e.target;
            if (!(t instanceof SVGRectElement)) {
                if (tip) { tip.remove(); tip = null; }
                return;
            }
            const text = t.getAttribute('data-tip');
            if (!text) return;
            if (!tip) {
                tip = document.createElement('div');
                tip.style.cssText = 'position:fixed;z-index:99997;pointer-events:none;background:rgba(20,16,10,0.96);color:#EAD8C0;border:1px solid rgba(184,115,51,0.32);border-radius:6px;padding:6px 10px;font-size:11.5px;font-family:JetBrains Mono, monospace;box-shadow:0 8px 22px rgba(0,0,0,0.45);white-space:nowrap;';
                document.body.appendChild(tip);
            }
            tip.textContent = text;
            tip.style.left = (e.clientX + 12) + 'px';
            tip.style.top  = (e.clientY - 28) + 'px';
        });
        svg.addEventListener('mouseleave', () => { if (tip) { tip.remove(); tip = null; } });
    }
}

async function copyScanLink(scanId) {
    if (!scanId) {
        if (typeof showToast === 'function') {
            showToast('No hay un escaneo abierto para copiar.', 'warning');
        }
        return;
    }
    const url = `${window.location.origin}${window.location.pathname}?scan=${scanId}`;
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(url);
        } else {
            // Fallback para HTTP / browsers viejos
            const ta = document.createElement('textarea');
            ta.value = url;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            ta.remove();
        }
        if (typeof showToast === 'function') {
            showToast(`Enlace al escaneo #${scanId} copiado`, 'success', { duration: 3500 });
        }
    } catch (e) {
        console.warn('copyScanLink fallo:', e);
        if (typeof showToast === 'function') {
            showToast('No se pudo copiar el enlace. Copialo manualmente:\n' + url, 'error');
        }
    }
}

function showSection(sectionName) {
    console.log('Cambiando a sección:', sectionName);
    
    // Actualizar navegación activa
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    const navItem = document.querySelector(`[data-section="${sectionName}"]`);
    if (navItem) {
        navItem.classList.add('active');
    } else {
        console.error('No se encontró elemento de navegación para:', sectionName);
    }

    // Ocultar todas las secciones
    document.querySelectorAll('.panel-section').forEach(section => {
        section.classList.remove('active');
        section.style.display = 'none';
    });

    // Mostrar sección seleccionada
    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
        targetSection.classList.add('active');
        targetSection.style.display = 'block';
        console.log('Sección mostrada:', targetSection.id);
    } else {
        console.error('No se encontró sección con ID:', `${sectionName}-section`);
    }

    // Actualizar título
    const titles = {
        'dashboard': 'Dashboard',
        'generar-app': 'Generar Aplicación',
        'tokens': 'Gestión de Tokens',
        'resultados': 'Resultados de Escaneos',
        'aprendizaje': 'Sistema de Aprendizaje',
        'administracion': 'Administración',
        'mi-empresa': 'Mi Empresa',
        'equipo': 'Equipo',
        'anticheat': 'Anti-Cheat',
        'argusai': 'Argus AI Oracle',
        'super-admin': 'Super Admin',
    };
    const titleElement = document.getElementById('section-title');
    if (titleElement) {
        titleElement.textContent = titles[sectionName] || 'Panel Staff';
    }
    
    // Cargar datos específicos de cada sección
    if (sectionName === 'administracion') {
        loadRegistrationTokens();
        loadDownloadLinks();
        loadUsers();
        loadCompanyUsersForAdmin();
        loadCompanyNotifications();
        loadCompanyGameProfiles();
    } else if (sectionName === 'mi-empresa') {
        loadCompanyInfo();
        loadCompanyTokens();
        loadCompanyUsers();
    } else if (sectionName === 'staff') {
        loadStaffUsers();
    } else if (sectionName === 'equipo') {
        loadStaffUsers();
        loadEquipoCompanyData();
    }

    // Limpiar badge de nuevos scans al visitar las secciones relacionadas
    if (sectionName === 'resultados' || sectionName === 'dashboard') {
        clearNewScansBadge();
    }

    // Cargar datos según sección
    switch(sectionName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'tokens':
            loadTokens();
            break;
        case 'resultados':
            loadScans();
            break;
        case 'generar-app':
            loadLearningStats();
            break;
    }
}

async function loadCompanyNotifications() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    if (!companyId) return;
    try {
        const r = await fetch(`/api/companies/${companyId}/notifications`);
        const d = await r.json();
        if (!d || !d.success) return;
        const items = Array.isArray(d.items) ? d.items : [];
        const discord = items.find(x => (x.type || '').toLowerCase() === 'discord') || {};
        const telegram = items.find(x => (x.type || '').toLowerCase() === 'telegram') || {};
        const minLevel = discord.filter_min_level || telegram.filter_min_level || 'HIGH';
        const dUrl = document.getElementById('notif-discord-url');
        const dEn = document.getElementById('notif-discord-enabled');
        const tUrl = document.getElementById('notif-telegram-url');
        const tEn = document.getElementById('notif-telegram-enabled');
        const lvl = document.getElementById('notif-min-level');
        if (dUrl) dUrl.value = discord.webhook_url || '';
        if (dEn) dEn.checked = !!discord.enabled;
        if (tUrl) tUrl.value = telegram.webhook_url || '';
        if (tEn) tEn.checked = !!telegram.enabled;
        if (lvl) lvl.value = minLevel;
    } catch (_) {}
}
window.loadCompanyNotifications = loadCompanyNotifications;

async function saveCompanyNotifications() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    if (!companyId) { showToast('No hay company_id activo', 'error'); return; }
    const minLevel = (document.getElementById('notif-min-level')?.value || 'HIGH').toUpperCase();
    const items = [
        {
            type: 'discord',
            webhook_url: (document.getElementById('notif-discord-url')?.value || '').trim(),
            enabled: !!document.getElementById('notif-discord-enabled')?.checked,
            filter_min_level: minLevel,
        },
        {
            type: 'telegram',
            webhook_url: (document.getElementById('notif-telegram-url')?.value || '').trim(),
            enabled: !!document.getElementById('notif-telegram-enabled')?.checked,
            filter_min_level: minLevel,
        },
    ];
    try {
        const r = await fetch(`/api/companies/${companyId}/notifications`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items }),
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo guardar');
        showToast('Notifications guardadas', 'success');
    } catch (e) {
        showToast(`Error guardando notifications: ${e.message}`, 'error');
    }
}
window.saveCompanyNotifications = saveCompanyNotifications;

async function previewCompanyDigest() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    if (!companyId) return;
    const out = document.getElementById('notif-preview');
    if (out) out.textContent = 'Generando preview...';
    try {
        const r = await fetch(`/api/admin/digest/preview?company_id=${encodeURIComponent(companyId)}`);
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        if (out) out.textContent = d.text_preview || JSON.stringify(d.digest || {}, null, 2);
    } catch (e) {
        if (out) out.textContent = `Error preview: ${e.message}`;
    }
}
window.previewCompanyDigest = previewCompanyDigest;

async function loadCompanyGameProfiles() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    const sel = document.getElementById('company-game-profile-select');
    if (!sel || !companyId) return;
    try {
        const [rp, rc] = await Promise.all([
            fetch('/api/game-profiles'),
            fetch(`/api/companies/${companyId}/game-profile`)
        ]);
        const pd = await rp.json();
        const cd = await rc.json();
        const items = (pd && pd.success && Array.isArray(pd.items)) ? pd.items : [];
        sel.innerHTML = items.map(x => `<option value="${x.id}">${escapeHtml(x.name)} (${escapeHtml(x.slug)})</option>`).join('');
        const activeId = cd && cd.success && cd.profile ? Number(cd.profile.game_profile_id || 0) : 0;
        if (activeId) sel.value = String(activeId);
    } catch (e) {
        if (typeof showToast === 'function') showToast(`Error profiles: ${e.message}`, 'error');
    }
}
window.loadCompanyGameProfiles = loadCompanyGameProfiles;

async function saveCompanyGameProfile() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    const sel = document.getElementById('company-game-profile-select');
    if (!companyId || !sel) return;
    try {
        const game_profile_id = Number(sel.value || 0);
        const r = await fetch(`/api/companies/${companyId}/game-profile`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_profile_id })
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo guardar');
        showToast('Game profile guardado', 'success');
    } catch (e) {
        showToast(`Error guardando profile: ${e.message}`, 'error');
    }
}
window.saveCompanyGameProfile = saveCompanyGameProfile;

async function browseSharedRules() {
    const box = document.getElementById('shared-rules-preview');
    if (box) box.textContent = 'Cargando marketplace...';
    try {
        const r = await fetch('/api/shared-rules?page=1&per_page=10');
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        const items = d.items || [];
        if (!items.length) { if (box) box.textContent = 'No hay reglas públicas.'; return; }
        if (box) {
            box.textContent = items.map(x => `#${x.id} ${x.name} · ⭐ ${Number(x.rating_avg || 0).toFixed(2)} · ⬇ ${x.downloads_count}`).join('\n');
        }
    } catch (e) {
        if (box) box.textContent = `Error marketplace: ${e.message}`;
    }
}
window.browseSharedRules = browseSharedRules;

async function exportFiltersConfig() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    if (!companyId) return;
    try {
        const r = await fetch(`/api/filters/export?company_id=${encodeURIComponent(companyId)}`);
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'Export falló');
        const txt = JSON.stringify(d.data || {}, null, 2);
        await navigator.clipboard.writeText(txt);
        const box = document.getElementById('shared-rules-preview');
        if (box) box.textContent = 'Export copiado al portapapeles.';
        showToast('Export copiado', 'success');
    } catch (e) {
        showToast(`Error export: ${e.message}`, 'error');
    }
}
window.exportFiltersConfig = exportFiltersConfig;

async function importFiltersConfig() {
    const companyId = Number(window.CURRENT_COMPANY_ID || 0);
    if (!companyId) return;
    const raw = prompt('Pegá JSON de import de filtros');
    if (!raw) return;
    try {
        const data = JSON.parse(raw);
        const r = await fetch('/api/filters/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ company_id: companyId, data })
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'Import falló');
        showToast('Import aplicado', 'success');
        loadCompanyGameProfiles();
    } catch (e) {
        showToast(`Error import: ${e.message}`, 'error');
    }
}
window.importFiltersConfig = importFiltersConfig;

async function loadWebhookSubscriptions() {
    const box = document.getElementById('advanced-admin-preview');
    if (box) box.textContent = 'Cargando webhooks...';
    try {
        const r = await fetch('/api/webhooks/subscriptions');
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        const items = d.items || [];
        if (box) box.textContent = items.length ? items.map(x => `#${x.id} ${x.url} [${(x.events || []).join(', ')}] active=${x.is_active}`).join('\n') : 'Sin subscriptions';
    } catch (e) {
        if (box) box.textContent = `Error webhooks: ${e.message}`;
    }
}
window.loadWebhookSubscriptions = loadWebhookSubscriptions;

async function createApiKey() {
    const name = prompt('Nombre de API key', 'default');
    if (!name) return;
    try {
        const r = await fetch('/api/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, scopes: ['read:scans', 'read:oracle'] })
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo crear');
        await navigator.clipboard.writeText(d.api_key || '');
        showToast('API key creada y copiada', 'success');
        const box = document.getElementById('advanced-admin-preview');
        if (box) box.textContent = `Nueva key creada (copiada): ${d.api_key || ''}`;
    } catch (e) {
        showToast(`Error API key: ${e.message}`, 'error');
    }
}
window.createApiKey = createApiKey;

async function loadApiKeys() {
    const box = document.getElementById('advanced-admin-preview');
    if (box) box.textContent = 'Cargando API keys...';
    try {
        const r = await fetch('/api/keys');
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        const items = d.items || [];
        if (box) box.textContent = items.length ? items.map(x => `#${x.id} ${x.name} scopes=${(x.scopes || []).join(',')} revoked=${x.revoked_at || 'no'}`).join('\n') : 'Sin API keys';
    } catch (e) {
        if (box) box.textContent = `Error api keys: ${e.message}`;
    }
}
window.loadApiKeys = loadApiKeys;

async function loadNotifPrefs() {
    const box = document.getElementById('advanced-admin-preview');
    if (box) box.textContent = 'Cargando notification prefs...';
    try {
        const r = await fetch('/api/me/notifications/prefs');
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        const items = d.items || [];
        if (box) box.textContent = items.length ? items.map(x => `${x.channel}:${x.event_type}=${x.enabled}`).join('\n') : 'Sin preferencias';
    } catch (e) {
        if (box) box.textContent = `Error prefs: ${e.message}`;
    }
}
window.loadNotifPrefs = loadNotifPrefs;

function open2FASetup() {
    showToast('2FA setup pendiente en este corte (backend parcial)', 'info');
}
window.open2FASetup = open2FASetup;

function gdprExport() {
    showToast('GDPR export se implementa en siguiente corte', 'info');
}
window.gdprExport = gdprExport;

function gdprDeleteRequest() {
    showToast('GDPR delete request se implementa en siguiente corte', 'info');
}
window.gdprDeleteRequest = gdprDeleteRequest;

async function loadSchedules() {
    const box = document.getElementById('schedules-list');
    if (!box) return;
    box.textContent = 'Cargando schedules...';
    try {
        const r = await fetch('/api/schedules');
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No disponible');
        const items = Array.isArray(d.items) ? d.items : [];
        if (!items.length) {
            box.textContent = 'No hay schedules activos.';
            return;
        }
        box.innerHTML = items.map(s => {
            const id = s.id;
            const host = escapeHtml(s.host || '');
            const freq = Number(s.frequency_hours || 24);
            const enabled = !!s.enabled;
            const next = s.next_run ? formatDate(s.next_run) : '-';
            return `<div style="padding:8px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;display:flex;gap:10px;align-items:center;justify-content:space-between;">
                <div><strong>${host}</strong> · cada ${freq}h · next: ${next} · ${enabled ? 'activo' : 'pausado'}</div>
                <button class="btn btn-secondary" type="button" onclick="deleteSchedule(${id})">Eliminar</button>
            </div>`;
        }).join('');
    } catch (e) {
        box.textContent = `Error schedules: ${e.message}`;
    }
}
window.loadSchedules = loadSchedules;

async function createSchedule() {
    const host = (document.getElementById('sched-host')?.value || '').trim();
    const frequency_hours = Number(document.getElementById('sched-freq')?.value || 24);
    if (!host) { showToast('Host requerido', 'error'); return; }
    try {
        const r = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, frequency_hours, enabled: true }),
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo crear');
        showToast('Schedule creado', 'success');
        loadSchedules();
    } catch (e) {
        showToast(`Error creando schedule: ${e.message}`, 'error');
    }
}
window.createSchedule = createSchedule;

async function deleteSchedule(id) {
    try {
        const r = await fetch('/api/schedules', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id }),
        });
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo eliminar');
        loadSchedules();
    } catch (e) {
        showToast(`Error eliminando schedule: ${e.message}`, 'error');
    }
}
window.deleteSchedule = deleteSchedule;

// ============================================================
// DASHBOARD
// ============================================================

function _nameToHslColor(name) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    const hue = ((hash % 360) + 360) % 360;
    return `hsl(${hue},55%,38%)`;
}

function animateNumber(el, target, duration = 750) {
    if (!el) return;
    const start = parseInt(el.textContent) || 0;
    if (start === target) { el.textContent = target; return; }
    const t0 = performance.now();
    const easeOut = t => 1 - (1 - t) ** 3;
    function step(now) {
        const p = Math.min((now - t0) / duration, 1);
        el.textContent = Math.round(start + (target - start) * easeOut(p));
        if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function _scanVerdict(scan) {
    const s = scan.verdict || scan.severity_summary || '';
    if (s === 'hack' || s === 'CRITICO' || s === 'SOSPECHOSO') return 'detected';
    if (s === 'POCO_SOSPECHOSO') return 'suspicious';
    if (s === 'clean' || s === 'LIMPIO') return 'clean';
    return '';
}

async function loadDashboard() {
    // Greeting text
    const greetEl = document.getElementById('greeting-text');
    const dateEl  = document.getElementById('greeting-date');
    if (greetEl) {
        const h = new Date().getHours();
        const saludo = h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches';
        const name = greetEl.textContent.replace(/^.*,\s*/, '').replace('!','').trim();
        greetEl.textContent = `${saludo}, ${name}!`;
    }
    if (dateEl) {
        const now = new Date();
        dateEl.textContent = now.toLocaleDateString('es-ES', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
    }

    try {
        const response = await fetch('/api/statistics');
        const data = await response.json();

        animateNumber(document.getElementById('total-scans'),     data.total_scans     || 0);
        animateNumber(document.getElementById('total-issues'),    data.total_issues    || 0);
        animateNumber(document.getElementById('unique-machines'), data.unique_machines || 0);
        animateNumber(document.getElementById('active-tokens'),   data.active_tokens   || 0);

        loadRecentScans();
        loadMonthlyChart();
        loadExtendedDashboard();
    } catch (error) {
        console.error('Error cargando dashboard:', error);
    }
}

function _scanInitials(machineName) {
    if (!machineName || machineName === 'N/A') return '??';
    const parts = machineName.replace(/[_-]/g,' ').split(' ').filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return machineName.substring(0,2).toUpperCase();
}

/**
 * Visual #12: hash determinístico (string → hue 0-360) para generar
 * un color de avatar único pero estable por jugador.
 * Mismo nombre = mismo color siempre.
 */
function _hashHue(str) {
    if (!str) return 0;
    let h = 0;
    for (let i = 0; i < str.length; i++) {
        h = ((h << 5) - h) + str.charCodeAt(i);
        h |= 0;
    }
    return Math.abs(h) % 360;
}

/**
 * Visual #12: estilo inline para .scan-avatar-circle deterministico.
 * Si ya hay clase semántica (av-detected/suspicious/clean), devuelve ''
 * y deja que el CSS gane. Si no, genera un gradient único + color del texto.
 */
function _scanAvatarStyle(machineName, hasSemanticClass) {
    if (hasSemanticClass) return '';
    const hue  = _hashHue(machineName || '?');
    const hue2 = (hue + 30) % 360;
    return `background:linear-gradient(135deg, hsla(${hue},65%,55%,0.32), hsla(${hue2},70%,45%,0.45));`
         + `border:1px solid hsla(${hue},60%,55%,0.40);`
         + `color:hsl(${hue},85%,80%);`
         + `font-weight:700;letter-spacing:0.5px;`;
}

// V7: Path highlight — folder gray, filename white-bold
function _formatPath(path) {
    if (!path) return '';
    const sep = path.includes('\\') ? '\\' : '/';
    const lastSep = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'));
    if (lastSep < 0) return `<span class="path-file">${path}</span>`;
    const dir  = path.slice(0, lastSep + 1);
    const file = path.slice(lastSep + 1);
    return `<span class="path-dir">${dir}</span><span class="path-file">${file}</span>`;
}

// V3: Category icons
function _catIcon(cat) {
    const m = {
        'GHOST_CLIENT':'💀','HACKS':'⚔️','FORENSE':'🔬','RED':'🌐',
        'NETWORK_FORENSICS':'🌐','PROCESO':'⚙️','PROCESSES':'⚙️',
        'MACRO_DETECTION':'🖱️','EXECUTED_FILES':'📄','CMD_HISTORY':'💻',
        'JAVA_MEMORY':'☕','JAVA_AGENT':'🤖','REGISTRY':'🔑',
        'MOUSE_WEIGHT':'🖱️','MOUSE':'🖱️','AUTOCLICKER':'🖱️',
    };
    return m[cat] || '🔎';
}

// V9: Flame indicators by severity × confidence
function _flameIndicator(alertLevel, confidence) {
    const c = confidence || 0;
    if (alertLevel === 'PAGINA_SOSPECHOSA') return '🌐';
    const isCrit = alertLevel === 'CRITICAL';
    const isSusp = alertLevel === 'SOSPECHOSO' || alertLevel === 'MUY_SOSPECHOSO';
    let flames = 1;
    if (isCrit && c >= 80) flames = 4;
    else if (isCrit && c >= 60) flames = 3;
    else if (isCrit) flames = 2;
    else if (isSusp && c >= 70) flames = 2;
    return '🔥'.repeat(flames);
}

// V41: Ripple effect — attach to a click event
function _addRipple(e) {
    const btn = e.currentTarget;
    const circle = document.createElement('span');
    circle.className = 'ripple-circle';
    const r = Math.max(btn.clientWidth, btn.clientHeight);
    const rect = btn.getBoundingClientRect();
    circle.style.cssText = `width:${r}px;height:${r}px;left:${e.clientX - rect.left - r/2}px;top:${e.clientY - rect.top - r/2}px`;
    btn.appendChild(circle);
    circle.addEventListener('animationend', () => circle.remove());
}

// V8: Copy to clipboard with feedback
function _copyWithFeedback(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = '✓';
        btn.style.color = '#10b981';
        setTimeout(() => { btn.textContent = orig; btn.style.color = ''; }, 2000);
    });
}
window._copyWithFeedback = _copyWithFeedback;

// V45: Shake element on error
function _shakeEl(el) {
    el.classList.remove('shake');
    void el.offsetWidth; // reflow
    el.classList.add('shake');
    el.addEventListener('animationend', () => el.classList.remove('shake'), { once: true });
}

// V1: Render SVG risk gauge
function _renderRiskGauge(containerId, value) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const v = Math.min(Math.max(value || 0, 0), 100);
    const r = 34, cx = 44, cy = 44;
    const circ = 2 * Math.PI * r;
    const fill = circ * (1 - v / 100);
    const color = v >= 80 ? '#ef4444' : v >= 60 ? '#f97316' : v >= 30 ? '#f59e0b' : '#10b981';
    const pulse = v >= 80 ? 'animation:critical-glow-pulse 2s ease-in-out infinite;' : '';
    el.innerHTML = `
        <div class="risk-gauge-wrap">
            <svg width="88" height="88" viewBox="0 0 88 88" style="${pulse}">
                <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="7"/>
                <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="7"
                    stroke-linecap="round" stroke-dasharray="${circ}"
                    stroke-dashoffset="${circ}"
                    class="risk-gauge-arc" id="${containerId}-arc"
                    style="transform:rotate(-90deg);transform-origin:${cx}px ${cy}px;"/>
                <text x="${cx}" y="${cy+7}" text-anchor="middle" font-size="18" font-weight="800" fill="${color}">${v}</text>
                <text x="${cx}" y="${cy+21}" text-anchor="middle" font-size="8" fill="rgba(255,255,255,0.35)" letter-spacing="1">RISK</text>
            </svg>
        </div>`;
    requestAnimationFrame(() => {
        setTimeout(() => {
            const arc = document.getElementById(`${containerId}-arc`);
            if (arc) arc.style.strokeDashoffset = fill;
        }, 80);
    });
}
window._renderRiskGauge = _renderRiskGauge;

// Render 6-system ensemble verdict card
function _renderEnsembleVerdict(scan) {
    const el = document.getElementById('ensemble-verdict-container');
    if (!el) return;
    const ens = scan.ensemble_data;
    if (!ens) { el.style.display = 'none'; return; }

    const _V = {
        HACK_CONFIRMADO:  { label: 'HACK CONFIRMADO',  color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.35)'  },
        MUY_SOSPECHOSO:   { label: 'MUY SOSPECHOSO',   color: '#f97316', bg: 'rgba(249,115,22,0.12)', border: 'rgba(249,115,22,0.35)' },
        SOSPECHOSO:       { label: 'SOSPECHOSO',        color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.35)' },
        POCO_SOSPECHOSO:  { label: 'POCO SOSPECHOSO',  color: '#6366f1', bg: 'rgba(99,102,241,0.12)', border: 'rgba(99,102,241,0.35)' },
        LIMPIO:           { label: 'LIMPIO',            color: '#10b981', bg: 'rgba(16,185,129,0.12)', border: 'rgba(16,185,129,0.35)' },
    };
    const vk = ens.verdict || 'LIMPIO';
    const v  = _V[vk] || _V.LIMPIO;
    const sys = ens.systems || {};
    const score = ens.score || 0;

    const _bar = (val, max=4, color) => {
        const pct = Math.round(val / max * 100);
        return `<div style="flex:1;height:4px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden;">
            <div style="width:${pct}%;height:100%;background:${color};border-radius:2px;transition:width .4s;"></div>
        </div>`;
    };
    const _row = (label, score, max, color, detail='') => `
        <div style="display:flex;align-items:center;gap:6px;font-size:10px;">
            <span style="color:var(--text-d);width:80px;flex-shrink:0;">${label}</span>
            ${_bar(score, max, color)}
            <span style="color:${color};font-weight:700;width:16px;text-align:right;">${score}</span>
        </div>`;

    const instSys  = sys.instance_layer    || {};
    const convSys  = sys.signal_convergence || {};
    const hashSys  = sys.hash_reputation   || {};
    const tempSys  = sys.temporality       || {};
    const rsSys    = sys.risk_score        || {};
    const mlSys    = sys.ml                || {};

    const sanctionHtml = ens.sanctionable
        ? `<span style="font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);">SANCIONABLE</span>`
        : `<span style="font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(245,158,11,0.12);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);">NO SANCIONABLE</span>`;

    // Instance gate indicator
    const inInst = instSys.in_instance || 0;
    const gateColor = inInst > 0 ? '#10b981' : '#f59e0b';
    const gateIcon  = inInst > 0 ? '🔓' : '🔒';
    const gateLabel = inInst > 0 ? `${inInst} en instancia` : 'Sin evidencia en instancia';
    const gateCapped = ens.gate_capped;
    const gateHtml = `<div style="display:flex;align-items:center;gap:5px;font-size:9px;padding:3px 7px;border-radius:5px;background:${inInst>0?'rgba(16,185,129,0.08)':'rgba(245,158,11,0.08)'};border:1px solid ${inInst>0?'rgba(16,185,129,0.2)':'rgba(245,158,11,0.2)'};">
        <span>${gateIcon}</span>
        <span style="color:${gateColor};font-weight:600;">${gateLabel}</span>
        ${gateCapped ? '<span style="color:var(--text-d);">· verdict topado</span>' : ''}
    </div>`;

    // Top clients from signal convergence
    const clients = convSys.clients || {};
    const topClients = Object.entries(clients).sort((a,b) => b[1].length - a[1].length).slice(0,2)
        .map(([k,v]) => `<span style="color:var(--text-m);">${k}</span> <span style="color:var(--text-d);">(${v.join(',')})</span>`).join(' · ');

    el.style.display = 'block';
    el.innerHTML = `
        <div style="background:${v.bg};border:1px solid ${v.border};border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;gap:8px;">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                <span style="font-size:11px;font-weight:800;color:${v.color};letter-spacing:.5px;">${v.label}</span>
                ${sanctionHtml}
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
                <div style="flex:1;height:5px;background:rgba(255,255,255,0.07);border-radius:3px;overflow:hidden;">
                    <div style="width:${score}%;height:100%;background:${v.color};border-radius:3px;transition:width .5s;"></div>
                </div>
                <span style="font-size:10px;color:${v.color};font-weight:700;">${score}</span>
            </div>
            ${gateHtml}
            <div style="display:flex;flex-direction:column;gap:4px;">
                ${_row('Risk Score',   rsSys.score||0,   4, '#f59e0b')}
                ${_row('Convergencia', convSys.score||0, 4, '#818cf8')}
                ${_row('Hash Rep.',    hashSys.score||0, 4, '#ef4444')}
                ${_row('Temporalidad', tempSys.score||0, 4, '#38bdf8')}
                ${_row('ML',           mlSys.score||0,   4, '#D4915A')}
            </div>
            ${topClients ? `<div style="font-size:9px;color:var(--text-d);">Clientes: ${topClients}</div>` : ''}
        </div>`;
}
window._renderEnsembleVerdict = _renderEnsembleVerdict;

function _resultBadge(scan) {
    let badge = '';
    if (scan.status === 'running') {
        badge = '<span class="result-badge" style="background:rgba(99,102,241,0.12);color:#818cf8;border-color:rgba(99,102,241,0.3)">⏳ Escaneando</span>';
    } else {
        const s = scan.verdict || scan.severity_summary || '';
        if (s === 'hack' || s === 'CRITICO' || s === 'SOSPECHOSO')
            badge = '<span class="result-badge result-detected">Detectado</span>';
        else if (s === 'clean' || s === 'LIMPIO')
            badge = '<span class="result-badge result-clean">Limpio</span>';
        else if (s === 'POCO_SOSPECHOSO')
            badge = '<span class="result-badge result-suspicious">Sospechoso</span>';
        else if (scan.status === 'completed')
            badge = '<span class="result-badge result-pending">Pendiente</span>';
        else
            badge = '<span class="result-badge result-pending">Pendiente</span>';
    }
    // Risk score mini-badge
    const rs = scan.risk_score;
    if (rs !== undefined && rs !== null && scan.status !== 'running') {
        const rsCls = rs >= 70 ? 'risk-hack' : rs >= 30 ? 'risk-suspicious' : 'risk-clean';
        badge += ` <span class="risk-score-badge ${rsCls}" style="font-size:10px;padding:2px 7px;margin-left:4px;">${rs}pts</span>`;
    }
    return badge;
}

function _indicatorDots(scan) {
    const issues = scan.issues_found || 0;
    const sev    = scan.severity_summary || '';
    if (issues === 0) return '<span class="indicator-dot dot-green"></span>';
    const dots = [];
    if (sev === 'CRITICO')           dots.push('<span class="indicator-dot dot-red"></span>');
    if (sev === 'SOSPECHOSO')        dots.push('<span class="indicator-dot dot-amber"></span>');
    if (sev === 'POCO_SOSPECHOSO')   dots.push('<span class="indicator-dot dot-amber"></span>');
    for (let i = dots.length; i < Math.min(issues, 5); i++)
        dots.push(`<span class="indicator-dot dot-${i < 2 ? 'red' : 'amber'}"></span>`);
    return dots.slice(0,5).join('');
}

async function loadRecentScans() {
    const container = document.getElementById('recent-scans');
    if (container) {
        container.innerHTML = Array(4).fill(0).map(() => `
            <div class="skel-row">
                <div class="skel skel-circle" style="width:34px;height:34px;flex-shrink:0;"></div>
                <div style="flex:1;">
                    <div class="skel" style="height:12px;width:58%;margin-bottom:6px;"></div>
                    <div class="skel" style="height:9px;width:38%;"></div>
                </div>
                <div class="skel" style="width:68px;height:22px;border-radius:20px;flex-shrink:0;"></div>
            </div>`).join('');
    }
    try {
        const response = await fetch('/api/scans?limit=6');
        const data = await response.json();
        if (data.scans && data.scans.length > 0) {
            container.innerHTML = data.scans.map((scan, i) => {
                const v = _scanVerdict(scan);
                const rowCls = v ? `row-${v}` : '';
                const avCls  = v ? `av-${v}` : '';
                const _avStyle = _scanAvatarStyle(scan.machine_name, !!v);
                return `<div class="echo-scan-row stagger-item ${rowCls}" style="animation-delay:${i*55}ms" onclick="viewScanDetails(${scan.id})">
                    <div class="scan-avatar-circle ${avCls}" style="${_avStyle}">${_scanInitials(scan.machine_name)}</div>
                    <div class="scan-row-info">
                        <div class="scan-row-machine">${scan.machine_name || 'N/A'}</div>
                        <div class="scan-row-date">${formatDate(scan.started_at)}</div>
                    </div>
                    <div class="indicator-dots">${_indicatorDots(scan)}</div>
                    ${_resultBadge(scan)}
                </div>`;
            }).join('');
        } else {
            container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-text">No hay escaneos recientes</div></div>';
        }
    } catch (error) {
        console.error('Error cargando escaneos recientes:', error);
    }
}

let monthlyChart = null;
async function loadMonthlyChart() {
    const canvas = document.getElementById('monthly-chart');
    if (!canvas || !window.Chart) return;
    try {
        const response = await fetch('/api/scans?limit=50');
        const data = await response.json();
        // Agrupar por día (últimos 30 días)
        const counts = {};
        const now = new Date();
        for (let i = 29; i >= 0; i--) {
            const d = new Date(now); d.setDate(d.getDate() - i);
            counts[d.toISOString().slice(0,10)] = 0;
        }
        if (data.scans) {
            data.scans.forEach(s => {
                if (!s.started_at) return;
                const day = new Date(s.started_at).toISOString().slice(0,10);
                if (day in counts) counts[day]++;
            });
        }
        const labels = Object.keys(counts).map(d => d.slice(5));
        const values = Object.values(counts);
        if (monthlyChart) monthlyChart.destroy();
        monthlyChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    data: values,
                    borderColor: '#B87333',
                    backgroundColor: 'rgba(184,115,51,0.10)',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.4,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false }, tooltip: { callbacks: { title: i => i[0].label } } },
                scales: {
                    x: { display: false },
                    y: { display: false, min: 0 }
                }
            }
        });
    } catch(e) { /* no chart data */ }
}

let verdictChart = null;
async function loadExtendedDashboard() {
    try {
        const res  = await fetch('/api/dashboard/extended');
        const data = await res.json();
        if (data.error) return;

        // --- Veredictos doughnut ---
        const canvas = document.getElementById('verdict-chart');
        const legend = document.getElementById('verdict-legend');
        if (canvas && window.Chart) {
            const { clean = 0, hack = 0, pending = 0 } = data.verdicts || {};
            const total = clean + hack + pending || 1;
            if (verdictChart) verdictChart.destroy();
            verdictChart = new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: ['Limpio', 'Con Hacks', 'Pendiente'],
                    datasets: [{
                        data: [clean, hack, pending],
                        backgroundColor: ['#22c55e', '#ef4444', '#6b7280'],
                        borderWidth: 0,
                        hoverOffset: 4,
                    }]
                },
                options: {
                    cutout: '70%',
                    responsive: false,
                    plugins: { legend: { display: false }, tooltip: { callbacks: {
                        label: ctx => ` ${ctx.label}: ${ctx.raw} (${Math.round(ctx.raw/total*100)}%)`
                    }}}
                }
            });
            if (legend) legend.innerHTML = [
                `<span style="color:#22c55e">&#9679;</span> Limpios: <strong>${clean}</strong> (${Math.round(clean/total*100)}%)`,
                `<span style="color:#ef4444">&#9679;</span> Con Hacks: <strong>${hack}</strong> (${Math.round(hack/total*100)}%)`,
                `<span style="color:#6b7280">&#9679;</span> Pendientes: <strong>${pending}</strong>`,
            ].join('<br>');
        }

        // --- Top hacks ---
        const listEl = document.getElementById('top-hacks-list');
        if (listEl) {
            const issues = data.top_issues || [];
            if (issues.length === 0) {
                listEl.innerHTML = '<div style="color:var(--text-d);font-size:13px;padding:8px 0;">Sin datos este mes</div>';
            } else {
                const max = issues[0].count || 1;
                listEl.innerHTML = issues.map((item, i) => `
                    <div style="margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
                            <span style="color:var(--text-s);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:75%;">${i+1}. ${item.name}</span>
                            <span style="color:var(--accent);font-weight:600;">${item.count}</span>
                        </div>
                        <div style="height:3px;background:var(--border);border-radius:2px;">
                            <div style="height:3px;width:${Math.round(item.count/max*100)}%;background:var(--accent);border-radius:2px;"></div>
                        </div>
                    </div>`).join('');
            }
        }

        // --- Tiempo promedio ---
        const avgEl = document.getElementById('avg-scan-time');
        if (avgEl && data.avg_duration != null) {
            const s = data.avg_duration;
            avgEl.textContent = s >= 60 ? `${Math.round(s/60)} min` : `${Math.round(s)} seg`;
        }
    } catch(e) { /* silent */ }

    // Load recidivism, issue type stats, and heatmap in parallel
    _loadRecidivism();
    _loadIssueTypeStats();
    _loadScanHeatmap();
}

async function _loadRecidivism() {
    const el = document.getElementById('recidivism-list');
    if (!el) return;
    try {
        const res  = await fetch('/api/statistics/recidivism?days=90&min_hacks=2&limit=10');
        const data = await res.json();
        const list = data.recidivists || [];
        if (list.length === 0) {
            el.innerHTML = '<div style="color:var(--text-d);font-size:13px;padding:8px 0;">Sin reincidentes en los últimos 90 días.</div>';
            return;
        }
        el.innerHTML = list.map(r => `
            <div onclick="loadScansForMachine('${r.machine_name}')"
                 style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid var(--border);cursor:pointer;">
                <div style="flex:1;min-width:0;">
                    <div style="font-size:12px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.machine_name}</div>
                    <div style="font-size:11px;color:var(--text-d);">${r.minecraft_username} — último: ${r.last_scan.slice(0,10)}</div>
                </div>
                <div style="text-align:right;flex-shrink:0;">
                    <div style="font-size:13px;font-weight:800;color:#ef4444;">${r.hack_count}x</div>
                    <div style="font-size:10px;color:var(--text-d);">risk avg ${r.avg_risk}</div>
                </div>
            </div>`).join('');
    } catch(e) {
        if (el) el.innerHTML = '<div style="color:var(--text-d);font-size:12px;padding:8px 0;">No disponible</div>';
    }
}

async function _loadIssueTypeStats() {
    const el = document.getElementById('issue-types-list');
    if (!el) return;
    try {
        const res  = await fetch('/api/statistics/issue_types?days=30&limit=12');
        const data = await res.json();
        const list = data.issue_types || [];
        if (list.length === 0) {
            el.innerHTML = '<div style="color:var(--text-d);font-size:13px;padding:8px 0;">Sin datos este mes.</div>';
            return;
        }
        const maxTotal = list[0].total || 1;
        const ALERT_C  = { CRITICAL:'#ef4444', SOSPECHOSO:'#f59e0b', MUY_SOSPECHOSO:'#ea580c' };
        el.innerHTML = list.map(item => {
            const hackPct = Math.round((item.hack_rate || 0) * 100);
            const barColor = hackPct >= 70 ? '#ef4444' : hackPct >= 30 ? '#f59e0b' : '#6b7280';
            return `
            <div style="padding:4px 0;border-bottom:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:2px;">
                    <span style="color:var(--text-s);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%;">${item.issue_type}</span>
                    <span style="color:${ALERT_C[item.max_alert]||'var(--text-d)'};font-weight:700;flex-shrink:0;margin-left:6px;">${item.total} <span style="color:${barColor};font-size:10px;">${hackPct}% hack</span></span>
                </div>
                <div style="height:2px;background:var(--border);border-radius:1px;">
                    <div style="height:2px;width:${Math.round(item.total/maxTotal*100)}%;background:${barColor};border-radius:1px;"></div>
                </div>
            </div>`;
        }).join('');
    } catch(e) {
        if (el) el.innerHTML = '<div style="color:var(--text-d);font-size:12px;padding:8px 0;">No disponible</div>';
    }
}

function loadScansForMachine(machineName) {
    showSection('escaneos');
    const searchInput = document.getElementById('filter-search');
    if (searchInput) {
        searchInput.value = machineName;
        loadScans();
    }
}

// P5 #18 — Heatmap de actividad de scans
async function _loadScanHeatmap() {
    const wrap = document.getElementById('scan-heatmap-wrap');
    if (!wrap) return;
    try {
        const res  = await fetch('/api/admin/scan-heatmap?days=30');
        if (!res.ok) { wrap.innerHTML = ''; return; }
        const data = await res.json();
        const matrix = data.matrix || [];
        const detMx  = data.detections_matrix || [];
        const days   = data.day_names || ['L','M','X','J','V','S','D'];
        const hours  = Array.from({length: 24}, (_, i) => `${i}h`);
        const maxVal = Math.max(1, ...matrix.flat());

        let html = '<table style="border-collapse:collapse;font-size:9px;width:100%;">';
        // Header row
        html += '<tr><td style="width:22px;"></td>' +
                hours.map((h, i) => `<td style="text-align:center;color:var(--text-d);padding:1px;width:${100/26}%;">${i%4===0?h:''}</td>`).join('') +
                '</tr>';
        days.forEach((day, d) => {
            html += `<tr><td style="color:var(--text-d);padding-right:4px;white-space:nowrap;">${day}</td>`;
            for (let h = 0; h < 24; h++) {
                const v   = matrix[d]?.[h] || 0;
                const dv  = detMx[d]?.[h] || 0;
                const pct = Math.round((v / maxVal) * 100);
                const bg  = dv > 0
                    ? `rgba(239,68,68,${0.15 + (pct/100)*0.65})`
                    : v > 0
                        ? `rgba(184,115,51,${0.12 + (pct/100)*0.55})`
                        : 'rgba(255,255,255,0.03)';
                const title = v > 0 ? `${day} ${h}h: ${v} scan(s)${dv>0?', '+dv+' con hacks':''}` : '';
                html += `<td title="${title}" style="padding:1px;">
                    <div style="background:${bg};border-radius:2px;height:14px;width:100%;"></div>
                </td>`;
            }
            html += '</tr>';
        });
        html += '</table>';
        html += `<div style="display:flex;gap:12px;margin-top:8px;font-size:10px;color:var(--text-d);">
            <span><span style="display:inline-block;width:10px;height:10px;background:rgba(184,115,51,0.5);border-radius:2px;margin-right:3px;vertical-align:middle;"></span>Scan</span>
            <span><span style="display:inline-block;width:10px;height:10px;background:rgba(239,68,68,0.5);border-radius:2px;margin-right:3px;vertical-align:middle;"></span>Con hack</span>
            <span style="margin-left:auto;">Total: ${data.total_scans} scans en 30d</span>
        </div>`;
        wrap.innerHTML = html;
    } catch(e) {
        if (wrap) wrap.innerHTML = '<div style="color:var(--text-d);font-size:12px;">No disponible</div>';
    }
}

// P5 #20 — Búsqueda de jugador por UUID o username en Mojang
async function searchMojangProfile() {
    const input = document.getElementById('mojang-search-input');
    const result = document.getElementById('mojang-search-result');
    if (!input || !result) return;
    const q = input.value.trim();
    if (!q) return;
    result.innerHTML = '<span style="color:var(--text-d);">Buscando...</span>';
    try {
        const res = await fetch(`/api/player/mojang-profile?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        if (data.error) {
            result.innerHTML = `<span style="color:#ef4444">${data.error}</span>`;
            return;
        }
        const uuid = data.uuid || '—';
        const fmtUuid = uuid.length === 32
            ? `${uuid.slice(0,8)}-${uuid.slice(8,12)}-${uuid.slice(12,16)}-${uuid.slice(16,20)}-${uuid.slice(20)}`
            : uuid;
        result.innerHTML = `
            <div style="padding:10px;background:var(--bg-t);border-radius:8px;border:1px solid var(--border);">
                <div style="display:flex;align-items:center;gap:10px;">
                    <img src="https://crafatar.com/avatars/${uuid}?size=32&overlay" width="32" height="32"
                         style="border-radius:4px;image-rendering:pixelated;" onerror="this.style.display='none'">
                    <div>
                        <div style="font-size:14px;font-weight:700;color:var(--text-h);">${data.username || '—'}</div>
                        <div style="font-size:10px;font-family:monospace;color:var(--text-d);word-break:break-all;">${fmtUuid}</div>
                    </div>
                </div>
                <button onclick="searchScansForMojang('${data.username}')"
                    style="margin-top:8px;width:100%;padding:5px;border-radius:6px;border:1px solid rgba(184,115,51,.4);background:rgba(184,115,51,.1);color:var(--accent);font-size:11px;cursor:pointer;">
                    Ver scans de ${data.username}
                </button>
            </div>`;
    } catch(e) {
        result.innerHTML = '<span style="color:#ef4444">Error de red</span>';
    }
}

function searchScansForMojang(username) {
    if (!username) return;
    loadScansForMachine(username);
}

// ============================================================
// TOKENS
// ============================================================

async function loadTokens() {
    try {
        // Cambiar a include_used=true para mostrar todos los tokens (activos, usados y expirados)
        const response = await fetch('/api/tokens?include_used=true');
        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }
        const data = await response.json();
        
        const tbody = document.getElementById('tokens-table-body');
        // El endpoint devuelve {success: true, tokens: [...]}
        const tokens = data.success ? data.tokens : (data.tokens || []);
        if (tokens && tokens.length > 0) {
            tbody.innerHTML = tokens.map(token => {
                const tokenStr = token.token || '';
                const usedCount = token.used_count || 0;
                const maxUses = token.max_uses || -1;
                const isUsed = maxUses > 0 && usedCount >= maxUses;
                const expiresAt = token.expires_at ? new Date(token.expires_at) : null;
                const isExpired = expiresAt && expiresAt < new Date();
                const isActive = token.is_active !== false && !isUsed && !isExpired;
                
                // Determinar estado y badge
                let statusText = 'Activo';
                let statusBadge = 'badge-success';
                if (isUsed) {
                    statusText = 'Usado';
                    statusBadge = 'badge-warning';
                } else if (isExpired) {
                    statusText = 'Expirado';
                    statusBadge = 'badge-danger';
                } else if (!isActive) {
                    statusText = 'Inactivo';
                    statusBadge = 'badge-secondary';
                }
                
                const codeDisplay = token.short_code
                    ? `<span style="font-family:'Consolas',monospace;font-size:18px;font-weight:900;letter-spacing:4px;color:#D4915A;">${token.short_code}</span>`
                    : `<code style="font-size:11px;opacity:0.5;">${tokenStr.substring(0, 12)}…</code>`;
                return `
                <tr>
                    <td>${codeDisplay}</td>
                    <td>${token.created_at ? formatDate(token.created_at) : 'N/A'}</td>
                    <td>${token.created_by || 'N/A'}</td>
                    <td>${usedCount}${maxUses > 0 ? ` / ${maxUses}` : ' / ∞'}</td>
                    <td><span class="badge ${statusBadge}">${statusText}</span></td>
                    <td>
                        ${window.CAN_TOKENS ? `<button class="btn btn-sm btn-danger" onclick="deleteToken(${token.id || token.token_id})" title="Eliminar este código">🗑️ Eliminar</button>` : ''}
                    </td>
                </tr>
            `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No hay tokens</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando tokens:', error);
    }
}

function setupEventListeners() {
    // Modal de token
    document.getElementById('create-token-btn')?.addEventListener('click', () => {
        document.getElementById('token-modal').classList.add('active');
    });
    document.getElementById('close-token-modal')?.addEventListener('click', () => {
        document.getElementById('token-modal').classList.remove('active');
    });
    document.getElementById('cancel-token-btn')?.addEventListener('click', () => {
        document.getElementById('token-modal').classList.remove('active');
    });

    let isCreatingToken = false;
    document.getElementById('confirm-create-token-btn')?.addEventListener('click', async () => {
        if (isCreatingToken) return;
        isCreatingToken = true;
        try {
            await createToken();
        } finally {
            setTimeout(() => { isCreatingToken = false; }, 1000);
        }
    });

    // Modal de resultado de token
    document.getElementById('close-token-result-modal')?.addEventListener('click', () => {
        document.getElementById('token-result-modal').classList.remove('active');
    });

    // Copiar código de acceso
    document.getElementById('copy-token-btn')?.addEventListener('click', async (e) => {
        e.preventDefault();
        const code = document.getElementById('generated-token')?.textContent?.trim();
        if (!code || code === '------') return;
        await _copyToClipboard(code, document.getElementById('copy-token-btn'), 'Copiar Código', '✓ Copiado!');
    });

    // Copiar URL de descarga fija
    document.getElementById('copy-download-url-btn')?.addEventListener('click', async () => {
        const url = document.getElementById('token-result-download-url')?.textContent?.trim();
        if (!url) return;
        await _copyToClipboard(url, document.getElementById('copy-download-url-btn'), 'Copiar', '✓ Copiado!');
    });

    // Modal de detalles de escaneo
    document.getElementById('close-scan-details-modal')?.addEventListener('click', () => {
        document.getElementById('scan-details-modal').classList.remove('active');
    });

    // Descargar aplicación
    document.getElementById('download-app-btn')?.addEventListener('click', async () => {
        await downloadApp();
    });
}

async function _copyToClipboard(text, btn, defaultLabel, copiedLabel) {
    try {
        await navigator.clipboard.writeText(text);
    } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (_2) { /* ignore */ }
        document.body.removeChild(ta);
    }
    if (btn) {
        const orig = btn.textContent;
        btn.textContent = copiedLabel; btn.style.background = '#22c55e';
        setTimeout(() => { btn.textContent = orig; btn.style.background = ''; }, 2000);
    }
}

async function createToken() {
    const btn = document.getElementById('confirm-create-token-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Generando...'; }

    try {
        const response = await fetch('/api/tokens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({})
        });

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            if (text.includes('<!DOCTYPE') || text.includes('<html')) {
                throw new Error('Sesión expirada. Recarga la página e inicia sesión nuevamente.');
            }
            throw new Error(`Error ${response.status}`);
        }

        const data = await response.json();

        if (data.success && data.short_code) {
            document.getElementById('generated-token').textContent = data.short_code;
            const dlUrlEl = document.getElementById('token-result-download-url');
            if (dlUrlEl) dlUrlEl.textContent = data.download_url || (window.location.origin + '/descargar');
            document.getElementById('token-modal').classList.remove('active');
            document.getElementById('token-result-modal').classList.add('active');
            setTimeout(() => loadTokens(), 500);
        } else {
            alert('Error al crear código: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error creando código:', error);
        alert('Error al crear código: ' + error.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Generar Código'; }
    }
}

async function deleteToken(tokenId) {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Eliminar token permanentemente?',
            body: 'Esta acción no se puede deshacer.\n\nSi algún cliente está usando este token, dejará de funcionar inmediatamente.',
            ok: 'Eliminar token',
            danger: true,
          })
        : Promise.resolve(confirm('¿Eliminar permanentemente este token?\n\n⚠️ Esta acción no se puede deshacer.\n\nSi algún cliente está usando este token, dejará de funcionar inmediatamente.')));
    if (!ok) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tokens/${tokenId}`, { method: 'DELETE' });
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Token eliminado permanentemente.\n\nLos clientes que usen este token no podrán autenticarse.');
            // Recargar tokens según la sección actual
            if (typeof loadTokens === 'function') {
                loadTokens();
            }
            if (typeof loadCompanyTokens === 'function') {
                loadCompanyTokens();
            }
        } else {
            alert('Error al eliminar token: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        alert('Error al eliminar token: ' + error.message);
    }
}

// Hacer la función disponible globalmente
window.deleteToken = deleteToken;

// ============================================================
// ESCANEOS Y RESULTADOS
// ============================================================

/** Pack 14 — chip y modal de metadata de archivo (JAR/ELF/PE).
 *  Recibe el `result.extra` (objeto) y devuelve un mini-chip clickeable que
 *  abre el modal con la metadata cruda. Vacío si no hay metadata.
 */
function _metadataVerdictChip(result) {
    const ex = (result && result.extra) || {};
    const blob = ex.jar_metadata || (ex.file_metadata && ex.file_metadata.meta) || ex.file_metadata || null;
    if (!blob || typeof blob !== 'object') return '';
    const verdict = String(blob.verdict || '').toLowerCase();
    let label = '', bg = '', fg = '', bd = '';
    if (verdict === 'legit_mod') {
        label = 'JAR LEGIT'; bg = 'rgba(16,185,129,0.14)'; fg = '#6ee7b7'; bd = 'rgba(16,185,129,0.36)';
    } else if (verdict === 'suspicious') {
        label = 'BYTECODE HIT'; bg = 'rgba(239,68,68,0.18)'; fg = '#fca5a5'; bd = 'rgba(239,68,68,0.45)';
    } else if (blob.mod_loader || blob.signed || blob.kind === 'jar') {
        label = 'JAR · ' + (blob.mod_loader || (blob.signed ? 'SIGNED' : 'UNKNOWN')).toUpperCase();
        bg = 'rgba(245,158,11,0.12)'; fg = '#fbbf24'; bd = 'rgba(245,158,11,0.32)';
    } else if (blob.kind === 'elf') {
        label = 'ELF · ' + (blob.arch || 'unknown').toUpperCase();
        bg = 'rgba(59,130,246,0.10)'; fg = '#93c5fd'; bd = 'rgba(59,130,246,0.30)';
    } else if (blob.kind === 'pe') {
        label = 'PE · ' + (blob.machine || 'unknown').toUpperCase();
        bg = 'rgba(148,163,184,0.10)'; fg = '#cbd5e1'; bd = 'rgba(148,163,184,0.28)';
    } else {
        return '';
    }
    const safeBlob = JSON.stringify(blob).replace(/'/g, '&#39;').replace(/</g, '&lt;');
    return `<button onclick="event.stopPropagation();_openMetadataModal('${safeBlob}')"
            title="Ver metadata del archivo"
            style="font-size:10px;font-weight:700;letter-spacing:0.4px;padding:1px 7px;border-radius:4px;
                   background:${bg};color:${fg};border:1px solid ${bd};cursor:pointer;flex-shrink:0;
                   white-space:nowrap;font-family:inherit;">${label}</button>`;
}

function _openMetadataModal(blobJsonEscaped) {
    let blob = {};
    try {
        const decoded = blobJsonEscaped.replace(/&#39;/g, "'").replace(/&lt;/g, '<');
        blob = JSON.parse(decoded);
    } catch (_e) { return; }
    const lines = [];
    const push = (k, v, kind) => {
        if (v === undefined || v === null || v === '') return;
        const valHtml = typeof v === 'object'
            ? `<code style="white-space:pre-wrap;display:block;font-size:11px;background:var(--bg-3);padding:6px 8px;border-radius:4px;color:var(--text-h);max-height:160px;overflow:auto;">${escapeHtml(JSON.stringify(v, null, 2))}</code>`
            : `<span style="color:${kind==='good'?'#6ee7b7':kind==='bad'?'#fca5a5':'var(--text-h)'};font-weight:600;">${escapeHtml(String(v))}</span>`;
        lines.push(`<div style="display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--border-m);">
            <div style="min-width:140px;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:0.4px;font-weight:600;">${k}</div>
            <div style="flex:1;font-size:12.5px;">${valHtml}</div>
        </div>`);
    };
    const verdict = String(blob.verdict || 'unknown');
    const verdictKind = verdict === 'legit_mod' ? 'good' : verdict === 'suspicious' ? 'bad' : 'neutral';
    push('Verdict', verdict, verdictKind);
    push('Tipo de archivo', blob.kind);
    if (blob.mod_loader) push('Mod loader', blob.mod_loader, 'good');
    if (blob.manifest_vendor) push('Vendor (manifest)', blob.manifest_vendor);
    if (blob.manifest_title)  push('Title (manifest)',  blob.manifest_title);
    if (blob.signed !== undefined)     push('Firmado',       blob.signed ? 'sí' : 'no', blob.signed ? 'good' : 'neutral');
    if (blob.cdn_signed !== undefined) push('Firma de CDN',  blob.cdn_signed ? 'sí (CurseForge/Modrinth/...)' : 'no', blob.cdn_signed ? 'good' : 'neutral');
    if (blob.bytecode_hits && blob.bytecode_hits.length) push('Bytecode hits', blob.bytecode_hits, 'bad');
    if (blob.class_count !== undefined) push('Clases (.class)', blob.class_count);
    if (blob.size_b !== undefined) {
        const kb = (blob.size_b / 1024);
        push('Tamaño', kb >= 1024 ? (kb/1024).toFixed(2) + ' MB' : kb.toFixed(1) + ' KB');
    }
    if (blob.arch)     push('Arquitectura', blob.arch);
    if (blob.elf_type) push('ELF type', blob.elf_type);
    if (blob.interp)   push('Interpreter', blob.interp);
    if (blob.machine)  push('PE machine', blob.machine);
    if (blob.error)    push('Error de parseo', blob.error, 'bad');

    const modal = document.createElement('div');
    modal.id = 'metadata-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.78);display:flex;align-items:center;justify-content:center;padding:24px;';
    modal.innerHTML = `
        <div style="background:var(--bg-2);border:1px solid var(--border-m);border-radius:12px;max-width:680px;width:100%;max-height:80vh;overflow:auto;box-shadow:0 20px 40px rgba(0,0,0,0.55);">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border-m);">
                <div style="font-size:14px;font-weight:700;color:var(--text-h);">🔬 Metadata del archivo</div>
                <button id="md-modal-close" style="background:none;border:none;color:var(--text-d);font-size:18px;cursor:pointer;line-height:1;">×</button>
            </div>
            <div style="padding:14px 18px;">${lines.join('') || '<div style="color:var(--text-d);font-size:12px;">Sin metadata estructurada disponible.</div>'}</div>
            <div style="padding:10px 18px;border-top:1px solid var(--border-m);font-size:11px;color:var(--text-d);">
                Inspector de metadatos · <a href="https://asperss.onrender.com/descargar?plat=lin" target="_blank" rel="noopener" style="color:var(--accent);">Argus Linux v1.6.45-linux3</a>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('#md-modal-close').onclick = () => modal.remove();
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}
window._openMetadataModal = _openMetadataModal;

/** SO / scanner: Linux vs Windows (columna scans.os + scanner_platform en detalle). */
function _scanPlatformLabel(scan) {
    const raw = String(scan?.os_name || scan?.os || '').trim();
    const plat = String(scan?.scanner_platform || '').toLowerCase();
    const low = raw.toLowerCase();
    if (plat === 'linux' || low.startsWith('linux'))
        return { key: 'linux', label: 'Linux', bg: 'rgba(34,197,94,0.14)', fg: '#86efac', bd: 'rgba(34,197,94,0.38)' };
    if (plat === 'windows' || /\bwindows\b|win\s*10|win\s*11|microsoft\s+windows/i.test(raw))
        return { key: 'windows', label: 'Windows', bg: 'rgba(59,130,246,0.14)', fg: '#93c5fd', bd: 'rgba(59,130,246,0.38)' };
    if (raw)
        return { key: 'other', label: 'Otro', bg: 'rgba(148,163,184,0.12)', fg: '#cbd5e1', bd: 'rgba(148,163,184,0.30)' };
    return { key: 'legacy', label: 'Windows', bg: 'rgba(59,130,246,0.10)', fg: '#93c5fd', bd: 'rgba(59,130,246,0.28)' };
}

function _scanPlatformChipHtml(scan) {
    const p = _scanPlatformLabel(scan);
    return `<span class="scan-platform-chip" data-platform="${p.key}" title="Cliente scanner: ${p.label}" style="display:inline-flex;align-items:center;margin-left:6px;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:800;letter-spacing:0.35px;text-transform:uppercase;background:${p.bg};color:${p.fg};border:1px solid ${p.bd};vertical-align:middle;">${p.label}</span>`;
}

/** Visual #50 — chip con la versión EXACTA del scanner que generó este scan.
 *  Vacío si el dato no está (deploys viejos / scanner pre-1.6.49). */
function _scannerVersionChipHtml(scan) {
    const v = String(scan?.scanner_version || '').trim();
    if (!v) return '';
    const safe = escapeHtml(v);
    return `<span class="scanner-version-chip" title="Versión del scanner cliente que generó este scan" style="display:inline-flex;align-items:center;margin-left:6px;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:0.3px;background:rgba(217,119,6,0.12);color:#fbbf24;border:1px solid rgba(217,119,6,0.32);vertical-align:middle;font-family:'JetBrains Mono','Fira Code',monospace;">v${safe}</span>`;
}

async function loadScans() {
    const tbody = document.getElementById('results-table-body');
    // V18: Skeleton loading
    if (tbody && !tbody._loaded) {
        tbody.innerHTML = Array(6).fill(0).map(() => `
            <tr>
                <td><div style="display:flex;gap:8px;align-items:center;">
                    <div class="skel" style="width:32px;height:32px;border-radius:50%;flex-shrink:0;"></div>
                    <div style="flex:1"><div class="skel" style="height:11px;width:70%;border-radius:4px;margin-bottom:5px;"></div><div class="skel" style="height:9px;width:40%;border-radius:4px;"></div></div>
                </div></td>
                <td><div class="skel" style="height:20px;width:70px;border-radius:10px;"></div></td>
                <td><div class="skel" style="height:20px;width:80px;border-radius:10px;"></div></td>
                <td><div class="skel" style="height:10px;width:60px;border-radius:4px;"></div></td>
                <td><div class="skel" style="height:28px;width:90px;border-radius:6px;"></div></td>
            </tr>`).join('');
    }
    try {
        const params = new URLSearchParams({ limit: 50 });
        const search    = (document.getElementById('filter-search')?.value || '').trim();
        const verdict   = document.getElementById('filter-verdict')?.value || '';
        const dateFrom  = document.getElementById('filter-date-from')?.value || '';
        const dateTo    = document.getElementById('filter-date-to')?.value || '';
        const country   = (document.getElementById('filter-country')?.value || '').trim();
        const risk      = document.getElementById('filter-risk')?.value || '';
        const os        = document.getElementById('filter-os')?.value || '';
        const staff     = (document.getElementById('filter-staff')?.value || '').trim();
        if (search)   params.set('search', search);
        if (verdict)  params.set('verdict', verdict);
        if (dateFrom) params.set('date_from', dateFrom);
        if (dateTo)   params.set('date_to', dateTo);
        if (country)  params.set('country', country);
        if (risk)     params.set('risk', risk);
        if (os)       params.set('os', os);
        if (staff)    params.set('staff', staff);

        const response = await fetch('/api/scans?' + params.toString());
        // Sesion expirada: avisar en la tabla en lugar de quedar en blanco
        if (response.status === 401 || response.status === 403) {
            if (tbody) {
                tbody._loaded = true;
                tbody.innerHTML = `
                    <tr><td colspan="5" style="text-align:center;padding:50px 20px;color:var(--text-m);">
                        <div style="font-size:38px;margin-bottom:12px">🔒</div>
                        <div style="font-size:14px;font-weight:700;color:var(--text-h);margin-bottom:6px;">Tu sesión expiró</div>
                        <div style="font-size:12px;margin-bottom:16px;">Inicia sesión otra vez para ver los escaneos.</div>
                        <a href="/login" class="btn btn-primary btn-sm" style="text-decoration:none;">Iniciar sesión</a>
                    </td></tr>`;
            }
            return;
        }
        const data = await response.json();

        if (data.scans && data.scans.length > 0) {
            if (tbody) tbody._loaded = true;
            // Actualizar baseline del polling con el scan más reciente visible
            if (data.scans[0].id > (_lastKnownScanId || 0)) {
                _lastKnownScanId = data.scans[0].id;
            }
            // V67: highlight search term in cells
            const searchTerm = (document.getElementById('filter-search')?.value || '').trim().toLowerCase();
            const _hl = (text) => {
                if (!searchTerm || !text) return text || '';
                const re = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`, 'gi');
                return String(text).replace(re, '<mark style="background:#fbbf2455;color:inherit;border-radius:2px;padding:0 1px;">$1</mark>');
            };

            const now = Date.now();
            // Visual #43 — registrar/desregistrar scans running para que
            // argusUI lance un toast si tardan demasiado (>4 min).
            if (window.argusUI && window.argusUI.markScanRunning) {
                data.scans.forEach(s => {
                    if (s.status === 'running') {
                        const startedTs = s.started_at ? new Date(s.started_at).getTime() : Date.now();
                        window.argusUI.markScanRunning(s.id, startedTs);
                    } else {
                        window.argusUI.markScanFinished(s.id);
                    }
                });
            }
            tbody.innerHTML = data.scans.map((scan, idx) => {
                const rs = scan.risk_score;
                const riskClass = rs >= 70 ? 'tr-risk-critical' : rs >= 30 ? 'tr-risk-suspicious' : (rs !== undefined && rs !== null ? 'tr-risk-clean' : '');

                // V12: Crafatar avatar or initials
                const uuid = scan.minecraft_uuid || null;
                const _avStyle = _scanAvatarStyle(scan.machine_name, false);
                const avatar = uuid
                    ? `<img src="https://crafatar.com/avatars/${uuid}?size=32&overlay" alt="" style="width:32px;height:32px;border-radius:6px;object-fit:cover;flex-shrink:0;" onerror="this.outerHTML='<div class=\\"scan-avatar-circle\\" style=\\"${_avStyle.replace(/"/g,'&quot;')}\\">${_scanInitials(scan.machine_name)}</div>'">`
                    : `<div class="scan-avatar-circle" style="${_avStyle}">${_scanInitials(scan.machine_name)}</div>`;

                // V13: NUEVO badge if scan < 30min old
                const scanAge = scan.started_at ? (now - new Date(scan.started_at).getTime()) : Infinity;
                const nuevoBadge = scanAge < 30 * 60 * 1000 ? `<span class="badge-nuevo">NUEVO</span>` : '';

                // V14: Trend arrow (up/down based on risk vs previous if available)
                const trend = scan.risk_trend;
                const trendArrow = trend === 'up' ? `<span style="color:#ef4444;font-size:11px;" title="Tendencia empeorando">↑</span>`
                    : trend === 'down' ? `<span style="color:#10b981;font-size:11px;" title="Tendencia mejorando">↓</span>` : '';

                // V17: OS icon + chip Linux/Windows (columna scans.os desde API)
                const osStr = (scan.os_name || scan.os || '').toLowerCase();
                const osIcon = osStr.includes('linux') ? '🐧' : osStr.includes('mac') ? '🍎' : (osStr.includes('win') || !osStr) ? '🪟' : '';
                const platChip = _scanPlatformChipHtml(scan) + _scannerVersionChipHtml(scan);

                const machineName = _hl(scan.machine_name || 'N/A');

                return `
                <tr class="${riskClass}" style="cursor:pointer" onclick="viewScanDetails(${scan.id})" data-scan-id="${scan.id}">
                    <td>
                        <div class="scan-details-cell">
                            ${avatar}
                            <div style="min-width:0;">
                                <div class="scan-machine-name" style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;"
                                    onclick="event.stopPropagation();viewPlayerProfile(${JSON.stringify(scan.machine_name || '')})"
                                    title="Ver perfil del jugador"
                                >${machineName}${nuevoBadge}${trendArrow}</div>
                                <div class="scan-date-small">${_timeAgo(scan.started_at)}</div>
                                ${scan.scanned_by ? `<div style="font-size:10px;color:var(--text-d);margin-top:1px;">por <strong style="color:var(--text-s);">${scan.scanned_by}</strong></div>` : ''}
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="game-badge" style="flex-wrap:wrap;">
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.2"/><path d="M4 6H8M6 4V8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                            Minecraft${osIcon ? ` <span>${osIcon}</span>` : ''}${platChip}
                        </span>
                    </td>
                    <td>${_resultBadge(scan)}</td>
                    <td><div class="indicator-dots">${_indicatorDots(scan)}</div></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();viewScanDetails(${scan.id})">
                            Ver detalles
                        </button>
                    </td>
                </tr>`;
            }).join('');
            // Visual #4 — staggered fade-in en filas de la tabla de scans.
            // Solo aplica al primer load (tbody._loaded marca la transición
            // de skeleton a contenido real). Re-render por filtros también
            // se anima — confirma visualmente que la lista se actualizó.
            try {
                if (tbody && window.argusUI && typeof window.argusUI.staggerIn === 'function') {
                    window.argusUI.staggerIn(tbody, { selector: ':scope > tr', step: 28, max: 18 });
                }
                if (tbody) tbody._loaded = true;
            } catch (_e) { /* never block render */ }
        } else {
            if (tbody) tbody._loaded = false;
            // Empty state ilustrado (Visual #25)
            const hasFilters = !!(search || verdict || dateFrom || dateTo || country || risk || os || staff);
            const title = hasFilters ? 'No hay escaneos para esos filtros' : 'Aún no hay escaneos registrados';
            const desc  = hasFilters
                ? 'Probá ajustar los filtros o limpiarlos para ver todos los escaneos.'
                : 'Cuando un cliente corra el scanner con un token de tu empresa, vas a verlo acá automáticamente.';
            const actionLabel = hasFilters ? 'Limpiar filtros' : null;
            tbody.innerHTML = `
                <tr><td colspan="5" style="padding:0;">
                    <div class="argus-empty">
                        <div class="argus-empty__art">
                            <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%">
                                <path d="M8 22h48l-4-12H12L8 22z"/>
                                <path d="M8 22v28a4 4 0 0 0 4 4h40a4 4 0 0 0 4-4V22"/>
                                <path d="M22 32h20"/>
                            </svg>
                        </div>
                        <div class="argus-empty__title">${title}</div>
                        <div class="argus-empty__desc">${desc}</div>
                        ${actionLabel ? `<button class="argus-empty__action" onclick="clearFilters()">${actionLabel}</button>` : ''}
                    </div>
                </td></tr>`;
        }
    } catch (error) {
        console.error('Error cargando escaneos:', error);
    }
}

// ── Feature 323: Virtual list para contenedores con >100 ítems ────────────
// Renderiza solo los ítems visibles + buffer de 5 arriba/abajo.
// Uso: _VirtualList(container, items, renderFn, { rowHeight })
function _VirtualList(container, items, renderFn, opts) {
    opts = opts || {};
    const ROW_H  = opts.rowHeight || 68;
    const BUFFER = 5;
    container.style.cssText += 'overflow-y:auto;position:relative;';
    const inner = document.createElement('div');
    inner.style.position = 'relative';
    inner.style.height   = (items.length * ROW_H) + 'px';
    container.innerHTML  = '';
    container.appendChild(inner);

    let _rendered = { start: -1, end: -1 };

    function _render() {
        const scrollTop = container.scrollTop;
        const viewH     = container.clientHeight || 400;
        const start = Math.max(0, Math.floor(scrollTop / ROW_H) - BUFFER);
        const end   = Math.min(items.length, Math.ceil((scrollTop + viewH) / ROW_H) + BUFFER);
        if (start === _rendered.start && end === _rendered.end) return;
        _rendered = { start, end };

        const frag = document.createDocumentFragment();
        const pad  = document.createElement('div');
        pad.style.height = (start * ROW_H) + 'px';
        frag.appendChild(pad);

        for (let i = start; i < end; i++) {
            const el = document.createElement('div');
            el.style.height = ROW_H + 'px';
            el.innerHTML    = renderFn(items[i], i);
            frag.appendChild(el);
        }

        const padBot = document.createElement('div');
        padBot.style.height = ((items.length - end) * ROW_H) + 'px';
        frag.appendChild(padBot);

        inner.innerHTML = '';
        inner.appendChild(frag);
    }

    container.addEventListener('scroll', _render, { passive: true });
    _render();
    return { refresh: _render };
}

// V20: time-ago helper
function _timeAgo(dateStr) {
    if (!dateStr) return '—';
    const diff = Date.now() - new Date(dateStr).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60)  return 'hace ' + s + 's';
    if (s < 3600) return 'hace ' + Math.floor(s/60) + 'min';
    if (s < 86400) return 'hace ' + Math.floor(s/3600) + 'h';
    return formatDate(dateStr);
}

function applyFilters() { loadScans(); }

function clearFilters() {
    const ids = ['filter-search','filter-verdict','filter-date-from','filter-date-to','filter-country','filter-risk','filter-os','filter-staff'];
    ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
    // Reset quick-chip active state
    document.querySelectorAll('.quick-chip').forEach(b => b.classList.remove('active'));
    const clearChip = document.getElementById('quick-clear-chip');
    if (clearChip) clearChip.style.display = 'none';
    loadScans();
}

function quickFilter(type) {
    // Reset all filters first
    const ids = ['filter-search','filter-verdict','filter-date-from','filter-date-to','filter-risk','filter-os','filter-country','filter-staff'];
    ids.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });

    const today   = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date(Date.now() - 7*24*60*60*1000).toISOString().slice(0, 10);

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    switch (type) {
        case 'pending':  set('filter-verdict', 'pending');  break;
        case 'hacks':    set('filter-verdict', 'hacks');    break;  // 'hacks' matches server verdict
        case 'today':    set('filter-date-from', today);    set('filter-date-to', today); break;
        case 'week':     set('filter-date-from', weekAgo);  set('filter-date-to', today); break;
        case 'critical': set('filter-risk', 'hack');        break;  // risk >= 70 on server
        case 'running':  set('filter-search', '');          break;  // no status filter; show all
    }

    // Show clear chip
    const clearChip = document.getElementById('quick-clear-chip');
    if (clearChip) clearChip.style.display = '';
    // Mark active chip
    document.querySelectorAll('.quick-chip:not(.chip-clear)').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(`'${type}'`));
    });

    loadScans();
}

// ── Visual #16 — Filtros guardados como presets nombrados ─────────────────
// Persistencia en localStorage('scan_filter_presets'). Cubre TODOS los campos
// del filter-bar (no solo search/verdict/date). Incluye delete + last-used.

const _PRESET_FIELDS = [
    'filter-search', 'filter-verdict', 'filter-date-from', 'filter-date-to',
    'filter-country', 'filter-os', 'filter-staff', 'filter-risk',
];

function _readCurrentFilters() {
    const out = {};
    _PRESET_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) out[id] = (el.value || '').trim();
    });
    return out;
}

function _hasAnyFilter(o) {
    return Object.values(o || {}).some(v => v && String(v).trim() !== '');
}

function saveFilterPreset() {
    const filters = _readCurrentFilters();
    if (!_hasAnyFilter(filters)) {
        if (window.showToast) window.showToast('No hay filtros activos para guardar.', 'warning');
        return;
    }
    const name = prompt('Nombre del preset (ej: "Pendientes hoy", "Mis FPs"):');
    if (!name || !name.trim()) return;
    const trimmed = name.trim().slice(0, 50);
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    presets[trimmed] = { fields: filters, savedAt: Date.now() };
    localStorage.setItem('scan_filter_presets', JSON.stringify(presets));
    _renderPresetOptions(trimmed);
    if (window.showToast) window.showToast(`✅ Preset "${trimmed}" guardado.`, 'success');
}

function loadFilterPreset(name) {
    if (!name) return;
    if (name === '__delete__') return _deleteFilterPresetPrompt();
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    const p = presets[name];
    if (!p) return;
    // Backward compat: presets viejos guardaban directo {search,verdict,...}
    const fields = p.fields || p;
    _PRESET_FIELDS.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        // Map legacy keys if existen
        let v = fields[id];
        if (typeof v === 'undefined') {
            const legacyMap = {
                'filter-search': 'search', 'filter-verdict': 'verdict',
                'filter-date-from': 'dateFrom', 'filter-date-to': 'dateTo',
                'filter-country': 'country', 'filter-os': 'os',
                'filter-staff': 'staff', 'filter-risk': 'risk',
            };
            v = fields[legacyMap[id]];
        }
        el.value = v || '';
    });
    try { localStorage.setItem('scan_filter_presets_last', name); } catch (_e) {}
    if (window.showToast) window.showToast(`Preset "${name}" cargado.`, 'info', { duration: 2500 });
    if (typeof loadScans === 'function') loadScans();
}

function _deleteFilterPresetPrompt() {
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    const names = Object.keys(presets);
    if (!names.length) {
        if (window.showToast) window.showToast('No hay presets guardados.', 'info');
        _renderPresetOptions();
        return;
    }
    const name = prompt('¿Qué preset borrar? Opciones:\n  ' + names.join('\n  '));
    if (!name || !presets[name]) {
        _renderPresetOptions();
        return;
    }
    delete presets[name];
    localStorage.setItem('scan_filter_presets', JSON.stringify(presets));
    _renderPresetOptions();
    if (window.showToast) window.showToast(`Preset "${name}" eliminado.`, 'success');
}

function _renderPresetOptions(highlight) {
    const sel = document.getElementById('filter-presets');
    if (!sel) return;
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    const names = Object.keys(presets).sort((a, b) => a.localeCompare(b));
    let html = '<option value="">Presets…</option>';
    if (names.length) {
        html += '<optgroup label="Tus presets">';
        names.forEach(n => {
            html += `<option value="${n}" ${highlight === n ? 'selected' : ''}>${n}</option>`;
        });
        html += '</optgroup>';
        html += '<option value="__delete__" style="color:#ef4444;">🗑 Borrar un preset…</option>';
    }
    sel.innerHTML = html;
}

window.saveFilterPreset = saveFilterPreset;
window.loadFilterPreset = loadFilterPreset;

// ── Staff management ───────────────────────────────────────────────────────

const STAFF_ROLES = ['helper', 'moderador', 'admin', 'owner'];
const STAFF_ROLE_LABELS = { helper: 'Helper', moderador: 'Moderador', admin: 'Admin', owner: 'Owner' };

async function loadStaffUsers() {
    const tbody = document.getElementById('staff-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Cargando...</td></tr>';
    try {
        const res = await fetch('/api/staff/users');
        if (!res.ok) { tbody.innerHTML = `<tr><td colspan="6" class="loading-cell">Sin acceso</td></tr>`; return; }
        const data = await res.json();
        if (!data.users || !data.users.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Sin usuarios visibles para tu rol</td></tr>';
            return;
        }
        const _roleOrder = { owner: 0, admin: 1, moderador: 2, helper: 3 };
        data.users.sort((a, b) => (_roleOrder[a.staff_role] ?? 99) - (_roleOrder[b.staff_role] ?? 99) || a.username.localeCompare(b.username));
        tbody.innerHTML = data.users.map(u => {
            const roleOptions = STAFF_ROLES.map(r =>
                `<option value="${r}" ${u.staff_role === r ? 'selected' : ''}>${STAFF_ROLE_LABELS[r]}</option>`
            ).join('');
            const avatarHtml = u.avatar_url
                ? `<img src="${u.avatar_url}" alt="${u.username}" style="width:32px;height:32px;border-radius:50%;object-fit:cover;border:2px solid var(--border-m);"
                       onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
                   <div style="display:none;width:32px;height:32px;border-radius:50%;background:var(--accent-bg);border:2px solid var(--border-m);align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--accent);">${u.username[0].toUpperCase()}</div>`
                : `<div style="width:32px;height:32px;border-radius:50%;background:var(--accent-bg);border:2px solid var(--border-m);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--accent);">${u.username[0].toUpperCase()}</div>`;
            return `<tr>
                <td style="width:44px;padding:6px 8px;">${avatarHtml}</td>
                <td><strong>${u.username}</strong>${u.email ? `<div style="font-size:11px;color:var(--text-d);">${u.email}</div>` : ''}</td>
                <td><span class="badge badge-${_staffBadge(u.staff_role)}">${STAFF_ROLE_LABELS[u.staff_role] || u.staff_role}</span></td>
                <td>${u.is_active ? '✅' : '❌'}</td>
                <td style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                    <select id="role-sel-${u.id}" class="filter-select" style="min-width:110px;font-size:12px;padding:5px 8px;">${roleOptions}</select>
                    <button class="btn btn-sm btn-primary" onclick="updateStaffRole(${u.id})">Guardar</button>
                    <button class="btn btn-sm btn-secondary" onclick="setUserAvatar(${u.id})" data-av="${(u.avatar_url||'').replace(/"/g,'&quot;')}" title="Cambiar avatar">🖼️</button>
                </td>
            </tr>`;
        }).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="6" class="loading-cell">Error: ${e.message}</td></tr>`;
    }
}

function _staffBadge(role) {
    return { owner: 'danger', admin: 'warning', moderador: 'info', helper: 'secondary' }[role] || 'secondary';
}

async function updateStaffRole(userId) {
    const sel = document.getElementById(`role-sel-${userId}`);
    if (!sel) return;
    const role = sel.value;
    const res = await fetch(`/api/staff/users/${userId}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role })
    });
    const data = await res.json();
    if (data.success) {
        if (window.showToast) {
            const msg = data.company_attached
                ? `✅ Rol actualizado y vinculado a tu empresa`
                : `✅ Rol actualizado`;
            window.showToast(msg, 'success', { duration: 2500 });
        }
        loadStaffUsers();
    } else {
        alert('Error: ' + (data.error || 'No se pudo actualizar'));
    }
}

// (P42) Las funciones attachUserToMyCompany / attachAllOrphanStaff fueron
// retiradas. La adopción de staff huérfanos (legacy con company_id NULL)
// ahora SOLO se hace desde el panel SuperAdmin (/aspers-sa) para mantener
// el aislamiento entre empresas.

// ── Screenshot display ─────────────────────────────────────────────────────

function renderScreenshot(data) {
    const container = document.getElementById('screenshot-container');
    if (!container) return;
    const b64 = data && data.screenshot;
    if (!b64) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-d);font-size:13px;">Sin captura de pantalla — el scanner tomará una automáticamente a partir de la próxima versión.</div>';
        return;
    }
    const ts = data.started_at ? formatDate(data.started_at) : '';
    const dataUrl = `data:image/jpeg;base64,${b64}`;
    container.innerHTML = `
        <div style="font-size:12px;color:var(--text-d);margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;">
            <span>Capturado al inicio del escaneo · ${ts}</span>
            <button class="argus-screenshot-fullscreen-btn"
                    style="font-size:11px;padding:4px 10px;border-radius:6px;border:1px solid var(--border-m);background:var(--bg-t);color:var(--text-m);cursor:pointer;">
                ⛶ Pantalla completa
            </button>
        </div>
        <img id="argus-screenshot-thumb"
             src="${dataUrl}"
             alt="Captura de pantalla"
             style="max-width:100%;border-radius:10px;border:1px solid var(--border);
                    box-shadow:0 4px 20px rgba(0,0,0,0.3);cursor:zoom-in;
                    transition:filter 200ms ease;"
             title="Click para abrir en pantalla completa con zoom y pan">`;
    const thumb = document.getElementById('argus-screenshot-thumb');
    const btn   = container.querySelector('.argus-screenshot-fullscreen-btn');
    if (thumb) thumb.addEventListener('click', () => _openScreenshotLightbox(dataUrl));
    if (btn)   btn.addEventListener('click',   () => _openScreenshotLightbox(dataUrl));
}

// Visual #45 — Lightbox para screenshot con zoom (rueda) y pan (drag).
// Esc o click fuera de la imagen cierra. Doble click resetea.
function _openScreenshotLightbox(src) {
    let modal = document.getElementById('argus-screenshot-lightbox');
    if (modal) modal.remove();
    modal = document.createElement('div');
    modal.id = 'argus-screenshot-lightbox';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.style.cssText = `
        position:fixed;inset:0;z-index:99800;
        background:rgba(5,3,1,0.92);backdrop-filter:blur(10px);
        display:flex;align-items:center;justify-content:center;
        cursor:zoom-out;animation:argusFadeIn 180ms ease both;`;
    modal.innerHTML = `
        <button id="argus-lb-close" aria-label="Cerrar"
            style="position:absolute;top:18px;right:22px;z-index:2;
                   width:38px;height:38px;border-radius:50%;
                   background:rgba(20,14,8,0.85);border:1px solid rgba(184,115,51,0.45);
                   color:#f1e6d3;cursor:pointer;font-size:18px;line-height:1;
                   display:flex;align-items:center;justify-content:center;">×</button>
        <div id="argus-lb-hint"
            style="position:absolute;bottom:18px;left:50%;transform:translateX(-50%);
                   background:rgba(20,14,8,0.75);border:1px solid rgba(184,115,51,0.30);
                   color:rgba(241,230,211,0.85);font-size:12px;padding:6px 14px;
                   border-radius:20px;pointer-events:none;letter-spacing:0.2px;">
            Rueda: zoom · Arrastrar: pan · Doble click: reset · Esc: cerrar
        </div>
        <img id="argus-lb-img" src="${src}" alt=""
             draggable="false"
             style="max-width:92vw;max-height:88vh;user-select:none;
                    transform-origin:center center;
                    transition:transform 100ms cubic-bezier(0.22,1,0.36,1);
                    box-shadow:0 30px 80px -10px rgba(0,0,0,0.7),
                               0 0 0 1px rgba(212,145,90,0.18) inset;
                    border-radius:6px;cursor:grab;">
    `;
    document.body.appendChild(modal);
    if (!document.getElementById('argus-lb-anim-style')) {
        const st = document.createElement('style');
        st.id = 'argus-lb-anim-style';
        st.textContent = '@keyframes argusFadeIn{from{opacity:0}to{opacity:1}}';
        document.head.appendChild(st);
    }
    const img = document.getElementById('argus-lb-img');
    const closeBtn = document.getElementById('argus-lb-close');
    let scale = 1, tx = 0, ty = 0;
    let dragging = false, startX = 0, startY = 0;
    function apply() {
        img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    }
    function reset() { scale = 1; tx = 0; ty = 0; apply(); }
    function close() {
        modal.style.opacity = '0';
        modal.style.transition = 'opacity 160ms ease';
        setTimeout(() => modal.remove(), 180);
        document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
        const k = (e.key || '').toLowerCase();
        if (k === 'escape') { e.preventDefault(); close(); }
        else if (k === '0')   { e.preventDefault(); reset(); }
        else if (k === '+' || k === '=') { e.preventDefault(); scale = Math.min(8, scale * 1.2); apply(); }
        else if (k === '-')   { e.preventDefault(); scale = Math.max(0.2, scale / 1.2); apply(); }
    }
    document.addEventListener('keydown', onKey);
    closeBtn.addEventListener('click', (e) => { e.stopPropagation(); close(); });
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
    img.addEventListener('click', (e) => e.stopPropagation());
    img.addEventListener('dblclick', (e) => { e.stopPropagation(); reset(); });
    img.addEventListener('wheel', (e) => {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
        const newScale = Math.max(0.25, Math.min(8, scale * factor));
        // Zoom hacia el cursor
        const rect = img.getBoundingClientRect();
        const offX = e.clientX - rect.left - rect.width  / 2;
        const offY = e.clientY - rect.top  - rect.height / 2;
        tx -= offX * (newScale / scale - 1);
        ty -= offY * (newScale / scale - 1);
        scale = newScale;
        apply();
    }, { passive: false });
    img.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = true;
        startX = e.clientX - tx;
        startY = e.clientY - ty;
        img.style.cursor = 'grabbing';
        img.style.transition = 'none';
    });
    window.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        tx = e.clientX - startX;
        ty = e.clientY - startY;
        apply();
    });
    window.addEventListener('mouseup', () => {
        if (!dragging) return;
        dragging = false;
        img.style.cursor = 'grab';
        img.style.transition = 'transform 100ms cubic-bezier(0.22,1,0.36,1)';
    });
}

// Apply permission guards on page load
function applyPermissionGuards() {
    if (typeof window.CAN_VERDICT !== 'undefined' && !window.CAN_VERDICT) {
        // Hide verdict action buttons for helpers
        const verdictBtns = document.querySelectorAll('#bulk-mark-hack-btn,#bulk-mark-legitimate-btn,[onclick*="openVerdictModal"],[onclick*="confirmVerdict"]');
        verdictBtns.forEach(b => b.style.display = 'none');
    }
}

let severityChart = null;

function _getCategoryLabel(cat) {
    const map = {
        'HACKS':             '⚔️ Hacks',
        'HACK_FILES':        '📦 Archivos',
        'GHOST_CLIENT':      '👻 Ghost Client',
        'MACRO_DETECTION':   '🖱️ Macros',
        'JAVA_MEMORY':       '☕ Java Mem',
        'JAVA_AGENT':        '🔌 Agentes',
        'NETWORK_FORENSICS': '🌐 Red',
        'RED':               '🌐 Red',
        'SYSTEM_TAMPERING':  '⚙️ Sistema',
        'RECENT_FILES':      '📅 Recientes',
        'REGISTRY':          '📋 Registro',
        'PROCESS':           '⚙️ Proceso',
        'PROCESO':           '⚙️ Proceso',
        'PROCESSES':         '⚙️ Procesos',
        'VPN':               '🔒 VPN',
        'EVASION':           '🛡️ Evasión',
        'EXECUTED_FILES':    '▶️ Ejecutados',
        'FORENSE':           '🔬 Forense',
        'TEXTURE_PACKS':     '🎨 Texturas',
        'OBFUSCATION':       '🔀 Ofuscación',
        'JAR_FILES':         '📦 JARs',
        'MINECRAFT':         '⛏️ Minecraft',
        'DELETED_FILES':     '🗑️ Borrados',
        'DNS_CACHE':         '🌐 DNS',
        'CMD_HISTORY':       '💻 Historial CMD',
        'HARDWARE':          '🖥️ Hardware',
        'USB':               '🔌 USB',
        'CLIPBOARD':         '📋 Portapapeles',
    };
    return map[cat] || cat || 'Otro';
}

// ── Buscador in-scan ────────────────────────────────────────────────────────

function _onIssuesSearch(scanId) {
    const q   = _normalize(document.getElementById('issues-search-input')?.value || '').trim();
    const sev = (document.getElementById('issues-severity-select')?.value || '').trim();
    _issuesSearchText = q;
    _issuesSeverity   = sev;
    currentIssuesPage = 0;
    const container   = document.getElementById('issues-list-container');
    if (container) renderIssuePage(container, scanId);
}

// Detecta si un path está dentro de una instancia activa de Minecraft
function _isInMinecraftInstance(path) {
    if (!path) return false;
    const p = path.toLowerCase().replace(/\\/g, '/');
    const instanceFrags = [
        '.minecraft/mods', '.minecraft/versions', '.minecraft/resourcepacks',
        '.minecraft/shaderpacks', '.minecraft/saves', '.minecraft/config',
        'multimc/instances', 'prismlauncher/instances',
        'curseforge/minecraft/instances', 'gdlauncher/instances',
        'atlauncher/instances',
    ];
    return instanceFrags.some(f => p.includes(f));
}

// Detecta si un path está en una ubicación de descarga (no cargado en el juego)
function _isNonInstanceLocation(path) {
    if (!path) return false;
    const p = path.toLowerCase().replace(/\\/g, '/');
    return p.includes('/downloads/') || p.includes('/desktop/') ||
           p.includes('/documents/') || p.includes('/temp/') ||
           p.includes('/appdata/local/temp');
}

function _renderWebHistory(items, scanId) {
    const el = document.getElementById('web-history-container');
    if (!el) return;
    if (!items || items.length === 0) { el.style.display = 'none'; return; }
    el.style.display = 'block';
    const rows = items.map(r => {
        const name = r.issue_name || r.issue_path || 'Página desconocida';
        const path = r.issue_path || '';
        const shortPath = path.length > 60 ? '…' + path.slice(-58) : path;
        return `<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid rgba(99,102,241,0.1);">
            <span style="font-size:13px;flex-shrink:0;">🌐</span>
            <div style="flex:1;min-width:0;">
                <div style="font-size:11px;font-weight:600;color:var(--text-h);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name}</div>
                ${shortPath && shortPath !== name ? `<div style="font-size:10px;color:var(--text-d);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${shortPath}</div>` : ''}
            </div>
            <span style="font-size:9px;font-weight:700;padding:1px 5px;border-radius:4px;background:rgba(99,102,241,0.12);color:#818cf8;border:1px solid rgba(99,102,241,0.25);flex-shrink:0;">Sospechoso</span>
        </div>`;
    }).join('');
    el.innerHTML = `
        <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2);border-radius:10px;overflow:hidden;margin-bottom:4px;">
            <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid rgba(99,102,241,0.15);">
                <span style="font-size:11px;font-weight:700;color:#818cf8;letter-spacing:.4px;">🌐 HISTORIAL WEB SOSPECHOSO</span>
                <span style="font-size:10px;color:var(--text-d);">${items.length} visita(s)</span>
            </div>
            <div style="max-height:140px;overflow-y:auto;">${rows}</div>
        </div>`;
}
window._renderWebHistory = _renderWebHistory;

function renderIssuePage(container, scanId) {
    const all = currentIssuesList;
    if (!all || all.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-d);font-size:13px;">Sin hallazgos críticos o sospechosos en este escaneo.</div>';
        return;
    }

    // Categorías disponibles
    const cats = ['all', ...new Set(all.map(r => r.issue_category || 'Otro').filter(Boolean))];

    // Filtro: categoría + búsqueda + severidad + solo-instancia
    let filtered = _issuesFilter === 'all' ? all : all.filter(r => (r.issue_category || 'Otro') === _issuesFilter);
    if (_issuesSeverity) filtered = filtered.filter(r => r.alert_level === _issuesSeverity);
    if (window._issuesOnlyInstance) filtered = filtered.filter(r => _isInMinecraftInstance(r.issue_path));
    if (_issuesSearchText) {
        const q = _issuesSearchText;
        filtered = filtered.filter(r =>
            _normalize(r.issue_name).includes(q) ||
            _normalize(r.issue_path).includes(q)
        );
    }

    // Actualizar contador
    const countLabel = document.getElementById('issues-count-label');
    if (countLabel) {
        countLabel.textContent = filtered.length === all.length
            ? `${all.length} hallazgo(s)`
            : `${filtered.length} de ${all.length}`;
    }
    const showCount = (currentIssuesPage + 1) * ISSUES_PER_PAGE;
    const slice = filtered.slice(0, showCount);
    const hasMore = filtered.length > showCount;

    // Agrupación por cliente hack
    const _KNOWN_CLIENTS_GRP = ['vape','entropy','whiteout','liquidbounce','wurst','sigma','flux','future','astolfo','ghost','rise','moon','drip','meteor','aristois','tenacity','vertex','inertia','salhack','slinky','reflex','rage','biscuit','thunder','autoclick','autoclicker'];
    const _cGroups = {};
    for (const r of slice) {
        const t = ((r.issue_name||'') + ' ' + (r.issue_type||'')).toLowerCase();
        const k = _KNOWN_CLIENTS_GRP.find(c => t.includes(c));
        if (k) { if (!_cGroups[k]) _cGroups[k] = []; _cGroups[k].push(r); }
    }
    Object.keys(_cGroups).forEach(k => { if (_cGroups[k].length < 2) delete _cGroups[k]; });

    // Chips de categoría
    const onlyInst = !!window._issuesOnlyInstance;
    const instCount = all.filter(r => _isInMinecraftInstance(r.issue_path)).length;

    const _catColors = {
        'GHOST_CLIENT':'#ef4444','HACKS':'#ef4444','FORENSE':'#8b5cf6',
        'RED':'#3b82f6','NETWORK_FORENSICS':'#3b82f6','PROCESO':'#f59e0b','PROCESSES':'#f59e0b',
        'MACRO_DETECTION':'#f59e0b','EXECUTED_FILES':'#10b981','CMD_HISTORY':'#10b981',
        'JAVA_MEMORY':'#06b6d4','JAVA_AGENT':'#06b6d4','REGISTRY':'#D4915A',
    };
    const chips = cats.map(c => {
        const count = c === 'all' ? all.length : all.filter(r => (r.issue_category || 'Otro') === c).length;
        const active = _issuesFilter === c;
        const accent = _catColors[c] || '#B87333';
        return `<button class="argus-chip-tab" role="tab" aria-selected="${active}" tabindex="${active ? '0' : '-1'}" onclick="_setIssueFilter('${c}',${scanId})" style="
            font-size:11px;padding:4px 10px;border-radius:20px;cursor:pointer;font-weight:600;
            border:1px solid ${active ? accent : 'var(--border-m)'};
            background:${active ? accent + '22' : 'var(--bg-t)'};
            color:${active ? accent : 'var(--text-m)'};white-space:nowrap;">
            ${c === 'all' ? '🔍 Todos' : _getCategoryLabel(c)} <span style="opacity:.7">${count}</span>
        </button>`;
    }).join('') + `<button onclick="_toggleOnlyInstance(${scanId})" style="
        font-size:11px;padding:4px 10px;border-radius:20px;cursor:pointer;font-weight:600;
        border:1px solid ${onlyInst ? '#10b981' : 'var(--border-m)'};
        background:${onlyInst ? 'rgba(16,185,129,0.15)' : 'var(--bg-t)'};
        color:${onlyInst ? '#10b981' : 'var(--text-m)'};white-space:nowrap;"
        title="Mostrar solo archivos cargados en una instancia activa de Minecraft">
        En instancia <span style="opacity:.7">${instCount}</span>
    </button>`;

    const rows = slice.map((result, rowIdx) => {
        // Group detection — skip non-lead items
        const _gText = ((result.issue_name||'') + ' ' + (result.issue_type||'')).toLowerCase();
        const _gKey  = _KNOWN_CLIENTS_GRP.find(c => _gText.includes(c) && _cGroups[c]);
        if (_gKey && _cGroups[_gKey][0] !== result) return '';
        const _grp = _gKey ? _cGroups[_gKey] : null;

        const isCrit  = result.alert_level === 'CRITICAL';
        const isMid   = result.alert_level === 'SOSPECHOSO' || result.alert_level === 'MUY_SOSPECHOSO';
        const isWeb   = result.alert_level === 'PAGINA_SOSPECHOSA';
        const accent  = isCrit ? '#ef4444' : isMid ? '#f59e0b' : isWeb ? '#818cf8' : '#6b7280';
        const bg      = isCrit ? 'rgba(239,68,68,0.05)' : isMid ? 'rgba(245,158,11,0.04)' : isWeb ? 'rgba(129,140,248,0.04)' : 'rgba(107,114,128,0.03)';
        const dot     = isCrit ? '🔴' : isMid ? '🟠' : isWeb ? '🌐' : '🔵';
        const cat     = result.issue_category || '';
        const name    = (result.issue_name || 'Hallazgo').slice(0, 100);
        const path    = result.issue_path || '';
        const truncPath = path.length > 90 ? '…' + path.slice(-87) : path;
        const inInst  = _isInMinecraftInstance(path);
        // PAGINA_SOSPECHOSA es una visita web — no tiene sentido el badge de instancia
        const instBadge = isWeb ? '' : (inInst
            ? `<span style="font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);flex-shrink:0;white-space:nowrap;">En instancia</span>`
            : `<span style="font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(245,158,11,0.1);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);flex-shrink:0;white-space:nowrap;">Fuera de instancia</span>`);
        const variantBadge = _grp ? `<button onclick="event.stopPropagation();var el=document.getElementById('vg_${_gKey}');el.style.display=el.style.display==='flex'?'none':'flex';" style="font-size:10px;padding:1px 7px;border-radius:4px;background:rgba(129,140,248,0.15);color:#818cf8;border:1px solid rgba(129,140,248,0.3);cursor:pointer;flex-shrink:0;">${_grp.length} variantes ▾</button>` : '';
        const metaChip = _metadataVerdictChip(result);
        // Filter #42 — Badge "primera vez visto" / "visto Nx".
        // Decorado por el backend con first_seen + seen_count en /api/scans/<id>.
        // Solo mostramos en CRITICAL/SOSPECHOSO (en informativos solo añade ruido).
        let seenBadge = '';
        if (isCrit || isMid) {
            if (result.first_seen === true) {
                seenBadge = `<span title="Esta evidencia es la primera vez que la vemos en cualquier scan de Argus. Sugerimos revisión humana antes de banear."
                    style="font-size:10px;font-weight:700;padding:1px 6px;border-radius:4px;
                    background:rgba(245,158,11,0.18);color:#f59e0b;border:1px solid rgba(245,158,11,0.45);
                    flex-shrink:0;white-space:nowrap;">🆕 Nueva</span>`;
            } else if (typeof result.seen_count === 'number' && result.seen_count >= 5) {
                seenBadge = `<span title="Esta evidencia ya ha aparecido ${result.seen_count} veces en otros scans. Más confianza en el verdict."
                    style="font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;
                    background:rgba(99,102,241,0.14);color:#818cf8;border:1px solid rgba(99,102,241,0.32);
                    flex-shrink:0;white-space:nowrap;">👁 Visto ${result.seen_count}×</span>`;
            }
        }

        const safeLevel = (result.alert_level || 'SOSPECHOSO').replace(/'/g,"");
        const safeName  = name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const catIcon = _catIcon(cat);
        const flames = _flameIndicator(result.alert_level, result.confidence);
        const glowCls = isCrit ? 'issue-critical-glow' : '';
        const staggerStyle = `animation-delay:${rowIdx * 40}ms;`;
        const conf = result.confidence;
        const confBar = (conf !== undefined && conf !== null) ? `
            <div style="margin-top:5px;display:flex;align-items:center;gap:6px;">
                <div style="flex:1;height:3px;background:rgba(255,255,255,0.07);border-radius:2px;overflow:hidden;">
                    <div style="height:100%;width:${Math.min(conf,100)}%;background:${accent};border-radius:2px;transition:width 0.8s ease;"></div>
                </div>
                <span style="font-size:10px;color:var(--text-d);flex-shrink:0;">${conf}%</span>
            </div>` : '';
        const fmtPath = _formatPath(path);
        const hashMatch = path.match(/\b([a-f0-9]{64})\b/i);
        const copyBtn = hashMatch ? `<button onclick="event.stopPropagation();_copyWithFeedback('${hashMatch[1]}',this)" title="Copiar hash" style="font-size:11px;padding:1px 5px;border-radius:4px;border:1px solid var(--border-m);background:var(--bg-t);color:var(--text-m);cursor:pointer;flex-shrink:0;margin-left:4px;">📋</button>` : '';

        const mainRow = `<div data-result-id="${result.id}" class="issue-row-stagger ${glowCls}" style="${staggerStyle}
            background:${bg};border:1px solid ${accent}33;border-left:3px solid ${accent};
            border-radius:8px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px;
            overflow:hidden;max-width:100%;min-width:0;cursor:pointer;transition:outline 0.15s,background 0.15s;"
            onclick="_selectIssue(this)">
            <span style="font-size:18px;flex-shrink:0;margin-top:0;">${catIcon}</span>
            <div style="flex:1;min-width:0;overflow:hidden;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);display:flex;align-items:center;gap:6px;flex-wrap:nowrap;min-width:0;overflow:hidden;">
                    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:break-all;min-width:0;flex:1;">${name}</span>
                    <span style="font-size:12px;flex-shrink:0;" title="Nivel de peligro">${flames}</span>
                    ${variantBadge}
                    ${metaChip}
                    ${seenBadge}
                    ${instBadge}
                    ${cat ? `<span style="font-size:10px;font-weight:500;color:var(--text-d);background:var(--bg-t);border:1px solid var(--border-m);padding:1px 6px;border-radius:4px;flex-shrink:0;white-space:nowrap;">${_getCategoryLabel(cat)}</span>` : ''}
                    <button onclick="event.stopPropagation();aiExplainFinding('${safeName}','${safeLevel}',this)" title="Explicar con IA"
                            style="font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid rgba(160,90,44,.35);
                                   background:rgba(160,90,44,.1);color:#D4915A;cursor:pointer;flex-shrink:0;">🤖</button>
                </div>
                ${truncPath ? `<div style="font-size:11px;color:var(--text-d);margin-top:3px;overflow:hidden;text-overflow:ellipsis;max-width:100%;" title="${path}">${fmtPath}${copyBtn}</div>` : ''}
                ${confBar}
            </div>
        </div>`;

        if (!_grp) return mainRow;

        const varHtml = _grp.slice(1).map(v => {
            const vn = (v.issue_name||'').slice(0, 100);
            const vp = v.issue_path || '';
            return `<div style="padding:7px 10px;border-radius:6px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);font-size:11px;">
                <div style="color:var(--text-h);font-weight:500;">${vn}</div>
                ${vp ? `<div style="color:var(--text-d);margin-top:2px;font-size:10px;">${vp.length>80?'…'+vp.slice(-78):vp}</div>` : ''}
            </div>`;
        }).join('');
        return `<div style="display:flex;flex-direction:column;gap:4px;">
            ${mainRow}
            <div id="vg_${_gKey}" style="display:none;flex-direction:column;gap:3px;margin-left:28px;padding-left:10px;border-left:2px solid rgba(129,140,248,0.25);">
                ${varHtml}
            </div>
        </div>`;
    }).join('');

    const loadMoreBtn = hasMore ? `
        <div style="text-align:center;padding:10px 0 4px;">
            <button onclick="_loadMoreIssues(${scanId})" style="
                font-size:12px;padding:6px 20px;border-radius:6px;border:1px solid var(--border-m);
                background:var(--bg-t);color:var(--text-m);cursor:pointer;">
                Cargar más (${filtered.length - showCount} restantes)
            </button>
        </div>` : filtered.length > 0 ? `<div style="text-align:center;padding:8px;font-size:11px;color:var(--text-d);">— ${filtered.length} hallazgo(s) total —</div>` : '';

    container.innerHTML = `
        <div class="argus-chip-tabs" role="tablist" aria-label="Filtrar hallazgos por categoría" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid var(--border);">${chips}</div>
        <div class="issues-stagger-host" style="display:flex;flex-direction:column;gap:6px;">${rows || '<div style="padding:20px;text-align:center;color:var(--text-d);font-size:12px;">Sin hallazgos en esta categoría.</div>'}</div>
        ${loadMoreBtn}`;
    // Visual #4 — staggered fade-in en results recién renderizados.
    // Solo se aplica a la primera página; al "Cargar más" la página suma
    // sin re-render, así que también la animamos para consistencia visual.
    try {
        const host = container.querySelector('.issues-stagger-host');
        if (host && window.argusUI && typeof window.argusUI.staggerIn === 'function') {
            window.argusUI.staggerIn(host, { selector: ':scope > *', step: 35, max: 22 });
        }
    } catch (_e) { /* nunca bloquear render por animación */ }
}

// V47: click to select/deselect a finding
function _selectIssue(el) {
    const wasSelected = el.classList.contains('issue-selected');
    document.querySelectorAll('.issue-selected').forEach(e => e.classList.remove('issue-selected'));
    if (!wasSelected) el.classList.add('issue-selected');
}
window._selectIssue = _selectIssue;

function _toggleOnlyInstance(scanId) {
    window._issuesOnlyInstance = !window._issuesOnlyInstance;
    currentIssuesPage = 0;
    const container = document.getElementById('issues-list-container');
    if (container) renderIssuePage(container, scanId);
}

function _setIssueFilter(cat, scanId) {
    _issuesFilter = cat;
    currentIssuesPage = 0;
    const container = document.getElementById('issues-list-container');
    if (container) renderIssuePage(container, scanId);
}

function _loadMoreIssues(scanId) {
    currentIssuesPage++;
    const container = document.getElementById('issues-list-container');
    if (container) renderIssuePage(container, scanId);
}

function changeIssuePage(delta, scanId) {
    const totalPages = Math.ceil(currentIssuesList.length / ISSUES_PER_PAGE);
    currentIssuesPage = Math.max(0, Math.min(currentIssuesPage + delta, totalPages - 1));
    const container = document.getElementById('issues-list-container');
    if (container) renderIssuePage(container, scanId);
}

// ── Verdict functions ──────────────────────────────────────────────────────

function updateBulkActions() { /* resets any stale selection state on load */ }

function skipVerdict() {
    document.getElementById('bulk-actions-bar').style.display = 'none';
}

let _pendingVerdictType = null;

function openVerdictModal(verdictType) {
    _pendingVerdictType = verdictType;
    const title = document.getElementById('verdict-reason-title');
    const btn   = document.getElementById('verdict-confirm-btn');
    const err   = document.getElementById('verdict-reason-error');
    const input = document.getElementById('verdict-reason-input');
    if (title) title.textContent = verdictType === 'clean' ? 'Confirmar: Usuario Limpio' : 'Confirmar: Usuario Con Hacks';
    if (btn)   btn.style.background = verdictType === 'clean' ? '#059669' : '#dc2626';
    if (err)   err.style.display = 'none';
    if (input) input.value = '';
    document.getElementById('verdict-reason-modal').classList.add('active');
}

async function confirmVerdict() {
    const reason = (document.getElementById('verdict-reason-input')?.value || '').trim();
    const errEl  = document.getElementById('verdict-reason-error');
    if (!reason) {
        if (errEl) errEl.style.display = 'block';
        // V45: shake the textarea on error
        const inp = document.getElementById('verdict-reason-input');
        if (inp) _shakeEl(inp);
        return;
    }
    if (errEl) errEl.style.display = 'none';

    const verdict = _pendingVerdictType;
    document.getElementById('verdict-reason-modal').classList.remove('active');

    try {
        // 1. Guardar veredicto en el scan
        const res = await fetch(`/api/scans/${currentScanId}/verdict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ verdict, reason }),
        });
        if (!res.ok) { const d = await res.json(); alert(d.error || 'Error al guardar veredicto'); return; }

        // 2. Si es "hack", abrir la selección de archivos; si es "clean", marcar todo como legítimo
        if (verdict === 'hack') {
            // V43: destroy animation — shake + staggered fade-out
            const issueEls = document.querySelectorAll('#issues-list-container [data-result-id]');
            issueEls.forEach((el, i) => {
                setTimeout(() => {
                    el.style.transition = 'opacity 0.3s, transform 0.3s';
                    el.style.transform = `translateX(${i % 2 === 0 ? -8 : 8}px) scale(0.97)`;
                    el.style.opacity = '0';
                }, i * 40);
            });
            openHackSelection();
        } else {
            // Visual #26 — confetti sutil al confirmar veredicto CLEAN.
            // Preferir argusUI.celebrate (vanilla canvas, sin dependencias);
            // fallback al confetti() global si está cargado en alguna build vieja.
            try {
                if (window.argusUI && typeof window.argusUI.celebrate === 'function') {
                    window.argusUI.celebrate({
                        palette: ['#10b981','#34d399','#6ee7b7','#B87333','#fbbf24','#FFFFFF'],
                        count: 110,
                        duration: 1900,
                        originY: 0.30,
                    });
                } else if (typeof confetti === 'function') {
                    confetti({ particleCount: 90, spread: 70, origin: { y: 0.5 },
                               colors: ['#10b981','#34d399','#6ee7b7','#fff'] });
                }
            } catch (_e) { /* never block verdict on confetti errors */ }
            await submitVerdictClean(reason);
        }

        // 3. Refrescar el banner de veredicto actual
        refreshCurrentVerdictBanner({ verdict, reason, verdict_by: 'tú', verdict_at: new Date().toISOString() });
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

async function submitVerdictClean(reason) {
    document.getElementById('bulk-actions-bar').style.display = 'none';
}

function refreshCurrentVerdictBanner(scanData) {
    const banner = document.getElementById('current-verdict-banner');
    if (!banner || !scanData?.verdict) { if (banner) banner.style.display = 'none'; return; }
    const colors = { clean: { bg: 'rgba(5,150,105,0.12)', border: 'rgba(5,150,105,0.3)', text: '#10b981' },
                     hack:  { bg: 'rgba(220,38,38,0.12)', border: 'rgba(220,38,38,0.3)', text: '#ef4444' },
                     pending: { bg: 'rgba(107,114,128,0.1)', border: 'rgba(107,114,128,0.2)', text: '#9ca3af' } };
    const c = colors[scanData.verdict] || colors.pending;
    const label = scanData.verdict === 'clean' ? 'LIMPIO' : scanData.verdict === 'hack' ? 'CON HACKS' : 'PENDIENTE';
    banner.style.cssText = `display:block;background:${c.bg};border:1px solid ${c.border};border-radius:10px;padding:12px 16px;margin-bottom:4px;font-size:13px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;`;
    let html = `<span style="font-weight:700;color:${c.text};">Veredicto: ${label}</span>`;
    if (scanData.verdict_reason) html += ` <span style="color:var(--text-s);">— ${escapeHtml(scanData.verdict_reason)}</span>`;
    if (scanData.verdict_by) {
        // Visual #40 — avatar circular del staff que firmó el veredicto
        const staffName = String(scanData.verdict_by);
        const initial   = (staffName.match(/[a-zA-Z0-9]/) || ['?'])[0].toUpperCase();
        const hue       = _staffHue(staffName);
        const avatarHtml = `<span title="Firmado por: ${escapeHtml(staffName)}"
            style="display:inline-flex;align-items:center;justify-content:center;
                   width:22px;height:22px;border-radius:50%;
                   background:linear-gradient(135deg, hsl(${hue},70%,50%), hsl(${(hue+30)%360},70%,38%));
                   color:#fff;font-size:11px;font-weight:700;
                   box-shadow:0 0 0 1.5px rgba(255,255,255,0.10), 0 2px 6px rgba(0,0,0,0.30);
                   font-family:ui-sans-serif,system-ui,sans-serif;letter-spacing:0;
                   margin-left:6px;flex-shrink:0;">${initial}</span>`;
        html += `<span style="color:var(--text-d);font-size:11px;display:inline-flex;align-items:center;">por ${escapeHtml(staffName)}${avatarHtml}</span>`;
    }
    banner.innerHTML = html;
}

// Visual #18 — Modal "¿Por qué este score?"
// Calcula breakdown agregando issues por (categoria, alerta) y estima
// el peso de cada bucket sobre el score total.
function _openRiskBreakdownModal(scanData, riskScore, riskClass) {
    // Cerrar modal previo si existe
    document.getElementById('argus-risk-breakdown-modal')?.remove();

    // Preferir issues del scanData si vinieron en el payload
    let issues = scanData?.issues_list || scanData?.issues || [];
    if (!Array.isArray(issues) || !issues.length) {
        // Fallback: extraer desde el DOM
        const cards = document.querySelectorAll('#issues-list-container [data-result-id], #issues-list-container .issue-card, #issues-list-container .result-row');
        issues = Array.from(cards).map(el => ({
            categoria: (el.dataset.categoria || el.dataset.category || 'OTROS').toUpperCase(),
            alerta:    (el.dataset.alerta || el.dataset.severity || 'SOSPECHOSO').toUpperCase(),
            nombre:    (el.dataset.nombre || el.querySelector('.issue-name')?.textContent || '').trim(),
        }));
    }

    // Agregar por (alerta) total
    const counts = { CRITICAL: 0, SOSPECHOSO: 0, NORMAL: 0, OTHER: 0 };
    const byCategory = {};
    issues.forEach(i => {
        const a = (i.alerta || i.severity || 'SOSPECHOSO').toUpperCase();
        if (a === 'CRITICAL' || a === 'CRÍTICO' || a === 'CRITICO') counts.CRITICAL++;
        else if (a === 'SOSPECHOSO') counts.SOSPECHOSO++;
        else if (a === 'NORMAL' || a === 'INFO') counts.NORMAL++;
        else counts.OTHER++;
        const c = (i.categoria || i.category || 'OTROS').toUpperCase();
        if (!byCategory[c]) byCategory[c] = { c: 0, s: 0, n: 0, total: 0 };
        if (a === 'CRITICAL' || a === 'CRÍTICO' || a === 'CRITICO') byCategory[c].c++;
        else if (a === 'SOSPECHOSO') byCategory[c].s++;
        else byCategory[c].n++;
        byCategory[c].total++;
    });

    // Estimación de contribución al score (peso aproximado del scanner real:
    // CRITICAL ~15pts, SOSPECHOSO ~5pts, NORMAL ~1pt — capped a 100)
    const W = { CRITICAL: 15, SOSPECHOSO: 5, NORMAL: 1, OTHER: 2 };
    const estPts = counts.CRITICAL * W.CRITICAL + counts.SOSPECHOSO * W.SOSPECHOSO
                 + counts.NORMAL * W.NORMAL    + counts.OTHER * W.OTHER;

    const verdict = (scanData?.verdict || '').toLowerCase();
    const ai = scanData?.ai_analysis || scanData?.ai_summary || '';

    const colorClass = riskClass || (riskScore >= 70 ? 'risk-hack' : riskScore >= 30 ? 'risk-suspicious' : 'risk-clean');
    const accentColor = riskScore >= 70 ? '#ef4444' : riskScore >= 30 ? '#fbbf24' : '#10b981';

    // Sort categorías por contribución estimada
    const catRows = Object.entries(byCategory)
        .map(([c, v]) => {
            const pts = v.c * W.CRITICAL + v.s * W.SOSPECHOSO + v.n * W.NORMAL;
            return { c, v, pts, pct: estPts ? Math.round(pts / estPts * 100) : 0 };
        })
        .sort((a, b) => b.pts - a.pts);

    const catHtml = catRows.length ? catRows.map(r => `
        <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px dashed var(--border);">
            <div style="flex:1;min-width:0;">
                <div style="font-weight:600;font-size:13px;color:var(--text);">${escapeHtml(r.c)}</div>
                <div style="font-size:11px;color:var(--text-d);margin-top:2px;">
                    ${r.v.c ? `<span style="color:#ef4444;">●</span> ${r.v.c} críticos · ` : ''}
                    ${r.v.s ? `<span style="color:#fbbf24;">●</span> ${r.v.s} sospechosos · ` : ''}
                    ${r.v.n ? `<span style="color:#9ca3af;">●</span> ${r.v.n} normales` : ''}
                </div>
            </div>
            <div style="min-width:130px;">
                <div style="background:var(--bg-3);height:8px;border-radius:4px;overflow:hidden;">
                    <div style="width:${Math.min(100, r.pct)}%;height:100%;background:linear-gradient(90deg, ${accentColor}aa, ${accentColor});transition:width 600ms cubic-bezier(0.22,1,0.36,1);"></div>
                </div>
                <div style="font-size:10.5px;color:var(--text-d);margin-top:3px;text-align:right;font-feature-settings:'tnum' 1;">~${r.pts} pts (${r.pct}%)</div>
            </div>
        </div>
    `).join('') : `<div style="text-align:center;color:var(--text-d);padding:30px;font-size:13px;">Sin issues detectadas — score derivado solo del análisis IA.</div>`;

    const modal = document.createElement('div');
    modal.id = 'argus-risk-breakdown-modal';
    modal.className = 'modal active';
    modal.style.cssText = 'display:flex;align-items:center;justify-content:center;position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,0.65);backdrop-filter:blur(8px);animation:fadeIn 200ms ease;';
    modal.innerHTML = `
        <div role="dialog" aria-labelledby="risk-bd-title" style="background:var(--bg-2);color:var(--text);width:min(560px, 92vw);max-height:88vh;overflow-y:auto;border-radius:14px;border:1px solid var(--border-m);box-shadow:0 20px 60px rgba(0,0,0,0.5);padding:0;">
            <header style="padding:18px 22px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:12px;">
                <h2 id="risk-bd-title" style="margin:0;font-size:15px;font-weight:700;letter-spacing:0.3px;">¿Por qué este score?</h2>
                <button id="risk-bd-close" type="button" aria-label="Cerrar" style="background:transparent;border:1px solid var(--border-m);color:var(--text-m);width:30px;height:30px;border-radius:50%;cursor:pointer;font-size:16px;line-height:1;">×</button>
            </header>
            <div style="padding:22px;">
                <div style="display:flex;align-items:center;gap:18px;margin-bottom:18px;">
                    <div style="font-size:42px;font-weight:800;color:${accentColor};font-feature-settings:'tnum' 1;line-height:1;">${riskScore}</div>
                    <div style="flex:1;">
                        <div style="font-size:13px;color:var(--text-m);margin-bottom:4px;">${riskScore >= 70 ? 'HACK detectado' : riskScore >= 30 ? 'Sospechoso — requiere review humano' : 'Limpio según heurísticas'}</div>
                        <div style="font-size:11px;color:var(--text-d);">El score es la suma de contribuciones por severidad y categoría, capeado a 100. La IA puede ajustarlo según contexto.</div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:18px;">
                    <div style="text-align:center;padding:10px 6px;background:rgba(239,68,68,0.10);border:1px solid rgba(239,68,68,0.25);border-radius:8px;">
                        <div style="font-size:18px;font-weight:800;color:#ef4444;font-feature-settings:'tnum' 1;">${counts.CRITICAL}</div>
                        <div style="font-size:10.5px;color:var(--text-d);margin-top:2px;">críticos · ${W.CRITICAL}pt c/u</div>
                    </div>
                    <div style="text-align:center;padding:10px 6px;background:rgba(251,191,36,0.10);border:1px solid rgba(251,191,36,0.25);border-radius:8px;">
                        <div style="font-size:18px;font-weight:800;color:#fbbf24;font-feature-settings:'tnum' 1;">${counts.SOSPECHOSO}</div>
                        <div style="font-size:10.5px;color:var(--text-d);margin-top:2px;">sospechosos · ${W.SOSPECHOSO}pts</div>
                    </div>
                    <div style="text-align:center;padding:10px 6px;background:rgba(156,163,175,0.10);border:1px solid rgba(156,163,175,0.25);border-radius:8px;">
                        <div style="font-size:18px;font-weight:800;color:#9ca3af;font-feature-settings:'tnum' 1;">${counts.NORMAL}</div>
                        <div style="font-size:10.5px;color:var(--text-d);margin-top:2px;">normales · ${W.NORMAL}pt</div>
                    </div>
                </div>
                <h3 style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;color:var(--text-d);margin:0 0 8px;">Contribución por categoría</h3>
                ${catHtml}
                ${ai ? `<details style="margin-top:18px;"><summary style="cursor:pointer;color:var(--accent);font-size:12px;font-weight:600;">Análisis de la IA</summary><div style="font-size:12.5px;line-height:1.55;color:var(--text-m);margin-top:8px;padding:10px 12px;background:var(--bg-3);border-radius:8px;border-left:3px solid ${accentColor};white-space:pre-wrap;">${escapeHtml(typeof ai === 'string' ? ai : JSON.stringify(ai, null, 2))}</div></details>` : ''}
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#risk-bd-close').onclick = () => modal.remove();
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}


// Visual #40 — color hash determinístico para avatares de staff
function _staffHue(name) {
    if (!name) return 30;
    let h = 0;
    const s = String(name);
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h) % 360;
}

// Helper para escapar HTML cuando no exista ya una versión global
function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

async function loadVerdictHistory() {
    const panel = document.getElementById('verdict-history-panel');
    if (!panel || !currentScanId) return;
    if (panel.style.display === 'block') { panel.style.display = 'none'; return; }
    panel.style.display = 'block';
    panel.innerHTML = 'Cargando historial...';
    try {
        const res  = await fetch(`/api/scans/${currentScanId}/verdict/history`);
        const data = await res.json();
        const h = data.history || [];
        if (!h.length) { panel.innerHTML = '<em>Sin historial de veredictos.</em>'; return; }
        panel.innerHTML = h.map(e =>
            `<div style="padding:5px 0;border-bottom:1px solid var(--border);last-child:border:none;">` +
            `<strong style="color:${e.verdict==='clean'?'#10b981':'#ef4444'}">${e.verdict==='clean'?'LIMPIO':'CON HACKS'}</strong>` +
            ` — ${escapeHtml(e.reason || '—')} <span style="color:var(--text-d);">por ${escapeHtml(e.changed_by || '?')} · ${formatDate(e.changed_at)}</span></div>`
        ).join('');
    } catch(e) { panel.innerHTML = 'Error cargando historial'; }
}

function openHackSelection() {
    const list = document.getElementById('hack-selection-list');
    if (!list) return;
    list.innerHTML = currentIssuesList.map(r => {
        const isCrit = r.alert_level === 'CRITICAL';
        const dot = isCrit ? '🔴' : '🟠';
        const name = r.issue_name || 'Hallazgo';
        const path = r.issue_path || '';
        const truncPath = path.length > 70 ? '…' + path.slice(-67) : path;
        return `<label style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:7px;border:1px solid var(--border-m);background:var(--bg-t);cursor:pointer;">
            <input type="checkbox" data-result-id="${r.id}" style="width:15px;height:15px;flex-shrink:0;cursor:pointer;">
            <span style="font-size:13px;flex-shrink:0;">${dot}</span>
            <div style="min-width:0;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name}</div>
                ${truncPath ? `<div style="font-size:11px;color:var(--text-d);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${truncPath}</div>` : ''}
            </div>
        </label>`;
    }).join('');
    document.getElementById('hack-selection-modal').classList.add('active');
}

function skipHackSelection() {
    document.getElementById('hack-selection-modal').classList.remove('active');
}

async function confirmHackSelection() {
    const modal = document.getElementById('hack-selection-modal');
    const checkboxes = modal.querySelectorAll('input[type="checkbox"]:not([disabled])');
    const hackIds = [];
    const cleanIds = [];
    checkboxes.forEach(cb => {
        const id = parseInt(cb.dataset.resultId);
        const result = currentIssuesList.find(r => r.id === id);
        if (!result) return;
        if (cb.checked) hackIds.push(id);
        else cleanIds.push(id);
    });

    if (!hackIds.length && !cleanIds.length) { skipHackSelection(); return; }

    try {
        const requests = [];
        if (hackIds.length) requests.push(fetch('/api/feedback/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ result_ids: hackIds, verification: 'hack', notes: 'Hack confirmado por staff' }) }));
        if (cleanIds.length) requests.push(fetch('/api/feedback/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ result_ids: cleanIds, verification: 'legitimate', notes: 'Legítimo confirmado por staff' }) }));
        await Promise.all(requests);

        skipHackSelection();
        document.getElementById('bulk-actions-bar').style.display = 'none';
        alert(`Veredicto guardado: ${hackIds.length} hack(s), ${cleanIds.length} limpio(s).`);
    } catch (e) {
        alert('Error al enviar feedback: ' + e.message);
    }
}

async function viewScanDetails(scanId) {
    currentScanId = scanId;

    // Ocultar todas las secciones y mostrar solo el detalle
    document.querySelectorAll('.panel-section').forEach(s => {
        s.classList.remove('active');
        s.style.display = 'none';
    });
    const detailSection = document.getElementById('issues-detail-section');
    detailSection.style.display = 'block';
    detailSection.classList.add('active');

    // Resetear estado UI inmediatamente (evita que quede el estado del escaneo anterior)
    const detectionBannerReset = document.getElementById('detection-banner');
    if (detectionBannerReset) detectionBannerReset.style.display = 'none';
    ['count-clean', 'count-alert', 'count-severe'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
    });
    const issuesContainerReset = document.getElementById('issues-list-container');
    if (issuesContainerReset) {
        if (window.argusUI?.renderLoading) {
            window.argusUI.renderLoading(issuesContainerReset, {
                title: 'Cargando resultados del scan…',
                sub: 'Recuperando hallazgos, metadatos del cliente y veredictos previos.',
                size: 'lg',
            });
        } else {
            issuesContainerReset.innerHTML = `<div class="skel-issues">${
                Array(5).fill(0).map(() => `
                <div class="skel-row">
                    <div class="skel skel-avatar"></div>
                    <div class="skel-text">
                        <div class="skel skel-line w-80"></div>
                        <div class="skel skel-line w-40"></div>
                    </div>
                    <div class="skel skel-badge-sm"></div>
                </div>`).join('')
            }</div>`;
        }
    }

    // Actualizar navegación
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.querySelector('[data-section="resultados"]')?.classList.add('active');

    try {
        const response = await fetch(`/api/scans/${scanId}`);
        // Si la sesion expiro (401) o no tenemos permiso (403), no podemos pintar nada;
        // en lugar de dejar todo en cero (que es la causa del bug "no veo los resultados"),
        // avisamos y redirigimos a /login para que el usuario reinicie sesion.
        if (response.status === 401 || response.status === 403) {
            const issuesContainer = document.getElementById('issues-list-container');
            if (issuesContainer) {
                issuesContainer.innerHTML = `
                    <div style="text-align:center;padding:60px 20px;color:var(--text-m);">
                        <div style="font-size:42px;margin-bottom:14px">🔒</div>
                        <div style="font-size:15px;font-weight:700;color:var(--text-h);margin-bottom:8px">Tu sesión expiró</div>
                        <div style="font-size:13px;margin-bottom:20px;">Por seguridad necesitas iniciar sesión otra vez para ver los resultados.</div>
                        <a href="/login" class="btn btn-primary" style="text-decoration:none;">Iniciar sesión</a>
                    </div>`;
            }
            return;
        }
        if (!response.ok) {
            // Intentamos extraer el detail del backend para diagnosticar rapido.
            let detailLine = '';
            try {
                const errBody = await response.clone().json();
                if (errBody && (errBody.detail || errBody.error)) {
                    detailLine = `<div style="font-size:11px;color:var(--text-d);margin-top:8px;font-family:JetBrains Mono,monospace;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:6px;padding:8px 10px;text-align:left;word-break:break-word;">${(errBody.detail || errBody.error)}</div>`;
                }
            } catch(_) {}
            const issuesContainer = document.getElementById('issues-list-container');
            if (issuesContainer) {
                issuesContainer.innerHTML = `
                    <div style="text-align:center;padding:60px 20px;color:var(--text-m);">
                        <div style="font-size:42px;margin-bottom:14px">⚠️</div>
                        <div style="font-size:15px;font-weight:700;color:var(--text-h);margin-bottom:8px">No se pudieron cargar los resultados</div>
                        <div style="font-size:13px;">Error HTTP ${response.status} al consultar /api/scans/${scanId}.</div>
                        ${detailLine}
                        <button class="btn btn-sm" style="margin-top:18px" onclick="viewScanDetails(${scanId})">Reintentar</button>
                    </div>`;
            }
            return;
        }
        const data = await response.json();
        _currentScanData = data;

        // Calcular estadísticas de severidad
        const severityStats = { clean: 0, alert: 0, severe: 0, low: 0 };
        if (data.results && data.results.length > 0) {
            data.results.forEach(result => {
                const level = result.alert_level;
                if (level === 'CRITICAL') severityStats.severe++;
                else if (level === 'SOSPECHOSO') severityStats.alert++;
                else if (level === 'POCO_SOSPECHOSO') severityStats.low++;
                else severityStats.clean++;
            });
        }
        // Actualizar IDs de compatibilidad (ocultos)
        const sc = document.getElementById('sum-critical'); if (sc) sc.textContent = severityStats.severe;
        const ss = document.getElementById('sum-suspicious'); if (ss) ss.textContent = severityStats.alert;
        const sl = document.getElementById('sum-low'); if (sl) sl.textContent = severityStats.low;
        const sk = document.getElementById('sum-clean'); if (sk) sk.textContent = (data.total_files_scanned || severityStats.clean).toLocaleString();

        // ── Severity summary bar (log de indicaciones) ──────────────────
        const _set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        // V5: animated counters for severity stats
        ['log-severe','ring-num-critical'].forEach(id => animateNumber(document.getElementById(id), severityStats.severe, 800));
        ['log-alert','ring-num-alert'].forEach(id => animateNumber(document.getElementById(id), severityStats.alert, 800));
        animateNumber(document.getElementById('log-clean'), severityStats.clean + severityStats.low, 800);
        animateNumber(document.getElementById('ring-num-low'), severityStats.low, 800);
        animateNumber(document.getElementById('ring-num-clean'), severityStats.clean, 800);

        // ── Donut ring chart (SVG) ───────────────────────────────────────
        (function renderRingChart(stats) {
            const total = stats.severe + stats.alert + stats.low + stats.clean;
            const numEl = document.getElementById('ring-center-num');
            const lblEl = document.getElementById('ring-center-label');
            if (numEl) numEl.textContent = stats.severe + stats.alert + stats.low;
            if (lblEl) lblEl.textContent = total === 0 ? 'sin datos' : stats.severe + stats.alert + stats.low === 0 ? 'limpio ✓' : 'hallazgos';

            const CIRC = 2 * Math.PI * 54; // r=54 → ~339.3
            const segments = [
                { id: 'ring-seg-clean',    count: stats.clean },
                { id: 'ring-seg-low',      count: stats.low   },
                { id: 'ring-seg-alert',    count: stats.alert  },
                { id: 'ring-seg-critical', count: stats.severe },
            ];
            let offset = 0;
            for (const seg of segments) {
                const el = document.getElementById(seg.id);
                if (!el) continue;
                if (total === 0 || seg.count === 0) {
                    el.setAttribute('stroke-dasharray', `0 ${CIRC}`);
                    el.setAttribute('stroke-dashoffset', '0');
                    continue;
                }
                const len = (seg.count / total) * CIRC;
                el.setAttribute('stroke-dasharray', `${len.toFixed(2)} ${(CIRC - len).toFixed(2)}`);
                el.setAttribute('stroke-dashoffset', (-offset).toFixed(2));
                offset += len;
            }
            // If all zero show a grey placeholder ring
            if (total === 0) {
                const el = document.getElementById('ring-seg-clean');
                if (el) { el.setAttribute('stroke', 'rgba(255,255,255,0.08)'); el.setAttribute('stroke-dasharray', `${CIRC} 0`); }
            }
        })(severityStats);
        
        // Actualizar información del escaneo (columna izquierda)
        const scanIdEl = document.getElementById('detail-scan-id');
        if (scanIdEl) scanIdEl.textContent = scanId;
        
        const osEl = document.getElementById('detail-os');
        if (osEl) {
            const osRaw = data.os || data.os_name || data.operating_system || '';
            const safeOs = escapeHtml(osRaw.trim() || '—');
            osEl.innerHTML = `${safeOs}${_scanPlatformChipHtml(data)}${_scannerVersionChipHtml(data)}`;
        }
        
        const machineEl = document.getElementById('detail-machine-name');
        if (machineEl) {
            machineEl.textContent = data.machine_name || 'N/A';
            machineEl.style.cursor = 'pointer';
            machineEl.title = 'Ver historial de este jugador';
            machineEl.style.textDecoration = 'underline dotted';
            machineEl.onclick = () => {
                const btn = document.querySelector('.subnav-item[data-subpage="escaneos-previos"]');
                if (btn) btn.click();
            };
        }
        
        const filesEl = document.getElementById('detail-files-count');
        if (filesEl) {
            const files = (data.total_files_scanned || 0).toLocaleString();
            const dirsN = data.total_dirs_scanned || 0;
            filesEl.textContent = dirsN > 0 ? `${files} arch. · ${dirsN.toLocaleString()} carpetas` : files;
        }
        
        const vmEl = document.getElementById('detail-vm');
        if (vmEl) vmEl.textContent = data.is_vm ? 'Sí' : 'No';
        
        const connectionEl = document.getElementById('detail-connection');
        if (connectionEl) connectionEl.textContent = data.connection_type || 'Residencial';
        
        const countryEl = document.getElementById('detail-country');
        if (countryEl) countryEl.textContent = data.country || 'N/A';
        
        const minecraftUsernameEl = document.getElementById('detail-minecraft-username');
        if (minecraftUsernameEl) minecraftUsernameEl.textContent = data.minecraft_username || 'No detectado';

        // Player avatar + subtitle label
        const _username = data.minecraft_username || data.machine_name || '';
        const avatarEl = document.getElementById('scan-header-avatar');
        if (avatarEl) {
            avatarEl.title = _username || 'Jugador';
            if (_username) {
                avatarEl.innerHTML = '';
                avatarEl.style.background = 'rgba(0,0,0,0.25)';
                avatarEl.style.padding = '2px';
                const _img = document.createElement('img');
                _img.src = `https://mc-heads.net/avatar/${encodeURIComponent(_username)}/32`;
                _img.style.cssText = 'width:100%;height:100%;border-radius:6px;object-fit:cover;image-rendering:pixelated;display:block;';
                _img.onerror = () => {
                    avatarEl.innerHTML = _username[0].toUpperCase();
                    avatarEl.style.background = _nameToHslColor(_username);
                    avatarEl.style.padding = '0';
                };
                avatarEl.appendChild(_img);
            } else {
                avatarEl.textContent = '?';
                avatarEl.style.background = 'var(--accent-d)';
                avatarEl.style.padding = '0';
            }
        }
        const playerLabelEl = document.getElementById('scan-page-player-label');
        if (playerLabelEl) playerLabelEl.textContent = _username || 'Minecraft';

        const scannedByEl = document.getElementById('detail-scanned-by');
        if (scannedByEl) scannedByEl.textContent = data.scanned_by || '—';
        
        // Mostrar historial de bans si existe
        const banHistoryItem = document.getElementById('ban-history-item');
        const banHistoryList = document.getElementById('ban-history-list');
        if (data.ban_history && data.ban_history.length > 0 && banHistoryItem && banHistoryList) {
            banHistoryItem.style.display = 'block';
            banHistoryList.innerHTML = data.ban_history.map(ban => {
                const banDate = ban.banned_at ? formatDate(ban.banned_at) : 'Fecha desconocida';
                return `
                    <div class="ban-history-entry">
                        <div class="ban-reason"><strong>${ban.hack_type || 'Desconocido'}:</strong> ${ban.reason || 'Sin razón especificada'}</div>
                        <div class="ban-date">${banDate}</div>
                    </div>
                `;
            }).join('');
        } else if (banHistoryItem) {
            banHistoryItem.style.display = 'none';
        }
        
        // Calcular duración del escaneo
        const scanDuration = data.scan_duration || 0;
        const minutes = Math.floor(scanDuration / 60);
        const seconds = Math.floor(scanDuration % 60);
        const durationText = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
        const speedEl = document.getElementById('detail-scan-speed');
        if (speedEl) speedEl.textContent = durationText;
        
        const dateEl = document.getElementById('detail-scan-date');
        if (dateEl) dateEl.textContent = formatDate(data.started_at);

        // Installation date + Recycle Bin date from scan results
        const _results = data.results || [];
        const _installResult = _results.find(r => {
            const n = (r.issue_name || '').toLowerCase();
            return n.includes('instalacion') || n.includes('installación') || n.includes('installation') || n.includes('install_date');
        });
        const mcInstallRow = document.getElementById('mc-install-row');
        const mcInstallEl  = document.getElementById('detail-mc-install');
        if (_installResult && mcInstallRow && mcInstallEl) {
            const _ip = _installResult.issue_path || _installResult.issue_name || '';
            const _dateMatch = _ip.match(/\d{4}-\d{2}-\d{2}/);
            if (_dateMatch) {
                mcInstallEl.textContent = _dateMatch[0];
                mcInstallRow.style.display = 'flex';
            }
        }
        const _recycleResult = _results.find(r => {
            const n = (r.issue_name || '').toLowerCase();
            const c = (r.issue_category || '').toLowerCase();
            return c === 'forense' && (n.includes('borrado') || n.includes('reciclaje') || n.includes('recicl') || n.includes('deleted') || n.includes('limpieza'));
        });
        const recycleDateRow = document.getElementById('recycle-date-row');
        const recycleDateEl  = document.getElementById('detail-recycle-date');
        if (_recycleResult && recycleDateRow && recycleDateEl) {
            const _rp = _recycleResult.issue_path || '';
            const _rdMatch = _rp.match(/\d{4}-\d{2}-\d{2}/);
            if (_rdMatch) {
                recycleDateEl.textContent = _rdMatch[0];
                recycleDateRow.style.display = 'flex';
            } else if (_recycleResult.issue_name) {
                recycleDateEl.textContent = 'Detectado';
                recycleDateRow.style.display = 'flex';
            }
        }

        // Risk score badge
        const riskScore = data.risk_score || 0;
        const riskBadge = document.getElementById('detail-risk-score-badge');
        const riskBar   = document.getElementById('detail-risk-score-bar');
        if (riskBadge && riskBar) {
            const riskClass = riskScore >= 70 ? 'risk-hack' : riskScore >= 30 ? 'risk-suspicious' : 'risk-clean';
            const riskLabel = riskScore >= 70 ? `${riskScore} — HACK` : riskScore >= 30 ? `${riskScore} — Sospechoso` : `${riskScore} — Limpio`;
            riskBadge.className = `risk-score-badge ${riskClass}`;
            // Visual #18 — botón "Por qué este score" (interrogante junto al texto)
            riskBadge.innerHTML = `<span style="display:inline-flex;align-items:center;gap:6px;">${escapeHtml(riskLabel)}<span class="risk-why-btn" title="¿Por qué este score? — Click para ver el breakdown" role="button" tabindex="0" style="display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;background:rgba(255,255,255,0.15);font-size:11px;font-weight:700;cursor:pointer;line-height:1;">?</span></span>`;
            riskBadge.style.cursor = 'pointer';
            riskBadge.title = 'Click para ver el breakdown del score';
            riskBadge.onclick = () => _openRiskBreakdownModal(data, riskScore, riskClass);
            riskBar.className = `risk-score-bar ${riskClass}`;
            riskBar.style.width = `${Math.min(riskScore, 100)}%`;
            // Visual #27 — sacudida sutil cuando el veredicto es hack
            // Permite re-disparar la animación quitándola y forzando reflow.
            if (riskClass === 'risk-hack' && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                riskBadge.classList.remove('argus-shake');
                void riskBadge.offsetWidth;
                riskBadge.classList.add('argus-shake');
            } else {
                riskBadge.classList.remove('argus-shake');
            }
        }

        // V1: Render animated SVG gauge if container exists
        if (riskScore !== undefined && riskScore !== null) {
            _renderRiskGauge('risk-gauge-container', riskScore);
        }

        // 6-system ensemble verdict card
        _renderEnsembleVerdict(data);

        // P3 #13 — Active learning: marcar casos inciertos donde la revisión del staff es más valiosa
        const verdict = data.verdict || '';
        const alBadge = document.getElementById('active-learning-badge');
        if (alBadge) {
            const uncertain = riskScore >= 30 && riskScore < 65 && !verdict && data.status === 'completed';
            alBadge.style.display = uncertain ? 'inline-flex' : 'none';
        }
        
        // Mostrar/ocultar banner de detección
        const detectionBanner = document.getElementById('detection-banner');
        if (data.status === 'running') {
            // Scan aún en curso — no mostrar banner ni resultados vacíos
            if (detectionBanner) detectionBanner.style.display = 'none';
            const issuesContainer = document.getElementById('issues-list-container');
            if (issuesContainer) issuesContainer.innerHTML = `
                <div style="text-align:center;padding:60px 20px;color:var(--text-m)">
                    <div style="font-size:36px;margin-bottom:14px">⏳</div>
                    <div style="font-size:15px;font-weight:700;color:var(--text);margin-bottom:8px">Scan en progreso...</div>
                    <div style="font-size:13px">El jugador debe dejar el scanner abierto hasta que termine y suba los resultados.</div>
                    <div style="font-size:12px;color:var(--text-d);margin-top:10px">Archivos hasta ahora: <strong>${(data.total_files_scanned || 0).toLocaleString()}</strong></div>
                    <button class="btn btn-sm" style="margin-top:18px" onclick="viewScanDetails(${scanId})">Actualizar</button>
                </div>`;
            document.getElementById('bulk-actions-bar').style.display = 'none';
            // Auto-refresh cada 8s mientras siga en running (evita pantalla "limpia" con 0 hallazgos)
            if (window._scanPollTimer) clearInterval(window._scanPollTimer);
            window._scanPollTimer = setInterval(() => {
                if (currentScanId === scanId) viewScanDetails(scanId);
            }, 8000);
            return;
        }
        if (window._scanPollTimer) {
            clearInterval(window._scanPollTimer);
            window._scanPollTimer = null;
        }
        if (data.status === 'abandoned' || data.status === 'failed') {
            const issuesContainer = document.getElementById('issues-list-container');
            if (issuesContainer) issuesContainer.innerHTML = `
                <div style="text-align:center;padding:60px 20px;color:var(--text-m)">
                    <div style="font-size:36px;margin-bottom:14px">⚠️</div>
                    <div style="font-size:15px;font-weight:700;color:var(--text);margin-bottom:8px">Scan incompleto</div>
                    <div style="font-size:13px">El scanner no envió resultados (cerrado, crash o timeout). Pedí al jugador que vuelva a ejecutar el SS.</div>
                    <button class="btn btn-sm" style="margin-top:18px" onclick="viewScanDetails(${scanId})">Reintentar</button>
                </div>`;
            document.getElementById('bulk-actions-bar').style.display = 'none';
            return;
        } else if (data.verdict === 'hack') {
            if (detectionBanner) detectionBanner.style.display = 'flex';
        } else if (data.verdict === 'clean' || data.verdict === 'limpio') {
            if (detectionBanner) detectionBanner.style.display = 'none';
        } else if (severityStats.severe > 0 || severityStats.alert > 0) {
            // Sin veredicto explícito — mostrar banner si hay hallazgos críticos
            if (detectionBanner) detectionBanner.style.display = 'flex';
        } else {
            if (detectionBanner) detectionBanner.style.display = 'none';
        }
        
        // Cargar escaneos previos si existe la subpágina
        loadPreviousScans(data.machine_name || data.machine_id);

        // Sugerencia de veredicto por IA (solo si el scan está completo y sin veredicto)
        const aiCard = document.getElementById('ai-verdict-card');
        if (aiCard) aiCard.style.display = 'none';
        if (data.status === 'completed' && !data.verdict) {
            _loadAIVerdictSuggestion(scanId);
        }
        
        // Inicializar navegación de subpáginas si no está inicializada
        if (typeof setupSubpageNavigation === 'function') {
            setupSubpageNavigation();
        }
        
        // Mostrar hallazgos: CRITICAL y SOSPECHOSO primero, luego MUY_SOSPECHOSO y POCO_SOSPECHOSO
        const issuesContainer = document.getElementById('issues-list-container');
        currentIssuesPage = 0;
        _issuesFilter = 'all';
        _issuesSearchText = '';
        _issuesSeverity   = '';
        window._issuesOnlyInstance = false;
        // Reset search UI
        const _si = document.getElementById('issues-search-input');
        const _ss = document.getElementById('issues-severity-select');
        if (_si) _si.value = '';
        if (_ss) _ss.value = '';
        const _cl = document.getElementById('issues-count-label');
        if (_cl) _cl.textContent = '';
        const _alertOrder = { CRITICAL: 0, SOSPECHOSO: 1, MUY_SOSPECHOSO: 2, POCO_SOSPECHOSO: 3 };
        const _allNonClean = (data.results || []).filter(r => r.alert_level && r.alert_level !== 'CLEAN');

        // Páginas web van a su propia sección — fuera de la lista principal
        const _webResults = _allNonClean.filter(r => r.alert_level === 'PAGINA_SOSPECHOSA');
        currentIssuesList = _allNonClean
            .filter(r => r.alert_level !== 'PAGINA_SOSPECHOSA')
            .sort((a, b) => {
                const ai = _isInMinecraftInstance(a.issue_path) ? 0 : 1;
                const bi = _isInMinecraftInstance(b.issue_path) ? 0 : 1;
                if (ai !== bi) return ai - bi;
                return (_alertOrder[a.alert_level] ?? 9) - (_alertOrder[b.alert_level] ?? 9);
            });

        // Renderizar sección de historial web si hay resultados
        _renderWebHistory(_webResults, scanId);

        renderIssuePage(issuesContainer, scanId);

        document.getElementById('bulk-actions-bar').style.display = currentIssuesList.length > 0 ? 'flex' : 'none';
        updateBulkActions();

        // V10: Auto-scroll to first CRITICAL after 600ms
        if (severityStats.severe > 0) {
            setTimeout(() => {
                const firstCrit = issuesContainer.querySelector('.issue-critical-glow');
                if (firstCrit) {
                    firstCrit.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstCrit.style.outline = '2px solid #ef4444';
                    firstCrit.style.outlineOffset = '2px';
                    setTimeout(() => { firstCrit.style.outline = ''; firstCrit.style.outlineOffset = ''; }, 2500);
                }
            }, 650);
        }

        // Mostrar veredicto actual si existe
        refreshCurrentVerdictBanner(data);

        // ── Mouse & Forensics tab ─────────────────────────────────────────
        const mouseFn = data.mouse_findings || [];
        const forensicFn = data.forensic_findings || [];
        const hasMF = mouseFn.length > 0 || forensicFn.length > 0;

        const subnavBtn = document.getElementById('subnav-mouse-forensics');
        if (subnavBtn) subnavBtn.style.display = hasMF ? '' : 'none';

        const mfBadge = document.getElementById('mf-badge');
        if (mfBadge) {
            const criticals = [...mouseFn, ...forensicFn].filter(f => f.alerta === 'CRITICAL').length;
            if (criticals > 0) { mfBadge.textContent = criticals; mfBadge.style.display = ''; }
            else mfBadge.style.display = 'none';
        }

        // Mouse list
        const mouseList = document.getElementById('mf-mouse-list');
        const mouseBadge = document.getElementById('mf-mouse-badge');
        if (mouseList) {
            if (mouseFn.length > 0) {
                if (mouseBadge) { mouseBadge.textContent = mouseFn.length + ' alerta(s)'; mouseBadge.style.display = ''; }
                mouseList.innerHTML = mouseFn.map(f => {
                    const color = f.alerta === 'CRITICAL' ? '#dc2626' : '#d97706';
                    return `<div style="background:rgba(${f.alerta==='CRITICAL'?'220,38,38':'217,119,6'},0.08);border-left:3px solid ${color};border-radius:6px;padding:10px 14px;">
                        <div style="font-weight:700;color:${color};font-size:13px;">${f.alerta==='CRITICAL'?'🔴':'🟠'} ${f.nombre||''}</div>
                        ${f.detalle?`<div style="color:var(--text-m);font-size:12px;margin-top:4px;">${f.detalle}</div>`:''}
                        ${f.descripcion?`<div style="color:var(--text-d);font-size:11px;margin-top:4px;">${f.descripcion}</div>`:''}
                    </div>`;
                }).join('');
            } else {
                if (mouseBadge) mouseBadge.style.display = 'none';
                mouseList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">✅ Sin indicadores de peso o manipulación de mouse.</p>';
            }
        }

        // Forensics list
        const forensicsList = document.getElementById('mf-forensics-list');
        const forensicsBadge = document.getElementById('mf-forensics-badge');
        if (forensicsList) {
            if (forensicFn.length > 0) {
                if (forensicsBadge) { forensicsBadge.textContent = forensicFn.length + ' hallazgo(s)'; forensicsBadge.style.display = ''; }
                forensicsList.innerHTML = forensicFn.map(f => {
                    const color = f.alerta === 'CRITICAL' ? '#9333ea' : '#6366f1';
                    return `<div style="background:rgba(99,102,241,0.08);border-left:3px solid ${color};border-radius:6px;padding:10px 14px;">
                        <div style="font-weight:700;color:${color};font-size:13px;">${f.alerta==='CRITICAL'?'🔴':'🔬'} ${f.nombre||''}</div>
                        <div style="color:var(--text-m);font-size:11px;margin-top:2px;">Fuente: ${f.tipo||'—'}</div>
                        ${f.detalle?`<div style="color:var(--text-m);font-size:12px;margin-top:4px;">${f.detalle}</div>`:''}
                        ${f.descripcion?`<div style="color:var(--text-d);font-size:11px;margin-top:4px;">${f.descripcion}</div>`:''}
                    </div>`;
                }).join('');
            } else {
                if (forensicsBadge) forensicsBadge.style.display = 'none';
                forensicsList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">✅ Sin evidencia forense histórica de hacks o autoclickers.</p>';
            }
        }


        // ── Nuevas secciones: Texture Packs, Ejecutados, Eliminados, Comandos ──
        const allResults = data.results || [];

        // Texture Packs
        const texturePacks = allResults.filter(r => r.issue_type === 'texture_pack' || r.issue_type === 'texture_pack_xray' || r.issue_category === 'TEXTURE_PACKS');
        const tpBtn = document.getElementById('subnav-texture-packs');
        if (tpBtn) tpBtn.style.display = texturePacks.length > 0 ? '' : 'none';
        const tpBadge = document.getElementById('tp-badge');
        if (tpBadge) {
            const xrays = texturePacks.filter(r => r.alert_level === 'CRITICAL').length;
            if (xrays > 0) { tpBadge.textContent = xrays; tpBadge.style.display = ''; }
            else tpBadge.style.display = 'none';
        }
        const tpList = document.getElementById('texture-packs-list');
        const tpCountBadge = document.getElementById('tp-count-badge');
        if (tpList) {
            if (texturePacks.length > 0) {
                if (tpCountBadge) { tpCountBadge.textContent = texturePacks.length; tpCountBadge.style.display = ''; }
                tpList.innerHTML = texturePacks.map(r => {
                    const isXray = r.alert_level === 'CRITICAL';
                    const accent = isXray ? '#ef4444' : '#10b981';
                    return `<div style="background:rgba(${isXray?'239,68,68':'16,185,129'},0.06);border:1px solid rgba(${isXray?'239,68,68':'16,185,129'},0.25);border-radius:8px;padding:12px 14px;display:flex;align-items:center;gap:12px;">
                        <span style="font-size:20px;">${isXray?'⚠️':'🖼️'}</span>
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:13px;font-weight:600;color:${accent};">${r.issue_name||r.issue_path||'Pack'}</div>
                            <div style="font-size:11px;color:var(--text-d);margin-top:2px;">${r.issue_path||''}</div>
                        </div>
                        <span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:5px;background:rgba(${isXray?'239,68,68':'16,185,129'},0.15);color:${accent};">${isXray?'POSIBLE XRAY':'NORMAL'}</span>
                    </div>`;
                }).join('');
            } else {
                if (tpCountBadge) tpCountBadge.style.display = 'none';
                tpList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">✅ Sin texture packs detectados.</p>';
            }
        }

        // Proceso Minecraft info (en scan-info-block)
        const mcProc = allResults.find(r => r.issue_type === 'minecraft_process_info');
        const mcProcBlock = document.getElementById('mc-process-info');
        if (mcProcBlock && mcProc) {
            mcProcBlock.style.display = 'flex';
            const parts = (mcProc.issue_path || '').split(' | ');
            const getPart = (prefix) => {
                const p = parts.find(s => s.startsWith(prefix));
                return p ? p.replace(prefix + ': ', '').trim() : '—';
            };
            const pidEl = document.getElementById('detail-mc-pid');
            const ramEl = document.getElementById('detail-mc-ram');
            const startEl = document.getElementById('detail-mc-started');
            const connEl = document.getElementById('detail-mc-conn');
            const connRow = document.getElementById('mc-conn-row');
            if (pidEl) pidEl.textContent = getPart('PID');
            if (ramEl) ramEl.textContent = getPart('RAM');
            if (startEl) startEl.textContent = getPart('Inicio');
            const connStr = getPart('Conexiones');
            if (connEl && connRow && connStr !== '—') {
                connEl.textContent = connStr;
                connRow.style.display = 'flex';
            }
        }

        // MC info from scanner detection (version, launcher, mods, agents)
        const mcInfoRow = document.getElementById('mc-info-row');
        if (mcInfoRow) {
            const mci = data.mc_info;
            if (mci && (mci.version || mci.launcher)) {
                mcInfoRow.style.display = 'flex';
                const verEl = document.getElementById('detail-mc-version');
                if (verEl) verEl.textContent = mci.version || '?';
                const launchEl = document.getElementById('detail-mc-launcher');
                if (launchEl) launchEl.textContent = mci.launcher || 'Desconocido';
                const agentsRow = document.getElementById('mc-agents-row');
                const agentsEl = document.getElementById('detail-mc-agents');
                if (agentsRow && agentsEl && mci.java_agents && mci.java_agents.length > 0) {
                    agentsEl.textContent = mci.java_agents.length + ' agente(s)';
                    agentsRow.style.display = 'flex';
                }
                const modsRow = document.getElementById('mc-mods-row');
                const modsEl = document.getElementById('detail-mc-mods');
                if (modsRow && modsEl && mci.mods && mci.mods.length > 0) {
                    modsEl.textContent = mci.mods.slice(0, 10).join(', ') + (mci.mods.length > 10 ? ` +${mci.mods.length - 10} más` : '');
                    modsRow.style.display = 'block';
                }
            } else {
                mcInfoRow.style.display = 'none';
            }
        }

        // ── Ejecutados ─────────────────────────────────────────────────────────
        // Categorías/tipos que indican que un programa fue ejecutado (no borrado)
        // Todos los sets en minúscula — comparar con .toLowerCase() para ser case-insensitive
        const EJECUTADOS_CATS = new Set(['appcompat','appswitched','usn_forensics']);
        const EJECUTADOS_TYPES = new Set([
            'usn_created','usn_renamed_old','usn_renamed_new',
            'appcompat_hack','appswitched_hack','recent_hack_exe',
            'prefetch_history','prefetch_suspicious',
            'userassist_history','userassist_suspicious',
            'shimcache_history','shimcache_suspicious',
            'muicache_history','muicache_suspicious',
        ]);
        const BORRADOS_CATS  = new Set(['executed_deleted','usn_forensics']);
        const BORRADOS_TYPES = new Set([
            'usn_deleted','usn_prefetch_deleted','executed_deleted_file',
            'deleted_suspicious','deleted_history','deleted_recycle',
        ]);

        const ejecutados = allResults.filter(r => {
            const cat  = (r.issue_category || '').toLowerCase();
            const tipo = (r.issue_type || '').toLowerCase();
            if (BORRADOS_TYPES.has(tipo) || cat === 'executed_deleted') return false;
            return EJECUTADOS_CATS.has(cat) || EJECUTADOS_TYPES.has(tipo);
        });
        const eliminados = allResults.filter(r => {
            const cat  = (r.issue_category || '').toLowerCase();
            const tipo = (r.issue_type || '').toLowerCase();
            return BORRADOS_TYPES.has(tipo) || cat === 'executed_deleted' ||
                   (BORRADOS_CATS.has(cat) && BORRADOS_TYPES.has(tipo));
        });

        const ejBtn = document.getElementById('subnav-ejecutados');
        if (ejBtn) ejBtn.style.display = ejecutados.length > 0 ? '' : 'none';
        const ejList = document.getElementById('ejecutados-list');
        if (ejList && ejecutados.length > 0) {
            ejList.innerHTML = ejecutados.map(r => {
                const isSusp = r.alert_level === 'CRITICAL' || r.alert_level === 'SOSPECHOSO';
                const accent = isSusp ? '#ef4444' : '#38bdf8';
                const bg = isSusp ? 'rgba(239,68,68,0.06)' : 'rgba(56,189,248,0.04)';
                const nameStr = (r.issue_name || r.issue_path || '—').slice(0, 120);
                return `<div style="background:${bg};border:1px solid ${accent}33;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:12px;font-weight:600;color:${accent};">${isSusp?'⚠️ ':'▶️ '}${nameStr}</div>
                    ${r.issue_path?`<div style="font-size:11px;color:var(--text-d);margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${r.issue_path}">${r.issue_path.length>100?'…'+r.issue_path.slice(-97):r.issue_path}</div>`:''}
                    ${r.alert_level?`<div style="margin-top:4px;font-size:10px;font-weight:700;color:${accent};text-transform:uppercase;">${r.alert_level}</div>`:''}
                </div>`;
            }).join('');
        } else if (ejList) {
            ejList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin historial de ejecutados para este escaneo.</p>';
        }

        const elBtn = document.getElementById('subnav-eliminados');
        if (elBtn) elBtn.style.display = eliminados.length > 0 ? '' : 'none';
        const elList = document.getElementById('eliminados-list');
        if (elList && eliminados.length > 0) {
            elList.innerHTML = eliminados.map(r => {
                const isCrit = r.alert_level === 'CRITICAL';
                const isSusp = isCrit || r.alert_level === 'SOSPECHOSO';
                const accent = isCrit ? '#ef4444' : isSusp ? '#f59e0b' : '#94a3b8';
                const bgRgb  = isCrit ? '239,68,68' : isSusp ? '245,158,11' : '148,163,184';
                const nameStr = (r.issue_name || r.issue_path || '—').slice(0, 120);
                // Extraer hora de borrado del nombre ("Borrado hace 2h: archivo.exe")
                const timeMatch = nameStr.match(/^Borrado (hace .+?):/);
                const timeTag   = timeMatch
                    ? `<span style="font-size:10px;font-weight:700;color:${accent};background:${accent}22;border-radius:4px;padding:1px 6px;margin-left:6px;">${timeMatch[1]}</span>`
                    : '';
                const displayName = timeMatch ? nameStr.replace(/^Borrado .+?: /, '') : nameStr;
                return `<div style="background:rgba(${bgRgb},0.06);border:1px solid ${accent}33;border-radius:8px;padding:12px 14px;">
                    <div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">
                        <span style="font-size:12px;font-weight:600;color:${accent};">🗑️ ${displayName}</span>${timeTag}
                    </div>
                    ${r.issue_path?`<div style="font-size:11px;color:var(--text-d);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${r.issue_path}">${r.issue_path.length>100?'…'+r.issue_path.slice(-97):r.issue_path}</div>`:''}
                    ${isCrit?`<div style="margin-top:4px;font-size:10px;font-weight:700;color:${accent};text-transform:uppercase;">CRÍTICO</div>`:''}
                </div>`;
            }).join('');
        } else if (elList) {
            elList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin archivos eliminados detectados para este escaneo.</p>';
        }

        // Comandos (CMD + PowerShell + descargas + tareas programadas)
        const CMD_TYPES = new Set([
            'cmd_history','cmd_history_full','powershell_history','powershell_suspicious',
            'browser_download_history','browser_download_suspicious','browser_download_hack','browser_visited_hack',
            'scheduled_task_suspicious',
        ]);
        const comandos = allResults.filter(r => {
            const cat  = (r.issue_category || '').toLowerCase();
            const tipo = (r.issue_type || '').toLowerCase();
            return cat === 'cmd_history' || CMD_TYPES.has(tipo);
        });
        const cmdBtn = document.getElementById('subnav-comandos');
        if (cmdBtn) cmdBtn.style.display = comandos.length > 0 ? '' : 'none';
        const cmdList = document.getElementById('comandos-list');
        if (cmdList && comandos.length > 0) {
            cmdList.innerHTML = comandos.map(r => {
                const isSusp = r.alert_level === 'CRITICAL' || r.alert_level === 'SOSPECHOSO';
                const accent = isSusp ? '#ef4444' : '#D4915A';
                return `<div style="background:rgba(${isSusp?'239,68,68':'167,139,250'},0.06);border:1px solid ${accent}33;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:12px;font-weight:600;color:${accent};">💻 ${r.issue_name||'—'}</div>
                    ${r.issue_path?`<div style="font-size:11px;color:var(--text-d);margin-top:3px;">${r.issue_path}</div>`:''}
                </div>`;
            }).join('');
        } else if (cmdList) {
            cmdList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin historial de comandos para este escaneo.</p>';
        }

        // ── Echo-style tabs: Cuentas, Launcher Profiles, Process Times, Explore, Utilities, Archivos de Windows, Settings ──
        _renderTabFindings('cuentas-list',         'subnav-cuentas',          'cuentas-badge',          allResults, ['MINECRAFT']);
        _renderTabFindings('launcher-profiles-list','subnav-launcher-profiles','launcher-badge',          allResults, ['MINECRAFT_CONFIGS', 'JAR_FILES']);
        _renderTabFindings('process-times-list',   'subnav-process-times',    'process-times-badge',     allResults, ['PROCESSES', 'BACKGROUND_PROCESSES', 'PREFETCH', 'EXECUTED_FILES', 'PROCESO']);
        _renderTabFindings('explore-list',         'subnav-explore',          'explore-badge',           allResults, ['RECENT_FILES', 'NEW_FILES', 'HIDDEN_FILES']);
        _renderFileActivityTable(allResults);
        _renderTabFindings('utilities-list',       'subnav-utilities',        'utilities-badge',         allResults, ['AUTOCLICK', 'AUTOCLICK_TOOLS', 'HARDWARE', 'LOGITECH', 'RAZER', 'USB_DEVICES', 'SERVICES', 'MACRO']);
        _renderTabFindings('archivos-windows-list','subnav-archivos-windows', 'archivos-windows-badge',  allResults, ['TEMP_FILES', 'FORENSE', 'INYECCION', 'JAVA_INJECTION', 'JNA', 'RED', 'NETWORK_CONNECTIONS']);
        _renderTabFindings('settings-list',        'subnav-settings',         'settings-badge',          allResults, ['DATE_CHANGES', 'EVASION', 'PERSISTENCIA', 'DNS_CACHE', 'VPN']);

    } catch (error) {
        console.error('Error cargando detalles:', error);
        alert('Error al cargar detalles del escaneo: ' + error.message);
    }
}

// ── File Activity Table (Explore > Logs tab) ────────────────────────────────
let _fileActivityAll = [];
let _exploreActionFilter = 'all';   // 'all' | 'deleted' | 'executed' | 'modified' | 'created'

function _resolveActivityAction(r) {
    let action = (r.extra && r.extra.action) || '';
    if (!action && r.issue_type) {
        const it = String(r.issue_type).toLowerCase();
        if (it.startsWith('file_')) action = it.slice(5);
        else action = it;
    }
    return action || 'deleted';
}

function _renderFileActivityTable(results) {
    const items = results.filter(r => (r.issue_category || '').toUpperCase() === 'FILE_ACTIVITY');
    _fileActivityAll = items.slice().sort((a, b) => {
        const ta = (a.extra && a.extra.ts) || 0;
        const tb = (b.extra && b.extra.ts) || 0;
        return tb - ta;
    });

    if (items.length > 0) {
        const eb = document.getElementById('subnav-explore');
        if (eb) eb.style.display = '';
    }

    const logsCount = document.getElementById('explore-logs-count');
    if (logsCount) logsCount.textContent = items.length;

    // Counts por acción para los chips
    const counts = { all: _fileActivityAll.length, deleted: 0, executed: 0, modified: 0, created: 0 };
    for (const r of _fileActivityAll) {
        const a = _resolveActivityAction(r);
        if (counts[a] !== undefined) counts[a]++;
    }
    for (const k of ['all', 'deleted', 'executed', 'modified', 'created']) {
        const el = document.getElementById('chip-count-' + k);
        if (el) el.textContent = counts[k] || 0;
    }

    // Reset filter al cargar un nuevo scan
    _exploreActionFilter = 'all';
    _highlightActionChip('all');
    filterExploreTable();
}

function _highlightActionChip(action) {
    const chips = document.querySelectorAll('#explore-action-chips .action-chip');
    chips.forEach(btn => {
        const isActive = btn.getAttribute('data-action') === action;
        btn.classList.toggle('active', isActive);
        btn.style.background = isActive ? 'var(--accent)' : 'var(--bg-t)';
        btn.style.color      = isActive ? '#fff' : 'var(--text-m)';
        const cnt = btn.querySelector('.chip-count');
        if (cnt) {
            cnt.style.background = isActive ? 'rgba(255,255,255,.25)' : 'var(--bg)';
            cnt.style.border     = isActive ? 'none' : '1px solid var(--border)';
        }
    });
}

function filterExploreAction(action) {
    _exploreActionFilter = action || 'all';
    _highlightActionChip(_exploreActionFilter);
    filterExploreTable();
}

function _drawFileActivityTable(items) {
    const tbody = document.getElementById('file-activity-body');
    if (!tbody) return;
    if (items.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="3" style="padding:0;">
                <div class="argus-empty">
                    <div class="argus-empty__art">
                        <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%">
                            <circle cx="32" cy="32" r="24"/>
                            <path d="M32 18v14l10 6"/>
                        </svg>
                    </div>
                    <div class="argus-empty__title">Sin actividad de archivos</div>
                    <div class="argus-empty__desc">No se registró actividad desde el último arranque del sistema. Si el scan se hizo justo después de reiniciar, esto es esperado.</div>
                </div>
            </td></tr>`;
        return;
    }
    const ACTION_CFG = {
        'deleted': { label: 'Deleted File', bg: '#ef4444', icon: '🗑' },
        'executed':{ label: 'Executed File', bg: '#8b5cf6', icon: '▶' },
        'created': { label: 'Created File', bg: '#22c55e', icon: '📄' },
        'modified':{ label: 'Modified File', bg: '#f59e0b', icon: '✏️' },
    };
    tbody.innerHTML = items.map((r, i) => {
        const action = _resolveActivityAction(r);
        const cfg  = ACTION_CFG[action] || ACTION_CFG['deleted'];
        const ts   = (r.extra && r.extra.timestamp) || '';
        const path = (r.issue_path || r.issue_name || '').slice(0, 200);
        const base = path.split(/[\\/]/).pop() || path;
        const dir  = path.length > base.length ? path.slice(0, path.length - base.length - 1) : '';
        const rowBg = i % 2 === 0 ? 'var(--bg-card)' : 'var(--bg)';
        return `<tr style="background:${rowBg};border-bottom:1px solid var(--border);" title="${path}">
            <td style="padding:8px 14px;white-space:nowrap;">
                <span style="display:inline-flex;align-items:center;gap:5px;background:${cfg.bg};color:#fff;border-radius:5px;padding:3px 8px;font-size:11px;font-weight:600;">
                    ${cfg.icon} ${cfg.label}
                </span>
            </td>
            <td style="padding:8px 14px;max-width:520px;overflow:hidden;">
                <span style="color:var(--text-d);font-size:11px;">${dir ? dir + '/' : ''}</span><span style="color:var(--text);font-weight:600;font-size:12px;">${base}</span>
            </td>
            <td style="padding:8px 14px;text-align:right;color:var(--text-d);font-size:11px;white-space:nowrap;">${ts}</td>
        </tr>`;
    }).join('');
}

function filterExploreTable() {
    const inputEl = document.getElementById('explore-search');
    const q = _normalize(inputEl && inputEl.value || '');
    let pool = _fileActivityAll;
    if (_exploreActionFilter && _exploreActionFilter !== 'all') {
        pool = pool.filter(r => _resolveActivityAction(r) === _exploreActionFilter);
    }
    const filtered = q ? pool.filter(r =>
        _normalize(r.issue_path).includes(q) ||
        _normalize(r.issue_name).includes(q) ||
        _normalize(_resolveActivityAction(r)).includes(q)
    ) : pool;
    _drawFileActivityTable(filtered);
}

function switchExploreTab(tab) {
    const isLogs = tab === 'logs';
    document.getElementById('explore-panel-logs').style.display  = isLogs ? '' : 'none';
    document.getElementById('explore-panel-files').style.display = isLogs ? 'none' : '';
    const btnL = document.getElementById('explore-tab-logs');
    const btnF = document.getElementById('explore-tab-files');
    if (btnL) { btnL.style.background = isLogs ? 'var(--accent)' : 'var(--bg-t)'; btnL.style.color = isLogs ? '#fff' : 'var(--text-m)'; }
    if (btnF) { btnF.style.background = isLogs ? 'var(--bg-t)' : 'var(--accent)'; btnF.style.color = isLogs ? 'var(--text-m)' : '#fff'; }
}

function _renderTabFindings(listId, btnId, badgeId, results, categories) {
    const cats = new Set(categories.map(c => c.toUpperCase()));
    const items = results.filter(r => cats.has((r.issue_category || '').toUpperCase()));
    const btn = document.getElementById(btnId);
    if (btn) btn.style.display = items.length > 0 ? '' : 'none';
    const badge = document.getElementById(badgeId);
    if (badge) {
        const hot = items.filter(r => r.alert_level === 'CRITICAL' || r.alert_level === 'SOSPECHOSO').length;
        if (hot > 0) { badge.textContent = hot; badge.style.display = ''; }
        else badge.style.display = 'none';
    }
    const list = document.getElementById(listId);
    if (!list) return;
    if (items.length === 0) {
        list.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin hallazgos en esta categoría.</p>';
        return;
    }
    list.innerHTML = items.map(r => {
        const isCrit  = r.alert_level === 'CRITICAL';
        const isMid   = r.alert_level === 'SOSPECHOSO';
        const accent  = isCrit ? '#ef4444' : isMid ? '#f59e0b' : '#6b7280';
        const bg      = isCrit ? 'rgba(239,68,68,0.05)' : isMid ? 'rgba(245,158,11,0.04)' : 'rgba(107,114,128,0.03)';
        const dot     = isCrit ? '🔴' : isMid ? '🟠' : '🔵';
        const name    = (r.issue_name || 'Hallazgo').slice(0, 120);
        const path    = r.issue_path || '';
        const trunc   = path.length > 90 ? '…' + path.slice(-87) : path;
        const cat     = _getCategoryLabel(r.issue_category || '');
        return `<div style="background:${bg};border:1px solid ${accent}33;border-left:3px solid ${accent};border-radius:8px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px;overflow:hidden;">
            <span style="font-size:14px;flex-shrink:0;margin-top:1px;">${dot}</span>
            <div style="flex:1;min-width:0;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);display:flex;align-items:center;gap:6px;flex-wrap:nowrap;min-width:0;overflow:hidden;">
                    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${name}</span>
                    ${cat ? `<span style="font-size:10px;color:var(--text-d);background:var(--bg-t);border:1px solid var(--border-m);padding:1px 6px;border-radius:4px;flex-shrink:0;white-space:nowrap;">${cat}</span>` : ''}
                </div>
                ${trunc ? `<div style="font-size:11px;color:var(--text-d);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${path}">${trunc}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

// Manejo de subpáginas
function setupSubpageNavigation() {
    const subnavItems = document.querySelectorAll('.subnav-item');
    subnavItems.forEach(item => {
        item.addEventListener('click', () => {
            const subpage = item.dataset.subpage;

            subnavItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            document.querySelectorAll('.subpage-content').forEach(page => {
                page.classList.remove('active');
            });

            const targetPage = document.getElementById(`subpage-${subpage}`);
            if (targetPage) targetPage.classList.add('active');

            // Cargar notas cuando se abre esa pestaña
            if (subpage === 'notas' && currentScanId) {
                loadScanNotes(currentScanId);
            }
            // Mostrar captura cuando se abre esa pestaña
            if (subpage === 'captura-pantalla') {
                renderScreenshot(_currentScanData);
            }
            // Cargar desglose del score
            if (subpage === 'detecciones-personalizadas' && currentScanId) {
                loadScoreBreakdown(currentScanId);
            }
        });
    });
}

// ============================================================
// SCORE BREAKDOWN (P3 #18 — SHAP-style)
// ============================================================

async function loadScoreBreakdown(scanId) {
    const container = document.getElementById('score-breakdown-container');
    if (!container) return;
    container.innerHTML = '<div class="loading-cell">Cargando desglose...</div>';
    try {
        const res  = await fetch(`/api/scans/${scanId}/score_breakdown`);
        const data = await res.json();
        if (data.error) { container.innerHTML = `<div class="loading-cell" style="color:#ef4444">${data.error}</div>`; return; }
        const breakdown = data.breakdown || [];
        const score     = data.risk_score || 0;
        const scoreColor = score >= 70 ? '#ef4444' : score >= 30 ? '#f59e0b' : '#22c55e';

        if (!breakdown.length) {
            container.innerHTML = '<div class="loading-cell">No se encontraron factores de riesgo.</div>';
            return;
        }
        const maxPts = Math.max(...breakdown.map(b => b.points), 1);
        container.innerHTML = `
            <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px;">
                <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;">
                    <div style="font-size:42px;font-weight:900;color:${scoreColor};">${score}</div>
                    <div>
                        <div style="font-size:13px;font-weight:700;color:var(--text);">Risk Score Total</div>
                        <div style="font-size:11px;color:var(--text-muted);">Calculado de ${breakdown.length} factores</div>
                        ${data.confidence_interval && data.confidence_interval.margin > 2
                            ? `<div style="font-size:11px;color:#a855f7;margin-top:4px;">
                                IC 95%: ${Math.round(data.confidence_interval.low)}–${Math.round(data.confidence_interval.high)}
                                ${data.needs_manual_review ? ' · <strong>⚠ Revisión recomendada</strong>' : ''}
                               </div>`
                            : ''}
                    </div>
                </div>
                ${breakdown.map(b => `
                    <div style="margin-bottom:12px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                            <span style="font-size:12px;color:var(--text);flex:1;margin-right:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(b.source)}">${escapeHtml(b.source)}</span>
                            <span style="font-size:13px;font-weight:700;color:${scoreColor};min-width:36px;text-align:right;">+${b.points}</span>
                        </div>
                        <div style="background:var(--bg);border-radius:4px;height:6px;overflow:hidden;">
                            <div style="background:${scoreColor};height:100%;width:${Math.round(b.points/maxPts*100)}%;border-radius:4px;transition:width 0.4s;"></div>
                        </div>
                        <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">${escapeHtml(b.reason || '')}</div>
                    </div>
                `).join('')}
            </div>`;
    } catch (e) {
        container.innerHTML = `<div class="loading-cell" style="color:#ef4444">Error: ${e.message}</div>`;
    }
}

// ============================================================
// NOTAS DE ESCANEO
// ============================================================

async function loadScanNotes(scanId) {
    const container = document.getElementById('scan-notes-list');
    if (!container) return;
    container.innerHTML = '<div style="color:var(--text-d);font-size:13px;">Cargando notas...</div>';
    try {
        const res  = await fetch(`/api/scans/${scanId}/notes`);
        const data = await res.json();
        const notes = data.notes || [];
        if (notes.length === 0) {
            container.innerHTML = '<div style="color:var(--text-d);font-size:13px;padding:8px 0;">Aún no hay notas para este escaneo.</div>';
            return;
        }
        container.innerHTML = notes.map(n => `
            <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-size:12px;font-weight:700;color:var(--accent);">${escapeHtml(n.author || '?')}</span>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="font-size:11px;color:var(--text-d);">${formatDate(n.created_at)}</span>
                        <button onclick="deleteScanNote(${scanId},${n.id},this)"
                            style="background:none;border:none;cursor:pointer;color:var(--text-d);font-size:12px;padding:2px 6px;border-radius:4px;transition:color .15s;"
                            title="Eliminar nota">✕</button>
                    </div>
                </div>
                <div style="font-size:13px;color:var(--text-s);white-space:pre-wrap;line-height:1.6;">${escapeHtml(n.body || '')}</div>
            </div>`).join('');
    } catch (e) {
        container.innerHTML = '<div style="color:#ef4444;font-size:13px;">Error cargando notas</div>';
    }
}

async function submitScanNote() {
    if (!currentScanId) return;
    const textarea = document.getElementById('new-note-body');
    const body = (textarea?.value || '').trim();
    if (!body) return;
    try {
        const res = await fetch(`/api/scans/${currentScanId}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ body }),
        });
        if (res.ok) {
            textarea.value = '';
            loadScanNotes(currentScanId);
        }
    } catch(e) { console.error('Error al agregar nota:', e); }
}

async function deleteScanNote(scanId, noteId, btn) {
    btn.disabled = true;
    try {
        const res = await fetch(`/api/scans/${scanId}/notes/${noteId}`, { method: 'DELETE' });
        if (res.ok) loadScanNotes(scanId);
        else btn.disabled = false;
    } catch(e) { btn.disabled = false; }
}

async function viewPlayerProfile(machineName) {
    if (!machineName) return;
    // Cargar el scan más reciente de ese jugador y abrir en "Escaneos Previos"
    try {
        const res  = await fetch(`/api/scans?machine_name=${encodeURIComponent(machineName)}&limit=1`);
        const data = await res.json();
        if (data.scans && data.scans.length > 0) {
            await viewScanDetails(data.scans[0].id);
            // Cambiar a la pestaña de escaneos previos
            const btn = document.querySelector('.subnav-item[data-subpage="escaneos-previos"]');
            if (btn) btn.click();
        }
    } catch(e) { console.error('Error cargando perfil de jugador:', e); }
}

async function loadPreviousScans(machineName) {
    try {
        const container = document.getElementById('previous-scans-list');
        if (container) {
            container.innerHTML = `<div class="skel-issues">${
                Array(4).fill(0).map(() => `
                <div class="skel-row" style="border-bottom:1px solid var(--border);padding:12px 0;">
                    <div class="skel-text">
                        <div class="skel skel-line w-60"></div>
                        <div class="skel skel-line w-40"></div>
                    </div>
                    <div class="skel skel-badge-sm" style="width:72px;height:22px;"></div>
                </div>`).join('')
            }</div>`;
        }
        const response = await fetch(`/api/scans?machine_name=${encodeURIComponent(machineName)}&limit=200`);
        const data = await response.json();

        if (!container) return;

        const allScans  = data.scans || [];
        const prevScans = allScans.filter(s => s.id !== currentScanId);
        const current   = allScans.find(s => s.id === currentScanId);

        // P5 #21 — Reputación del jugador
        _renderPlayerReputation(machineName, allScans);

        if (prevScans.length > 0) {
            // ── Risk score trend chart ───────────────────────────────
            const trendWrap = document.getElementById('risk-trend-wrap');
            const trendCanvas = document.getElementById('risk-trend-chart');
            if (trendWrap && trendCanvas && allScans.length >= 2) {
                trendWrap.style.display = 'block';
                const sorted = [...allScans].sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
                const labels = sorted.map(s => s.started_at ? s.started_at.toString().slice(5,10) : '?');
                const scores = sorted.map(s => s.risk_score || 0);
                const colors = scores.map(v => v >= 70 ? '#ef4444' : v >= 30 ? '#f59e0b' : '#10b981');
                if (window._riskTrendChart) window._riskTrendChart.destroy();
                window._riskTrendChart = new Chart(trendCanvas, {
                    type: 'line',
                    data: {
                        labels,
                        datasets: [{
                            data: scores,
                            borderColor: '#8b5cf6',
                            backgroundColor: 'rgba(184,115,51,0.10)',
                            pointBackgroundColor: colors,
                            pointRadius: 5,
                            tension: 0.3,
                            fill: true,
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false }, tooltip: {
                            callbacks: { label: ctx => ` Risk: ${ctx.parsed.y}` }
                        }},
                        scales: {
                            y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.05)' },
                                 ticks: { color: '#6b7280', font: { size: 10 } } },
                            x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 10 } } }
                        }
                    }
                });
            }
            // ────────────────────────────────────────────────────────
            // Estadísticas de historial
            const totalScans = allScans.length;
            const withHacks  = allScans.filter(s => s.verdict === 'hack').length;
            const clean      = allScans.filter(s => s.verdict === 'clean').length;

            const statsHtml = `
                <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px;">
                    <div style="background:var(--bg-s);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center;">
                        <div style="font-size:22px;font-weight:800;color:var(--accent);">${totalScans}</div>
                        <div style="font-size:11px;color:var(--text-d);">Escaneos totales</div>
                    </div>
                    <div style="background:var(--bg-s);border:1px solid rgba(220,38,38,0.3);border-radius:10px;padding:12px;text-align:center;">
                        <div style="font-size:22px;font-weight:800;color:#ef4444;">${withHacks}</div>
                        <div style="font-size:11px;color:var(--text-d);">Con hacks</div>
                    </div>
                    <div style="background:var(--bg-s);border:1px solid rgba(16,185,129,0.3);border-radius:10px;padding:12px;text-align:center;">
                        <div style="font-size:22px;font-weight:800;color:#10b981;">${clean}</div>
                        <div style="font-size:11px;color:var(--text-d);">Limpios</div>
                    </div>
                </div>`;

            // Render stats header then scans (virtual scroll when >50)
            container.innerHTML = statsHtml;
            const listEl = document.createElement('div');
            if (prevScans.length > 50) {
                listEl.style.maxHeight = '420px';
            }
            container.appendChild(listEl);

            const _renderScanItem = (scan, i) => {
                const prev       = prevScans[i + 1];
                const issuesDiff = prev != null ? (scan.issues_found || 0) - (prev.issues_found || 0) : null;
                const diffBadge  = issuesDiff === null ? '' :
                    issuesDiff > 0 ? `<span style="color:#ef4444;font-size:11px;">▲ ${issuesDiff}</span>` :
                    issuesDiff < 0 ? `<span style="color:#10b981;font-size:11px;">▼ ${Math.abs(issuesDiff)}</span>` :
                                     `<span style="color:var(--text-d);font-size:11px;">= igual</span>`;
                const verdictBadge = scan.verdict === 'hack'  ? '<span style="font-size:10px;font-weight:700;color:#ef4444;background:rgba(220,38,38,0.12);padding:1px 6px;border-radius:6px;">HACKS</span>' :
                                     scan.verdict === 'clean' ? '<span style="font-size:10px;font-weight:700;color:#10b981;background:rgba(16,185,129,0.12);padding:1px 6px;border-radius:6px;">LIMPIO</span>' : '';
                return `<div class="previous-scan-item" onclick="viewScanDetails(${scan.id})" style="cursor:pointer;">
                        <div class="previous-scan-header">
                            <span class="previous-scan-id">Escaneo #${scan.id} ${verdictBadge}</span>
                            <span class="previous-scan-date">${formatDate(scan.started_at)}</span>
                        </div>
                        <div class="previous-scan-stats">
                            <span class="previous-scan-stat"><strong>${scan.issues_found || 0}</strong> issues ${diffBadge}</span>
                            <span class="previous-scan-stat"><strong>${scan.total_files_scanned || 0}</strong> archivos</span>
                            ${scan.risk_score != null ? `<span class="previous-scan-stat" style="color:${scan.risk_score>=70?'#ef4444':scan.risk_score>=30?'#f59e0b':'#10b981'};font-weight:700;">Risk ${scan.risk_score}</span>` : ''}
                            <button onclick="event.stopPropagation();compareScanWith(${scan.id})"
                                style="margin-left:auto;font-size:10px;padding:2px 8px;background:rgba(184,115,51,0.15);border:1px solid rgba(184,115,51,0.4);color:var(--accent);border-radius:6px;cursor:pointer;">Comparar</button>
                            <button onclick="event.stopPropagation();markScanAsBaseline(${scan.id})"
                                style="font-size:10px;padding:2px 8px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.35);color:#10b981;border-radius:6px;cursor:pointer;">Baseline</button>
                            <button onclick="event.stopPropagation();openScanTrend(${scan.id})"
                                style="font-size:10px;padding:2px 8px;background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.35);color:#60a5fa;border-radius:6px;cursor:pointer;">Trend</button>
                        </div></div>`;
            };

            if (prevScans.length > 50) {
                _VirtualList(listEl, prevScans, _renderScanItem, { rowHeight: 70 });
            } else {
                listEl.innerHTML = prevScans.map(_renderScanItem).join('');
            }
        } else {
            container.innerHTML = `
                <div class="argus-empty argus-empty--v2">
                    <div class="argus-empty-art">🆕</div>
                    <div class="argus-empty-title">Primer escaneo de esta máquina</div>
                    <div class="argus-empty-msg">No hay escaneos anteriores registrados para este machine_id. Los próximos scans aparecerán aquí para comparar evolución.</div>
                </div>`;
        }
    } catch (error) {
        console.error('Error cargando escaneos previos:', error);
        const container = document.getElementById('previous-scans-list');
        if (container) {
            container.innerHTML = '<div class="loading-cell">Error al cargar escaneos previos.</div>';
        }
    }
}

async function markScanAsBaseline(scanId) {
    try {
        const res = await fetch(`/api/scans/${scanId}/set-baseline`, { method: 'POST' });
        const d = await res.json();
        if (!res.ok || !d.success) throw new Error(d.error || 'No se pudo marcar baseline');
        showToast(`Scan #${scanId} marcado como baseline`, 'success');
        loadPreviousScans();
    } catch (e) {
        showToast(`Error baseline: ${e.message}`, 'error');
    }
}

function renderScanDiff(diff) {
    const ALERT_COLOR = { CRITICAL:'#ef4444', HIGH:'#ef4444', SOSPECHOSO:'#f59e0b', MUY_SOSPECHOSO:'#ea580c', POCO_SOSPECHOSO:'#6366f1' };
    const riskDelta = diff.risk_delta || 0;
    const riskColor = riskDelta > 0 ? '#ef4444' : riskDelta < 0 ? '#10b981' : 'var(--text-m)';
    const riskSign = riskDelta > 0 ? '+' : '';
    const renderIssueList = (items, bgColor) => (items || []).length === 0
        ? `<p style="color:var(--text-d);font-size:12px;margin:0;">Ninguno</p>`
        : (items || []).map(f => `
            <div style="padding:6px 10px;border-radius:6px;background:${bgColor};margin-bottom:4px;font-size:12px;">
                <span style="color:${ALERT_COLOR[f.alert]||'var(--text-m)'};font-weight:700;margin-right:6px;">${f.alert||''}</span>
                <span style="color:var(--text);">${f.name||f.type}</span>
                <span style="float:right;color:var(--text-d);">${Math.round((f.confidence||0)*100)}%</span>
            </div>`).join('');
    return `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
            <div style="background:var(--bg-s);border-radius:8px;padding:14px;">
                <div style="font-size:11px;color:var(--text-d);margin-bottom:4px;">ESCANEO BASE</div>
                <div style="font-weight:700;font-size:15px;">Scan #${diff.scan_a.id}</div>
                <div style="font-size:12px;color:var(--text-m);">${diff.scan_a.date}</div>
                <div style="font-size:13px;margin-top:6px;">Risk: <strong>${diff.scan_a.risk}</strong></div>
            </div>
            <div style="background:var(--bg-s);border-radius:8px;padding:14px;">
                <div style="font-size:11px;color:var(--text-d);margin-bottom:4px;">ESCANEO COMPARADO</div>
                <div style="font-weight:700;font-size:15px;">Scan #${diff.scan_b.id}</div>
                <div style="font-size:12px;color:var(--text-m);">${diff.scan_b.date}</div>
                <div style="font-size:13px;margin-top:6px;">Risk: <strong>${diff.scan_b.risk}</strong>
                    <span style="color:${riskColor};margin-left:8px;font-weight:700;">${riskSign}${riskDelta} pts</span>
                </div>
            </div>
        </div>
        ${diff.verdict_change ? `<div style="background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.4);border-radius:8px;padding:10px;margin-bottom:16px;font-size:13px;color:#f59e0b;">
            Veredicto cambió: <strong>${diff.scan_a.verdict.toUpperCase()}</strong> → <strong>${diff.scan_b.verdict.toUpperCase()}</strong>
        </div>` : ''}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;">
            <div><div style="font-size:13px;font-weight:700;color:#22c55e;margin-bottom:8px;">Nuevos (${diff.summary.new_count})</div>${renderIssueList(diff.new_findings, 'rgba(34,197,94,0.08)')}</div>
            <div><div style="font-size:13px;font-weight:700;color:#ef4444;margin-bottom:8px;">Resueltos (${diff.summary.resolved_count})</div>${renderIssueList(diff.resolved_findings, 'rgba(239,68,68,0.08)')}</div>
        </div>
        <div><div style="font-size:13px;font-weight:700;color:#f59e0b;margin-bottom:8px;">Persistentes (${diff.summary.persistent_count})</div>${renderIssueList(diff.persistent_findings, 'rgba(245,158,11,0.08)')}</div>
    `;
}

async function compareScanWith(scanIdB) {
    if (!currentScanId) return;
    const modal = document.getElementById('compare-modal');
    const body  = document.getElementById('compare-modal-body');
    if (!modal || !body) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-m);">Cargando comparación...</div>';
    modal.style.display = 'flex';
    try {
        const res  = await fetch(`/api/scans/compare?scan1=${encodeURIComponent(currentScanId)}&scan2=${encodeURIComponent(scanIdB)}`);
        const diff = await res.json();
        if (diff.error) { body.innerHTML = `<p style="color:#ef4444">${diff.error}</p>`; return; }
        body.innerHTML = renderScanDiff(diff);
    } catch (e) {
        body.innerHTML = `<p style="color:#ef4444">Error: ${e.message}</p>`;
    }
}

async function openScanTrend(scanId) {
    try {
        const s = await fetch(`/api/scans/${scanId}`);
        const sd = await s.json();
        const host = sd?.scan?.machine_name || sd?.scan?.machine_id || '';
        const user = sd?.scan?.minecraft_username || '';
        if (!host && !user) throw new Error('No hay host/user para timeline');
        const q = new URLSearchParams();
        if (host) q.set('host', host);
        if (user) q.set('user', user);
        q.set('limit', '30');
        const r = await fetch(`/api/scans/timeline?${q.toString()}`);
        const d = await r.json();
        if (!r.ok || !d.success) throw new Error(d.error || 'No se pudo cargar timeline');
        const modal = document.getElementById('compare-modal');
        const body = document.getElementById('compare-modal-body');
        if (!modal || !body) return;
        modal.style.display = 'flex';
        body.innerHTML = `<div style="height:280px"><canvas id="dual-scan-trend-chart"></canvas></div>`;
        const ctx = document.getElementById('dual-scan-trend-chart');
        if (!ctx) return;
        const labels = (d.timeline || []).map(x => new Date(x.timestamp).toLocaleString());
        const values = (d.timeline || []).map(x => Number(x.issues_found || 0));
        if (window._dualTrendChart) window._dualTrendChart.destroy();
        window._dualTrendChart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets: [{ label: 'Issues', data: values, borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,.18)', tension: .25, fill: true }] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (c) => {
                                const row = (d.timeline || [])[c.dataIndex] || {};
                                return `Issues: ${row.issues_found} · Risk: ${row.risk_score} · Verdict: ${row.verdict}`;
                            }
                        }
                    }
                }
            }
        });
    } catch (e) {
        showToast(`Trend error: ${e.message}`, 'error');
    }
}

function updateSeverityChart(stats) {
    const ctx = document.getElementById('severity-chart');
    if (!ctx) return;
    
    // Destruir gráfico anterior si existe
    if (severityChart) {
        severityChart.destroy();
    }
    
    const total = stats.clean + stats.alert + stats.severe;
    
    // Si no hay datos, mostrar gráfico vacío
    if (total === 0) {
        severityChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Sin detecciones'],
                datasets: [{
                    data: [1],
                    backgroundColor: ['#1e293b'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                },
                cutout: '70%'
            }
        });
        return;
    }
    
    severityChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Limpio', 'Alerta', 'Severo'],
            datasets: [{
                data: [stats.clean, stats.alert, stats.severe],
                backgroundColor: [
                    '#10b981', // Verde para limpio
                    '#f59e0b', // Amarillo para alerta
                    '#ef4444'  // Rojo para severo
                ],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    },
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: {
                        size: 14,
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 13
                    }
                }
            },
            cutout: '70%',
            animation: {
                animateRotate: true,
                duration: 1000
            }
        }
    });
}

// Función para volver a la lista de escaneos
document.getElementById('back-to-scans-btn')?.addEventListener('click', () => {
    document.getElementById('issues-detail-section').style.display = 'none';
    document.getElementById('issues-detail-section').classList.remove('active');
    document.getElementById('resultados-section').classList.add('active');
    loadScans();
});

// Función para descargar reporte HTML
document.getElementById('download-report-btn')?.addEventListener('click', async () => {
    if (!currentScanId) {
        alert('No hay escaneo seleccionado');
        return;
    }
    
    try {
        const response = await fetch(`/api/scans/${currentScanId}/report-html`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ASPERS_Report_Scan_${currentScanId}_${new Date().toISOString().split('T')[0]}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            alert('✅ Reporte HTML descargado exitosamente. Puedes compartirlo con el staff superior.');
        } else {
            throw new Error('Error al generar reporte');
        }
    } catch (error) {
        alert('Error al descargar reporte: ' + error.message);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar navegación de subpáginas
    setupSubpageNavigation();
});

// ============================================================
// APRENDIZAJE DE IA
// ============================================================

async function loadLearningStats() {
    try {
        const data = await fetch('/api/learning-stats').then(r => r.json());

        // Generar App stats chips
        const setChip = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val ?? '—';
        };
        setChip('ga-patterns-val',   data.patterns_count ?? '—');
        setChip('ga-hashes-val',     data.hashes_count   ?? '—');
        setChip('ga-autolabels-val', data.auto_labels     ?? '—');

        const rfEl = document.getElementById('ga-ai-status-val');
        if (rfEl) {
            if (data.rf_available) {
                rfEl.textContent = `${data.rf_trained_on ?? 0} muestras`;
                rfEl.style.color = '#34d399';
            } else {
                rfEl.textContent = 'Sin entrenar';
                rfEl.style.color = 'var(--text-m)';
            }
        }

        const isoEl = document.getElementById('ga-iso-status');
        if (isoEl) isoEl.textContent = data.iso_available ? `${data.iso_trained_on ?? 0} scans` : 'Sin datos';

    } catch (e) {
        console.error('Error cargando learning stats:', e);
    }
}

async function mlCluster() {
    const res = document.getElementById('ml-cluster-result');
    if (!res) return;
    res.style.display = 'block';
    res.style.color = 'var(--text-muted)';
    res.textContent = 'Analizando clusters...';
    try {
        const r = await fetch('/api/ml/cluster', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({days: 30, n_clusters: 5})
        });
        const d = await r.json();
        if (d.error) { res.style.color='#ef4444'; res.textContent=d.error; return; }
        const alertColor = d.alert ? '#ef4444' : '#22c55e';
        res.style.color = alertColor;
        let html = `<strong>${d.alert ? '⚠ ' : '✅ '}${d.n_clusters} clusters</strong> en ${d.total_scans} scans (últimos 30 días)<br>`;
        if (d.alert_message) html += `<span style="color:#ef4444">${d.alert_message}</span><br>`;
        html += '<br>';
        (d.clusters || []).forEach(c => {
            const riskColor = c.avg_risk >= 70 ? '#ef4444' : c.avg_risk >= 30 ? '#f59e0b' : '#22c55e';
            html += `<div style="display:flex;gap:12px;align-items:center;margin-bottom:6px;padding:6px 10px;background:var(--bg);border-radius:6px;">
                <span style="font-weight:700;color:${riskColor};">Cluster ${c.cluster_id}</span>
                <span>${c.size} scans</span>
                <span>Risk avg: <strong style="color:${riskColor}">${c.avg_risk}</strong></span>
                <span>Issues avg: ${c.avg_issues}</span>
                ${c.alert ? '<span style="color:#ef4444;font-weight:700;">⚠ ALTO RIESGO</span>' : ''}
            </div>`;
        });
        res.innerHTML = html;
    } catch (e) {
        res.style.color = '#ef4444';
        res.textContent = `Error: ${e.message}`;
    }
}

async function loadCoordinatedCheating() {
    const res = document.getElementById('coord-cheating-result');
    const daysEl = document.getElementById('coord-days-select');
    if (!res) return;
    const days = daysEl ? parseInt(daysEl.value) : 30;
    res.innerHTML = '<span style="color:var(--text-d);">Analizando...</span>';
    try {
        const r = await fetch(`/api/ml/coordinated-cheating?days=${days}&min_players=2`);
        const d = await r.json();
        if (d.error) { res.innerHTML = `<span style="color:#ef4444">${d.error}</span>`; return; }
        const clusters = d.clusters || [];
        if (clusters.length === 0) {
            res.innerHTML = '<span style="color:#10b981;">✅ No se detectaron patrones de cheating coordinado.</span>';
            return;
        }
        let html = `<div style="color:#f87171;font-weight:700;margin-bottom:10px;">⚠️ ${clusters.length} grupo(s) detectado(s)</div>`;
        clusters.forEach(c => {
            const players = c.players || [];
            const uniquePlayers = [...new Map(players.map(p => [p.machine_name, p])).values()];
            html += `<div style="padding:10px 12px;background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.2);border-radius:8px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
                    <span style="font-weight:700;color:#f87171;">${c.issue_type}</span>
                    <span style="font-size:11px;color:var(--text-d);">${c.date}</span>
                </div>
                <div style="font-size:11px;color:var(--text-m);margin-bottom:6px;">${c.player_count} jugador(es) con este hack el mismo día</div>
                <div style="display:flex;flex-wrap:wrap;gap:4px;">
                    ${uniquePlayers.map(p =>
                        `<span onclick="viewScanDetails(${p.scan_id})" style="cursor:pointer;font-size:10px;padding:2px 7px;border-radius:10px;background:rgba(239,68,68,0.1);color:#fca5a5;border:1px solid rgba(239,68,68,0.25);">${p.machine_name}</span>`
                    ).join('')}
                </div>
            </div>`;
        });
        res.innerHTML = html;
    } catch(e) {
        res.innerHTML = `<span style="color:#ef4444">Error: ${e.message}</span>`;
    }
}

async function mlTrain() {
    const btn = document.getElementById('ml-train-btn');
    const res = document.getElementById('ml-train-result');
    if (!btn || !res) return;
    btn.disabled = true;
    btn.textContent = 'Entrenando...';
    res.style.display = 'none';
    try {
        const r = await fetch('/api/ml/train', {method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}'});
        const d = await r.json();
        res.style.display = 'block';
        if (d.trained) {
            res.style.background = 'rgba(34,197,94,0.1)';
            res.style.border = '1px solid rgba(34,197,94,0.3)';
            res.style.color = '#22c55e';
            res.innerHTML = `✅ Entrenado: ${d.samples} muestras (${d.hack_count} hacks / ${d.clean_count} limpios) &nbsp;·&nbsp; Accuracy: ${(d.accuracy*100).toFixed(1)}%`;
        } else {
            res.style.background = 'rgba(239,68,68,0.1)';
            res.style.border = '1px solid rgba(239,68,68,0.3)';
            res.style.color = '#ef4444';
            res.innerHTML = `❌ ${d.error || 'Error desconocido'}`;
        }
        loadLearningStats();
    } catch (e) {
        res.style.display = 'block';
        res.style.color = '#ef4444';
        res.textContent = `Error: ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Entrenar ahora';
    }
}

async function loadLearnedPatterns() {
    try {
        const response = await fetch('/api/learned-patterns');
        const data = await response.json();
        
        const container = document.getElementById('patterns-list');
        if (data.patterns && data.patterns.length > 0) {
            container.innerHTML = data.patterns.map(pattern => `
                <div class="pattern-item">
                    <div class="pattern-header">
                        <strong>${pattern.value}</strong>
                        <span class="badge badge-${pattern.category === 'high_risk' ? 'danger' : pattern.category === 'medium_risk' ? 'warning' : 'info'}">
                            ${pattern.category}
                        </span>
                    </div>
                    <div class="pattern-details">
                        <span>Confianza: ${(pattern.confidence * 100).toFixed(0)}%</span>
                        <span>•</span>
                        <span>Aprendido ${pattern.learned_from_count} veces</span>
                        <span>•</span>
                        <span>${formatDate(pattern.first_learned_at)}</span>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="argus-empty argus-empty--v2">
                    <div class="argus-empty-art">🧠</div>
                    <div class="argus-empty-title">Sin patrones aprendidos todavía</div>
                    <div class="argus-empty-msg">Argus AI aún no tiene datos para inferir patrones de hack. Marca resultados como <b>HACK</b> en los veredictos para que el modelo aprenda y refine sus heurísticas.</div>
                </div>`;
        }
    } catch (error) {
        console.error('Error cargando patrones:', error);
    }
}

async function updateModel() {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Actualizar el modelo de IA de Argus?',
            body: 'Los clientes descargarán automáticamente los nuevos patrones al iniciar.\n\nNO es necesario recompilar el ejecutable.',
            ok: 'Actualizar modelo',
          })
        : Promise.resolve(confirm('¿Actualizar el modelo de IA de ASPERS Projects?\n\nLos clientes descargarán automáticamente los nuevos patrones al iniciar.\nNO es necesario recompilar el ejecutable.')));
    if (!ok) {
        return;
    }

    const btn = document.getElementById('update-model-btn');
    btn.disabled = true;
    btn.innerHTML = '<span>Actualizando...</span>';

    try {
        const response = await fetch('/api/update-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.success) {
            alert(`✅ Modelo actualizado exitosamente.\n\nVersión: ${data.version}\nPatrones: ${data.patterns_count}\nHashes: ${data.hashes_count}\n\nLos clientes descargarán automáticamente estos patrones al iniciar.\nNO es necesario recompilar el ejecutable.`);
            loadLearningStats();
            loadLearnedPatterns();
        } else {
            alert('Error al actualizar modelo: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        alert('Error al actualizar modelo: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Actualizar Modelo de IA</span><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 3L10 17M3 10L17 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    }
}

// ============================================================
// ADMIN: BORRAR SCANS DE PRUEBA
// ============================================================

async function purgeGarbageResults() {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: 'Purga de resultados basura',
            body: 'Eliminará TODOS los resultados basura de la BD completa (EXECUTED_DELETED, nombres binarios).\n\n¿Continuar?',
            ok: 'Purgar',
            danger: true,
          })
        : Promise.resolve(confirm('⚠️ Eliminará TODOS los resultados basura de la BD completa (EXECUTED_DELETED, nombres binarios).\n\n¿Continuar?')));
    if (!ok) return;
    const res = await fetch('/api/admin/purge-garbage-results', {method: 'POST', headers: {'Content-Type':'application/json'}});
    const d = await res.json();
    const el = document.getElementById('purge-result');
    if (el) el.textContent = d.error ? '❌ ' + d.error : '✅ ' + d.message;
}

async function deleteMachineScans() {
    const machineName = document.getElementById('scan-machine-name')?.textContent?.trim();
    if (!machineName || machineName === '-') {
        alert('No se encontró el nombre de la máquina.');
        return;
    }
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: 'Eliminar scans de máquina',
            body: `Esto eliminará TODOS los scans de "${machineName}" de la base de datos.\n\nÚsalo solo para limpiar scans de prueba propios.\n\n¿Continuar?`,
            ok: 'Eliminar scans',
            danger: true,
          })
        : Promise.resolve(confirm(`⚠️ Esto eliminará TODOS los scans de "${machineName}" de la base de datos.\n\nÚsalo solo para limpiar scans de prueba propios.\n\n¿Continuar?`)));
    if (!ok) return;

    try {
        const res = await fetch('/api/admin/scans/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({machine_name: machineName})
        });
        const d = await res.json();
        if (d.error) { alert('Error: ' + d.error); return; }
        alert(`✅ ${d.message}`);
        // Volver a la lista de scans
        document.querySelectorAll('.panel-section').forEach(s => { s.classList.remove('active'); s.style.display = 'none'; });
        const rs = document.getElementById('resultados-section');
        if (rs) { rs.classList.add('active'); rs.style.display = ''; }
        if (typeof loadScans === 'function') loadScans();
    } catch (e) {
        alert('Error de conexión: ' + e.message);
    }
}

// ============================================================
// UTILIDADES
// ============================================================

function exportScanCSV() {
    if (!currentScanId) return;
    window.open(`/api/scans/${currentScanId}/export/csv`, '_blank');
}

function exportScanPDF() {
    if (!currentScanId) return;
    window.open(`/api/scans/${currentScanId}/export/pdf`, '_blank');
}

function _parseUTC(s) {
    if (!s) return null;
    s = String(s).trim();
    if (/Z$|[+-]\d{2}:\d{2}$/.test(s)) return new Date(s);
    return new Date(s.replace(' ', 'T') + 'Z');
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = _parseUTC(dateString);
    if (!date || isNaN(date.getTime())) return String(dateString);
    return date.toLocaleString('es-ES');
}

function _normalize(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function formatDuration(seconds) {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(0);
    return `${minutes}m ${secs}s`;
}

// ============================================================
// DESCARGAR APLICACIÓN (SIN COMPILAR)
// ============================================================

async function downloadApp() {
    try {
        // Buscar el ejecutable más reciente
        const response = await fetch('/api/get-latest-exe');
        const data = await response.json();
        
        if (data.success && data.download_url) {
            // Iniciar descarga automática
            const downloadLink = document.createElement('a');
            downloadLink.href = data.download_url;
            downloadLink.download = data.filename;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
            
            alert(`✅ Descarga iniciada.\n\nArchivo: ${data.filename}\n\nEste ejecutable incluye todas las actualizaciones de IA descargadas automáticamente.`);
        } else {
            // Mensaje cuando no se encuentra el ejecutable
            const errorMsg = data.error || 'No se encontró el ejecutable compilado.';
            
            if (data.is_render) {
                // Mensaje específico para Render
                alert(`⚠️ ${errorMsg}`);
            } else {
                // Mensaje para local
                alert(`⚠️ ${errorMsg}\n\n` +
                      'El ejecutable debe estar en una de estas ubicaciones:\n' +
                      '• downloads/ArgusScanner.exe\n' +
                      '• source/dist/ArgusScanner.exe\n' +
                      '• ArgusScanner.exe (raíz del proyecto)\n\n' +
                      'Asegúrate de que el archivo .exe esté compilado.');
            }
        }
    } catch (error) {
        alert('Error al descargar aplicación: ' + error.message);
    }
}

// ============================================================
// COMPILAR APLICACIÓN (SOLO SI HAY CAMBIOS EN CÓDIGO)
// ============================================================

async function compileApp() {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Compilar nueva versión del ejecutable?',
            body: 'SOLO usa esto si hay cambios en el código del programa.\n\nLas actualizaciones de IA se descargan automáticamente sin necesidad de recompilar.\n\nEl proceso puede tardar varios minutos.',
            ok: 'Compilar',
            danger: true,
          })
        : Promise.resolve(confirm('¿Compilar nueva versión del ejecutable?\n\n⚠️ SOLO usa esto si hay cambios en el código del programa.\n\nLas actualizaciones de IA se descargan automáticamente sin necesidad de recompilar.\n\nEl proceso puede tardar varios minutos.')));
    if (!ok) {
        return;
    }

    const btn = document.getElementById('compile-app-btn');
    const statusDiv = document.getElementById('generation-status');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const logContainer = document.getElementById('generation-log');
    const logContent = document.getElementById('log-content');

    // Deshabilitar botón
    btn.disabled = true;
    btn.innerHTML = '<span>Compilando...</span>';

    // Mostrar progreso
    progressContainer.style.display = 'block';
    logContainer.style.display = 'block';
    logContent.innerHTML = '';
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<div class="status-indicator"><div class="status-dot" style="background: #3b82f6;"></div><span>Compilando ejecutable...</span></div>';

    try {
        const response = await fetch('/api/generate-app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            throw new Error('Error al iniciar compilación');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        
                        // Actualizar progreso
                        if (data.progress !== undefined) {
                            progressFill.style.width = `${data.progress}%`;
                            progressText.textContent = `${data.progress}%`;
                        }

                        // Agregar log
                        const logEntry = document.createElement('div');
                        logEntry.className = 'log-entry';
                        logEntry.textContent = data.step;
                        logContent.appendChild(logEntry);
                        logContent.scrollTop = logContent.scrollHeight;

                        // Verificar si hay error
                        if (data.error) {
                            statusDiv.innerHTML = `<div class="status-indicator"><div class="status-dot" style="background: #ef4444;"></div><span>Error en compilación</span></div>`;
                            btn.disabled = false;
                            btn.innerHTML = '<span>Compilar Ejecutable</span><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 3L10 17M3 10L17 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
                            return;
                        }

                        // Verificar si completó exitosamente
                        if (data.success && data.download_url) {
                            statusDiv.innerHTML = `<div class="status-indicator"><div class="status-dot" style="background: #22c55e;"></div><span>✅ Aplicación generada exitosamente</span></div>`;
                            
                            // Iniciar descarga automática
                            const downloadLink = document.createElement('a');
                            downloadLink.href = data.download_url;
                            downloadLink.download = data.filename;
                            document.body.appendChild(downloadLink);
                            downloadLink.click();
                            document.body.removeChild(downloadLink);

                            alert(`✅ Aplicación compilada exitosamente.\n\nArchivo: ${data.filename}\n\nLa descarga debería iniciarse automáticamente.`);
                            
                            btn.disabled = false;
                            btn.innerHTML = '<span>Compilar Ejecutable</span><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 3L10 17M3 10L17 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
                            return;
                        }
                    } catch (e) {
                        console.error('Error parseando datos:', e);
                    }
                }
            }
        }
    } catch (error) {
        alert('Error al compilar aplicación: ' + error.message);
        statusDiv.innerHTML = '<div class="status-indicator"><div class="status-dot" style="background: #ef4444;"></div><span>Error en compilación</span></div>';
        btn.disabled = false;
        btn.innerHTML = '<span>Compilar Ejecutable</span><svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M10 3L10 17M3 10L17 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
    }
}

// ============================================================
// ADMINISTRACIÓN (Solo para admins)
// ============================================================

function setupAdminListeners() {
    // Formulario de generación de token de REGISTRO (solo para admins)
    // NOTA: Los tokens de ESCANEO están en /api/tokens y pueden ser creados por cualquier usuario
    document.getElementById('registration-token-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const description = document.getElementById('reg-token-description').value;
        const expiresHours = parseInt(document.getElementById('reg-token-expires').value) || 24;
        
        try {
            // Usar endpoint correcto para tokens de REGISTRO (no de escaneo)
            const response = await fetch('/api/admin/registration-tokens', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    description: description,
                    expires_hours: expiresHours
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Mostrar token generado
                    document.getElementById('generated-registration-token').textContent = data.token;
                    document.getElementById('registration-token-result').style.display = 'block';
                    
                    // Resetear formulario
                    document.getElementById('registration-token-form').reset();
                    document.getElementById('reg-token-expires').value = 24;
                    
                    // Recargar lista de tokens
                    loadRegistrationTokens();
                } else {
                    alert('Error: ' + (data.error || 'Error desconocido'));
                }
            } else {
                const error = await response.json();
                alert('Error: ' + (error.error || 'Error al generar token'));
            }
        } catch (error) {
            alert('Error de conexión: ' + error.message);
        }
    });
    
    // Botón copiar token de registro
    document.getElementById('copy-registration-token-btn')?.addEventListener('click', async () => {
        const tokenElement = document.getElementById('generated-registration-token');
        const token = tokenElement?.textContent;
        
        if (!token) {
            alert('No hay token para copiar');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(token);
            const btn = document.getElementById('copy-registration-token-btn');
            const originalText = btn.textContent;
            btn.textContent = '✓ Copiado!';
            btn.style.background = '#22c55e';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (error) {
            // Fallback
            const textArea = document.createElement('textarea');
            textArea.value = token;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                alert('Token copiado al portapapeles');
            } catch (err) {
                alert('Error al copiar. Por favor, copia manualmente: ' + token);
            }
            document.body.removeChild(textArea);
        }
    });
    
    // Formulario de enlace de descarga
    document.getElementById('download-link-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const filename = document.getElementById('download-link-filename').value;
        const expiresHours = parseInt(document.getElementById('download-link-expires').value) || 24;
        const maxDownloads = parseInt(document.getElementById('download-link-max').value) || 1;
        const description = document.getElementById('download-link-description').value;
        
        try {
            const response = await fetch('/api/download-links', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    filename: filename,
                    expires_hours: expiresHours,
                    max_downloads: maxDownloads,
                    description: description
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Mostrar enlace generado
                    document.getElementById('generated-download-link').value = data.download_url;
                    document.getElementById('download-link-result').style.display = 'block';
                    
                    // Resetear formulario
                    document.getElementById('download-link-form').reset();
                    document.getElementById('download-link-expires').value = 24;
                    document.getElementById('download-link-max').value = 1;
                    
                    // Recargar lista de enlaces
                    loadDownloadLinks();
                } else {
                    alert('Error: ' + (data.error || 'Error desconocido'));
                }
            } else {
                const error = await response.json();
                alert('Error: ' + (error.error || 'Error al generar enlace'));
            }
        } catch (error) {
            alert('Error de conexión: ' + error.message);
        }
    });
    
    // Botón copiar enlace de descarga
    document.getElementById('copy-download-link-btn')?.addEventListener('click', async () => {
        const linkInput = document.getElementById('generated-download-link');
        const link = linkInput?.value;
        
        if (!link) {
            alert('No hay enlace para copiar');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(link);
            const btn = document.getElementById('copy-download-link-btn');
            const originalText = btn.textContent;
            btn.textContent = '✓ Copiado!';
            btn.style.background = '#22c55e';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (error) {
            alert('Error al copiar: ' + error.message);
        }
    });
}

async function loadRegistrationTokens() {
    try {
        // Usar endpoint correcto para tokens de REGISTRO (no de escaneo)
        const response = await fetch('/api/admin/registration-tokens?include_used=false');
        const data = await response.json();
        
        const tbody = document.getElementById('registration-tokens-table-body');
        if (data.success && data.tokens && data.tokens.length > 0) {
            tbody.innerHTML = data.tokens.map(token => {
                const expiresAt = token.expires_at ? (_parseUTC(token.expires_at) || new Date(0)).toLocaleString('es-ES') : 'Sin expiración';
                const isExpired = token.expires_at ? (_parseUTC(token.expires_at) || new Date(0)) < new Date() : false;

                return `
                <tr>
                    <td><code style="font-size: 11px;">${token.token.substring(0, 20)}...</code></td>
                    <td>${token.created_by || 'N/A'}</td>
                    <td>${(_parseUTC(token.created_at) || new Date()).toLocaleString('es-ES')}</td>
                    <td>${expiresAt}</td>
                    <td>
                        <span class="badge badge-${token.is_used ? 'danger' : (isExpired ? 'warning' : 'success')}">
                            ${token.is_used ? 'Usado' : (isExpired ? 'Expirado' : 'Activo')}
                        </span>
                    </td>
                </tr>
            `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay tokens de registro activos</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando tokens de registro:', error);
        const tbody = document.getElementById('registration-tokens-table-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error al cargar tokens</td></tr>';
        }
    }
}

async function loadDownloadLinks() {
    try {
        const response = await fetch('/api/download-links');
        const data = await response.json();
        
        const container = document.getElementById('download-links-list');
        if (data.success && data.links && data.links.length > 0) {
            container.innerHTML = `
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Enlace</th>
                                <th>Archivo</th>
                                <th>Creado por</th>
                                <th>Descargas</th>
                                <th>Expira</th>
                                <th>Estado</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.links.map(link => {
                                const expiresAt = link.expires_at ? (_parseUTC(link.expires_at) || new Date(0)).toLocaleString('es-ES') : 'Sin expiración';
                                const isExpired = link.expires_at ? (_parseUTC(link.expires_at) || new Date(0)) < new Date() : false;
                                const isLimitReached = link.download_count >= link.max_downloads;
                                const status = !link.is_active ? 'Desactivado' : (isExpired ? 'Expirado' : (isLimitReached ? 'Límite alcanzado' : 'Activo'));
                                const statusBadge = !link.is_active ? 'danger' : (isExpired ? 'warning' : (isLimitReached ? 'warning' : 'success'));
                                
                                return `
                                <tr>
                                    <td>
                                        <code style="font-size: 11px; word-break: break-all;">${link.download_url}</code>
                                        <button class="btn btn-sm btn-secondary" onclick="copyToClipboard('${link.download_url}')" style="margin-top: 4px;">
                                            📋 Copiar
                                        </button>
                                    </td>
                                    <td>${link.filename}</td>
                                    <td>${link.created_by || 'N/A'}</td>
                                    <td>${link.download_count} / ${link.max_downloads}</td>
                                    <td>${expiresAt}</td>
                                    <td>
                                        <span class="badge badge-${statusBadge}">${status}</span>
                                    </td>
                                    <td>
                                        ${link.is_active ? `
                                            <button class="btn btn-sm btn-danger" onclick="deleteDownloadLink(${link.id})">
                                                Desactivar
                                            </button>
                                        ` : '<span class="text-muted">-</span>'}
                                    </td>
                                </tr>
                            `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="loading-text">No hay enlaces de descarga activos</p>';
        }
    } catch (error) {
        console.error('Error cargando enlaces de descarga:', error);
        const container = document.getElementById('download-links-list');
        if (container) {
            container.innerHTML = '<p class="error-text">Error al cargar enlaces</p>';
        }
    }
}

async function deleteDownloadLink(linkId) {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Desactivar enlace de descarga?',
            body: 'El enlace dejará de funcionar. Los clientes que tengan el link guardado no podrán descargar el scanner desde él.',
            ok: 'Desactivar',
            danger: true,
          })
        : Promise.resolve(confirm('¿Estás seguro de que quieres desactivar este enlace de descarga?')));
    if (!ok) {
        return;
    }
    
    try {
        const response = await fetch(`/api/download-links/${linkId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Enlace desactivado exitosamente');
            loadDownloadLinks();
        } else {
            alert('Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error desactivando enlace:', error);
        alert('Error al desactivar enlace');
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('✓ Enlace copiado al portapapeles');
    }).catch(err => {
        alert('Error al copiar: ' + err.message);
    });
}

async function loadUsers() {
    try {
        const response = await fetch('/api/admin/users');
        const data = await response.json();
        
        const tbody = document.getElementById('users-table-body');
        if (data.success && data.users && data.users.length > 0) {
            tbody.innerHTML = data.users.map(user => {
                const lastLogin = user.last_login ? (_parseUTC(user.last_login) || new Date()).toLocaleString('es-ES') : 'Nunca';
                
                return `
                <tr>
                    <td><strong>${user.username}</strong></td>
                    <td>${user.email || 'N/A'}</td>
                    <td>
                        <span class="badge badge-${user.roles && user.roles.includes('admin') ? 'warning' : user.roles && user.roles.includes('administrador') ? 'info' : 'success'}">
                            ${user.roles ? user.roles.join(', ') : (user.role || 'Usuario')}
                        </span>
                    </td>
                    <td>${lastLogin}</td>
                    <td>
                        <span class="badge badge-${user.is_active ? 'success' : 'danger'}">
                            ${user.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                </tr>
            `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay usuarios registrados</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando usuarios:', error);
        const tbody = document.getElementById('users-table-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error al cargar usuarios</td></tr>';
        }
    }
}

async function loadCompanyUsersForAdmin() {
    try {
        const response = await fetch('/api/company/users');
        const data = await response.json();
        
        const tbody = document.getElementById('company-users-admin-table-body');
        if (!tbody) return; // Si no existe la tabla, no hacer nada
        
        if (data.success && data.users && data.users.length > 0) {
            tbody.innerHTML = data.users.map(user => {
                const lastLogin = user.last_login ? (_parseUTC(user.last_login) || new Date()).toLocaleString('es-ES') : 'Nunca';
                const roles = Array.isArray(user.roles) ? user.roles.join(', ') : (user.role || 'Usuario');
                const isAdmin = Array.isArray(user.roles) && user.roles.includes('administrador');
                const currentUserId = parseInt(document.body.getAttribute('data-user-id') || '0');
                const canModify = user.id !== currentUserId; // No permitir modificar su propia cuenta
                
                return `
                <tr>
                    <td><strong>${user.username}</strong> ${isAdmin ? '<span style="color: #3b82f6;">👑</span>' : ''}</td>
                    <td>${user.email || 'N/A'}</td>
                    <td>
                        <span class="badge badge-${isAdmin ? 'info' : 'success'}">
                            ${roles}
                        </span>
                    </td>
                    <td>${lastLogin}</td>
                    <td>
                        <span class="badge badge-${user.is_active ? 'success' : 'danger'}">
                            ${user.is_active ? 'Activo' : 'Inactivo'}
                        </span>
                    </td>
                    <td>
                        ${canModify ? `
                            <div style="display: flex; gap: 8px;">
                                ${user.is_active ? `
                                    <button class="btn btn-warning btn-small" onclick="deactivateUser(${user.id})" title="Dar de baja">
                                        ⚠️ Desactivar
                                    </button>
                                ` : `
                                    <button class="btn btn-success btn-small" onclick="activateUser(${user.id})" title="Activar">
                                        ✅ Activar
                                    </button>
                                `}
                                <button class="btn btn-danger btn-small" onclick="deleteUser(${user.id}, '${user.username}')" title="Eliminar permanentemente">
                                    🗑️ Eliminar
                                </button>
                            </div>
                        ` : '<span style="color: var(--text-secondary); font-size: 0.875rem;">Tu cuenta</span>'}
                    </td>
                </tr>
            `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No hay usuarios en la empresa</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando usuarios de empresa:', error);
        const tbody = document.getElementById('company-users-admin-table-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Error al cargar usuarios</td></tr>';
        }
    }
}

async function deactivateUser(userId) {
    const ok = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Desactivar usuario?',
            body: 'El usuario no podrá iniciar sesión hasta que lo reactives.',
            ok: 'Desactivar',
            danger: true,
          })
        : Promise.resolve(confirm('¿Estás seguro de que quieres desactivar este usuario? El usuario no podrá iniciar sesión hasta que lo reactives.')));
    if (!ok) {
        return;
    }
    
    try {
        const response = await fetch(`/api/company/users/${userId}/deactivate`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Usuario desactivado exitosamente');
            loadCompanyUsersForAdmin();
        } else {
            alert('Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error desactivando usuario:', error);
        alert('Error al desactivar usuario');
    }
}

async function activateUser(userId) {
    try {
        const response = await fetch(`/api/company/users/${userId}/activate`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Usuario activado exitosamente');
            loadCompanyUsersForAdmin();
        } else {
            alert('Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error activando usuario:', error);
        alert('Error al activar usuario');
    }
}

async function deleteUser(userId, username) {
    const ok1 = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: '¿Eliminar usuario permanentemente?',
            body: `Vas a ELIMINAR de forma permanente al usuario "${username}".\n\nEsta acción NO se puede deshacer.`,
            ok: 'Eliminar usuario',
            danger: true,
          })
        : Promise.resolve(confirm(`¿Estás SEGURO de que quieres ELIMINAR permanentemente al usuario "${username}"?\n\nEsta acción NO se puede deshacer.`)));
    if (!ok1) {
        return;
    }

    const ok2 = await (window.argusUI?.confirm
        ? window.argusUI.confirm({
            title: 'Confirmación final',
            body: 'Esta acción es PERMANENTE. ¿Estás 100% seguro?',
            ok: 'Sí, eliminar',
            cancel: 'Cancelar',
            danger: true,
          })
        : Promise.resolve(confirm('Esta acción es PERMANENTE. ¿Confirmas la eliminación?')));
    if (!ok2) {
        return;
    }
    
    try {
        const response = await fetch(`/api/company/users/${userId}/delete`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('Usuario eliminado exitosamente');
            loadCompanyUsersForAdmin();
        } else {
            alert('Error: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error eliminando usuario:', error);
        alert('Error al eliminar usuario');
    }
}

// ── Equipo section ─────────────────────────────────────────────────────────

function showEquipoTab(tabName) {
    document.querySelectorAll('.equipo-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.equipoTab === tabName);
    });
    // Show/hide tab content divs by ID convention equipo-tab-<name>
    ['miembros', 'empresa'].forEach(name => {
        const el = document.getElementById(`equipo-tab-${name}`);
        if (el) el.classList.toggle('equipo-tab-hidden', name !== tabName);
    });
}

async function loadEquipoCompanyData() {
    const infoWrap  = document.getElementById('equipo-company-info-body');
    const usersWrap = document.getElementById('equipo-company-users-body');
    if (!infoWrap && !usersWrap) return;

    if (infoWrap) infoWrap.innerHTML = '<div style="color:var(--text-d);font-size:13px;">Cargando...</div>';
    try {
        const res = await fetch('/api/company/info');
        if (!res.ok) {
            if (infoWrap) infoWrap.innerHTML = '<div style="color:var(--text-d);font-size:13px;">Sin empresa asignada.</div>';
            return;
        }
        const data = await res.json();
        const c = data.company || {};
        if (infoWrap) infoWrap.innerHTML = `
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;">
                <div class="info-field"><div class="info-label">Nombre</div><div class="info-value">${c.name || '—'}</div></div>
                <div class="info-field"><div class="info-label">País</div><div class="info-value">${c.country || '—'}</div></div>
                <div class="info-field"><div class="info-label">Tipo</div><div class="info-value">${c.company_type || '—'}</div></div>
                <div class="info-field"><div class="info-label">Creada</div><div class="info-value">${c.created_at ? formatDate(c.created_at) : '—'}</div></div>
            </div>`;
    } catch(e) {
        if (infoWrap) infoWrap.innerHTML = `<div style="color:var(--text-d);font-size:13px;">Error: ${e.message}</div>`;
    }

    if (!usersWrap) return;
    try {
        const ures = await fetch('/api/company/users');
        if (!ures.ok) { usersWrap.innerHTML = '<tr><td colspan="4" class="loading-cell">Sin acceso.</td></tr>'; return; }
        const ud = await ures.json();
        const users = ud.users || [];
        usersWrap.innerHTML = users.length ? users.map(u => `
            <tr>
                <td><strong>${u.username}</strong></td>
                <td style="font-size:11px;color:var(--text-d);">${u.email||'—'}</td>
                <td><span class="badge badge-${_staffBadge(u.staff_role)}">${STAFF_ROLE_LABELS[u.staff_role]||u.staff_role||'—'}</span></td>
                <td>${u.is_active ? '✅' : '❌'}</td>
            </tr>`).join('')
            : '<tr><td colspan="4" class="loading-cell">Sin usuarios en la empresa.</td></tr>';
    } catch(e) {
        usersWrap.innerHTML = `<tr><td colspan="4" class="loading-cell">Error: ${e.message}</td></tr>`;
    }
}

function setUserAvatar(userId, currentAvatarUrl) {
    if (currentAvatarUrl === undefined) {
        // Intentar leer desde el botón que activó el evento (tabla de staff)
        const btn = document.activeElement;
        if (btn && btn.dataset && btn.dataset.av) {
            currentAvatarUrl = btn.dataset.av;
        } else {
            // Fallback: leer desde el img del sidebar (propio usuario)
            const sidebarImg = document.querySelector('.sidebar-user-avatar .avatar-circle img');
            currentAvatarUrl = (sidebarImg && sidebarImg.src && !sidebarImg.src.startsWith('blob:')) ? sidebarImg.src : '';
        }
    }
    let modal = document.getElementById('avatar-upload-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'avatar-upload-modal';
        modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.65);backdrop-filter:blur(4px);align-items:center;justify-content:center;';
        modal.innerHTML = `
            <div style="background:var(--bg-card);border:1px solid var(--border-m);border-radius:16px;padding:28px 32px;min-width:320px;max-width:420px;width:90vw;box-shadow:0 8px 40px rgba(0,0,0,0.4);">
                <h3 style="margin:0 0 20px;font-size:16px;font-weight:700;color:var(--text-h);">Cambiar avatar</h3>
                <!-- Preview -->
                <div style="display:flex;justify-content:center;margin-bottom:20px;">
                    <div id="avatar-preview-wrap" style="width:90px;height:90px;border-radius:50%;border:3px solid var(--accent);overflow:hidden;background:var(--accent-bg);display:flex;align-items:center;justify-content:center;font-size:32px;font-weight:700;color:var(--accent);">
                        <img id="avatar-preview-img" src="" alt="" style="width:100%;height:100%;object-fit:cover;display:none;">
                        <span id="avatar-preview-initial">?</span>
                    </div>
                </div>
                <!-- Zona de drop/click para subir archivo -->
                <label id="avatar-drop-zone" style="display:block;border:2px dashed var(--border-m);border-radius:12px;padding:22px;text-align:center;cursor:pointer;color:var(--text-d);font-size:13px;transition:border-color .15s,background .15s;margin-bottom:12px;"
                    ondragover="event.preventDefault();this.style.borderColor='var(--accent)';this.style.background='var(--accent-bg)'"
                    ondragleave="this.style.borderColor='';this.style.background=''"
                    ondrop="_avatarDrop(event)">
                    <div style="font-size:28px;margin-bottom:6px;">🖼️</div>
                    <div style="font-weight:600;">Arrastra una imagen o <span style="color:var(--accent)">haz clic para seleccionar</span></div>
                    <div style="font-size:11px;margin-top:4px;">JPG, PNG, WEBP · máx 450 KB</div>
                    <input id="avatar-file-input" type="file" accept="image/jpeg,image/png,image/webp,image/gif" style="display:none;" onchange="_avatarFileSelected(event)">
                </label>
                <!-- O pegar URL -->
                <div style="font-size:11px;color:var(--text-d);text-align:center;margin-bottom:8px;">— o pega una URL externa —</div>
                <input id="avatar-url-input" type="url" placeholder="https://..." style="width:100%;box-sizing:border-box;background:var(--bg-t);border:1px solid var(--border-m);border-radius:8px;padding:8px 12px;color:var(--text);font-size:13px;outline:none;" oninput="_avatarUrlPreview(this.value)">
                <div id="avatar-error" style="color:#ef4444;font-size:12px;margin-top:8px;display:none;"></div>
                <!-- Botones -->
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:20px;">
                    <button onclick="_closeAvatarModal()" style="padding:8px 18px;border-radius:8px;border:1px solid var(--border-m);background:var(--bg-t);color:var(--text-m);cursor:pointer;font-size:13px;">Cancelar</button>
                    <button id="avatar-save-btn" onclick="_saveAvatar()" style="padding:8px 20px;border-radius:8px;border:none;background:var(--accent);color:#fff;cursor:pointer;font-weight:600;font-size:13px;">Guardar</button>
                </div>
            </div>`;
        document.body.appendChild(modal);
    }

    // Reset state
    modal._userId = userId;
    modal._dataUrl = currentAvatarUrl || '';
    document.getElementById('avatar-url-input').value = currentAvatarUrl && currentAvatarUrl.startsWith('http') ? currentAvatarUrl : '';
    document.getElementById('avatar-error').style.display = 'none';
    _avatarUpdatePreview(currentAvatarUrl || '');
    modal.style.display = 'flex';
}

function _avatarUpdatePreview(src) {
    const img     = document.getElementById('avatar-preview-img');
    const initial = document.getElementById('avatar-preview-initial');
    if (!img) return;
    if (src) {
        img.src = src;
        img.style.display = 'block';
        img.onerror = () => { img.style.display = 'none'; if (initial) initial.style.display = ''; };
        if (initial) initial.style.display = 'none';
    } else {
        img.style.display = 'none';
        if (initial) initial.style.display = '';
    }
}

function _avatarUrlPreview(val) {
    const modal = document.getElementById('avatar-upload-modal');
    if (modal) modal._dataUrl = val.trim();
    _avatarUpdatePreview(val.trim());
}

function _avatarFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    _avatarReadFile(file);
}

function _avatarDrop(event) {
    event.preventDefault();
    const dz = document.getElementById('avatar-drop-zone');
    if (dz) { dz.style.borderColor = ''; dz.style.background = ''; }
    const file = event.dataTransfer.files[0];
    if (!file || !file.type.startsWith('image/')) return;
    _avatarReadFile(file);
}

function _avatarReadFile(file) {
    const errEl = document.getElementById('avatar-error');
    if (file.size > 460_000) {
        if (errEl) { errEl.textContent = 'Imagen demasiado grande. Máx 450 KB.'; errEl.style.display = 'block'; }
        return;
    }
    if (errEl) errEl.style.display = 'none';
    const reader = new FileReader();
    reader.onload = e => {
        const dataUrl = e.target.result;
        const modal = document.getElementById('avatar-upload-modal');
        if (modal) modal._dataUrl = dataUrl;
        const urlInput = document.getElementById('avatar-url-input');
        if (urlInput) urlInput.value = '';
        _avatarUpdatePreview(dataUrl);
    };
    reader.readAsDataURL(file);
}

function _closeAvatarModal() {
    const modal = document.getElementById('avatar-upload-modal');
    if (modal) modal.style.display = 'none';
}

async function _saveAvatar() {
    const modal  = document.getElementById('avatar-upload-modal');
    const errEl  = document.getElementById('avatar-error');
    const btn    = document.getElementById('avatar-save-btn');
    if (!modal) return;
    const avatarUrl = modal._dataUrl || '';
    if (errEl) errEl.style.display = 'none';
    if (btn) { btn.textContent = 'Guardando…'; btn.disabled = true; }
    try {
        const res = await fetch(`/api/staff/users/${modal._userId}/avatar`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ avatar_url: avatarUrl }),
        });
        const data = await res.json();
        if (data.success) {
            _closeAvatarModal();
            loadStaffUsers();
            // If editing own avatar, refresh sidebar immediately
            const currentUserId = parseInt(document.body.dataset.userId || '0');
            if (modal._userId === currentUserId) {
                const circle = document.querySelector('.sidebar-user-avatar .avatar-circle');
                if (circle) {
                    let img = circle.querySelector('img');
                    const initial = circle.querySelector('span');
                    if (avatarUrl) {
                        if (!img) { img = document.createElement('img'); img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;'; circle.prepend(img); }
                        img.src = avatarUrl;
                        img.style.display = 'block';
                        img.onerror = () => { img.style.display = 'none'; };
                        if (initial) initial.style.display = 'none';
                    } else if (img) {
                        img.style.display = 'none';
                        if (initial) initial.style.display = '';
                    }
                }
            }
        } else {
            if (errEl) { errEl.textContent = data.error || 'Error al guardar'; errEl.style.display = 'block'; }
        }
    } catch(e) {
        if (errEl) { errEl.textContent = 'Error de red: ' + e.message; errEl.style.display = 'block'; }
    } finally {
        if (btn) { btn.textContent = 'Guardar'; btn.disabled = false; }
    }
}

async function submitEquipoRegToken(event) {
    event.preventDefault();
    const desc    = (document.getElementById('equipo-reg-token-desc')?.value || '').trim();
    const hours   = parseInt(document.getElementById('equipo-reg-token-hours')?.value) || 24;
    const isAdmin = document.getElementById('equipo-reg-token-admin')?.checked || false;
    try {
        const res = await fetch('/api/admin/registration-tokens', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: desc, expires_hours: hours, is_admin: isAdmin }),
        });
        const data = await res.json();
        if (data.success && data.token) {
            const tokenEl  = document.getElementById('equipo-generated-token');
            const resultEl = document.getElementById('equipo-reg-token-result');
            if (tokenEl)  tokenEl.textContent = data.token;
            if (resultEl) resultEl.style.display = 'block';
        } else {
            alert('Error: ' + (data.error || 'No se pudo generar el token'));
        }
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ARGUS IA CHAT
// ═══════════════════════════════════════════════════════════════════════════

let _aiChatOpen = false;

function toggleAIChat() {
    const panel = document.getElementById('ai-chat-panel');
    const btn   = document.getElementById('ai-chat-btn');
    if (!panel) return;
    _aiChatOpen = !_aiChatOpen;
    panel.style.display = _aiChatOpen ? 'flex' : 'none';
    btn.style.transform = _aiChatOpen ? 'scale(1.1)' : 'scale(1)';
    btn.style.boxShadow = _aiChatOpen
        ? '0 4px 28px rgba(160,90,44,.7)'
        : '0 4px 20px rgba(160,90,44,.45)';
    if (_aiChatOpen) {
        _updateAIChatScanBadge();
        document.getElementById('ai-floating-chat-input').focus();
    }
}

function _updateAIChatScanBadge() {
    const badge = document.getElementById('ai-chat-scan-badge');
    if (!badge) return;
    if (currentScanId) {
        badge.textContent = `Contexto: Scan #${currentScanId}`;
        badge.style.display = 'block';
    } else {
        badge.style.display = 'none';
    }
}

function aiQuick(msg) {
    const inp = document.getElementById('ai-floating-chat-input');
    if (inp) { inp.value = msg; inp.style.height = 'auto'; }
    sendAIChatMessage();
}

function aiChatKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendAIChatMessage();
    }
}

function _scrollAIChatToBottom(container) {
    if (!container) return;
    const last = container.lastElementChild;
    if (last && typeof last.scrollIntoView === 'function') {
        last.scrollIntoView({ behavior: 'smooth', block: 'end' });
        return;
    }
    container.scrollTop = container.scrollHeight;
}

async function sendAIChatMessage() {
    const inp  = document.getElementById('ai-floating-chat-input');
    const msgs = document.getElementById('ai-chat-messages');
    if (!inp || !msgs) return;

    const msg = inp.value.trim();
    if (!msg) return;

    inp.value = '';
    inp.style.height = 'auto';

    // Mensaje del staff (derecha)
    _appendChatMsg(msgs, msg, 'user');

    // Typing indicator
    const typing = _appendChatMsg(msgs, '&nbsp;⋯', 'bot', true);

    try {
        const body = { message: msg };
        if (currentScanId) body.scan_id = currentScanId;
        let data = null;
        initArgusSocket();
        if (_argusSocket && _argusSocketConnected) {
            data = await new Promise((resolve) => {
                _argusSocketPendingResolve = resolve;
                _argusSocket.emit('oracle_message', body);
                setTimeout(() => {
                    if (_argusSocketPendingResolve === resolve) {
                        _argusSocketPendingResolve = null;
                        resolve({ error: 'WS timeout, usando fallback HTTP' });
                    }
                }, 4500);
            });
        }
        if (!data || data.error === 'WS timeout, usando fallback HTTP') {
            const res  = await fetch('/api/staff/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            data = await res.json();
        }

        typing.remove();

        if (data.error) {
            _appendChatMsg(msgs, `⚠️ ${data.error}`, 'bot');
        } else {
            let reply = data.reply || '';
            // Badge de proveedores + búsqueda web usada
            const meta = [];
            if (data.providers_used && data.providers_used.length)
                meta.push('🤖 ' + data.providers_used.map(p => ({claude:'Claude',groq:'Groq',gemini:'Gemini'}[p]||p)).join(' + '));
            if (data.search_done) meta.push('🔍 búsqueda web');
            if (meta.length) reply += `\n\n<span style="font-size:11px;opacity:.55">${meta.join(' · ')}</span>`;
            const botBubble = _appendChatMsg(msgs, _formatAIReply(reply), 'bot');
            if (data.conversation_id) {
                _appendOracleFeedbackButtons(msgs, data.conversation_id, botBubble);
            }
        }
    } catch (e) {
        typing.remove();
        _appendChatMsg(msgs, `⚠️ Error de conexión: ${e.message}`, 'bot');
    }

    _scrollAIChatToBottom(msgs);
}

function _appendChatMsg(container, text, role, isTyping) {
    const el = document.createElement('div');
    const isUser = role === 'user';
    el.style.cssText = [
        'border-radius:' + (isUser ? '12px 12px 4px 12px' : '12px 12px 12px 4px'),
        'padding:10px 13px',
        'font-size:13px',
        'color:#e2e8f0',
        'max-width:88%',
        'line-height:1.5',
        'white-space:pre-wrap',
        'align-self:' + (isUser ? 'flex-end' : 'flex-start'),
        'background:' + (isUser ? 'rgba(79,70,229,.35)' : 'rgba(160,90,44,.15)'),
    ].join(';');
    el.innerHTML = isTyping ? '<span class="ai-typing-dots">● ● ●</span>' : text;
    container.appendChild(el);
    _scrollAIChatToBottom(container);
    return el;
}

function _appendOracleFeedbackButtons(container, conversationId, anchorEl) {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;gap:8px;align-self:flex-start;margin-top:4px;opacity:.85';
    const up = document.createElement('button');
    const down = document.createElement('button');
    up.type = 'button';
    down.type = 'button';
    up.textContent = '👍 útil';
    down.textContent = '👎 no útil';
    [up, down].forEach((b) => {
        b.style.cssText = 'background:rgba(148,163,184,.12);border:1px solid rgba(148,163,184,.25);color:#cbd5e1;border-radius:8px;padding:3px 7px;font-size:11px;cursor:pointer';
    });
    const sendFeedback = async (thumb) => {
        try {
            await fetch('/api/oracle/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ conversation_id: conversationId, thumb })
            });
            wrap.innerHTML = '<span style="font-size:11px;color:#94a3b8">Gracias por el feedback.</span>';
        } catch (_) {
            wrap.innerHTML = '<span style="font-size:11px;color:#ef4444">No se pudo guardar feedback.</span>';
        }
    };
    up.addEventListener('click', () => sendFeedback('up'));
    down.addEventListener('click', () => sendFeedback('down'));
    wrap.appendChild(up);
    wrap.appendChild(down);
    if (anchorEl && anchorEl.nextSibling) {
        container.insertBefore(wrap, anchorEl.nextSibling);
    } else {
        container.appendChild(wrap);
    }
}

function _formatAIReply(text) {
    const safe = escapeHtml(text || '');
    return safe
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '• $1')
        .replace(/\n/g, '<br>');
}

async function clearAIChat() {
    const msgs = document.getElementById('ai-chat-messages');
    if (!msgs) return;
    // Limpiar en servidor
    await fetch('/api/staff/chat/clear', { method: 'POST' }).catch(() => {});
    // Limpiar UI — dejar solo el mensaje de bienvenida
    msgs.innerHTML = `<div style="background:rgba(160,90,44,.15);border-radius:12px 12px 12px 4px;
        padding:10px 13px;font-size:13px;color:#e2e8f0;max-width:90%">
        Conversación borrada. ¿En qué te ayudo?</div>`;
}

// Actualizar badge cuando cambia el scan activo
const _origOpenScanDetail = typeof openScanDetail === 'function' ? openScanDetail : null;
// Hook pasivo: _updateAIChatScanBadge se llama desde toggleAIChat al abrir

// ─── Sugerencia automática de veredicto (Parte 3 item 22) ───────────────────

async function _loadAIVerdictSuggestion(scanId) {
    const card       = document.getElementById('ai-verdict-card');
    const badge      = document.getElementById('ai-verdict-badge');
    const reasonsEl  = document.getElementById('ai-verdict-reasons');
    const confEl     = document.getElementById('ai-verdict-confidence');
    if (!card) return;

    // Mostrar estado cargando
    card.style.display = 'block';
    badge.textContent  = '⋯';
    badge.style.background = 'rgba(160,90,44,.2)';
    badge.style.color  = '#D4915A';
    reasonsEl.innerHTML = '<li style="list-style:none;color:var(--text-d)">Analizando hallazgos...</li>';
    confEl.textContent  = '';

    try {
        const res  = await fetch(`/api/staff/ai/suggest-verdict/${scanId}`);
        const data = await res.json();
        if (data.error) { card.style.display = 'none'; return; }

        const isHack = data.verdict === 'HACK';
        badge.textContent  = isHack ? '⚠️ HACK' : '✅ LIMPIO';
        badge.style.background = isHack ? 'rgba(239,68,68,.2)' : 'rgba(16,185,129,.15)';
        badge.style.color      = isHack ? '#ef4444' : '#10b981';
        card.style.borderColor = isHack ? 'rgba(239,68,68,.35)' : 'rgba(16,185,129,.3)';
        card.style.background  = isHack ? 'rgba(239,68,68,.06)' : 'rgba(16,185,129,.05)';

        const reasons = data.reasons || [];
        reasonsEl.innerHTML = reasons.map(r => `<li style="margin-bottom:2px">${r}</li>`).join('');
        confEl.textContent  = `Confianza IA: ${data.confidence}%`;
    } catch(e) {
        card.style.display = 'none';
    }
}

// ─── Explicación individual de hallazgos (Parte 3 item 21) ──────────────────

async function aiExplainFinding(name, level, btn) {
    const row = btn.closest('[data-result-id]');
    let expEl = row ? row.querySelector('.ai-explain-text') : null;

    if (expEl && expEl.style.display !== 'none') {
        expEl.style.display = 'none';
        btn.textContent = '🤖';
        return;
    }

    btn.textContent = '⋯';
    btn.disabled = true;

    try {
        const res  = await fetch(`/api/staff/ai/explain?name=${encodeURIComponent(name)}&level=${encodeURIComponent(level)}`);
        const data = await res.json();
        const text = data.explanation || 'Sin explicación disponible.';

        if (!expEl) {
            expEl = document.createElement('div');
            expEl.className = 'ai-explain-text';
            expEl.style.cssText = 'font-size:11px;color:#c4b5fd;margin-top:5px;padding:5px 8px;background:rgba(160,90,44,.1);border-radius:6px;border-left:2px solid #7c3aed;line-height:1.5;';
            if (row) row.querySelector('div[style*="flex:1"]')?.appendChild(expEl);
        }
        expEl.textContent = '🤖 ' + text;
        expEl.style.display = 'block';
        btn.textContent = '🤖';
    } catch(e) {
        btn.textContent = '🤖';
    }
    btn.disabled = false;
}

// ─── Resumen ejecutivo del scan (P3 #12) ─────────────────────────────────────

async function aiScanSummary(scanId, btn) {
    const containerId = 'ai-scan-summary-' + scanId;
    let el = document.getElementById(containerId);

    if (el && el.style.display !== 'none') {
        el.style.display = 'none';
        if (btn) btn.textContent = '📝 Resumen IA';
        return;
    }

    if (btn) { btn.textContent = '⋯'; btn.disabled = true; }

    try {
        const res  = await fetch(`/api/staff/ai/scan-summary/${scanId}`);
        const data = await res.json();
        const text = data.summary || 'No se pudo generar el resumen.';

        if (!el) {
            el = document.createElement('div');
            el.id = containerId;
            el.style.cssText = 'margin-top:10px;padding:10px 14px;background:rgba(160,90,44,.08);border:1px solid rgba(160,90,44,.25);border-radius:8px;font-size:12px;line-height:1.6;color:var(--text-m);';
            const card = document.getElementById('ai-verdict-card');
            if (card) card.appendChild(el);
        }
        // Visual #41 — typewriter del resumen IA. Header inmediato + texto con
        // animación typing. Si argusUI.typewriter no está disponible (build vieja
        // de argus-ui.js), volvemos al render plano.
        el.innerHTML = '<span style="color:#D4915A;font-weight:600">📝 Resumen IA:</span><br><span class="ai-summary-text"></span>';
        el.style.display = 'block';
        const target = el.querySelector('.ai-summary-text');
        if (target && window.argusUI?.typewriter) {
            window.argusUI.typewriter(target, text, { speedCps: 120 });
        } else if (target) {
            target.textContent = text;
        } else {
            el.innerHTML = '<span style="color:#D4915A;font-weight:600">📝 Resumen IA:</span><br>' + text;
        }
    } catch(e) {
        console.error('aiScanSummary error', e);
    }
    if (btn) { btn.textContent = '📝 Resumen IA'; btn.disabled = false; }
}

// ─── Inconsistencias IA (P3 #23) ─────────────────────────────────────────────

async function aiShowInconsistencies(scanId, btn) {
    const container = document.getElementById('ai-inconsistencies-container');
    if (!container) return;

    if (container.style.display !== 'none') {
        container.style.display = 'none';
        if (btn) btn.textContent = '⚠️ Inconsistencias';
        return;
    }

    if (btn) { btn.textContent = '⋯'; btn.disabled = true; }
    container.innerHTML = 'Analizando inconsistencias...';
    container.style.display = 'block';

    try {
        const res  = await fetch(`/api/staff/ai/inconsistencies/${scanId}`);
        const data = await res.json();
        const items = data.inconsistencies || [];
        if (items.length === 0) {
            container.innerHTML = '✅ No se detectaron inconsistencias significativas.';
        } else {
            container.innerHTML = '<strong style="color:#f59e0b">Inconsistencias detectadas:</strong><ul style="margin:4px 0 0 16px;padding:0;">' +
                items.map(i => `<li style="margin-bottom:3px;">${i}</li>`).join('') + '</ul>';
        }
    } catch(e) {
        container.innerHTML = 'Error al analizar inconsistencias.';
    }
    if (btn) { btn.textContent = '⚠️ Inconsistencias'; btn.disabled = false; }
}

// ─── Anomalía Isolation Forest (P3 #3) ────────────────────────────────────────

async function aiCheckAnomaly(scanId, btn) {
    const containerId = 'ai-anomaly-result-' + scanId;
    let el = document.getElementById(containerId);

    if (el && el.style.display !== 'none') {
        el.style.display = 'none';
        if (btn) btn.textContent = '🔬 Anomalía';
        return;
    }

    if (!el) {
        el = document.createElement('div');
        el.id = containerId;
        el.style.cssText = 'margin-top:8px;font-size:11px;padding:6px 10px;border-radius:6px;border-left:2px solid #ef4444;background:rgba(239,68,68,.07);color:#f87171;';
        const container = document.getElementById('ai-inconsistencies-container');
        if (container && container.parentNode) container.parentNode.insertBefore(el, container.nextSibling);
    }

    if (btn) { btn.textContent = '⋯'; btn.disabled = true; }
    el.textContent = 'Analizando perfil de anomalía...';
    el.style.display = 'block';

    try {
        const res  = await fetch(`/api/ml/anomaly/${scanId}`);
        const data = await res.json();
        if (data.error) {
            el.textContent = '⚠️ ' + data.error;
        } else if (!data.is_anomaly) {
            el.style.borderLeftColor = '#10b981';
            el.style.background = 'rgba(16,185,129,.06)';
            el.style.color = '#6ee7b7';
            el.textContent = `✅ Scan dentro del rango normal (score: ${data.anomaly_score}, baseline: ${data.baseline_size} scans limpios)`;
        } else {
            el.textContent = `🚨 Scan ANÓMALO (score: ${data.anomaly_score}): ${data.reason}`;
        }
    } catch(e) {
        el.textContent = 'Error al verificar anomalía.';
    }
    if (btn) { btn.textContent = '🔬 Anomalía'; btn.disabled = false; }
}

async function aiFollowupQuestions(scanId, btn) {
    const container = document.getElementById('ai-followup-container');
    if (!container) return;

    if (container.style.display !== 'none' && container.dataset.scanId == scanId) {
        container.style.display = 'none';
        if (btn) btn.textContent = '❓ Preguntas';
        return;
    }

    if (btn) { btn.textContent = '⋯'; btn.disabled = true; }
    container.style.display = 'block';
    container.dataset.scanId = scanId;
    container.innerHTML = '<em>Generando preguntas de seguimiento...</em>';

    try {
        const res  = await fetch(`/api/staff/ai/followup-questions/${scanId}`);
        const data = await res.json();
        if (data.error) {
            container.innerHTML = '⚠️ ' + data.error;
        } else {
            const qs = data.questions || [];
            if (!qs.length) {
                container.innerHTML = data.raw || 'Sin preguntas generadas.';
            } else {
                container.innerHTML = '<strong style="color:#6ee7b7">Preguntas sugeridas para el jugador:</strong><ol style="margin:6px 0 0 16px;padding:0">' +
                    qs.map(q => `<li style="margin-bottom:4px">${q}</li>`).join('') + '</ol>';
            }
        }
    } catch(e) {
        container.innerHTML = 'Error al generar preguntas.';
    }
    if (btn) { btn.textContent = '❓ Preguntas'; btn.disabled = false; }
}

// ── Generate Ban Message (P5 #19) ─────────────────────────────────────────────

async function generateBanMessage(scanId, btn) {
    if (!scanId) return;
    const container = document.getElementById('ban-message-container');
    const orig = btn ? btn.textContent : '';
    if (btn) { btn.textContent = '⏳ Generando...'; btn.disabled = true; }
    if (container) { container.style.display = 'none'; container.textContent = ''; }
    try {
        const res  = await fetch('/api/staff/ai/generate-ban-message', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({scan_id: scanId}),
        });
        const data = await res.json();
        if (data.error) {
            if (container) { container.style.display = 'block'; container.textContent = '❌ ' + data.error; }
        } else if (data.ban_message) {
            if (container) {
                container.style.display = 'block';
                container.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-weight:600;font-size:10px;color:#94a3b8;letter-spacing:.05em;">MENSAJE GENERADO — COPIAR Y EDITAR SEGÚN CONTEXTO</span>
                    <button onclick="navigator.clipboard.writeText(this.closest('[data-msg]')?.dataset.msg||'').then(()=>{this.textContent='✅ Copiado';setTimeout(()=>this.textContent='📋 Copiar',1500)})"
                        style="font-size:10px;padding:2px 8px;border-radius:4px;border:1px solid rgba(239,68,68,.4);background:rgba(239,68,68,.1);color:#f87171;cursor:pointer;">📋 Copiar</button>
                </div>
                <div data-msg="${data.ban_message.replace(/"/g,'&quot;')}" style="white-space:pre-wrap;font-family:monospace;">${data.ban_message.replace(/</g,'&lt;')}</div>`;
                // fix copy button reference
                const copyBtn = container.querySelector('button');
                const msgDiv  = container.querySelector('[data-msg]');
                if (copyBtn && msgDiv) {
                    copyBtn.onclick = () => {
                        navigator.clipboard.writeText(msgDiv.dataset.msg || data.ban_message)
                            .then(() => { copyBtn.textContent = '✅ Copiado'; setTimeout(() => copyBtn.textContent = '📋 Copiar', 1500); });
                    };
                }
            }
        }
    } catch(e) {
        if (container) { container.style.display = 'block'; container.textContent = '❌ Error de red: ' + e.message; }
    } finally {
        if (btn) { btn.textContent = orig || '🔨 Msg Ban'; btn.disabled = false; }
    }
}

// ── IOC Extractor ─────────────────────────────────────────────────────────────

function openIocExtractor() {
    const m = document.getElementById('ioc-modal');
    if (m) { m.style.display = 'flex'; }
}

function closeIocExtractor() {
    const m = document.getElementById('ioc-modal');
    if (m) { m.style.display = 'none'; }
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeIocExtractor();
});

async function runIocExtract() {
    const text = (document.getElementById('ioc-input')?.value || '').trim();
    const out  = document.getElementById('ioc-results');
    if (!text) { out.innerHTML = '<span style="color:#ef4444">Pega texto primero.</span>'; return; }
    out.innerHTML = '<span style="color:#94a3b8">Extrayendo…</span>';
    try {
        const res  = await fetch('/api/staff/extract-iocs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text}),
        });
        const d = await res.json();
        if (d.error) { out.innerHTML = `<span style="color:#ef4444">⚠️ ${d.error}</span>`; return; }

        const section = (title, color, items) => items.length
            ? `<div style="margin-bottom:10px"><span style="color:${color};font-weight:700">${title}</span><br>`
              + items.map(x => `<span style="color:#e2e8f0;background:#0f172a;border-radius:4px;padding:1px 6px;display:inline-block;margin:2px">${x}</span>`).join(' ')
              + '</div>'
            : '';

        const parts = [
            section('🌐 IPs públicas',    '#60a5fa', d.ips?.public  || []),
            section('🌐 Todas las IPs',   '#94a3b8', (d.ips?.all || []).filter(ip => !(d.ips?.public||[]).includes(ip))),
            section('🔑 SHA-256',         '#D4915A', d.hashes?.sha256 || []),
            section('🔑 SHA-1',           '#c084fc', d.hashes?.sha1   || []),
            section('🔑 MD5',             '#e879f9', d.hashes?.md5    || []),
            section('🌍 Dominios',        '#34d399', d.domains        || []),
            section('📂 Rutas',           '#fbbf24', d.file_paths     || []),
            section('☕ JARs',            '#fb923c', d.jar_files      || []),
        ].filter(Boolean).join('');

        out.innerHTML = parts || '<span style="color:#94a3b8">No se encontraron IOCs.</span>';
        if (d.total) {
            out.innerHTML = `<div style="color:#94a3b8;margin-bottom:8px;font-size:11px">Total: ${d.total} IOC(s) encontrados</div>` + out.innerHTML;
        }
    } catch(e) {
        out.innerHTML = '<span style="color:#ef4444">Error de red.</span>';
    }
}

// P5 #21 + P5 #14 — Reputación del jugador y sparkline de risk score
async function _renderPlayerReputation(machineName, allScans) {
    const card = document.getElementById('player-reputation-card');
    if (!card) return;

    const total  = allScans.length;
    const hacks  = allScans.filter(s => s.verdict === 'hack').length;
    const clean  = allScans.filter(s => s.verdict === 'clean').length;
    const scores = allScans.map(s => s.risk_score).filter(v => v != null);
    const avgRisk = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;

    // Badges de reputación
    const badges = [];
    if (total === 1) {
        badges.push(['Primera vez', '#6366f1']);
    } else if (hacks >= 3) {
        badges.push(['Reincidente', '#dc2626']);
    } else if (hacks >= 1) {
        badges.push(['Sospechoso', '#f59e0b']);
    } else if (clean > 0 && hacks === 0) {
        badges.push(['Historial limpio', '#10b981']);
    }
    if (total >= 10) badges.push(['Veterano', '#8b5cf6']);
    const lastScan = allScans[0];
    if (lastScan && lastScan.risk_score >= 80) badges.push(['Alto riesgo', '#ef4444']);

    const badgeEl = document.getElementById('player-rep-badges');
    if (badgeEl) {
        badgeEl.innerHTML = badges.map(([label, color]) =>
            `<span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:10px;background:${color}22;color:${color};border:1px solid ${color}44;">${label}</span>`
        ).join('');
    }

    const nameEl = document.getElementById('player-rep-name');
    if (nameEl) nameEl.textContent = machineName || 'Jugador';

    const setEl = (id, val, color) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = val ?? '—';
        if (color) el.style.color = color;
    };
    setEl('player-rep-total', total);
    setEl('player-rep-hacks', hacks, hacks > 0 ? '#ef4444' : '#10b981');
    setEl('player-rep-clean', clean, clean > 0 ? '#10b981' : 'var(--text-m)');
    const riskColor = avgRisk == null ? 'var(--text-m)' : avgRisk >= 70 ? '#ef4444' : avgRisk >= 30 ? '#f59e0b' : '#10b981';
    setEl('player-rep-risk', avgRisk, riskColor);

    card.style.display = 'block';

    // P5 #14 — Sparkline: intentar usar /api/player/timeline si hay machine_id en el scan actual
    const machineId = _currentScanData && _currentScanData.machine_id;
    if (machineId) {
        try {
            const res = await fetch(`/api/player/timeline/${encodeURIComponent(machineId)}`);
            if (res.ok) {
                const tl = await res.json();
                const entries = tl.timeline || [];
                if (entries.length >= 2) {
                    const sparkWrap   = document.getElementById('player-sparkline-wrap');
                    const sparkCanvas = document.getElementById('player-sparkline-chart');
                    if (sparkWrap && sparkCanvas) {
                        sparkWrap.style.display = 'block';
                        const labels = entries.map(e => (e.date || '').slice(5, 10));
                        const scores = entries.map(e => e.risk_score);
                        const ptColors = scores.map(v => v >= 70 ? '#ef4444' : v >= 30 ? '#f59e0b' : '#10b981');
                        // Draw trend line if provided
                        const trendData = tl.trend_line || null;
                        const datasets = [{
                            label: 'Risk Score',
                            data: scores,
                            borderColor: '#8b5cf6',
                            backgroundColor: 'rgba(184,115,51,0.08)',
                            pointBackgroundColor: ptColors,
                            pointRadius: 4,
                            tension: 0.3,
                            fill: true,
                        }];
                        if (trendData && trendData.length === entries.length) {
                            datasets.push({
                                label: 'Tendencia',
                                data: trendData,
                                borderColor: 'rgba(251,191,36,0.6)',
                                borderDash: [4, 4],
                                pointRadius: 0,
                                fill: false,
                                tension: 0,
                            });
                        }
                        if (window._playerSparklineChart) window._playerSparklineChart.destroy();
                        window._playerSparklineChart = new Chart(sparkCanvas, {
                            type: 'line',
                            data: { labels, datasets },
                            options: {
                                responsive: true,
                                animation: false,
                                plugins: { legend: { display: false }, tooltip: {
                                    callbacks: { label: ctx => ` Risk: ${ctx.parsed.y}` }
                                }},
                                scales: {
                                    y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.04)' },
                                         ticks: { color: '#6b7280', font: { size: 9 } } },
                                    x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 9 } } }
                                }
                            }
                        });
                    }
                }
            }
        } catch(_) {}
    } else if (allScans.length >= 2) {
        // Fallback: sparkline from scan history data
        const sparkWrap   = document.getElementById('player-sparkline-wrap');
        const sparkCanvas = document.getElementById('player-sparkline-chart');
        if (sparkWrap && sparkCanvas) {
            const sorted = [...allScans].sort((a, b) => new Date(a.started_at) - new Date(b.started_at));
            const sLabels = sorted.map(s => s.started_at ? s.started_at.toString().slice(5,10) : '?');
            const sScores = sorted.map(s => s.risk_score || 0);
            const sColors = sScores.map(v => v >= 70 ? '#ef4444' : v >= 30 ? '#f59e0b' : '#10b981');
            sparkWrap.style.display = 'block';
            if (window._playerSparklineChart) window._playerSparklineChart.destroy();
            window._playerSparklineChart = new Chart(sparkCanvas, {
                type: 'line',
                data: {
                    labels: sLabels,
                    datasets: [{ data: sScores, borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(184,115,51,0.08)',
                        pointBackgroundColor: sColors, pointRadius: 4,
                        tension: 0.3, fill: true }]
                },
                options: {
                    responsive: true, animation: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.04)' },
                             ticks: { color: '#6b7280', font: { size: 9 } } },
                        x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 9 } } }
                    }
                }
            });
        }
    }
}

// ============================================================
// V31: SIDEBAR COLLAPSE TOGGLE
// ============================================================
function toggleSidebarCollapse() {
    const sidebar = document.querySelector('.sidebar');
    const btn     = document.getElementById('sidebar-toggle-btn');
    const main    = document.querySelector('.main-content');
    if (!sidebar) return;
    const collapsed = sidebar.classList.toggle('collapsed');
    localStorage.setItem('argus_sidebar_collapsed', collapsed ? '1' : '0');
    if (btn) {
        btn.textContent = collapsed ? '▶' : '◀';
        btn.style.left = collapsed ? '47px' : '227px';
    }
    if (main) main.style.marginLeft = collapsed ? '60px' : '';
}
window.toggleSidebarCollapse = toggleSidebarCollapse;

(function _initSidebarCollapse() {
    if (localStorage.getItem('argus_sidebar_collapsed') === '1') {
        document.addEventListener('DOMContentLoaded', () => {
            const sidebar = document.querySelector('.sidebar');
            const btn     = document.getElementById('sidebar-toggle-btn');
            const main    = document.querySelector('.main-content');
            if (sidebar) sidebar.classList.add('collapsed');
            if (btn) { btn.textContent = '▶'; btn.style.left = '47px'; }
            if (main)    main.style.marginLeft = '60px';
        });
    }
})();

// ============================================================
// V39: SCROLL TO TOP
// ============================================================
(function _initScrollToTop() {
    window.addEventListener('scroll', () => {
        const btn = document.getElementById('scroll-to-top');
        const header = document.querySelector('.panel-header');
        if (!btn) return;
        btn.classList.toggle('visible', window.scrollY > 300);
        if (header) header.classList.toggle('is-scrolled', window.scrollY > 8);
    }, { passive: true });
})();

// ============================================================
// V37: KEYBOARD SHORTCUTS OVERLAY
// ============================================================
function closeKbdOverlay() {
    document.getElementById('kbd-overlay')?.classList.remove('open');
}
window.closeKbdOverlay = closeKbdOverlay;

// ============================================================
// V38: GLOBAL SEARCH (Ctrl+K)
// ============================================================
let _globalSearchIndex = -1;
let _globalSearchResults = [];

function openGlobalSearch() {
    const overlay = document.getElementById('global-search-overlay');
    if (!overlay) return;
    overlay.classList.add('open');
    setTimeout(() => document.getElementById('global-search-input')?.focus(), 50);
}
function closeGlobalSearch() {
    document.getElementById('global-search-overlay')?.classList.remove('open');
    _globalSearchIndex = -1;
}
window.openGlobalSearch = openGlobalSearch;
window.closeGlobalSearch = closeGlobalSearch;

async function _globalSearchInput(q) {
    const res = document.getElementById('global-search-results');
    if (!res) return;
    q = q.trim();
    if (q.length < 2) {
        res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:var(--text-d);">Escribe al menos 2 caracteres...</div>';
        _globalSearchResults = [];
        return;
    }
    res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:var(--text-d);">Buscando...</div>';
    try {
        const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&types=scans,users,companies,violations`);
        const d = await r.json();
        _globalSearchResults = d.results || [];
        _globalSearchIndex   = -1;
        if (_globalSearchResults.length === 0) {
            res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:var(--text-d);">Sin resultados</div>';
            return;
        }
        res.innerHTML = _globalSearchResults.map((s, i) => {
            return `<div class="global-search-result" data-idx="${i}" onclick="_globalSearchOpen(${i})">
                <span style="font-size:18px;">${s.type === 'scan' ? '🧪' : s.type === 'user' ? '👤' : s.type === 'company' ? '🏢' : '⚠️'}</span>
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${s.label || 'N/A'}</div>
                    <div style="font-size:11px;color:var(--text-d);">${s.type || 'item'}</div>
                </div>
            </div>`;
        }).join('');
    } catch(_) {
        res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:#ef4444;">Error de búsqueda</div>';
    }
}
function _globalSearchOpen(idx) {
    const s = _globalSearchResults[idx];
    if (!s) return;
    closeGlobalSearch();
    if (s.type === 'scan') viewScanDetails(s.id);
    else if (s.type === 'user') showToast(`Usuario #${s.id}`, 'info');
    else if (s.type === 'company') showToast(`Empresa #${s.id}`, 'info');
    else showToast(String(s.label || ''), 'info');
}
function _globalSearchKey(e) {
    const items = document.querySelectorAll('.global-search-result');
    if (e.key === 'ArrowDown') {
        _globalSearchIndex = Math.min(_globalSearchIndex + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
        _globalSearchIndex = Math.max(_globalSearchIndex - 1, 0);
    } else if (e.key === 'Enter') {
        if (_globalSearchIndex >= 0) _globalSearchOpen(_globalSearchIndex);
        else if (_globalSearchResults.length > 0) _globalSearchOpen(0);
        return;
    } else if (e.key === 'Escape') {
        closeGlobalSearch(); return;
    }
    items.forEach((el, i) => el.classList.toggle('selected', i === _globalSearchIndex));
    if (items[_globalSearchIndex]) items[_globalSearchIndex].scrollIntoView({ block: 'nearest' });
}
window._globalSearchInput = _globalSearchInput;
window._globalSearchKey   = _globalSearchKey;
window._globalSearchOpen  = _globalSearchOpen;

// ============================================================
// V69: NOTIFICATION CENTER
// ============================================================
const _notifications = [];
let _unreadNotifCount = 0;

function _addNotification({ icon, text, scanId, time }) {
    _notifications.unshift({ icon, text, scanId, time, read: false });
    if (_notifications.length > 20) _notifications.pop();
    _unreadNotifCount++;
    const badge = document.getElementById('notif-badge');
    if (badge) { badge.textContent = _unreadNotifCount; badge.classList.add('visible'); }
    _renderNotifList();
}

function _renderNotifList() {
    const list = document.getElementById('notif-list');
    if (!list) return;
    if (_notifications.length === 0) {
        list.innerHTML = '<div style="padding:16px 14px;font-size:12px;color:var(--text-d);text-align:center;">Sin notificaciones</div>';
        return;
    }
    list.innerHTML = _notifications.map((n, i) => `
        <div class="notif-item ${n.read ? '' : 'unread'}" onclick="_notifClick(${i})">
            <span style="font-size:14px;margin-right:6px;">${n.icon}</span>
            <div style="flex:1;min-width:0;">
                <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${n.text}</div>
                <div style="font-size:10px;color:var(--text-d);margin-top:2px;">${_timeAgo(n.time)}</div>
            </div>
        </div>`).join('');
}

function _notifClick(idx) {
    const n = _notifications[idx];
    if (!n) return;
    n.read = true;
    if (n.scanId) { viewScanDetails(n.scanId); toggleNotifCenter(null); }
    _renderNotifList();
}

function toggleNotifCenter(e) {
    if (e) e.stopPropagation();
    const dd = document.getElementById('notif-dropdown');
    if (!dd) return;
    dd.classList.toggle('open');
    if (dd.classList.contains('open')) {
        _unreadNotifCount = 0;
        _notifications.forEach(n => n.read = true);
        const badge = document.getElementById('notif-badge');
        if (badge) badge.classList.remove('visible');
        _renderNotifList();
    }
}
window.toggleNotifCenter = toggleNotifCenter;
window._notifClick = _notifClick;

// Close notif dropdown on outside click
document.addEventListener('click', e => {
    const dd = document.getElementById('notif-dropdown');
    const btn = document.getElementById('notif-bell-btn');
    if (dd && btn && !dd.contains(e.target) && !btn.contains(e.target)) {
        dd.classList.remove('open');
    }
});

// ============================================================
// V68: CRITICAL ALERT BANNER
// ============================================================
let _criticalAlertScanId = null;
function _showCriticalBanner(name, scanId) {
    _criticalAlertScanId = scanId;
    const banner = document.getElementById('critical-alert-banner');
    const nameEl = document.getElementById('critical-alert-name');
    if (!banner) return;
    if (nameEl) nameEl.textContent = name;
    banner.classList.add('visible');
    showToast(`⚠️ CRÍTICO: ${name}`, 'error', scanId);
    playCriticalSound();
    _addNotification({ icon: '🔴', text: `⚠️ CRÍTICO: ${name}`, scanId, time: new Date() });
    setTimeout(() => banner.classList.remove('visible'), 12000);
}
function _criticalAlertView() {
    if (_criticalAlertScanId) {
        viewScanDetails(_criticalAlertScanId);
        document.getElementById('critical-alert-banner')?.classList.remove('visible');
    }
}
window._criticalAlertView = _criticalAlertView;

// ============================================================
// V70: CRITICAL SOUND (extended)
// ============================================================
function playCriticalSound() {
    if (!_soundEnabled) return;
    try {
        const ctx  = new (window.AudioContext || window.webkitAudioContext)();
        const gain = ctx.createGain();
        gain.connect(ctx.destination);
        gain.gain.setValueAtTime(0.18, ctx.currentTime);

        // Two-note alert chord
        [880, 1109].forEach((freq, i) => {
            const osc = ctx.createOscillator();
            osc.connect(gain);
            osc.type = 'square';
            osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.12);
            gain.gain.setValueAtTime(0.18, ctx.currentTime + i * 0.12);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.35);
            osc.start(ctx.currentTime + i * 0.12);
            osc.stop(ctx.currentTime + i * 0.12 + 0.35);
        });
    } catch(_) {}
}

// ============================================================
// V40: SECTION TRANSITION ANIMATION
// ============================================================
const _origShowSection = window.showSection;
window.showSection = function(sectionId) {
    const current = document.querySelector('.panel-section.active');
    if (current && current.id !== sectionId) {
        current.classList.add('section-leaving');
        setTimeout(() => {
            current.classList.remove('section-leaving');
            if (typeof _origShowSection === 'function') _origShowSection(sectionId);
            else _showSectionInner(sectionId);
            const next = document.getElementById(sectionId);
            if (next) next.classList.add('section-entering');
            setTimeout(() => next?.classList.remove('section-entering'), 220);
        }, 120);
    } else {
        if (typeof _origShowSection === 'function') _origShowSection(sectionId);
        else _showSectionInner(sectionId);
    }
};
function _showSectionInner(sectionId) {
    document.querySelectorAll('.panel-section').forEach(s => {
        s.classList.remove('active'); s.style.display = 'none';
    });
    const target = document.getElementById(sectionId);
    if (target) { target.style.display = 'block'; target.classList.add('active'); }
}

// ============================================================
// V41: RIPPLE — attach to all buttons on DOMContentLoaded
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    document.addEventListener('click', e => {
        const btn = e.target.closest('.btn, button[class*="btn"]');
        if (!btn) return;
        _addRipple({ ...e, currentTarget: btn });
    });
});

// ============================================================
// V62: MATRIX THEME + KONAMI CODE
// ============================================================
const _konamiSeq = ['ArrowUp','ArrowUp','ArrowDown','ArrowDown','ArrowLeft','ArrowRight','ArrowLeft','ArrowRight','b','a'];
let _konamiIdx = 0;
document.addEventListener('keydown', e => {
    if (e.key === _konamiSeq[_konamiIdx]) {
        _konamiIdx++;
        if (_konamiIdx === _konamiSeq.length) {
            _konamiIdx = 0;
            const active = document.body.classList.toggle('matrix-theme');
            localStorage.setItem('argus_matrix', active ? '1' : '0');
            showToast(active ? '🟩 Matrix mode activado' : 'Matrix mode desactivado');
        }
    } else {
        _konamiIdx = 0;
    }
});
if (localStorage.getItem('argus_matrix') === '1') document.body.classList.add('matrix-theme');

// ============================================================
// V63: CUSTOM COLOR PICKER (extended palette panel)
// ============================================================
function _initCustomColorPicker() {
    const panel = document.getElementById('palette-panel');
    if (!panel) return;
    if (panel.querySelector('.custom-color-input')) return;
    const wrap = document.createElement('div');
    wrap.style.cssText = 'margin-top:10px;display:flex;align-items:center;gap:8px;';
    wrap.innerHTML = `
        <label style="font-size:11px;color:var(--text-d);">Custom:</label>
        <input type="color" class="custom-color-input" value="#B87333"
               style="width:28px;height:28px;border:none;border-radius:6px;cursor:pointer;background:none;padding:0;"
               oninput="_applyCustomColor(this.value)">`;
    panel.appendChild(wrap);
    const saved = localStorage.getItem('argus_custom_color');
    if (saved) { wrap.querySelector('input').value = saved; _applyCustomColor(saved); }
}
function _applyCustomColor(hex) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    const dr = Math.max(r-40,0), dg = Math.max(g-40,0), db = Math.max(b-40,0);
    document.documentElement.style.setProperty('--accent', hex);
    document.documentElement.style.setProperty('--accent-d', `rgb(${dr},${dg},${db})`);
    document.documentElement.style.setProperty('--accent-bg', `rgba(${r},${g},${b},0.08)`);
    document.documentElement.style.setProperty('--accent-glow', `rgba(${r},${g},${b},0.22)`);
    localStorage.setItem('argus_custom_color', hex);
}
document.addEventListener('DOMContentLoaded', _initCustomColorPicker);
window._applyCustomColor = _applyCustomColor;

// ============================================================
// V64: SORTABLE TABLE COLUMNS
// ============================================================
let _sortKey = null;
let _sortDir = 1;

function _sortScans(key) {
    if (_sortKey === key) _sortDir *= -1;
    else { _sortKey = key; _sortDir = -1; }

    // Update sort icons
    document.querySelectorAll('[id^="sort-"][id$="-icon"]').forEach(el => el.textContent = '');
    const iconEl = document.getElementById(`sort-${key}-icon`);
    if (iconEl) iconEl.textContent = _sortDir === -1 ? '↓' : '↑';

    const tbody = document.getElementById('results-table-body');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr[data-scan-id]'));
    if (rows.length === 0) return;

    rows.sort((a, b) => {
        if (key === 'risk') {
            const ra = parseFloat(a.querySelector('.risk-score-badge')?.textContent || '0');
            const rb = parseFloat(b.querySelector('.risk-score-badge')?.textContent || '0');
            return (ra - rb) * _sortDir;
        }
        if (key === 'machine') {
            const na = a.querySelector('.scan-machine-name')?.textContent?.trim() || '';
            const nb = b.querySelector('.scan-machine-name')?.textContent?.trim() || '';
            return na.localeCompare(nb) * _sortDir;
        }
        return 0;
    });

    rows.forEach((r, i) => {
        r.style.transition = 'opacity 0.15s';
        r.style.opacity = '0';
        setTimeout(() => {
            tbody.appendChild(r);
            r.style.opacity = '1';
        }, i * 25);
    });
}
window._sortScans = _sortScans;

// ============================================================
// V65: TABLE DENSITY TOGGLE
// ============================================================
function setTableDensity(density) {
    document.body.classList.remove('density-compact','density-spacious');
    if (density !== 'normal') document.body.classList.add(`density-${density}`);
    localStorage.setItem('argus_density', density);
}
window.setTableDensity = setTableDensity;
(function _initDensity() {
    const d = localStorage.getItem('argus_density');
    if (d) setTableDensity(d);
})();

// ============================================================
// V37: KEYBOARD SHORTCUT HANDLER
// ============================================================
let _kbdChordGAt = 0;
document.addEventListener('keydown', e => {
    const tag = (document.activeElement?.tagName || '').toLowerCase();
    const inInput = tag === 'input' || tag === 'textarea' || tag === 'select';

    // Ctrl+K: global search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        openGlobalSearch();
        return;
    }
    if (inInput) return;

    // "/" -> foco directo al buscador de scans
    if (e.key === '/') {
        e.preventDefault();
        document.getElementById('filter-search')?.focus();
        return;
    }

    if (e.key === '?') {
        const overlay = document.getElementById('kbd-overlay');
        if (overlay) overlay.classList.toggle('open');
        return;
    }
    if (e.key === 'Escape') {
        closeKbdOverlay();
        closeGlobalSearch();
        document.getElementById('critical-alert-banner')?.classList.remove('visible');
        return;
    }
    // Chords: "g s", "g o", "g d"
    const now = Date.now();
    const isChordWindow = (now - _kbdChordGAt) < 900;
    if (e.key === 'g' || e.key === 'G') {
        _kbdChordGAt = now;
        return;
    }
    if (isChordWindow) {
        _kbdChordGAt = 0;
        const k = String(e.key || '').toLowerCase();
        if (k === 's') { document.querySelector('[data-section="resultados"]')?.click(); return; }
        if (k === 'o') {
            document.querySelector('[data-section="oracle"]')?.click()
                || document.getElementById('ai-chat-btn')?.click();
            return;
        }
        if (k === 'd') { document.querySelector('[data-section="dashboard"]')?.click(); return; }
    }
    if (e.key === 'n' || e.key === 'N') {
        document.querySelector('#new-scan-btn,[data-action="new-scan"],[data-action="new"]')?.click();
        return;
    }
    if (e.key === '1') { const a = document.querySelector('[data-section="dashboard"]');  if (a) a.click(); }
    if (e.key === '2') { const a = document.querySelector('[data-section="resultados"]'); if (a) a.click(); }
    if (e.key === '3') { const a = document.querySelector('[data-section="tokens"]');     if (a) a.click(); }
    if (e.key === 'f' || e.key === 'F') { document.getElementById('filter-search')?.focus(); }
});

// ============================================================
// V33: BREADCRUMB helper
// ============================================================
function _setBreadcrumb(parts) {
    let container = document.getElementById('argus-breadcrumb');
    if (!container) {
        container = document.createElement('div');
        container.id = 'argus-breadcrumb';
        container.className = 'argus-breadcrumb';
        const mainContent = document.querySelector('.main-content');
        const header = document.querySelector('.panel-header');
        if (header && mainContent) mainContent.insertBefore(container, header.nextSibling);
    }
    container.innerHTML = parts.map((p, i) => {
        const isLast = i === parts.length - 1;
        const sep = i > 0 ? `<span class="sep">›</span>` : '';
        if (isLast) return `${sep}<span class="current">${p.label}</span>`;
        return `${sep}<a onclick="${p.onclick || ''}">${p.label}</a>`;
    }).join('');
}
window._setBreadcrumb = _setBreadcrumb;

// ============================================================
// 🖼 BACKGROUND CUSTOMIZER
// ============================================================

const BG_PRESETS = ['default','aurora','nebula','cyber','ocean','lava','forest','classic','midnight'];
const CURSOR_MODES = ['argus','system'];

function openBgCustomizer() {
    document.getElementById('bg-customizer')?.classList.add('open');
    _syncBgUI();
}
function closeBgCustomizer() {
    document.getElementById('bg-customizer')?.classList.remove('open');
}
window.openBgCustomizer  = openBgCustomizer;
window.closeBgCustomizer = closeBgCustomizer;

function _syncBgUI() {
    const cfg = _loadBgCfg();
    // Active preset card
    document.querySelectorAll('.bg-preset-card').forEach(c =>
        c.classList.toggle('active', c.dataset.preset === (cfg.preset || 'default')));
    // Active cursor option
    const curMode = cfg.cursor || 'argus';
    document.querySelectorAll('.bg-cursor-opt').forEach(b =>
        b.classList.toggle('active', b.dataset.cursor === curMode));
    // Sliders
    const ov = document.getElementById('bg-overlay-slider');
    const bl = document.getElementById('bg-blur-slider');
    const gr = document.getElementById('bg-grid-slider');
    if (ov) { ov.value = cfg.overlay ?? 72; document.getElementById('bg-overlay-val').textContent = (cfg.overlay ?? 72) + '%'; }
    if (bl) { bl.value = cfg.blur ?? 0;    document.getElementById('bg-blur-val').textContent   = (cfg.blur ?? 0) + 'px'; }
    if (gr) { gr.value = cfg.grid ?? 100;  document.getElementById('bg-grid-val').textContent   = (cfg.grid ?? 100) + '%'; }
    // Preview
    const prev = document.getElementById('bg-upload-preview');
    if (prev && cfg.customUrl) {
        prev.src = cfg.customUrl;
        prev.style.display = 'block';
    }
}

function _loadBgCfg() {
    try { return JSON.parse(localStorage.getItem('argus_bg') || '{}'); } catch(_) { return {}; }
}
function _saveBgCfg(patch) {
    const cfg = { ..._loadBgCfg(), ...patch };
    localStorage.setItem('argus_bg', JSON.stringify(cfg));
    return cfg;
}

function setBgPreset(preset) {
    const cfg = _saveBgCfg({ preset, customUrl: preset !== 'custom' ? undefined : _loadBgCfg().customUrl });
    if (preset && preset !== 'default') {
        try {
            ['--accent','--accent-d','--accent-rgb','--accent-bg','--accent-glow','--border','--border-m','--border-h']
                .forEach(v => document.documentElement.style.removeProperty(v));
        } catch(_) {}
    }
    _applyBg(cfg);
    _syncBgUI();
    try { window.dispatchEvent(new CustomEvent('argus:preset-changed', { detail: { preset } })); } catch(_) {}
}
window.setBgPreset = setBgPreset;

function setCursorMode(mode) {
    if (!CURSOR_MODES.includes(mode)) mode = 'argus';
    const cfg = _saveBgCfg({ cursor: mode });
    _applyCursor(cfg);
    _syncBgUI();
    if (window.showToast) {
        window.showToast(mode === 'system' ? '🖱 Puntero del sistema activado' : '🖱 Puntero Argus activado', 'success', { duration: 2000 });
    }
}
window.setCursorMode = setCursorMode;

function _applyCursor(cfg) {
    const mode = (cfg && cfg.cursor) || 'argus';
    document.body.classList.toggle('cursor-system', mode === 'system');
}

function handleBgUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
        const url = ev.target.result;
        const prev = document.getElementById('bg-upload-preview');
        if (prev) { prev.src = url; prev.style.display = 'block'; }
        // Try to store — if too large for localStorage, warn
        try {
            const cfg = _saveBgCfg({ preset: 'custom', customUrl: url });
            _applyBg(cfg);
            _syncBgUI();
        } catch(err) {
            showToast('Imagen demasiado grande para localStorage. Usa una imagen más pequeña.', 'error');
        }
    };
    reader.readAsDataURL(file);
}
window.handleBgUpload = handleBgUpload;

function updateBgOverlay(val) {
    document.getElementById('bg-overlay-val').textContent = val + '%';
    const cfg = _saveBgCfg({ overlay: parseInt(val) });
    _applyBg(cfg);
}
function updateBgBlur(val) {
    document.getElementById('bg-blur-val').textContent = val + 'px';
    const cfg = _saveBgCfg({ blur: parseInt(val) });
    _applyBg(cfg);
}
function updateBgGrid(val) {
    document.getElementById('bg-grid-val').textContent = val + '%';
    const cfg = _saveBgCfg({ grid: parseInt(val) });
    _applyBg(cfg);
}
window.updateBgOverlay = updateBgOverlay;
window.updateBgBlur    = updateBgBlur;
window.updateBgGrid    = updateBgGrid;

function resetBg() {
    localStorage.removeItem('argus_bg');
    document.body.classList.remove('cursor-system');
    BG_PRESETS.forEach(p => document.body.classList.remove(`bg-${p}`));
    _applyBg({});
    _syncBgUI();
    const prev = document.getElementById('bg-upload-preview');
    if (prev) { prev.src = ''; prev.style.display = 'none'; }
    const inp = document.getElementById('bg-file-input');
    if (inp) inp.value = '';
}
window.resetBg = resetBg;

function _applyBg(cfg) {
    const body      = document.body;
    const bgEl      = document.getElementById('argus-bg');
    const overlayEl = document.getElementById('argus-bg-overlay');
    const preset    = cfg.preset || 'default';
    const overlay   = cfg.overlay ?? 72;
    const blur      = cfg.blur    ?? 0;
    const grid      = cfg.grid    ?? 100;

    // Remove all bg preset classes
    BG_PRESETS.forEach(p => body.classList.remove(`bg-${p}`));

    if (preset === 'custom' && cfg.customUrl) {
        if (bgEl) { bgEl.style.backgroundImage = `url(${cfg.customUrl})`; bgEl.style.background = ''; }
    } else if (preset !== 'default') {
        body.classList.add(`bg-${preset}`);
        if (bgEl) bgEl.style.backgroundImage = '';
    } else {
        if (bgEl) { bgEl.style.backgroundImage = ''; bgEl.style.background = ''; }
    }

    // Overlay darkness
    if (overlayEl) {
        overlayEl.style.setProperty('--bg-overlay-color', `rgba(9,9,28,${overlay/100})`);
        overlayEl.style.background = `rgba(9,9,28,${overlay/100})`;
        overlayEl.style.backdropFilter = `blur(${blur}px)`;
        overlayEl.style.webkitBackdropFilter = `blur(${blur}px)`;
    }

    // Grid opacity
    document.documentElement.style.setProperty('--grid-opacity', grid / 100);

    // Cursor mode (argus / system)
    _applyCursor(cfg);
}

// ── Feature 355: Hover preview para preset cards ─────────────────────────
function _initPresetPreviews() {
    document.querySelectorAll('.bg-preset-card').forEach(card => {
        if (card.querySelector('.bg-preset-preview')) return;
        const label = card.querySelector('span')?.textContent || '';
        const bg    = card.style.background || card.style.backgroundImage || '';
        const inner = card.querySelector('div');
        const innerStyle = inner ? inner.style.cssText : '';

        const preview = document.createElement('div');
        preview.className = 'bg-preset-preview';
        preview.style.cssText = `background:${bg};`;
        preview.innerHTML = `
            <div style="position:absolute;inset:0;${innerStyle}pointer-events:none;"></div>
            <div style="position:absolute;top:8px;left:8px;right:8px;height:8px;background:rgba(255,255,255,0.08);border-radius:3px;"></div>
            <div style="position:absolute;top:22px;left:8px;width:40%;height:6px;background:rgba(255,255,255,0.05);border-radius:3px;"></div>
            <div style="position:absolute;top:34px;left:8px;right:8px;bottom:20px;background:rgba(0,0,0,0.2);border-radius:4px;"></div>
            <div class="bg-preset-preview-label">${label}</div>`;
        card.appendChild(preview);
    });
}

// Init on load
document.addEventListener('DOMContentLoaded', () => {
    const cfg = _loadBgCfg();
    if (cfg && Object.keys(cfg).length > 0) {
        _applyBg(cfg);
    } else {
        _applyCursor({});
    }

    // Feature 355: inject hover previews after customizer opens
    document.getElementById('bg-customizer')?.addEventListener('transitionend', _initPresetPreviews, { once: true });

    // Drag & drop on the upload area
    const uploadLabel = document.getElementById('bg-upload-label');
    if (uploadLabel) {
        uploadLabel.addEventListener('dragover', e => { e.preventDefault(); uploadLabel.style.borderColor = 'var(--accent)'; });
        uploadLabel.addEventListener('dragleave', () => { uploadLabel.style.borderColor = ''; });
        uploadLabel.addEventListener('drop', e => {
            e.preventDefault();
            uploadLabel.style.borderColor = '';
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                document.getElementById('bg-file-input').files = e.dataTransfer.files;
                handleBgUpload({ target: { files: [file] } });
            }
        });
    }
});

// Also close on Esc
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeBgCustomizer();
});

// ── Feature 360: Auto-switch día/noche ────────────────────────────────────
// Day (06:00-19:59): ocean (azul claro). Night (20:00-05:59): midnight (azul oscuro).
let _autoThemeTimer = null;

function _autoThemePreset() {
    const h = new Date().getHours();
    return (h >= 6 && h < 20) ? 'ocean' : 'midnight';
}

function _applyAutoTheme() {
    if (localStorage.getItem('argus_auto_theme') !== '1') return;
    setBgPreset(_autoThemePreset());
}

function _syncAutoThemeUI() {
    const on = localStorage.getItem('argus_auto_theme') === '1';
    const dot   = document.getElementById('auto-theme-dot');
    const label = document.getElementById('auto-theme-label');
    if (dot) {
        dot.style.background = on ? 'var(--accent, #06b6d4)' : '#333';
        const thumb = dot.querySelector('span');
        if (thumb) thumb.style.left = on ? '16px' : '2px';
    }
    if (label) {
        const h = new Date().getHours();
        const next = on ? (_autoThemePreset() === 'ocean' ? 'Día → Ocean. Noche → Midnight' : 'Noche → Midnight. Día → Ocean') : 'Desactivado';
        label.textContent = next;
    }
}

function toggleAutoTheme() {
    const on = localStorage.getItem('argus_auto_theme') === '1';
    localStorage.setItem('argus_auto_theme', on ? '0' : '1');
    _syncAutoThemeUI();
    if (!on) {
        _applyAutoTheme();
        if (_autoThemeTimer) clearInterval(_autoThemeTimer);
        _autoThemeTimer = setInterval(_applyAutoTheme, 60000);
    } else {
        if (_autoThemeTimer) { clearInterval(_autoThemeTimer); _autoThemeTimer = null; }
    }
}
window.toggleAutoTheme = toggleAutoTheme;

document.addEventListener('DOMContentLoaded', () => {
    _syncAutoThemeUI();
    if (localStorage.getItem('argus_auto_theme') === '1') {
        _applyAutoTheme();
        _autoThemeTimer = setInterval(_applyAutoTheme, 60000);
    }
});

// ============================================================
// ④ PARTÍCULAS FLOTANTES
// ============================================================
(function initParticles() {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let W, H, particles = [];

    function resize() {
        W = canvas.width  = window.innerWidth;
        H = canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize, { passive: true });

    const N = 55;
    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#B87333';

    for (let i = 0; i < N; i++) {
        particles.push({
            x: Math.random() * 1920,
            y: Math.random() * 1080,
            r: Math.random() * 1.4 + 0.3,
            vx: (Math.random() - 0.5) * 0.18,
            vy: (Math.random() - 0.5) * 0.18,
            o: Math.random() * 0.5 + 0.1,
        });
    }

    let raf;
    function draw() {
        ctx.clearRect(0, 0, W, H);
        const col = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#B87333';
        particles.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x % W, p.y % H, p.r, 0, Math.PI * 2);
            ctx.fillStyle = col;
            ctx.globalAlpha = p.o;
            ctx.fill();
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0) p.x = W;
            if (p.x > W) p.x = 0;
            if (p.y < 0) p.y = H;
            if (p.y > H) p.y = 0;
        });
        ctx.globalAlpha = 1;

        // Draw faint connection lines between nearby particles
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx*dx + dy*dy);
                if (dist < 120) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x % W, particles[i].y % H);
                    ctx.lineTo(particles[j].x % W, particles[j].y % H);
                    ctx.strokeStyle = col;
                    ctx.globalAlpha = (1 - dist / 120) * 0.08;
                    ctx.lineWidth = 0.6;
                    ctx.stroke();
                    ctx.globalAlpha = 1;
                }
            }
        }
        raf = requestAnimationFrame(draw);
    }
    draw();

    // Pause when tab hidden to save resources
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) cancelAnimationFrame(raf);
        else draw();
    });
})();

// ============================================================
// ⑤ ANIMACIÓN DE ENTRADA
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    // Sidebar
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) { sidebar.style.opacity = '0'; sidebar.style.transform = 'translateX(-20px)';
        requestAnimationFrame(() => {
            sidebar.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            sidebar.style.opacity = '1'; sidebar.style.transform = '';
        });
    }
    // Header
    const header = document.querySelector('.panel-header');
    if (header) { header.style.opacity = '0'; header.style.transform = 'translateY(-16px)';
        setTimeout(() => {
            header.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            header.style.opacity = '1'; header.style.transform = '';
        }, 120);
    }
});

// ============================================================
// ⑥ HOVER 3D TILT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    function applyTilt(el) {
        el.addEventListener('mousemove', e => {
            const rect = el.getBoundingClientRect();
            const cx = rect.left + rect.width  / 2;
            const cy = rect.top  + rect.height / 2;
            const dx = (e.clientX - cx) / (rect.width  / 2);
            const dy = (e.clientY - cy) / (rect.height / 2);
            el.style.transform = `perspective(900px) rotateY(${dx * 5}deg) rotateX(${-dy * 5}deg) translateY(-4px)`;
        });
        el.addEventListener('mouseleave', () => {
            el.style.transform = '';
            el.style.transition = 'transform 0.4s cubic-bezier(0.4,0,0.2,1)';
            setTimeout(() => el.style.transition = '', 400);
        });
    }
    document.querySelectorAll('.tilt-card').forEach(applyTilt);

    // Also observe for dynamically added tilt-cards
    const obs = new MutationObserver(muts => {
        muts.forEach(m => m.addedNodes.forEach(n => {
            if (n.nodeType === 1) {
                if (n.classList?.contains('tilt-card')) applyTilt(n);
                n.querySelectorAll?.('.tilt-card').forEach(applyTilt);
            }
        }));
    });
    obs.observe(document.body, { childList: true, subtree: true });
});

// ============================================================
// ⑨ TYPING ANIMATION EN EL SALUDO
// ============================================================
function _typeText(el, text, speed = 38) {
    if (!el) return;
    el.classList.add('typing-cursor');
    el.textContent = '';
    let i = 0;
    const interval = setInterval(() => {
        el.textContent += text[i++];
        if (i >= text.length) {
            clearInterval(interval);
            setTimeout(() => el.classList.remove('typing-cursor'), 800);
        }
    }, speed);
}

// Override greeting rendering to use typing effect
const _origLoadDashboard = window.loadDashboard || null;
const _greetingDone = { done: false };

document.addEventListener('DOMContentLoaded', () => {
    // Hook into loadDashboard to add typing effect
    const greetEl = document.getElementById('greeting-text');
    if (greetEl && !_greetingDone.done) {
        _greetingDone.done = true;
        setTimeout(() => {
            const h = new Date().getHours();
            const saludo = h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches';
            // Extract name from Jinja2-rendered element (panel.js is static, can't use template syntax)
            const rendered = greetEl.textContent.trim();
            const name = rendered.replace(/^(buenos\s+d[íi]as|buenas\s+tardes|buenas\s+noches|bienvenido)[,\s]*/i, '').replace(/!$/, '').trim() || 'Staff';
            _typeText(greetEl, `${saludo}, ${name}!`, 40);
        }, 500);
    }
});

// ============================================================
// ② SPARKLINES EN STAT CARDS
// ============================================================
function _drawSparkline(canvasId, values, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !values || values.length < 2) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const min = Math.min(...values);
    const max = Math.max(...values) || 1;
    const range = max - min || 1;
    ctx.clearRect(0, 0, W, H);

    const pts = values.map((v, i) => ({
        x: (i / (values.length - 1)) * W,
        y: H - ((v - min) / range) * (H - 4) - 2,
    }));

    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, color + '55');
    grad.addColorStop(1, color + '00');

    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    pts.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    pts.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.8;
    ctx.stroke();
}
window._drawSparkline = _drawSparkline;

// Draw placeholder sparklines on load (random-ish trend)
document.addEventListener('DOMContentLoaded', () => {
    const makeTrend = (end, len = 8) => {
        const arr = [];
        let v = end * 0.6;
        for (let i = 0; i < len; i++) {
            v += (Math.random() - 0.4) * (end * 0.15);
            arr.push(Math.max(0, v));
        }
        arr[arr.length - 1] = end;
        return arr;
    };
    setTimeout(() => {
        const ts = parseInt(document.getElementById('total-scans')?.textContent) || 20;
        const ti = parseInt(document.getElementById('total-issues')?.textContent) || 8;
        const um = parseInt(document.getElementById('unique-machines')?.textContent) || 15;
        const at = parseInt(document.getElementById('active-tokens')?.textContent) || 5;
        const accent = (getComputedStyle(document.body).getPropertyValue('--accent') || '#B87333').trim() || '#B87333';
        _drawSparkline('spark-scans',    makeTrend(ts), accent);
        _drawSparkline('spark-issues',   makeTrend(ti), '#f43f5e');
        _drawSparkline('spark-machines', makeTrend(um), '#06b6d4');
        _drawSparkline('spark-tokens',   makeTrend(at), '#10b981');
    }, 1200);
});

// Re-pinta el sparkline 'scans' al cambiar de preset (Personalizar Fondo)
window.addEventListener('argus:preset-changed', () => {
    setTimeout(() => {
        const ts = parseInt(document.getElementById('total-scans')?.textContent) || 20;
        const accent = (getComputedStyle(document.body).getPropertyValue('--accent') || '#B87333').trim() || '#B87333';
        const arr = [];
        let v = ts * 0.6;
        for (let i = 0; i < 8; i++) { v += (Math.random() - 0.4) * (ts * 0.15); arr.push(Math.max(0, v)); }
        arr[arr.length - 1] = ts;
        if (typeof _drawSparkline === 'function') _drawSparkline('spark-scans', arr, accent);
    }, 60);
});

// ============================================================
// ③ SCAN DETAIL HEADER DINÁMICO
// ============================================================
function _setDetailRiskTheme(riskScore) {
    const sec = document.getElementById('issues-detail-section');
    if (!sec) return;
    sec.classList.remove('risk-critical','risk-suspicious','risk-clean');
    if      (riskScore >= 70) sec.classList.add('risk-critical');
    else if (riskScore >= 30) sec.classList.add('risk-suspicious');
    else                       sec.classList.add('risk-clean');
}
window._setDetailRiskTheme = _setDetailRiskTheme;

// ============================================================
// ⑪ FOCUS MODE toggle
// ============================================================
function toggleFocusMode() {
    const on = document.body.classList.toggle('focus-mode');
    showToast(on ? 'Modo focus activado — mueve el mouse a la sidebar para verla' : 'Modo focus desactivado', 'info');
    localStorage.setItem('argus_focus', on ? '1' : '0');
}
window.toggleFocusMode = toggleFocusMode;
document.addEventListener('DOMContentLoaded', () => {
    if (localStorage.getItem('argus_focus') === '1') document.body.classList.add('focus-mode');
});

// ============================================================
// ⑫ FLIP ANIMATION EN EL animateNumber OVERRIDE
// ============================================================
const _origAnimateNumber = animateNumber;
window.animateNumber = function(el, target, duration) {
    if (!el) return;
    el.style.perspective = '300px';
    const orig = _origAnimateNumber;
    // Wrap each digit update with a quick flip class on final value
    orig(el, target, duration || 750);
    setTimeout(() => {
        el.classList.add('num-flip');
        el.addEventListener('animationend', () => el.classList.remove('num-flip'), { once: true });
    }, duration || 750);
};

// ============================================================
// HOOK viewScanDetails to set risk theme
// ============================================================
const _origViewScan = window.viewScanDetails;
if (_origViewScan) {
    window.viewScanDetails = async function(scanId) {
        await _origViewScan(scanId);
        // Apply risk theme after data is loaded
        const rs = _currentScanData?.risk_score;
        if (rs !== undefined && rs !== null) _setDetailRiskTheme(rs);
        // Auto-enable focus mode preference
        if (localStorage.getItem('argus_focus') === '1') document.body.classList.add('focus-mode');
    };
}


/* ════════════════════════════════════════════════════════════════════════
// Feature 382: badges acumulados del jugador basados en historial de scans
function _computePlayerBadges(data) {
    const total   = data.scans_total || 0;
    const hacks   = data.hacks   || 0;
    const cleans  = data.cleans  || 0;
    const avgRisk = data.avg_risk || 0;

    const BADGE_DEFS = [
        { id: 'veteran',   icon: '🏅', label: 'Veterano',        color: '#f59e0b', cond: total >= 10,        tip: `${total} scans en total`       },
        { id: 'clean5',    icon: '✅', label: 'Limpio ×5',       color: '#22c55e', cond: cleans >= 5,        tip: `${cleans} scans limpios`        },
        { id: 'clean10',   icon: '🌟', label: 'Limpio ×10',      color: '#10b981', cond: cleans >= 10,       tip: `${cleans} scans limpios`        },
        { id: 'hacked',    icon: '🔴', label: 'Hack detectado',  color: '#ef4444', cond: hacks >= 1,         tip: `${hacks} veredicto(s) hack`     },
        { id: 'recidivo',  icon: '⚑',  label: 'Reincidente',     color: '#f97316', cond: hacks >= 2,         tip: `${hacks} hacks detectados`      },
        { id: 'highrisk',  icon: '⚠️', label: 'Alto riesgo',     color: '#fbbf24', cond: avgRisk >= 50,      tip: `Risk promedio: ${avgRisk}`      },
        { id: 'lowrisk',   icon: '🛡️', label: 'Bajo riesgo',     color: '#3b82f6', cond: avgRisk < 20 && total >= 3, tip: `Risk promedio: ${avgRisk}` },
        { id: 'prolific',  icon: '📊', label: 'Frecuente',       color: '#8b5cf6', cond: total >= 25,        tip: `${total} scans registrados`     },
    ];

    const earned = BADGE_DEFS.filter(b => b.cond);
    if (!earned.length) return '';

    return `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">
        ${earned.map(b => `
            <span title="${b.tip}" style="
                display:inline-flex;align-items:center;gap:4px;
                padding:3px 9px;border-radius:12px;font-size:11.5px;font-weight:700;
                background:${b.color}18;border:1px solid ${b.color}44;color:${b.color};">
                ${b.icon} ${b.label}
            </span>`).join('')}
    </div>`;
}

 /* Pack 33 — V#47 Timeline visual del jugador
 * Muestra todos los eventos del jugador (scans, verdict changes, notas)
 * ordenados cronológicamente. Modal full-height con timeline vertical.
 * ════════════════════════════════════════════════════════════════════════ */
async function openPlayerTimelineModal(username, opts) {
    if (!username) return;
    opts = opts || {};
    const sinceDays = opts.since_days || 180;
    const limit     = opts.limit || 80;

    // Modal mount
    let root = document.getElementById('argus-timeline-modal');
    if (!root) {
        root = document.createElement('div');
        root.id = 'argus-timeline-modal';
        root.className = 'modal';
        root.innerHTML = `
            <div class="modal-content" style="max-width:780px; width:96vw; max-height:90vh; overflow-y:auto;">
                <div class="modal-header" style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                    <h3 style="margin:0; display:flex; align-items:center; gap:8px;">
                        <span aria-hidden="true">📍</span>
                        <span id="argus-timeline-title">Timeline del jugador</span>
                    </h3>
                    <div style="display:flex; gap:6px;">
                        <select id="argus-timeline-range"
                                class="select-sm"
                                style="padding:4px 8px; font-size:13px; background:rgba(0,0,0,.18); color:var(--text-h); border:1px solid var(--border, rgba(255,255,255,.1)); border-radius:6px;">
                            <option value="30">30 días</option>
                            <option value="90">90 días</option>
                            <option value="180" selected>180 días</option>
                            <option value="365">1 año</option>
                            <option value="730">2 años</option>
                        </select>
                        <button class="modal-close" type="button"
                                onclick="document.getElementById('argus-timeline-modal').classList.remove('show')"
                                aria-label="Cerrar">×</button>
                    </div>
                </div>
                <div class="modal-body" id="argus-timeline-body" style="padding:14px 18px;">
                    <div style="text-align:center; padding:40px 0; color:var(--text-d);">
                        Cargando timeline…
                    </div>
                </div>
            </div>`;
        document.body.appendChild(root);
        // Click fuera cierra
        root.addEventListener('click', (e) => {
            if (e.target === root) root.classList.remove('show');
        });
        // Cambio de rango refrescar
        root.querySelector('#argus-timeline-range').addEventListener('change', (e) => {
            openPlayerTimelineModal(root.dataset.username, {
                since_days: parseInt(e.target.value, 10) || 180,
                limit
            });
        });
    }
    root.dataset.username = username;
    const titleEl = root.querySelector('#argus-timeline-title');
    const esc = (typeof _qsEscapeSafe === 'function') ? _qsEscapeSafe : (s) => String(s);
    titleEl.innerHTML = `<img src="https://mc-heads.net/avatar/${encodeURIComponent(username)}/32"
        alt="${esc(username)}" width="32" height="32"
        style="border-radius:4px;image-rendering:pixelated;vertical-align:middle;margin-right:6px;"
        onerror="this.style.display='none'">Timeline · ${esc(username)}`;
    root.querySelector('#argus-timeline-range').value = String(sinceDays);
    root.classList.add('show');

    const body = root.querySelector('#argus-timeline-body');
    body.innerHTML = `
        <div style="text-align:center; padding:40px 0; color:var(--text-d);">
            Cargando timeline…
        </div>`;

    let data;
    try {
        const r = await fetch(
            `/api/players/${encodeURIComponent(username)}/timeline?` +
            `limit=${limit}&since_days=${sinceDays}`,
            { credentials: 'include' }
        );
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        data = await r.json();
    } catch (e) {
        body.innerHTML = `
            <div style="text-align:center; padding:40px 16px; color:#ef4444;">
                <div style="font-size:32px; margin-bottom:8px;">⚠️</div>
                <div>Error cargando timeline: ${_qsEscapeSafe(e.message || e)}</div>
            </div>`;
        return;
    }

    const events = (data.events || []);
    if (!events.length) {
        body.innerHTML = `
            <div style="text-align:center; padding:40px 16px; color:var(--text-d);">
                <div style="font-size:32px; margin-bottom:8px;">📭</div>
                <div>Sin actividad para <b>${_qsEscapeSafe(username)}</b> en los últimos ${sinceDays} días</div>
            </div>`;
        return;
    }

    // Feature 382: calcular badges del jugador a partir del timeline
    const badgesHtml = _computePlayerBadges(data);

    // Stats header
    const statsRow = `
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; padding:10px 12px;
                    background:rgba(184,115,51,.08); border:1px solid var(--border, rgba(255,255,255,.08));
                    border-radius:8px; font-size:13px;">
            <div><b>${data.scans_total || 0}</b> scan${data.scans_total === 1 ? '' : 's'}</div>
            ${data.hacks    ? `<div style="color:#ef4444;"><b>${data.hacks}</b> hack${data.hacks === 1 ? '' : 's'}</div>` : ''}
            ${data.cleans   ? `<div style="color:#22c55e;"><b>${data.cleans}</b> clean${data.cleans === 1 ? '' : 's'}</div>` : ''}
            ${data.pendings ? `<div style="color:#fbbf24;"><b>${data.pendings}</b> pending</div>` : ''}
            ${data.avg_risk !== null && data.avg_risk !== undefined
                ? `<div>risk avg: <b>${data.avg_risk}</b></div>` : ''}
        </div>
        ${badgesHtml}
        <div id="argus-timeline-risk-profile" style="margin-bottom:12px;"></div>`;

    // Timeline items
    const items = events.map(ev => _renderTimelineEvent(ev)).join('');

    body.innerHTML = `
        ${statsRow}
        <div class="argus-timeline" style="position:relative; padding-left:36px;">
            <div style="position:absolute; left:13px; top:6px; bottom:6px; width:2px;
                        background:linear-gradient(180deg, rgba(184,115,51,.5), rgba(184,115,51,.05));"></div>
            ${items}
        </div>`;

    // Pack 36 — Inyectar Player Risk Profile asíncrono
    try {
        const profileRes = await fetch(
            `/api/players/${encodeURIComponent(username)}/risk-profile?since_days=${Math.max(sinceDays, 365)}`,
            { credentials: 'include' }
        );
        if (profileRes.ok) {
            const prof = await profileRes.json();
            if (prof && prof.available !== false && prof.total_scans > 0) {
                _renderTimelineRiskProfile(body.querySelector('#argus-timeline-risk-profile'), prof);
            }
        }
    } catch (_e) { /* silently */ }
}

function _renderTimelineRiskProfile(container, prof) {
    if (!container || !prof) return;
    const trendIcon = prof.trend === 'rising' ? '📈' :
                      prof.trend === 'falling' ? '📉' :
                      prof.trend === 'stable' ? '➡️' : '❓';
    const trendColor = prof.trend === 'rising' ? '#ef4444' :
                       prof.trend === 'falling' ? '#22c55e' :
                       prof.trend === 'stable' ? '#60a5fa' : 'var(--text-d)';
    const trendLabel = prof.trend === 'rising' ? 'subiendo' :
                       prof.trend === 'falling' ? 'bajando' :
                       prof.trend === 'stable' ? 'estable' : 'datos insuficientes';

    let alertBox = '';
    if (prof.regression_alert) {
        const escape = (typeof _qsEscapeSafe === 'function') ? _qsEscapeSafe : (s) => String(s);
        alertBox = `
            <div style="margin-top:8px;padding:8px 10px;background:rgba(239,68,68,.10);border:1px solid #ef4444;border-radius:6px;font-size:12.5px;color:#fca5a5;">
                ⚠️ <b>Regresión detectada</b>: ${escape(prof.regression_reason || '')}
            </div>`;
    }

    container.innerHTML = `
        <div style="padding:10px 12px;background:rgba(96,165,250,.06);border:1px solid var(--border, rgba(96,165,250,.2));border-radius:8px;font-size:12.5px;">
            <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;">
                <div><span style="color:var(--text-d);">Risk avg:</span> <b>${prof.risk_avg ?? '—'}</b></div>
                <div><span style="color:var(--text-d);">Min:</span> <b>${prof.risk_min ?? '—'}</b></div>
                <div><span style="color:var(--text-d);">Max:</span> <b>${prof.risk_max ?? '—'}</b></div>
                <div style="color:${trendColor};">${trendIcon} <b>${trendLabel}</b></div>
                ${prof.risk_recent && prof.risk_recent.length
                    ? `<div style="color:var(--text-d);font-size:11.5px;">Últimos: ${prof.risk_recent.join(', ')}</div>`
                    : ''}
            </div>
            ${alertBox}
        </div>`;
}

function _renderTimelineEvent(ev) {
    const ts = ev.ts ? _parseUTC(ev.ts) : null;
    const tsStr = ts && !isNaN(ts.getTime())
        ? ts.toLocaleString('es-AR', {
            year:'numeric', month:'short', day:'numeric',
            hour:'2-digit', minute:'2-digit'
        })
        : '—';

    const escape = (typeof _qsEscapeSafe === 'function')
        ? _qsEscapeSafe
        : (s) => String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    let icon = '📌';
    let color = 'var(--accent, #B87333)';
    let title = '';
    let body  = '';
    let cta   = '';

    if (ev.kind === 'scan') {
        const v = (ev.verdict || '').toLowerCase();
        if (v === 'hack')   { icon = '🔴'; color = '#ef4444'; }
        else if (v === 'clean')  { icon = '🟢'; color = '#22c55e'; }
        else if (v === 'pending'){ icon = '🟡'; color = '#fbbf24'; }
        else                     { icon = '🔵'; color = '#60a5fa'; }
        title = `Scan #${ev.scan_id}`;
        const parts = [];
        if (ev.risk_score !== null && ev.risk_score !== undefined) {
            parts.push(`risk <b>${ev.risk_score}</b>`);
        }
        if (ev.criticals) parts.push(`<span style="color:#ef4444;">${ev.criticals} crítico${ev.criticals === 1 ? '' : 's'}</span>`);
        if (ev.issues)    parts.push(`${ev.issues} hallazgo${ev.issues === 1 ? '' : 's'}`);
        if (ev.files)     parts.push(`${ev.files.toLocaleString('es-AR')} archivos`);
        if (ev.duration_ms) parts.push(`${(ev.duration_ms/1000).toFixed(1)}s`);
        if (ev.machine)   parts.push(`<span style="opacity:.7;">${escape(ev.machine)}</span>`);
        if (ev.country)   parts.push(`${escape(ev.country)}`);
        body = parts.join(' · ');
        cta = `<a href="javascript:void(0)" onclick="if(window.openScanDetail) window.openScanDetail(${ev.scan_id})"
                  style="font-size:12px; color:var(--accent, #B87333); text-decoration:none;">Abrir scan →</a>`;
    } else if (ev.kind === 'verdict_change') {
        icon = '⚖️';
        color = '#8b5cf6';
        title = `Veredicto cambiado a "${escape(ev.verdict || '?')}"`;
        body = ev.reason
            ? `<div style="font-style:italic; opacity:.85;">"${escape(ev.reason)}"</div>` +
              (ev.changed_by ? `<div style="font-size:11px; opacity:.6;">por ${escape(ev.changed_by)}</div>` : '')
            : (ev.changed_by ? `por ${escape(ev.changed_by)}` : '');
        cta = `<a href="javascript:void(0)" onclick="if(window.openScanDetail) window.openScanDetail(${ev.scan_id})"
                  style="font-size:12px; color:#8b5cf6; text-decoration:none;">Ver scan →</a>`;
    } else if (ev.kind === 'note') {
        icon = '📝';
        color = '#06b6d4';
        title = `Nota de ${escape(ev.author || 'staff')}`;
        body = `<div style="opacity:.9;">${escape(ev.body || '')}</div>`;
        cta = `<a href="javascript:void(0)" onclick="if(window.openScanDetail) window.openScanDetail(${ev.scan_id})"
                  style="font-size:12px; color:#06b6d4; text-decoration:none;">Ver scan →</a>`;
    } else {
        title = ev.kind || 'evento';
        body = '';
    }

    return `
        <div class="argus-timeline-item" style="position:relative; margin-bottom:14px; padding:10px 12px;
              background:rgba(255,255,255,.02); border:1px solid var(--border, rgba(255,255,255,.06));
              border-radius:8px;">
            <div style="position:absolute; left:-32px; top:8px; width:26px; height:26px;
                        border-radius:50%; background:rgba(20,18,28,.95);
                        border:2px solid ${color}; display:flex; align-items:center; justify-content:center;
                        font-size:13px; box-shadow:0 0 10px ${color}88;">
                ${icon}
            </div>
            <div style="display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:4px;">
                <div style="font-weight:600; font-size:14px;">${escape(title)}</div>
                <div style="font-size:11px; opacity:.6; white-space:nowrap;">${escape(tsStr)}</div>
            </div>
            <div style="font-size:13px; line-height:1.5; opacity:.92;">${body}</div>
            ${cta ? `<div style="margin-top:6px; text-align:right;">${cta}</div>` : ''}
        </div>`;
}

window.openPlayerTimelineModal = openPlayerTimelineModal;


/* ════════════════════════════════════════════════════════════════════════
 * Pack 35 — AI Quality Dashboard
 * Muestra precision/recall/f1/drift del ensemble vs verdicts humanos +
 * sugerencias de adaptive thresholds + retrain trigger + top FP candidates
 * ════════════════════════════════════════════════════════════════════════ */
async function openAIQualityDashboard(opts) {
    opts = opts || {};
    const sinceDays = opts.since_days || 90;

    let root = document.getElementById('argus-ai-quality-modal');
    if (!root) {
        root = document.createElement('div');
        root.id = 'argus-ai-quality-modal';
        root.className = 'modal';
        root.innerHTML = `
            <div class="modal-content" style="max-width:880px; width:96vw; max-height:92vh; overflow-y:auto;">
                <div class="modal-header" style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
                    <h3 style="margin:0;display:flex;align-items:center;gap:8px;">
                        <span aria-hidden="true">🧠</span>
                        <span>Dashboard de calidad IA</span>
                    </h3>
                    <div style="display:flex;gap:6px;">
                        <select id="argus-aiq-range" class="select-sm" style="padding:4px 8px;font-size:13px;background:rgba(0,0,0,.18);color:var(--text-h);border:1px solid var(--border, rgba(255,255,255,.1));border-radius:6px;">
                            <option value="30">30 días</option>
                            <option value="60">60 días</option>
                            <option value="90" selected>90 días</option>
                            <option value="180">180 días</option>
                            <option value="365">1 año</option>
                        </select>
                        <button class="modal-close" type="button" onclick="document.getElementById('argus-ai-quality-modal').classList.remove('show')" aria-label="Cerrar">×</button>
                    </div>
                </div>
                <div class="modal-body" id="argus-aiq-body" style="padding:14px 18px;">
                    <div style="text-align:center;padding:40px 0;color:var(--text-d);">Cargando métricas IA…</div>
                </div>
            </div>`;
        document.body.appendChild(root);
        root.addEventListener('click', (e) => { if (e.target === root) root.classList.remove('show'); });
        root.querySelector('#argus-aiq-range').addEventListener('change', (e) => {
            openAIQualityDashboard({ since_days: parseInt(e.target.value, 10) || 90 });
        });
    }
    root.querySelector('#argus-aiq-range').value = String(sinceDays);
    root.classList.add('show');

    const body = root.querySelector('#argus-aiq-body');
    body.innerHTML = `<div style="text-align:center;padding:40px 0;color:var(--text-d);">Cargando métricas IA…</div>`;

    let metrics, suggestions;
    try {
        const [m, s] = await Promise.all([
            fetch(`/api/ai-quality/metrics?since_days=${sinceDays}`, { credentials: 'include' }).then(r => r.json()),
            fetch(`/api/ai-quality/learn-fp-suggestions?limit=15`, { credentials: 'include' }).then(r => r.json()),
        ]);
        metrics = m; suggestions = s;
    } catch (e) {
        body.innerHTML = `<div style="padding:30px;text-align:center;color:#ef4444;">Error: ${(e.message || e)}</div>`;
        return;
    }

    if (!metrics || metrics.available === false) {
        body.innerHTML = `<div style="padding:30px;text-align:center;color:var(--text-d);">Módulo ai_quality no disponible en el servidor.</div>`;
        return;
    }
    const m = metrics.metrics || {};
    const sugg = metrics.suggestion || {};
    const retrain = metrics.retrain || {};

    const pct = (v) => v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;
    const escape = (typeof _qsEscapeSafe === 'function')
        ? _qsEscapeSafe
        : (s) => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const colorFor = (v, good = 0.75, ok = 0.60) => {
        if (v === null || v === undefined) return 'var(--text-d)';
        return v >= good ? '#22c55e' : v >= ok ? '#fbbf24' : '#ef4444';
    };

    const stat = (label, val, color, hint) => `
        <div style="flex:1;min-width:130px;padding:12px 14px;background:rgba(255,255,255,.02);border:1px solid var(--border, rgba(255,255,255,.06));border-radius:10px;">
            <div style="font-size:10px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px;">${label}</div>
            <div style="font-size:24px;font-weight:700;color:${color};font-variant-numeric:tabular-nums;">${val}</div>
            ${hint ? `<div style="font-size:11px;color:var(--text-d);opacity:.8;margin-top:4px;">${hint}</div>` : ''}
        </div>`;

    const cm = `
        <div style="margin-top:14px;padding:10px 12px;background:rgba(0,0,0,.2);border:1px solid var(--border, rgba(255,255,255,.05));border-radius:8px;font-size:13px;">
            <div style="font-weight:600;margin-bottom:8px;color:var(--text-h);">Confusion matrix</div>
            <div style="display:grid;grid-template-columns:auto 1fr 1fr;gap:6px;align-items:center;">
                <div></div>
                <div style="font-size:11px;color:var(--text-d);text-align:center;">Humano: hack</div>
                <div style="font-size:11px;color:var(--text-d);text-align:center;">Humano: clean</div>
                <div style="font-size:11px;color:var(--text-d);">IA: hack</div>
                <div style="text-align:center;padding:6px;background:rgba(34,197,94,.10);border-radius:6px;color:#22c55e;font-weight:700;">${m.tp || 0} <span style="opacity:.6;font-weight:400;">TP</span></div>
                <div style="text-align:center;padding:6px;background:rgba(239,68,68,.10);border-radius:6px;color:#ef4444;font-weight:700;">${m.fp || 0} <span style="opacity:.6;font-weight:400;">FP</span></div>
                <div style="font-size:11px;color:var(--text-d);">IA: clean</div>
                <div style="text-align:center;padding:6px;background:rgba(239,68,68,.10);border-radius:6px;color:#ef4444;font-weight:700;">${m.fn || 0} <span style="opacity:.6;font-weight:400;">FN</span></div>
                <div style="text-align:center;padding:6px;background:rgba(34,197,94,.10);border-radius:6px;color:#22c55e;font-weight:700;">${m.tn || 0} <span style="opacity:.6;font-weight:400;">TN</span></div>
            </div>
            ${m.ambiguous ? `<div style="font-size:11px;color:var(--text-d);margin-top:6px;">+ ${m.ambiguous} en zona ambigua (SOSPECHOSO) — no contados.</div>` : ''}
        </div>`;

    const suggColor = sugg.action === 'raise' ? '#fbbf24' : sugg.action === 'lower' ? '#60a5fa' : '#22c55e';
    const suggIcon  = sugg.action === 'raise' ? '⬆️' : sugg.action === 'lower' ? '⬇️' : '✅';
    const applyBtn  = (sugg.action === 'raise' || sugg.action === 'lower')
        ? `<button onclick="applyAIThresholdSuggestion(${sugg.delta})" style="margin-top:10px;padding:6px 14px;background:${suggColor};color:#000;border:0;border-radius:6px;font-weight:600;font-size:12px;cursor:pointer;">Aplicar (${sugg.delta > 0 ? '+' : ''}${sugg.delta})</button>`
        : '';

    const suggBox = `
        <div style="margin-top:14px;padding:12px 14px;background:rgba(${sugg.action === 'raise' ? '251,191,36' : sugg.action === 'lower' ? '96,165,250' : '34,197,94'},.08);border:1px solid ${suggColor}55;border-radius:10px;">
            <div style="font-weight:600;font-size:13px;color:${suggColor};margin-bottom:6px;">${suggIcon} Sugerencia threshold</div>
            <div style="font-size:13px;line-height:1.5;color:var(--text-h);">${escape(sugg.rationale || '')}</div>
            <div style="font-size:11px;color:var(--text-d);margin-top:4px;">Confianza: ${escape(sugg.confidence || 'low')}</div>
            ${applyBtn}
        </div>`;

    const retrainColor = retrain.urgency === 'high' ? '#ef4444' : retrain.urgency === 'medium' ? '#fbbf24' : 'var(--text-d)';
    const retrainBox = retrain.should_retrain ? `
        <div style="margin-top:10px;padding:10px 12px;background:rgba(239,68,68,.06);border:1px solid ${retrainColor}55;border-radius:10px;">
            <div style="font-weight:600;font-size:13px;color:${retrainColor};margin-bottom:5px;">🔄 Retrain RF recomendado (${escape(retrain.urgency)})</div>
            <ul style="margin:0;padding-left:18px;font-size:12px;color:var(--text-h);">
                ${(retrain.reasons || []).map(r => `<li>${escape(r)}</li>`).join('')}
            </ul>
        </div>` : '';

    const fpRows = (suggestions && suggestions.rows && suggestions.rows.length)
        ? suggestions.rows.map(r => `
            <tr style="border-bottom:1px solid var(--border, rgba(255,255,255,.05));">
                <td style="padding:6px 10px;font-family:monospace;font-size:11.5px;word-break:break-all;">${escape(r.path_full || '')}</td>
                <td style="padding:6px 10px;text-align:center;font-weight:600;">${r.count || 0}</td>
                <td style="padding:6px 10px;text-align:right;">
                    <button onclick="(async function(){
                        if (!confirm('Aplicar learn-fp para fragmento: ${escape(r.fragment)}?')) return;
                        const resp = await fetch('/api/staff/learn-fp', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({fragment: ${JSON.stringify(r.fragment)}}) });
                        const d = await resp.json();
                        if (resp.ok) { if (window.showToast) showToast('learn-fp aplicado', 'success'); }
                        else { alert('Error: ' + (d.error || resp.status)); }
                    })()" style="padding:3px 8px;font-size:11px;background:rgba(184,115,51,.15);border:1px solid var(--accent, #B87333);color:var(--accent, #B87333);border-radius:4px;cursor:pointer;">Aplicar</button>
                </td>
            </tr>`).join('')
        : `<tr><td colspan="3" style="padding:14px;text-align:center;color:var(--text-d);">Sin candidatos en los últimos 30 días.</td></tr>`;

    body.innerHTML = `
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
            ${stat('Verdicts evaluados', m.total_evaluated || 0, 'var(--text-h)', `${escape(String(m.since_days || sinceDays))} días`)}
            ${stat('Precision', pct(m.precision), colorFor(m.precision), 'TP / (TP+FP)')}
            ${stat('Recall',    pct(m.recall),    colorFor(m.recall),    'TP / (TP+FN)')}
            ${stat('F1 score',  pct(m.f1),        colorFor(m.f1),        'media armónica')}
            ${stat('Accuracy',  pct(m.accuracy),  colorFor(m.accuracy),  '(TP+TN) / total')}
            ${stat('Drift',     pct(m.drift_score), m.drift_score >= 0.30 ? '#ef4444' : m.drift_score >= 0.20 ? '#fbbf24' : '#22c55e', 'desacuerdo IA-humano')}
        </div>
        ${cm}
        ${suggBox}
        ${retrainBox}
        <div style="margin-top:18px;">
            <div style="font-weight:600;font-size:13px;color:var(--text-h);margin-bottom:8px;">
                Top false positives candidatos a learn-fp (último mes)
            </div>
            <div style="border:1px solid var(--border, rgba(255,255,255,.05));border-radius:8px;overflow:hidden;">
                <table style="width:100%;border-collapse:collapse;font-size:12.5px;">
                    <thead style="background:rgba(0,0,0,.20);">
                        <tr>
                            <th style="padding:8px 10px;text-align:left;font-weight:600;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Path</th>
                            <th style="padding:8px 10px;text-align:center;font-weight:600;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">FPs</th>
                            <th style="padding:8px 10px;text-align:right;font-weight:600;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Acción</th>
                        </tr>
                    </thead>
                    <tbody>${fpRows}</tbody>
                </table>
            </div>
        </div>`;
}

async function applyAIThresholdSuggestion(delta) {
    if (!confirm(`Aplicar ajuste de ${delta > 0 ? '+' : ''}${delta} a tus thresholds?\n\nEsto modifica los thresholds críticos/sospechosos guardados en BD.`)) return;
    try {
        const r = await fetch('/api/ai-quality/apply-threshold', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            credentials: 'include', body: JSON.stringify({ delta })
        });
        const d = await r.json();
        if (r.ok) {
            if (window.showToast) showToast(`Threshold aplicado: critical=${d.threshold_critical}, suspicious=${d.threshold_suspicious}`, 'success');
            // Refrescar el dashboard
            await openAIQualityDashboard();
        } else {
            alert('Error: ' + (d.error || r.status));
        }
    } catch (e) {
        alert('Error: ' + (e.message || e));
    }
}

window.openAIQualityDashboard = openAIQualityDashboard;
window.applyAIThresholdSuggestion = applyAIThresholdSuggestion;


/* ════════════════════════════════════════════════════════════════════════
 * Pack 37 — Top Repeat Offenders modal
 * Lista de jugadores con >=2 verdicts hack en los últimos 90 días
 * ════════════════════════════════════════════════════════════════════════ */
async function openRepeatOffendersModal(opts) {
    opts = opts || {};
    const sinceDays = opts.since_days || 90;
    const limit = opts.limit || 30;

    let root = document.getElementById('argus-offenders-modal');
    if (!root) {
        root = document.createElement('div');
        root.id = 'argus-offenders-modal';
        root.className = 'modal';
        root.innerHTML = `
            <div class="modal-content" style="max-width:680px;width:96vw;max-height:90vh;overflow-y:auto;">
                <div class="modal-header" style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
                    <h3 style="margin:0;display:flex;align-items:center;gap:8px;">
                        <span aria-hidden="true">🚨</span>
                        <span>Top reincidentes</span>
                    </h3>
                    <div style="display:flex;gap:6px;">
                        <select id="argus-off-range" class="select-sm" style="padding:4px 8px;font-size:13px;background:rgba(0,0,0,.18);color:var(--text-h);border:1px solid var(--border, rgba(255,255,255,.1));border-radius:6px;">
                            <option value="30">30 días</option>
                            <option value="60">60 días</option>
                            <option value="90" selected>90 días</option>
                            <option value="180">180 días</option>
                            <option value="365">1 año</option>
                        </select>
                        <button class="modal-close" type="button" onclick="document.getElementById('argus-offenders-modal').classList.remove('show')" aria-label="Cerrar">×</button>
                    </div>
                </div>
                <div class="modal-body" id="argus-off-body" style="padding:14px 18px;">
                    <div style="text-align:center;padding:30px 0;color:var(--text-d);">Cargando…</div>
                </div>
            </div>`;
        document.body.appendChild(root);
        root.addEventListener('click', (e) => { if (e.target === root) root.classList.remove('show'); });
        root.querySelector('#argus-off-range').addEventListener('change', (e) => {
            openRepeatOffendersModal({ since_days: parseInt(e.target.value, 10) || 90 });
        });
    }
    root.querySelector('#argus-off-range').value = String(sinceDays);
    root.classList.add('show');
    const body = root.querySelector('#argus-off-body');
    body.innerHTML = `<div style="text-align:center;padding:30px 0;color:var(--text-d);">Cargando…</div>`;

    let data;
    try {
        const r = await fetch(`/api/repeat-offenders?since_days=${sinceDays}&limit=${limit}`, { credentials: 'include' });
        data = await r.json();
        if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    } catch (e) {
        body.innerHTML = `<div style="padding:30px;text-align:center;color:#ef4444;">Error: ${(e.message || e)}</div>`;
        return;
    }

    if (!data.available) {
        body.innerHTML = `<div style="padding:30px;text-align:center;color:var(--text-d);">Módulo no disponible.</div>`;
        return;
    }
    if (!data.rows || !data.rows.length) {
        body.innerHTML = `<div style="padding:40px 16px;text-align:center;color:var(--text-d);">
            <div style="font-size:32px;margin-bottom:8px;">✨</div>
            <div>Sin reincidentes en los últimos ${sinceDays} días</div>
        </div>`;
        return;
    }

    const escape = (typeof _qsEscapeSafe === 'function') ? _qsEscapeSafe : (s) => String(s);
    const rows = data.rows.map((r, i) => {
        const dt = r.last_hack ? new Date(r.last_hack) : null;
        const dtStr = dt && !isNaN(dt.getTime()) ? dt.toLocaleDateString('es-AR', {year:'numeric',month:'short',day:'numeric'}) : '—';
        const rankColor = i < 3 ? '#ef4444' : i < 10 ? '#fbbf24' : 'var(--text-d)';
        return `
            <tr style="border-bottom:1px solid var(--border, rgba(255,255,255,.05));">
                <td style="padding:8px 10px;font-weight:700;color:${rankColor};text-align:center;">#${i+1}</td>
                <td style="padding:8px 10px;font-weight:600;">
                    <a href="javascript:void(0)" onclick="if(window.openPlayerTimelineModal) openPlayerTimelineModal('${escape(r.minecraft_username)}')" style="color:var(--accent, #B87333);text-decoration:none;">${escape(r.minecraft_username || '?')}</a>
                </td>
                <td style="padding:8px 10px;text-align:center;color:#ef4444;font-weight:700;">${r.hacks}</td>
                <td style="padding:8px 10px;text-align:center;font-variant-numeric:tabular-nums;">${r.max_risk}</td>
                <td style="padding:8px 10px;color:var(--text-d);font-size:11.5px;">${escape(dtStr)}</td>
            </tr>`;
    }).join('');

    body.innerHTML = `
        <div style="margin-bottom:12px;font-size:13px;color:var(--text-d);">
            <b style="color:var(--text-h);">${data.count}</b> jugadores con ≥2 verdicts hack en los últimos ${data.since_days} días.
            Click en el username para abrir su timeline completo.
        </div>
        <div style="border:1px solid var(--border, rgba(255,255,255,.06));border-radius:8px;overflow:hidden;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead style="background:rgba(0,0,0,.20);">
                    <tr>
                        <th style="padding:8px 10px;text-align:center;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">#</th>
                        <th style="padding:8px 10px;text-align:left;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Jugador</th>
                        <th style="padding:8px 10px;text-align:center;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Hacks</th>
                        <th style="padding:8px 10px;text-align:center;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Max Risk</th>
                        <th style="padding:8px 10px;text-align:left;font-size:11px;color:var(--text-d);text-transform:uppercase;letter-spacing:.05em;">Último</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

window.openRepeatOffendersModal = openRepeatOffendersModal;
