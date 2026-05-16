<div align="center">

# Mohjos DamageRace
### World of Tanks — Community Damage Race Tracker

[![WoT Mod](https://img.shields.io/badge/WoT-Mod-FFD700)](https://wgmods.net)
[![Docker](https://img.shields.io/badge/Server-Docker%20ready-1e1e28?logo=docker)](https://hub.docker.com)
[![by Mohjo_beist](https://img.shields.io/badge/by-Mohjo__beist-FFD700)](https://github.com/Benjamin-Web)

**Streamer-Wettkampf, automatisch.**
Events, Teams, Einladungslinks — komplett im Browser steuerbar.

</div>

---

## Was ist DamageRace?

DamageRace ist ein von **Mohjo_beist** entwickeltes Setup für World-of-Tanks-Community-Events. Mehrere Streamer treten in Teams gegeneinander an oder kooperieren auf ein gemeinsames Schadensziel. Damage wird live gemessen, Counter im OBS-Overlay laufen synchron auf allen Streams.

**Drei Säulen:**
- **WoT-Mod** — misst Damage automatisch und sendet ihn an den Server
- **Server + Admin-Panel** — Events erstellen, Teams konfigurieren, Invite-Links versenden
- **OBS-Overlay** — zeigt Gesamt- und Team-Counter live, Glasmorphismus-Design

---

## Features

- 🏁 **Event-Wizard** — Name, Ziel, 2-4 Teams, Coop oder Versus
- 🔗 **Invite-Links** — Pro Event und pro Team, mit einem Klick kopieren
- 🎯 **Team-Modi** — Kooperativ (gemeinsames Ziel) oder Versus (Wettstreit)
- 📊 **Live-Overlay** — Team-Farben, Fortschrittsbalken, Glow-Flash bei Damage
- 🛡 **Login-geschützt** — Admin-Panel nur mit Passwort
- 🔄 **Idempotenz** — Doppelzählung ausgeschlossen, Retry bei Netzwerkfehler
- ⚙ **Ein-Klick-Installer** — Streamer geben nur ihren WoT-Namen ein
- 🎨 **Material-Design-3-UI** — Gold-Akzent, Dark Theme, Glasmorphismus

---

## So funktioniert's

```
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┐
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┤──►  [Server (privat gehostet)]  ──►  [OBS-Overlay aller Streamer]
[Streamer-PC: WoT + mohjos_damagerace.wotmod]  ──┘            ▲
                                                              │
                                              [Admin-Panel im Browser]
```

**Workflow:**
1. **Admin** öffnet `/admin`, erstellt ein Event mit Teams.
2. **Admin** kopiert Team-Invite-Links und schickt sie an Streamer.
3. **Streamer** öffnet Link → gibt WoT-Namen ein → wird Team zugeordnet.
4. **Streamer** installiert die Exe (einmalig) mit demselben Namen.
5. **OBS** lädt `/overlay` als Browser-Source.
6. Spiel läuft — Damage wird automatisch gezählt und sichtbar.

---

## Setup

### Server (für den Veranstalter)

```bash
git clone https://github.com/Benjamin-Web/WOT-Damage-Challenge-.git
cd WOT-Damage-Challenge-
```

`server/config.py` editieren (Passwörter setzen!) oder Env-Variablen verwenden:
```yaml
# docker-compose.yml
environment:
  ADMIN_SECRET: "dein-passwort"
  SESSION_SECRET: "lang-zufaellig"
  PUBLIC_BASE_URL: "http://deine-ip:5000"
```

```bash
docker compose up -d
```

Admin-Panel: `http://<deine-ip>:5000/admin` (Login mit `ADMIN_SECRET`)

### Mod-Build (einmalig)

Voraussetzung: Python 2.7 (für den `.wotmod`) und Python 3 + PyInstaller (für die Exe).

```bash
python2.7 mod/build_wotmod.py   # erzeugt dist/mohjos_damagerace.wotmod
python build_exe.py             # erzeugt dist/DamageRace-Install.exe
```

### Streamer

1. Invite-Link öffnen, WoT-Namen eingeben.
2. `DamageRace-Install.exe` herunterladen, starten, WoT-Namen eingeben.
3. World of Tanks starten — Damage wird automatisch gezählt.

---

## Architektur

- `mod/` — WoT-Mod (Python 2.7, BigWorld-API, Dual-Hook auf `showShotResults` + `updateVehicleHealth`)
- `server/` — Flask + Flask-Session, thread-safe State, UUID-Idempotenz
- `overlay/` — Login, Admin, Overlay, Join-Page (alle Vanilla JS, M3-Design)
- `installer_gui.py` — CustomTkinter-Setup, baked-in Server-URL
- `Dockerfile` + `docker-compose.yml` — VPS-Deployment

---

## Tech

| Komponente | Stack |
|---|---|
| WoT-Mod | Python 2.7, BigWorld API |
| Server | Python 3.11, Flask, flask-cors, Flask-Session |
| Frontend | Vanilla JS, Inter Font, Material Design 3 |
| Installer | CustomTkinter, PyInstaller (onefile) |
| Deployment | Docker, docker-compose |

---

<div align="center">

Made by **Mohjo_beist** · Twitch Streamer Community Project

</div>
