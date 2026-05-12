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
      });
    }
    return _escapeHTML(str);
  }

  function safeSetText(el, text) {
    if (!el) return;
    el.textContent = text == null ? '' : String(text);
  }

  function safeSetHTML(el, htmlStr) {
    if (!el) return;
    el.innerHTML = _sanitizeHTML(htmlStr);
  }

  // Hardening global: sanitizea toda escritura de innerHTML.
  try {
    var desc = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
    if (desc && typeof desc.set === 'function' && !Element.prototype.__argusSafeInnerHTMLPatched) {
      Object.defineProperty(Element.prototype, 'innerHTML', {
        configurable: true,
        enumerable: desc.enumerable,
        get: function () {
          return desc.get.call(this);
        },
        set: function (value) {
          desc.set.call(this, _sanitizeHTML(value));
        },
      });
      Object.defineProperty(Element.prototype, '__argusSafeInnerHTMLPatched', {
        value: true,
        configurable: false,
        enumerable: false,
        writable: false,
      });
    }
  } catch (e) {
    console.warn('[safe.js] no se pudo parchear innerHTML:', e);
  }

  window.escapeHTML = _escapeHTML;
  window.safeSetText = safeSetText;
  window.safeSetHTML = safeSetHTML;
})();
