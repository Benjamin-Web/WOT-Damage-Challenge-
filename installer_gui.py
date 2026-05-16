"""
installer_gui.py — Mohjos DamageRace Streamer-Setup.
Modernes Dark-UI mit CustomTkinter, Heist-Bot-Branding (Gold).
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

# ─── Brand-Farben (Heist Bot M3 Gold-Theme) ───────────────────────────────────

BG      = "#0d0d14"     # surface-dim
BG2     = "#17171f"     # surface-container
BG3     = "#1e1e28"     # surface-container-high
BDR     = "#2a2a35"     # outline
ACCENT  = "#ffd700"     # primary
ACCENT2 = "#efb700"     # tertiary
GREEN   = "#00e676"
RED     = "#cf6679"
WHITE   = "#f3f4f6"
GRAY    = "#9ca3af"
DIM     = "#6b7280"

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
                "event_name": "Mohjos DamageRace"}

_icfg      = _load_installer_config()
SERVER_URL = _icfg.get("server_url", "http://localhost:5000")
EVENT_NAME = _icfg.get("event_name", "Mohjos DamageRace")
WOTMOD_SRC = _res(os.path.join("dist", "mohjos_damagerace.wotmod"))

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
    shutil.copy2(WOTMOD_SRC, os.path.join(mods_dir, "mohjos_damagerace.wotmod"))
    cfg_dir = os.path.join(wot_path, "res_mods", version, "mods", "damagerace")
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
        self.title("Mohjos DamageRace — Setup")
        self.geometry("480x580")
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

    def _build(self):
        # Gold-Accent oben
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # Header
        hdr = ctk.CTkFrame(self, fg_color=BG2, corner_radius=0)
        hdr.pack(fill="x")
        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=24, pady=(20, 18))

        # Logo + Brand
        logo_row = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        logo_row.pack(anchor="w")
        mark = tk.Label(logo_row, text="M", bg=ACCENT, fg="#000",
                        font=("Inter", 16, "bold"), width=2, height=1)
        mark.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(logo_row, text="Mohjos DamageRace",
                     font=ctk.CTkFont("Inter", 20, "bold"),
                     text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(hdr_inner,
                     text="Mod-Installer  ·  " + EVENT_NAME,
                     font=ctk.CTkFont("Inter", 11),
                     text_color=GRAY).pack(anchor="w", pady=(6, 0))

        # Body
        body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        body.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(body,
                     text="DEIN WORLD OF TANKS ACCOUNT-NAME",
                     font=ctk.CTkFont("Inter", 10, "bold"),
                     text_color=GRAY).pack(anchor="w", pady=(0, 8))

        self.name_entry = ctk.CTkEntry(
            body,
            placeholder_text="z.B. Mohjo_beist",
            font=ctk.CTkFont("Inter", 14),
            height=46,
            fg_color=BG2,
            border_color=BDR,
            text_color=WHITE,
            placeholder_text_color=DIM,
            corner_radius=8)
        self.name_entry.pack(fill="x", pady=(0, 6))
        self.name_entry.bind("<Return>", lambda _: self._try_install())

        ctk.CTkLabel(body,
                     text="Muss exakt zum Namen im Invite-Link passen (Groß-/Kleinschreibung)",
                     font=ctk.CTkFont("Inter", 11),
                     text_color=DIM).pack(anchor="w", pady=(0, 20))

        tk.Frame(body, bg=BDR, height=1).pack(fill="x", pady=(0, 18))

        # WoT-Pfad-Status
        wot_ok = os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe"))
        version = _find_version(self._wot_path) if wot_ok else None

        if wot_ok and version:
            icon, color, txt = "✓", GREEN, f"World of Tanks gefunden  ·  Version {version}"
        elif wot_ok:
            icon, color, txt = "!", "#ff9800", "WoT gefunden, aber res_mods/ fehlt — bitte WoT einmal starten"
        else:
            icon, color, txt = "✕", RED, "World of Tanks nicht gefunden"

        path_row = ctk.CTkFrame(body, fg_color="transparent")
        path_row.pack(fill="x")

        self.path_label = ctk.CTkLabel(
            path_row, text=f"{icon}  {txt}",
            font=ctk.CTkFont("Inter", 11),
            text_color=color)
        self.path_label.pack(side="left")

        ctk.CTkButton(
            path_row, text="Anderen Ordner",
            font=ctk.CTkFont("Inter", 11),
            width=130, height=30,
            fg_color=BG3, hover_color=BDR,
            text_color=WHITE, border_color=BDR, border_width=1,
            corner_radius=6,
            command=self._browse).pack(side="right")

        ctk.CTkFrame(body, fg_color="transparent", height=24).pack()

        self.install_btn = ctk.CTkButton(
            body,
            text="Jetzt installieren  →",
            font=ctk.CTkFont("Inter", 14, "bold"),
            height=50,
            fg_color=ACCENT,
            hover_color=ACCENT2,
            text_color="#000",
            corner_radius=8,
            command=self._try_install)
        self.install_btn.pack(fill="x")

        self.status_label = ctk.CTkLabel(
            body, text="",
            font=ctk.CTkFont("Inter", 12),
            text_color=GRAY,
            wraplength=400,
            justify="left")
        self.status_label.pack(anchor="w", pady=(16, 0))

    def _browse(self):
        from tkinter import filedialog
        p = filedialog.askdirectory(title="World of Tanks Ordner waehlen")
        if not p:
            return
        self._wot_path = p
        ok = os.path.isfile(os.path.join(p, "WorldOfTanks.exe"))
        v  = _find_version(p) if ok else None
        if ok and v:
            self.path_label.configure(
                text=f"✓  World of Tanks gefunden  ·  Version {v}",
                text_color=GREEN)
        elif ok:
            self.path_label.configure(
                text="!  WoT gefunden, aber res_mods/ fehlt — bitte WoT starten",
                text_color="#ff9800")
        else:
            self.path_label.configure(
                text="✕  WorldOfTanks.exe nicht gefunden",
                text_color=RED)

    def _try_install(self):
        name = self.name_entry.get().strip()
        if not name:
            self.status_label.configure(
                text="!  Bitte deinen WoT-Account-Namen eingeben.",
                text_color="#ff9800")
            return
        if not os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe")):
            self.status_label.configure(
                text="✕  WoT-Ordner nicht gefunden. Bitte 'Anderen Ordner' waehlen.",
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
                text=(f"✓  Fertig! WoT-Version {result}\n\n"
                      f"Starte World of Tanks neu.\n"
                      f"Spiel eine Runde — der Veranstalter sieht dich als \"{name}\"."),
                text_color=GREEN)
            self.install_btn.configure(text="Erledigt ✓", state="disabled",
                                       fg_color=BG2, text_color=GREEN)
        else:
            self.status_label.configure(text=f"✕  {result}", text_color=RED)


if __name__ == "__main__":
    App().mainloop()
