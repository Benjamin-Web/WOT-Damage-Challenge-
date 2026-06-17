<div align="center">

# Mohjos DamageRace
### World of Tanks — Community Damage Race Tracker

[![WoT Mod](https://img.shields.io/badge/WoT-Mod-FFD700)](https://wgmods.net)
[![Docker](https://img.shields.io/badge/Server-Docker%20ready-1e1e28?logo=docker)](https://hub.docker.com)
[![by Mohjo_beist](https://img.shields.io/badge/by-Mohjo__beist-FFD700)](https://github.com/Benjamin-Web)

**🇩🇪 Deutsch** · [🇬🇧 English](README.en.md)

**Streamer-Wettkampf, automatisch.**
Events, Teams, Einladungslinks — komplett in der DamageRace.exe steuerbar, kein Browser nötig.

</div>

---

## Was ist DamageRace?

DamageRace ist ein von **Mohjo_beist** entwickeltes Setup für World-of-Tanks-Community-Events. Mehrere Streamer treten in Teams gegeneinander an (Versus) oder kooperieren auf ein gemeinsames Schadensziel (Coop). Damage wird live gemessen, Counter im OBS-Overlay laufen synchron auf allen Streams.

**Drei Säulen:**
- **WoT-Mod** — misst den eigenen Schaden + Assist automatisch und sendet ihn an den Server
- **DamageRace.exe** — eingebettetes Admin-Dashboard (Veranstalter) bzw. Ein-Klick-Mod-Installer (Streamer)
- **OBS-Overlay** — zeigt Gesamt- und Team-Counter live, Glasmorphismus-Design

---

## Features

- 🏁 **Event-Wizard** — Name, Ziel, 2–4 Teams, Coop oder Versus
- ✏️ **Live-Event-Editing** — Modus umschalten, Teams hinzufügen/entfernen/umbenennen, Ziel anpassen — **ohne Re-Invite und ohne Mod-Reinstall**
- 🔗 **Invite-Links** — pro Event und pro Team, mit einem Klick kopieren
- 🖱 **Drag & Drop Roster** — Streamer per Drag & Drop zwischen Teams verschieben
- 🎯 **Team-Modi** — Coop (gemeinsames Ziel) oder Versus (jedes Team rennt eigenständig aufs Ziel)
- 📊 **Live-Overlay** — Team-Farben, Fortschrittsbalken, Glow-Flash bei Damage; im Versus-Modus zeigt es den Rest des führenden Teams
- 🔐 **Twitch-Login** — Admin-Dashboard per Twitch-OAuth, jeder Veranstalter hat sein eigenes Event
- 🧮 **Faire Damage-Erkennung** — nur der **eigene** Direkt-Schaden zählt (Teammate-/Arty-Treffer am selben Ziel werden nicht mitgezählt), Assist-Schaden wird am Gefechtsende dazugerechnet
- 🔄 **Idempotenz** — Doppelzählung ausgeschlossen, Retry bei Netzwerkfehler
- ⚙ **Ein-Klick-Mod-Install** — Streamer geben nur ihren WoT-Namen ein, die .wotmod + config.json werden automatisch installiert
- ⬆️ **Auto-Update** — die EXE prüft GitHub-Releases und aktualisiert sich selbst
- 🎥 **OBS-WebSocket** — Browser-Source per Klick aus dem Dashboard in OBS einrichten
- 💬 **Discord-Recap** — Webhook postet nach Event-Ende ein Embed mit Gewinner-Team, Top-Streamern und Standings
- 🤖 **Heist-Bot-Synergy** — der Heist Bot kann Milestone-Ansagen (10/25/50/75/100 %) im Twitch-Chat posten

---

## So funktioniert's

```
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┐
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┤──►  [Server (Docker/VPS)]  ──►  [OBS-Overlay aller Streamer]
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┘            ▲
                                                              │
                                          [DamageRace.exe — eingebettetes Admin-Dashboard]
```

**Workflow:**
1. **Veranstalter** öffnet `DamageRace.exe` → „Veranstalter" → loggt sich mit Twitch ein.
2. **Veranstalter** erstellt im Dashboard ein Event mit Teams und kopiert die Team-Invite-Links.
3. **Streamer** öffnet `DamageRace.exe`, fügt den Invite-Link ein, gibt seinen WoT-Namen ein → Mod wird automatisch installiert.
4. **OBS** lädt die Overlay-URL als Browser-Source (oder per „In OBS hinzufügen"-Button).
5. Spiel läuft — Damage wird automatisch gezählt und live sichtbar.
6. Nach dem Event: optionaler Discord-Recap-Post.

> **Während des Events** kann der Veranstalter Modus, Teams und Ziel jederzeit ändern — die Streamer müssen nichts neu installieren, ihr Token bleibt gültig.

---

## Setup

### Server (für den Veranstalter / Self-Hosting)

```bash
git clone https://github.com/Benjamin-Web/WOT-Damage-Challenge-.git
cd WOT-Damage-Challenge-
```

`docker-compose.yml` editieren — Twitch-Client-Secret setzen (für den OAuth-Code-Flow):
```yaml
environment:
  PUBLIC_BASE_URL: "https://deine-domain"
  TWITCH_CLIENT_SECRET: "dein-secret-aus-der-twitch-dev-console"
```

```bash
docker compose up -d
```

Die `overlay/`- und `server/`-Ordner sind als Read-only-Volumes gemountet — Frontend-/Server-Änderungen landen mit `git pull && docker compose restart`, ein Image-Rebuild ist nur bei `requirements.txt`/`Dockerfile`-Änderungen nötig.

Admin-Dashboard: `https://<deine-domain>/admin` (Login per Twitch).

### Mod- & EXE-Build (einmalig)

Voraussetzung: **Python 2.7** (für den WoT-kompatiblen `.wotmod`-Bytecode) und **Python 3.12** + PyInstaller (für die EXE).

```bash
C:\Python27\python.exe mod\build_wotmod.py   # erzeugt dist/mohjos_damagerace.wotmod
py -3.12 build_exe.py                        # erzeugt dist/DamageRace.exe
```

> `build_exe.py` bündelt die in `dist/` liegende `.wotmod` — die `.wotmod` also **immer zuerst** bauen, sonst landet die alte Mod-Version in der EXE.

### Release veröffentlichen

```bash
gh release create v1.0.1 dist/DamageRace.exe --title "v1.0.1" --notes "..."
```

Das Asset muss exakt `DamageRace.exe` heißen — der Auto-Updater sucht danach.

### Streamer

1. `DamageRace.exe` herunterladen und starten.
2. Invite-Link einfügen, WoT-Namen eingeben → Mod wird automatisch installiert.
3. World of Tanks starten — Damage wird automatisch gezählt.

---

## Architektur

- `mod/` — WoT-Mod (Python 2.7, BigWorld-API). Hooks: `PlayerAvatar.showShotResults` (eigene Schüsse merken), `Vehicle.onHealthChanged` (HP-Deltas → Direkt-Schaden), Battle-Feedback-Bus (`PLAYER_ASSIST_TO_KILL_ENEMY` → Assist-Schaden).
- `server/` — Flask + SQLite (`db.py`), Twitch-OAuth, UUID-Idempotenz, `/status/<slug>`-Public-Read-Endpoint, Discord-Recap (`discord_recap.py`).
- `overlay/` — Login, Admin-Dashboard, Overlay, Join-Page (alle Vanilla JS), `i18n.js` (5 Sprachen).
- `installer_gui.py` — CustomTkinter-Welcome-Screen + eingebettetes Admin-Dashboard via pywebview (WebView2).
- `installer/` — `bridge.py` (JS↔Python-Bridge: Mod-Install, OBS-WebSocket), `updater.py` (GitHub-Auto-Update).
- `build_exe.py` / `mod/build_wotmod.py` — Build-Skripte.
- `Dockerfile` + `docker-compose.yml` — VPS-Deployment.

---

## Tech

| Komponente | Stack |
|---|---|
| WoT-Mod | Python 2.7, BigWorld API |
| Server | Python 3, Flask, SQLite, Twitch OAuth |
| Frontend | Vanilla JS, Inter Font, i18n (DE/EN/ES/RU/ZH) |
| Desktop-Client | CustomTkinter + pywebview (WebView2), PyInstaller (onefile) |
| Integrationen | OBS-WebSocket (obsws-python), Discord-Webhook, GitHub-Releases-API |
| Deployment | Docker, docker-compose, Caddy |

---

## Datenschutz & Netzwerk

Der WoT-Mod sendet während eines Events **nur deinen eigenen Schaden** (Direkt + Assist) per HTTPS an den Event-Server — keine Gegnerdaten, keine Account-Daten. Übertragung ist freiwillig (nur mit Token) und per `"enabled": false` abschaltbar. Volle Offenlegung: **[PRIVACY.md](PRIVACY.md)**.

---

<div align="center">

Made by **Mohjo_beist** · Twitch Streamer Community Project

</div>
