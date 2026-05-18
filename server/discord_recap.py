"""Discord webhook posting for end-of-event recaps.

The recap is built entirely from the event-state dict (no extra DB
queries) so the same builder works for the live "test" button and
for the final post.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

log = logging.getLogger("damagerace.discord")

WEBHOOK_RE = re.compile(
    r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+/?$"
)
DEFAULT_COLOR = 0xFFD700  # gold


def is_valid_webhook(url: str) -> bool:
    return bool(url) and bool(WEBHOOK_RE.match(url.strip()))


def _hex_to_int(color: str | None) -> int:
    if not color:
        return DEFAULT_COLOR
    raw = color.lstrip("#")
    try:
        return int(raw[:6], 16)
    except ValueError:
        return DEFAULT_COLOR


def _fmt(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


def build_recap_embed(event_state: dict, top_streamers: list[dict],
                      kind: str = "final") -> dict:
    event = event_state["event"]
    teams = sorted(event_state.get("teams", []),
                   key=lambda t: t.get("damage", 0), reverse=True)
    winner = teams[0] if teams else None

    title_prefix = "🏁" if kind == "final" else "🧪"
    title = f"{title_prefix} {event['name']}"

    desc_parts = [f"**Modus:** {event.get('mode', 'coop').title()}"]
    if winner:
        desc_parts.append(
            f"**Gewinner:** {winner['name']} mit "
            f"`{_fmt(winner.get('damage', 0))}` Damage"
        )
    desc_parts.append(
        f"**Gesamt-Damage:** `{_fmt(event.get('total_dealt', 0))}` / "
        f"`{_fmt(event.get('goal', 0))}`"
    )

    standings = "\n".join(
        f"`{i+1}.` **{t['name']}** — {_fmt(t.get('damage', 0))}"
        for i, t in enumerate(teams)
    ) or "—"

    top_lines = "\n".join(
        f"`{i+1}.` **{s.get('wot_name', '?')}** — {_fmt(s.get('damage', 0))}"
        for i, s in enumerate(top_streamers)
    ) or "—"

    embed = {
        "title": title,
        "description": "\n".join(desc_parts),
        "color": _hex_to_int(winner.get("color") if winner else None),
        "fields": [
            {"name": "Team-Standings", "value": standings, "inline": False},
            {"name": "Top-Streamer",   "value": top_lines, "inline": False},
        ],
        "footer": {"text": "via Mohjos DamageRace"},
    }
    if kind == "test":
        embed["description"] = "(Test-Post)\n\n" + embed["description"]
    return embed


def post_webhook(url: str, embed: dict) -> tuple[bool, str | None]:
    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json",
                 "User-Agent": "DamageRace-Recap/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.status < 300:
                return True, None
            return False, f"http_{resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"http_{exc.code}"
    except urllib.error.URLError as exc:
        return False, f"network_{exc.reason}"
    except Exception as exc:
        log.warning("Discord webhook failed: %s", exc)
        return False, "unknown"
