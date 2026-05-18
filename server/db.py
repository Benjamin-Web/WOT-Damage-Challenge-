"""SQLite persistence layer for DamageRace.

One database file holds every tenant. The schema enforces:

    - one active event per Twitch owner (`UNIQUE(owner_twitch_id)`),
    - unique slugs for public overlay URLs,
    - unique invite tokens across events and teams,
    - unique (event, wot_name) per streamer participation.

The connection helper enables WAL mode and foreign keys, both required for
the row-level cascades to behave deterministically under concurrent writes.
"""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable

log = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "DAMAGERACE_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "damagerace.db"),
)

MAX_TEAMS = 4
MIN_TEAMS = 2
MAX_DAMAGE_PER_REQUEST = 10_000
EVENT_LOG_LIMIT = 200
IDEMPOTENCY_TTL_SECONDS = 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_token(prefix: str = "") -> str:
    return prefix + secrets.token_urlsafe(8)


def _new_uuid() -> str:
    return secrets.token_urlsafe(16)


class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    # ── Connection ────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              twitch_id    TEXT PRIMARY KEY,
              twitch_login TEXT NOT NULL,
              display_name TEXT NOT NULL,
              avatar_url   TEXT,
              created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
              id                  INTEGER PRIMARY KEY AUTOINCREMENT,
              owner_twitch_id     TEXT NOT NULL UNIQUE,
              name                TEXT NOT NULL,
              goal                REAL NOT NULL DEFAULT 100000,
              mode                TEXT NOT NULL DEFAULT 'coop',
              paused              INTEGER NOT NULL DEFAULT 0,
              total_dealt         REAL NOT NULL DEFAULT 0,
              event_invite_token  TEXT NOT NULL UNIQUE,
              slug                TEXT NOT NULL UNIQUE,
              created_at          TEXT NOT NULL,
              FOREIGN KEY(owner_twitch_id) REFERENCES users(twitch_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS teams (
              id            INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id      INTEGER NOT NULL,
              position      INTEGER NOT NULL,
              name          TEXT NOT NULL,
              color         TEXT NOT NULL,
              damage        REAL NOT NULL DEFAULT 0,
              invite_token  TEXT NOT NULL UNIQUE,
              FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS streamers (
              token       TEXT PRIMARY KEY,
              event_id    INTEGER NOT NULL,
              team_id     INTEGER,
              wot_name    TEXT NOT NULL,
              damage      REAL NOT NULL DEFAULT 0,
              last_seen   TEXT,
              active      INTEGER NOT NULL DEFAULT 1,
              created_at  TEXT NOT NULL,
              FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE,
              FOREIGN KEY(team_id)  REFERENCES teams(id)  ON DELETE SET NULL,
              UNIQUE(event_id, wot_name)
            );

            CREATE TABLE IF NOT EXISTS event_log (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id   INTEGER NOT NULL,
              t          TEXT NOT NULL,
              wot_name   TEXT NOT NULL,
              team_id    INTEGER,
              damage     INTEGER NOT NULL,
              remaining  INTEGER NOT NULL,
              FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
              id         TEXT PRIMARY KEY,
              twitch_id  TEXT,
              created_at TEXT NOT NULL,
              expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS oauth_pending (
              state       TEXT PRIMARY KEY,
              session_id  TEXT NOT NULL,
              created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idempotency (
              key      TEXT PRIMARY KEY,
              created  REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_streamers_event ON streamers(event_id);
            CREATE INDEX IF NOT EXISTS idx_teams_event     ON teams(event_id);
            CREATE INDEX IF NOT EXISTS idx_log_event       ON event_log(event_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
            """)

            # Additive migrations — wrap in try/except so reruns are idempotent.
            for ddl in (
                "ALTER TABLE events ADD COLUMN discord_webhook TEXT",
                "ALTER TABLE events ADD COLUMN recap_posted_at TEXT",
            ):
                try:
                    c.execute(ddl)
                except sqlite3.OperationalError:
                    pass

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, twitch_id: str, twitch_login: str,
                    display_name: str, avatar_url: str | None = None) -> dict | None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT INTO users (twitch_id, twitch_login, display_name, avatar_url, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(twitch_id) DO UPDATE SET
                  twitch_login = excluded.twitch_login,
                  display_name = excluded.display_name,
                  avatar_url   = excluded.avatar_url
                """,
                (twitch_id, twitch_login, display_name, avatar_url, _now_iso()),
            )
        return self.get_user(twitch_id)

    def get_user(self, twitch_id: str) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM users WHERE twitch_id = ?", (twitch_id,),
            ).fetchone()
            return dict(row) if row else None

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, twitch_id: str | None = None,
                       ttl_seconds: int = 30 * 24 * 3600) -> str:
        sid = _new_uuid()
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO sessions (id, twitch_id, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (sid, twitch_id, str(now), str(now + ttl_seconds)),
            )
        return sid

    def get_session(self, sid: str | None) -> dict | None:
        if not sid:
            return None
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM sessions WHERE id = ?", (sid,),
            ).fetchone()
            if not row:
                return None
            if float(row["expires_at"]) < time.time():
                c.execute("DELETE FROM sessions WHERE id = ?", (sid,))
                return None
            return dict(row)

    def attach_user_to_session(self, sid: str, twitch_id: str) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                "UPDATE sessions SET twitch_id = ? WHERE id = ?",
                (twitch_id, sid),
            )

    def delete_session(self, sid: str) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM sessions WHERE id = ?", (sid,))

    def cleanup_expired_sessions(self) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "DELETE FROM sessions WHERE expires_at < ?", (str(time.time()),),
            )
            return cur.rowcount or 0

    # ── OAuth-State ───────────────────────────────────────────────────────────

    def create_oauth_state(self, session_id: str) -> str:
        state = _new_uuid()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO oauth_pending (state, session_id, created_at) "
                "VALUES (?, ?, ?)",
                (state, session_id, _now_iso()),
            )
        return state

    def consume_oauth_state(self, state: str) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM oauth_pending WHERE state = ?", (state,),
            ).fetchone()
            if not row:
                return None
            c.execute("DELETE FROM oauth_pending WHERE state = ?", (state,))
            return dict(row)

    # ── Events ────────────────────────────────────────────────────────────────

    def _slug_for_user(self, twitch_login: str, conn: sqlite3.Connection) -> str:
        base = "".join(ch.lower() for ch in twitch_login if ch.isalnum())[:24] or "event"
        candidate = base
        i = 1
        while conn.execute(
            "SELECT 1 FROM events WHERE slug = ?", (candidate,),
        ).fetchone():
            i += 1
            candidate = f"{base}-{i}"
        return candidate

    def get_event_by_owner(self, twitch_id: str) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM events WHERE owner_twitch_id = ?", (twitch_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_event_by_slug(self, slug: str) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM events WHERE slug = ?", (slug,),
            ).fetchone()
            return dict(row) if row else None

    def get_event_by_id(self, event_id: int) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,),
            ).fetchone()
            return dict(row) if row else None

    def create_or_replace_event(self, owner_twitch_id: str, name: str,
                                goal: float, mode: str,
                                team_specs: Iterable[dict[str, Any]],
                                twitch_login: str | None = None) -> int:
        teams = list(team_specs)[:MAX_TEAMS]
        with self._lock, self._conn() as c:
            existing = c.execute(
                "SELECT id FROM events WHERE owner_twitch_id = ?",
                (owner_twitch_id,),
            ).fetchone()
            if existing:
                c.execute("DELETE FROM events WHERE id = ?", (existing["id"],))

            slug = self._slug_for_user(twitch_login or owner_twitch_id, c)
            event_invite = _new_token("ev_")
            cur = c.execute(
                """
                INSERT INTO events (owner_twitch_id, name, goal, mode, paused,
                                    total_dealt, event_invite_token, slug, created_at)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
                """,
                (owner_twitch_id, name, float(goal), mode,
                 event_invite, slug, _now_iso()),
            )
            event_id = cur.lastrowid

            for position, spec in enumerate(teams):
                team_name = (spec.get("name") or f"Team {position + 1}").strip()
                color = (spec.get("color") or "#ffd700").strip()
                c.execute(
                    """
                    INSERT INTO teams (event_id, position, name, color, damage, invite_token)
                    VALUES (?, ?, ?, ?, 0, ?)
                    """,
                    (event_id, position, team_name, color, _new_token("tm_")),
                )
            log.info("Created event id=%s owner=%s slug=%s teams=%d",
                     event_id, owner_twitch_id, slug, len(teams))
            return event_id

    def delete_event(self, event_id: int) -> None:
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM events WHERE id = ?", (event_id,))

    def set_event_goal(self, event_id: int, goal: float) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE events SET goal = ? WHERE id = ?",
                      (float(goal), event_id))

    def set_event_paused(self, event_id: int, paused: bool) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE events SET paused = ? WHERE id = ?",
                      (1 if paused else 0, event_id))

    def reset_event(self, event_id: int, new_goal: float | None = None) -> None:
        with self._lock, self._conn() as c:
            if new_goal is not None:
                c.execute(
                    "UPDATE events SET total_dealt = 0, paused = 0, goal = ? "
                    "WHERE id = ?",
                    (float(new_goal), event_id),
                )
            else:
                c.execute(
                    "UPDATE events SET total_dealt = 0, paused = 0 WHERE id = ?",
                    (event_id,),
                )
            c.execute("UPDATE teams     SET damage = 0 WHERE event_id = ?", (event_id,))
            c.execute("UPDATE streamers SET damage = 0, last_seen = NULL "
                      "WHERE event_id = ?", (event_id,))
            c.execute("DELETE FROM event_log WHERE event_id = ?", (event_id,))

    def regenerate_event_invite(self, event_id: int) -> str:
        token = _new_token("ev_")
        with self._lock, self._conn() as c:
            c.execute("UPDATE events SET event_invite_token = ? WHERE id = ?",
                      (token, event_id))
        return token

    def regenerate_team_invite(self, team_id: int) -> str:
        token = _new_token("tm_")
        with self._lock, self._conn() as c:
            c.execute("UPDATE teams SET invite_token = ? WHERE id = ?",
                      (token, team_id))
        return token

    # ── Invites & Join ────────────────────────────────────────────────────────

    def resolve_invite(self, token: str | None) -> tuple[str | None, dict | None]:
        """Return (kind, info) for an invite token. `kind` is 'event' or
        'team'; for team invites the result row also carries the joined event
        fields prefixed with `e_`."""
        if not token:
            return None, None
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM events WHERE event_invite_token = ?", (token,),
            ).fetchone()
            if row:
                return "event", dict(row)
            row = c.execute(
                """
                SELECT teams.*, events.id AS e_id, events.name AS e_name,
                       events.slug AS e_slug, events.owner_twitch_id AS e_owner
                FROM teams JOIN events ON teams.event_id = events.id
                WHERE teams.invite_token = ?
                """,
                (token,),
            ).fetchone()
            if row:
                return "team", dict(row)
            return None, None

    def join_via_invite(self, token: str, wot_name: str
                        ) -> tuple[dict | None, str | None]:
        """Returns (result_dict, error_key). The caller maps `error_key`
        to a localized message via i18n."""
        wot_name = (wot_name or "").strip()
        if not wot_name:
            return None, "invite.wot_name_empty"

        kind, info = self.resolve_invite(token)
        if not kind or not info:
            return None, "invite.invalid"

        event_id = info["id"] if kind == "event" else info["event_id"]
        team_id = info["id"] if kind == "team" else None

        with self._lock, self._conn() as c:
            existing = c.execute(
                "SELECT * FROM streamers WHERE event_id = ? AND wot_name = ?",
                (event_id, wot_name),
            ).fetchone()
            if existing:
                streamer_token = existing["token"]
                c.execute(
                    "UPDATE streamers SET team_id = ?, active = 1 WHERE token = ?",
                    (team_id, streamer_token),
                )
            else:
                streamer_token = _new_uuid()
                c.execute(
                    """
                    INSERT INTO streamers (token, event_id, team_id, wot_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (streamer_token, event_id, team_id, wot_name, _now_iso()),
                )

            event = c.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,),
            ).fetchone()
            team = None
            if team_id:
                team = c.execute(
                    "SELECT * FROM teams WHERE id = ?", (team_id,),
                ).fetchone()
            log.info("Streamer joined event=%s name=%r team=%s",
                     event_id, wot_name, team_id)
            return {
                "streamer_token": streamer_token,
                "event": dict(event),
                "team":  dict(team) if team else None,
            }, None

    # ── Integrations (Discord webhook) ────────────────────────────────────────

    def set_discord_webhook(self, event_id: int, webhook_url: str | None) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE events SET discord_webhook = ? WHERE id = ?",
                      (webhook_url, event_id))

    def mark_recap_posted(self, event_id: int) -> None:
        with self._lock, self._conn() as c:
            c.execute("UPDATE events SET recap_posted_at = ? WHERE id = ?",
                      (_now_iso(), event_id))

    def get_event_row(self, event_id: int) -> dict | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM events WHERE id = ?",
                            (event_id,)).fetchone()
            return dict(row) if row else None

    def get_top_streamers(self, event_id: int, limit: int = 3) -> list[dict]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT wot_name, damage, team_id FROM streamers "
                "WHERE event_id = ? AND damage > 0 "
                "ORDER BY damage DESC LIMIT ?",
                (event_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Owner-managed roster ──────────────────────────────────────────────────

    def add_streamer(self, event_id: int, team_id: int | None,
                     wot_name: str) -> tuple[dict | None, str | None]:
        wot_name = (wot_name or "").strip()
        if not wot_name:
            return None, "roster.wot_name_empty"
        with self._lock, self._conn() as c:
            if team_id is not None:
                team = c.execute(
                    "SELECT id FROM teams WHERE id = ? AND event_id = ?",
                    (team_id, event_id),
                ).fetchone()
                if not team:
                    return None, "roster.team_not_in_event"
            existing = c.execute(
                "SELECT * FROM streamers WHERE event_id = ? AND wot_name = ?",
                (event_id, wot_name),
            ).fetchone()
            if existing:
                c.execute(
                    "UPDATE streamers SET team_id = ?, active = 1 WHERE token = ?",
                    (team_id, existing["token"]),
                )
                token = existing["token"]
            else:
                token = _new_uuid()
                c.execute(
                    """
                    INSERT INTO streamers (token, event_id, team_id, wot_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (token, event_id, team_id, wot_name, _now_iso()),
                )
            return {"streamer_token": token, "wot_name": wot_name,
                    "team_id": team_id}, None

    def move_streamer(self, event_id: int, wot_name: str,
                      team_id: int | None) -> str | None:
        with self._lock, self._conn() as c:
            if team_id is not None:
                team = c.execute(
                    "SELECT id FROM teams WHERE id = ? AND event_id = ?",
                    (team_id, event_id),
                ).fetchone()
                if not team:
                    return "roster.team_not_in_event"
            res = c.execute(
                "UPDATE streamers SET team_id = ? "
                "WHERE event_id = ? AND wot_name = ?",
                (team_id, event_id, wot_name),
            )
            if res.rowcount == 0:
                return "roster.streamer_unknown"
            return None

    def remove_streamer(self, event_id: int, wot_name: str) -> str | None:
        with self._lock, self._conn() as c:
            res = c.execute(
                "DELETE FROM streamers WHERE event_id = ? AND wot_name = ?",
                (event_id, wot_name),
            )
            if res.rowcount == 0:
                return "roster.streamer_unknown"
            return None

    # ── Damage ────────────────────────────────────────────────────────────────

    def record_damage(self, streamer_token: str, damage: int,
                      key: str | None = None) -> tuple[bool, int]:
        damage = int(damage)
        if damage <= 0:
            return False, 0
        if damage > MAX_DAMAGE_PER_REQUEST:
            log.warning("Clamped implausible damage value: %d", damage)
            damage = MAX_DAMAGE_PER_REQUEST

        with self._lock, self._conn() as c:
            now = time.time()
            c.execute("DELETE FROM idempotency WHERE created < ?",
                      (now - IDEMPOTENCY_TTL_SECONDS,))
            if key:
                try:
                    c.execute(
                        "INSERT INTO idempotency (key, created) VALUES (?, ?)",
                        (key, now),
                    )
                except sqlite3.IntegrityError:
                    return True, 0  # duplicate request, already counted

            streamer = c.execute(
                "SELECT * FROM streamers WHERE token = ?", (streamer_token,),
            ).fetchone()
            if not streamer or not streamer["active"]:
                return False, 0

            event = c.execute(
                "SELECT * FROM events WHERE id = ?", (streamer["event_id"],),
            ).fetchone()
            if not event:
                return False, 0
            if event["paused"]:
                return False, max(0, int(event["goal"] - event["total_dealt"]))

            new_total = event["total_dealt"] + damage
            c.execute("UPDATE events SET total_dealt = ? WHERE id = ?",
                      (new_total, event["id"]))
            c.execute(
                "UPDATE streamers SET damage = damage + ?, last_seen = ? "
                "WHERE token = ?",
                (damage, _now_iso(), streamer_token),
            )
            if streamer["team_id"]:
                c.execute(
                    "UPDATE teams SET damage = damage + ? WHERE id = ?",
                    (damage, streamer["team_id"]),
                )
            remaining = max(0, int(event["goal"] - new_total))
            c.execute(
                """
                INSERT INTO event_log (event_id, t, wot_name, team_id, damage, remaining)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event["id"], datetime.now().strftime("%H:%M:%S"),
                 streamer["wot_name"], streamer["team_id"], damage, remaining),
            )
            c.execute(
                """
                DELETE FROM event_log
                 WHERE event_id = ?
                   AND id NOT IN (
                       SELECT id FROM event_log
                        WHERE event_id = ?
                        ORDER BY id DESC LIMIT ?
                   )
                """,
                (event["id"], event["id"], EVENT_LOG_LIMIT),
            )
            return True, remaining

    # ── State snapshot ────────────────────────────────────────────────────────

    def get_event_state(self, event_id: int, base_url: str = "") -> dict | None:
        with self._lock, self._conn() as c:
            event = c.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,),
            ).fetchone()
            if not event:
                return None
            teams = c.execute(
                "SELECT * FROM teams WHERE event_id = ? ORDER BY position",
                (event_id,),
            ).fetchall()
            streamers = c.execute(
                "SELECT * FROM streamers WHERE event_id = ?", (event_id,),
            ).fetchall()
            logs = c.execute(
                "SELECT * FROM event_log WHERE event_id = ? "
                "ORDER BY id DESC LIMIT 30",
                (event_id,),
            ).fetchall()
            owner = c.execute(
                "SELECT * FROM users WHERE twitch_id = ?",
                (event["owner_twitch_id"],),
            ).fetchone()

        base = base_url.rstrip("/") if base_url else ""

        teams_out: list[dict] = []
        for team in teams:
            members = [s["wot_name"] for s in streamers if s["team_id"] == team["id"]]
            teams_out.append({
                "id":           team["id"],
                "name":         team["name"],
                "color":        team["color"],
                "damage":       int(team["damage"]),
                "invite_token": team["invite_token"],
                "invite_url":   f"{base}/join/{team['invite_token']}" if base else None,
                "members":      members,
            })

        streamers_map: dict[str, dict] = {}
        for streamer in streamers:
            streamers_map[streamer["wot_name"]] = {
                "token":     streamer["token"],
                "team_id":   streamer["team_id"],
                "damage":    int(streamer["damage"]),
                "last_seen": streamer["last_seen"],
                "active":    bool(streamer["active"]),
            }

        log_out = []
        for entry in logs:
            row = dict(entry)
            row["streamer"] = row["wot_name"]  # backward-compatible alias
            log_out.append(row)

        return {
            "event": {
                "id":           event["id"],
                "slug":         event["slug"],
                "name":         event["name"],
                "goal":         int(event["goal"]),
                "mode":         event["mode"],
                "paused":       bool(event["paused"]),
                "total_dealt":  int(event["total_dealt"]),
                "remaining":    max(0, int(event["goal"] - event["total_dealt"])),
                "invite_token": event["event_invite_token"],
                "invite_url":   f"{base}/join/{event['event_invite_token']}" if base else None,
                "overlay_url":  f"{base}/overlay/{event['slug']}" if base else None,
                "owner":        dict(owner) if owner else None,
                "discord_webhook":   event["discord_webhook"] if "discord_webhook" in event.keys() else None,
                "recap_posted_at":   event["recap_posted_at"] if "recap_posted_at" in event.keys() else None,
            },
            "teams":     teams_out,
            "streamers": streamers_map,
            "event_log": log_out,
        }
