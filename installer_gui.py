"""
installer_gui.py — Mohjos DamageRace Desktop-App

Welcome-Screen mit zwei Modi:
  1. Veranstalter (Organizer) — Twitch-OAuth-Login -> Event-Wizard
  2. Teilnehmer (Streamer)    — Invite-Code -> WoT-Mod installieren

Branding: Heist-Bot Material Design 3, Gold (#ffd700), Inter.
"""
import sys
import os
import json
import shutil
import threading
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Brand-Tokens (Heist Bot M3 Gold) ─────────────────────────────────────────

BG      = "#0d0d14"
BG2     = "#17171f"
BG3     = "#1e1e28"
BG4     = "#262631"
BDR     = "#2a2a35"
ACCENT  = "#ffd700"
ACCENT2 = "#efb700"
TWITCH  = "#9146ff"
TWITCH2 = "#7d2def"
GREEN   = "#00e676"
RED     = "#cf6679"
WHITE   = "#f3f4f6"
GRAY    = "#9ca3af"
DIM     = "#6b7280"

FONT_FAM = "Inter"

# ─── Config + Ressourcen ──────────────────────────────────────────────────────

def _res(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def _load_cfg():
    try:
        with open(_res("installer_config.json"), "r") as f:
            return json.load(f)
    except Exception:
        return {"server_url": "https://mohjos-damagerace.duckdns.org",
                "event_name": "Mohjos DamageRace"}

_CFG       = _load_cfg()
SERVER_URL = _CFG.get("server_url", "https://mohjos-damagerace.duckdns.org").rstrip("/")
WOTMOD_SRC = _res(os.path.join("dist", "mohjos_damagerace.wotmod"))

# ─── HTTP-Helper ──────────────────────────────────────────────────────────────

def http_json(method, path, data=None, cookies=None):
    url = SERVER_URL + path
    body = None
    headers = {"Content-Type": "application/json"}
    if cookies:
        headers["Cookie"] = "; ".join("{}={}".format(k, v) for k, v in cookies.items())
    if data is not None:
        body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode()
            set_cookie = r.headers.get("Set-Cookie")
            new_cookies = dict(cookies or {})
            if set_cookie:
                # primitive Set-Cookie-Parser
                first = set_cookie.split(";", 1)[0]
                if "=" in first:
                    k, v = first.split("=", 1)
                    new_cookies[k.strip()] = v.strip()
            try:
                return True, json.loads(text), new_cookies
            except Exception:
                return True, {"raw": text}, new_cookies
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode()), cookies or {}
        except Exception:
            return False, {"error": "HTTP {}".format(e.code)}, cookies or {}
    except Exception as e:
        return False, {"error": str(e)}, cookies or {}

# ─── WoT-Erkennung ────────────────────────────────────────────────────────────

_REG_KEYS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}", "InstallLocation"),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}", "InstallLocation"),
]
_COMMON = [
    r"C:\Games\World_of_Tanks",
    r"C:\Games\World_of_Tanks_EU",
    r"D:\Games\World_of_Tanks",
    r"C:\Program Files (x86)\World_of_Tanks",
]

def find_wot():
    if HAS_WINREG:
        for sub, val in _REG_KEYS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
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

def find_version(wot_path):
    res_mods = os.path.join(wot_path, "res_mods")
    if not os.path.isdir(res_mods):
        return None
    versions = sorted(
        [d for d in os.listdir(res_mods)
         if os.path.isdir(os.path.join(res_mods, d)) and d[:1].isdigit()],
        reverse=True)
    return versions[0] if versions else None

