<div align="center">

# 🐾 BeastSync | Mohjo_beist
### World of Tanks — Community Damage Challenge Tracker

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![WoT Mod](https://img.shields.io/badge/WoT-Offizieller%20Mod-green)](https://wgmods.net)
[![Docker](https://img.shields.io/badge/Server-Docker%20ready-blue?logo=docker)](https://hub.docker.com)
[![Made by Mohjo_beist](https://img.shields.io/badge/by-Mohjo__beist-red)](https://github.com/Benjamin-Web)

**Kein manuelles Abziehen mehr.**
Jeder Streamer installiert einmal eine Exe — fertig.
Der Damage-Counter läuft von da an von selbst.

</div>

---

## Wer macht was?

| | Veranstalter (Mohjo_beist) | Streamer |
|---|---|---|
| **Einmalig** | Server auf VPS deployen, Exe bauen | `DamageChallenge-Install.exe` ausführen |
| **Pro Event** | Ziel + Streamer im Admin-Panel setzen | WoT starten und spielen |
| **Während Event** | Counter im Server-Fenster beobachten | Spielen |

---

## 📥 Für Streamer — So einfach geht's

> Du bekommst vom Veranstalter eine Datei: **`DamageChallenge-Install.exe`**

**1.** Doppelklick auf die Exe

**2.** Deinen World of Tanks Account-Namen eingeben

**3.** „Jetzt installieren" klicken

**4.** WoT neu starten — fertig ✅

Der Installer erkennt World of Tanks automatisch. Du musst nichts weiter wissen oder installieren. Kein Python, kein Config-File, nichts.

```
┌─────────────────────────────────────────────────────┐
│  🐾 BeastSync Setup — Mohjo_beist BeastSync         │
│─────────────────────────────────────────────────────│
│                                                     │
│  Dein World of Tanks Account-Name                   │
│  ┌───────────────────────────────────────────────┐  │
│  │  Mohjo_beist                                  │  │
│  └───────────────────────────────────────────────┘  │
│  ⚠  Groß-/Kleinschreibung beachten!                 │
│                                                     │
│  ─────────────────────────────────────────────────  │
│  ✅  WoT gefunden (Version 1.24.1.0)                │
│                                                     │
│                        [Jetzt installieren  →]      │
└─────────────────────────────────────────────────────┘
```

---

## 🖥️ Für den Veranstalter

### Schritt 1 — Server deployen (einmalig)

**Option A: VPS mit Docker** *(empfohlen — läuft immer)*

```bash
# Auf dem VPS (z.B. Hetzner, DigitalOcean, Netcup):
git clone https://github.com/Benjamin-Web/WOT-Damage-Challenge-.git
cd WOT-Damage-Challenge-

# server/config.py anpassen:
#   INITIAL_GOAL = 100000
#   ADMIN_SECRET = 'meinPasswort'
#   STREAMER_NAMES = []   # leer lassen — Streamer werden automatisch registriert

docker compose up -d
```

**Option B: Direkt mit Python**

```bash
pip install flask flask-cors
python server/server.py
```

---

### Schritt 2 — Installer-Exe bauen (einmalig pro Server-URL)

```bash
# 1. Server-URL eintragen:
#    installer_config.json öffnen → server_url auf deine VPS-IP setzen

# 2. WoT-Mod kompilieren (Python 2.7 nötig):
python2.7 mod/build_wotmod.py

# 3. Beide Exe-Dateien bauen:
pip install pyinstaller flask flask-cors
python build_exe.py
```

Ergebnis in `dist/`:
- **`DamageChallenge-Install.exe`** → an alle Streamer schicken
- **`DamageChallenge-Server.exe`** → optional, für lokalen Betrieb ohne Docker

---

### Schritt 3 — Event starten

Vor jedem Event das Admin-Panel öffnen: `http://DEINE-IP:5000/admin`

```
┌──────────────────────────────────────────────────────────────────┐
│  🐾 BeastSync Admin                   87.543 / 100.000 Damage   │
│──────────────────────────────────────────────────────────────────│
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ RESTDAMAGE  │  │    DEALT    │  │    ZIEL     │             │
│  │   12.457    │  │   87.543    │  │   100.000   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│  ████████████████████████░░░░░░░░░░░░░  87,5%                   │
│──────────────────────────────────────────────────────────────────│
│  Name            Damage    Zuletzt    Status                     │
│  Mohjo_beist     45.230    2s         ● Online                   │
│  Streamer2       28.100    18s        ● Online                   │
│  Streamer3       14.213    4min       ○ Offline                  │
│──────────────────────────────────────────────────────────────────│
│  [Streamer hinzufügen]  [Pause]  [Reset]  [Ziel setzen]         │
└──────────────────────────────────────────────────────────────────┘
```

**Streamer-Verwaltung live im Admin-Panel:**
- Neue Streamer können jederzeit per Knopfdruck hinzugefügt werden
- Unbekannte Streamer werden beim ersten Damage automatisch registriert — kein Vortippen nötig
- Einzelne Streamer können deaktiviert werden (z.B. bei technischen Problemen)

---

## 📺 OBS-Overlay einrichten (alle Streamer)

Die OBS-URL steht im Server-Fenster und im Admin-Panel.

**In OBS:**
1. Quelle hinzufügen → **Browser**
2. URL: `http://DEINE-SERVER-IP:5000/overlay`
3. Breite `300` · Höhe `80`
4. Custom CSS: `body { background: transparent !important; }`

Der Counter sieht auf allen Streams gleich aus und ist für alle synchron.

```
┌────────────────────────┐
│ RESTDAMAGE             │
│ 87.543                 │   ← Transparentes OBS-Overlay
└────────────────────────┘
```

---

## 🏗️ Architektur

```
  VPS / Server-PC
  ┌────────────────────────────────────────┐
  │  BeastSync Server (Flask, Port 5000)  │
  │                                        │
  │  GET /status   ◄── OBS Browser Source │◄──── alle Streamer-OBS
  │  POST /damage  ◄── WoT-Mod (je PC)    │
  │  GET /admin    ◄── Veranstalter       │
  └────────────────────────────────────────┘
          ▲                    ▲
          │                    │
  ┌───────────────┐    ┌───────────────┐
  │ Streamer 1    │    │ Streamer 2    │   ...
  │ WoT + Mod     │    │ WoT + Mod     │
  └───────────────┘    └───────────────┘
```

---

## 🛡️ WoT Regelkonformität

| Kriterium | Status |
|-----------|--------|
| Offizielles `.wotmod`-Format | ✅ |
| Offizielle BigWorld Python API | ✅ |
| Spielvorteil | ❌ Keiner |
| Liest fremde Spieler-Daten | ❌ Nein — nur eigener Damage |
| WoT Fair Play Policy | ✅ Erfüllt |

---

## 📁 Projektstruktur

```
WOT-Damage-Challenge-/
├── installer_config.json        ← Server-URL — VOR DEM EXE-BUILD ANPASSEN
├── installer_gui.py             ← Streamer-Installer (wird zu .exe)
├── server_gui.py                ← Server-GUI (wird zu .exe)
├── build_exe.py                 ← Baut beide .exe mit PyInstaller
├── Dockerfile                   ← VPS-Deployment
├── docker-compose.yml
│
├── mod/
│   ├── mod_mohjobeist_beastsync.py   ← WoT Python 2.7 Mod
│   ├── build_wotmod.py               ← Baut .wotmod Paket
│   └── config.example.json
│
├── server/
│   ├── server.py                ← Flask-Server + alle Endpunkte
│   ├── state.py                 ← Thread-sicherer Damage-Counter
│   └── config.py                ← Ziel, Streamer-Liste, Passwort
│
└── overlay/
    ├── index.html               ← OBS Browser Source
    └── admin.html               ← Admin-Panel
```

---

## 🔧 Technische Details

<details>
<summary><b>Wie der WoT-Mod Damage erkennt</b></summary>

Zwei Monkey-Patches auf `Avatar.PlayerAvatar`:

1. **`showShotResults`** — feuert wenn der eigene Schuss trifft → speichert Target-ID + HP-Snapshot
2. **`updateVehicleHealth`** — feuert bei HP-Änderung → `damage = old_hp - new_hp` wenn es das letzte Ziel war

HTTP-Versand über `BigWorld.fetchURL` (async, non-blocking). Bei Netzwerkfehler wird der Damage gepuffert und nach 5 Sekunden erneut gesendet. Jedes Paket hat eine UUID als Idempotency-Key — kein doppeltes Zählen bei Verbindungsabbrüchen.

</details>

<details>
<summary><b>Server-API</b></summary>

| Method | Endpoint | Beschreibung |
|--------|----------|--------------|
| `POST/GET` | `/damage` | Mod meldet `{streamer, damage, key}` |
| `GET` | `/status` | OBS-Overlay und Admin pollen hier |
| `POST` | `/admin/set` | Ziel setzen / Reset |
| `POST` | `/admin/pause` | Pause umschalten |
| `POST` | `/admin/streamers` | Streamer `add` / `remove` |
| `GET` | `/overlay` | OBS Browser Source HTML |
| `GET` | `/admin` | Admin-Panel HTML |

</details>

---

## 📜 Lizenz

MIT — siehe [LICENSE](LICENSE)

---

<div align="center">

Made with ❤️ by **[Mohjo_beist](https://github.com/Benjamin-Web)**

*"Einfach spielen. Der Rest läuft von selbst."*

</div>
