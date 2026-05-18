"""DamageRace desktop client.

Two flows live behind the welcome screen:

* Organizer — Twitch OAuth login -> event wizard / dashboard.
* Participant — Invite code -> WoT mod installation.

The application talks to the public DamageRace server via JSON HTTP. It also
detects the local World of Tanks installation through the registry and a
handful of common paths.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any

import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

try:
    import winreg  # type: ignore[import-not-found]
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("damagerace.client")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Brand tokens ──────────────────────────────────────────────────────────────

BG       = "#0d0d14"
BG2      = "#17171f"
BG3      = "#1e1e28"
BG4      = "#262631"
BDR      = "#2a2a35"
ACCENT   = "#ffd700"
ACCENT2  = "#efb700"
TWITCH   = "#9146ff"
TWITCH2  = "#7d2def"
KOFI     = "#ff5e5b"
KOFI2    = "#e84541"
KOFI_URL = "https://ko-fi.com/ronincannons"
GREEN    = "#00e676"
RED      = "#cf6679"
WARN     = "#ff9800"
WHITE    = "#f3f4f6"
GRAY     = "#9ca3af"
DIM      = "#6b7280"

FONT_FAM = "Inter"

# ── Configuration ─────────────────────────────────────────────────────────────

__version__ = "1.0.0"

DEFAULT_SERVER_URL = "https://mohjos-damagerace.duckdns.org"
SETTINGS_FILE = "damagerace_settings.json"
GITHUB_REPO = "Benjamin-Web/WOT-Damage-Challenge-"


def _resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _user_settings_path() -> str:
    home = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(home, "MohjosDamageRace")
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        folder = os.path.expanduser("~")
    return os.path.join(folder, SETTINGS_FILE)


def _load_installer_config() -> dict[str, Any]:
    try:
        with open(_resource_path("installer_config.json"), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"server_url": DEFAULT_SERVER_URL, "event_name": "Mohjos DamageRace"}


def _load_user_settings() -> dict[str, Any]:
    try:
        with open(_user_settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_user_settings(data: dict[str, Any]) -> None:
    try:
        with open(_user_settings_path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError as exc:
        log.warning("Could not persist settings: %s", exc)


_CFG = _load_installer_config()
SERVER_URL = _CFG.get("server_url", DEFAULT_SERVER_URL).rstrip("/")
WOTMOD_SRC = _resource_path(os.path.join("dist", "mohjos_damagerace.wotmod"))

# ── i18n ──────────────────────────────────────────────────────────────────────

SUPPORTED_LANGS = ("de", "en")
DEFAULT_LANG = "de"

_MESSAGES: dict[str, dict[str, str]] = {
    "app.title":                {"de": "Mohjos DamageRace",
                                 "en": "Mohjos DamageRace"},
    "app.subtitle":             {"de": "World of Tanks Community Damage Race",
                                 "en": "World of Tanks Community Damage Race"},
    "welcome.prompt":           {"de": "WOFUER MOECHTEST DU ES NUTZEN?",
                                 "en": "WHAT DO YOU WANT TO DO?"},
    "welcome.organizer_title":  {"de": "Event veranstalten",
                                 "en": "Host an event"},
    "welcome.organizer_desc":   {"de": "Du erstellst ein eigenes Event,\nkonfigurierst Teams und laedst Streamer ein.",
                                 "en": "Create your own event, configure\nteams and invite streamers."},
    "welcome.organizer_badge":  {"de": "Veranstalter", "en": "Organizer"},
    "welcome.participant_title":{"de": "An Event teilnehmen",
                                 "en": "Join an event"},
    "welcome.participant_desc": {"de": "Du hast einen Invite-Code von einem\nVeranstalter und willst mitmachen.",
                                 "en": "You have an invite code from an\norganizer and want to participate."},
    "welcome.participant_badge":{"de": "Streamer", "en": "Streamer"},
    "common.back":              {"de": "Zurueck", "en": "Back"},
    "common.cancel":            {"de": "Abbrechen", "en": "Cancel"},
    "common.copy":              {"de": "Kopieren", "en": "Copy"},
    "common.required":          {"de": "Pflicht", "en": "Required"},
    "common.refresh":           {"de": "Aktualisieren", "en": "Refresh"},
    "common.error":             {"de": "Fehler", "en": "Error"},
    "server.label":             {"de": "Server", "en": "Server"},
    "support.kofi":             {"de": "☕  Auf Ko-fi unterstuetzen",
                                 "en": "☕  Support on Ko-fi"},
    "support.note":             {"de": "Falls dir DamageRace gefaellt, hilf mit die Serverkosten zu decken — danke!",
                                 "en": "If you enjoy DamageRace, help cover the server costs — thanks!"},

    "login.title":              {"de": "Veranstalter-Login",
                                 "en": "Organizer login"},
    "login.subtitle":           {"de": "Mit Twitch anmelden, um Events zu erstellen",
                                 "en": "Sign in with Twitch to manage events"},
    "login.button":             {"de": "🟣  Mit Twitch anmelden",
                                 "en": "🟣  Sign in with Twitch"},
    "login.browser_hint":       {"de": "Browser geoeffnet — bitte mit Twitch anmelden…",
                                 "en": "Browser opened — please sign in on Twitch…"},
    "login.afterhint":          {"de": "Hinweis: Es oeffnet sich dein Browser. Nach erfolgreicher\nTwitch-Anmeldung kommst du automatisch hierher zurueck.",
                                 "en": "Note: Your browser opens. After signing in with\nTwitch you are returned to this window automatically."},
    "login.timeout":            {"de": "Login-Timeout. Bitte erneut versuchen.",
                                 "en": "Login timed out. Please try again."},

    "update.available_title":   {"de": "Update verfuegbar",
                                 "en": "Update available"},
    "update.available_body":    {"de": "Version {tag} ist verfuegbar (aktuell: {current}).\nJetzt installieren? Die App startet sich neu.",
                                 "en": "Version {tag} is available (current: {current}).\nInstall now? The app will restart."},
    "update.downloading":       {"de": "Update wird heruntergeladen…",
                                 "en": "Downloading update…"},
    "update.download_failed":   {"de": "Update fehlgeschlagen. Bitte spaeter erneut versuchen.",
                                 "en": "Update failed. Please try again later."},

    "organizer.window_title":   {"de": "DamageRace · Veranstalter",
                                 "en": "DamageRace · Organizer"},
    "organizer.webview_missing":{"de": "WebView2 fehlt. Bitte die Microsoft Edge WebView2 Runtime\ninstallieren (Suche: 'WebView2 Evergreen Standalone').\nFallback: Admin-Dashboard wird im Standard-Browser geoeffnet.",
                                 "en": "WebView2 runtime is missing. Please install the Microsoft\nEdge WebView2 Runtime ('WebView2 Evergreen Standalone').\nFalling back to the system browser."},

    "dash.title":               {"de": "Dein Event", "en": "Your event"},
    "dash.logged_in_as":        {"de": "Eingeloggt als {name}",
                                 "en": "Signed in as {name}"},
    "dash.mode_goal":           {"de": "Modus: {mode} · Ziel: {goal}",
                                 "en": "Mode: {mode} · Goal: {goal}"},
    "dash.mode.coop":           {"de": "Coop", "en": "Coop"},
    "dash.mode.versus":         {"de": "Versus", "en": "Versus"},
    "dash.stat.remaining":      {"de": "Restdamage", "en": "Remaining"},
    "dash.stat.dealt":          {"de": "Verursacht", "en": "Dealt"},
    "dash.obs_url":             {"de": "OBS BROWSER-SOURCE URL",
                                 "en": "OBS BROWSER SOURCE URL"},
    "dash.teams_section":       {"de": "TEAMS & EINLADUNGSLINKS",
                                 "en": "TEAMS & INVITE LINKS"},
    "dash.team.summary":        {"de": "{damage} Damage · {n} Mitglieder",
                                 "en": "{damage} damage · {n} members"},
    "dash.team.copy_code":      {"de": "Code", "en": "Code"},
    "dash.reset":               {"de": "↻ Reset", "en": "↻ Reset"},
    "dash.delete":              {"de": "🗑 Event loeschen",
                                 "en": "🗑 Delete event"},
    "dash.refresh":             {"de": "🔄 Aktualisieren",
                                 "en": "🔄 Refresh"},

    "wizard.heading":           {"de": "Noch kein Event — leg eines an:",
                                 "en": "No event yet — create one:"},
    "wizard.name":              {"de": "EVENT-NAME", "en": "EVENT NAME"},
    "wizard.name_hint":         {"de": "z.B. Mohjos Sommer-Cup",
                                 "en": "e.g. Mohjos Summer Cup"},
    "wizard.goal":              {"de": "SCHADEN-ZIEL", "en": "DAMAGE GOAL"},
    "wizard.mode":              {"de": "MODUS", "en": "MODE"},
    "wizard.mode_coop":         {"de": "Kooperativ", "en": "Cooperative"},
    "wizard.mode_versus":       {"de": "Versus", "en": "Versus"},
    "wizard.teams":             {"de": "TEAMS (2-4)", "en": "TEAMS (2-4)"},
    "wizard.add_team":          {"de": "+ Team hinzufuegen",
                                 "en": "+ Add team"},
    "wizard.submit":            {"de": "Event erstellen",
                                 "en": "Create event"},
    "wizard.creating":          {"de": "Event wird erstellt…",
                                 "en": "Creating event…"},
    "wizard.error":             {"de": "Fehler: {detail}",
                                 "en": "Error: {detail}"},

    "join.title":               {"de": "An Event teilnehmen",
                                 "en": "Join an event"},
    "join.subtitle":            {"de": "Gib den Einladungscode deines Veranstalters ein",
                                 "en": "Enter the invite code from your organizer"},
    "join.code_label":          {"de": "EINLADUNGSCODE",
                                 "en": "INVITE CODE"},
    "join.code_hint":           {"de": "Vom Veranstalter erhalten (z.B. tm_AbCd1234)",
                                 "en": "Received from the organizer (e.g. tm_AbCd1234)"},
    "join.wot_label":           {"de": "DEIN WORLD-OF-TANKS NAME",
                                 "en": "YOUR WORLD OF TANKS NAME"},
    "join.wot_hint":            {"de": "Exakt wie im Spiel — Gross-/Kleinschreibung beachten",
                                 "en": "Exactly as in-game — case-sensitive"},
    "join.wot_placeholder":     {"de": "z.B. Mohjo_beist", "en": "e.g. Mohjo_beist"},
    "join.detect.found":        {"de": "✓  World of Tanks · Version {version}",
                                 "en": "✓  World of Tanks · version {version}"},
    "join.detect.no_res_mods":  {"de": "!  WoT gefunden, res_mods/ fehlt — bitte WoT einmal starten",
                                 "en": "!  WoT found but res_mods/ missing — launch WoT once"},
    "join.detect.missing":      {"de": "✕  World of Tanks nicht gefunden",
                                 "en": "✕  World of Tanks not found"},
    "join.pick_folder":         {"de": "Anderen Ordner waehlen",
                                 "en": "Pick another folder"},
    "join.install_btn":         {"de": "Beitreten und Mod installieren",
                                 "en": "Join and install mod"},
    "join.connecting":          {"de": "Verbinde mit Server…",
                                 "en": "Connecting to server…"},
    "join.installing":          {"de": "Installiere Mod…",
                                 "en": "Installing mod…"},
    "join.need_fields":         {"de": "Bitte Einladungscode UND WoT-Name eingeben.",
                                 "en": "Please provide both an invite code and your WoT name."},
    "join.wot_missing":         {"de": "WoT-Ordner fehlt.",
                                 "en": "WoT folder not selected."},
    "join.success":             {"de": "Beigetreten zu \"{event}\"{team}\nMod installiert (WoT {version})\n\nStarte WoT neu — fertig!",
                                 "en": "Joined \"{event}\"{team}\nMod installed (WoT {version})\n\nRestart WoT — done!"},
    "join.success_team":        {"de": " · Team: {name}",
                                 "en": " · team: {name}"},
    "join.failed":              {"de": "Beitritt fehlgeschlagen",
                                 "en": "Could not join the event"},
    "join.done":                {"de": "Erledigt ✓",
                                 "en": "Done ✓"},

    "mod.error.no_exe":         {"de": "WorldOfTanks.exe nicht im Ordner.",
                                 "en": "WorldOfTanks.exe not found in folder."},
    "mod.error.no_resmods":     {"de": "Kein Versionsordner in res_mods/ gefunden.\nBitte WoT einmal starten.",
                                 "en": "No version folder in res_mods/.\nLaunch WoT once first."},
    "mod.error.write":          {"de": "Mod-Installation fehlgeschlagen: {detail}",
                                 "en": "Mod install failed: {detail}"},
}

_settings_cache = _load_user_settings()
_current_lang = _settings_cache.get("lang") if _settings_cache.get("lang") in SUPPORTED_LANGS else DEFAULT_LANG


def get_lang() -> str:
    return _current_lang


def set_lang(lang: str) -> None:
    global _current_lang
    if lang not in SUPPORTED_LANGS:
        return
    _current_lang = lang
    _settings_cache["lang"] = lang
    _save_user_settings(_settings_cache)


def t(key: str, **params: object) -> str:
    entry = _MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(_current_lang, entry.get(DEFAULT_LANG, key))
    if params:
        try:
            text = text.format(**params)
        except (KeyError, IndexError):
            pass
    return text


def fmt_int(value: int) -> str:
    sep = "," if _current_lang == "en" else "."
    return f"{int(value):,}".replace(",", sep)


# ── HTTP helper ───────────────────────────────────────────────────────────────

class HttpResult:
    __slots__ = ("ok", "data", "cookies")

    def __init__(self, ok: bool, data: dict[str, Any], cookies: dict[str, str]) -> None:
        self.ok = ok
        self.data = data
        self.cookies = cookies


def http_json(method: str, path: str, data: dict | None = None,
              cookies: dict | None = None, *, timeout: int = 15) -> HttpResult:
    url = SERVER_URL + path
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "MohjosDamageRace-Client/1.0",
        "Accept-Language": _current_lang,
    }
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
            new_cookies = dict(cookies or {})
            set_cookie = response.headers.get("Set-Cookie")
            if set_cookie:
                first = set_cookie.split(";", 1)[0]
                if "=" in first:
                    name, value = first.split("=", 1)
                    new_cookies[name.strip()] = value.strip()
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = {"raw": text}
            return HttpResult(True, payload, new_cookies)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
        except (json.JSONDecodeError, OSError):
            payload = {"error": f"HTTP {exc.code}"}
        return HttpResult(False, payload, cookies or {})
    except urllib.error.URLError as exc:
        return HttpResult(False, {"error": str(exc.reason)}, cookies or {})
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("Unexpected HTTP failure")
        return HttpResult(False, {"error": str(exc)}, cookies or {})


# ── World of Tanks detection ──────────────────────────────────────────────────

_REGISTRY_KEYS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}",
     "InstallLocation"),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\{1EAC1D02-C6AC-4FA6-9A44-96258C37C812}",
     "InstallLocation"),
]
_COMMON_PATHS = (
    r"C:\Games\World_of_Tanks",
    r"C:\Games\World_of_Tanks_EU",
    r"D:\Games\World_of_Tanks",
    r"C:\Program Files (x86)\World_of_Tanks",
)


def find_wot() -> str:
    if HAS_WINREG:
        for subkey, value_name in _REGISTRY_KEYS:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as key:
                    path, _ = winreg.QueryValueEx(key, value_name)
                    if path and os.path.isfile(os.path.join(path, "WorldOfTanks.exe")):
                        return path
            except (FileNotFoundError, OSError):
                pass
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam") as key:
                steam, _ = winreg.QueryValueEx(key, "InstallPath")
            candidate = os.path.join(steam, "steamapps", "common", "World of Tanks")
            if os.path.isfile(os.path.join(candidate, "WorldOfTanks.exe")):
                return candidate
        except (FileNotFoundError, OSError):
            pass
    for path in _COMMON_PATHS:
        if os.path.isfile(os.path.join(path, "WorldOfTanks.exe")):
            return path
    return ""


def find_version(wot_path: str) -> str | None:
    res_mods = os.path.join(wot_path, "res_mods")
    if not os.path.isdir(res_mods):
        return None
    try:
        versions = sorted(
            (d for d in os.listdir(res_mods)
             if os.path.isdir(os.path.join(res_mods, d)) and d[:1].isdigit()),
            reverse=True,
        )
    except OSError:
        return None
    return versions[0] if versions else None


def install_mod(wot_path: str, wot_name: str, streamer_token: str
                ) -> tuple[bool, str]:
    if not os.path.isfile(os.path.join(wot_path, "WorldOfTanks.exe")):
        return False, t("mod.error.no_exe")
    version = find_version(wot_path)
    if not version:
        return False, t("mod.error.no_resmods")
    try:
        # WoT only reliably loads .wotmod files placed in the version-specific
        # mods folder (mods/<version>/). The legacy top-level path works on
        # some clients but not on official WG/EU/NA installs.
        mods_dir = os.path.join(wot_path, "mods", version)
        os.makedirs(mods_dir, exist_ok=True)
        shutil.copy2(WOTMOD_SRC, os.path.join(mods_dir, "mohjos_damagerace.wotmod"))

        # Clean up any stray copy in the top-level mods/ folder from earlier
        # installs so WoT cannot load two competing versions.
        legacy = os.path.join(wot_path, "mods", "mohjos_damagerace.wotmod")
        if os.path.isfile(legacy):
            try:
                os.remove(legacy)
            except OSError:
                pass

        config_dir = os.path.join(wot_path, "res_mods", version, "mods", "damagerace")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "config.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "server_url":         SERVER_URL,
                "streamer_token":     streamer_token,
                "streamer_name":      wot_name,
                "enabled":            True,
                "send_interval_ms":   200,
                "allowed_arena_types": [1, 7],
            }, fh, indent=2)
    except OSError as exc:
        return False, t("mod.error.write", detail=str(exc))
    return True, version


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_logo(parent: tk.Misc, *, big: bool = False) -> tk.Frame:
    size = 56 if big else 32
    font_size = 28 if big else 16
    frame = tk.Frame(parent, bg=ACCENT, width=size, height=size)
    frame.pack_propagate(False)
    tk.Label(frame, text="M", bg=ACCENT, fg="#000",
             font=(FONT_FAM, font_size, "bold")
             ).place(relx=0.5, rely=0.5, anchor="center")
    return frame


# ── Main application ──────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(t("app.title"))
        self.geometry("520x680")
        self.minsize(520, 680)
        self.configure(fg_color=BG)
        self.cookies: dict[str, str] = {}
        self.user: dict[str, Any] | None = None
        self._wot_path = ""
        self._wizard_teams: list[dict[str, str]] = []
        self._wizard_mode = "coop"
        self._pending_update: dict[str, str] | None = None
        self._center()
        self.show_welcome()
        self._start_update_check()

    def _center(self) -> None:
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _make_lang_toggle(self, parent: tk.Misc) -> ctk.CTkFrame:
        container = ctk.CTkFrame(parent, fg_color="transparent")
        for code in SUPPORTED_LANGS:
            btn = ctk.CTkButton(
                container, text=code.upper(), width=36, height=24,
                font=ctk.CTkFont(FONT_FAM, 10, "bold"),
                fg_color=ACCENT if code == _current_lang else BG3,
                hover_color=BDR,
                text_color="#000" if code == _current_lang else GRAY,
                border_color=BDR, border_width=1, corner_radius=6,
                command=lambda c=code: self._switch_lang(c),
            )
            btn.pack(side="left", padx=1)
        return container

    def _switch_lang(self, code: str) -> None:
        if code == _current_lang:
            return
        set_lang(code)
        self.title(t("app.title"))
        # Re-render the current screen by re-calling the responsible method.
        # Each screen tracks itself by clearing and rebuilding; the simplest
        # approach is to call show_welcome / show_organizer_dashboard /
        # show_participant from the active code path. We hook the latest
        # screen factory below.
        renderer = getattr(self, "_active_screen", None)
        if callable(renderer):
            renderer()

    def _topbar(self, parent: tk.Misc, title_text: str, subtitle: str = "",
                back: Any = None) -> None:
        tk.Frame(parent, bg=ACCENT, height=3).pack(fill="x")
        bar = ctk.CTkFrame(parent, fg_color=BG2, corner_radius=0)
        bar.pack(fill="x")
        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=22, pady=(18, 18))

        if back:
            ctk.CTkButton(row, text="← " + t("common.back"), width=90, height=28,
                          font=ctk.CTkFont(FONT_FAM, 11),
                          fg_color=BG3, hover_color=BDR,
                          text_color=GRAY, border_color=BDR, border_width=1,
                          corner_radius=6, command=back).pack(side="left")
            tk.Frame(row, bg=BG2, width=14).pack(side="left")

        make_logo(row).pack(side="left", padx=(0, 12))
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col, text=title_text,
                     font=ctk.CTkFont(FONT_FAM, 18, "bold"),
                     text_color=ACCENT).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(col, text=subtitle,
                         font=ctk.CTkFont(FONT_FAM, 11),
                         text_color=GRAY).pack(anchor="w")

        self._make_lang_toggle(row).pack(side="right")

    # ── Update check ──────────────────────────────────────────────────────────

    def _start_update_check(self) -> None:
        try:
            from installer import updater
        except ImportError:
            return

        def _on_update_available(info: dict[str, str]) -> None:
            # Bounce onto the Tk thread.
            self.after(0, lambda: self._prompt_update(info))

        updater.check_in_background(GITHUB_REPO, __version__, _on_update_available)

    def _prompt_update(self, info: dict[str, str]) -> None:
        self._pending_update = info
        from tkinter import messagebox
        answer = messagebox.askyesno(
            t("update.available_title"),
            t("update.available_body", tag=info["tag"], current=__version__),
        )
        if not answer:
            return
        from installer import updater
        if not updater.apply_update(info["download_url"]):
            messagebox.showerror(
                t("update.available_title"),
                t("update.download_failed"),
            )
            return
        # apply_update spawned the replacement process; exit cleanly.
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    def _copy(self, text_value: str | None) -> None:
        if not text_value:
            return
        self.clipboard_clear()
        self.clipboard_append(text_value)
        self.update()

    # ── Welcome ───────────────────────────────────────────────────────────────

    def show_welcome(self) -> None:
        self._active_screen = self.show_welcome
        self._clear()
        tk.Frame(self, bg=ACCENT, height=3).pack(fill="x")

        # Top language toggle (fixed)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(14, 0))
        self._make_lang_toggle(top).pack(side="right")

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(20, 0))
        logo = tk.Frame(header, bg=ACCENT, width=72, height=72)
        logo.pack_propagate(False)
        logo.pack(pady=(0, 16))
        tk.Label(logo, text="M", bg=ACCENT, fg="#000",
                 font=(FONT_FAM, 36, "bold")
                 ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(header, text=t("app.title"),
                     font=ctk.CTkFont(FONT_FAM, 24, "bold"),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(header, text=t("app.subtitle"),
                     font=ctk.CTkFont(FONT_FAM, 12),
                     text_color=GRAY).pack(pady=(4, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=30)

        ctk.CTkLabel(body, text=t("welcome.prompt"),
                     font=ctk.CTkFont(FONT_FAM, 10, "bold"),
                     text_color=DIM).pack(anchor="w", pady=(0, 12))

        self._mode_card(body, t("welcome.organizer_title"),
                        t("welcome.organizer_desc"),
                        t("welcome.organizer_badge"),
                        ACCENT, self.show_organizer_login
                        ).pack(fill="x", pady=(0, 14))

        self._mode_card(body, t("welcome.participant_title"),
                        t("welcome.participant_desc"),
                        t("welcome.participant_badge"),
                        "#03dac6", self.show_participant
                        ).pack(fill="x")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=10)

        ctk.CTkButton(
            footer,
            text=t("support.kofi"),
            font=ctk.CTkFont(FONT_FAM, 11, "bold"),
            height=32,
            fg_color=KOFI, hover_color=KOFI2,
            text_color="#fff",
            corner_radius=8,
            width=200,
            command=lambda: webbrowser.open(KOFI_URL),
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            footer, text=t("support.note"),
            font=ctk.CTkFont(FONT_FAM, 10),
            text_color=DIM, wraplength=440, justify="center",
        ).pack()

        ctk.CTkLabel(
            footer, text=f"{t('server.label')}: {SERVER_URL}",
            font=ctk.CTkFont(FONT_FAM, 9),
            text_color=DIM,
        ).pack(pady=(8, 0))

    def _mode_card(self, parent: tk.Misc, title_text: str, desc: str,
                   badge: str, color: str, command: Any) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=BG2, border_color=BDR,
                             border_width=1, corner_radius=12, height=140)
        outer.pack_propagate(False)

        ctk.CTkLabel(outer, text=badge,
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=color, fg_color=BG3, corner_radius=99,
                     padx=10, pady=2).pack(anchor="w", padx=20, pady=(16, 6))
        ctk.CTkLabel(outer, text=title_text,
                     font=ctk.CTkFont(FONT_FAM, 17, "bold"),
                     text_color=WHITE).pack(anchor="w", padx=20)
        ctk.CTkLabel(outer, text=desc,
                     font=ctk.CTkFont(FONT_FAM, 12),
                     text_color=GRAY, justify="left"
                     ).pack(anchor="w", padx=20, pady=(4, 14))

        def hover_in(_event: tk.Event) -> None:
            outer.configure(fg_color=BG3, border_color=color)

        def hover_out(_event: tk.Event) -> None:
            outer.configure(fg_color=BG2, border_color=BDR)

        def trigger(_event: tk.Event) -> None:
            command()

        for widget in (outer, *outer.winfo_children()):
            widget.bind("<Button-1>", trigger)
            widget.bind("<Enter>", hover_in)
            widget.bind("<Leave>", hover_out)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass
        return outer

    # ── Organizer entry (embedded admin dashboard) ────────────────────────────

    def show_organizer_login(self) -> None:
        """Launch the embedded admin dashboard.

        The whole organizer flow (Twitch OAuth + event management) now lives
        in the web admin UI loaded inside a pywebview window — no separate
        browser, no CTk dashboard. The old `show_organizer_dashboard` code
        is kept below for now in case we need to fall back to it; nothing
        calls it anymore.
        """
        # Set a flag that the bootstrap at the bottom of the file picks up
        # after Tk's mainloop exits. pywebview must own the main thread, so
        # we tear down Tk first and start the WebView from a clean context.
        self.launch_admin_webview = True
        try:
            self.withdraw()
        except Exception:
            pass
        self.quit()

    def _start_twitch_login(self) -> None:
        self._status_label.configure(text=t("login.browser_hint"), text_color=GRAY)
        # Allocate a server-side session and capture its sid so the browser
        # OAuth flow can attach the user to the very same session the client
        # is polling on.
        result = http_json("GET", "/auth/me")
        if result.cookies:
            self.cookies.update(result.cookies)
        sid = result.data.get("sid") if result.ok else None
        sid = sid or self.cookies.get("damagerace_sid", "")
        if not sid:
            self._status_label.configure(
                text=t("login.timeout"), text_color=RED,
            )
            return
        webbrowser.open(
            SERVER_URL + "/auth/twitch/start?sid=" + urllib.parse.quote(sid),
        )
        threading.Thread(target=self._poll_login, daemon=True).start()

    def _poll_login(self) -> None:
        for _ in range(120):  # ~4 minutes
            time.sleep(2)
            result = http_json("GET", "/auth/me", cookies=self.cookies)
            if result.cookies:
                self.cookies.update(result.cookies)
            if result.ok and result.data.get("authenticated"):
                self.user = result.data.get("user")
                log.info("Organizer authenticated: %s",
                         self.user.get("display_name") if self.user else "?")
                self.after(0, self.show_organizer_dashboard)
                return
        self.after(0, lambda: self._status_label.configure(
            text=t("login.timeout"), text_color=RED))

    # ── Organizer dashboard ───────────────────────────────────────────────────

    def show_organizer_dashboard(self) -> None:
        self._active_screen = self.show_organizer_dashboard
        self._clear()
        display_name = (self.user or {}).get("display_name", "?")
        self._topbar(self, t("dash.title"),
                     t("dash.logged_in_as", name=display_name),
                     back=self._logout)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        result = http_json("GET", "/api/my-event", cookies=self.cookies)
        if result.cookies:
            self.cookies.update(result.cookies)

        if not result.ok or not result.data.get("authenticated"):
            self._logout()
            return

        if not result.data.get("event"):
            self._render_wizard(body)
            return

        self._render_event_status(body, result.data)

    def _render_event_status(self, body: ctk.CTkScrollableFrame,
                             data: dict[str, Any]) -> None:
        event = data["event"]
        teams = data.get("teams", [])

        card = ctk.CTkFrame(body, fg_color=BG2, border_color=BDR,
                            border_width=1, corner_radius=12)
        card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(inner, text=event["name"],
                     font=ctk.CTkFont(FONT_FAM, 18, "bold"),
                     text_color=WHITE).pack(anchor="w")
        mode_key = "dash.mode.versus" if event["mode"] == "versus" else "dash.mode.coop"
        ctk.CTkLabel(inner,
                     text=t("dash.mode_goal",
                            mode=t(mode_key), goal=fmt_int(event["goal"])),
                     font=ctk.CTkFont(FONT_FAM, 11),
                     text_color=GRAY).pack(anchor="w", pady=(2, 0))

        stat_row = ctk.CTkFrame(inner, fg_color="transparent")
        stat_row.pack(fill="x", pady=(14, 0))
        for label_key, value, color in (
            ("dash.stat.remaining", event["remaining"], ACCENT),
            ("dash.stat.dealt",     event["total_dealt"], GREEN),
        ):
            cell = ctk.CTkFrame(stat_row, fg_color=BG3, corner_radius=8)
            cell.pack(side="left", expand=True, fill="x", padx=4)
            ctk.CTkLabel(cell, text=t(label_key).upper(),
                         font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                         text_color=GRAY).pack(pady=(10, 0))
            ctk.CTkLabel(cell, text=fmt_int(value),
                         font=ctk.CTkFont(FONT_FAM, 20, "bold"),
                         text_color=color).pack(pady=(2, 12))

        overlay = ctk.CTkFrame(body, fg_color=BG2, corner_radius=10)
        overlay.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(overlay, text=t("dash.obs_url"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w", padx=14, pady=(12, 4))
        url_row = ctk.CTkFrame(overlay, fg_color="transparent")
        url_row.pack(fill="x", padx=14, pady=(0, 12))
        url_entry = ctk.CTkEntry(url_row, font=ctk.CTkFont(FONT_FAM, 11),
                                 fg_color=BG, border_color=BDR,
                                 text_color=ACCENT, height=32)
        url_entry.insert(0, event.get("overlay_url") or "")
        url_entry.configure(state="readonly")
        url_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(url_row, text=t("common.copy"), width=90, height=32,
                      font=ctk.CTkFont(FONT_FAM, 11, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT2, text_color="#000",
                      command=lambda url=event.get("overlay_url"): self._copy(url)
                      ).pack(side="right", padx=(8, 0))

        ctk.CTkLabel(body, text=t("dash.teams_section"),
                     font=ctk.CTkFont(FONT_FAM, 10, "bold"),
                     text_color=GRAY).pack(anchor="w", pady=(8, 8))

        for team in teams:
            self._render_team_card(body, team)

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(buttons, text=t("dash.reset"),
                      font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                      height=42, fg_color=BG3, hover_color=BDR,
                      text_color=RED, border_color=RED, border_width=1,
                      corner_radius=8, command=self._reset_event
                      ).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(buttons, text=t("dash.delete"),
                      font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                      height=42, fg_color=BG3, hover_color=BDR,
                      text_color=RED, border_color=RED, border_width=1,
                      corner_radius=8, command=self._delete_event
                      ).pack(side="left", expand=True, fill="x", padx=(5, 0))

        ctk.CTkButton(body, text=t("dash.refresh"),
                      font=ctk.CTkFont(FONT_FAM, 11),
                      height=36, fg_color=BG2, hover_color=BG3,
                      text_color=GRAY, border_color=BDR, border_width=1,
                      corner_radius=6,
                      command=self.show_organizer_dashboard
                      ).pack(fill="x", pady=(14, 0))

    def _render_team_card(self, body: tk.Misc, team: dict[str, Any]) -> None:
        card = ctk.CTkFrame(body, fg_color=BG2, border_color=BDR,
                            border_width=1, corner_radius=10)
        card.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x")
        tk.Frame(head, bg=team["color"], width=10, height=10).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(head, text=team["name"],
                     font=ctk.CTkFont(FONT_FAM, 14, "bold"),
                     text_color=WHITE).pack(side="left")
        ctk.CTkLabel(head,
                     text=t("dash.team.summary",
                            damage=fmt_int(team["damage"]),
                            n=len(team["members"])),
                     font=ctk.CTkFont(FONT_FAM, 11),
                     text_color=GRAY).pack(side="right")

        code_row = ctk.CTkFrame(inner, fg_color="transparent")
        code_row.pack(fill="x", pady=(10, 0))
        code_entry = ctk.CTkEntry(code_row, font=ctk.CTkFont(FONT_FAM, 11),
                                  fg_color=BG, border_color=BDR,
                                  text_color=team["color"], height=32)
        code_entry.insert(0, team["invite_token"])
        code_entry.configure(state="readonly")
        code_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(code_row, text=t("dash.team.copy_code"), width=70, height=32,
                      font=ctk.CTkFont(FONT_FAM, 11, "bold"),
                      fg_color=team["color"], hover_color=team["color"],
                      text_color="#000",
                      command=lambda token=team["invite_token"]: self._copy(token)
                      ).pack(side="right", padx=(6, 0))

    # ── Event wizard ──────────────────────────────────────────────────────────

    def _render_wizard(self, body: tk.Misc) -> None:
        names = self._default_team_names()
        self._wizard_teams = [
            {"name": names[0], "color": "#ffd700"},
            {"name": names[1], "color": "#03dac6"},
        ]
        self._wizard_mode = "coop"

        ctk.CTkLabel(body, text=t("wizard.heading"),
                     font=ctk.CTkFont(FONT_FAM, 13, "bold"),
                     text_color=WHITE).pack(anchor="w", pady=(0, 14))

        ctk.CTkLabel(body, text=t("wizard.name"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self.w_name = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 13),
                                   placeholder_text=t("wizard.name_hint"),
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=40, corner_radius=8)
        self.w_name.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(body, text=t("wizard.goal"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self.w_goal = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 13),
                                   placeholder_text="100000",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=40, corner_radius=8)
        self.w_goal.insert(0, "100000")
        self.w_goal.pack(fill="x", pady=(4, 14))

        ctk.CTkLabel(body, text=t("wizard.mode"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        mode_row = ctk.CTkFrame(body, fg_color="transparent")
        mode_row.pack(fill="x", pady=(4, 14))
        self._mode_buttons = {}
        for code, key in (("coop", "wizard.mode_coop"),
                          ("versus", "wizard.mode_versus")):
            button = ctk.CTkButton(
                mode_row, text=t(key),
                font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                height=44, corner_radius=8,
                fg_color=BG2 if code != self._wizard_mode else ACCENT,
                hover_color=BG3,
                text_color=WHITE if code != self._wizard_mode else "#000",
                border_color=BDR, border_width=1,
                command=lambda c=code: self._set_mode(c),
            )
            button.pack(side="left", expand=True, fill="x", padx=4)
            self._mode_buttons[code] = button

        ctk.CTkLabel(body, text=t("wizard.teams"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        self._teams_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._teams_frame.pack(fill="x", pady=(4, 8))
        self._render_team_rows()

        self.w_add_team = ctk.CTkButton(body, text=t("wizard.add_team"),
                                        font=ctk.CTkFont(FONT_FAM, 11),
                                        height=34, fg_color=BG2, hover_color=BG3,
                                        text_color=GRAY,
                                        border_color=BDR, border_width=1,
                                        corner_radius=6,
                                        command=self._add_team)
        self.w_add_team.pack(fill="x", pady=(0, 18))

        ctk.CTkButton(body, text=t("wizard.submit"),
                      font=ctk.CTkFont(FONT_FAM, 14, "bold"),
                      height=48, fg_color=ACCENT, hover_color=ACCENT2,
                      text_color="#000", corner_radius=8,
                      command=self._submit_event).pack(fill="x")

        self.w_status = ctk.CTkLabel(body, text="",
                                     font=ctk.CTkFont(FONT_FAM, 11),
                                     text_color=GRAY,
                                     wraplength=420, justify="left")
        self.w_status.pack(anchor="w", pady=(10, 0))

    def _default_team_names(self) -> list[str]:
        if _current_lang == "en":
            return ["Team Gold", "Team Cyan", "Team Red", "Team Violet"]
        return ["Team Gold", "Team Cyan", "Team Rot", "Team Violett"]

    def _render_team_rows(self) -> None:
        for child in self._teams_frame.winfo_children():
            child.destroy()
        for index, team in enumerate(self._wizard_teams):
            row = ctk.CTkFrame(self._teams_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            swatch = tk.Frame(row, bg=team["color"], width=28, height=28)
            swatch.pack(side="left", padx=(0, 8))
            swatch.bind("<Button-1>", lambda _e, i=index: self._cycle_color(i))
            entry = ctk.CTkEntry(row, font=ctk.CTkFont(FONT_FAM, 12),
                                 fg_color=BG2, border_color=BDR,
                                 text_color=WHITE, height=34, corner_radius=6)
            entry.insert(0, team["name"])
            entry.bind(
                "<KeyRelease>",
                lambda _e, i=index, widget=entry: self._update_team_name(i, widget.get()),
            )
            entry.pack(side="left", fill="x", expand=True)
            if len(self._wizard_teams) > 2:
                ctk.CTkButton(row, text="✕", width=34, height=34,
                              font=ctk.CTkFont(FONT_FAM, 12, "bold"),
                              fg_color=BG2, hover_color=BG3, text_color=RED,
                              border_color=BDR, border_width=1,
                              corner_radius=6,
                              command=lambda i=index: self._remove_team(i)
                              ).pack(side="left", padx=(6, 0))

    def _set_mode(self, mode: str) -> None:
        self._wizard_mode = mode
        for code, button in self._mode_buttons.items():
            button.configure(
                fg_color=ACCENT if code == mode else BG2,
                text_color="#000" if code == mode else WHITE,
            )

    def _cycle_color(self, index: int) -> None:
        palette = ["#ffd700", "#03dac6", "#ff6b6b", "#a78bfa"]
        current = self._wizard_teams[index]["color"]
        idx = palette.index(current) if current in palette else 0
        self._wizard_teams[index]["color"] = palette[(idx + 1) % len(palette)]
        self._render_team_rows()

    def _update_team_name(self, index: int, name: str) -> None:
        self._wizard_teams[index]["name"] = name

    def _add_team(self) -> None:
        if len(self._wizard_teams) >= 4:
            return
        defaults = (("#ffd700"), ("#03dac6"), ("#ff6b6b"), ("#a78bfa"))
        names = self._default_team_names()
        self._wizard_teams.append({
            "name":  names[len(self._wizard_teams)],
            "color": defaults[len(self._wizard_teams)],
        })
        self._render_team_rows()

    def _remove_team(self, index: int) -> None:
        if len(self._wizard_teams) <= 2:
            return
        self._wizard_teams.pop(index)
        self._render_team_rows()

    def _submit_event(self) -> None:
        name = self.w_name.get().strip() or t("app.title")
        try:
            goal = int(self.w_goal.get().strip() or "100000")
        except ValueError:
            goal = 100000
        payload = {
            "name":  name,
            "goal":  goal,
            "mode":  self._wizard_mode,
            "teams": self._wizard_teams,
        }
        self.w_status.configure(text=t("wizard.creating"), text_color=GRAY)

        def run() -> None:
            result = http_json("POST", "/api/event", payload, self.cookies)
            if result.cookies:
                self.cookies.update(result.cookies)
            if result.ok and result.data.get("ok"):
                self.after(0, self.show_organizer_dashboard)
            else:
                detail = result.data.get("error", t("common.error"))
                self.after(0, lambda: self.w_status.configure(
                    text=t("wizard.error", detail=detail), text_color=RED))

        threading.Thread(target=run, daemon=True).start()

    def _reset_event(self) -> None:
        result = http_json("POST", "/api/event/set", {"reset": True}, self.cookies)
        if result.cookies:
            self.cookies.update(result.cookies)
        self.show_organizer_dashboard()

    def _delete_event(self) -> None:
        result = http_json("POST", "/api/event/delete", {}, self.cookies)
        if result.cookies:
            self.cookies.update(result.cookies)
        self.show_organizer_dashboard()

    def _logout(self) -> None:
        try:
            http_json("POST", "/auth/logout", {}, self.cookies)
        except Exception:
            log.debug("Logout request failed (ignored)", exc_info=True)
        self.cookies = {}
        self.user = None
        self.show_welcome()

    # ── Participant ───────────────────────────────────────────────────────────

    def show_participant(self) -> None:
        self._active_screen = self.show_participant
        self._clear()
        self._topbar(self, t("join.title"), t("join.subtitle"),
                     back=self.show_welcome)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(body, text=t("join.code_label"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        ctk.CTkLabel(body, text=t("join.code_hint"),
                     font=ctk.CTkFont(FONT_FAM, 10),
                     text_color=DIM).pack(anchor="w", pady=(2, 6))
        self.p_code = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 14),
                                   placeholder_text="tm_…",
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=44, corner_radius=8)
        self.p_code.pack(fill="x", pady=(0, 18))

        ctk.CTkLabel(body, text=t("join.wot_label"),
                     font=ctk.CTkFont(FONT_FAM, 9, "bold"),
                     text_color=GRAY).pack(anchor="w")
        ctk.CTkLabel(body, text=t("join.wot_hint"),
                     font=ctk.CTkFont(FONT_FAM, 10),
                     text_color=DIM).pack(anchor="w", pady=(2, 6))
        self.p_name = ctk.CTkEntry(body, font=ctk.CTkFont(FONT_FAM, 14),
                                   placeholder_text=t("join.wot_placeholder"),
                                   fg_color=BG2, border_color=BDR,
                                   text_color=WHITE, height=44, corner_radius=8)
        self.p_name.pack(fill="x", pady=(0, 22))

        self._wot_path = find_wot()
        version = find_version(self._wot_path) if self._wot_path else None
        wot_exists = bool(self._wot_path and
                          os.path.isfile(os.path.join(self._wot_path, "WorldOfTanks.exe")))

        if wot_exists and version:
            label_color, label_text = GREEN, t("join.detect.found", version=version)
        elif wot_exists:
            label_color, label_text = WARN, t("join.detect.no_res_mods")
        else:
            label_color, label_text = RED, t("join.detect.missing")

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(0, 18))
        self.p_path_label = ctk.CTkLabel(
            row, text=label_text,
            font=ctk.CTkFont(FONT_FAM, 11),
            text_color=label_color,
        )
        self.p_path_label.pack(side="left")
        ctk.CTkButton(row, text=t("join.pick_folder"), width=160, height=30,
                      font=ctk.CTkFont(FONT_FAM, 11),
                      fg_color=BG2, hover_color=BG3,
                      text_color=GRAY, border_color=BDR, border_width=1,
                      corner_radius=6, command=self._browse_wot
                      ).pack(side="right")

        self.p_install = ctk.CTkButton(
            body, text=t("join.install_btn"),
            font=ctk.CTkFont(FONT_FAM, 14, "bold"),
            height=50, fg_color=ACCENT, hover_color=ACCENT2,
            text_color="#000", corner_radius=8, command=self._do_install,
        )
        self.p_install.pack(fill="x")

        self.p_status = ctk.CTkLabel(
            body, text="",
            font=ctk.CTkFont(FONT_FAM, 12),
            text_color=GRAY, wraplength=420, justify="left",
        )
        self.p_status.pack(anchor="w", pady=(16, 0))

    def _browse_wot(self) -> None:
        path = filedialog.askdirectory(title="World of Tanks")
        if not path:
            return
        self._wot_path = path
        exists = os.path.isfile(os.path.join(path, "WorldOfTanks.exe"))
        version = find_version(path) if exists else None
        if exists and version:
            self.p_path_label.configure(
                text=t("join.detect.found", version=version), text_color=GREEN,
            )
        elif exists:
            self.p_path_label.configure(text=t("join.detect.no_res_mods"), text_color=WARN)
        else:
            self.p_path_label.configure(text=t("join.detect.missing"), text_color=RED)

    def _do_install(self) -> None:
        code = self.p_code.get().strip()
        name = self.p_name.get().strip()
        if not code or not name:
            self.p_status.configure(text=t("join.need_fields"), text_color=WARN)
            return
        if not self._wot_path or not os.path.isfile(
                os.path.join(self._wot_path, "WorldOfTanks.exe")):
            self.p_status.configure(text=t("join.wot_missing"), text_color=RED)
            return

        self.p_install.configure(state="disabled", text=t("join.connecting"))
        self.p_status.configure(text="", text_color=GRAY)

        def run() -> None:
            result = http_json("POST", "/api/join",
                               {"token": code, "wot_name": name})
            if not result.ok or not result.data.get("ok"):
                detail = result.data.get("error", t("join.failed"))
                self.after(0, lambda: self._after_install(False, detail))
                return

            token = result.data["streamer_token"]
            event = result.data.get("event", {})
            team = result.data.get("team")
            self.after(0, lambda: self.p_install.configure(text=t("join.installing")))
            ok, version_or_err = install_mod(self._wot_path, name, token)
            if ok:
                team_text = t("join.success_team", name=team["name"]) if team else ""
                message = t("join.success",
                            event=event.get("name", "?"),
                            team=team_text,
                            version=version_or_err)
                self.after(0, lambda: self._after_install(True, message))
            else:
                self.after(0, lambda: self._after_install(False, version_or_err))

        threading.Thread(target=run, daemon=True).start()

    def _after_install(self, ok: bool, message: str) -> None:
        if ok:
            self.p_install.configure(text=t("join.done"), state="disabled",
                                     fg_color=BG2, text_color=GREEN)
            self.p_status.configure(text="✓  " + message, text_color=GREEN)
        else:
            self.p_install.configure(state="normal", text=t("join.install_btn"))
            self.p_status.configure(text="✕  " + message, text_color=RED)


def _open_admin_webview() -> None:
    """Run the embedded admin dashboard. Blocks on the main thread."""
    try:
        import webview
    except ImportError:
        log.warning("pywebview not installed; falling back to system browser")
        webbrowser.open(SERVER_URL + "/admin")
        return

    # Wire up the JS-to-Python bridge so the dashboard can drive OBS, etc.
    try:
        from installer.bridge import WebviewBridge

        def _get(key: str) -> str | None:
            return _load_user_settings().get(key)

        def _set(key: str, value: str) -> None:
            data = _load_user_settings()
            data[key] = value
            _save_user_settings(data)

        bridge = WebviewBridge(settings_get=_get, settings_set=_set)
    except ImportError:
        bridge = None

    try:
        webview.create_window(
            t("organizer.window_title"),
            SERVER_URL + "/admin",
            width=1280, height=820,
            min_size=(960, 640),
            background_color=BG,
            js_api=bridge,
        )
        webview.start()
    except Exception as exc:
        log.exception("pywebview failed (%s); falling back to system browser", exc)
        webbrowser.open(SERVER_URL + "/admin")


if __name__ == "__main__":
    try:
        from installer.updater import handle_replace_flag
        handle_replace_flag()
    except ImportError:
        pass
    app = App()
    app.mainloop()
    if getattr(app, "launch_admin_webview", False):
        try:
            app.destroy()
        except Exception:
            pass
        _open_admin_webview()
