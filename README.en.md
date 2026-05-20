<div align="center">

# Mohjos DamageRace
### World of Tanks — Community Damage Race Tracker

[![WoT Mod](https://img.shields.io/badge/WoT-Mod-FFD700)](https://wgmods.net)
[![Docker](https://img.shields.io/badge/Server-Docker%20ready-1e1e28?logo=docker)](https://hub.docker.com)
[![by Mohjo_beist](https://img.shields.io/badge/by-Mohjo__beist-FFD700)](https://github.com/Benjamin-Web)

[🇩🇪 Deutsch](README.md) · **🇬🇧 English**

**Automated streamer competition.**
Events, teams, invite links — fully controlled from DamageRace.exe, no browser needed.

</div>

---

## What is DamageRace?

DamageRace is a setup built by **Mohjo_beist** for World of Tanks community events. Multiple streamers compete in teams against each other (Versus) or cooperate towards a shared damage goal (Coop). Damage is measured live, and counters in the OBS overlay stay in sync across every stream.

**Three pillars:**
- **WoT mod** — automatically measures your own damage + assist and sends it to the server
- **DamageRace.exe** — embedded admin dashboard (organizer) or one-click mod installer (streamer)
- **OBS overlay** — shows global and per-team counters live, glassmorphism design

---

## Features

- 🏁 **Event wizard** — name, goal, 2–4 teams, Coop or Versus
- ✏️ **Live event editing** — switch mode, add/remove/rename teams, adjust the goal — **without re-inviting anyone and without a mod reinstall**
- 🔗 **Invite links** — per event and per team, copy with one click
- 🖱 **Drag & drop roster** — move streamers between teams by drag & drop
- 🎯 **Team modes** — Coop (shared goal) or Versus (each team races to the goal independently)
- 📊 **Live overlay** — team colors, progress bars, glow flash on damage; in Versus mode it shows the leading team's remaining damage
- 🔐 **Twitch login** — admin dashboard via Twitch OAuth, every organizer gets their own event
- 🧮 **Fair damage detection** — only your **own** direct damage counts (teammate/arty hits on the same target are not counted), assist damage is added at the end of the battle
- 🔄 **Idempotency** — double counting impossible, retry on network errors
- ⚙ **One-click mod install** — streamers just enter their WoT name, the .wotmod + config.json are installed automatically
- ⬆️ **Auto-update** — the EXE checks GitHub releases and updates itself
- 🎥 **OBS WebSocket** — add the browser source to OBS with one click from the dashboard
- 💬 **Discord recap** — a webhook posts an embed with the winning team, top streamers and standings after the event ends
- 🤖 **Heist Bot synergy** — the Heist Bot can post milestone announcements (10/25/50/75/100%) in Twitch chat

---

## How it works

```
[Streamer PC: WoT + mohjos_damagerace.wotmod]  ──┐
[Streamer PC: WoT + mohjos_damagerace.wotmod]  ──┤──►  [Server (Docker/VPS)]  ──►  [OBS overlay on every stream]
[Streamer PC: WoT + mohjos_damagerace.wotmod]  ──┘            ▲
                                                              │
                                          [DamageRace.exe — embedded admin dashboard]
```

**Workflow:**
1. The **organizer** opens `DamageRace.exe` → "Organizer" → logs in with Twitch.
2. The **organizer** creates an event with teams in the dashboard and copies the team invite links.
3. A **streamer** opens `DamageRace.exe`, pastes the invite link, enters their WoT name → the mod is installed automatically.
4. **OBS** loads the overlay URL as a browser source (or via the "Add to OBS" button).
5. The match runs — damage is counted automatically and shown live.
6. After the event: optional Discord recap post.

> **During the event** the organizer can change mode, teams and goal at any time — streamers don't need to reinstall anything, their token stays valid.

---

## Setup

### Server (for the organizer / self-hosting)

```bash
git clone https://github.com/Benjamin-Web/WOT-Damage-Challenge-.git
cd WOT-Damage-Challenge-
```

Edit `docker-compose.yml` — set the Twitch client secret (for the OAuth code flow):
```yaml
environment:
  PUBLIC_BASE_URL: "https://your-domain"
  TWITCH_CLIENT_SECRET: "your-secret-from-the-twitch-dev-console"
```

```bash
docker compose up -d
```

The `overlay/` and `server/` folders are mounted as read-only volumes — frontend/server changes land with `git pull && docker compose restart`; an image rebuild is only needed for `requirements.txt`/`Dockerfile` changes.

Admin dashboard: `https://<your-domain>/admin` (login via Twitch).

### Mod & EXE build (one-time)

Prerequisites: **Python 2.7** (for the WoT-compatible `.wotmod` bytecode) and **Python 3.12** + PyInstaller (for the EXE).

```bash
C:\Python27\python.exe mod\build_wotmod.py   # produces dist/mohjos_damagerace.wotmod
py -3.12 build_exe.py                        # produces dist/DamageRace.exe
```

> `build_exe.py` bundles the `.wotmod` found in `dist/` — always build the `.wotmod` **first**, otherwise the old mod version ends up in the EXE.

### Publishing a release

```bash
gh release create v1.0.1 dist/DamageRace.exe --title "v1.0.1" --notes "..."
```

The asset must be named exactly `DamageRace.exe` — the auto-updater looks for it.

### Streamers

1. Download and run `DamageRace.exe`.
2. Paste the invite link, enter your WoT name → the mod is installed automatically.
3. Start World of Tanks — damage is counted automatically.

---

## Architecture

- `mod/` — WoT mod (Python 2.7, BigWorld API). Hooks: `PlayerAvatar.showShotResults` (remember own shots), `Vehicle.onHealthChanged` (HP deltas → direct damage), battle feedback bus (`PLAYER_ASSIST_TO_KILL_ENEMY` → assist damage).
- `server/` — Flask + SQLite (`db.py`), Twitch OAuth, UUID idempotency, `/status/<slug>` public read endpoint, Discord recap (`discord_recap.py`).
- `overlay/` — login, admin dashboard, overlay, join page (all vanilla JS), `i18n.js` (5 languages).
- `installer_gui.py` — CustomTkinter welcome screen + embedded admin dashboard via pywebview (WebView2).
- `installer/` — `bridge.py` (JS↔Python bridge: mod install, OBS WebSocket), `updater.py` (GitHub auto-update).
- `build_exe.py` / `mod/build_wotmod.py` — build scripts.
- `Dockerfile` + `docker-compose.yml` — VPS deployment.

---

## Tech

| Component | Stack |
|---|---|
| WoT mod | Python 2.7, BigWorld API |
| Server | Python 3, Flask, SQLite, Twitch OAuth |
| Frontend | Vanilla JS, Inter font, i18n (DE/EN/ES/RU/ZH) |
| Desktop client | CustomTkinter + pywebview (WebView2), PyInstaller (onefile) |
| Integrations | OBS WebSocket (obsws-python), Discord webhook, GitHub Releases API |
| Deployment | Docker, docker-compose, Caddy |

---

<div align="center">

Made by **Mohjo_beist** · Twitch Streamer Community Project

</div>
