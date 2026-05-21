/**
 * Argus Core — voz (micrófono + TTS del navegador)
 * Requiere Chrome/Edge; en Firefox solo texto.
 */
(function () {
  'use strict';

  const STORAGE_VOICE = 'argus_core_voice_on';
  const STORAGE_CONVO = 'argus_core_voice_convo';

  let voiceOn = localStorage.getItem(STORAGE_VOICE) === '1';
  let convoMode = localStorage.getItem(STORAGE_CONVO) === '1';
  let listening = false;
  let recognition = null;
  let preferredVoice = null;

  function $(id) { return document.getElementById(id); }

  function _stripForSpeech(htmlOrText) {
    const div = document.createElement('div');
    div.innerHTML = String(htmlOrText || '');
    let t = (div.textContent || '').replace(/\s+/g, ' ').trim();
    t = t.replace(/✦ Gemini[^·]*·[^·]*/gi, '');
    t = t.replace(/🤖[^·]*/g, '');
    return t.slice(0, 1200);
  }

  function _initRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    const r = new SR();
    r.lang = 'es-AR';
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.continuous = false;
    r.onstart = function () {
      listening = true;
      const mic = $('argus-core-mic-btn');
      if (mic) mic.classList.add('is-listening');
      const st = $('argus-core-status');
      if (st) st.textContent = 'Escuchando…';
    };
    r.onend = function () {
      listening = false;
      const mic = $('argus-core-mic-btn');
      if (mic) mic.classList.remove('is-listening');
      _syncStatusLabel();
    };
    r.onerror = function (e) {
      console.warn('[Argus Core voice]', e.error);
      if (e.error === 'not-allowed') {
        _toast('Permití el micrófono en el navegador para hablar con Argus Core.');
      }
    };
    r.onresult = function (ev) {
      const text = (ev.results[0] && ev.results[0][0] && ev.results[0][0].transcript) || '';
      const trimmed = text.trim();
      if (!trimmed) return;
      const inp = $('ai-floating-chat-input');
      if (inp) {
        inp.value = trimmed;
        inp.style.height = 'auto';
        inp.style.height = Math.min(inp.scrollHeight, 80) + 'px';
      }
      if (typeof window.sendAIChatMessage === 'function') {
        window.sendAIChatMessage();
      }
    };
    return r;
  }

  function _pickSpanishVoice() {
    if (preferredVoice) return preferredVoice;
    const voices = window.speechSynthesis ? speechSynthesis.getVoices() : [];
    preferredVoice = voices.find(function (v) {
      return /es(-|_)(AR|MX|ES|419|US)?/i.test(v.lang) && /google|microsoft|natural|premium/i.test(v.name);
    }) || voices.find(function (v) { return v.lang && v.lang.startsWith('es'); }) || voices[0];
    return preferredVoice;
  }

  function _speak(text, onDone) {
    if (!voiceOn || !window.speechSynthesis) {
      if (onDone) onDone();
      return;
    }
    const plain = _stripForSpeech(text);
    if (!plain) {
      if (onDone) onDone();
      return;
    }
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(plain);
    u.lang = 'es-AR';
    const v = _pickSpanishVoice();
    if (v) u.voice = v;
    u.rate = 1.02;
    u.pitch = 0.95;
    const st = $('argus-core-status');
    if (st) st.textContent = 'Argus Core hablando…';
    u.onend = function () {
      _syncStatusLabel();
      if (onDone) onDone();
    };
    u.onerror = function () {
      _syncStatusLabel();
      if (onDone) onDone();
    };
    speechSynthesis.speak(u);
  }

  window._argusCoreSpeak = _speak;

  function _syncStatusLabel() {
    const st = $('argus-core-status');
    if (!st || listening) return;
    if (voiceOn) {
      st.textContent = convoMode ? 'Voz · modo conversación' : 'Voz activa';
      st.classList.add('is-live');
    } else if (typeof window.currentScanId !== 'undefined' && window.currentScanId) {
      st.textContent = 'Caso activo · Scan #' + window.currentScanId;
    }
  }

  function _toast(msg) {
    const msgs = $('ai-chat-messages');
    if (!msgs || typeof window._appendChatMsg !== 'function') {
      alert(msg);
      return;
    }
    window._appendChatMsg(msgs, msg, 'bot', false);
  }

  function _startListening() {
    if (!recognition) {
      _toast('Tu navegador no soporta micrófono. Usá Chrome o Edge.');
      return;
    }
    if (listening) {
      recognition.stop();
      return;
    }
    try {
      speechSynthesis.cancel();
      recognition.start();
    } catch (e) {
      console.warn('[Argus Core voice] start', e);
    }
  }

  function _updateVoiceUi() {
    const togg = $('argus-core-voice-toggle');
    const mic = $('argus-core-mic-btn');
    const conv = $('argus-core-convo-toggle');
    if (togg) togg.classList.toggle('is-on', voiceOn);
    if (togg) togg.setAttribute('aria-pressed', voiceOn ? 'true' : 'false');
    if (conv) conv.classList.toggle('is-on', convoMode);
    if (mic) mic.disabled = false;
    _syncStatusLabel();
  }

  function _bindControls() {
    const togg = $('argus-core-voice-toggle');
    const mic = $('argus-core-mic-btn');
    const conv = $('argus-core-convo-toggle');

    if (togg) {
      togg.addEventListener('click', function () {
        voiceOn = !voiceOn;
        localStorage.setItem(STORAGE_VOICE, voiceOn ? '1' : '0');
        if (!voiceOn) speechSynthesis.cancel();
        _updateVoiceUi();
        if (voiceOn) _speak('Voz activada. Podés usar el micrófono.', function () {
          if (convoMode) _startListening();
        });
      });
    }

    if (conv) {
      conv.addEventListener('click', function () {
        convoMode = !convoMode;
        localStorage.setItem(STORAGE_CONVO, convoMode ? '1' : '0');
        if (convoMode) voiceOn = true;
        localStorage.setItem(STORAGE_VOICE, voiceOn ? '1' : '0');
        _updateVoiceUi();
      });
    }

    if (mic) {
      mic.addEventListener('click', _startListening);
    }

    if (window.speechSynthesis) {
      speechSynthesis.onvoiceschanged = function () { _pickSpanishVoice(); };
      _pickSpanishVoice();
    }

    recognition = _initRecognition();
    if (!recognition && mic) {
      mic.title = 'Micrófono no disponible en este navegador';
      mic.disabled = true;
    }
    _updateVoiceUi();
  }

  function _wrapAppend() {
    const orig = window._appendChatMsg;
    if (typeof orig !== 'function' || orig._argusVoiceWrapped) return;

    window._appendChatMsg = function (container, text, role, isTyping) {
      const el = orig.apply(this, arguments);
      if (!isTyping && role === 'bot' && voiceOn && text) {
        const raw = typeof text === 'string' ? text : (el && el.textContent) || '';
        _speak(raw, function () {
          if (convoMode && voiceOn) {
            setTimeout(_startListening, 400);
          }
        });
      }
      return el;
    };
    window._appendChatMsg._argusVoiceWrapped = true;
  }

  function init() {
    _wrapAppend();
    _bindControls();
    if (voiceOn) _syncStatusLabel();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
