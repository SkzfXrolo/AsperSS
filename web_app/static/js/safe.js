/* safe.js - helpers de rendering seguro para panel.js */
(function () {
  function _escapeHTML(input) {
    if (input == null) return '';
    return String(input)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function _sanitizeHTML(html) {
    var str = String(html == null ? '' : html);
    if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      return window.DOMPurify.sanitize(str, {
        USE_PROFILES: { html: true },
        ADD_ATTR: ['onclick', 'oninput', 'onchange', 'target'],
      });
    }
    return str;
  }

  function safeSetText(el, text) {
    if (!el) return;
    el.textContent = text == null ? '' : String(text);
  }

  // Usar solo para contenido que venga de entrada del usuario (notas, búsquedas, etc.)
  // NO usar para HTML generado internamente por panel.js
  function safeSetHTML(el, htmlStr) {
    if (!el) return;
    el.innerHTML = _sanitizeHTML(htmlStr);
  }

  // El override global de innerHTML fue eliminado — era demasiado agresivo y
  // eliminaba onclick/oninput/data: URLs del HTML generado por el propio panel.js.
  // XSS prevention se aplica puntualmente con safeSetHTML() donde hay input real de usuario.

  window.escapeHTML   = _escapeHTML;
  window.safeSetText  = safeSetText;
  window.safeSetHTML  = safeSetHTML;
})();
