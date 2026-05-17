"""
db.py — SQLite Layer fuer Mohjos DamageRace (Multi-Tenant)

Schema:
  users(twitch_id PK, twitch_login, display_name, created_at)
  events(id PK, owner_twitch_id FK, name, goal, mode, paused, total_dealt,
         event_invite_token, created_at)
  teams(id PK, event_id FK, slug, name, color, damage, invite_token, position)
  streamers(token PK uuid, event_id FK, team_id FK NULL, wot_name, damage,
            last_seen, active, created_at)
  event_log(id PK, event_id FK, t, wot_name, team_id, damage, remaining)

Ein User hat 0 oder 1 aktives Event (UNIQUE auf events.owner_twitch_id).
"""
import os
import sqlite3
import threading
import secrets
import time
from datetime import datetime, timezone

DB_PATH = os.environ.get('DAMAGERACE_DB',
                         os.path.join(os.path.dirname(__file__), '..', 'data', 'damagerace.db'))


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _new_token(prefix=''):
    return prefix + secrets.token_urlsafe(8)


def _new_uuid():
    return secrets.token_urlsafe(16)


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def _init_schema(self):
        with self._lock, self._conn() as c:
            c.executescript('''
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
              key       TEXT PRIMARY KEY,
              created   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_streamers_event ON streamers(event_id);
            CREATE INDEX IF NOT EXISTS idx_teams_event     ON teams(event_id);
            CREATE INDEX IF NOT EXISTS idx_log_event       ON event_log(event_id, id DESC);
            ''')

    # ── Users ─────────────────────────────────────────────────────────────────

    def upsert_user(self, twitch_id, twitch_login, display_name, avatar_url=None):
        with self._lock, self._conn() as c:
            c.execute('''
                INSERT INTO users (twitch_id, twitch_login, display_name, avatar_url, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(twitch_id) DO UPDATE SET
                  twitch_login = excluded.twitch_login,
                  display_name = excluded.display_name,
                  avatar_url   = excluded.avatar_url
            ''', (twitch_id, twitch_login, display_name, avatar_url, _now_iso()))
            return self.get_user(twitch_id)

    def get_user(self, twitch_id):
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM users WHERE twitch_id = ?', (twitch_id,)).fetchone()
            return dict(r) if r else None

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, twitch_id=None, ttl_seconds=30*24*3600):
        sid = _new_uuid()
        now = time.time()
        with self._lock, self._conn() as c:
            c.execute('INSERT INTO sessions (id, twitch_id, created_at, expires_at) VALUES (?,?,?,?)',
                      (sid, twitch_id, str(now), str(now + ttl_seconds)))
        return sid

    def get_session(self, sid):
        if not sid:
            return None
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM sessions WHERE id = ?', (sid,)).fetchone()
            if not r:
                return None
            if float(r['expires_at']) < time.time():
                c.execute('DELETE FROM sessions WHERE id = ?', (sid,))
                return None
            return dict(r)

    def attach_user_to_session(self, sid, twitch_id):
        with self._lock, self._conn() as c:
            c.execute('UPDATE sessions SET twitch_id = ? WHERE id = ?', (twitch_id, sid))

    def delete_session(self, sid):
        with self._lock, self._conn() as c:
            c.execute('DELETE FROM sessions WHERE id = ?', (sid,))

    # ── OAuth-State ───────────────────────────────────────────────────────────

    def create_oauth_state(self, session_id):
        state = _new_uuid()
        with self._lock, self._conn() as c:
            c.execute('INSERT INTO oauth_pending (state, session_id, created_at) VALUES (?,?,?)',
                      (state, session_id, _now_iso()))
        return state

    def consume_oauth_state(self, state):
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM oauth_pending WHERE state = ?', (state,)).fetchone()
            if not r:
                return None
            c.execute('DELETE FROM oauth_pending WHERE state = ?', (state,))
            return dict(r)

    # ── Events ────────────────────────────────────────────────────────────────

    def _slug_for_user(self, twitch_login, c):
        base = ''.join(ch.lower() for ch in twitch_login if ch.isalnum())[:24] or 'event'
        cand = base
        i = 1
        while c.execute('SELECT 1 FROM events WHERE slug = ?', (cand,)).fetchone():
            i += 1
            cand = '{}-{}'.format(base, i)
        return cand

    def get_event_by_owner(self, twitch_id):
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM events WHERE owner_twitch_id = ?', (twitch_id,)).fetchone()
            return dict(r) if r else None

    def get_event_by_slug(self, slug):
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM events WHERE slug = ?', (slug,)).fetchone()
            return dict(r) if r else None

    def get_event_by_id(self, event_id):
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
            return dict(r) if r else None

    def create_or_replace_event(self, owner_twitch_id, name, goal, mode, team_specs, twitch_login=None):
        with self._lock, self._conn() as c:
            existing = c.execute('SELECT id FROM events WHERE owner_twitch_id = ?',
                                 (owner_twitch_id,)).fetchone()
            if existing:
                c.execute('DELETE FROM events WHERE id = ?', (existing['id'],))

            slug = self._slug_for_user(twitch_login or owner_twitch_id, c)
            event_invite = _new_token('ev_')
            cur = c.execute('''
                INSERT INTO events (owner_twitch_id, name, goal, mode, paused,
                                    total_dealt, event_invite_token, slug, created_at)
                VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?)
            ''', (owner_twitch_id, name, float(goal), mode, event_invite, slug, _now_iso()))
            event_id = cur.lastrowid

            for i, spec in enumerate(team_specs[:4]):
                c.execute('''
                    INSERT INTO teams (event_id, position, name, color, damage, invite_token)
                    VALUES (?, ?, ?, ?, 0, ?)
                ''', (event_id, i, (spec.get('name') or 'Team {}'.format(i+1)).strip(),
                      (spec.get('color') or '#ffd700').strip(), _new_token('tm_')))
            return event_id

    def delete_event(self, event_id):
        with self._lock, self._conn() as c:
            c.execute('DELETE FROM events WHERE id = ?', (event_id,))

    def set_event_goal(self, event_id, goal):
        with self._lock, self._conn() as c:
            c.execute('UPDATE events SET goal = ? WHERE id = ?', (float(goal), event_id))

    def set_event_paused(self, event_id, paused):
        with self._lock, self._conn() as c:
            c.execute('UPDATE events SET paused = ? WHERE id = ?', (1 if paused else 0, event_id))

    def reset_event(self, event_id, new_goal=None):
        with self._lock, self._conn() as c:
            if new_goal is not None:
                c.execute('UPDATE events SET total_dealt=0, paused=0, goal=? WHERE id=?',
                          (float(new_goal), event_id))
            else:
                c.execute('UPDATE events SET total_dealt=0, paused=0 WHERE id=?', (event_id,))
            c.execute('UPDATE teams     SET damage=0 WHERE event_id=?', (event_id,))
            c.execute('UPDATE streamers SET damage=0, last_seen=NULL WHERE event_id=?', (event_id,))
            c.execute('DELETE FROM event_log WHERE event_id=?', (event_id,))

    def regenerate_event_invite(self, event_id):
        token = _new_token('ev_')
        with self._lock, self._conn() as c:
            c.execute('UPDATE events SET event_invite_token = ? WHERE id = ?', (token, event_id))
        return token

    def regenerate_team_invite(self, team_id):
        token = _new_token('tm_')
        with self._lock, self._conn() as c:
            c.execute('UPDATE teams SET invite_token = ? WHERE id = ?', (token, team_id))
        return token

    # ── Invites + Join ────────────────────────────────────────────────────────

    def resolve_invite(self, token):
        """Returns ('event', event_dict) or ('team', team_dict + event_dict) or (None, None)"""
        if not token:
            return None, None
        with self._lock, self._conn() as c:
            r = c.execute('SELECT * FROM events WHERE event_invite_token = ?', (token,)).fetchone()
            if r:
                return 'event', dict(r)
            r = c.execute('''
                SELECT teams.*, events.id AS e_id, events.name AS e_name,
                       events.slug AS e_slug, events.owner_twitch_id AS e_owner
                FROM teams JOIN events ON teams.event_id = events.id
                WHERE teams.invite_token = ?
            ''', (token,)).fetchone()
            if r:
                d = dict(r)
                return 'team', d
            return None, None

    def join_via_invite(self, token, wot_name):
        kind, info = self.resolve_invite(token)
        if not kind:
            return None, 'Einladungslink ungueltig.'
        wot_name = (wot_name or '').strip()
        if not wot_name:
            return None, 'WoT-Name darf nicht leer sein.'
        event_id = info['id'] if kind == 'event' else info['event_id']
        team_id  = info['id'] if kind == 'team'  else None

        with self._lock, self._conn() as c:
            existing = c.execute(
                'SELECT * FROM streamers WHERE event_id = ? AND wot_name = ?',
                (event_id, wot_name)).fetchone()
            if existing:
                streamer_token = existing['token']
                c.execute('UPDATE streamers SET team_id = ?, active = 1 WHERE token = ?',
                          (team_id, streamer_token))
            else:
                streamer_token = _new_uuid()
                c.execute('''
                    INSERT INTO streamers (token, event_id, team_id, wot_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (streamer_token, event_id, team_id, wot_name, _now_iso()))

            event = c.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
            team  = c.execute('SELECT * FROM teams WHERE id = ?', (team_id,)).fetchone() if team_id else None
            return {
                'streamer_token': streamer_token,
                'event': dict(event),
                'team':  dict(team) if team else None,
            }, 'OK'

    # ── Damage ────────────────────────────────────────────────────────────────

    def record_damage(self, streamer_token, damage, key=None):
        damage = int(damage)
        if damage <= 0:
            return False, 0
        with self._lock, self._conn() as c:
            # Idempotency cleanup
            now = time.time()
            c.execute('DELETE FROM idempotency WHERE created < ?', (now - 60,))
            if key:
                try:
                    c.execute('INSERT INTO idempotency (key, created) VALUES (?, ?)',
                              (key, now))
                except sqlite3.IntegrityError:
                    return True, 0  # already counted

            s = c.execute('SELECT * FROM streamers WHERE token = ?',
                          (streamer_token,)).fetchone()
            if not s or not s['active']:
                return False, 0
            ev = c.execute('SELECT * FROM events WHERE id = ?', (s['event_id'],)).fetchone()
            if not ev or ev['paused']:
                return False, max(0, int(ev['goal'] - ev['total_dealt'])) if ev else 0

            new_total = ev['total_dealt'] + damage
            c.execute('UPDATE events SET total_dealt = ? WHERE id = ?',
                      (new_total, ev['id']))
            c.execute('UPDATE streamers SET damage = damage + ?, last_seen = ? WHERE token = ?',
                      (damage, _now_iso(), streamer_token))
            if s['team_id']:
                c.execute('UPDATE teams SET damage = damage + ? WHERE id = ?',
                          (damage, s['team_id']))
            remaining = max(0, int(ev['goal'] - new_total))
            c.execute('''
                INSERT INTO event_log (event_id, t, wot_name, team_id, damage, remaining)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ev['id'], datetime.now().strftime('%H:%M:%S'),
                  s['wot_name'], s['team_id'], damage, remaining))
            # Trim log to last 200 per event
            c.execute('''
                DELETE FROM event_log WHERE event_id = ? AND id NOT IN (
                    SELECT id FROM event_log WHERE event_id = ? ORDER BY id DESC LIMIT 200
                )
            ''', (ev['id'], ev['id']))
            return True, remaining

    # ── Snapshots ─────────────────────────────────────────────────────────────

    def get_event_state(self, event_id, base_url=''):
        with self._lock, self._conn() as c:
            ev = c.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
            if not ev:
                return None
            teams = c.execute('SELECT * FROM teams WHERE event_id = ? ORDER BY position',
                              (event_id,)).fetchall()
            streamers = c.execute('SELECT * FROM streamers WHERE event_id = ?',
                                  (event_id,)).fetchall()
            logs = c.execute('SELECT * FROM event_log WHERE event_id = ? ORDER BY id DESC LIMIT 30',
                             (event_id,)).fetchall()

            owner = c.execute('SELECT * FROM users WHERE twitch_id = ?',
                              (ev['owner_twitch_id'],)).fetchone()

            base = base_url.rstrip('/') if base_url else ''
            teams_out = []
            for t in teams:
                teams_out.append({
                    'id':           t['id'],
                    'name':         t['name'],
                    'color':        t['color'],
                    'damage':       int(t['damage']),
                    'invite_token': t['invite_token'],
                    'invite_url':   '{}/join/{}'.format(base, t['invite_token']) if base else None,
                    'members':      [s['wot_name'] for s in streamers if s['team_id'] == t['id']],
                })

            streamers_map = {}
            for s in streamers:
                streamers_map[s['wot_name']] = {
                    'team_id':   s['team_id'],
                    'damage':    int(s['damage']),
                    'last_seen': s['last_seen'],
                    'active':    bool(s['active']),
                }

            log_out = [dict(l) for l in logs]
            for entry in log_out:
                entry['streamer'] = entry['wot_name']  # alias for frontend compat

            return {
                'event': {
                    'id':           ev['id'],
                    'slug':         ev['slug'],
                    'name':         ev['name'],
                    'goal':         int(ev['goal']),
                    'mode':         ev['mode'],
                    'paused':       bool(ev['paused']),
                    'total_dealt':  int(ev['total_dealt']),
                    'remaining':    max(0, int(ev['goal'] - ev['total_dealt'])),
                    'invite_token': ev['event_invite_token'],
                    'invite_url':   '{}/join/{}'.format(base, ev['event_invite_token']) if base else None,
                    'overlay_url':  '{}/overlay/{}'.format(base, ev['slug']) if base else None,
                    'owner': dict(owner) if owner else None,
                },
                'teams':     teams_out,
                'streamers': streamers_map,
                'event_log': log_out,
            }
