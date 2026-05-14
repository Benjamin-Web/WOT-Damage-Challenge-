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

BeastSync ist ein von **Mohjo_beist** entwickelter World of Tanks Mod für Community Damage-Challenges. Mehrere Streamer spielen gleichzeitig und arbeiten gemeinsam auf ein Schadensziel hin. Der Counter läuft automatisch — live, für alle sichtbar im OBS-Overlay.

Alles läuft über unseren eigenen Server. Streamer müssen nichts einrichten außer der Installer-Exe.

---

## 📥 Für Streamer — So einfach geht's

> Du bekommst von Mohjo_beist eine Datei: **`DamageChallenge-Install.exe`**

**1.** Doppelklick auf die Exe

**2.** Deinen World of Tanks Account-Namen eingeben

**3.** „Jetzt installieren" klicken

**4.** WoT neu starten — fertig ✅

Der Installer erkennt World of Tanks automatisch und verbindet sich mit dem BeastSync-Server. Kein Python, kein Config-File, nichts weiter nötig.

```
┌─────────────────────────────────────────────────────┐
│  🐾 BeastSync Setup                                 │
│─────────────────────────────────────────────────────│
│                                                     │
│  Dein World of Tanks Account-Name                   │
│  ┌───────────────────────────────────────────────┐  │
│  │  Mohjo_beist                                  │  │
│  └───────────────────────────────────────────────┘  │
│  ⚠  Groß-/Kleinschreibung beachten!                 │
│                                                     │
│  ✅  WoT gefunden (Version 1.24.1.0)                │
│                                                     │
│                        [Jetzt installieren  →]      │
└─────────────────────────────────────────────────────┘
```

---

## 🎛️ Für Mohjo_beist — Admin-Zugang

Das Admin-Panel ist passwortgeschützt und läuft komplett im Browser. Kein lokales Programm nötig — auch vom Handy oder Tablet aus bedienbar.

**Admin-Panel:** Wird privat kommuniziert.

Funktionen im Admin-Panel:
- Schadensziel setzen und zurücksetzen
- Streamer live hinzufügen oder entfernen
- Pause / Fortsetzen
- Live-Log aller Treffer

---

## 📺 OBS-Overlay

Die OBS-URL wird von Mohjo_beist vor dem Event an alle Streamer kommuniziert.

**In OBS:**
1. Quelle hinzufügen → **Browser**
2. URL einfügen (vom Veranstalter)
3. Breite `300` · Höhe `80`
4. Custom CSS: `body { background: transparent !important; }`

---

## 🏗️ Architektur

```
  BeastSync Server (privat gehostet)
  ┌────────────────────────────────────────┐
  │                                        │
  │  GET /status   ◄── OBS Browser Source │◄──── alle Streamer-OBS
  │  POST /damage  ◄── WoT-Mod (je PC)    │
  │  GET /admin    ◄── Mohjo_beist (Login)│
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
├── installer_config.json        ← Server-Verbindung (privat)
├── installer_gui.py             ← Streamer-Installer
├── build_exe.py                 ← Baut Installer.exe
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
    ├── admin.html    ← Admin-Panel
    └── login.html    ← Login
```

---

<div align="center">

Entwickelt von **[Mohjo_beist](https://github.com/Benjamin-Web)** für die WoT Streaming Community

*"Einfach spielen. Der Rest läuft von selbst."*

</div>
