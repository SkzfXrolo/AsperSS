/**
 * Argus UI Kit — toasts, empty states, skeleton loaders.
 *
 * Visual #5  Skeleton loaders
 * Visual #6  Toast system (reemplaza alert() con feedback no bloqueante)
 * Visual #25 Empty states ilustrados
 *
 * Cargado ANTES de panel.js. Expone:
 *   - showToast(message, type, options)
 *   - renderEmptyState(target, config)
 *   - renderSkeleton(target, count)
 *   - sustituye window.alert por una versión que muestra un toast
 *     auto-detectando el tipo a partir del prefijo (✅ / ⚠️ / ❌ / sin emoji).
 */

(function () {
    'use strict';

    // ── Container ────────────────────────────────────────────────────────────
    function _ensureContainer() {
        let c = document.getElementById('argus-toast-container');
        if (c) return c;
        c = document.createElement('div');
        c.id = 'argus-toast-container';
        c.setAttribute('aria-live', 'polite');
        c.setAttribute('aria-atomic', 'false');
        document.body.appendChild(c);
        return c;
    }

    // ── Toast core ───────────────────────────────────────────────────────────

    /**
     * Muestra una notificación tipo toast.
     *
     * @param {string} message  Texto principal (puede contener \n).
     * @param {string} [type]   'info' | 'success' | 'warning' | 'error'.
     *                          Default: 'info'.
     * @param {object} [opts]
     * @param {number} [opts.duration]  ms hasta auto-cierre (default 4500;
     *                                  6500 para 'error').
     * @param {string} [opts.title]     título opcional encima del mensaje.
     * @param {boolean} [opts.dismissible] mostrar botón ×. Default true.
     */
    function showToast(message, type, opts) {
        type = type || 'info';
        opts = opts || {};
        const container = _ensureContainer();

        const ICONS = {
            info:    'i',
            success: '✓',
            warning: '!',
            error:   '×',
        };
        const TITLES = {
            info:    null,
            success: opts.title || 'Listo',
            warning: opts.title || 'Atención',
            error:   opts.title || 'Error',
        };

        const toast = document.createElement('div');
        toast.className = 'argus-toast argus-toast--' + type;
        toast.setAttribute('role', type === 'error' ? 'alert' : 'status');

        const iconEl = document.createElement('div');
        iconEl.className = 'argus-toast__icon';
        iconEl.textContent = ICONS[type] || ICONS.info;

        const body = document.createElement('div');
        body.className = 'argus-toast__body';
        const title = opts.title !== undefined ? opts.title : TITLES[type];
        if (title) {
            const t = document.createElement('div');
            t.className = 'argus-toast__title';
            t.textContent = title;
            body.appendChild(t);
        }
        const msg = document.createElement('div');
        msg.className = 'argus-toast__message';
        msg.textContent = String(message || '');
        body.appendChild(msg);

        toast.appendChild(iconEl);
        toast.appendChild(body);

        if (opts.dismissible !== false) {
            const close = document.createElement('button');
            close.className = 'argus-toast__close';
            close.setAttribute('aria-label', 'Cerrar notificación');
            close.innerHTML = '&times;';
            close.addEventListener('click', () => _dismiss(toast));
            toast.appendChild(close);
        }

        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('is-visible'));

        const duration = (typeof opts.duration === 'number')
            ? opts.duration
            : (type === 'error' ? 6500 : 4500);
        if (duration > 0) {
            setTimeout(() => _dismiss(toast), duration);
        }

        return {
            dismiss: () => _dismiss(toast),
            element: toast,
        };
    }

    function _dismiss(toast) {
        if (!toast || !toast.isConnected) return;
        toast.classList.remove('is-visible');
        toast.classList.add('is-leaving');
        setTimeout(() => {
            if (toast && toast.isConnected) toast.remove();
        }, 240);
    }

    // ── alert() override ─────────────────────────────────────────────────────
    // Detecta el tipo automáticamente por el prefijo del mensaje.
    // Mantiene la firma original (un solo argumento string).
    const _origAlert = window.alert ? window.alert.bind(window) : null;

    function _detectType(text) {
        const s = String(text || '').trim();
        if (s.startsWith('✅') || s.startsWith('✓')) return 'success';
        if (s.startsWith('❌') || s.startsWith('✗')) return 'error';
        if (s.startsWith('⚠️') || s.startsWith('⚠'))  return 'warning';
        if (/^error[: ]/i.test(s) || /\berror\b/i.test(s.split('\n')[0])) {
            return 'error';
        }
        return 'info';
    }

    function _stripPrefix(text) {
        return String(text || '')
            .replace(/^[\s]*(?:✅|✓|❌|✗|⚠️|⚠)\s*/, '')
            .trim();
    }

    window.alert = function (message) {
        try {
            const type = _detectType(message);
            const cleaned = _stripPrefix(message);
            showToast(cleaned, type);
        } catch (err) {
            if (_origAlert) _origAlert(message);
            else console.warn('alert override failed:', err, message);
        }
    };

    // Conservamos el alert nativo accesible por si alguien lo necesita
    // explícitamente (modales realmente bloqueantes).
    window.argusNativeAlert = _origAlert;

    // ── Empty State ──────────────────────────────────────────────────────────

    /**
     * Renderiza un empty state ilustrado.
     *
     * @param {HTMLElement|string} target  Elemento o selector contenedor.
     * @param {object} config
     * @param {string} [config.icon]   uno de: 'box','search','shield','file',
     *                                 'clock','plug','folder','sparkles' o
     *                                 una cadena SVG inline.
     * @param {string} config.title    título.
     * @param {string} [config.desc]   descripción breve.
     * @param {object} [config.action] { label, onClick }.
     */
    function renderEmptyState(target, config) {
        const el = (typeof target === 'string') ? document.querySelector(target) : target;
        if (!el) return;
        config = config || {};

        const wrap = document.createElement('div');
        wrap.className = 'argus-empty';

        const art = document.createElement('div');
        art.className = 'argus-empty__art';
        art.innerHTML = _resolveIcon(config.icon || 'box');
        wrap.appendChild(art);

        if (config.title) {
            const h = document.createElement('div');
            h.className = 'argus-empty__title';
            h.textContent = config.title;
            wrap.appendChild(h);
        }
        if (config.desc) {
            const p = document.createElement('div');
            p.className = 'argus-empty__desc';
            p.textContent = config.desc;
            wrap.appendChild(p);
        }
        if (config.action && config.action.label) {
            const btn = document.createElement('button');
            btn.className = 'argus-empty__action';
            btn.type = 'button';
            btn.textContent = config.action.label;
            if (typeof config.action.onClick === 'function') {
                btn.addEventListener('click', config.action.onClick);
            } else if (typeof config.action.href === 'string') {
                btn.addEventListener('click', () => {
                    window.location.href = config.action.href;
                });
            }
            wrap.appendChild(btn);
        }

        el.innerHTML = '';
        el.appendChild(wrap);
    }

    const _ICONS = {
        // Inbox vacío — para "no hay scans"
        box: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M8 22h48l-4-12H12L8 22z"/><path d="M8 22v28a4 4 0 0 0 4 4h40a4 4 0 0 0 4-4V22"/><path d="M22 32h20"/></svg>',
        // Lupa — para "sin resultados de búsqueda"
        search: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><circle cx="28" cy="28" r="16"/><path d="M40 40l14 14"/></svg>',
        // Escudo — para "sin amenazas"
        shield: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M32 6l22 8v14c0 14-9 24-22 30C19 52 10 42 10 28V14L32 6z"/><path d="M22 32l7 7 14-14"/></svg>',
        // Archivo — para "sin documentos"
        file: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M14 6h26l12 12v40a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4V10a4 4 0 0 1 4-4z"/><path d="M40 6v12h12"/></svg>',
        // Reloj — para "sin actividad reciente"
        clock: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><circle cx="32" cy="32" r="24"/><path d="M32 18v14l10 6"/></svg>',
        // Plug desconectado — para "sin conexión"
        plug: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M22 6v12M42 6v12M14 24h36v8a16 16 0 0 1-16 16h-4A16 16 0 0 1 14 32v-8z"/><path d="M32 48v10"/></svg>',
        // Folder — para "sin tokens"
        folder: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M6 16a4 4 0 0 1 4-4h14l6 6h24a4 4 0 0 1 4 4v28a4 4 0 0 1-4 4H10a4 4 0 0 1-4-4V16z"/></svg>',
        // Sparkles — para estados positivos
        sparkles: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M32 6v12M32 46v12M6 32h12M46 32h12M14 14l8 8M42 42l8 8M50 14l-8 8M14 50l8-8"/></svg>',
        // Line chart — para "sin histórico"
        chart: '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="100%" height="100%"><path d="M8 52h48M12 44l10-12 10 8 12-18 10 12"/><circle cx="22" cy="32" r="2"/><circle cx="32" cy="40" r="2"/><circle cx="44" cy="22" r="2"/><circle cx="54" cy="34" r="2"/></svg>',
    };

    function _resolveIcon(spec) {
        if (typeof spec === 'string' && spec.trim().startsWith('<svg')) return spec;
        return _ICONS[spec] || _ICONS.box;
    }

    // ── Skeleton Loaders ─────────────────────────────────────────────────────

    /**
     * Renderiza N skeleton cards en target.
     *
     * @param {HTMLElement|string} target
     * @param {number} [count=3]
     * @param {object} [opts]
     * @param {boolean} [opts.avatar=false]  Mostrar avatar circular a la izq.
     */
    function renderSkeleton(target, count, opts) {
        const el = (typeof target === 'string') ? document.querySelector(target) : target;
        if (!el) return;
        count = (typeof count === 'number' && count > 0) ? count : 3;
        opts = opts || {};

        const cards = [];
        for (let i = 0; i < count; i++) {
            const c = document.createElement('div');
            c.className = 'argus-skel';
            const inner = opts.avatar
                ? `<div class="argus-skel__row">
                       <div class="argus-skel__avatar"></div>
                       <div style="flex:1;min-width:0;">
                           <div class="argus-skel__line argus-skel__line--md"></div>
                           <div class="argus-skel__line argus-skel__line--sm"></div>
                       </div>
                   </div>`
                : `<div class="argus-skel__line argus-skel__line--lg"></div>
                   <div class="argus-skel__line argus-skel__line--md"></div>
                   <div class="argus-skel__line argus-skel__line--sm"></div>`;
            c.innerHTML = inner;
            cards.push(c);
        }
        el.innerHTML = '';
        cards.forEach(c => el.appendChild(c));
    }

    // ── Footer con version + uptime (Visual #38) ─────────────────────────────

    async function _refreshFooter() {
        try {
            const r = await fetch('/api/version', { cache: 'no-store' });
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const d = await r.json();
            const vEl = document.getElementById('argus-footer-version');
            const uEl = document.getElementById('argus-footer-uptime');
            const dot = document.getElementById('argus-footer-dot');
            const txt = document.getElementById('argus-footer-status-text');
            if (vEl) vEl.textContent = `Argus v${d.version}`;
            if (uEl) uEl.textContent = `uptime ${d.uptime_human}`;
            if (dot && txt) {
                if (d.db_ok) {
                    dot.style.background = '#10b981';
                    dot.style.boxShadow  = '0 0 8px #10b981';
                    txt.textContent = 'online';
                } else {
                    dot.style.background = '#f59e0b';
                    dot.style.boxShadow  = '0 0 8px #f59e0b';
                    txt.textContent = 'DB lenta';
                }
            }
        } catch (_e) {
            const dot = document.getElementById('argus-footer-dot');
            const txt = document.getElementById('argus-footer-status-text');
            if (dot) {
                dot.style.background = '#ef4444';
                dot.style.boxShadow  = '0 0 8px #ef4444';
            }
            if (txt) txt.textContent = 'sin conexión';
        }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _refreshFooter);
    } else {
        _refreshFooter();
    }
    setInterval(_refreshFooter, 60000);

    // ── Tooltips contextuales (Visual #8) ────────────────────────────────────
    // Aplica a cualquier elemento con data-argus-tip="texto".
    // También se puede configurar  data-argus-tip-pos="top|bottom|left|right".
    // Si el elemento es un .argus-help (chip de ayuda dorado), también recibe
    // estilos especiales. La accesibilidad: aria-describedby se conecta al tip.

    let _tipEl = null;
    let _tipShowTimer = null;

    function _ensureTooltipNode() {
        if (_tipEl) return _tipEl;
        _tipEl = document.createElement('div');
        _tipEl.id = 'argus-tooltip';
        _tipEl.setAttribute('role', 'tooltip');
        _tipEl.setAttribute('aria-hidden', 'true');
        document.body.appendChild(_tipEl);
        return _tipEl;
    }

    function _positionTip(target, pos) {
        const tip = _ensureTooltipNode();
        const r = target.getBoundingClientRect();
        const tr = tip.getBoundingClientRect();
        const margin = 10;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        let top = 0, left = 0;
        let actualPos = pos || 'top';

        if (actualPos === 'top' && r.top - tr.height - margin < 4) actualPos = 'bottom';
        if (actualPos === 'bottom' && r.bottom + tr.height + margin > vh - 4) actualPos = 'top';

        switch (actualPos) {
            case 'bottom':
                top  = r.bottom + margin;
                left = r.left + (r.width - tr.width) / 2;
                break;
            case 'left':
                top  = r.top + (r.height - tr.height) / 2;
                left = r.left - tr.width - margin;
                break;
            case 'right':
                top  = r.top + (r.height - tr.height) / 2;
                left = r.right + margin;
                break;
            case 'top':
            default:
                top  = r.top - tr.height - margin;
                left = r.left + (r.width - tr.width) / 2;
                break;
        }
        // Clamp horizontal a viewport
        if (left < 6) left = 6;
        if (left + tr.width > vw - 6) left = vw - tr.width - 6;
        if (top  < 6) top  = 6;

        tip.style.top  = `${Math.round(top)}px`;
        tip.style.left = `${Math.round(left)}px`;
        tip.setAttribute('data-pos', actualPos);
    }

    function _showTip(target) {
        const text = target.getAttribute('data-argus-tip');
        if (!text) return;
        const pos = target.getAttribute('data-argus-tip-pos') || 'top';
        const tip = _ensureTooltipNode();
        tip.innerHTML = text; // permite <kbd>, <b>, <br>
        tip.setAttribute('aria-hidden', 'false');
        // primer paint para medir
        tip.style.opacity = '0';
        tip.classList.add('is-visible');
        // tras layout, posicionar
        requestAnimationFrame(() => {
            _positionTip(target, pos);
            tip.style.opacity = '';
        });
    }

    function _hideTip() {
        if (_tipShowTimer) { clearTimeout(_tipShowTimer); _tipShowTimer = null; }
        if (!_tipEl) return;
        _tipEl.classList.remove('is-visible');
        _tipEl.setAttribute('aria-hidden', 'true');
    }

    function _bindTip(el) {
        if (el.__argusTipBound) return;
        el.__argusTipBound = true;
        // Quitar title nativo si existe, para evitar tooltip duplicado del SO
        const nativeTitle = el.getAttribute('title');
        if (nativeTitle && !el.getAttribute('data-argus-tip')) {
            el.setAttribute('data-argus-tip', nativeTitle);
            el.removeAttribute('title');
        }
        el.addEventListener('mouseenter', () => {
            if (_tipShowTimer) clearTimeout(_tipShowTimer);
            _tipShowTimer = setTimeout(() => _showTip(el), 220);
        });
        el.addEventListener('mouseleave', _hideTip);
        el.addEventListener('focus', () => _showTip(el));
        el.addEventListener('blur',  _hideTip);
        // Cerrar al scrollear
        window.addEventListener('scroll', _hideTip, { passive: true, once: true });
    }

    function _initTooltips() {
        document.querySelectorAll('[data-argus-tip]').forEach(_bindTip);
        // MutationObserver para enganchar tips de elementos nuevos
        try {
            const obs = new MutationObserver(muts => {
                for (const m of muts) {
                    for (const node of m.addedNodes) {
                        if (node.nodeType !== 1) continue;
                        if (node.matches && node.matches('[data-argus-tip]')) _bindTip(node);
                        if (node.querySelectorAll) {
                            node.querySelectorAll('[data-argus-tip]').forEach(_bindTip);
                        }
                    }
                }
            });
            obs.observe(document.body, { childList: true, subtree: true });
        } catch (_e) { /* no soportado, da igual */ }
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initTooltips);
    } else {
        _initTooltips();
    }

    // ── Esc global cierra cualquier .modal.active (Visual #53) ───────────────
    // El proyecto usa la convención `.modal.active` para abrir modales (CSS:
    // .modal { display:none } / .modal.active { display:flex }). Esc cierra
    // el último modal activo (LIFO) sin tocar tooltips, toasts o quicksearch
    // (esos tienen su propio handler).
    document.addEventListener('keydown', (e) => {
        if ((e.key || '').toLowerCase() !== 'escape') return;
        // No cerrar si el quicksearch está abierto — su handler ya se encarga.
        const qs = document.getElementById('argus-quicksearch');
        if (qs && qs.style.display === 'flex') return;
        // No cerrar si el lightbox de screenshot está abierto.
        if (document.getElementById('argus-screenshot-lightbox')) return;
        const actives = Array.from(document.querySelectorAll('.modal.active'));
        if (!actives.length) return;
        const top = actives[actives.length - 1];
        top.classList.remove('active');
    });
    // Click sobre el backdrop (la zona oscura del .modal pero no el contenido)
    // también cierra. Algunos modales ya lo hacen, pero esto generaliza.
    document.addEventListener('click', (e) => {
        const t = e.target;
        if (!(t instanceof HTMLElement)) return;
        if (!t.classList.contains('modal') || !t.classList.contains('active')) return;
        // Solo si el click fue sobre el backdrop, no sobre .modal-content
        t.classList.remove('active');
    });

    // ── Quick search global Cmd+K / Ctrl+K (Visual #17) ──────────────────────
    // Visual #18 — Command palette: el quicksearch ahora también acepta
    // "comandos" prefijados con `>` o `/`, o que coincidan con el title del
    // comando. Cada comando es una entry navegable con el mismo UX que un scan.
    const QS_DEBOUNCE_MS = 220;
    let _qsDebounce  = null;
    let _qsItems     = [];     // mix de {kind:'scan',...} y {kind:'cmd',...}
    let _qsActiveIdx = 0;
    let _qsAbort     = null;

    // Catálogo de comandos. Cada uno: { id, title, hint, run: () => void }.
    // Algunos comandos son condicionales según permisos — usamos `enabled()`.
    const _qsCommandCatalog = [
        {
            id: 'goto-scans',
            title: 'Ir a Scans',
            hint:  'Lista de escaneos recientes',
            keys:  ['scans', 'historial', 'lista'],
            run:   () => { window.location.hash = '#scans-section'; window.scrollTo({ top: 0, behavior: 'smooth' }); },
        },
        {
            id: 'goto-tokens',
            title: 'Ir a Tokens',
            hint:  'Generar / revocar tokens del scanner',
            keys:  ['tokens', 'token', 'generar token', 'revocar'],
            run:   () => { window.location.hash = '#tokens-section'; },
        },
        {
            id: 'goto-users',
            title: 'Ir a Usuarios',
            hint:  'Gestionar staff / clientes Pro',
            keys:  ['users', 'usuarios', 'staff'],
            run:   () => { window.location.hash = '#users-section'; },
        },
        {
            id: 'theme-toggle',
            title: 'Cambiar tema (claro/oscuro)',
            hint:  'Alterna entre dark bronze y light bronze',
            keys:  ['theme', 'tema', 'oscuro', 'claro', 'dark', 'light', 'modo'],
            run:   () => { if (typeof window.toggleTheme === 'function') window.toggleTheme(); },
        },
        {
            id: 'stream-mode',
            title: 'Modo Stream-friendly',
            hint:  'Blur en nombres / IP / UUIDs (anti-doxing)',
            keys:  ['stream', 'streamer', 'blur', 'privacidad', 'twitch', 'ocultar'],
            run:   () => setStreamFriendly(!_isStreamFriendly()),
        },
        {
            id: 'sound-toggle',
            title: 'Sonido al recibir scan',
            hint:  'Habilitar / silenciar notificación de scan nuevo',
            keys:  ['sonido', 'sound', 'audio', 'ding', 'silencio', 'mute'],
            run:   () => setSoundEnabled(!_isSoundEnabled()),
        },
        {
            id: 'density-cozy',
            title: 'Densidad cómoda',
            hint:  'Más espacio entre filas',
            keys:  ['density', 'densidad', 'cozy', 'comoda', 'cómoda', 'espacio'],
            run:   () => setDensity('cozy'),
        },
        {
            id: 'density-compact',
            title: 'Densidad compacta',
            hint:  'Más información visible por pantalla',
            keys:  ['density', 'densidad', 'compact', 'compacta', 'denso'],
            run:   () => setDensity('compact'),
        },
        {
            id: 'fontsize-bigger',
            title: 'Aumentar tamaño de letra',
            hint:  'Sube un nivel (A → A+ → A++)',
            keys:  ['font', 'tamaño', 'letra', 'zoom', 'grande', 'a+'],
            run:   () => {
                const order = ['xs','sm','normal','lg','xl'];
                const cur = _getFontSize();
                const next = order[Math.min(order.length - 1, order.indexOf(cur) + 1)];
                setFontSize(next);
            },
        },
        {
            id: 'logout',
            title: 'Cerrar sesión',
            hint:  'Termina la sesión actual',
            keys:  ['logout', 'salir', 'cerrar', 'desconectar', 'sign out'],
            run:   () => { window.location.href = '/logout'; },
        },
        {
            id: 'help-shortcuts',
            title: 'Ver atajos de teclado',
            hint:  'Cmd/Ctrl+K · Esc · ↑↓ Enter',
            keys:  ['help', 'ayuda', 'atajos', 'shortcuts', 'keyboard', 'teclado'],
            run:   () => {
                showToast(
                    'Atajos: Ctrl+K abre búsqueda · ↑/↓ navegan · Enter abre · Esc cierra · `>` filtra solo comandos',
                    'info', { duration: 6500 }
                );
            },
        },
    ];

    function _qsMatchCommands(q) {
        const stripped = q.replace(/^[>\/\s]+/, '').toLowerCase().trim();
        if (!stripped) {
            // Sin texto pero con prefijo: mostrar todos
            return _qsCommandCatalog.map(c => ({ ...c, _score: 0 }));
        }
        const tokens = stripped.split(/\s+/).filter(Boolean);
        const out = [];
        for (const cmd of _qsCommandCatalog) {
            let score = 0;
            const haystack = (cmd.title + ' ' + (cmd.hint || '') + ' ' + (cmd.keys || []).join(' ')).toLowerCase();
            for (const t of tokens) {
                if (haystack.includes(t)) score += t.length >= 4 ? 3 : 1;
                if (cmd.title.toLowerCase().startsWith(t)) score += 2;
            }
            if (score > 0) out.push({ ...cmd, _score: score });
        }
        out.sort((a, b) => b._score - a._score);
        return out;
    }

    function _qsOpen() {
        const root = document.getElementById('argus-quicksearch');
        if (!root) return;
        root.style.display = 'flex';
        const input = document.getElementById('argus-quicksearch-input');
        if (input) {
            input.value = '';
            setTimeout(() => input.focus(), 30);
        }
        _qsItems = [];
        _qsActiveIdx = 0;
        _qsRender('');
    }
    function _qsClose() {
        const root = document.getElementById('argus-quicksearch');
        if (!root) return;
        root.style.display = 'none';
        if (_qsAbort) { try { _qsAbort.abort(); } catch(_){} _qsAbort = null; }
    }
    function _qsRender(query) {
        const box = document.getElementById('argus-quicksearch-results');
        if (!box) return;
        if (!query) {
            box.innerHTML = '<div style="padding:24px;text-align:center;color:rgba(241,230,211,0.5);font-size:13px;">' +
                'Empieza a escribir para buscar…<br>' +
                '<span style="font-size:11px;opacity:0.7;">Tip: número = abrir scan · prefijo <code style="background:rgba(184,115,51,0.18);padding:1px 5px;border-radius:3px;">&gt;</code> = solo comandos · Cmd/Ctrl+K abre/cierra.</span>' +
                '</div>';
            return;
        }
        if (!_qsItems.length) {
            box.innerHTML = '<div style="padding:18px;text-align:center;color:rgba(241,230,211,0.55);font-size:13px;">' +
                'Sin resultados para <b>' + _qsEscape(query) + '</b><br>' +
                '<span style="font-size:11px;opacity:0.7;">Probá empezar con <code>&gt;</code> para ver comandos disponibles.</span>' +
                '</div>';
            return;
        }
        const html = _qsItems.map((it, i) => {
            const active = (i === _qsActiveIdx);
            const baseStyle = 'display:flex;align-items:center;gap:10px;padding:9px 16px;cursor:pointer;' +
                'border-left:3px solid ' + (active ? 'rgba(212,145,90,0.95)' : 'transparent') + ';' +
                'background:' + (active ? 'rgba(184,115,51,0.10)' : 'transparent') + ';';

            // Visual #18 — render diferente para comandos
            if (it.kind === 'cmd') {
                return '<div class="argus-qs-item" data-kind="cmd" data-cmd-id="' + _qsEscape(it.id) + '" data-idx="' + i + '"' +
                       ' style="' + baseStyle + '">' +
                           '<span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:6px;' +
                                'background:rgba(184,115,51,0.18);color:#fbbf24;font-size:13px;font-weight:700;flex-shrink:0;">›_</span>' +
                           '<div style="flex:1;min-width:0;">' +
                               '<div style="font-size:13px;font-weight:600;color:#f1e6d3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                                   _qsEscape(String(it.title)) +
                               '</div>' +
                               '<div style="font-size:11px;color:rgba(241,230,211,0.55);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                                   _qsEscape(String(it.hint || 'Comando')) +
                               '</div>' +
                           '</div>' +
                           '<span style="font-size:9.5px;font-weight:700;color:#fbbf24;letter-spacing:0.4px;' +
                                'background:rgba(245,158,11,0.10);padding:2px 7px;border-radius:10px;border:1px solid rgba(245,158,11,0.28);' +
                                'text-transform:uppercase;">CMD</span>' +
                       '</div>';
            }

            // Default: scan
            const s = it;
            const risk = s.risk_score == null ? '—' : s.risk_score;
            const riskColor = risk >= 70 ? '#ef4444' : risk >= 30 ? '#f59e0b' : '#10b981';
            const player    = s.minecraft_user || s.user || s.usuario || 'Sin jugador';
            const company   = s.empresa_name || s.company || s.empresa || '';
            const created   = s.created_at ? new Date(s.created_at).toLocaleString() : '';
            return '<div class="argus-qs-item" data-kind="scan" data-id="' + s.id + '" data-idx="' + i + '"' +
                   ' style="' + baseStyle + '">' +
                       '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + riskColor + ';' +
                            'box-shadow:0 0 6px ' + riskColor + ';flex-shrink:0;"></span>' +
                       '<div style="flex:1;min-width:0;">' +
                           '<div style="font-size:13px;font-weight:600;color:#f1e6d3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                               '#' + s.id + ' &middot; ' + _qsEscape(String(player)) +
                           '</div>' +
                           '<div style="font-size:11px;color:rgba(241,230,211,0.55);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
                               (company ? _qsEscape(String(company)) + ' &middot; ' : '') + created +
                           '</div>' +
                       '</div>' +
                       '<span style="font-size:11px;font-weight:700;color:' + riskColor + ';' +
                            'background:rgba(255,255,255,0.04);padding:2px 8px;border-radius:10px;">' + risk + '</span>' +
                   '</div>';
        }).join('');
        box.innerHTML = html;
        box.querySelectorAll('.argus-qs-item').forEach(el => {
            el.addEventListener('click', () => _qsActivateItem(parseInt(el.dataset.idx, 10)));
            el.addEventListener('mouseenter', () => {
                _qsActiveIdx = parseInt(el.dataset.idx, 10);
                _qsRender(document.getElementById('argus-quicksearch-input').value);
            });
        });
    }

    function _qsActivateItem(idx) {
        const it = _qsItems[idx];
        if (!it) return;
        if (it.kind === 'cmd') {
            _qsClose();
            try { it.run(); }
            catch (e) {
                if (typeof showToast === 'function')
                    showToast('Error ejecutando comando: ' + (e?.message || e), 'error');
            }
            return;
        }
        _qsOpenScan(parseInt(it.id, 10));
    }
    function _qsEscape(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;',
        })[c]);
    }
    function _qsOpenScan(id) {
        _qsClose();
        if (typeof window.viewScanDetails === 'function') {
            window.viewScanDetails(id);
        } else {
            window.location.href = '/staff?scan=' + id;
        }
    }
    async function _qsFetch(query) {
        if (_qsAbort) { try { _qsAbort.abort(); } catch(_){} }
        _qsAbort = (typeof AbortController === 'function') ? new AbortController() : null;

        // Visual #18 — modo "solo comandos" cuando empieza con `>` o `/`.
        if (/^[>\/]/.test(query)) {
            _qsItems = _qsMatchCommands(query).map(c => ({ ...c, kind: 'cmd' }));
            _qsActiveIdx = 0;
            _qsRender(query);
            return;
        }

        // Caso numérico puro: solo scans, sin mezcla de comandos
        const isNumeric = /^\d+$/.test(query);

        // Comandos relevantes según la query (siempre arriba, máx 3)
        const cmdMatches = isNumeric ? [] : _qsMatchCommands(query).slice(0, 3).map(c => ({ ...c, kind: 'cmd' }));

        try {
            const url = '/api/scans?limit=40&q=' + encodeURIComponent(query);
            const r = await fetch(url, _qsAbort ? { signal: _qsAbort.signal } : {});
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const d = await r.json();
            let items = (d && d.scans) ? d.scans : (Array.isArray(d) ? d : []);
            if (isNumeric) {
                const idQ = parseInt(query, 10);
                const exact = items.find(s => s.id === idQ);
                if (!exact) {
                    items = [{ id: idQ, minecraft_user: '(abrir scan #' + idQ + ')', risk_score: null }, ...items];
                }
            } else {
                const ql = query.toLowerCase();
                items = items.filter(s => {
                    const haystack = [
                        s.id, s.minecraft_user, s.user, s.usuario,
                        s.empresa_name, s.company, s.empresa,
                    ].filter(Boolean).join(' ').toLowerCase();
                    return haystack.includes(ql);
                });
            }
            const scanItems = items.slice(0, 25 - cmdMatches.length).map(s => ({ ...s, kind: 'scan' }));
            _qsItems = [...cmdMatches, ...scanItems];
            _qsActiveIdx = 0;
            _qsRender(query);
        } catch (e) {
            if (e && e.name === 'AbortError') return;
            // Si falla la fetch pero hay comandos, igual mostramos los comandos
            _qsItems = cmdMatches;
            _qsActiveIdx = 0;
            _qsRender(query);
        }
    }
    function _initQuickSearch() {
        const input = document.getElementById('argus-quicksearch-input');
        const root  = document.getElementById('argus-quicksearch');
        if (!input || !root) return;
        // Atajos globales: Ctrl/Cmd + K abre, Esc cierra (también click fuera)
        document.addEventListener('keydown', (e) => {
            const key = (e.key || '').toLowerCase();
            if ((e.ctrlKey || e.metaKey) && key === 'k') {
                e.preventDefault();
                if (root.style.display === 'flex') _qsClose(); else _qsOpen();
                return;
            }
            if (root.style.display !== 'flex') return;
            if (key === 'escape') { e.preventDefault(); _qsClose(); }
            else if (key === 'arrowdown') {
                e.preventDefault();
                if (_qsItems.length) {
                    _qsActiveIdx = (_qsActiveIdx + 1) % _qsItems.length;
                    _qsRender(input.value);
                }
            } else if (key === 'arrowup') {
                e.preventDefault();
                if (_qsItems.length) {
                    _qsActiveIdx = (_qsActiveIdx - 1 + _qsItems.length) % _qsItems.length;
                    _qsRender(input.value);
                }
            } else if (key === 'enter') {
                e.preventDefault();
                // Visual #18 — usa el activador unificado que sabe distinguir
                // scans de comandos del catálogo.
                if (_qsItems.length) _qsActivateItem(_qsActiveIdx);
            }
        });
        root.addEventListener('click', (e) => {
            if (e.target === root) _qsClose();
        });
        input.addEventListener('input', () => {
            const q = input.value.trim();
            if (_qsDebounce) clearTimeout(_qsDebounce);
            if (!q) {
                // Sin texto: si no hay nada, mostrar hint; pero si el usuario
                // escribió solo `>` o `/`, mostrar el catálogo entero.
                _qsItems = [];
                _qsRender('');
                return;
            }
            // Comandos puros (`>...`) son sincrónicos — sin debounce.
            if (/^[>\/]/.test(q)) {
                _qsFetch(q);
                return;
            }
            _qsDebounce = setTimeout(() => _qsFetch(q), QS_DEBOUNCE_MS);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initQuickSearch);
    } else {
        _initQuickSearch();
    }

    // ── Sticky-header drop shadow al scrollear (Visual #15) ──────────────────
    function _initStickyHeaderShadow() {
        const header = document.querySelector('.panel-header');
        if (!header) return;
        let ticking = false;
        const SCROLL_THRESHOLD = 6; // px desde el top
        function update() {
            const y = window.scrollY || document.documentElement.scrollTop || 0;
            const should = y > SCROLL_THRESHOLD;
            if (should !== header.classList.contains('scrolled')) {
                header.classList.toggle('scrolled', should);
            }
            ticking = false;
        }
        function onScroll() {
            if (!ticking) {
                window.requestAnimationFrame(update);
                ticking = true;
            }
        }
        window.addEventListener('scroll', onScroll, { passive: true });
        // Inicial — por si la página carga ya scrolleada
        update();
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initStickyHeaderShadow);
    } else {
        _initStickyHeaderShadow();
    }

    // ── Modo Stream-friendly (Visual #22) ────────────────────────────────────
    // Toggleable via argusUI.setStreamFriendly(true|false). Persiste en LS.
    // Aplica html.argus-stream-friendly y el CSS hace el blur en columnas
    // de machine_name/IP/UUID. Hover quita el blur localmente.
    const SF_KEY = 'argus_stream_friendly';
    function _isStreamFriendly() {
        try { return localStorage.getItem(SF_KEY) === '1'; }
        catch (_e) { return false; }
    }
    function _applyStreamFriendly(b) {
        document.documentElement.classList.toggle('argus-stream-friendly', !!b);
        try { localStorage.setItem(SF_KEY, b ? '1' : '0'); } catch (_e) {}
    }
    function setStreamFriendly(b) {
        _applyStreamFriendly(!!b);
        if (typeof window.showToast === 'function') {
            window.showToast(
                b ? '🎥 Modo stream activado: nombres de jugadores con blur (hover para ver)'
                  : '👁 Modo stream desactivado',
                b ? 'success' : 'info',
                { duration: 2400 }
            );
        }
    }
    _applyStreamFriendly(_isStreamFriendly());


    // ── Tag color determinístico por empresa (Visual #41) ────────────────────
    // Hash de empresa → color HSL estable (mismo company siempre = mismo color).
    // argusUI.companyTag(name) devuelve un <span> listo para insertar.
    // argusUI.companyColor(name) devuelve {hue, color, bg, border}.
    function _hashStrToHue(s) {
        if (!s) return 0;
        let h = 0;
        const str = String(s);
        for (let i = 0; i < str.length; i++) {
            h = (h * 31 + str.charCodeAt(i)) | 0;
        }
        return Math.abs(h) % 360;
    }
    function companyColor(name) {
        const hue = _hashStrToHue(name || 'unknown');
        // Saturación y luminosidad templadas para que no salten naranjas chillones
        return {
            hue:    hue,
            color:  'hsl(' + hue + ', 70%, 70%)',
            bg:     'hsl(' + hue + ', 65%, 18%)',
            border: 'hsl(' + hue + ', 65%, 45%)',
        };
    }
    function companyTag(name) {
        const safeName = (name == null || name === '') ? 'Sin empresa' : String(name);
        const c = companyColor(safeName);
        const span = document.createElement('span');
        span.className = 'argus-company-tag';
        span.style.color = c.color;
        span.title = 'Empresa: ' + safeName;
        span.textContent = safeName;
        return span;
    }


    // ── Sonido sutil al recibir scan nuevo (Visual #44) ──────────────────────
    // No requiere assets: genera un "ding" suave con WebAudio API.
    // Toggleable via argusUI.setSoundEnabled(true|false) y persiste en LS.
    // Volumen sutil (~0.10), 2 notas (E5 -> A5) en 220ms para no irritar.
    const SND_KEY = 'argus_sound_enabled';
    function _isSoundEnabled() {
        try { return localStorage.getItem(SND_KEY) === '1'; }
        catch (_e) { return false; }
    }
    function setSoundEnabled(b) {
        try { localStorage.setItem(SND_KEY, b ? '1' : '0'); } catch (_e) {}
        if (b && typeof window.showToast === 'function') {
            window.showToast('🔔 Sonido activado para scans nuevos', 'success', { duration: 2200 });
            // Probar inmediatamente para que el usuario sepa cómo suena
            setTimeout(() => playScanDing(), 150);
        }
    }
    let _audioCtx = null;
    function _getAudioCtx() {
        if (_audioCtx) return _audioCtx;
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (!Ctx) return null;
            _audioCtx = new Ctx();
        } catch (_e) { _audioCtx = null; }
        return _audioCtx;
    }
    function playScanDing(force) {
        if (!force && !_isSoundEnabled()) return;
        const ctx = _getAudioCtx();
        if (!ctx) return;
        // Si el contexto está suspendido (autoplay policy), intentar reanudar
        if (ctx.state === 'suspended') {
            try { ctx.resume(); } catch (_e) {}
        }
        const now = ctx.currentTime;
        function note(freq, start, dur, peak) {
            const osc  = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, now + start);
            gain.gain.setValueAtTime(0, now + start);
            gain.gain.linearTargetAtTime ? null : null;  // no-op, broaden compat
            gain.gain.linearRampToValueAtTime(peak,    now + start + 0.012);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + start + dur);
            osc.connect(gain).connect(ctx.destination);
            osc.start(now + start);
            osc.stop(now + start + dur + 0.02);
        }
        note(659.25, 0.000, 0.18, 0.10);  // E5
        note(880.00, 0.080, 0.22, 0.08);  // A5
    }


    // ── Font-size base configurable (Visual #52) ─────────────────────────────
    // Aplica clase argus-fontsize-{small|normal|large|xlarge} a <html>.
    // El CSS usa `zoom` (Chrome/Edge/Safari). Firefox cae en fallback JS.
    const FS_KEY = 'argus_fontsize';
    const FS_VALID = ['small', 'normal', 'large', 'xlarge'];
    const FS_FALLBACK = { small: 0.92, normal: 1, large: 1.12, xlarge: 1.24 };
    function _supportsZoom() {
        try {
            const t = document.createElement('div');
            t.style.zoom = '1.5';
            return t.style.zoom === '1.5' || t.style.zoom !== '';
        } catch (_e) { return false; }
    }
    const _hasZoom = _supportsZoom();
    function _applyFontSize(s) {
        if (!FS_VALID.includes(s)) s = 'normal';
        const html = document.documentElement;
        FS_VALID.forEach(v => html.classList.remove('argus-fontsize-' + v));
        html.classList.add('argus-fontsize-' + s);
        if (!_hasZoom && document.body) {
            const f = FS_FALLBACK[s] || 1;
            document.body.style.transformOrigin = 'top left';
            if (Math.abs(f - 1) < 0.01) {
                document.body.style.transform = '';
                document.body.style.width    = '';
            } else {
                document.body.style.transform = 'scale(' + f + ')';
                document.body.style.width = (100 / f) + '%';
            }
        }
        try { localStorage.setItem(FS_KEY, s); } catch (_e) {}
    }
    function _getFontSize() {
        try { return localStorage.getItem(FS_KEY) || 'normal'; }
        catch (_e) { return 'normal'; }
    }
    function setFontSize(s) { _applyFontSize(s); }
    _applyFontSize(_getFontSize());


    // ── Densidad ajustable (Visual #33) ──────────────────────────────────────
    // Aplica clase argus-density-{cozy|normal|compact} a <html>. Persiste
    // la preferencia en localStorage('argus_density').
    const DENSITY_KEY = 'argus_density';
    const DENSITY_VALID = ['cozy', 'normal', 'compact'];
    function _applyDensity(d) {
        if (!DENSITY_VALID.includes(d)) d = 'normal';
        const html = document.documentElement;
        DENSITY_VALID.forEach(v => html.classList.remove('argus-density-' + v));
        html.classList.add('argus-density-' + d);
        try { localStorage.setItem(DENSITY_KEY, d); } catch (_e) {}
    }
    function _getDensity() {
        try { return localStorage.getItem(DENSITY_KEY) || 'normal'; }
        catch (_e) { return 'normal'; }
    }
    function setDensity(d) { _applyDensity(d); }
    // Aplicar al cargar (early — antes incluso del DOMContentLoaded)
    _applyDensity(_getDensity());

    // ── Toggle vista cards/lista/tabla en historial (Visual #32) ─────────────
    const VIEW_KEY = 'argus_scans_view';
    const VIEW_VALID = ['cards', 'list', 'table'];
    function _applyScansView(v) {
        if (!VIEW_VALID.includes(v)) v = 'cards';
        const sec = document.getElementById('scans-section') ||
                    document.getElementById('historial') ||
                    document.querySelector('[data-scans-container]');
        if (!sec) return;
        VIEW_VALID.forEach(x => sec.classList.remove('scans-view-' + x));
        sec.classList.add('scans-view-' + v);
        // Update toggle UI si existe
        document.querySelectorAll('.scans-view-toggle button').forEach(btn => {
            btn.classList.toggle('is-active', btn.dataset.view === v);
        });
        try { localStorage.setItem(VIEW_KEY, v); } catch (_e) {}
    }
    function _getScansView() {
        try { return localStorage.getItem(VIEW_KEY) || 'cards'; }
        catch (_e) { return 'cards'; }
    }
    function setScansView(v) { _applyScansView(v); }

    // ── Toast si un scan tarda demasiado (Visual #43) ────────────────────────
    // Mantiene un mapa { scanId: epoch_ms } de "running scans" reportados
    // por panel.js (window.argusUI.markScanRunning(id, started)). Cada 30s
    // chequea si alguno supera el umbral (4 min). Si sí, muestra UN toast
    // por scan (no spam) y olvida el id.
    const _slowThresholdMs = 240 * 1000;
    const _slowSeen = new Set();
    const _runningScans = new Map();
    function markScanRunning(id, startedTs) {
        if (typeof id === 'undefined' || id === null) return;
        const t = (startedTs && Number(startedTs)) || Date.now();
        _runningScans.set(String(id), t);
    }
    function markScanFinished(id) {
        const k = String(id);
        _runningScans.delete(k);
        _slowSeen.delete(k);
    }
    function _slowScansTick() {
        const now = Date.now();
        for (const [id, started] of _runningScans.entries()) {
            if (_slowSeen.has(id)) continue;
            if (now - started > _slowThresholdMs) {
                _slowSeen.add(id);
                if (typeof window.showToast === 'function') {
                    const mins = Math.round((now - started) / 60000);
                    window.showToast(
                        `⚠️ El scan #${id} lleva ${mins} min ejecutándose. ` +
                        `Si no termina en breve, podría haberse colgado en el cliente.`,
                        'warning',
                        { duration: 9000 }
                    );
                }
            }
        }
    }
    setInterval(_slowScansTick, 30 * 1000);

    // ── Visual #4 — Staggered fade-in helper ─────────────────────────────────
    // Aplica argusStaggerIn keyframe con delay incremental por hijo directo.
    // Uso: argusUI.staggerIn(containerEl, { selector: '> *', step: 40, max: 28 }).
    // Respeta prefers-reduced-motion (queda como simple fadeIn instantáneo).
    function staggerIn(container, opts) {
        if (!container) return;
        const o = opts || {};
        const sel  = o.selector || ':scope > *';
        const step = o.step || 40;          // ms entre cada hijo
        const max  = o.max  || 28;          // tope: a partir de aquí, todos juntos
        let nodes;
        try { nodes = container.querySelectorAll(sel); }
        catch (_e) { return; }
        const reduce = window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        nodes.forEach((el, i) => {
            const idx = Math.min(i, max);
            el.style.setProperty('--argus-stagger-idx', idx);
            el.style.setProperty('--argus-stagger-delay', (idx * step) + 'ms');
            el.classList.add('argus-stagger-item');
            if (reduce) {
                el.style.animationDuration = '0.001ms';
                el.style.animationDelay = '0ms';
            }
        });
        container.classList.add('argus-stagger-in');
    }


    // ── Visual #26 — Confeti sutil al confirmar veredicto CLEAN ──────────────
    // Implementación canvas vanilla, sin libs externas. ~80 partículas que
    // caen con gravedad y rotación durante ~1.6s. Auto-removible. Honra
    // prefers-reduced-motion (no-op si está activo). Colores configurables.
    function celebrate(opts) {
        const reduce = window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduce) return;
        const o = opts || {};
        const palette = o.palette || ['#10b981', '#34d399', '#6ee7b7', '#B87333', '#fbbf24', '#FFFFFF'];
        const count   = Math.max(30, Math.min(180, o.count || 90));
        const duration = Math.max(700, Math.min(3500, o.duration || 1800));
        const originX = (o.originX != null ? o.originX : 0.5) * window.innerWidth;
        const originY = (o.originY != null ? o.originY : 0.18) * window.innerHeight;

        const canvas = document.createElement('canvas');
        canvas.style.cssText = 'position:fixed;inset:0;z-index:99998;pointer-events:none;';
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
        document.body.appendChild(canvas);
        const ctx = canvas.getContext('2d');
        if (!ctx) { canvas.remove(); return; }

        const parts = [];
        for (let i = 0; i < count; i++) {
            const angle = (-Math.PI / 2) + (Math.random() - 0.5) * (Math.PI * 0.6);
            const speed = 6 + Math.random() * 7;
            parts.push({
                x: originX + (Math.random() - 0.5) * 24,
                y: originY,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                size: 5 + Math.random() * 6,
                color: palette[(Math.random() * palette.length) | 0],
                rot: Math.random() * Math.PI * 2,
                vrot: (Math.random() - 0.5) * 0.3,
                shape: Math.random() < 0.6 ? 'rect' : 'circ',
            });
        }
        const tStart = performance.now();
        function frame(now) {
            const elapsed = now - tStart;
            if (elapsed > duration) {
                canvas.remove();
                return;
            }
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const fadeAlpha = elapsed > duration * 0.7
                ? 1 - ((elapsed - duration * 0.7) / (duration * 0.3))
                : 1;
            for (const p of parts) {
                p.vy += 0.22;             // gravedad
                p.vx *= 0.995;
                p.x  += p.vx;
                p.y  += p.vy;
                p.rot += p.vrot;
                ctx.save();
                ctx.globalAlpha = Math.max(0, fadeAlpha);
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                ctx.fillStyle = p.color;
                if (p.shape === 'rect') {
                    ctx.fillRect(-p.size / 2, -p.size / 3, p.size, p.size / 1.5);
                } else {
                    ctx.beginPath();
                    ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();
            }
            requestAnimationFrame(frame);
        }
        requestAnimationFrame(frame);
    }


    // ── Visual #34 — Keyboard navigation en chip-tabs ────────────────────────
    // Cualquier contenedor con class "argus-chip-tabs" gana navegación por
    // teclado: ←/→ mueven el foco entre tabs, Home/End van al primero/último,
    // Enter/Space activan la tab focalizada (delegado a click()). Patrón
    // ARIA standard: solo el tab activo tiene tabindex=0; el resto -1, así
    // Tab del browser entra y sale del tablist completo.
    document.addEventListener('keydown', function (e) {
        const t = e.target;
        if (!(t instanceof HTMLElement)) return;
        const tab = t.classList && t.classList.contains('argus-chip-tab') ? t
                  : (t.classList && t.classList.contains('equipo-tab') ? t : null);
        if (!tab) return;
        const list = tab.closest('.argus-chip-tabs');
        if (!list) return;
        const items = Array.from(list.querySelectorAll('.argus-chip-tab, .equipo-tab'))
            .filter(el => !el.disabled);
        if (!items.length) return;
        const idx = items.indexOf(tab);
        let next = -1;
        const k = (e.key || '').toLowerCase();
        if (k === 'arrowright' || k === 'arrowdown') next = (idx + 1) % items.length;
        else if (k === 'arrowleft' || k === 'arrowup') next = (idx - 1 + items.length) % items.length;
        else if (k === 'home') next = 0;
        else if (k === 'end')  next = items.length - 1;
        else if (k === 'enter' || k === ' ') {
            e.preventDefault();
            tab.click();
            return;
        }
        if (next >= 0) {
            e.preventDefault();
            // Solo reasignamos foco; la activación ocurre con Enter (no con
            // las flechas) para no disparar fetches involuntarios.
            items.forEach((el, i) => { el.setAttribute('tabindex', i === next ? '0' : '-1'); });
            items[next].focus();
        }
    });


    // ── Visual #22 — Loading states más informativos ─────────────────────────
    // argusUI.renderLoading(target, {title, sub, size}) renderiza un bloque
    // <div.argus-loading> con anillo bronce giratorio + título + subtitulo.
    // Reemplaza el clásico textContent='Cargando…' por feedback con contexto
    // (qué se está cargando) y una sugerencia opcional.
    function renderLoading(target, opts) {
        const el = (typeof target === 'string') ? document.querySelector(target) : target;
        if (!el) return;
        const o = opts || {};
        const sizeClass = o.size === 'sm' ? ' sm' : (o.size === 'lg' ? ' lg' : '');
        const title = o.title || 'Cargando…';
        const sub   = o.sub || '';
        el.innerHTML =
            '<div class="argus-loading">' +
                '<div class="argus-spinner-ring' + sizeClass + '" role="progressbar" aria-label="Cargando"></div>' +
                '<div class="argus-loading-title">' + String(title).replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</div>' +
                (sub ? '<div class="argus-loading-sub">' + String(sub).replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</div>' : '') +
            '</div>';
    }


    // ── Visual #7 — Modal de confirmación unificado ──────────────────────────
    // Reemplaza el confirm() del browser (que en Chrome muestra el ugly diálogo
    // nativo y bloquea TODO el thread). API: argusUI.confirm({title, body, ok,
    // cancel, danger}) → Promise<boolean>. backdrop blur, animaciones consistentes,
    // foco autoseteado en el botón cancel para evitar acciones destructivas
    // accidentales con Enter. Esc / click fuera = cancelar.
    function confirmModal(opts) {
        const o = opts || {};
        const title  = o.title  || '¿Confirmar acción?';
        const body   = o.body   || '';
        const okLabel     = o.ok     || 'Confirmar';
        const cancelLabel = o.cancel || 'Cancelar';
        const danger = !!o.danger;
        const okBg     = danger ? 'linear-gradient(135deg,#dc2626,#b91c1c)' : 'linear-gradient(135deg,var(--accent,#B87333),var(--accent-d,#7A4824))';
        const okShadow = danger ? 'rgba(220,38,38,0.40)' : 'rgba(184,115,51,0.40)';

        // Si ya hay uno abierto, lo cerramos primero
        document.getElementById('argus-confirm-modal')?.remove();

        return new Promise((resolve) => {
            const root = document.createElement('div');
            root.id = 'argus-confirm-modal';
            root.style.cssText = [
                'position:fixed',
                'inset:0',
                'z-index:99996',
                'display:flex',
                'align-items:center',
                'justify-content:center',
                'padding:24px',
                'background:rgba(8,6,4,0.62)',
                'backdrop-filter:blur(10px)',
                '-webkit-backdrop-filter:blur(10px)',
                'animation:argusConfirmFadeIn 180ms cubic-bezier(0.22,1,0.36,1)',
            ].join(';') + ';';

            // El cuerpo soporta string plano O HTML escapado por el caller
            const bodyHtml = (typeof body === 'string' && body.includes('<'))
                ? body
                : String(body).split('\n').map(l => `<div>${(l || '&nbsp;').replace(/&/g,'&amp;').replace(/</g,'&lt;')}</div>`).join('');

            root.innerHTML = `
                <div role="dialog" aria-modal="true" aria-labelledby="argus-confirm-title"
                     style="background:var(--bg-2,#15110A);color:var(--text,#EAD8C0);
                            border:1px solid var(--border-m,rgba(184,115,51,0.28));
                            border-radius:14px;width:min(460px,92vw);
                            box-shadow:0 24px 64px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) inset;
                            animation:argusConfirmPop 220ms cubic-bezier(0.22,1,0.36,1);overflow:hidden;">
                    <div style="padding:20px 22px 8px;">
                        <div id="argus-confirm-title" style="font-size:15px;font-weight:700;color:var(--text-h,#EAD8C0);letter-spacing:0.2px;">${title.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</div>
                    </div>
                    <div style="padding:6px 22px 18px;font-size:13px;line-height:1.55;color:var(--text-m,#A89578);">
                        ${bodyHtml}
                    </div>
                    <div style="padding:14px 22px;background:rgba(0,0,0,0.18);
                                border-top:1px solid var(--border,rgba(184,115,51,0.12));
                                display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap;">
                        <button id="argus-confirm-cancel" type="button"
                                style="font-size:12.5px;font-weight:600;padding:8px 16px;border-radius:8px;
                                       background:transparent;border:1px solid var(--border-m,rgba(184,115,51,0.28));
                                       color:var(--text-m,#A89578);cursor:pointer;letter-spacing:0.2px;
                                       transition:all 160ms ease;">${cancelLabel.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</button>
                        <button id="argus-confirm-ok" type="button"
                                style="font-size:12.5px;font-weight:700;padding:8px 18px;border-radius:8px;
                                       background:${okBg};border:none;color:#fff;cursor:pointer;
                                       letter-spacing:0.2px;box-shadow:0 6px 18px -6px ${okShadow};
                                       transition:all 160ms ease;">${okLabel.replace(/&/g,'&amp;').replace(/</g,'&lt;')}</button>
                    </div>
                </div>`;

            document.body.appendChild(root);

            const close = (val) => {
                document.removeEventListener('keydown', onKey, true);
                root.style.animation = 'argusConfirmFadeOut 140ms cubic-bezier(0.22,1,0.36,1)';
                setTimeout(() => { root.remove(); resolve(val); }, 130);
            };
            const onKey = (e) => {
                if (e.key === 'Escape') { e.preventDefault(); close(false); }
                else if (e.key === 'Enter') { e.preventDefault(); close(true); }
            };
            document.addEventListener('keydown', onKey, true);
            root.addEventListener('click', (e) => { if (e.target === root) close(false); });
            root.querySelector('#argus-confirm-cancel').addEventListener('click', () => close(false));
            root.querySelector('#argus-confirm-ok').addEventListener('click',     () => close(true));
            // Foco al cancel para que Enter accidental NO confirme acciones destructivas
            setTimeout(() => {
                (danger ? root.querySelector('#argus-confirm-cancel')
                        : root.querySelector('#argus-confirm-ok')).focus();
            }, 30);
        });
    }


    // ── Visual #41 — Typewriter / animación typing en text containers ─────────
    // Usado para el resumen IA y otros textos generados que aparecen "vivos".
    // API: argusUI.typewriter(el, text, opts) → Promise<void> que resuelve
    // al terminar. Cancelable (.argus-tw-cancel = true sobre el elemento).
    function typewriter(el, text, opts) {
        const o = opts || {};
        const speed = Math.max(2, o.speedCps ? Math.round(1000 / o.speedCps) : (o.delay || 12));
        const reduce = window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        return new Promise((resolve) => {
            if (!el || !text) { if (el) el.textContent = String(text || ''); return resolve(); }
            if (reduce) { el.textContent = String(text); return resolve(); }
            el._argusTwCancel = false;
            el.textContent = '';
            // Caret pulsante
            const caret = document.createElement('span');
            caret.className = 'argus-tw-caret';
            caret.style.cssText = 'display:inline-block;width:1px;height:1em;background:currentColor;margin-left:1px;animation:argusTwBlink 850ms steps(2) infinite;vertical-align:-2px;opacity:0.7;';
            el.appendChild(caret);

            const chars = String(text).split('');
            let i = 0;
            // Escribir en chunks de 1-3 chars para sentir más "humano"
            function step() {
                if (el._argusTwCancel) {
                    if (caret.parentNode) caret.remove();
                    el.textContent = String(text);
                    return resolve();
                }
                const burst = 1 + (Math.random() < 0.25 ? 2 : 0);
                for (let k = 0; k < burst && i < chars.length; k++, i++) {
                    caret.insertAdjacentText('beforebegin', chars[i]);
                }
                if (i >= chars.length) {
                    setTimeout(() => { if (caret.parentNode) caret.remove(); resolve(); }, 350);
                    return;
                }
                // Pausa más larga después de signos de puntuación
                const last = chars[i - 1] || '';
                const extra = '.,;:?!\n'.includes(last) ? 80 : 0;
                setTimeout(step, speed + extra);
            }
            step();
        });
    }


    // ── Visual #3 — Modo low-motion manual (independiente del SO) ───────────
    // Aplica clase .argus-lowmotion a <html>. CSS en argus-ui.css desactiva
    // todas las animaciones/transiciones cuando esa clase está presente.
    // Persiste en localStorage('argus_lowmotion').
    const LM_KEY = 'argus_lowmotion';
    function _applyLowMotion(b) {
        const html = document.documentElement;
        if (b) html.classList.add('argus-lowmotion');
        else   html.classList.remove('argus-lowmotion');
        try { localStorage.setItem(LM_KEY, b ? '1' : '0'); } catch (_e) {}
    }
    function _getLowMotion() {
        try { return localStorage.getItem(LM_KEY) === '1'; }
        catch (_e) { return false; }
    }
    function setLowMotion(b) { _applyLowMotion(!!b); }
    _applyLowMotion(_getLowMotion());


    // ── Visual #10 — Line chart SVG vanilla para risk score histórico ───────
    // Sin libs externas. Recibe target (selector | element) y data: array
    // de {date: 'YYYY-MM-DD', value: number}. Dibuja un SVG con línea suave
    // (cubic Bezier), área bajo la curva con gradient bronce, dots en cada
    // punto, ejes X (fechas espaciadas) e Y (0-100), tooltip on hover.
    // Honra prefers-reduced-motion (no anima la línea).
    function renderLineChart(target, data, opts) {
        const t = (typeof target === 'string') ? document.querySelector(target) : target;
        if (!t) return;
        const o = opts || {};
        const w = o.width || t.clientWidth || 720;
        const h = o.height || 200;
        const pad = { top: 16, right: 14, bottom: 28, left: 36 };
        const innerW = w - pad.left - pad.right;
        const innerH = h - pad.top - pad.bottom;
        const yMin = 0;
        const yMax = o.yMax || 100;
        const reduce = window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (!data || !data.length) {
            t.innerHTML = '';
            renderEmptyState(t, {
                icon: 'chart',
                title: 'Sin datos históricos',
                description: 'Cuando este staff confirme veredictos, aparecerán acá.',
            });
            return;
        }
        const n = data.length;
        const xAt = (i) => pad.left + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
        const yAt = (v) => pad.top + innerH - ((Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin)) * innerH;
        const points = data.map((d, i) => [xAt(i), yAt(d.value)]);
        // Path con curvas Catmull-Rom → Bezier
        let line = '';
        for (let i = 0; i < points.length; i++) {
            const [x, y] = points[i];
            if (i === 0) { line += `M ${x.toFixed(1)} ${y.toFixed(1)}`; continue; }
            const [px, py] = points[i - 1];
            const cx1 = px + (x - px) * 0.45;
            const cy1 = py;
            const cx2 = x  - (x - px) * 0.45;
            const cy2 = y;
            line += ` C ${cx1.toFixed(1)} ${cy1.toFixed(1)}, ${cx2.toFixed(1)} ${cy2.toFixed(1)}, ${x.toFixed(1)} ${y.toFixed(1)}`;
        }
        const baseY = pad.top + innerH;
        const area = line + ` L ${points[points.length - 1][0].toFixed(1)} ${baseY} L ${points[0][0].toFixed(1)} ${baseY} Z`;
        // Y-axis ticks: 0, 25, 50, 75, 100 (o lo que dicte yMax)
        const yTicks = [0, 25, 50, 75, 100].filter(v => v >= yMin && v <= yMax);
        const yTickHtml = yTicks.map(v => {
            const yy = yAt(v);
            return `<line x1="${pad.left}" x2="${w - pad.right}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="2,4"/>` +
                   `<text x="${pad.left - 6}" y="${(yy + 4).toFixed(1)}" text-anchor="end" fill="rgba(234,216,192,0.5)" font-size="10" font-family="ui-monospace,monospace">${v}</text>`;
        }).join('');
        // X-axis labels — máximo 6 etiquetas equiespaciadas
        const xLabelStep = Math.max(1, Math.floor(n / 6));
        const xLabelHtml = data.map((d, i) => {
            if (i % xLabelStep !== 0 && i !== n - 1) return '';
            const xx = xAt(i);
            const lbl = (d.label || (d.date ? d.date.slice(5) : ''));
            return `<text x="${xx.toFixed(1)}" y="${(h - 8).toFixed(1)}" text-anchor="middle" fill="rgba(234,216,192,0.45)" font-size="10" font-family="ui-monospace,monospace">${lbl}</text>`;
        }).join('');
        const dotsHtml = points.map(([x, y], i) => {
            const v = data[i].value;
            const color = v >= 70 ? '#FF6B6B' : v >= 30 ? '#FFB86B' : '#5BC180';
            return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${color}" stroke="#1a1410" stroke-width="1.5">` +
                   `<title>${data[i].label || data[i].date || ''}: ${v}</title></circle>`;
        }).join('');
        const gradId = 'argusLineGrad_' + Math.random().toString(36).slice(2, 7);
        const animAttr = reduce ? '' :
            ' style="stroke-dasharray:1500;stroke-dashoffset:1500;animation:argusLineDraw 1.8s 0.1s ease-out forwards"';
        t.innerHTML = `
        <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Risk score histórico">
            <defs>
                <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%"   stop-color="#EAD8C0" stop-opacity="0.32"/>
                    <stop offset="100%" stop-color="#EAD8C0" stop-opacity="0"/>
                </linearGradient>
            </defs>
            ${yTickHtml}
            <path d="${area}" fill="url(#${gradId})"/>
            <path d="${line}" fill="none" stroke="#EAD8C0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"${animAttr}/>
            ${dotsHtml}
            ${xLabelHtml}
        </svg>`;
    }

    // Re-export el helper para que panel.js pueda llamarlo
    function renderLineChartPublic(target, data, opts) {
        return renderLineChart(target, data, opts);
    }


    // ── Visual #13 — Sistema de logros / streaks gamificado ─────────────────
    // Catálogo client-side de achievements. Recibe stats {scans_total,
    // verdicts_total, days_active, streak, best_streak, clean_count,
    // hack_count, sus_count} y devuelve array de logros calificados.
    const ACHIEVEMENTS = [
        // Volumen
        { id: 'first_scan',   icon: '🎯', label: 'Primer scan',           desc: 'Confirmaste tu primer veredicto',       check: s => (s.verdicts_total || 0) >= 1 },
        { id: 'ten_scans',    icon: '🔟', label: '10 scans',               desc: 'Confirmaste 10 veredictos',             check: s => (s.verdicts_total || 0) >= 10 },
        { id: 'fifty_scans',  icon: '🚀', label: '50 scans',               desc: 'Confirmaste 50 veredictos',             check: s => (s.verdicts_total || 0) >= 50 },
        { id: 'hundred',      icon: '💯', label: 'Centenario',             desc: 'Confirmaste 100 veredictos',            check: s => (s.verdicts_total || 0) >= 100 },
        { id: 'half_grand',   icon: '🏛️', label: '500 veredictos',         desc: 'Llegaste a 500 confirmaciones',         check: s => (s.verdicts_total || 0) >= 500 },
        { id: 'grand',        icon: '👑', label: 'Mil scans',              desc: 'Mil veredictos confirmados',            check: s => (s.verdicts_total || 0) >= 1000 },
        // Streaks
        { id: 'streak_3',     icon: '🔥', label: 'Racha de 3 días',        desc: '3 días seguidos activo',                check: s => (s.streak || 0) >= 3 },
        { id: 'streak_7',     icon: '⚡', label: 'Una semana al hilo',    desc: '7 días seguidos confirmando',          check: s => (s.streak || 0) >= 7 },
        { id: 'streak_30',    icon: '🌙', label: 'Mes de constancia',     desc: '30 días seguidos activo',               check: s => (s.streak || 0) >= 30 },
        { id: 'streak_best',  icon: '🏆', label: 'Mejor racha 14+',       desc: 'Tu mejor racha llegó a 14 días',        check: s => (s.best_streak || 0) >= 14 },
        // Distribución
        { id: 'clean_keeper', icon: '🟩', label: 'Cuidador',                desc: '50+ veredictos LIMPIO confirmados',     check: s => (s.clean_count || 0) >= 50 },
        { id: 'cazador',      icon: '🎯', label: 'Cazador',                 desc: '20+ veredictos HACK confirmados',       check: s => (s.hack_count || 0) >= 20 },
        { id: 'detective',    icon: '🔎', label: 'Detective',               desc: '20+ veredictos SOSPECHOSO',             check: s => (s.sus_count || 0) >= 20 },
        // Días activos
        { id: 'active_30',    icon: '📅', label: '30 días activos',         desc: 'Activo en 30 días distintos',           check: s => (s.days_active || 0) >= 30 },
        { id: 'active_100',   icon: '🗓️', label: '100 días activos',        desc: 'Activo en 100 días distintos',          check: s => (s.days_active || 0) >= 100 },
    ];

    function evaluateAchievements(stats) {
        const s = stats || {};
        return ACHIEVEMENTS.map(a => ({
            id: a.id, icon: a.icon, label: a.label,
            description: a.desc,
            unlocked: !!(a.check && a.check(s)),
        }));
    }

    function renderAchievements(target, stats) {
        const t = (typeof target === 'string') ? document.querySelector(target) : target;
        if (!t) return;
        const list = evaluateAchievements(stats);
        const unlocked = list.filter(x => x.unlocked).length;
        const total = list.length;
        const pct = Math.round(unlocked / total * 100);
        const html = `
        <div class="argus-achievement-grid">
            <div class="argus-achievement-summary">
                <div class="argus-achievement-progress">
                    <div class="argus-achievement-progress-bar" style="width:${pct}%"></div>
                </div>
                <div class="argus-achievement-count">${unlocked}<span>/${total} logros</span></div>
            </div>
            <div class="argus-achievement-cards">
                ${list.map(a => `
                    <div class="argus-achievement-card${a.unlocked ? ' is-unlocked' : ''}" title="${a.description.replace(/"/g, '&quot;')}">
                        <div class="argus-achievement-icon">${a.icon}</div>
                        <div class="argus-achievement-text">
                            <div class="argus-achievement-label">${a.label}</div>
                            <div class="argus-achievement-desc">${a.description}</div>
                        </div>
                        ${a.unlocked
                            ? '<div class="argus-achievement-badge">✓</div>'
                            : '<div class="argus-achievement-lock">🔒</div>'
                        }
                    </div>
                `).join('')}
            </div>
        </div>`;
        t.innerHTML = html;
    }


    // ── Export ───────────────────────────────────────────────────────────────
    window.showToast        = showToast;
    window.renderEmptyState = renderEmptyState;
    window.renderSkeleton   = renderSkeleton;
    window.argusUI = {
        showToast,
        renderEmptyState,
        renderSkeleton,
        refreshFooter: _refreshFooter,
        setDensity,
        getDensity: _getDensity,
        setScansView,
        getScansView: _getScansView,
        markScanRunning,
        markScanFinished,
        openQuickSearch:  _qsOpen,
        closeQuickSearch: _qsClose,
        setFontSize,
        getFontSize: _getFontSize,
        setSoundEnabled,
        isSoundEnabled: _isSoundEnabled,
        playScanDing,
        setStreamFriendly,
        isStreamFriendly: _isStreamFriendly,
        companyColor,
        companyTag,
        staggerIn,
        celebrate,
        confirm: confirmModal,
        typewriter,
        renderLoading,
        setLowMotion,
        getLowMotion: _getLowMotion,
        renderLineChart: renderLineChartPublic,
        renderAchievements,
        evaluateAchievements,
    };

    // Re-aplicar la vista guardada cuando se haya cargado el DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => _applyScansView(_getScansView()));
    } else {
        _applyScansView(_getScansView());
    }
})();
