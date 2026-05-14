"""
installer_gui.py — BeastSync Streamer-Setup.
Modernes Dark-UI mit CustomTkinter.
Streamer geben nur ihren WoT-Namen ein — alles andere ist automatisch.
"""

import sys
import os
import json
import shutil
import winreg
import threading
import tkinter as tk
import customtkinter as ctk

# ─── Appearance ───────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Farben (konsistent mit Admin-Panel) ──────────────────────────────────────

BG      = "#0d1117"
BG2     = "#161b22"
BDR     = "#30363d"
ACCENT  = "#ffe033"
GREEN   = "#3fb950"
RED     = "#f85149"
WHITE   = "#e6edf3"
GRAY    = "#8b949e"

# ─── Ressourcenpfad ───────────────────────────────────────────────────────────

def _res(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def _load_installer_config():
    try:
        with open(_res("installer_config.json"), "r") as f:
            return json.load(f)
    except Exception:
        return {"server_url": "http://localhost:5000",
                "event_name": "BeastSync Challenge"}

_icfg      = _load_installer_config()
SERVER_URL = _icfg.get("server_url", "http://localhost:5000")
EVENT_NAME = _icfg.get("event_name", "BeastSync Challenge")
WOTMOD_SRC = _res(os.path.join("dist", "mohjobeist_beastsync.wotmod"))

# ─── WoT-Erkennung ────────────────────────────────────────────────────────────

_REG_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}",
     "InstallLocation"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}",
     "InstallLocation"),
]
_COMMON = [
    r"C:\Games\World_of_Tanks",
    r"C:\Games\World_of_Tanks_EU",
    r"D:\Games\World_of_Tanks",
    r"C:\Program Files (x86)\World_of_Tanks",
]

def _find_wot():
    for hkey, sub, val in _REG_KEYS:
        try:
            with winreg.OpenKey(hkey, sub) as k:
                p, _ = winreg.QueryValueEx(k, val)
                if p and os.path.isfile(os.path.join(p, "WorldOfTanks.exe")):
                    return p
        except (FileNotFoundError, OSError):
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam") as k:
            steam, _ = winreg.QueryValueEx(k, "InstallPath")
        p = os.path.join(steam, "steamapps", "common", "World of Tanks")
        if os.path.isfile(os.path.join(p, "WorldOfTanks.exe")):
            return p
    except (FileNotFoundError, OSError):
        pass
    for p in _COMMON:
        if os.path.isfile(os.path.join(p, "WorldOfTanks.exe")):
            return p
    return ""

def _find_version(wot_path):
    res_mods = os.path.join(wot_path, "res_mods")
    if not os.path.isdir(res_mods):
        return None
    versions = sorted(
        [d for d in os.listdir(res_mods)
         if os.path.isdir(os.path.join(res_mods, d)) and d[0].isdigit()],
        reverse=True)
    return versions[0] if versions else None

def _install(wot_path, name):
    if not os.path.isfile(os.path.join(wot_path, "WorldOfTanks.exe")):
        return False, "WorldOfTanks.exe nicht in diesem Ordner gefunden."
    version = _find_version(wot_path)
    if not version:
        return False, ("Kein Versionsordner in res_mods/ gefunden.\n"
                       "Bitte World of Tanks einmal starten, dann erneut versuchen.")
    mods_dir = os.path.join(wot_path, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    shutil.copy2(WOTMOD_SRC, os.path.join(mods_dir, "mohjobeist_beastsync.wotmod"))
    cfg_dir = os.path.join(wot_path, "res_mods", version, "mods", "beastsync")
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "config.json"), "w") as f:
        json.dump({
            "server_url":       SERVER_URL,
            "streamer_name":    name.strip(),
            "enabled":          True,
            "send_interval_ms": 200,
            "allowed_arena_types": [1, 7],
        }, f, indent=2)
    return True, version

