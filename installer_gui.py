"""
installer_gui.py — BeastSync Streamer-Setup (ein Klick, kein technisches Wissen noetig).
Server-URL ist in installer_config.json gebacken.
Streamer geben nur ihren WoT-Account-Namen ein.
"""

import sys
import os
import json
import shutil
import winreg
import tkinter as tk
from tkinter import filedialog, messagebox

# ─── Ressourcenpfad ───────────────────────────────────────────────────────────

def _res(rel):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ─── Gebundene Konfiguration laden ────────────────────────────────────────────

def _load_installer_config():
    path = _res('installer_config.json')
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {'server_url': 'http://localhost:5000', 'event_name': 'BeastSync Challenge'}


_icfg      = _load_installer_config()
SERVER_URL = _icfg.get('server_url', 'http://localhost:5000')
EVENT_NAME = _icfg.get('event_name', 'BeastSync Challenge')
WOTMOD_SRC = _res(os.path.join('dist', 'mohjobeist_beastsync.wotmod'))

# ─── WoT Auto-Erkennung ───────────────────────────────────────────────────────

_REGISTRY_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}',
     'InstallLocation'),
    (winreg.HKEY_LOCAL_MACHINE,
     r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}',
     'InstallLocation'),
]

_COMMON_PATHS = [
    r'C:\Games\World_of_Tanks',
    r'C:\Games\World_of_Tanks_EU',
    r'D:\Games\World_of_Tanks',
    r'C:\Program Files (x86)\World_of_Tanks',
    r'C:\Program Files\World_of_Tanks',
]


def _find_wot():
    for hkey, sub, val in _REGISTRY_KEYS:
        try:
            with winreg.OpenKey(hkey, sub) as k:
                path, _ = winreg.QueryValueEx(k, val)
                if path and os.path.isfile(os.path.join(path, 'WorldOfTanks.exe')):
                    return path
        except (FileNotFoundError, OSError):
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam') as k:
            steam, _ = winreg.QueryValueEx(k, 'InstallPath')
        p = os.path.join(steam, 'steamapps', 'common', 'World of Tanks')
        if os.path.isfile(os.path.join(p, 'WorldOfTanks.exe')):
            return p
    except (FileNotFoundError, OSError):
        pass
    for p in _COMMON_PATHS:
        if os.path.isfile(os.path.join(p, 'WorldOfTanks.exe')):
            return p
    return ''


def _find_version(wot_path):
    res_mods = os.path.join(wot_path, 'res_mods')
    if not os.path.isdir(res_mods):
        return None
    versions = sorted(
        [d for d in os.listdir(res_mods)
         if os.path.isdir(os.path.join(res_mods, d)) and d[0].isdigit()],
        reverse=True)
    return versions[0] if versions else None


def _install(wot_path, streamer_name):
    if not os.path.isfile(os.path.join(wot_path, 'WorldOfTanks.exe')):
        return False, 'WorldOfTanks.exe nicht in diesem Ordner gefunden.'

    version = _find_version(wot_path)
    if not version:
        return False, (
            'Keinen WoT-Versionsordner in res_mods/ gefunden.\n'
            'Bitte World of Tanks einmal starten und danach nochmal versuchen.')

    # .wotmod
    mods_dir = os.path.join(wot_path, 'mods')
    os.makedirs(mods_dir, exist_ok=True)
    shutil.copy2(WOTMOD_SRC, os.path.join(mods_dir, 'mohjobeist_beastsync.wotmod'))

    # config.json
    cfg_dir = os.path.join(wot_path, 'res_mods', version, 'mods', 'beastsync')
    os.makedirs(cfg_dir, exist_ok=True)
    cfg = {
        'server_url': SERVER_URL,
        'streamer_name': streamer_name.strip(),
        'enabled': True,
        'send_interval_ms': 200,
        'allowed_arena_types': [1, 7],
    }
    with open(os.path.join(cfg_dir, 'config.json'), 'w') as f:
        json.dump(cfg, f, indent=2)

    return True, version


# ─── GUI ──────────────────────────────────────────────────────────────────────

