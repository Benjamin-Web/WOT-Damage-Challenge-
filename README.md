<div align="center">

# 🐾 BeastSync | Mohjo_beist
### World of Tanks — Community Damage Challenge Tracker

[![WoT Mod](https://img.shields.io/badge/WoT-Offizieller%20Mod-green)](https://wgmods.net)
[![Docker](https://img.shields.io/badge/Server-Docker%20ready-blue?logo=docker)](https://hub.docker.com)
[![Made by Mohjo_beist](https://img.shields.io/badge/by-Mohjo__beist-red)](https://github.com/Benjamin-Web)

**Kein manuelles Abziehen mehr.**
Jeder Streamer installiert einmal eine Exe — fertig.
Der Damage-Counter läuft von da an von selbst.

</div>

---

## Was ist BeastSync?

BeastSync ist ein von **Mohjo_beist** entwickelter World of Tanks Mod und Server für Community Damage-Challenges. Mehrere Streamer spielen gleichzeitig und arbeiten gemeinsam auf ein Schadensziel hin. Der Counter läuft automatisch — live, für alle sichtbar im OBS-Overlay.

Der Mod läuft über unseren eigenen Server. Streamer müssen nichts einrichten außer der Installer-Exe.

---

## Wer macht was?

| | Mohjo_beist (Veranstalter) | Streamer |
|---|---|---|
| **Einmalig** | — | `DamageChallenge-Install.exe` ausführen |
| **Pro Event** | Ziel + Streamer im Admin-Panel setzen | WoT starten und spielen |
| **Während Event** | Counter im Admin-Panel beobachten | Spielen |

---

## 📥 Für Streamer — So einfach geht's

> Du bekommst von Mohjo_beist eine Datei: **`DamageChallenge-Install.exe`**

**1.** Doppelklick auf die Exe

**2.** Deinen World of Tanks Account-Namen eingeben

**3.** „Jetzt installieren" klicken

**4.** WoT neu starten — fertig ✅

Der Installer erkennt World of Tanks automatisch und verbindet sich mit unserem Server. Du musst nichts weiter wissen oder installieren.

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

## 🖥️ Für Mohjo_beist — Server & Admin

### Server

Der BeastSync-Server läuft auf unserem VPS und ist dauerhaft erreichbar.

```bash
# Auf dem Server (einmalig einrichten):
git clone https://github.com/Benjamin-Web/WOT-Damage-Challenge-.git
cd WOT-Damage-Challenge-
docker compose up -d
```

Admin-Panel: `http://109.123.244.109:5000/admin`
OBS-Overlay: `http://109.123.244.109:5000/overlay`

### Exe neu bauen (nach Änderungen)

```bash
python2.7 mod/build_wotmod.py   # WoT-Mod kompilieren
python build_exe.py             # Installer-Exe bauen
```

Die fertige `DamageChallenge-Install.exe` liegt danach in `dist/`.

---

## 📺 OBS-Overlay einrichten

**In OBS bei jedem Streamer:**
1. Quelle hinzufügen → **Browser**
2. URL: `http://109.123.244.109:5000/overlay`
3. Breite `300` · Höhe `80`
4. Custom CSS: `body { background: transparent !important; }`

```
┌────────────────────────┐
│ RESTDAMAGE             │
│ 87.543                 │
└────────────────────────┘
```

---

## 🎛️ Admin-Panel

Unter `http://109.123.244.109:5000/admin` erreichbar (auch vom Handy).

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

- Streamer live hinzufügen oder entfernen — kein Serverneustart nötig
- Unbekannte Streamer werden beim ersten Damage automatisch registriert
- Pause, Reset, Ziel ändern per Klick

---

## 🏗️ Architektur

```
  VPS (109.123.244.109)
  ┌────────────────────────────────────────┐
  │  BeastSync Server (Flask, Port 5000)  │
  │                                        │
  │  GET /status   ◄── OBS Browser Source │◄──── alle Streamer-OBS
  │  POST /damage  ◄── WoT-Mod (je PC)    │
  │  GET /admin    ◄── Mohjo_beist        │
  └────────────────────────────────────────┘
          ▲                    ▲
  ┌───────────────┐    ┌───────────────┐
  │ Streamer 1    │    │ Streamer 2    │  ...
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
├── installer_config.json        ← Server-URL (fest eingetragen)
├── installer_gui.py             ← Streamer-Installer
├── server_gui.py                ← Server-GUI
├── build_exe.py                 ← Baut .exe Dateien
├── Dockerfile / docker-compose.yml
│
├── mod/
│   ├── mod_mohjobeist_beastsync.py   ← WoT Mod
│   └── build_wotmod.py
│
├── server/
│   ├── server.py / state.py / config.py
│
└── overlay/
    ├── index.html    ← OBS Browser Source
    └── admin.html    ← Admin-Panel
```

---

<div align="center">

Entwickelt von **[Mohjo_beist](https://github.com/Benjamin-Web)** für die WoT Streaming Community

*"Einfach spielen. Der Rest läuft von selbst."*

</div>
