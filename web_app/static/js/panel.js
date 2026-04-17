/**
 * Panel del Staff - ASPERS Projects
 * Sistema de gestión y aprendizaje progresivo
 */

// Estado global
let currentScanId = null;
let currentResultId = null;

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
});

// ============================================================
// NAVEGACIÓN
// ============================================================

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
            'mi-empresa': 'mi-empresa'
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
        const response = await fetch('/api/scans?limit=50');
        const data = await response.json();
        
        const tbody = document.getElementById('results-table-body');
        if (data.scans && data.scans.length > 0) {
            tbody.innerHTML = data.scans.map(scan => `
                <tr style="cursor:pointer" onclick="viewScanDetails(${scan.id})">
                    <td>
                        <div class="scan-details-cell">
                            <div class="scan-avatar-circle">${_scanInitials(scan.machine_name)}</div>
                            <div>
                                <div class="scan-machine-name">${scan.machine_name || 'N/A'}</div>
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

let severityChart = null;

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
        
        // Calcular estadísticas de severidad
        const severityStats = {
            clean: 0,
            alert: 0,
            severe: 0
        };
        
        if (data.results && data.results.length > 0) {
            data.results.forEach(result => {
                const level = result.alert_level;
                if (level === 'CRITICAL') {
                    severityStats.severe++;
                } else if (level === 'SOSPECHOSO') {
                    severityStats.alert++;
                } else {
                    severityStats.clean++;
                }
            });
        }
        
        // Actualizar información del escaneo (columna izquierda)
        const scanIdEl = document.getElementById('detail-scan-id');
        if (scanIdEl) scanIdEl.textContent = scanId;
        
        const osEl = document.getElementById('detail-os');
        if (osEl) osEl.textContent = data.os || data.operating_system || 'Windows';
        
        const machineEl = document.getElementById('detail-machine-name');
        if (machineEl) machineEl.textContent = data.machine_name || 'N/A';
        
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
        
        // Actualizar contadores de severidad (columna derecha)
        document.getElementById('count-clean').textContent  = severityStats.clean;
        document.getElementById('count-alert').textContent  = severityStats.alert;
        document.getElementById('count-severe').textContent = severityStats.severe;

        // Mostrar/ocultar banner de detección
        const detectionBanner = document.getElementById('detection-banner');
        if (severityStats.severe > 0 || severityStats.alert > 0) {
            detectionBanner.style.display = 'flex';
        } else {
            detectionBanner.style.display = 'none';
        }
        
        // Generar gráfico donut
        updateSeverityChart(severityStats);
        
        // Cargar escaneos previos si existe la subpágina
        loadPreviousScans(data.machine_name || data.machine_id);
        
        // Inicializar navegación de subpáginas si no está inicializada
        if (typeof setupSubpageNavigation === 'function') {
            setupSubpageNavigation();
        }
        
        // Mostrar issues individuales con botones de feedback
        const issuesContainer = document.getElementById('issues-list-container');
        if (data.results && data.results.length > 0) {
            issuesContainer.innerHTML = data.results.map((result) => {
                const isCrit = result.alert_level === 'CRITICAL';
                const isSusp = result.alert_level === 'SOSPECHOSO';
                const borderColor = isCrit ? 'var(--red)' : isSusp ? 'var(--amber)' : 'var(--border-m)';
                const iconColor   = isCrit ? 'var(--red)' : isSusp ? 'var(--amber)' : 'var(--text-d)';
                const hasFeedback = result.feedback_status;

                const issueNameEscaped = (result.issue_name || 'Issue Desconocido').replace(/'/g, "\\'");
                const issuePathEscaped = (result.issue_path || 'N/A').replace(/'/g, "\\'");

                const feedbackTag = hasFeedback === 'hack'
                    ? '<span class="result-badge result-detected" style="font-size:10px;padding:2px 8px;">✓ Hack</span>'
                    : hasFeedback === 'legitimate'
                    ? '<span class="result-badge result-clean" style="font-size:10px;padding:2px 8px;">✓ Legítimo</span>'
                    : '';

                return `
                    <div class="echo-issue-row" data-result-id="${result.id}" style="border-left-color:${borderColor}">
                        <div class="echo-issue-icon-col">
                            <input type="checkbox" class="issue-checkbox" data-result-id="${result.id}" ${hasFeedback ? 'disabled' : ''} onchange="updateBulkActions()" style="margin:0">
                        </div>
                        <div class="echo-issue-x" style="color:${iconColor}">
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            </svg>
                        </div>
                        <div class="echo-issue-body">
                            <div class="echo-issue-name">${result.issue_name || 'Issue Desconocido'}</div>
                            <div class="echo-issue-path">${result.issue_path || 'N/A'}</div>
                            ${result.ai_analysis ? `<div class="echo-issue-analysis">${result.ai_analysis}</div>` : ''}
                            ${result.detected_patterns && result.detected_patterns.length > 0
                                ? `<div class="echo-issue-patterns">${result.detected_patterns.join(' · ')}</div>` : ''}
                        </div>
                        <div class="echo-issue-actions">
                            ${feedbackTag}
                            ${!hasFeedback ? `
                                <button class="echo-action-btn echo-action-hack" title="Marcar como Hack"
                                    onclick="markAsHack(${result.id}, ${scanId}, '${issueNameEscaped}', '${issuePathEscaped}')">
                                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M7 1.5L12.5 10.5H1.5L7 1.5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>
                                    Hack
                                </button>
                                <button class="echo-action-btn echo-action-legit" title="Marcar como Legítimo"
                                    onclick="markAsLegitimate(${result.id}, ${scanId}, '${issueNameEscaped}', '${issuePathEscaped}')">
                                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M2.5 7L5.5 10L11.5 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
                                    Legítimo
                                </button>
                            ` : `
                                <button class="echo-action-btn" title="Cambiar feedback"
                                    onclick="changeFeedback(${result.id}, ${scanId})">
                                    <svg width="13" height="13" viewBox="0 0 14 14" fill="none"><path d="M9.5 2.5L11.5 4.5L5 11H3V9L9.5 2.5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>
                                    Editar
                                </button>
                            `}
                        </div>
                    </div>
                `;
            }).join('');
            
            // Mostrar barra de acciones masivas si hay issues sin feedback
            const hasUnprocessedIssues = data.results.some(r => !r.feedback_status);
            if (hasUnprocessedIssues) {
                document.getElementById('bulk-actions-bar').style.display = 'flex';
            }

            updateBulkActions();
        } else {
            issuesContainer.innerHTML = '<div class="loading-cell">No se encontraron issues en este escaneo.</div>';
            document.getElementById('bulk-actions-bar').style.display = 'none';
        }

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

        // ── Poblar tabs por categoría ─────────────────────────────────────────
        const TAB_CATEGORIES = {
            'cuentas':            ['MINECRAFT', 'MINECRAFT_CONFIGS', 'NETWORK_CONNECTIONS'],
            'launcher-profiles':  ['JAR_FILES', 'JAVA_CMD', 'LAUNCHER'],
            'resource-packs':     ['texture_modification', 'RESOURCE_PACKS'],
            'historial-archivos': ['RECENT_FILES', 'DELETED_FILES', 'NEW_FILES', 'RENAMED_FILES', 'DATE_CHANGES'],
            'utilities':          ['AUTOCLICK_TOOLS', 'autoclicker', 'injection', 'LOGITECH', 'RAZER', 'USB_DEVICES'],
            'archivos-windows':   ['PREFETCH', 'JNA', 'TEMP_FILES', 'SERVICES', 'PROCESSES', 'BACKGROUND_PROCESSES', 'DNS_CACHE', 'HIDDEN_FILES'],
        };
        const allResults = data.results || [];

        Object.entries(TAB_CATEGORIES).forEach(([tab, cats]) => {
            const container = document.getElementById(`subpage-${tab}`);
            if (!container) return;
            const filtered = allResults.filter(r => cats.includes(r.issue_category));
            if (filtered.length === 0) {
                container.innerHTML = `<div class="subpage-placeholder"><p style="color:var(--text-m);font-size:13px;padding:40px 0;">Sin hallazgos en esta categoría.</p></div>`;
                return;
            }
            container.innerHTML = filtered.map(r => {
                const isCrit = r.alert_level === 'CRITICAL';
                const isSusp = r.alert_level === 'SOSPECHOSO' || r.alert_level === 'HACKS';
                const borderColor = isCrit ? 'var(--red)' : isSusp ? 'var(--amber)' : 'var(--border-m)';
                const iconColor   = isCrit ? 'var(--red)' : isSusp ? 'var(--amber)' : 'var(--text-d)';
                return `
                    <div class="echo-issue-row" style="border-left-color:${borderColor}">
                        <div class="echo-issue-x" style="color:${iconColor}">
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                            </svg>
                        </div>
                        <div class="echo-issue-body">
                            <div class="echo-issue-name">${r.issue_name || r.issue_type || 'Hallazgo'}</div>
                            <div class="echo-issue-path">${r.issue_path || ''}</div>
                            ${r.ai_analysis ? `<div class="echo-issue-analysis">${r.ai_analysis}</div>` : ''}
                        </div>
                    </div>`;
            }).join('');
        });

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
            
            // Remover active de todos los items
            subnavItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            // Ocultar todas las subpáginas
            document.querySelectorAll('.subpage-content').forEach(page => {
                page.classList.remove('active');
            });
            
            // Mostrar la subpágina seleccionada
            const targetPage = document.getElementById(`subpage-${subpage}`);
            if (targetPage) {
                targetPage.classList.add('active');
            }
        });
    });
}

async function loadPreviousScans(machineName) {
    try {
        const response = await fetch(`/api/scans?machine_name=${encodeURIComponent(machineName)}&limit=10`);
        const data = await response.json();
        
        const container = document.getElementById('previous-scans-list');
        if (!container) return;
        
        if (data.scans && data.scans.length > 1) {
            // Filtrar el escaneo actual
            const previousScans = data.scans.filter(s => s.id !== currentScanId);
            
            if (previousScans.length > 0) {
                container.innerHTML = previousScans.map(scan => {
                    const previewText = scan.severity_summary === 'CRITICO' ? '🔴 CRÍTICO' :
                                       scan.severity_summary === 'SOSPECHOSO' ? '🟠 SOSPECHOSO' :
                                       scan.severity_summary === 'POCO_SOSPECHOSO' ? '🟡 POCO SOSPECHOSO' :
                                       scan.severity_summary === 'LIMPIO' ? '🟢 LIMPIO' : '⚪ NORMAL';
                    
                    return `
                        <div class="previous-scan-item" onclick="viewScanDetails(${scan.id})">
                            <div class="previous-scan-header">
                                <span class="previous-scan-id">Escaneo #${scan.id}</span>
                                <span class="previous-scan-date">${formatDate(scan.started_at)}</span>
                            </div>
                            <div class="previous-scan-stats">
                                <span class="previous-scan-stat"><strong>${scan.issues_found || 0}</strong> issues</span>
                                <span class="previous-scan-stat"><strong>${scan.total_files_scanned || 0}</strong> archivos</span>
                                <span class="previous-scan-stat">${previewText}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                container.innerHTML = '<div class="loading-cell">No hay escaneos previos de esta máquina.</div>';
            }
        } else {
            container.innerHTML = '<div class="loading-cell">No hay escaneos previos de esta máquina.</div>';
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
                      '• downloads/MinecraftSSTool.exe\n' +
                      '• source/dist/MinecraftSSTool.exe\n' +
                      '• MinecraftSSTool.exe (raíz del proyecto)\n\n' +
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

