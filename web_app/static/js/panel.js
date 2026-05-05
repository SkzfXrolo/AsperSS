/**
 * Panel del Staff - ASPERS Projects
 * Sistema de gestión y aprendizaje progresivo
 */

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

// ── Paleta de colores ──────────────────────────────────────────────────────
const ARGUS_PALETTES = {
    purple: { label:'Morado',  swatch:'#8B5CF6', accent:'#8B5CF6', d:'#6D28D9', bg:'rgba(139,92,246,0.08)', glow:'rgba(139,92,246,0.22)', border:'rgba(139,92,246,0.12)', borderM:'rgba(139,92,246,0.28)', borderH:'rgba(139,92,246,0.55)' },
    blue:   { label:'Azul',    swatch:'#3B82F6', accent:'#3B82F6', d:'#1D4ED8', bg:'rgba(59,130,246,0.08)',  glow:'rgba(59,130,246,0.22)',  border:'rgba(59,130,246,0.12)',  borderM:'rgba(59,130,246,0.28)',  borderH:'rgba(59,130,246,0.55)'  },
    green:  { label:'Verde',   swatch:'#10B981', accent:'#10B981', d:'#059669', bg:'rgba(16,185,129,0.08)',  glow:'rgba(16,185,129,0.22)',  border:'rgba(16,185,129,0.12)',  borderM:'rgba(16,185,129,0.28)',  borderH:'rgba(16,185,129,0.55)'  },
    orange: { label:'Naranja', swatch:'#F59E0B', accent:'#F59E0B', d:'#D97706', bg:'rgba(245,158,11,0.08)',  glow:'rgba(245,158,11,0.22)',  border:'rgba(245,158,11,0.12)',  borderM:'rgba(245,158,11,0.28)',  borderH:'rgba(245,158,11,0.55)'  },
    red:    { label:'Rojo',    swatch:'#EF4444', accent:'#EF4444', d:'#DC2626', bg:'rgba(239,68,68,0.08)',   glow:'rgba(239,68,68,0.22)',   border:'rgba(239,68,68,0.12)',   borderM:'rgba(239,68,68,0.28)',   borderH:'rgba(239,68,68,0.55)'   },
    pink:   { label:'Rosa',    swatch:'#EC4899', accent:'#EC4899', d:'#DB2777', bg:'rgba(236,72,153,0.08)',  glow:'rgba(236,72,153,0.22)',  border:'rgba(236,72,153,0.12)',  borderM:'rgba(236,72,153,0.28)',  borderH:'rgba(236,72,153,0.55)'  },
    cyan:   { label:'Cyan',    swatch:'#06B6D4', accent:'#06B6D4', d:'#0891B2', bg:'rgba(6,182,212,0.08)',   glow:'rgba(6,182,212,0.22)',   border:'rgba(6,182,212,0.12)',   borderM:'rgba(6,182,212,0.28)',   borderH:'rgba(6,182,212,0.55)'   },
    white:  { label:'Blanco',  swatch:'#E2E8F7', accent:'#E2E8F7', d:'#C4CFDF', bg:'rgba(226,232,247,0.08)', glow:'rgba(226,232,247,0.15)', border:'rgba(226,232,247,0.10)', borderM:'rgba(226,232,247,0.22)', borderH:'rgba(226,232,247,0.45)' },
};
let _currentPalette = 'purple';

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
function showToast(message, type = 'info', scanId = null) {
    if (!_toastContainer) {
        _toastContainer = document.createElement('div');
        _toastContainer.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
        document.body.appendChild(_toastContainer);
    }
    const cfg = {
        info:    { color: '#8B5CF6', bg: 'rgba(139,92,246,0.12)', icon: '◆' },
        success: { color: '#10b981', bg: 'rgba(16,185,129,0.12)',  icon: '✓' },
        error:   { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',   icon: '✗' },
    };
    const c = cfg[type] || cfg.info;
    const toast = document.createElement('div');
    toast.style.cssText = `
        background:var(--bg-card,#1e1e2e);
        border:1px solid ${c.color}55;
        border-left:3px solid ${c.color};
        border-radius:10px;padding:11px 15px;
        font-size:13px;color:var(--text,#e2e8f0);
        box-shadow:0 8px 32px rgba(0,0,0,0.35),0 0 0 0 ${c.color};
        pointer-events:all;cursor:${scanId?'pointer':'default'};
        max-width:290px;min-width:220px;
        animation:slideInRight .22s cubic-bezier(0.4,0,0.2,1);
        display:flex;gap:10px;align-items:flex-start;
        position:relative;overflow:hidden;`;
    toast.innerHTML = `
        <span style="font-size:14px;font-weight:700;color:${c.color};flex-shrink:0;margin-top:1px;">${c.icon}</span>
        <div style="flex:1;min-width:0;">
            <div style="font-weight:600;margin-bottom:2px;font-size:12px;color:${c.color};">Argus Projects</div>
            <div style="color:var(--text-m,#94a3b8);font-size:12.5px;line-height:1.4;">${message}</div>
        </div>
        <div style="position:absolute;bottom:0;left:0;height:2px;background:${c.color};opacity:0.5;animation:toast-drain 5s linear forwards;width:100%;transform-origin:left;"></div>`;
    if (scanId) toast.onclick = () => { viewScanDetails(scanId); toast.remove(); };
    _toastContainer.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .35s'; setTimeout(() => toast.remove(), 350); }, 5000);
}

let _soundEnabled = localStorage.getItem('notif-sound') !== 'false';
function playNotificationSound() {
    if (!_soundEnabled) return;
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
        case 'aprendizaje':
            loadLearningStats();
            loadLearnedPatterns();
            break;
        case 'generar-app':
            // No necesita cargar datos adicionales
            break;
    }
}

