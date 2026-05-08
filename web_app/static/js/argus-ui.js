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

    // ── Export ───────────────────────────────────────────────────────────────
    window.showToast        = showToast;
    window.renderEmptyState = renderEmptyState;
    window.renderSkeleton   = renderSkeleton;
    window.argusUI = { showToast, renderEmptyState, renderSkeleton };
})();
