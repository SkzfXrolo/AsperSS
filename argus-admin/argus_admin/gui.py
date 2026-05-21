"""
ArgusAdmin — ventana: enroll voz → desbloqueo → panel imperial.
"""
from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, scrolledtext, simpledialog

from . import ADMIN_TITLE, ADMIN_VERSION
from .api_client import ArgusAdminApi
from .config_local import load, update
from .voice_lock import (
    VoiceProfileOutdated,
    all_fingerprint_hashes,
    enroll_sample,
    finalize_profile,
    is_enrolled,
    is_server_synced,
    mark_server_synced,
    primary_fingerprint_hash,
    profile_needs_reenroll,
    record_wav,
    reset_profile,
    verify_wav,
    voice_threshold_percent,
)


class ArgusAdminApp:
    BG = '#0a0a0f'
    GOLD = '#B87333'
    TEXT = '#f5e6d8'

    def __init__(self) -> None:
        self.cfg = load()
        try:
            self.api = ArgusAdminApi()
        except RuntimeError as e:
            self.api = None
            self._api_init_error = str(e)
        else:
            self._api_init_error = ''
        self.unlocked = False
        self.root = tk.Tk()
        self.root.title(ADMIN_TITLE)
        self.root.geometry('560x720')
        self.root.configure(bg=self.BG)
        self._show_gate()

    def _clear(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()

    def _show_gate(self) -> None:
        self._clear()
        f = tk.Frame(self.root, bg=self.BG, padx=24, pady=24)
        f.pack(fill='both', expand=True)

        tk.Label(f, text='◆ ARGUS ADMIN', font=('Segoe UI', 20, 'bold'), fg=self.GOLD, bg=self.BG).pack()
        tk.Label(
            f, text=f'v{ADMIN_VERSION} · Candado por voz + Render',
            font=('Segoe UI', 10), fg='#888', bg=self.BG,
        ).pack(pady=(4, 20))

        if self._api_init_error:
            tk.Label(
                f, text=self._api_init_error, fg='#f88', bg=self.BG, wraplength=420,
            ).pack(pady=8)
        elif self.api:
            ok_api, api_msg = self.api.check_api_available()
            if not ok_api:
                tk.Label(
                    f, text=api_msg, fg='#f88', bg=self.BG, wraplength=440, justify='left',
                ).pack(pady=8)
            else:
                tk.Label(f, text=api_msg, fg='#5a8', bg=self.BG, font=('Segoe UI', 9)).pack()

        if profile_needs_reenroll():
            tk.Label(
                f,
                text='Perfil de voz antiguo — tenés que Regrabar voz (3 muestras).',
                fg='#f88', bg=self.BG, wraplength=420, font=('Segoe UI', 11, 'bold'),
            ).pack(pady=12)
            tk.Button(
                f, text='Regrabar voz (obligatorio)', command=self._enroll_voice,
                bg=self.GOLD, fg='#1a1008', relief='flat', padx=16, pady=14,
            ).pack(pady=12, fill='x')
        elif not is_enrolled():
            tk.Label(
                f, text='Primera vez: grabá tu voz (3 veces la misma frase).',
                fg=self.TEXT, bg=self.BG, wraplength=420,
            ).pack()
            tk.Button(
                f, text='1. Configurar cuenta y API', command=self._setup_account,
                bg='#21262d', fg=self.TEXT, relief='flat', padx=16, pady=8,
            ).pack(pady=8, fill='x')
            tk.Button(
                f, text='2. Grabar mi voz (3 muestras)', command=self._enroll_voice,
                bg=self.GOLD, fg='#1a1008', relief='flat', padx=16, pady=10,
            ).pack(pady=8, fill='x')
        else:
            sync_note = '' if is_server_synced() else '\n⚠ Falta sync con Render — Regrabar voz.'
            tk.Label(
                f,
                text=f'Decí tu frase: «{self.cfg.get("phrase", "desbloqueo argus")}»{sync_note}',
                fg=self.TEXT, bg=self.BG, wraplength=420, font=('Segoe UI', 11, 'bold'),
            ).pack(pady=12)
            tk.Button(
                f, text='🎤 Desbloquear con mi voz', command=self._unlock_voice,
                bg=self.GOLD, fg='#1a1008', relief='flat', padx=16, pady=14,
            ).pack(pady=12, fill='x')
            tk.Button(
                f, text='Regrabar voz', command=self._enroll_voice,
                bg='#21262d', fg=self.TEXT, relief='flat',
            ).pack(pady=4)
            tk.Button(
                f, text='Solo contraseña (sin voz)', command=self._unlock_password_only,
                bg='#21262d', fg='#aaa', relief='flat',
            ).pack(pady=6)

        tk.Label(
            f,
            text='Tip: hablá claro la misma frase. Si falla, Regrabar voz (3 muestras).',
            fg='#666', bg=self.BG, font=('Segoe UI', 9),
        ).pack(pady=12)

    def _setup_account(self) -> None:
        url = simpledialog.askstring('API', 'URL Render:', initialvalue=self.cfg.get('api_url', ''))
        user = simpledialog.askstring(
            'Cuenta', 'Usuario owner (ej. arefy_admin):', initialvalue=self.cfg.get('username', ''),
        )
        if url:
            update(api_url=url.rstrip('/'))
        if user:
            update(username=user)
        self.cfg = load()
        try:
            self.api = ArgusAdminApi()
            self._api_init_error = ''
        except RuntimeError as e:
            self.api = None
            self._api_init_error = str(e)
        messagebox.showinfo('ArgusAdmin', 'Guardado en %APPDATA%\\ArgusAdmin\\config.json')

    def _enroll_voice(self) -> None:
        if not self.cfg.get('username'):
            self._setup_account()
            self.cfg = load()
        if not self.api:
            messagebox.showerror('Error', self._api_init_error or 'Configurá la URL del API primero.')
            return
        pwd = simpledialog.askstring('Contraseña', 'Contraseña del panel owner:', show='*')
        if not pwd:
            return
        ok_api, api_msg = self.api.check_api_available()
        if not ok_api:
            messagebox.showerror('API no disponible', api_msg)
            return
        reset_profile()
        phrase = self.cfg.get('phrase') or 'desbloqueo argus'
        for i in range(3):
            messagebox.showinfo(
                'Grabación',
                f'Muestra {i + 1}/3\nDecí en voz alta (mismo tono cada vez):\n«{phrase}»',
            )
            try:
                wav = record_wav(4.5)
                enroll_sample(wav)
            except Exception as e:
                messagebox.showerror('Error de grabación', str(e))
                return
        fp = finalize_profile()
        if not fp:
            messagebox.showerror('Error', 'No se pudo crear el perfil de voz (faltan muestras).')
            return
        try:
            self.api = ArgusAdminApi()
            self.api.login(self.cfg['username'], pwd)
            self.api.enroll_voice(fp, extra_hashes=all_fingerprint_hashes())
            mark_server_synced()
            messagebox.showinfo('ArgusAdmin', 'Voz registrada en este PC y en Render.')
        except Exception as e:
            messagebox.showwarning(
                'Solo local',
                f'Perfil de voz guardado en este PC.\n\n'
                f'No se pudo sincronizar con Render:\n{e}\n\n'
                'Probá de nuevo cuando el servidor esté despierto.',
            )
        self.cfg = load()
        self._show_gate()

    def _unlock_voice(self) -> None:
        if not self.api:
            messagebox.showerror('Error', self._api_init_error or 'Falta configurar API.')
            return
        pwd = simpledialog.askstring('Contraseña', 'Contraseña owner:', show='*')
        if not pwd:
            return
        phrase = self.cfg.get('phrase') or 'desbloqueo argus'
        messagebox.showinfo('Voz', f'Decí claro: «{phrase}»\n(mismo tono que al registrar)')
        try:
            wav = record_wav(4.5)
            ok, sim, fp = verify_wav(wav)
            if not ok:
                pct = int(sim * 100)
                need = voice_threshold_percent()
                hint = (
                    f'Coincidencia {pct}% (necesitás {need}% o más).\n\n'
                    'Hablá igual que en las 3 muestras, o usá «Regrabar voz».'
                )
                messagebox.showerror('Bloqueado', hint)
                return
            if not fp:
                messagebox.showerror('Error', 'Perfil incompleto. Usá Regrabar voz.')
                return
            if not is_server_synced():
                messagebox.showwarning(
                    'Render',
                    'Tu voz local coincide, pero no está en el servidor.\n'
                    'Usá «Regrabar voz» con internet.',
                )
            self.api = ArgusAdminApi()
            data = self.api.unlock_voice(self.cfg['username'], pwd, fp)
            self.unlocked = True
            self._show_dashboard(data)
        except VoiceProfileOutdated as e:
            messagebox.showwarning('Regrabar voz', str(e))
            self._show_gate()
        except Exception as e:
            err = str(e)
            if 'not aligned' in err or 'shapes' in err:
                messagebox.showwarning(
                    'Regrabar voz',
                    'Perfil de voz incompatible con esta versión.\n'
                    'Usá «Regrabar voz» y grabá las 3 muestras de nuevo.',
                )
                self._show_gate()
            else:
                messagebox.showerror('Error', err)

    def _unlock_password_only(self) -> None:
        if not self.api:
            messagebox.showerror('Error', self._api_init_error or 'Falta configurar API.')
            return
        pwd = simpledialog.askstring('Contraseña', 'Contraseña owner:', show='*')
        if not pwd:
            return
        try:
            fp = primary_fingerprint_hash()
            if not fp:
                messagebox.showerror('Error', 'Primero registrá tu voz (3 muestras).')
                return
            self.api = ArgusAdminApi()
            data = self.api.unlock_voice(self.cfg['username'], pwd, fp)
            self.unlocked = True
            self._show_dashboard(data)
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def _show_dashboard(self, unlock_data: dict) -> None:
        self._clear()
        top = tk.Frame(self.root, bg='#16161f', padx=16, pady=12)
        top.pack(fill='x')
        tk.Label(
            top, text='IMPERIAL — DESBLOQUEADO', fg=self.GOLD, bg='#16161f',
            font=('Segoe UI', 12, 'bold'),
        ).pack(side='left')
        tk.Button(
            top, text='Cerrar sesión', command=self._show_gate, bg='#333', fg='#fff', relief='flat',
        ).pack(side='right')

        perms = unlock_data.get('permissions') or []
        self.log = scrolledtext.ScrolledText(self.root, bg='#0d0d12', fg=self.TEXT, font=('Consolas', 10))
        self.log.pack(fill='both', expand=True, padx=12, pady=12)
        self._println('Permisos ArgusAdmin:')
        for p in perms:
            self._println(f'  • {p}')

        try:
            ov = self.api.overview()
            self._println('\nKPIs Render:')
            if ov.get('error'):
                self._println(f'  error: {ov["error"]}')
            for k, v in (ov.get('kpis') or {}).items():
                self._println(f'  {k}: {v}')
        except Exception as e:
            self._println(f'KPIs error: {e}')

        btns = tk.Frame(self.root, bg=self.BG, padx=12, pady=8)
        btns.pack(fill='x')
        base = self.cfg.get('api_url', '')
        tk.Button(
            btns, text='Abrir Super Admin web (/aspers-sa)',
            command=lambda: webbrowser.open(f'{base}/aspers-sa'),
            bg=self.GOLD, fg='#1a1008', relief='flat', pady=8,
        ).pack(fill='x', pady=4)
        tk.Button(
            btns, text='Panel staff',
            command=lambda: webbrowser.open(f'{base}/panel'),
            bg='#21262d', fg=self.TEXT, relief='flat', pady=6,
        ).pack(fill='x')

    def _println(self, line: str) -> None:
        self.log.insert('end', line + '\n')
        self.log.see('end')

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    ArgusAdminApp().run()
