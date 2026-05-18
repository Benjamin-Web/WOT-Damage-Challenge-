"""Message catalog and locale resolution for the API layer.

The catalog only contains user-facing messages that the API returns to the
client. Internal log lines stay in English.
"""
from __future__ import annotations

SUPPORTED = ("de", "en")
DEFAULT = "de"

_MESSAGES: dict[str, dict[str, str]] = {
    "auth.required":          {"de": "Anmeldung erforderlich.",
                               "en": "Authentication required."},
    "auth.state_missing":     {"de": "Fehlender state-Parameter.",
                               "en": "Missing state parameter."},
    "auth.state_invalid":     {"de": "Auth-Sitzung abgelaufen oder ungueltig.",
                               "en": "Authentication session expired or invalid."},
    "auth.code_missing":      {"de": "Kein Code von Twitch erhalten.",
                               "en": "No authorization code returned from Twitch."},
    "auth.profile_failed":    {"de": "Twitch-Profil konnte nicht geladen werden.",
                               "en": "Could not load Twitch profile."},
    "auth.exchange_failed":   {"de": "Twitch-Authentifizierung fehlgeschlagen: {detail}",
                               "en": "Twitch authentication failed: {detail}"},
    "auth.session_invalid":   {"de": "Sitzung ungueltig.",
                               "en": "Session invalid."},
    "auth.success":           {"de": "Login erfolgreich. Du kannst dieses Fenster schliessen.",
                               "en": "Login successful. You can close this window."},

    "event.none":             {"de": "Kein aktives Event.",
                               "en": "No active event."},
    "event.invalid_payload":  {"de": "Ungueltige Event-Daten.",
                               "en": "Invalid event payload."},
    "event.goal_invalid":     {"de": "Schaden-Ziel muss eine positive Zahl sein.",
                               "en": "Damage goal must be a positive number."},
    "event.mode_invalid":     {"de": "Modus muss 'coop' oder 'versus' sein.",
                               "en": "Mode must be 'coop' or 'versus'."},
    "event.teams_invalid":    {"de": "Es muessen 2 bis 4 Teams angegeben werden.",
                               "en": "Between 2 and 4 teams are required."},
    "event.name_invalid":     {"de": "Event-Name darf nicht leer sein.",
                               "en": "Event name must not be empty."},

    "invite.invalid":         {"de": "Einladungslink ungueltig.",
                               "en": "Invitation link is invalid."},
    "invite.fields_required": {"de": "Token und WoT-Name sind erforderlich.",
                               "en": "Token and WoT name are required."},
    "invite.wot_name_empty":  {"de": "WoT-Name darf nicht leer sein.",
                               "en": "WoT name must not be empty."},

    "damage.token_required":  {"de": "streamer_token ist erforderlich.",
                               "en": "streamer_token is required."},
    "damage.invalid":         {"de": "Damage-Wert ungueltig.",
                               "en": "Damage value is invalid."},
    "damage.must_be_positive":{"de": "Damage muss positiv sein.",
                               "en": "Damage must be positive."},
    "damage.streamer_unknown":{"de": "Streamer-Token unbekannt oder deaktiviert.",
                               "en": "Streamer token unknown or disabled."},

    "event.not_found":        {"de": "Event nicht gefunden.",
                               "en": "Event not found."},

    "roster.wot_name_empty":   {"de": "WoT-Name darf nicht leer sein.",
                                "en": "WoT name must not be empty."},
    "roster.team_not_in_event":{"de": "Team gehoert nicht zu diesem Event.",
                                "en": "Team does not belong to this event."},
    "roster.streamer_unknown": {"de": "Streamer nicht im Event gefunden.",
                                "en": "Streamer not found in this event."},
}


def normalize(lang: str | None) -> str:
    """Return a supported locale, falling back to the default."""
    if not lang:
        return DEFAULT
    code = lang.strip().lower().split("-")[0].split("_")[0]
    return code if code in SUPPORTED else DEFAULT


def t(key: str, lang: str | None = None, **params: object) -> str:
    """Translate `key` for the given language. Unknown keys return the key
    itself, which makes missing entries easy to spot during testing."""
    entry = _MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(normalize(lang), entry.get(DEFAULT, key))
    if params:
        try:
            text = text.format(**params)
        except (KeyError, IndexError):
            pass
    return text
