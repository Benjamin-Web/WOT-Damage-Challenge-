# Datenverarbeitung & Netzwerkverbindung · Data Processing & Network Connection

**🇩🇪 Deutsch** · [🇬🇧 English](#-english)

---

## 🇩🇪 Deutsch — Transparenzhinweis

Dieser Mod ist Teil eines Community-Event-Tools („Damage Race"). Damit der Schaden
mehrerer Streamer live auf einem gemeinsamen Overlay zusammenlaufen kann, sendet der
Mod Daten an einen Event-Server.

**Welche Daten gesendet werden:**
- dein eigener im Gefecht verursachter **Direkt- und Assist-Schaden** (als Zahlenwert),
- eine **Streamer-Kennung** (Token bzw. der von dir selbst eingegebene Name),
- ein zufälliger **Vorgangsschlüssel** (UUID), um Doppelzählungen zu verhindern.

**Welche Daten NICHT gesendet werden:** keine Gegnerdaten, keine Positionen, keine
Spielinhalte über deinen eigenen Schaden hinaus, keine Account-Zugangsdaten, keine
Wargaming-Anmeldedaten.

**Wohin:** per **HTTPS** an den in der `config.json` hinterlegten Event-Server.
Standard: `mohjos-damagerace.duckdns.org`.

**Wann:** nur während eines aktiven Gefechts in einem zugewiesenen Event.

**Freiwillig & abschaltbar:** Der Mod überträgt **nur**, wenn du aktiv an einem Event
teilnimmst (gültiges Token in der Config). Ohne Token passiert nichts. Über
`"enabled": false` in der `config.json` lässt sich die Übertragung komplett deaktivieren.

**Lokales Debug-Log:** Zur Fehlersuche schreibt der Mod eine Logdatei nach
`%TEMP%\damagerace_debug.log`. Sie enthält keine personenbezogenen Daten außer den
oben genannten und kann jederzeit gelöscht werden.

**Quelloffen:** Der vollständige Quellcode liegt der `.wotmod` bei und ist öffentlich
einsehbar: https://github.com/Benjamin-Web/WOT-Damage-Challenge-

---

## 🇬🇧 English — Transparency Notice

This mod is part of a community event tool ("Damage Race"). To combine the damage of
several streamers live on a shared overlay, the mod sends data to an event server.

**Data that is sent:**
- your own **direct and assist damage** dealt in battle (as a numeric value),
- a **streamer identifier** (a token, or the name you entered yourself),
- a random **idempotency key** (UUID) to prevent double-counting.

**Data that is NOT sent:** no enemy data, no positions, no game information beyond your
own damage, no account credentials, no Wargaming login data.

**Where:** via **HTTPS** to the event server configured in `config.json`.
Default: `mohjos-damagerace.duckdns.org`.

**When:** only during an active battle within an assigned event.

**Voluntary & switchable:** the mod transmits **only** when you actively join an event
(a valid token in the config). With no token, nothing happens. Transmission can be fully
disabled via `"enabled": false` in `config.json`.

**Local debug log:** for troubleshooting, the mod writes a log file to
`%TEMP%\damagerace_debug.log`. It contains no personal data beyond the items listed
above and can be deleted at any time.

**Open source:** the full source code is included in the `.wotmod` and is publicly
available: https://github.com/Benjamin-Web/WOT-Damage-Challenge-