// ============================================================
// DASHBOARD
// ============================================================

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
    const isCrit = alertLevel === 'CRITICAL';
    const isSusp = alertLevel === 'SOSPECHOSO';
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
                return `<div class="echo-scan-row stagger-item ${rowCls}" style="animation-delay:${i*55}ms" onclick="viewScanDetails(${scan.id})">
                    <div class="scan-avatar-circle ${avCls}">${_scanInitials(scan.machine_name)}</div>
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
                    borderColor: '#8B5CF6',
                    backgroundColor: 'rgba(139,92,246,0.10)',
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
                        ? `rgba(139,92,246,${0.12 + (pct/100)*0.55})`
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
            <span><span style="display:inline-block;width:10px;height:10px;background:rgba(139,92,246,0.5);border-radius:2px;margin-right:3px;vertical-align:middle;"></span>Scan</span>
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
                    style="margin-top:8px;width:100%;padding:5px;border-radius:6px;border:1px solid rgba(139,92,246,.4);background:rgba(139,92,246,.1);color:var(--accent);font-size:11px;cursor:pointer;">
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
                    ? `<span style="font-family:'Consolas',monospace;font-size:18px;font-weight:900;letter-spacing:4px;color:#a78bfa;">${token.short_code}</span>`
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

    // Actualizar modelo
    document.getElementById('update-model-btn')?.addEventListener('click', async () => {
        await updateModel();
    });

    // Descargar aplicación (sin compilar)
    document.getElementById('download-app-btn')?.addEventListener('click', async () => {
        await downloadApp();
    });

    // Compilar aplicación (solo si hay cambios en código)
    document.getElementById('compile-app-btn')?.addEventListener('click', async () => {
        await compileApp();
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
    if (!confirm('¿Eliminar permanentemente este token?\n\n⚠️ Esta acción no se puede deshacer.\n\nSi algún cliente está usando este token, dejará de funcionar inmediatamente.')) {
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
            tbody.innerHTML = data.scans.map((scan, idx) => {
                const rs = scan.risk_score;
                const riskClass = rs >= 70 ? 'tr-risk-critical' : rs >= 30 ? 'tr-risk-suspicious' : (rs !== undefined && rs !== null ? 'tr-risk-clean' : '');

                // V12: Crafatar avatar or initials
                const uuid = scan.minecraft_uuid || null;
                const avatar = uuid
                    ? `<img src="https://crafatar.com/avatars/${uuid}?size=32&overlay" alt="" style="width:32px;height:32px;border-radius:6px;object-fit:cover;flex-shrink:0;" onerror="this.outerHTML='<div class=\\"scan-avatar-circle\\">${_scanInitials(scan.machine_name)}</div>'">`
                    : `<div class="scan-avatar-circle">${_scanInitials(scan.machine_name)}</div>`;

                // V13: NUEVO badge if scan < 30min old
                const scanAge = scan.started_at ? (now - new Date(scan.started_at).getTime()) : Infinity;
                const nuevoBadge = scanAge < 30 * 60 * 1000 ? `<span class="badge-nuevo">NUEVO</span>` : '';

                // V14: Trend arrow (up/down based on risk vs previous if available)
                const trend = scan.risk_trend;
                const trendArrow = trend === 'up' ? `<span style="color:#ef4444;font-size:11px;" title="Tendencia empeorando">↑</span>`
                    : trend === 'down' ? `<span style="color:#10b981;font-size:11px;" title="Tendencia mejorando">↓</span>` : '';

                // V17: OS icon
                const osStr = (scan.os_name || scan.os || '').toLowerCase();
                const osIcon = osStr.includes('linux') ? '🐧' : osStr.includes('mac') ? '🍎' : osStr.includes('win') ? '🪟' : '';

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
                        <span class="game-badge">
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.2"/><path d="M4 6H8M6 4V8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                            Minecraft${osIcon ? ` <span>${osIcon}</span>` : ''}
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
        } else {
            if (tbody) tbody._loaded = false;
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay escaneos</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando escaneos:', error);
    }
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

function saveFilterPreset() {
    const search   = (document.getElementById('filter-search')?.value || '').trim();
    const verdict  = document.getElementById('filter-verdict')?.value || '';
    const dateFrom = document.getElementById('filter-date-from')?.value || '';
    const dateTo   = document.getElementById('filter-date-to')?.value || '';
    if (!search && !verdict && !dateFrom && !dateTo) return;
    const name = prompt('Nombre del preset:');
    if (!name) return;
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    presets[name] = { search, verdict, dateFrom, dateTo };
    localStorage.setItem('scan_filter_presets', JSON.stringify(presets));
    _renderPresetOptions();
}

function loadFilterPreset(name) {
    if (!name) return;
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    const p = presets[name];
    if (!p) return;
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
    set('filter-search', p.search);
    set('filter-verdict', p.verdict);
    set('filter-date-from', p.dateFrom);
    set('filter-date-to', p.dateTo);
    loadScans();
}

function _renderPresetOptions() {
    const sel = document.getElementById('filter-presets');
    if (!sel) return;
    const presets = JSON.parse(localStorage.getItem('scan_filter_presets') || '{}');
    sel.innerHTML = '<option value="">Presets...</option>' +
        Object.keys(presets).map(n => `<option value="${n}">${n}</option>`).join('');
}

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
            tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Sin usuarios</td></tr>';
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
        tbody.innerHTML = `<tr><td colspan="5" class="loading-cell">Error: ${e.message}</td></tr>`;
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
        loadStaffUsers();
    } else {
        alert('Error: ' + (data.error || 'No se pudo actualizar'));
    }
}

// ── Screenshot display ─────────────────────────────────────────────────────

function renderScreenshot(data) {
    const container = document.getElementById('screenshot-container');
    if (!container) return;
    const b64 = data && data.screenshot;
    if (!b64) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-d);font-size:13px;">Sin captura de pantalla — el scanner tomará una automáticamente a partir de la próxima versión.</div>';
        return;
    }
    const ts = data.started_at ? new Date(data.started_at).toLocaleString() : '';
    container.innerHTML = `
        <div style="font-size:12px;color:var(--text-d);margin-bottom:8px;">
            Capturado el inicio del escaneo · ${ts}
        </div>
        <img src="data:image/jpeg;base64,${b64}"
             alt="Captura de pantalla"
             style="max-width:100%;border-radius:10px;border:1px solid var(--border);box-shadow:0 4px 20px rgba(0,0,0,0.3);"
             onclick="this.style.maxWidth=this.style.maxWidth==='100%'?'none':'100%'"
             title="Click para ver tamaño completo">`;
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
    const q   = (document.getElementById('issues-search-input')?.value || '').toLowerCase().trim();
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
            (r.issue_name  || '').toLowerCase().includes(q) ||
            (r.issue_path  || '').toLowerCase().includes(q)
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

    // Chips de categoría
    const onlyInst = !!window._issuesOnlyInstance;
    const instCount = all.filter(r => _isInMinecraftInstance(r.issue_path)).length;

    const _catColors = {
        'GHOST_CLIENT':'#ef4444','HACKS':'#ef4444','FORENSE':'#8b5cf6',
        'RED':'#3b82f6','NETWORK_FORENSICS':'#3b82f6','PROCESO':'#f59e0b','PROCESSES':'#f59e0b',
        'MACRO_DETECTION':'#f59e0b','EXECUTED_FILES':'#10b981','CMD_HISTORY':'#10b981',
        'JAVA_MEMORY':'#06b6d4','JAVA_AGENT':'#06b6d4','REGISTRY':'#a78bfa',
    };
    const chips = cats.map(c => {
        const count = c === 'all' ? all.length : all.filter(r => (r.issue_category || 'Otro') === c).length;
        const active = _issuesFilter === c;
        const accent = _catColors[c] || '#8B5CF6';
        return `<button onclick="_setIssueFilter('${c}',${scanId})" style="
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

    const rows = slice.map((result) => {
        const isCrit  = result.alert_level === 'CRITICAL';
        const isMid   = result.alert_level === 'SOSPECHOSO';
        const accent  = isCrit ? '#ef4444' : isMid ? '#f59e0b' : '#6b7280';
        const bg      = isCrit ? 'rgba(239,68,68,0.05)' : isMid ? 'rgba(245,158,11,0.04)' : 'rgba(107,114,128,0.03)';
        const dot     = isCrit ? '🔴' : isMid ? '🟠' : '🔵';
        const cat     = result.issue_category || '';
        const name    = (result.issue_name || 'Hallazgo').slice(0, 100);
        const path    = result.issue_path || '';
        const truncPath = path.length > 90 ? '…' + path.slice(-87) : path;
        const inInst  = _isInMinecraftInstance(path);
        const instBadge = inInst
            ? `<span style="font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);flex-shrink:0;white-space:nowrap;">En instancia</span>`
            : `<span style="font-size:10px;font-weight:600;padding:1px 6px;border-radius:4px;background:rgba(245,158,11,0.1);color:#f59e0b;border:1px solid rgba(245,158,11,0.3);flex-shrink:0;white-space:nowrap;">Fuera de instancia</span>`;

        const safeLevel = (result.alert_level || 'SOSPECHOSO').replace(/'/g,"");
        const safeName  = name.replace(/'/g, "\\'").replace(/"/g, '&quot;');
        const rowIdx    = slice.indexOf(result);

        // V3: Category icon
        const catIcon = _catIcon(cat);
        // V9: Flames
        const flames = _flameIndicator(result.alert_level, result.confidence);
        // V4: Critical glow class
        const glowCls = isCrit ? 'issue-critical-glow' : '';
        // V48: Stagger delay
        const staggerStyle = `animation-delay:${rowIdx * 40}ms;`;
        // V2: Confidence bar
        const conf = result.confidence;
        const confBar = (conf !== undefined && conf !== null) ? `
            <div style="margin-top:5px;display:flex;align-items:center;gap:6px;">
                <div style="flex:1;height:3px;background:rgba(255,255,255,0.07);border-radius:2px;overflow:hidden;">
                    <div style="height:100%;width:${Math.min(conf,100)}%;background:${accent};border-radius:2px;transition:width 0.8s ease;"></div>
                </div>
                <span style="font-size:10px;color:var(--text-d);flex-shrink:0;">${conf}%</span>
            </div>` : '';
        // V7: Formatted path
        const fmtPath = _formatPath(path);
        // V8: Copy hash button (shown if path contains SHA256-like string)
        const hashMatch = path.match(/\b([a-f0-9]{64})\b/i);
        const copyBtn = hashMatch ? `<button onclick="event.stopPropagation();_copyWithFeedback('${hashMatch[1]}',this)" title="Copiar hash" style="font-size:11px;padding:1px 5px;border-radius:4px;border:1px solid var(--border-m);background:var(--bg-t);color:var(--text-m);cursor:pointer;flex-shrink:0;margin-left:4px;">📋</button>` : '';

        return `<div data-result-id="${result.id}" class="issue-row-stagger ${glowCls}" style="${staggerStyle}
            background:${bg};border:1px solid ${accent}33;border-left:3px solid ${accent};
            border-radius:8px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px;
            overflow:hidden;max-width:100%;min-width:0;cursor:pointer;transition:outline 0.15s,background 0.15s;"
            onclick="_selectIssue(this)">
            <span style="font-size:18px;flex-shrink:0;margin-top:0;">${catIcon}</span>
            <div style="flex:1;min-width:0;overflow:hidden;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);display:flex;align-items:center;gap:6px;flex-wrap:nowrap;min-width:0;overflow:hidden;">
                    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:break-all;min-width:0;flex:1;">${name}</span>
                    <span style="font-size:12px;flex-shrink:0;" title="Nivel de peligro">${flames}</span>
                    ${instBadge}
                    ${cat ? `<span style="font-size:10px;font-weight:500;color:var(--text-d);background:var(--bg-t);border:1px solid var(--border-m);padding:1px 6px;border-radius:4px;flex-shrink:0;white-space:nowrap;">${_getCategoryLabel(cat)}</span>` : ''}
                    <button onclick="event.stopPropagation();aiExplainFinding('${safeName}','${safeLevel}',this)" title="Explicar con IA"
                            style="font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid rgba(124,58,237,.35);
                                   background:rgba(124,58,237,.1);color:#a78bfa;cursor:pointer;flex-shrink:0;">🤖</button>
                </div>
                ${truncPath ? `<div style="font-size:11px;color:var(--text-d);margin-top:3px;overflow:hidden;text-overflow:ellipsis;max-width:100%;" title="${path}">${fmtPath}${copyBtn}</div>` : ''}
                ${confBar}
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
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid var(--border);">${chips}</div>
        <div style="display:flex;flex-direction:column;gap:6px;">${rows || '<div style="padding:20px;text-align:center;color:var(--text-d);font-size:12px;">Sin hallazgos en esta categoría.</div>'}</div>
        ${loadMoreBtn}`;
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
            // V42: confetti on clean verdict
            if (typeof confetti === 'function') {
                confetti({ particleCount: 90, spread: 70, origin: { y: 0.5 }, colors: ['#10b981','#34d399','#6ee7b7','#fff'] });
            }
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
    banner.style.cssText = `display:block;background:${c.bg};border:1px solid ${c.border};border-radius:10px;padding:12px 16px;margin-bottom:4px;font-size:13px;`;
    banner.innerHTML = `<span style="font-weight:700;color:${c.text};">Veredicto: ${label}</span>${scanData.verdict_reason ? ` — <span style="color:var(--text-s);">${scanData.verdict_reason}</span>` : ''}${scanData.verdict_by ? `<span style="color:var(--text-d);font-size:11px;margin-left:8px;">por ${scanData.verdict_by}</span>` : ''}`;
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
            ` — ${e.reason || '—'} <span style="color:var(--text-d);">por ${e.changed_by} · ${formatDate(e.changed_at)}</span></div>`
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
    if (issuesContainerReset) issuesContainerReset.innerHTML = '<div class="loading-cell">Cargando...</div>';

    // Actualizar navegación
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.querySelector('[data-section="resultados"]')?.classList.add('active');

    try {
        const response = await fetch(`/api/scans/${scanId}`);
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
        if (osEl) osEl.textContent = data.os || data.operating_system || 'Windows';
        
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

        // Risk score badge
        const riskScore = data.risk_score || 0;
        const riskBadge = document.getElementById('detail-risk-score-badge');
        const riskBar   = document.getElementById('detail-risk-score-bar');
        if (riskBadge && riskBar) {
            const riskClass = riskScore >= 70 ? 'risk-hack' : riskScore >= 30 ? 'risk-suspicious' : 'risk-clean';
            const riskLabel = riskScore >= 70 ? `${riskScore} — HACK` : riskScore >= 30 ? `${riskScore} — Sospechoso` : `${riskScore} — Limpio`;
            riskBadge.className = `risk-score-badge ${riskClass}`;
            riskBadge.textContent = riskLabel;
            riskBar.className = `risk-score-bar ${riskClass}`;
            riskBar.style.width = `${Math.min(riskScore, 100)}%`;
        }

        // V1: Render animated SVG gauge if container exists
        if (riskScore !== undefined && riskScore !== null) {
            _renderRiskGauge('risk-gauge-container', riskScore);
        }

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
                    <div style="font-size:13px">Los resultados aparecerán cuando el scanner termine.</div>
                    <button class="btn btn-sm" style="margin-top:18px" onclick="viewScanDetails(${scanId})">Actualizar</button>
                </div>`;
            document.getElementById('bulk-actions-bar').style.display = 'none';
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
        currentIssuesList = (data.results || [])
            .filter(r => r.alert_level && r.alert_level !== 'CLEAN')
            // Primero en-instancia, luego por severidad dentro de cada grupo
            .sort((a, b) => {
                const ai = _isInMinecraftInstance(a.issue_path) ? 0 : 1;
                const bi = _isInMinecraftInstance(b.issue_path) ? 0 : 1;
                if (ai !== bi) return ai - bi;
                return (_alertOrder[a.alert_level] ?? 9) - (_alertOrder[b.alert_level] ?? 9);
            });
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
                const accent = isSusp ? '#ef4444' : '#a78bfa';
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
        _renderTabFindings('utilities-list',       'subnav-utilities',        'utilities-badge',         allResults, ['AUTOCLICK', 'AUTOCLICK_TOOLS', 'HARDWARE', 'LOGITECH', 'RAZER', 'USB_DEVICES', 'SERVICES', 'MACRO']);
        _renderTabFindings('archivos-windows-list','subnav-archivos-windows', 'archivos-windows-badge',  allResults, ['TEMP_FILES', 'FORENSE', 'INYECCION', 'JAVA_INJECTION', 'JNA', 'RED', 'NETWORK_CONNECTIONS']);
        _renderTabFindings('settings-list',        'subnav-settings',         'settings-badge',          allResults, ['DATE_CHANGES', 'EVASION', 'PERSISTENCIA', 'DNS_CACHE', 'VPN']);

    } catch (error) {
        console.error('Error cargando detalles:', error);
        alert('Error al cargar detalles del escaneo: ' + error.message);
    }
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
                            <span style="font-size:12px;color:var(--text);flex:1;margin-right:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${b.source}">${b.source}</span>
                            <span style="font-size:13px;font-weight:700;color:${scoreColor};min-width:36px;text-align:right;">+${b.points}</span>
                        </div>
                        <div style="background:var(--bg);border-radius:4px;height:6px;overflow:hidden;">
                            <div style="background:${scoreColor};height:100%;width:${Math.round(b.points/maxPts*100)}%;border-radius:4px;transition:width 0.4s;"></div>
                        </div>
                        <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">${b.reason}</div>
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
                    <span style="font-size:12px;font-weight:700;color:var(--accent);">${n.author}</span>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="font-size:11px;color:var(--text-d);">${formatDate(n.created_at)}</span>
                        <button onclick="deleteScanNote(${scanId},${n.id},this)"
                            style="background:none;border:none;cursor:pointer;color:var(--text-d);font-size:12px;padding:2px 6px;border-radius:4px;transition:color .15s;"
                            title="Eliminar nota">✕</button>
                    </div>
                </div>
                <div style="font-size:13px;color:var(--text-s);white-space:pre-wrap;line-height:1.6;">${n.body.replace(/</g,'&lt;')}</div>
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
        const response = await fetch(`/api/scans?machine_name=${encodeURIComponent(machineName)}&limit=20`);
        const data = await response.json();

        const container = document.getElementById('previous-scans-list');
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
                            backgroundColor: 'rgba(139,92,246,0.10)',
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

            container.innerHTML = statsHtml + prevScans.map((scan, i) => {
                const prev      = prevScans[i + 1];
                const issuesDiff = prev != null ? (scan.issues_found || 0) - (prev.issues_found || 0) : null;
                const diffBadge = issuesDiff === null ? '' :
                    issuesDiff > 0 ? `<span style="color:#ef4444;font-size:11px;">▲ ${issuesDiff}</span>` :
                    issuesDiff < 0 ? `<span style="color:#10b981;font-size:11px;">▼ ${Math.abs(issuesDiff)}</span>` :
                                    `<span style="color:var(--text-d);font-size:11px;">= igual</span>`;
                const verdictBadge = scan.verdict === 'hack'  ? '<span style="font-size:10px;font-weight:700;color:#ef4444;background:rgba(220,38,38,0.12);padding:1px 6px;border-radius:6px;">HACKS</span>' :
                                     scan.verdict === 'clean' ? '<span style="font-size:10px;font-weight:700;color:#10b981;background:rgba(16,185,129,0.12);padding:1px 6px;border-radius:6px;">LIMPIO</span>' : '';
                return `
                    <div class="previous-scan-item" onclick="viewScanDetails(${scan.id})" style="cursor:pointer;">
                        <div class="previous-scan-header">
                            <span class="previous-scan-id">Escaneo #${scan.id} ${verdictBadge}</span>
                            <span class="previous-scan-date">${formatDate(scan.started_at)}</span>
                        </div>
                        <div class="previous-scan-stats">
                            <span class="previous-scan-stat"><strong>${scan.issues_found || 0}</strong> issues ${diffBadge}</span>
                            <span class="previous-scan-stat"><strong>${scan.total_files_scanned || 0}</strong> archivos</span>
                            ${scan.risk_score != null ? `<span class="previous-scan-stat" style="color:${scan.risk_score>=70?'#ef4444':scan.risk_score>=30?'#f59e0b':'#10b981'};font-weight:700;">Risk ${scan.risk_score}</span>` : ''}
                            <button onclick="event.stopPropagation();compareScanWith(${scan.id})"
                                style="margin-left:auto;font-size:10px;padding:2px 8px;background:rgba(139,92,246,0.15);
                                       border:1px solid rgba(139,92,246,0.4);color:var(--accent);border-radius:6px;cursor:pointer;">
                                Comparar
                            </button>
                        </div>
                    </div>`;
            }).join('');
        } else {
            container.innerHTML = '<div class="loading-cell">Primer escaneo de esta máquina.</div>';
        }
    } catch (error) {
        console.error('Error cargando escaneos previos:', error);
        const container = document.getElementById('previous-scans-list');
        if (container) {
            container.innerHTML = '<div class="loading-cell">Error al cargar escaneos previos.</div>';
        }
    }
}

async function compareScanWith(scanIdB) {
    if (!currentScanId) return;
    const modal = document.getElementById('compare-modal');
    const body  = document.getElementById('compare-modal-body');
    if (!modal || !body) return;
    body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-m);">Cargando comparación...</div>';
    modal.style.display = 'flex';
    try {
        const res  = await fetch(`/api/scans/${currentScanId}/compare/${scanIdB}`);
        const diff = await res.json();
        if (diff.error) { body.innerHTML = `<p style="color:#ef4444">${diff.error}</p>`; return; }

        const ALERT_COLOR = { CRITICAL:'#ef4444', SOSPECHOSO:'#f59e0b', MUY_SOSPECHOSO:'#ea580c', POCO_SOSPECHOSO:'#6366f1' };
        const riskDelta = diff.risk_delta;
        const riskColor = riskDelta > 0 ? '#ef4444' : riskDelta < 0 ? '#10b981' : 'var(--text-m)';
        const riskSign  = riskDelta > 0 ? '+' : '';

        const renderIssueList = (items, bgColor) => items.length === 0
            ? `<p style="color:var(--text-d);font-size:12px;margin:0;">Ninguno</p>`
            : items.map(f => `
                <div style="padding:6px 10px;border-radius:6px;background:${bgColor};margin-bottom:4px;font-size:12px;">
                    <span style="color:${ALERT_COLOR[f.alert]||'var(--text-m)'};font-weight:700;margin-right:6px;">${f.alert||''}</span>
                    <span style="color:var(--text);">${f.name||f.type}</span>
                    <span style="float:right;color:var(--text-d);">${Math.round((f.confidence||0)*100)}%</span>
                </div>`).join('');

        body.innerHTML = `
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
            <div style="margin-bottom:16px;">
                <div style="font-size:13px;font-weight:700;color:#ef4444;margin-bottom:8px;">
                    Hallazgos nuevos (${diff.summary.new_count})
                </div>
                ${renderIssueList(diff.new_findings, 'rgba(220,38,38,0.08)')}
            </div>
            <div style="margin-bottom:16px;">
                <div style="font-size:13px;font-weight:700;color:#10b981;margin-bottom:8px;">
                    Hallazgos resueltos / desaparecidos (${diff.summary.resolved_count})
                </div>
                ${renderIssueList(diff.resolved_findings, 'rgba(16,185,129,0.08)')}
            </div>
            <div>
                <div style="font-size:13px;font-weight:700;color:var(--text-m);margin-bottom:8px;">
                    Persistentes en ambos scans (${diff.summary.persistent_count})
                </div>
                ${renderIssueList(diff.persistent_findings, 'var(--bg-s)')}
            </div>`;
    } catch (e) {
        body.innerHTML = `<p style="color:#ef4444">Error: ${e.message}</p>`;
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
        const response = await fetch('/api/learning-stats');
        const data = await response.json();
        document.getElementById('learned-patterns-count').textContent = data.patterns_count  ?? 0;
        document.getElementById('learned-hashes-count').textContent   = data.hashes_count   ?? 0;
    } catch (error) {
        console.error('Error cargando estadísticas de aprendizaje:', error);
    }
    // P3 #1 — Estado del clasificador RF
    try {
        const r2  = await fetch('/api/ml/status');
        const ml  = await r2.json();
        const txt = document.getElementById('ml-status-text');
        if (txt) {
            if (ml.available) {
                txt.textContent = `✅ Modelo activo — entrenado con ${ml.trained_on} muestras`;
                txt.style.color = 'var(--success, #22c55e)';
            } else {
                txt.textContent = '⚠ Modelo no disponible — haz clic en "Entrenar ahora" para generarlo';
                txt.style.color = 'var(--warning, #f59e0b)';
            }
        }
    } catch (_) {}
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
            container.innerHTML = '<div class="loading-cell">No hay patrones aprendidos aún. Marca resultados como hack para que ASPERS Projects aprenda.</div>';
        }
    } catch (error) {
        console.error('Error cargando patrones:', error);
    }
}

async function updateModel() {
    if (!confirm('¿Actualizar el modelo de IA de ASPERS Projects?\n\nLos clientes descargarán automáticamente los nuevos patrones al iniciar.\nNO es necesario recompilar el ejecutable.')) {
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
    if (!confirm('⚠️ Eliminará TODOS los resultados basura de la BD completa (EXECUTED_DELETED, nombres binarios).\n\n¿Continuar?')) return;
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
    if (!confirm(`⚠️ Esto eliminará TODOS los scans de "${machineName}" de la base de datos.\n\nÚsalo solo para limpiar scans de prueba propios.\n\n¿Continuar?`)) return;

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

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('es-ES');
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
    if (!confirm('¿Compilar nueva versión del ejecutable?\n\n⚠️ SOLO usa esto si hay cambios en el código del programa.\n\nLas actualizaciones de IA se descargan automáticamente sin necesidad de recompilar.\n\nEl proceso puede tardar varios minutos.')) {
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
                const expiresAt = token.expires_at ? new Date(token.expires_at).toLocaleString('es-ES') : 'Sin expiración';
                const isExpired = token.expires_at ? new Date(token.expires_at) < new Date() : false;
                
                return `
                <tr>
                    <td><code style="font-size: 11px;">${token.token.substring(0, 20)}...</code></td>
                    <td>${token.created_by || 'N/A'}</td>
                    <td>${new Date(token.created_at).toLocaleString('es-ES')}</td>
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
                                const expiresAt = link.expires_at ? new Date(link.expires_at).toLocaleString('es-ES') : 'Sin expiración';
                                const isExpired = link.expires_at ? new Date(link.expires_at) < new Date() : false;
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
    if (!confirm('¿Estás seguro de que quieres desactivar este enlace de descarga?')) {
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
                const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString('es-ES') : 'Nunca';
                
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
                const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString('es-ES') : 'Nunca';
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
    if (!confirm('¿Estás seguro de que quieres desactivar este usuario? El usuario no podrá iniciar sesión hasta que lo reactives.')) {
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
    if (!confirm(`¿Estás SEGURO de que quieres ELIMINAR permanentemente al usuario "${username}"?\n\nEsta acción NO se puede deshacer.`)) {
        return;
    }
    
    if (!confirm('Esta acción es PERMANENTE. ¿Confirmas la eliminación?')) {
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
        ? '0 4px 28px rgba(124,58,237,.7)'
        : '0 4px 20px rgba(124,58,237,.45)';
    if (_aiChatOpen) {
        _updateAIChatScanBadge();
        document.getElementById('ai-chat-input').focus();
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
    const inp = document.getElementById('ai-chat-input');
    if (inp) { inp.value = msg; inp.style.height = 'auto'; }
    sendAIChatMessage();
}

function aiChatKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendAIChatMessage();
    }
}

async function sendAIChatMessage() {
    const inp  = document.getElementById('ai-chat-input');
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

        const res  = await fetch('/api/staff/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();

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
            _appendChatMsg(msgs, _formatAIReply(reply), 'bot');
        }
    } catch (e) {
        typing.remove();
        _appendChatMsg(msgs, `⚠️ Error de conexión: ${e.message}`, 'bot');
    }

    msgs.scrollTop = msgs.scrollHeight;
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
        'background:' + (isUser ? 'rgba(79,70,229,.35)' : 'rgba(124,58,237,.15)'),
    ].join(';');
    el.innerHTML = isTyping ? '<span class="ai-typing-dots">● ● ●</span>' : text;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
    return el;
}

function _formatAIReply(text) {
    return text
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
    msgs.innerHTML = `<div style="background:rgba(124,58,237,.15);border-radius:12px 12px 12px 4px;
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
    badge.style.background = 'rgba(124,58,237,.2)';
    badge.style.color  = '#a78bfa';
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
            expEl.style.cssText = 'font-size:11px;color:#c4b5fd;margin-top:5px;padding:5px 8px;background:rgba(124,58,237,.1);border-radius:6px;border-left:2px solid #7c3aed;line-height:1.5;';
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
            el.style.cssText = 'margin-top:10px;padding:10px 14px;background:rgba(124,58,237,.08);border:1px solid rgba(124,58,237,.25);border-radius:8px;font-size:12px;line-height:1.6;color:var(--text-m);';
            const card = document.getElementById('ai-verdict-card');
            if (card) card.appendChild(el);
        }
        el.innerHTML = '<span style="color:#a78bfa;font-weight:600">📝 Resumen IA:</span><br>' + text;
        el.style.display = 'block';
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
            section('🔑 SHA-256',         '#a78bfa', d.hashes?.sha256 || []),
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
                            backgroundColor: 'rgba(139,92,246,0.08)',
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
                        backgroundColor: 'rgba(139,92,246,0.08)',
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
    if (btn) btn.textContent = collapsed ? '▶' : '◀';
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
            if (btn)     btn.textContent = '▶';
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
        if (!btn) return;
        btn.classList.toggle('visible', window.scrollY > 300);
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
        const r = await fetch(`/api/scans?search=${encodeURIComponent(q)}&limit=8`);
        const d = await r.json();
        _globalSearchResults = d.scans || [];
        _globalSearchIndex   = -1;
        if (_globalSearchResults.length === 0) {
            res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:var(--text-d);">Sin resultados</div>';
            return;
        }
        res.innerHTML = _globalSearchResults.map((s, i) => {
            const rs = s.risk_score;
            const col = rs >= 70 ? '#ef4444' : rs >= 30 ? '#f59e0b' : '#10b981';
            return `<div class="global-search-result" data-idx="${i}" onclick="_globalSearchOpen(${i})">
                <span style="font-size:18px;">${rs >= 70 ? '🔴' : rs >= 30 ? '🟠' : '🟢'}</span>
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${s.machine_name || 'N/A'}</div>
                    <div style="font-size:11px;color:var(--text-d);">${_timeAgo(s.started_at)} · <span style="color:${col};">${rs !== undefined ? rs + ' pts' : '—'}</span></div>
                </div>
            </div>`;
        }).join('');
    } catch(_) {
        res.innerHTML = '<div style="padding:14px 20px;font-size:12px;color:#ef4444;">Error de búsqueda</div>';
    }
}
function _globalSearchOpen(idx) {
    const s = _globalSearchResults[idx];
    if (s) { closeGlobalSearch(); viewScanDetails(s.id); }
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
    if (dd && !dd.contains(e.target) && e.target !== btn) dd.classList.remove('open');
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
        <input type="color" class="custom-color-input" value="#8B5CF6"
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

const BG_PRESETS = ['default','aurora','nebula','cyber','ocean','lava','forest'];

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
    _applyBg(cfg);
    _syncBgUI();
}
window.setBgPreset = setBgPreset;

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
}

// Init on load
document.addEventListener('DOMContentLoaded', () => {
    const cfg = _loadBgCfg();
    if (cfg && Object.keys(cfg).length > 0) _applyBg(cfg);

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