# ─── App ──────────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BeastSync Setup")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self._wot_path = _find_wot()
        self._build()
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Accent-Streifen
        accent_bar = tk.Frame(self, bg=ACCENT, height=4)
        accent_bar.pack(fill="x")

        # Header
        hdr = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="🐾  BeastSync",
                     font=ctk.CTkFont("Segoe UI", 22, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=24, pady=(18, 2))
        ctk.CTkLabel(hdr, text="Mod Setup — " + EVENT_NAME,
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=GRAY).pack(anchor="w", padx=24, pady=(0, 16))

        # Body
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # WoT-Name
        ctk.CTkLabel(body,
                     text="DEIN WORLD OF TANKS ACCOUNT-NAME",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=GRAY).pack(anchor="w", pady=(0, 6))

        self.name_entry = ctk.CTkEntry(
            body,
            placeholder_text="z.B. Mohjo_beist",
            font=ctk.CTkFont("Segoe UI", 15),
            height=46,
            fg_color=BG2,
            border_color=BDR,
            text_color=WHITE,
            placeholder_text_color=GRAY,
            corner_radius=8)
        self.name_entry.pack(fill="x", pady=(0, 6))
        self.name_entry.bind("<Return>", lambda _: self._try_install())

        ctk.CTkLabel(body,
                     text="⚠  Groß-/Kleinschreibung beachten",
                     font=ctk.CTkFont("Segoe UI", 11, "italic"),
                     text_color=GRAY).pack(anchor="w", pady=(0, 20))

        # Trennlinie
        tk.Frame(body, bg=BDR, height=1).pack(fill="x", pady=(0, 16))

        # WoT-Pfad-Status
        wot_ok = os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe"))
        version = _find_version(self._wot_path) if wot_ok else None

        if wot_ok and version:
            icon, color, txt = "✅", GREEN, f"World of Tanks gefunden  ·  Version {version}"
        elif wot_ok:
            icon, color, txt = "⚠", "#d29922", "WoT gefunden, aber res_mods/ fehlt — bitte WoT einmal starten"
        else:
            icon, color, txt = "✗", RED, "World of Tanks nicht gefunden"

        path_row = ctk.CTkFrame(body, fg_color="transparent")
        path_row.pack(fill="x")

        self.path_label = ctk.CTkLabel(
            path_row, text=f"{icon}  {txt}",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=color)
        self.path_label.pack(side="left")

        ctk.CTkButton(
            path_row, text="Anderen Ordner",
            font=ctk.CTkFont("Segoe UI", 11),
            width=120, height=28,
            fg_color=BG2, hover_color=BDR,
            text_color=GRAY, border_color=BDR, border_width=1,
            corner_radius=6,
            command=self._browse).pack(side="right")

        # Spacer
        ctk.CTkFrame(body, fg_color="transparent", height=20).pack()

        # Installieren-Button
        self.install_btn = ctk.CTkButton(
            body,
            text="Jetzt installieren  →",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            height=48,
            fg_color=ACCENT,
            hover_color="#e6c900",
            text_color="#0d1117",
            corner_radius=8,
            command=self._try_install)
        self.install_btn.pack(fill="x")

        # Status-Label (Ergebnis)
        self.status_label = ctk.CTkLabel(
            body, text="",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=GRAY,
            wraplength=380,
            justify="left")
        self.status_label.pack(anchor="w", pady=(14, 0))

    # ── Aktionen ──────────────────────────────────────────────────────────────

    def _browse(self):
        from tkinter import filedialog
        p = filedialog.askdirectory(title="World of Tanks Ordner wählen")
        if not p:
            return
        self._wot_path = p
        ok = os.path.isfile(os.path.join(p, "WorldOfTanks.exe"))
        v  = _find_version(p) if ok else None
        if ok and v:
            self.path_label.configure(
                text=f"✅  World of Tanks gefunden  ·  Version {v}",
                text_color=GREEN)
        elif ok:
            self.path_label.configure(
                text="⚠  WoT gefunden, aber res_mods/ fehlt — bitte WoT starten",
                text_color="#d29922")
        else:
            self.path_label.configure(
                text="✗  WorldOfTanks.exe nicht gefunden",
                text_color=RED)

    def _try_install(self):
        name = self.name_entry.get().strip()
        if not name:
            self.status_label.configure(
                text="⚠  Bitte deinen WoT-Account-Namen eingeben.",
                text_color="#d29922")
            return
        if not os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe")):
            self.status_label.configure(
                text="✗  WoT-Ordner nicht gefunden. Bitte 'Anderen Ordner' wählen.",
                text_color=RED)
            return

        self.install_btn.configure(state="disabled", text="Installiere…")
        self.status_label.configure(text="", text_color=GRAY)

        threading.Thread(target=self._do_install, args=(name,), daemon=True).start()

    def _do_install(self, name):
        ok, result = _install(self._wot_path, name)
        self.after(0, lambda: self._show_result(ok, name, result))

    def _show_result(self, ok, name, result):
        self.install_btn.configure(state="normal", text="Jetzt installieren  →")
        if ok:
            self.status_label.configure(
                text=(f"✅  Fertig! WoT-Version {result}\n\n"
                      f"Starte World of Tanks neu.\n"
                      f"Spiel eine Runde — der Veranstalter sieht dich dann als \"{name}\"."),
                text_color=GREEN)
            self.install_btn.configure(text="Fertig ✓", state="disabled",
                                       fg_color=BG2, text_color=GREEN)
        else:
            self.status_label.configure(text=f"✗  {result}", text_color=RED)

# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()