def install_mod(wot_path, wot_name, streamer_token):
    if not os.path.isfile(os.path.join(wot_path, "WorldOfTanks.exe")):
        return False, "WorldOfTanks.exe nicht im Ordner."
    version = find_version(wot_path)
    if not version:
        return False, "Kein Versionsordner in res_mods/ gefunden.\nBitte WoT einmal starten."
    mods_dir = os.path.join(wot_path, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    shutil.copy2(WOTMOD_SRC, os.path.join(mods_dir, "mohjos_damagerace.wotmod"))
    cfg_dir = os.path.join(wot_path, "res_mods", version, "mods", "damagerace")
    os.makedirs(cfg_dir, exist_ok=True)
    with open(os.path.join(cfg_dir, "config.json"), "w") as f:
        json.dump({
            "server_url":         SERVER_URL,
            "streamer_token":     streamer_token,
            "streamer_name":      wot_name,
            "enabled":            True,
            "send_interval_ms":   200,
            "allowed_arena_types": [1, 7],
        }, f, indent=2)
    return True, version

# ─── Brand-Logo Widget ────────────────────────────────────────────────────────

def make_logo(parent, big=False):
    size = 56 if big else 32
    font_size = 28 if big else 16
    fr = tk.Frame(parent, bg=ACCENT, width=size, height=size)
    fr.pack_propagate(False)
    lbl = tk.Label(fr, text="M", bg=ACCENT, fg="#000",
                   font=(FONT_FAM, font_size, "bold"))
    lbl.place(relx=0.5, rely=0.5, anchor="center")
    return fr

# ─── Hauptfenster ─────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Mohjos DamageRace")
        self.geometry("520x640")
        self.minsize(520, 640)
        self.configure(fg_color=BG)
        self.cookies = {}
        self.user = None
        self._center()
        self.show_welcome()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _clear(self):
        for child in self.winfo_children():
            child.destroy()

    def _topbar(self, parent, title, subtitle="", back=None):
        tk.Frame(parent, bg=ACCENT, height=3).pack(fill="x")
        bar = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=0)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(18, 18))
        if back:
            ctk.CTkButton(row, text="← Zurueck", width=90, height=28,
                          font=ctk.CTkFont(FONT_FAM, 11),
                          fg_color=BG3, hover_color=BDR,
                          text_color=GRAY, border_color=BDR, border_width=1,
                          corner_radius=6, command=back).pack(side="left")
            tk.Frame(row, bg=BG2, width=14).pack(side="left")
        logo = make_logo(row, big=False)
        logo.pack(side="left", padx=(0, 12))
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x")
        ctk.CTkLabel(col, text=title,
                     font=ctk.CTkFont(FONT_FAM, 18, "bold"),
                     text_color=ACCENT).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(col, text=subtitle,
                         font=ctk.CTkFont(FONT_FAM, 11),
                         text_color=GRAY).pack(anchor="w")

    # ── Screens ───────────────────────────────────────────────────────────────

    def show_welcome(self):
        self._clear()
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(40, 0))
        big_logo = tk.Frame(hdr, bg=ACCENT, width=72, height=72)
        big_logo.pack_propagate(False)
        big_logo.pack(pady=(0, 16))
        tk.Label(big_logo, text="M", bg=ACCENT, fg="#000",
                 font=(FONT_FAM, 36, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(hdr, text="Mohjos DamageRace",
                     font=ctk.CTkFont(FONT_FAM, 24, "bold"),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(hdr, text="World of Tanks Community Damage Race",
                     font=ctk.CTkFont(FONT_FAM, 12),
                     text_color=GRAY).pack(pady=(4, 0))

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(body, text="WOFUER MOECHTEST DU ES NUTZEN?",
                     font=ctk.CTkFont(FONT_FAM, 10, "bold"),
                     text_color=DIM).pack(anchor="w", pady=(0, 12))

        # Veranstalter-Card
        card1 = self._mode_card(body,
                                title="Event veranstalten",
                                desc="Du erstellst ein eigenes Event,\nteams konfigurieren, Streamer einladen.",
                                badge="Veranstalter",
                                color=ACCENT,
                                cmd=self.show_organizer_login)
        card1.pack(fill="x", pady=(0, 14))

        # Teilnehmer-Card
        card2 = self._mode_card(body,
                                title="An Event teilnehmen",
                                desc="Du hast einen Invite-Code von einem\nVeranstalter und willst mitmachen.",
                                badge="Streamer",
                                color="#03dac6",
                                cmd=self.show_participant)
        card2.pack(fill="x")

        # Footer
        ctk.CTkLabel(self,
                     text=f"Server: {SERVER_URL}",
                     font=ctk.CTkFont(FONT_FAM, 10),
                     text_color=DIM).pack(side="bottom", pady=10)

    def _mode_card(self, parent, title, desc, badge, color, cmd):
        outer = ctk.CTkFrame(parent, fg_color=BG2, border_color=BDR,
                             border_width=1, corner_radius=12)
        inner = ctk.CTkButton(outer, text="", fg_color="transparent",
                              hover_color=BG3, corner_radius=12,
                              command=cmd, anchor="w")
        inner.pack(fill="both", expand=True, padx=0, pady=0)

        content = ctk.CTkFrame(inner, fg_color="transparent")
        content.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Badge oben
        b = ctk.CTkLabel(content, text=badge,
                         font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                         text_color=color,
                         fg_color=BG3, corner_radius=99,
                         padx=10, pady=2)
        b.pack(anchor="w", padx=20, pady=(16, 6))

        ctk.CTkLabel(content, text=title,
                     font=ctk.CTkFont(FONT_FAM, 17, "bold"),
                     text_color=WHITE).pack(anchor="w", padx=20)
        ctk.CTkLabel(content, text=desc,
                     font=ctk.CTkFont(FONT_FAM, 12),
                     text_color=GRAY, justify="left").pack(anchor="w", padx=20, pady=(4, 18))

        outer.configure(height=130)
        outer.pack_propagate(False)
        return outer

    # ── Veranstalter: Login ───────────────────────────────────────────────────

    def show_organizer_login(self):
        self._clear()
        self._topbar(self, "Veranstalter-Login",
                     "Mit Twitch anmelden um Events zu erstellen",
                     back=self.show_welcome)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=40)

        # Twitch-Button
        twitch_btn = ctk.CTkButton(body, text="🟣  Mit Twitch anmelden",
                                   font=ctk.CTkFont(FONT_FAM, 15, "bold"),
                                   height=52,
                                   fg_color=TWITCH, hover_color=TWITCH2,
                                   text_color="#fff",
                                   corner_radius=8,
                                   command=self._do_twitch_login)
        twitch_btn.pack(fill="x")

        self.status_lbl = ctk.CTkLabel(body, text="",
                                       font=ctk.CTkFont(FONT_FAM, 12),
                                       text_color=GRAY,
                                       wraplength=420, justify="left")
        self.status_lbl.pack(anchor="w", pady=(20, 0))

        ctk.CTkLabel(body,
                     text="Hinweis: Es oeffnet sich dein Browser. Nach erfolgreicher\n"
                          "Twitch-Anmeldung kommst du automatisch hier zurueck.",
                     font=ctk.CTkFont(FONT_FAM, 11),
                     text_color=DIM, justify="left").pack(anchor="w", pady=(28, 0))

    def _do_twitch_login(self):
        self.status_lbl.configure(text="Browser geoeffnet — bitte mit Twitch anmelden…",
                                  text_color=GRAY)
        # Erst Cookie holen (Session anlegen serverseitig)
        ok, data, cookies = http_json("GET", "/auth/me")
        if cookies:
            self.cookies.update(cookies)
        # Auth-URL oeffnen
        webbrowser.open(SERVER_URL + "/auth/twitch/start")
        # Polling: alle 2s pruefen ob eingeloggt
        threading.Thread(target=self._poll_login, daemon=True).start()

    def _poll_login(self):
        import time
        for i in range(120):  # max 4 Minuten
            time.sleep(2)
            ok, data, cookies = http_json("GET", "/auth/me", cookies=self.cookies)
            if cookies:
                self.cookies.update(cookies)
            if ok and data.get("authenticated"):
                self.user = data.get("user")
                self.after(0, self.show_organizer_dashboard)
                return
        self.after(0, lambda: self.status_lbl.configure(
            text="Login-Timeout. Bitte erneut versuchen.", text_color=RED))

    # ── Veranstalter: Dashboard ───────────────────────────────────────────────

    def show_organizer_dashboard(self):
        self._clear()
        u = self.user or {}
        sub = "Eingeloggt als {}".format(u.get("display_name", "?"))
        self._topbar(self, "Dein Event", sub, back=self._logout)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # Event-State laden
        ok, data, cookies = http_json("GET", "/api/my-event", cookies=self.cookies)
        if cookies:
            self.cookies.update(cookies)

        if not ok or not data.get("authenticated"):
            self._logout()
            return

        if not data.get("event"):
            # Kein Event — Wizard direkt anzeigen
            self._render_wizard(body)
            return

        # Event existiert — Status + Buttons
        self._render_event_status(body, data)

    def _render_event_status(self, body, data):
        ev = data["event"]
        teams = data.get("teams", [])

        # Status-Card
        card = ctk.CTkFrame(body, fg_color=BG2, border_color=BDR,
                            border_width=1, corner_radius=12)
        card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(inner, text=ev["name"],
                     font=ctk.CTkFont(FONT_FAM, 18, "bold"),
                     text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(inner,
                     text="Modus: {} · Ziel: {:,}".format(
                         "Versus" if ev["mode"] == "versus" else "Coop",
                         ev["goal"]).replace(",", "."),
                     font=ctk.CTkFont(FONT_FAM, 11),
                     text_color=GRAY).pack(anchor="w", pady=(2, 0))

        # Stats
        stat = ctk.CTkFrame(inner, fg_color="transparent")
        stat.pack(fill="x", pady=(14, 0))
        for lbl, val, col in [
            ("Restdamage", ev["remaining"], ACCENT),
            ("Dealt",      ev["total_dealt"], GREEN),
        ]:
            cell = ctk.CTkFrame(stat, fg_color=BG3, corner_radius=8)
            cell.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(cell, text=lbl,
                         font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                         text_color=GRAY).pack(pady=(10, 0))
            ctk.CTkLabel(cell, text="{:,}".format(val).replace(",", "."),
                         font=ctk.CTkFont(FONT_FAM, 20, "bold"),
                         text_color=col).pack(pady=(2, 12))

        # Overlay-URL
        ovl = ctk.CTkFrame(body, fg_color=BG2, corner_radius=10)
        ovl.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(ovl, text="OBS BROWSER-SOURCE URL",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w", padx=14, pady=(12, 4))
        url_row = ctk.CTkFrame(ovl, fg_color="transparent")
        url_row.pack(fill="x", padx=14, pady=(0, 12))
        url_entry = ctk.CTkEntry(url_row, font=ctk.CTkFont(FONT_FAM, 11),
                                 fg_color=BG, border_color=BDR, text_color=ACCENT,
                                 height=32)
        url_entry.insert(0, ev.get("overlay_url") or "")
        url_entry.configure(state="readonly")
        url_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(url_row, text="Kopieren", width=90, height=32,
                      font=ctk.CTkFont(FONT_FAM, 11, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#000",
                      command=lambda u=ev.get("overlay_url"): self._copy(u)).pack(side="right", padx=(8, 0))

        # Teams + Invite-Links
        ctk.CTkLabel(body, text="TEAMS & INVITE-LINKS",
                     font=ctk.CTkFont(FONT_FAM, 10, "bold"),
                     text_color=GRAY).pack(anchor="w", pady=(8, 8))

        for t in teams:
            tcard = ctk.CTkFrame(body, fg_color=BG2,
                                 border_color=BDR, border_width=1,
                                 corner_radius=10)
            tcard.pack(fill="x", pady=(0, 10))
            tinner = ctk.CTkFrame(tcard, fg_color="transparent")
            tinner.pack(fill="x", padx=14, pady=12)

            head = ctk.CTkFrame(tinner, fg_color="transparent")
            head.pack(fill="x")
            dot = tk.Frame(head, bg=t["color"], width=10, height=10)
            dot.pack(side="left", padx=(0, 8))
            ctk.CTkLabel(head, text=t["name"],
                         font=ctk.CTkFont(FONT_FAM, 14, "bold"),
                         text_color=WHITE).pack(side="left")
            ctk.CTkLabel(head,
                         text="{:,} Damage · {} Mitglieder".format(t["damage"], len(t["members"])).replace(",", "."),
                         font=ctk.CTkFont(FONT_FAM, 11),
                         text_color=GRAY).pack(side="right")

            # Invite code field
            code_row = ctk.CTkFrame(tinner, fg_color="transparent")
            code_row.pack(fill="x", pady=(10, 0))
            code_entry = ctk.CTkEntry(code_row, font=ctk.CTkFont(FONT_FAM, 11),
                                      fg_color=BG, border_color=BDR,
                                      text_color=t["color"], height=32)
            code_entry.insert(0, t["invite_token"])
            code_entry.configure(state="readonly")
            code_entry.pack(side="left", fill="x", expand=True)
            ctk.CTkButton(code_row, text="Code", width=70, height=32,
                          font=ctk.CTkFont(FONT_FAM, 11, "bold"),
                          fg_color=t["color"], hover_color=t["color"],
                          text_color="#000",
                          command=lambda tok=t["invite_token"]: self._copy(tok)).pack(side="right", padx=(6, 0))

        # Buttons
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(btn_row, text="↻ Reset",
                      font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                      height=42, fg_color=BG3, hover_color=BDR,
                      text_color=RED, border_color=RED, border_width=1,
                      corner_radius=8, command=self._reset_event).pack(side="left", expand=True, fill="x", padx=(0,5))
        ctk.CTkButton(btn_row, text="🗑 Event loeschen",
                      font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                      height=42, fg_color=BG3, hover_color=BDR,
                      text_color=RED, border_color=RED, border_width=1,
                      corner_radius=8, command=self._delete_event).pack(side="left", expand=True, fill="x", padx=(5,0))

        ctk.CTkButton(body, text="🔄 Aktualisieren",
                      font=ctk.CTkFont(FONT_FAM, 11),
                      height=36, fg_color=BG2, hover_color=BG3,
                      text_color=GRAY, border_color=BDR, border_width=1,
                      corner_radius=6,
                      command=self.show_organizer_dashboard).pack(fill="x", pady=(14, 0))

    # ── Event-Wizard ──────────────────────────────────────────────────────────

    def _render_wizard(self, body):
        self._wizard_teams = [
            {"name": "Team Gold", "color": "#ffd700"},
            {"name": "Team Cyan", "color": "#03dac6"},
        ]
        self._wizard_mode = "coop"

        ctk.CTkLabel(body, text="Noch kein Event — leg eines an:",
                     font=ctk.CTkFont(FONT_FAM, 13, "bold"),
                     text_color=WHITE).pack(anchor="w", pady=(0, 14))

        # Name
        ctk.CTkLabel(body, text="EVENT-NAME",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self.w_name = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 13),
                                   placeholder_text="z.B. Mohjos Sommer-Cup",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=40,
                                   corner_radius=8)
        self.w_name.pack(fill="x", pady=(4, 14))

        # Goal
        ctk.CTkLabel(body, text="SCHADEN-ZIEL",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self.w_goal = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 13),
                                   placeholder_text="100000",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=40,
                                   corner_radius=8)
        self.w_goal.insert(0, "100000")
        self.w_goal.pack(fill="x", pady=(4, 14))

        # Mode
        ctk.CTkLabel(body, text="MODUS",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        mode_row = ctk.CTkFrame(body, fg_color="transparent")
        mode_row.pack(fill="x", pady=(4, 14))
        self._mode_btns = {}
        for m, lbl in [("coop", "Kooperativ"), ("versus", "Versus")]:
            b = ctk.CTkButton(mode_row, text=lbl,
                              font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                              height=44, corner_radius=8,
                              fg_color=BG2 if m != self._wizard_mode else ACCENT,
                              hover_color=BG3, text_color=WHITE if m != self._wizard_mode else "#000",
                              border_color=BDR, border_width=1,
                              command=lambda mm=m: self._set_mode(mm))
            b.pack(side="left", expand=True, fill="x", padx=4)
            self._mode_btns[m] = b

        # Teams
        ctk.CTkLabel(body, text="TEAMS (2-4)",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self._teams_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._teams_frame.pack(fill="x", pady=(4, 8))
        self._render_team_rows()

        self.w_add_team = ctk.CTkButton(body, text="+ Team hinzufuegen",
                                        font=ctk.CTkFont(FONT_FAM, 11),
                                        height=34, fg_color=BG2, hover_color=BG3,
                                        text_color=GRAY,
                                        border_color=BDR, border_width=1,
                                        corner_radius=6,
                                        command=self._add_team)
        self.w_add_team.pack(fill="x", pady=(0, 18))

        ctk.CTkButton(body, text="Event erstellen",
                      font=ctk.CTkFont(FONT_FAM, 14, "bold"),
                      height=48, fg_color=ACCENT, hover_color=ACCENT2,
                      text_color="#000", corner_radius=8,
                      command=self._submit_event).pack(fill="x")

        self.w_status = ctk.CTkLabel(body, text="",
                                     font=ctk.CTkFont(FONT_FAM, 11),
                                     text_color=GRAY, wraplength=420, justify="left")
        self.w_status.pack(anchor="w", pady=(10, 0))

    def _render_team_rows(self):
        for child in self._teams_frame.winfo_children():
            child.destroy()
        DEFAULTS = [("Team Gold","#ffd700"),("Team Cyan","#03dac6"),
                    ("Team Rot","#ff6b6b"),("Team Violett","#a78bfa")]
        for i, t in enumerate(self._wizard_teams):
            row = ctk.CTkFrame(self._teams_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            swatch = tk.Frame(row, bg=t["color"], width=28, height=28)
            swatch.pack(side="left", padx=(0,8))
            swatch.bind("<Button-1>", lambda e, idx=i: self._cycle_color(idx))
            e = ctk.CTkEntry(row, font=ctk.CTkFont(FONT_FAM, 12),
                             fg_color=BG2, border_color=BDR,
                             text_color=WHITE, height=34, corner_radius=6)
            e.insert(0, t["name"])
            e.bind("<KeyRelease>", lambda ev, idx=i, en=e: self._update_team_name(idx, en.get()))
            e.pack(side="left", fill="x", expand=True)
            if len(self._wizard_teams) > 2:
                ctk.CTkButton(row, text="✕", width=34, height=34,
                              font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                              fg_color=BG2, hover_color=BG3, text_color=RED,
                              border_color=BDR, border_width=1,
                              corner_radius=6,
                              command=lambda idx=i: self._remove_team(idx)).pack(side="left", padx=(6,0))

    def _set_mode(self, m):
        self._wizard_mode = m
        for k, b in self._mode_btns.items():
            b.configure(fg_color=ACCENT if k == m else BG2,
                        text_color="#000" if k == m else WHITE)

    def _cycle_color(self, i):
        colors = ["#ffd700","#03dac6","#ff6b6b","#a78bfa"]
        idx = colors.index(self._wizard_teams[i]["color"]) if self._wizard_teams[i]["color"] in colors else 0
        self._wizard_teams[i]["color"] = colors[(idx+1) % len(colors)]
        self._render_team_rows()

    def _update_team_name(self, i, name):
        self._wizard_teams[i]["name"] = name

    def _add_team(self):
        if len(self._wizard_teams) >= 4: return
        DEF = [("Team Gold","#ffd700"),("Team Cyan","#03dac6"),
               ("Team Rot","#ff6b6b"),("Team Violett","#a78bfa")]
        n, c = DEF[len(self._wizard_teams)]
        self._wizard_teams.append({"name": n, "color": c})
        self._render_team_rows()

    def _remove_team(self, i):
        if len(self._wizard_teams) <= 2: return
        self._wizard_teams.pop(i)
        self._render_team_rows()

    def _submit_event(self):
        name = self.w_name.get().strip() or "Mohjos DamageRace"
        try:
            goal = int(self.w_goal.get().strip() or "100000")
        except ValueError:
            goal = 100000
        payload = {"name": name, "goal": goal, "mode": self._wizard_mode,
                   "teams": self._wizard_teams}
        self.w_status.configure(text="Event wird erstellt…", text_color=GRAY)
        def _go():
            ok, data, cookies = http_json("POST", "/api/event", payload, self.cookies)
            if cookies: self.cookies.update(cookies)
            if ok and data.get("ok"):
                self.after(0, self.show_organizer_dashboard)
            else:
                err = data.get("error", "Fehler")
                self.after(0, lambda: self.w_status.configure(
                    text="Fehler: " + err, text_color=RED))
        threading.Thread(target=_go, daemon=True).start()

    def _reset_event(self):
        ok, data, cookies = http_json("POST", "/api/event/set",
                                       {"reset": True}, self.cookies)
        if cookies: self.cookies.update(cookies)
        self.show_organizer_dashboard()

    def _delete_event(self):
        ok, data, cookies = http_json("POST", "/api/event/delete",
                                       {}, self.cookies)
        if cookies: self.cookies.update(cookies)
        self.show_organizer_dashboard()

    def _logout(self):
        try:
            http_json("POST", "/auth/logout", {}, self.cookies)
        except Exception:
            pass
        self.cookies = {}
        self.user = None
        self.show_welcome()

    def _copy(self, text):
        if not text: return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

    # ── Teilnehmer ────────────────────────────────────────────────────────────

    def show_participant(self):
        self._clear()
        self._topbar(self, "An Event teilnehmen",
                     "Gib den Invite-Code von deinem Veranstalter ein",
                     back=self.show_welcome)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # Invite-Code
        ctk.CTkLabel(body, text="INVITE-CODE",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        ctk.CTkLabel(body, text="Vom Veranstalter erhalten (z.B. tm_AbCd1234)",
                     font=ctk.CTkFont(FONT_FAM, 10),
                     text_color=DIM).pack(anchor="w", pady=(2, 6))
        self.p_code = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 14),
                                   placeholder_text="tm_…",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=44,
                                   corner_radius=8)
        self.p_code.pack(fill="x", pady=(0, 18))

        # WoT-Name
        ctk.CTkLabel(body, text="DEIN WORLD-OF-TANKS NAME",
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        ctk.CTkLabel(body, text="Exakt wie im Spiel — Gross-/Kleinschreibung beachten",
                     font=ctk.CTkFont(FONT_FAM, 10),
                     text_color=DIM).pack(anchor="w", pady=(2, 6))
        self.p_name = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 14),
                                   placeholder_text="z.B. Mohjo_beist",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=44,
                                   corner_radius=8)
        self.p_name.pack(fill="x", pady=(0, 22))

        # WoT-Pfad
        self._wot_path = find_wot()
        wot_ok = os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe")) if self._wot_path else False
        version = find_version(self._wot_path) if wot_ok else None

        if wot_ok and version:
            icon, color, txt = "✓", GREEN, f"World of Tanks · Version {version}"
        elif wot_ok:
            icon, color, txt = "!", "#ff9800", "WoT gefunden, res_mods/ fehlt — bitte WoT einmal starten"
        else:
            icon, color, txt = "✕", RED, "World of Tanks nicht gefunden"

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 18))
        self.p_path_lbl = ctk.CTkLabel(row, text=f"{icon}  {txt}",
                                       font=ctk.CTkFont(FONT_FAM, 11),
                                       text_color=color)
        self.p_path_lbl.pack(side="left")
        ctk.CTkButton(row, text="Anderer Ordner", width=130, height=30,
                      font=ctk.CTkFont(FONT_FAM, 11),
                      fg_color=BG2, hover_color=BG3,
                      text_color=GRAY, border_color=BDR, border_width=1,
                      corner_radius=6,
                      command=self._browse_wot).pack(side="right")

        # Install-Button
        self.p_install = ctk.CTkButton(body,
                                       text="Beitreten und Mod installieren",
                                       font=ctk.CTkFont(FONT_FAM, 14, "bold"),
                                       height=50, fg_color=ACCENT, hover_color=ACCENT2,
                                       text_color="#000", corner_radius=8,
                                       command=self._do_install)
        self.p_install.pack(fill="x")

        self.p_status = ctk.CTkLabel(body, text="",
                                     font=ctk.CTkFont(FONT_FAM, 12),
                                     text_color=GRAY, wraplength=420, justify="left")
        self.p_status.pack(anchor="w", pady=(16, 0))

    def _browse_wot(self):
        p = filedialog.askdirectory(title="World of Tanks Ordner waehlen")
        if not p: return
        self._wot_path = p
        ok = os.path.isfile(os.path.join(p, "WorldOfTanks.exe"))
        v = find_version(p) if ok else None
        if ok and v:
            self.p_path_lbl.configure(text=f"✓  World of Tanks · Version {v}", text_color=GREEN)
        elif ok:
            self.p_path_lbl.configure(text="!  res_mods/ fehlt — WoT einmal starten", text_color="#ff9800")
        else:
            self.p_path_lbl.configure(text="✕  WorldOfTanks.exe nicht gefunden", text_color=RED)

    def _do_install(self):
        code = self.p_code.get().strip()
        name = self.p_name.get().strip()
        if not code or not name:
            self.p_status.configure(text="Bitte Invite-Code UND WoT-Name eingeben.",
                                    text_color="#ff9800")
            return
        if not self._wot_path or not os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe")):
            self.p_status.configure(text="WoT-Ordner fehlt.", text_color=RED)
            return
        self.p_install.configure(state="disabled", text="Verbinde mit Server…")
        self.p_status.configure(text="", text_color=GRAY)

        def _run():
            ok, data, _ = http_json("POST", "/api/join",
                                    {"token": code, "wot_name": name})
            if not ok or not data.get("ok"):
                err = data.get("error", "Beitritt fehlgeschlagen")
                self.after(0, lambda: self._after_install(False, err))
                return
            token = data["streamer_token"]
            event = data.get("event", {})
            team  = data.get("team")
            self.after(0, lambda: self.p_install.configure(text="Installiere Mod…"))
            inst_ok, msg = install_mod(self._wot_path, name, token)
            if inst_ok:
                team_str = f" · Team: {team['name']}" if team else ""
                self.after(0, lambda: self._after_install(
                    True, f"Beigetreten zu \"{event.get('name','?')}\"{team_str}\n"
                          f"Mod installiert (WoT {msg})\n\nStart WoT neu — fertig!"))
            else:
                self.after(0, lambda: self._after_install(False, msg))

        threading.Thread(target=_run, daemon=True).start()

    def _after_install(self, ok, msg):
        self.p_install.configure(state="normal",
                                 text="Erledigt ✓" if ok else "Beitreten und Mod installieren")
        if ok:
            self.p_install.configure(fg_color=BG2, text_color=GREEN, state="disabled")
            self.p_status.configure(text="✓  " + msg, text_color=GREEN)
        else:
            self.p_status.configure(text="✕  " + msg, text_color=RED)


if __name__ == "__main__":
    App().mainloop()
