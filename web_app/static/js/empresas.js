/**
 * Funciones de gestión de empresas - ASPERS Projects
 */

// ============================================================
// GESTIÓN DE EMPRESAS
// ============================================================

async function loadCompanyInfo() {
    try {
        const response = await fetch('/api/company/info');
        const data = await response.json();
        
        const card = document.getElementById('company-info-card');
        if (!card) return;
        
        if (data.success && data.company) {
            const company = data.company;
            const usedUsers = company.current_users || 0;
            const maxUsers = company.max_users || 8;
            const usedAdmins = company.current_admins || 0;
            const maxAdmins = company.max_admins || 3;
            
            card.innerHTML = `
                <h3 class="card-title">Información de la Empresa</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px;">
                    <div>
                        <strong>Nombre:</strong> ${company.name || 'N/A'}
                    </div>
                    <div>
                        <strong>Email de contacto:</strong> ${company.contact_email || 'N/A'}
                    </div>
                    <div>
                        <strong>Teléfono:</strong> ${company.contact_phone || 'N/A'}
                    </div>
                    <div>
                        <strong>Estado de suscripción:</strong> 
                        <span class="badge badge-${company.subscription_status === 'active' ? 'success' : 'danger'}">
                            ${company.subscription_status || 'N/A'}
                        </span>
                    </div>
                    <div>
                        <strong>Usuarios:</strong> ${usedUsers} / ${maxUsers}
                        <div style="width: 100%; background: #1e2329; border-radius: 4px; height: 8px; margin-top: 4px;">
                            <div style="width: ${(usedUsers / maxUsers) * 100}%; background: ${usedUsers >= maxUsers ? '#ef4444' : '#10b981'}; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    <div>
                        <strong>Administradores:</strong> ${usedAdmins} / ${maxAdmins}
                        <div style="width: 100%; background: #1e2329; border-radius: 4px; height: 8px; margin-top: 4px;">
                            <div style="width: ${(usedAdmins / maxAdmins) * 100}%; background: ${usedAdmins >= maxAdmins ? '#ef4444' : '#3b82f6'}; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            card.innerHTML = '<div class="loading-cell">Error al cargar información de la empresa</div>';
        }
    } catch (error) {
        console.error('Error cargando información de empresa:', error);
        const card = document.getElementById('company-info-card');
        if (card) {
            card.innerHTML = '<div class="loading-cell">Error al cargar información de la empresa</div>';
        }
    }
}

async function loadCompanyTokens() {
    // Cargar tokens de ESCANEO de la empresa
    try {
        const scanTokensResponse = await fetch('/api/company/scan-tokens');
        const scanTokensData = await scanTokensResponse.json();
        
        const scanTokensTbody = document.getElementById('company-scan-tokens-table-body');
        if (scanTokensTbody) {
            if (scanTokensData.success && scanTokensData.tokens && scanTokensData.tokens.length > 0) {
                scanTokensTbody.innerHTML = scanTokensData.tokens.map(token => {
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
                    
                    const createdDate = token.created_at ? new Date(token.created_at) : null;
                    
                    return `
                        <tr>
                            <td><code style="font-size: 11px;">${tokenStr.substring(0, 20)}...</code></td>
                            <td>${usedCount}${maxUses > 0 ? ` / ${maxUses}` : ' / ∞'}</td>
                            <td>${createdDate ? createdDate.toLocaleString('es-ES') : 'N/A'}</td>
                            <td>${token.created_by || 'N/A'}</td>
                            <td><span class="badge ${statusBadge}">${statusText}</span></td>
                            <td>
                                <button class="btn btn-sm btn-danger" onclick="if(typeof deleteToken === 'function') { deleteToken(${token.id}); } else { alert('Función deleteToken no disponible'); }" title="Eliminar permanentemente este token">
                                    🗑️ Eliminar
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } else {
                scanTokensTbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No hay tokens de escaneo</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error cargando tokens de escaneo de empresa:', error);
        const scanTokensTbody = document.getElementById('company-scan-tokens-table-body');
        if (scanTokensTbody) {
            scanTokensTbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Error al cargar tokens</td></tr>';
        }
    }
    
    // Cargar tokens de REGISTRO de la empresa
    try {
        const response = await fetch('/api/company/registration-tokens?include_used=false');
        const data = await response.json();
        
        const tbody = document.getElementById('company-tokens-table-body');
        if (!tbody) return;
        
        if (data.success && data.tokens && data.tokens.length > 0) {
            tbody.innerHTML = data.tokens.map(token => {
                const createdDate = new Date(token.created_at);
                const expiresDate = token.expires_at ? new Date(token.expires_at) : null;
                const isExpired = expiresDate && expiresDate < new Date();
                const tokenSnippet = token.token.substring(0, 20) + '...';
                const tokenType = token.is_admin_token ? 'ADMIN' : 'USUARIO';
                
                // Determinar el estado: si está expirado, mostrar EXPIRADO; si está usado, mostrar USADO; si no, mostrar ACTIVO
                let statusBadge = '';
                let statusText = '';
                if (isExpired) {
                    statusBadge = 'badge-danger';
                    statusText = 'EXPIRADO';
                } else if (token.is_used) {
                    statusBadge = 'badge-warning';
                    statusText = 'USADO';
                } else {
                    statusBadge = 'badge-success';
                    statusText = 'ACTIVO';
                }
                
                return `
                    <tr>
                        <td><code style="font-size: 12px;">${tokenSnippet}</code></td>
                        <td><span class="badge badge-${token.is_admin_token ? 'info' : 'success'}">${tokenType}</span></td>
                        <td>${createdDate.toLocaleString('es-ES')}</td>
                        <td>${expiresDate ? expiresDate.toLocaleString('es-ES') : 'Sin expiración'}</td>
                        <td>
                            <span class="badge ${statusBadge}">
                                ${statusText}
                            </span>
                        </td>
                    </tr>
                `;
            }).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay tokens de registro</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando tokens de registro de empresa:', error);
        const tbody = document.getElementById('company-tokens-table-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error al cargar tokens</td></tr>';
        }
    }
}

async function loadCompanyUsers() {
    try {
        const response = await fetch('/api/company/users');
        const data = await response.json();
        
        const tbody = document.getElementById('company-users-table-body');
        if (!tbody) return;
        
        if (data.success && data.users && data.users.length > 0) {
            tbody.innerHTML = data.users.map(user => {
                const lastLogin = user.last_login ? new Date(user.last_login).toLocaleString('es-ES') : 'Nunca';
                const roles = user.roles || [];
                const roleBadges = roles.map(role => {
                    if (role === 'admin') return '<span class="badge badge-warning">Admin</span>';
                    if (role === 'administrador') return '<span class="badge badge-info">Admin Empresa</span>';
                    if (role === 'empresa') return '<span class="badge badge-success">Empresa</span>';
                    if (role === 'staff') return '<span class="badge badge-success">Staff</span>';
                    return `<span class="badge badge-secondary">${role}</span>`;
                }).join(' ');
                
                return `
                    <tr>
                        <td>${user.username}</td>
                        <td>${user.email || 'N/A'}</td>
                        <td>${roleBadges}</td>
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
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">No hay usuarios en la empresa</td></tr>';
        }
    } catch (error) {
        console.error('Error cargando usuarios de empresa:', error);
        const tbody = document.getElementById('company-users-table-body');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading-cell">Error al cargar usuarios</td></tr>';
        }
    }
}

function setupCompanyListeners() {
    // Formulario de token de registro de empresa
    const companyTokenForm = document.getElementById('company-registration-token-form');
    if (companyTokenForm) {
        companyTokenForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const description = document.getElementById('company-reg-token-description').value;
            const expiresHours = parseInt(document.getElementById('company-reg-token-expires').value) || 24;
            const isAdminToken = document.getElementById('company-reg-token-is-admin').checked;
            
            try {
                const response = await fetch('/api/company/registration-tokens', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        description: description,
                        expires_hours: expiresHours,
                        is_admin_token: isAdminToken
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const resultDiv = document.getElementById('company-registration-token-result');
                    const tokenCode = document.getElementById('generated-company-registration-token');
                    
                    if (resultDiv && tokenCode) {
                        tokenCode.textContent = data.token;
                        resultDiv.style.display = 'block';
                        companyTokenForm.reset();
                        document.getElementById('company-reg-token-expires').value = 24;
                        loadCompanyTokens();
                    }
                } else {
                    alert('Error: ' + (data.error || 'Error desconocido'));
                }
            } catch (error) {
                console.error('Error creando token de empresa:', error);
                alert('Error al crear token de registro');
            }
        });
    }
    
    // Botón copiar token de empresa
    const copyCompanyTokenBtn = document.getElementById('copy-company-registration-token-btn');
    if (copyCompanyTokenBtn) {
        copyCompanyTokenBtn.addEventListener('click', function() {
            const tokenCode = document.getElementById('generated-company-registration-token');
            if (tokenCode) {
                const token = tokenCode.textContent;
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(token).then(() => {
                        copyCompanyTokenBtn.textContent = '✓ Copiado';
                        setTimeout(() => {
                            copyCompanyTokenBtn.textContent = 'Copiar';
                        }, 2000);
                    });
                } else {
                    // Fallback para navegadores antiguos
                    const textarea = document.createElement('textarea');
                    textarea.value = token;
                    document.body.appendChild(textarea);
                    textarea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textarea);
                    copyCompanyTokenBtn.textContent = '✓ Copiado';
                    setTimeout(() => {
                        copyCompanyTokenBtn.textContent = 'Copiar';
                    }, 2000);
                }
            }
        });
    }
}


