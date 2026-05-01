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
    if (!isOpen) _buildPaletteSwatches();
}

function _loadSavedPalette() {
    const saved = localStorage.getItem('argus_palette');
    if (saved && ARGUS_PALETTES[saved]) applyPalette(saved);
}

// Inicialización - OPTIMIZADO: Cargar datos críticos primero, el resto en background
document.addEventListener('DOMContentLoaded', function() {
    _loadSavedPalette();
    initializeNavigation();
    setupEventListeners();
    setupAdminListeners();
    setupCompanyListeners();
    // Cerrar palette panel al hacer click fuera
    document.addEventListener('click', e => {
        const panel = document.getElementById('palette-panel');
        const btn   = document.getElementById('palette-toggle');
        if (panel && btn && !panel.contains(e.target) && !btn.contains(e.target)) {
            panel.style.display = 'none';
        }
    });

    // Cargar datos críticos primero
    loadDashboard();

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
                showToast(`Nuevo scan de ${completed[0].machine_name || 'desconocido'}`, 'info', completed[0].id);
                playNotificationSound();
                const activeSection = document.querySelector('.panel-section.active');
                if (activeSection && activeSection.id === 'dashboard-section') loadDashboard();
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
            showToast(`Scan completado: ${name}`, 'success', id);
            playNotificationSound();
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

    // Load recidivism and issue type stats in parallel
    _loadRecidivism();
    _loadIssueTypeStats();
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
        
        const tbody = document.getElementById('results-table-body');
        if (data.scans && data.scans.length > 0) {
            // Actualizar baseline del polling con el scan más reciente visible
            if (data.scans[0].id > (_lastKnownScanId || 0)) {
                _lastKnownScanId = data.scans[0].id;
            }
            tbody.innerHTML = data.scans.map(scan => `
                <tr style="cursor:pointer" onclick="viewScanDetails(${scan.id})">
                    <td>
                        <div class="scan-details-cell">
                            <div class="scan-avatar-circle">${_scanInitials(scan.machine_name)}</div>
                            <div>
                                <div class="scan-machine-name"
                                    onclick="event.stopPropagation();viewPlayerProfile(${JSON.stringify(scan.machine_name || '')})"
                                    title="Ver perfil del jugador"
                                    style="cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px;"
                                >${scan.machine_name || 'N/A'}</div>
                                <div class="scan-date-small">${formatDate(scan.started_at)}</div>
                                ${scan.scanned_by ? `<div style="font-size:10px;color:var(--text-d);margin-top:1px;">por <strong style="color:var(--text-s);">${scan.scanned_by}</strong></div>` : ''}
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="game-badge">
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><rect x="1" y="1" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.2"/><path d="M4 6H8M6 4V8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                            Minecraft
                        </span>
                    </td>
                    <td>${_resultBadge(scan)}</td>
                    <td><div class="indicator-dots">${_indicatorDots(scan)}</div></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();viewScanDetails(${scan.id})">
                            Ver detalles
                        </button>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay escaneos</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando escaneos:', error);
    }
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
        'HACKS': '⚔️ Hacks', 'HACK_FILES': '📦 Archivos', 'MACRO_DETECTION': '🖱️ Macros',
        'JAVA_MEMORY': '☕ Java', 'JAVA_AGENT': '🔌 Agentes', 'NETWORK_FORENSICS': '🌐 Red',
        'SYSTEM_TAMPERING': '⚙️ Sistema', 'RECENT_FILES': '📅 Recientes',
        'REGISTRY': '📋 Registro', 'PROCESS': '⚙️ Procesos',
        'VPN': '🔒 VPN', 'EVASION': '🛡️ Evasión', 'EXECUTED_FILES': '▶️ Ejecutados',
        'FORENSE': '🔬 Forense', 'TEXTURE_PACKS': '🎨 Texturas', 'OBFUSCATION': '🔀 Ofuscación',
        'JAR_FILES': '📦 JARs', 'MINECRAFT': '⛏️ Minecraft',
        'DELETED_FILES': '🗑️ Borrados', 'PROCESSES': '⚙️ Procesos', 'DNS_CACHE': '🌐 DNS',
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

    const chips = cats.map(c => {
        const count = c === 'all' ? all.length : all.filter(r => (r.issue_category || 'Otro') === c).length;
        const active = _issuesFilter === c;
        return `<button onclick="_setIssueFilter('${c}',${scanId})" style="
            font-size:11px;padding:4px 10px;border-radius:20px;cursor:pointer;font-weight:600;
            border:1px solid ${active ? '#8B5CF6' : 'var(--border-m)'};
            background:${active ? 'rgba(139,92,246,0.15)' : 'var(--bg-t)'};
            color:${active ? '#8B5CF6' : 'var(--text-m)'};white-space:nowrap;">
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

        return `<div data-result-id="${result.id}" style="
            background:${bg};border:1px solid ${accent}33;border-left:3px solid ${accent};
            border-radius:8px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px;
            overflow:hidden;max-width:100%;min-width:0;">
            <span style="font-size:14px;flex-shrink:0;margin-top:1px;">${dot}</span>
            <div style="flex:1;min-width:0;overflow:hidden;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);display:flex;align-items:center;gap:6px;flex-wrap:nowrap;min-width:0;overflow:hidden;">
                    <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;word-break:break-all;min-width:0;flex:1;">${name}</span>
                    ${instBadge}
                    ${cat ? `<span style="font-size:10px;font-weight:500;color:var(--text-d);background:var(--bg-t);border:1px solid var(--border-m);padding:1px 6px;border-radius:4px;flex-shrink:0;white-space:nowrap;">${_getCategoryLabel(cat)}</span>` : ''}
                </div>
                ${truncPath ? `<div style="font-size:11px;color:var(--text-d);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;" title="${path}">${truncPath}</div>` : ''}
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
    if (!reason) { if (errEl) errEl.style.display = 'block'; return; }
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
            openHackSelection();
        } else {
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
        _set('log-severe', severityStats.severe);
        _set('log-alert',  severityStats.alert);
        _set('log-clean',  severityStats.clean + severityStats.low);
        _set('ring-num-critical', severityStats.severe);
        _set('ring-num-alert',    severityStats.alert);
        _set('ring-num-low',      severityStats.low);
        _set('ring-num-clean',    severityStats.clean);

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
        const response = await fetch(`/api/scans?machine_name=${encodeURIComponent(machineName)}&limit=10`);
        const data = await response.json();
        
        const container = document.getElementById('previous-scans-list');
        if (!container) return;
        
        const allScans  = data.scans || [];
        const prevScans = allScans.filter(s => s.id !== currentScanId);
        const current   = allScans.find(s => s.id === currentScanId);

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