BG     = '#0d1117'
BG2    = '#161b22'
BDR    = '#30363d'
ACCENT = '#ffe033'
GREEN  = '#3fb950'
RED    = '#f85149'
WHITE  = '#e6edf3'
GRAY   = '#8b949e'
FONT   = 'Segoe UI'


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BeastSync Setup — ' + EVENT_NAME)
        self.configure(bg=BG)
        self.resizable(False, False)

        self._wot_path   = _find_wot()
        self._page       = 0   # 0 = Eingabe, 1 = Ergebnis
        self._name_var   = tk.StringVar()
        self._path_var   = tk.StringVar(value=self._wot_path)

        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f'{w}x{h}+{x}+{y}')

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Banner
        banner = tk.Frame(self, bg=ACCENT, height=6)
        banner.pack(fill='x')

        # Header
        hdr = tk.Frame(self, bg=BG, padx=28, pady=20)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🐾 BeastSync', bg=BG, fg=ACCENT,
                 font=(FONT, 20, 'bold')).pack(anchor='w')
        tk.Label(hdr, text='Mod Setup — ' + EVENT_NAME,
                 bg=BG, fg=GRAY, font=(FONT, 11)).pack(anchor='w')

        # Content-Frame (wird pro Seite neu befuellt)
        self._content = tk.Frame(self, bg=BG, padx=28)
        self._content.pack(fill='both', expand=True)

        # Footer
        self._footer = tk.Frame(self, bg=BG2, padx=28, pady=16)
        self._footer.pack(fill='x')

        self._show_input()

    def _clear(self):
        for w in self._content.winfo_children():
            w.destroy()
        for w in self._footer.winfo_children():
            w.destroy()

    # ── Seite 1: Eingabe ──────────────────────────────────────────────────────

    def _show_input(self):
        self._clear()
        c = self._content

        tk.Label(c, text='Dein World of Tanks Account-Name',
                 bg=BG, fg=WHITE, font=(FONT, 12, 'bold')).pack(anchor='w', pady=(0, 6))
        tk.Label(c,
                 text='Genau so eingeben wie er im Spiel angezeigt wird.',
                 bg=BG, fg=GRAY, font=(FONT, 10)).pack(anchor='w', pady=(0, 12))

        # Name-Eingabe
        name_entry = tk.Entry(self._content, textvariable=self._name_var,
                              bg=BG2, fg=WHITE, insertbackground=WHITE,
                              font=(FONT, 14), bd=0, relief='flat',
                              highlightthickness=1, highlightbackground=BDR,
                              highlightcolor=ACCENT)
        name_entry.pack(fill='x', ipady=10, pady=(0, 4))
        name_entry.focus_set()
        name_entry.bind('<Return>', lambda _: self._try_install())

        tk.Label(c, text='⚠  Groß-/Kleinschreibung beachten!',
                 bg=BG, fg=GRAY, font=(FONT, 9, 'italic')).pack(anchor='w')

        # WoT-Pfad (zugeklappt, nur bei Bedarf sichtbar)
        sep = tk.Frame(c, bg=BDR, height=1)
        sep.pack(fill='x', pady=18)

        path_row = tk.Frame(c, bg=BG)
        path_row.pack(fill='x')

        path_icon = '✅' if os.path.isfile(
            os.path.join(self._path_var.get(), 'WorldOfTanks.exe')) else '⚠'
        self._path_status = tk.Label(
            path_row, text=f'{path_icon}  WoT gefunden',
            bg=BG, fg=GREEN if path_icon == '✅' else '#ffaa33',
            font=(FONT, 10))
        self._path_status.pack(side='left')

        tk.Button(path_row, text='Anderen Ordner wählen',
                  bg=BG2, fg=GRAY, font=(FONT, 9), bd=0,
                  padx=10, pady=4, cursor='hand2',
                  command=self._browse).pack(side='right')

        # Footer: Installieren-Button
        tk.Button(self._footer, text='Jetzt installieren  →',
                  bg=ACCENT, fg='#0d1117',
                  font=(FONT, 12, 'bold'), bd=0,
                  padx=24, pady=10, cursor='hand2',
                  command=self._try_install).pack(side='right')

    def _browse(self):
        p = filedialog.askdirectory(title='World of Tanks Ordner auswählen')
        if p:
            self._path_var.set(p)
            ok = os.path.isfile(os.path.join(p, 'WorldOfTanks.exe'))
            self._path_status.config(
                text=('✅  WoT gefunden' if ok else '✗  WorldOfTanks.exe nicht gefunden'),
                fg=(GREEN if ok else RED))

    def _try_install(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning('Hinweis', 'Bitte deinen WoT-Account-Namen eingeben.')
            return

        if not os.path.isfile(os.path.join(self._path_var.get(), 'WorldOfTanks.exe')):
            messagebox.showerror('Fehler',
                'WoT-Ordner nicht gefunden.\nBitte "Anderen Ordner wählen" nutzen.')
            return

        self._show_progress()
        self.update()

        ok, result = _install(self._path_var.get(), name)
        self._show_result(ok, name, result)

    # ── Seite 2: Fortschritt / Ergebnis ───────────────────────────────────────

    def _show_progress(self):
        self._clear()
        tk.Label(self._content, text='Installiere…',
                 bg=BG, fg=GRAY, font=(FONT, 13)).pack(pady=30)

    def _show_result(self, ok, name, result):
        self._clear()
        c = self._content

        if ok:
            tk.Label(c, text='✅  Fertig!', bg=BG, fg=GREEN,
                     font=(FONT, 18, 'bold')).pack(anchor='w', pady=(0, 12))
            tk.Label(c,
                     text=f'Der Mod wurde erfolgreich installiert.\nWoT-Version: {result}',
                     bg=BG, fg=WHITE, font=(FONT, 11), justify='left').pack(anchor='w')

            tk.Frame(c, bg=BDR, height=1).pack(fill='x', pady=18)

            tk.Label(c, text='Nächste Schritte:', bg=BG, fg=GRAY,
                     font=(FONT, 10, 'bold')).pack(anchor='w')
            steps = [
                f'1.  World of Tanks neu starten',
                f'2.  Eine Runde spielen',
                f'3.  Der Veranstalter sieht dich dann als "{name}" im System',
            ]
            for s in steps:
                tk.Label(c, text=s, bg=BG, fg=WHITE,
                         font=(FONT, 10)).pack(anchor='w', pady=2)

            # Footer: Schließen
            tk.Button(self._footer, text='Schließen',
                      bg=ACCENT, fg='#0d1117',
                      font=(FONT, 12, 'bold'), bd=0,
                      padx=24, pady=10, cursor='hand2',
                      command=self.destroy).pack(side='right')

        else:
            tk.Label(c, text='❌  Fehler', bg=BG, fg=RED,
                     font=(FONT, 18, 'bold')).pack(anchor='w', pady=(0, 12))
            tk.Label(c, text=result, bg=BG, fg=WHITE,
                     font=(FONT, 11), justify='left', wraplength=400).pack(anchor='w')

            # Footer: Zurück
            tk.Button(self._footer, text='← Zurück',
                      bg=BG2, fg=WHITE,
                      font=(FONT, 12, 'bold'), bd=0,
                      padx=24, pady=10, cursor='hand2',
                      command=self._show_input).pack(side='right')


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    App().mainloop()
