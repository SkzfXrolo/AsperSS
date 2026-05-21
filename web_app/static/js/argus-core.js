/**
 * Argus Core — copiloto del panel (UI + saludo proactivo)
 * Usa /api/staff/chat y funciones de panel.js (sendAIChatMessage, etc.)
 */
(function () {
  'use strict';

  const CORE_LABEL = 'Argus Core';

  function $(id) { return document.getElementById(id); }

  function _orbThinking(on) {
    const fab = $('ai-chat-btn');
    if (fab) fab.classList.toggle('is-thinking', !!on);
  }

  async function _fetchBrief() {
    try {
      const res = await fetch('/api/argus-core/brief');
      if (!res.ok) return null;
      return await res.json();
    } catch (_e) {
      return null;
    }
  }

  function _appendCoreMsg(container, html, role, isSystem) {
    const el = document.createElement('div');
    el.className = 'argus-core-msg argus-core-msg--' + (role === 'user' ? 'user' : 'bot');
    if (isSystem) el.classList.add('argus-core-msg--system');
    if (role === 'bot' && !isSystem) {
      el.innerHTML = '<div class="argus-core-msg-label">' + CORE_LABEL + '</div>' + html;
    } else {
      el.innerHTML = html;
    }
    container.appendChild(el);
    if (typeof _scrollAIChatToBottom === 'function') {
      _scrollAIChatToBottom(container);
    } else {
      container.scrollTop = container.scrollHeight;
    }
    return el;
  }

  async function _showProactiveGreeting() {
    const msgs = $('ai-chat-messages');
    if (!msgs || msgs.dataset.coreGreeted === '1') return;

    const brief = await _fetchBrief();
    if (!brief || !brief.greeting) return;

    msgs.dataset.coreGreeted = '1';
    const first = msgs.querySelector('.argus-core-welcome');
    if (first) first.remove();

    _appendCoreMsg(msgs, brief.greeting, 'bot', true);

    const sub = $('argus-core-status');
    if (sub) {
      sub.textContent = brief.pending_scans
        ? brief.pending_scans + ' pendientes · en línea'
        : 'Todos los sistemas · en línea';
      sub.classList.add('is-live');
    }
  }

  function _enhanceToggle() {
    const orig = window.toggleAIChat;
    if (!orig || orig._argusCoreWrapped) return;

    window.toggleAIChat = function () {
      const panel = $('ai-chat-panel');
      const fab = $('ai-chat-btn');
      orig.apply(this, arguments);
      if (fab) {
        fab.classList.toggle('is-open', panel && panel.style.display === 'flex');
      }
      if (panel && panel.style.display === 'flex') {
        if (window.currentScanId) {
          _loadScanConversation(window.currentScanId);
        } else {
          _showProactiveGreeting();
        }
        const inp = $('ai-floating-chat-input');
        if (inp) inp.placeholder = window.currentScanId
          ? 'Pregunta sobre el scan #' + window.currentScanId + '…'
          : 'Habla con Argus Core…';
      }
    };
    window.toggleAIChat._argusCoreWrapped = true;
  }

  function _enhanceSend() {
    const orig = window.sendAIChatMessage;
    if (!orig || orig._argusCoreWrapped) return;

    window.sendAIChatMessage = async function () {
      _orbThinking(true);
      try {
        await orig.apply(this, arguments);
      } finally {
        _orbThinking(false);
      }
    };
    window.sendAIChatMessage._argusCoreWrapped = true;
  }

  function _enhanceAppend() {
    const orig = window._appendChatMsg;
    if (typeof orig !== 'function' || orig._argusCoreWrapped) return;

    window._appendChatMsg = function _appendChatMsgCore(container, text, role, isTyping) {
      if (isTyping) {
        const el = document.createElement('div');
        el.className = 'argus-core-msg argus-core-msg--bot';
        el.innerHTML = '<div class="argus-core-msg-label">' + CORE_LABEL + '</div><span class="ai-typing-dots">● ● ●</span>';
        container.appendChild(el);
        if (typeof _scrollAIChatToBottom === 'function') _scrollAIChatToBottom(container);
        return el;
      }
      if (role === 'user') {
        return _appendCoreMsg(container, text, 'user', false);
      }
      const html = typeof _formatAIReply === 'function' ? _formatAIReply(text) : text;
      return _appendCoreMsg(container, html, 'bot', false);
    };
    window._appendChatMsg._argusCoreWrapped = true;
  }

  function _enhanceClear() {
    const orig = window.clearAIChat;
    if (!orig) return;

    window.clearAIChat = async function () {
      const msgs = $('ai-chat-messages');
      if (msgs) delete msgs.dataset.coreGreeted;
      await orig.apply(this, arguments);
    };
  }

  function _bindShortcut() {
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        if (typeof window.toggleAIChat === 'function') window.toggleAIChat();
      }
    });
  }

  function _watchScanContext() {
    setInterval(function () {
      const badge = $('ai-chat-scan-badge');
      const sub = $('argus-core-status');
      if (!badge) return;
      if (window.currentScanId) {
        badge.textContent = 'Contexto activo · Scan #' + window.currentScanId;
        badge.style.display = 'block';
        if (sub && !sub.textContent.includes('Scan')) {
          /* keep brief status */
        }
      } else {
        badge.style.display = 'none';
      }
    }, 2000);
  }

  function _resetChatUi(msgs, welcomeHtml) {
    if (!msgs) return;
    msgs.innerHTML = '';
    _appendCoreMsg(msgs, welcomeHtml || 'Argus Core listo.', 'bot', true);
  }

  window._argusCoreResetChat = function (msgsEl) {
    const msgs = msgsEl || $('ai-chat-messages');
    const sid = window.currentScanId;
    const welcome = sid
      ? 'Memoria del scan #' + sid + ' reiniciada. ¿Analizamos hallazgos o veredicto?'
      : 'Memoria reiniciada. Abrí un escaneo para analizarlo con Gemini.';
    _resetChatUi(msgs, welcome);
  };

  async function _loadGeminiStatus() {
    const sub = $('argus-core-status');
    if (!sub) return;
    try {
      const res = await fetch('/api/argus-core/status');
      const data = await res.json();
      if (!data.ready) {
        sub.textContent = 'Gemini no configurado';
        sub.classList.remove('is-live');
        return;
      }
      sub.textContent = 'Gemini · ' + (data.model || 'online');
      sub.classList.add('is-live');
    } catch (_e) {
      sub.textContent = 'Sin conexión al motor';
    }
  }

  async function _loadScanConversation(scanId) {
    const msgs = $('ai-chat-messages');
    const panel = $('ai-chat-panel');
    if (!msgs || !scanId) return;
    if (panel && panel.style.display !== 'flex') return;

    try {
      const res = await fetch('/api/argus-core/history?scan_id=' + encodeURIComponent(scanId));
      if (!res.ok) return;
      const data = await res.json();
      const turns = data.turns || [];
      if (!turns.length) return;

      msgs.innerHTML = '';
      msgs.dataset.coreGreeted = '1';
      turns.forEach(function (t) {
        if (t.role === 'user') {
          _appendCoreMsg(msgs, t.text, 'user', false);
        } else {
          const html = typeof window._formatAIReply === 'function' ? window._formatAIReply(t.text) : t.text;
          _appendCoreMsg(msgs, html, 'bot', false);
        }
      });
    } catch (_e) { /* ignore */ }
  }

  window._argusCoreOnScanOpen = function (scanId) {
    const badge = $('ai-chat-scan-badge');
    const sub = $('argus-core-status');
    if (badge && scanId) {
      badge.textContent = 'Gemini · Scan #' + scanId;
      badge.style.display = 'block';
    }
    if (sub) sub.textContent = 'Caso activo · Scan #' + scanId;

    const panel = $('ai-chat-panel');
    if (panel && panel.style.display === 'flex') {
      _loadScanConversation(scanId);
    } else {
      const msgs = $('ai-chat-messages');
      if (msgs) delete msgs.dataset.coreGreeted;
    }
  };

  function init() {
    _enhanceToggle();
    _enhanceSend();
    _enhanceAppend();
    _enhanceClear();
    _bindShortcut();
    _watchScanContext();
    _loadGeminiStatus();

    const fab = $('ai-chat-btn');
    if (fab) {
      fab.title = 'Argus Core — Gemini · scan a scan (Ctrl+J)';
    }

  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
