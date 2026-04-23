/**
 * Panel del Staff - ASPERS Projects
 * Sistema de gestión y aprendizaje progresivo
 */

// Estado global
let currentScanId = null;
let currentResultId = null;
let currentIssuesList = [];
let currentIssuesPage = 0;
const ISSUES_PER_PAGE = 25;
let _issuesFilter = 'all'; // filtro de categoría activo
let _currentScanData = null;

// Inicialización - OPTIMIZADO: Cargar datos críticos primero, el resto en background
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
    setupEventListeners();
    setupAdminListeners();
    setupCompanyListeners();

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
    const colors = { info: '#8B5CF6', success: '#10b981', error: '#ef4444' };
    const toast  = document.createElement('div');
    toast.style.cssText = `background:var(--bg-card,#1e1e2e);border:1px solid ${colors[type]||colors.info};border-left:3px solid ${colors[type]||colors.info};border-radius:10px;padding:12px 16px;font-size:13px;color:var(--text,#e2e8f0);box-shadow:0 4px 20px rgba(0,0,0,0.3);pointer-events:all;cursor:${scanId?'pointer':'default'};max-width:280px;animation:slideInRight .25s ease;`;
    toast.innerHTML = `<div style="font-weight:600;margin-bottom:2px;">Argus Projects</div><div style="color:var(--text-s,#94a3b8);">${message}</div>`;
    if (scanId) toast.onclick = () => { viewScanDetails(scanId); toast.remove(); };
    _toastContainer.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity .4s'; setTimeout(() => toast.remove(), 400); }, 5000);
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
            'mi-empresa': 'mi-empresa',
            'staff': 'staff',
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
        'resultados': 'Resultados de Escaneos - ASPERS Projects',
        'aprendizaje': 'Sistema de Aprendizaje - ASPERS Projects',
        'administracion': 'Administración - ASPERS Projects',
        'mi-empresa': 'Mi Empresa - ASPERS Projects'
    };
    const titleElement = document.getElementById('section-title');
    if (titleElement) {
        titleElement.textContent = titles[sectionName] || 'Panel Staff';
    }
    
    // Cargar datos específicos de cada sección
    if (sectionName === 'administracion') {
        loadRegistrationTokens();
        loadDownloadLinks(); // Cargar enlaces de descarga
        loadUsers();
        loadCompanyUsersForAdmin(); // Cargar usuarios de empresa para admin de empresa
    } else if (sectionName === 'mi-empresa') {
        loadCompanyInfo();
        loadCompanyTokens();
        loadCompanyUsers();
    } else if (sectionName === 'staff') {
        loadStaffUsers();
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

        document.getElementById('total-scans').textContent    = data.total_scans    || 0;
        document.getElementById('total-issues').textContent   = data.total_issues   || 0;
        document.getElementById('unique-machines').textContent = data.unique_machines || 0;
        document.getElementById('active-tokens').textContent  = data.active_tokens  || 0;

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
    if (scan.status === 'running')
        return '<span class="result-badge" style="background:rgba(99,102,241,0.12);color:#818cf8;border-color:rgba(99,102,241,0.3)">⏳ Escaneando</span>';
    const s = scan.severity_summary || '';
    if (s === 'CRITICO' || s === 'SOSPECHOSO')
        return '<span class="result-badge result-detected">Detectado</span>';
    if (s === 'POCO_SOSPECHOSO')
        return '<span class="result-badge result-suspicious">Sospechoso</span>';
    if (s === 'LIMPIO')
        return '<span class="result-badge result-clean">Limpio</span>';
    if (scan.status === 'completed')
        return '<span class="result-badge result-pending">Revisado</span>';
    return '<span class="result-badge result-pending">Pendiente</span>';
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
    try {
        const response = await fetch('/api/scans?limit=6');
        const data = await response.json();
        const container = document.getElementById('recent-scans');
        if (data.scans && data.scans.length > 0) {
            container.innerHTML = data.scans.map(scan => `
                <div class="echo-scan-row" onclick="viewScanDetails(${scan.id})">
                    <div class="scan-avatar-circle">${_scanInitials(scan.machine_name)}</div>
                    <div class="scan-row-info">
                        <div class="scan-row-machine">${scan.machine_name || 'N/A'}</div>
                        <div class="scan-row-date">${formatDate(scan.started_at)}</div>
                    </div>
                    <div class="indicator-dots">${_indicatorDots(scan)}</div>
                    ${_resultBadge(scan)}
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="echo-scan-row"><div class="scan-row-info"><div class="scan-row-machine" style="color:var(--text-d)">No hay escaneos recientes</div></div></div>';
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
                
                return `
                <tr>
                    <td><code>${tokenStr.substring(0, 20)}...</code></td>
                    <td>${token.created_at ? formatDate(token.created_at) : 'N/A'}</td>
                    <td>${token.created_by || 'N/A'}</td>
                    <td>${usedCount}${maxUses > 0 ? ` / ${maxUses}` : ' / ∞'}</td>
                    <td><span class="badge ${statusBadge}">${statusText}</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="deleteToken(${token.id || token.token_id})" title="Eliminar permanentemente este token">
                            🗑️ Eliminar
                        </button>
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

    // Botón de copiar token
    document.getElementById('copy-token-btn')?.addEventListener('click', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        const tokenElement = document.getElementById('generated-token');
        const token = tokenElement?.textContent;
        
        if (!token) {
            alert('No hay token para copiar');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(token);
            const btn = document.getElementById('copy-token-btn');
            const originalText = btn.textContent;
            btn.textContent = '✓ Copiado!';
            btn.style.background = '#22c55e';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (error) {
            // Fallback para navegadores que no soportan clipboard API
            const textArea = document.createElement('textarea');
            textArea.value = token;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                const btn = document.getElementById('copy-token-btn');
                const originalText = btn.textContent;
                btn.textContent = '✓ Copiado!';
                btn.style.background = '#22c55e';
                setTimeout(() => {
                    btn.textContent = originalText;
                    btn.style.background = '';
                }, 2000);
            } catch (err) {
                alert('Error al copiar. Por favor, copia manualmente: ' + token);
            }
            document.body.removeChild(textArea);
        }
    });
    
    // Botón de copiar enlace de descarga desde el modal de token
    document.getElementById('copy-download-link-from-token-btn')?.addEventListener('click', async () => {
        const linkInput = document.getElementById('generated-download-link-from-token');
        const link = linkInput?.value;
        
        if (!link) {
            alert('No hay enlace para copiar');
            return;
        }
        
        try {
            await navigator.clipboard.writeText(link);
            const btn = document.getElementById('copy-download-link-from-token-btn');
            const originalText = btn.textContent;
            btn.textContent = '✓ Copiado!';
            btn.style.background = '#22c55e';
            setTimeout(() => {
                btn.textContent = originalText;
                btn.style.background = '';
            }, 2000);
        } catch (err) {
            // Fallback para navegadores que no soportan clipboard API
            const textArea = document.createElement('textarea');
            textArea.value = link;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                document.body.removeChild(textArea);
                alert('✓ Enlace copiado al portapapeles');
            } catch (err2) {
                document.body.removeChild(textArea);
                alert('Error al copiar: ' + err2.message);
            }
        }
    });

    // Modal de feedback
    document.getElementById('close-feedback-modal')?.addEventListener('click', () => {
        document.getElementById('feedback-modal').classList.remove('active');
    });
    
    document.getElementById('cancel-feedback-btn')?.addEventListener('click', () => {
        document.getElementById('feedback-modal').classList.remove('active');
    });
    
    document.getElementById('feedback-form')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        await submitFeedback();
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

async function createToken() {
    const btn = document.getElementById('confirm-create-token-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Creando...'; }

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

        if (data.success && data.token) {
            document.getElementById('generated-token').textContent = data.token;
            const downloadLinkSection = document.getElementById('download-link-section');
            const downloadLinkInput = document.getElementById('generated-download-link-from-token');
            if (data.download_url && downloadLinkSection && downloadLinkInput) {
                downloadLinkInput.value = data.download_url;
                downloadLinkSection.style.display = 'block';
            } else if (downloadLinkSection) {
                downloadLinkSection.style.display = 'none';
            }
            document.getElementById('token-modal').classList.remove('active');
            document.getElementById('token-result-modal').classList.add('active');
            setTimeout(() => loadTokens(), 500);
        } else {
            alert('Error al crear token: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        console.error('Error creando token:', error);
        alert('Error al crear token: ' + error.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Crear Token'; }
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
        if (search)   params.set('search', search);
        if (verdict)  params.set('verdict', verdict);
        if (dateFrom) params.set('date_from', dateFrom);
        if (dateTo)   params.set('date_to', dateTo);

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
    const ids = ['filter-search','filter-verdict','filter-date-from','filter-date-to'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
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
    tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Cargando...</td></tr>';
    try {
        const res = await fetch('/api/staff/users');
        if (!res.ok) { tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">Sin acceso</td></tr>`; return; }
        const data = await res.json();
        if (!data.users || !data.users.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Sin usuarios</td></tr>';
            return;
        }
        tbody.innerHTML = data.users.map(u => {
            const roleOptions = STAFF_ROLES.map(r =>
                `<option value="${r}" ${u.staff_role === r ? 'selected' : ''}>${STAFF_ROLE_LABELS[r]}</option>`
            ).join('');
            return `<tr>
                <td><strong>${u.username}</strong>${u.email ? `<div style="font-size:11px;color:var(--text-d);">${u.email}</div>` : ''}</td>
                <td><span class="badge badge-${_staffBadge(u.staff_role)}">${STAFF_ROLE_LABELS[u.staff_role] || u.staff_role}</span></td>
                <td>${u.is_active ? '✅' : '❌'}</td>
                <td style="display:flex;gap:6px;align-items:center;">
                    <select id="role-sel-${u.id}" class="filter-select" style="min-width:110px;font-size:12px;padding:5px 8px;">${roleOptions}</select>
                    <button class="btn btn-sm btn-primary" onclick="updateStaffRole(${u.id})">Guardar</button>
                </td>
            </tr>`;
        }).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="4" class="loading-cell">Error: ${e.message}</td></tr>`;
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
    if (typeof window.CAN_TOKENS !== 'undefined' && !window.CAN_TOKENS) {
        const btn = document.getElementById('create-token-btn');
        if (btn) btn.style.display = 'none';
    }
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
    };
    return map[cat] || cat || 'Otro';
}

function renderIssuePage(container, scanId) {
    const all = currentIssuesList;
    if (!all || all.length === 0) {
        container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-d);font-size:13px;">Sin hallazgos críticos o sospechosos en este escaneo.</div>';
        return;
    }

    // Categorías disponibles
    const cats = ['all', ...new Set(all.map(r => r.issue_category || 'Otro').filter(Boolean))];
    const filtered = _issuesFilter === 'all' ? all : all.filter(r => (r.issue_category || 'Otro') === _issuesFilter);
    const showCount = (currentIssuesPage + 1) * ISSUES_PER_PAGE;
    const slice = filtered.slice(0, showCount);
    const hasMore = filtered.length > showCount;

    // Chips de categoría
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
    }).join('');

    const rows = slice.map((result) => {
        const isCrit = result.alert_level === 'CRITICAL';
        const isMid  = result.alert_level === 'SOSPECHOSO';
        const accent = isCrit ? '#ef4444' : isMid ? '#f59e0b' : '#6b7280';
        const bg     = isCrit ? 'rgba(239,68,68,0.05)' : isMid ? 'rgba(245,158,11,0.04)' : 'rgba(107,114,128,0.03)';
        const dot    = isCrit ? '🔴' : isMid ? '🟠' : '🔵';
        const cat    = result.issue_category || '';
        const hasFeedback = result.feedback_status;
        const name = result.issue_name || 'Hallazgo';
        const path = result.issue_path || '';
        const truncPath = path.length > 90 ? '…' + path.slice(-87) : path;

        return `<div data-result-id="${result.id}" style="
            background:${bg};border:1px solid ${accent}33;border-left:3px solid ${accent};
            border-radius:8px;padding:10px 14px;display:flex;align-items:flex-start;gap:10px;">
            <span style="font-size:14px;flex-shrink:0;margin-top:1px;">${dot}</span>
            <div style="flex:1;min-width:0;">
                <div style="font-size:12px;font-weight:600;color:var(--text-h);display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                    <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:380px;">${name}</span>
                    ${cat ? `<span style="font-size:10px;font-weight:500;color:var(--text-d);background:var(--bg-t);border:1px solid var(--border-m);padding:1px 6px;border-radius:4px;flex-shrink:0;">${_getCategoryLabel(cat)}</span>` : ''}
                </div>
                ${truncPath ? `<div style="font-size:11px;color:var(--text-d);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${path}">${truncPath}</div>` : ''}
            </div>
            <div style="display:flex;gap:6px;flex-shrink:0;align-items:center;margin-top:1px;">
                ${hasFeedback === 'hack'
                    ? `<span style="font-size:10px;font-weight:700;padding:3px 8px;border-radius:5px;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);">Hack</span>`
                    : hasFeedback === 'legitimate'
                    ? `<span style="font-size:10px;font-weight:700;padding:3px 8px;border-radius:5px;background:rgba(16,185,129,0.12);color:#10b981;border:1px solid rgba(16,185,129,0.25);">Legítimo</span>`
                    : ''}
                ${hasFeedback ? `<button onclick="changeFeedback(${result.id},${scanId})"
                    style="font-size:11px;padding:3px 8px;border-radius:5px;border:1px solid var(--border-m);background:var(--bg-t);color:var(--text-m);cursor:pointer;" title="Cambiar veredicto">✎</button>` : ''}
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
    const unprocessed = currentIssuesList.filter(r => !r.feedback_status);
    if (!unprocessed.length) { skipVerdict(); return; }
    try {
        const res = await fetch('/api/feedback/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ result_ids: unprocessed.map(r => r.id), verification: 'legitimate', notes: reason || 'Usuario limpio confirmado por staff' })
        });
        if (!res.ok) throw new Error(await res.text());
        unprocessed.forEach(r => r.feedback_status = 'legitimate');
        document.getElementById('bulk-actions-bar').style.display = 'none';
        const container = document.getElementById('issues-list-container');
        if (container) renderIssuePage(container, currentScanId);
    } catch (e) {
        alert('Error al enviar veredicto: ' + e.message);
    }
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
        const already = r.feedback_status;
        return `<label style="display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:7px;border:1px solid var(--border-m);background:var(--bg-t);cursor:pointer;">
            <input type="checkbox" data-result-id="${r.id}" ${already === 'hack' ? 'checked' : ''} ${already === 'legitimate' ? 'disabled' : ''} style="width:15px;height:15px;flex-shrink:0;cursor:pointer;">
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
        if (!result || result.feedback_status) return;
        if (cb.checked) hackIds.push(id);
        else cleanIds.push(id);
    });

    if (!hackIds.length && !cleanIds.length) { skipHackSelection(); return; }

    try {
        const requests = [];
        if (hackIds.length) requests.push(fetch('/api/feedback/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ result_ids: hackIds, verification: 'hack', notes: 'Hack confirmado por staff' }) }));
        if (cleanIds.length) requests.push(fetch('/api/feedback/batch', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ result_ids: cleanIds, verification: 'legitimate', notes: 'Legítimo confirmado por staff' }) }));
        await Promise.all(requests);

        hackIds.forEach(id => { const r = currentIssuesList.find(x => x.id === id); if (r) r.feedback_status = 'hack'; });
        cleanIds.forEach(id => { const r = currentIssuesList.find(x => x.id === id); if (r) r.feedback_status = 'legitimate'; });

        skipHackSelection();
        const container = document.getElementById('issues-list-container');
        if (container) renderIssuePage(container, currentScanId);
        const hasUnprocessed = currentIssuesList.some(r => !r.feedback_status);
        document.getElementById('bulk-actions-bar').style.display = hasUnprocessed ? 'flex' : 'none';
        alert(`Feedback enviado: ${hackIds.length} hack(s), ${cleanIds.length} legítimo(s).`);
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
        // Actualizar tarjetas de resumen
        const sc = document.getElementById('sum-critical'); if (sc) sc.textContent = severityStats.severe;
        const ss = document.getElementById('sum-suspicious'); if (ss) ss.textContent = severityStats.alert;
        const sl = document.getElementById('sum-low'); if (sl) sl.textContent = severityStats.low;
        const sk = document.getElementById('sum-clean'); if (sk) sk.textContent = severityStats.clean;
        
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
        } else if (severityStats.severe > 0 || severityStats.alert > 0) {
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
        const _alertOrder = { CRITICAL: 0, SOSPECHOSO: 1, MUY_SOSPECHOSO: 2, POCO_SOSPECHOSO: 3 };
        currentIssuesList = (data.results || [])
            .filter(r => r.alert_level && r.alert_level !== 'CLEAN')
            .sort((a, b) => (_alertOrder[a.alert_level] ?? 9) - (_alertOrder[b.alert_level] ?? 9));
        renderIssuePage(issuesContainer, scanId);

        const hasUnprocessed = currentIssuesList.some(r => !r.feedback_status);
        document.getElementById('bulk-actions-bar').style.display = (currentIssuesList.length > 0 && hasUnprocessed) ? 'flex' : 'none';
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

        // Ejecutados
        const EXECUTED_TYPES = new Set([
            'prefetch_history','prefetch_suspicious','userassist_history','userassist_suspicious',
            'bam_history','bam_suspicious','recent_lnk_history','recent_lnk_suspicious',
            'shimcache_history','shimcache_suspicious','muicache_history','muicache_suspicious',
            'minecraft_process_info',
        ]);
        const ejecutados = allResults.filter(r => r.issue_category === 'EXECUTED_FILES' || EXECUTED_TYPES.has(r.issue_type));
        const ejBtn = document.getElementById('subnav-ejecutados');
        if (ejBtn) ejBtn.style.display = ejecutados.length > 0 ? '' : 'none';
        const ejList = document.getElementById('ejecutados-list');
        if (ejList && ejecutados.length > 0) {
            ejList.innerHTML = ejecutados.map(r => {
                const isSusp = r.alert_level === 'CRITICAL' || r.alert_level === 'SOSPECHOSO';
                const accent = isSusp ? '#ef4444' : '#38bdf8';
                const bg = isSusp ? 'rgba(239,68,68,0.06)' : 'rgba(56,189,248,0.04)';
                return `<div style="background:${bg};border:1px solid ${accent}33;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:12px;font-weight:600;color:${accent};">${isSusp?'⚠️ ':'▶️ '}${r.issue_name||r.issue_path||'—'}</div>
                    ${r.issue_path?`<div style="font-size:11px;color:var(--text-d);margin-top:3px;word-break:break-all;">${r.issue_path}</div>`:''}
                    ${r.alert_level?`<div style="margin-top:4px;font-size:10px;font-weight:700;color:${accent};text-transform:uppercase;">${r.alert_level}</div>`:''}
                </div>`;
            }).join('');
        } else if (ejList) {
            ejList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin historial de ejecutados para este escaneo.</p>';
        }

        // Eliminados
        const eliminados = allResults.filter(r => r.issue_category === 'DELETED_FILES' || r.issue_type === 'deleted_suspicious' || r.issue_type === 'deleted_history');
        const elBtn = document.getElementById('subnav-eliminados');
        if (elBtn) elBtn.style.display = eliminados.length > 0 ? '' : 'none';
        const elList = document.getElementById('eliminados-list');
        if (elList && eliminados.length > 0) {
            elList.innerHTML = eliminados.map(r => {
                const isSusp = r.alert_level === 'CRITICAL' || r.alert_level === 'SOSPECHOSO';
                const accent = isSusp ? '#ef4444' : '#f59e0b';
                return `<div style="background:rgba(${isSusp?'239,68,68':'245,158,11'},0.06);border:1px solid ${accent}33;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:12px;font-weight:600;color:${accent};">🗑️ ${r.issue_name||r.issue_path||'—'}</div>
                    ${r.issue_path?`<div style="font-size:11px;color:var(--text-d);margin-top:3px;word-break:break-all;">${r.issue_path}</div>`:''}
                </div>`;
            }).join('');
        } else if (elList) {
            elList.innerHTML = '<p style="color:var(--text-m);font-size:13px;">Sin archivos eliminados detectados para este escaneo.</p>';
        }

        // Comandos (CMD + PowerShell + descargas + tareas programadas)
        const CMD_TYPES = new Set([
            'cmd_history','cmd_history_full','powershell_history','powershell_suspicious',
            'browser_download_history','browser_download_suspicious','scheduled_task_suspicious',
        ]);
        const comandos = allResults.filter(r => r.issue_category === 'CMD_HISTORY' || CMD_TYPES.has(r.issue_type));
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

    } catch (error) {
        console.error('Error cargando detalles:', error);
        alert('Error al cargar detalles del escaneo: ' + error.message);
    }
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
        });
    });
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
                    <div class="previous-scan-item" onclick="viewScanDetails(${scan.id})">
                        <div class="previous-scan-header">
                            <span class="previous-scan-id">Escaneo #${scan.id} ${verdictBadge}</span>
                            <span class="previous-scan-date">${formatDate(scan.started_at)}</span>
                        </div>
                        <div class="previous-scan-stats">
                            <span class="previous-scan-stat"><strong>${scan.issues_found || 0}</strong> issues ${diffBadge}</span>
                            <span class="previous-scan-stat"><strong>${scan.total_files_scanned || 0}</strong> archivos</span>
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

// Función para marcar como hack (ahora abre el modal mejorado)
async function markAsHack(resultId, scanId, issueName, issuePath) {
    openFeedbackModal(resultId, issueName, issuePath, 'hack', scanId);
}

// Función para marcar como legítimo (ahora abre el modal mejorado)
async function markAsLegitimate(resultId, scanId, issueName, issuePath) {
    openFeedbackModal(resultId, issueName, issuePath, 'legitimate', scanId);
}

// Función para cambiar feedback (ahora abre el modal mejorado)
async function changeFeedback(resultId, scanId) {
    // Obtener información del resultado para mostrar en el modal
    try {
        const response = await fetch(`/api/scans/${scanId}/results`);
        if (response.ok) {
            const data = await response.json();
            const result = data.results?.find(r => r.id === resultId);
            if (result) {
                // Pre-seleccionar el feedback actual si existe
                const currentFeedback = result.feedback_status || null;
                openFeedbackModal(resultId, result.issue_name, result.issue_path, currentFeedback, scanId);
            } else {
                openFeedbackModal(resultId, 'Archivo', 'Ruta desconocida', null, scanId);
            }
        } else {
            openFeedbackModal(resultId, 'Archivo', 'Ruta desconocida', null, scanId);
        }
    } catch (error) {
        openFeedbackModal(resultId, 'Archivo', 'Ruta desconocida', null, scanId);
    }
}

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

function openFeedbackModal(resultId, fileName, filePath, verificationType, scanId) {
    currentResultId = resultId;
    
    // Establecer valores en campos ocultos
    const resultIdEl = document.getElementById('feedback-result-id');
    const scanIdEl = document.getElementById('feedback-scan-id');
    if (resultIdEl) resultIdEl.value = resultId;
    if (scanIdEl && scanId) scanIdEl.value = scanId;
    
    // Actualizar preview del archivo mejorado
    const fileNameEl = document.getElementById('feedback-file-name');
    const filePathEl = document.getElementById('feedback-file-path');
    
    if (fileNameEl) fileNameEl.textContent = fileName || 'Nombre no disponible';
    if (filePathEl) filePathEl.textContent = filePath || 'Ruta no disponible';
    
    // Resetear formulario
    const form = document.getElementById('feedback-form');
    const notesEl = document.getElementById('feedback-notes');
    if (form) form.reset();
    if (notesEl) notesEl.value = '';
    
    // Restablecer valores ocultos después del reset
    if (resultIdEl) resultIdEl.value = resultId;
    if (scanIdEl && scanId) scanIdEl.value = scanId;
    
    // Pre-seleccionar según el tipo de verificación
    const hackRadio = document.querySelector('input[value="hack"]');
    const legitRadio = document.querySelector('input[value="legitimate"]');
    
    if (verificationType === 'hack' && hackRadio) {
        hackRadio.checked = true;
    } else if (verificationType === 'legitimate' && legitRadio) {
        legitRadio.checked = true;
    } else {
        // Deseleccionar todo si no hay tipo específico
        if (hackRadio) hackRadio.checked = false;
        if (legitRadio) legitRadio.checked = false;
    }
    
    document.getElementById('scan-details-modal')?.classList.remove('active');
    document.getElementById('feedback-modal').classList.add('active');
}

async function submitFeedback() {
    const verificationRadio = document.querySelector('input[name="verification"]:checked');
    if (!verificationRadio) {
        alert('Por favor selecciona si es un hack o un archivo legítimo');
        return;
    }
    
    const verification = verificationRadio.value;
    const notes = document.getElementById('feedback-notes').value;
    const resultIdEl = document.getElementById('feedback-result-id');
    const scanIdEl = document.getElementById('feedback-scan-id');

    const resultId = currentResultId || (resultIdEl ? resultIdEl.value : null);
    const scanId = scanIdEl ? scanIdEl.value : null;

    if (!resultId) {
        alert('Error: No hay resultado seleccionado');
        return;
    }

    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                result_id: parseInt(resultId),
                scan_id: scanId ? parseInt(scanId) : null,
                verification: verification,
                notes: notes,
                verified_by: 'staff'
            })
        });

        const data = await response.json();
        if (data.success) {
            alert(`✅ Feedback enviado exitosamente.\n\nASPERS Projects ha aprendido de este resultado.\n${data.extracted_patterns && data.extracted_patterns.length > 0 ? `Patrones extraídos: ${data.extracted_patterns.join(', ')}` : ''}\n\n${data.should_update_model ? '⚠️ Se recomienda actualizar el modelo de IA.' : ''}`);
            
            document.getElementById('feedback-modal').classList.remove('active');
            if (currentScanId) {
                viewScanDetails(currentScanId);
            }
            loadLearningStats();
        } else {
            alert('Error al enviar feedback: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        alert('Error al enviar feedback: ' + error.message);
    }
}

// ============================================================
// FEEDBACK MASIVO
// ============================================================

// Hacer funciones disponibles globalmente
window.updateBulkActions = function() {
    const checkboxes = document.querySelectorAll('.issue-checkbox:not(:disabled)');
    const checked = document.querySelectorAll('.issue-checkbox:not(:disabled):checked');
    const selectedCount = checked.length;
    
    const bulkBar = document.getElementById('bulk-actions-bar');
    const selectedCountSpan = document.getElementById('selected-count');
    const bulkHackBtn = document.getElementById('bulk-mark-hack-btn');
    const bulkLegitimateBtn = document.getElementById('bulk-mark-legitimate-btn');
    
    if (selectedCountSpan) {
        selectedCountSpan.textContent = selectedCount;
    }
    
    if (bulkHackBtn && bulkLegitimateBtn) {
        bulkHackBtn.disabled = selectedCount === 0;
        bulkLegitimateBtn.disabled = selectedCount === 0;
    }
}

window.selectAll = function() {
    const checkboxes = document.querySelectorAll('.issue-checkbox:not(:disabled)');
    checkboxes.forEach(cb => cb.checked = true);
    updateBulkActions();
}

window.deselectAll = function() {
    const checkboxes = document.querySelectorAll('.issue-checkbox:checked');
    checkboxes.forEach(cb => cb.checked = false);
    updateBulkActions();
}

async function submitBulkFeedback(verification) {
    const checked = document.querySelectorAll('.issue-checkbox:not(:disabled):checked');
    if (checked.length === 0) {
        alert('Por favor selecciona al menos un archivo');
        return;
    }
    
    const resultIds = Array.from(checked).map(cb => parseInt(cb.dataset.resultId));
    const count = resultIds.length;
    
    const confirmMessage = verification === 'hack' 
        ? `¿Estás seguro de marcar ${count} archivo(s) como HACK?\n\nEsta acción mejorará el aprendizaje de ASPERS Projects.`
        : `¿Estás seguro de marcar ${count} archivo(s) como LEGÍTIMO?\n\nEsta acción mejorará el aprendizaje de ASPERS Projects.`;
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    // Deshabilitar botones mientras se procesa
    const bulkHackBtn = document.getElementById('bulk-mark-hack-btn');
    const bulkLegitimateBtn = document.getElementById('bulk-mark-legitimate-btn');
    const originalHackText = bulkHackBtn.innerHTML;
    const originalLegitimateText = bulkLegitimateBtn.innerHTML;
    
    bulkHackBtn.disabled = true;
    bulkLegitimateBtn.disabled = true;
    bulkHackBtn.innerHTML = '⏳ Procesando...';
    bulkLegitimateBtn.innerHTML = '⏳ Procesando...';
    
    try {
        const response = await fetch('/api/feedback/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                result_ids: resultIds,
                verification: verification,
                notes: `Feedback masivo: ${count} archivos marcados como ${verification}`,
                verified_by: 'staff'
            })
        });

        const data = await response.json();
        if (data.success) {
            const message = `✅ ${data.processed} de ${data.total} archivos procesados exitosamente.\n\n` +
                          `ASPERS Projects ha aprendido de estos resultados.\n` +
                          (data.extracted_patterns && data.extracted_patterns.length > 0 
                            ? `Patrones extraídos: ${data.extracted_patterns.join(', ')}\n` 
                            : '') +
                          (data.errors && data.errors.length > 0 
                            ? `\n⚠️ Errores: ${data.errors.join(', ')}` 
                            : '') +
                          (data.should_update_model ? '\n\n⚠️ Se recomienda actualizar el modelo de IA.' : '');
            
            alert(message);
            
            // Deseleccionar todos y recargar la vista
            deselectAll();
            if (currentScanId) {
                viewScanDetails(currentScanId);
            }
            loadLearningStats();
        } else {
            alert('Error al enviar feedback masivo: ' + (data.error || 'Error desconocido'));
        }
    } catch (error) {
        alert('Error al enviar feedback masivo: ' + error.message);
    } finally {
        // Restaurar botones
        bulkHackBtn.disabled = false;
        bulkLegitimateBtn.disabled = false;
        bulkHackBtn.innerHTML = originalHackText;
        bulkLegitimateBtn.innerHTML = originalLegitimateText;
        updateBulkActions();
    }
}

// Event listeners para acciones masivas y navegación de subpáginas
document.addEventListener('DOMContentLoaded', () => {
    const bulkHackBtn = document.getElementById('bulk-mark-hack-btn');
    const bulkLegitimateBtn = document.getElementById('bulk-mark-legitimate-btn');
    const bulkSelectAllBtn = document.getElementById('bulk-select-all-btn');
    const bulkDeselectBtn = document.getElementById('bulk-deselect-all-btn');
    
    if (bulkHackBtn) {
        bulkHackBtn.addEventListener('click', () => submitBulkFeedback('hack'));
    }
    
    if (bulkLegitimateBtn) {
        bulkLegitimateBtn.addEventListener('click', () => submitBulkFeedback('legitimate'));
    }
    
    if (bulkSelectAllBtn) {
        bulkSelectAllBtn.addEventListener('click', selectAll);
    }
    
    if (bulkDeselectBtn) {
        bulkDeselectBtn.addEventListener('click', deselectAll);
    }
    
    // Inicializar navegación de subpáginas
    setupSubpageNavigation();
});

// ============================================================
// APRENDIZAJE DE IA
// ============================================================

async function loadLearningStats() {
    try {
        const response = await fetch('/api/learned-patterns');
        const data = await response.json();
        
        document.getElementById('learned-patterns-count').textContent = data.total || 0;
        
        // Cargar hashes (simulado por ahora)
        // En producción, esto vendría de un endpoint específico
        document.getElementById('learned-hashes-count').textContent = '0';
        document.getElementById('total-feedbacks-count').textContent = '0';
    } catch (error) {
        console.error('Error cargando estadísticas de aprendizaje:', error);
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
// UTILIDADES
// ============================================================

function exportScanCSV() {
    if (!currentScanId) return;
    window.open(`/api/scans/${currentScanId}/export/csv`, '_blank');
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

