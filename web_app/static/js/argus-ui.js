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
    const QS_DEBOUNCE_MS = 220;
    let _qsDebounce  = null;
    let _qsItems     = [];
    let _qsActiveIdx = 0;
    let _qsAbort     = null;

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
                '<span style="font-size:11px;opacity:0.7;">Tip: si escribís solo un número, abre ese scan directamente.</span>' +
                '</div>';
            return;
        }
        if (!_qsItems.length) {
            box.innerHTML = '<div style="padding:18px;text-align:center;color:rgba(241,230,211,0.55);font-size:13px;">' +
                'Sin resultados para <b>' + _qsEscape(query) + '</b></div>';
            return;
        }
        const html = _qsItems.map((s, i) => {
            const risk = s.risk_score == null ? '—' : s.risk_score;
            const riskColor = risk >= 70 ? '#ef4444' : risk >= 30 ? '#f59e0b' : '#10b981';
            const player    = s.minecraft_user || s.user || s.usuario || 'Sin jugador';
            const company   = s.empresa_name || s.company || s.empresa || '';
            const created   = s.created_at ? new Date(s.created_at).toLocaleString() : '';
            const active = (i === _qsActiveIdx);
            return '<div class="argus-qs-item" data-id="' + s.id + '" data-idx="' + i + '"' +
                   ' style="display:flex;align-items:center;gap:10px;padding:9px 16px;cursor:pointer;' +
                   'border-left:3px solid ' + (active ? 'rgba(212,145,90,0.95)' : 'transparent') + ';' +
                   'background:' + (active ? 'rgba(184,115,51,0.10)' : 'transparent') + ';">' +
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
            el.addEventListener('click', () => {
                _qsOpenScan(parseInt(el.dataset.id, 10));
            });
            el.addEventListener('mouseenter', () => {
                _qsActiveIdx = parseInt(el.dataset.idx, 10);
                _qsRender(document.getElementById('argus-quicksearch-input').value);
            });
        });
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
        try {
            const url = '/api/scans?limit=40&q=' + encodeURIComponent(query);
            const r = await fetch(url, _qsAbort ? { signal: _qsAbort.signal } : {});
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const d = await r.json();
            let items = (d && d.scans) ? d.scans : (Array.isArray(d) ? d : []);
            // Si la query es solo numérica, intentamos también que aparezca el ID exacto
            const isNumeric = /^\d+$/.test(query);
            if (isNumeric) {
                const idQ = parseInt(query, 10);
                const exact = items.find(s => s.id === idQ);
                if (!exact) {
                    items = [{ id: idQ, minecraft_user: '(abrir scan #' + idQ + ')', risk_score: null }, ...items];
                }
            } else {
                // Filtro client-side adicional por si el backend ignora ?q=
                const ql = query.toLowerCase();
                items = items.filter(s => {
                    const haystack = [
                        s.id, s.minecraft_user, s.user, s.usuario,
                        s.empresa_name, s.company, s.empresa,
                    ].filter(Boolean).join(' ').toLowerCase();
                    return haystack.includes(ql);
                });
            }
            _qsItems = items.slice(0, 25);
            _qsActiveIdx = 0;
            _qsRender(query);
        } catch (e) {
            if (e && e.name === 'AbortError') return;
            _qsItems = [];
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
                if (_qsItems.length) _qsOpenScan(_qsItems[_qsActiveIdx].id);
            }
        });
        root.addEventListener('click', (e) => {
            if (e.target === root) _qsClose();
        });
        input.addEventListener('input', () => {
            const q = input.value.trim();
            if (_qsDebounce) clearTimeout(_qsDebounce);
            if (!q) { _qsItems = []; _qsRender(''); return; }
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
    };

    // Re-aplicar la vista guardada cuando se haya cargado el DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => _applyScansView(_getScansView()));
    } else {
        _applyScansView(_getScansView());
    }
})();
