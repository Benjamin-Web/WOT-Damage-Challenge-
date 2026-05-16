"""
state.py — Mohjos DamageRace State Manager

Datenmodell:
- Ein aktives Event mit Name, Ziel, Modus (versus | coop), 2-4 Teams
- Teams haben Farbe, eigenen Damage-Counter, eigenen Invite-Token
- Streamer werden ueber Event- oder Team-Invite-Link registriert
- /damage Endpunkt nimmt Streamer-Name an und mappt auf dessen Team
"""
import secrets
import threading
import time
from datetime import datetime, timezone


# Default Team-Farben (Heist-Bot-Style: gold-tonal + akzent)
DEFAULT_COLORS = ['#ffd700', '#03dac6', '#ff6b6b', '#a78bfa']
DEFAULT_TEAM_NAMES = ['Team Gold', 'Team Cyan', 'Team Rot', 'Team Violett']


def _now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _new_token(prefix=''):
    return prefix + secrets.token_urlsafe(8)


class RaceState:
    def __init__(self):
        self._lock = threading.Lock()
        # Default-Event beim Start (leer, Admin konfiguriert spaeter)
        self.event = self._make_default_event()
        # Global Streamer-Registry: name -> {team_id, damage, last_seen, active}
        self.streamers = {}
        self.event_log = []
        self._seen_keys = {}

    # ── Event-Erstellung ─────────────────────────────────────────────────────

    def _make_default_event(self):
        return {
            'name':         'Mohjos DamageRace',
            'goal':         100000.0,
            'mode':         'coop',     # 'coop' | 'versus'
            'paused':       False,
            'created_at':   _now_iso(),
            'event_invite': _new_token('ev_'),
            'teams':        {},          # team_id -> Team-Dict
            'total_dealt':  0.0,
        }

    def create_event(self, name, goal, mode, team_specs):
        """
        team_specs: Liste von Dicts mit {name, color}
        Replaced das aktive Event komplett (kein History laut User-Wunsch).
        """
        mode = mode if mode in ('coop', 'versus') else 'coop'
        teams = {}
        for i, spec in enumerate(team_specs[:4]):
            tid = 'team_%d' % (i + 1)
            teams[tid] = {
                'id':           tid,
                'name':         (spec.get('name') or DEFAULT_TEAM_NAMES[i]).strip(),
                'color':        (spec.get('color') or DEFAULT_COLORS[i]).strip(),
                'damage':       0.0,
                'invite_token': _new_token('tm_'),
                'members':      [],
            }

        with self._lock:
            self.event = {
                'name':         (name or 'DamageRace').strip(),
                'goal':         float(goal) if goal else 100000.0,
                'mode':         mode,
                'paused':       False,
                'created_at':   _now_iso(),
                'event_invite': _new_token('ev_'),
                'teams':        teams,
                'total_dealt':  0.0,
            }
            self.streamers.clear()
            self.event_log.clear()
            self._seen_keys.clear()
        return True

    # ── Streamer / Invites ────────────────────────────────────────────────────

    def _find_team_by_token(self, token):
        for tid, team in self.event['teams'].items():
            if team['invite_token'] == token:
                return tid
        return None

    def resolve_invite(self, token):
        """Gibt (kind, info) zurueck. kind: 'event' | 'team' | None"""
        with self._lock:
            if not token:
                return None, None
            if token == self.event['event_invite']:
                return 'event', {'event_name': self.event['name']}
            tid = self._find_team_by_token(token)
            if tid:
                team = self.event['teams'][tid]
                return 'team', {'team_id': tid, 'team_name': team['name'],
                                'team_color': team['color'],
                                'event_name': self.event['name']}
        return None, None

    def join_via_invite(self, token, streamer_name):
        streamer_name = (streamer_name or '').strip()
        if not streamer_name:
            return False, 'Name darf nicht leer sein.'
        with self._lock:
            kind = None
            team_id = None
            if token == self.event['event_invite']:
                kind = 'event'
            else:
                team_id = self._find_team_by_token(token)
                if team_id:
                    kind = 'team'
            if not kind:
                return False, 'Einladungslink ungueltig.'

            existing = self.streamers.get(streamer_name)
            if existing and existing.get('team_id') and team_id and existing['team_id'] != team_id:
                # Streamer wechselt Team
                old_team_id = existing['team_id']
                if old_team_id in self.event['teams']:
                    members = self.event['teams'][old_team_id]['members']
                    if streamer_name in members:
                        members.remove(streamer_name)

            if not existing:
                self.streamers[streamer_name] = {
                    'team_id':   team_id,
                    'damage':    0.0,
                    'last_seen': None,
                    'active':    True,
                }
            else:
                existing['active'] = True
                if team_id:
                    existing['team_id'] = team_id

            if team_id:
                members = self.event['teams'][team_id]['members']
                if streamer_name not in members:
                    members.append(streamer_name)
                return True, 'Beitritt zu Team "{}" erfolgreich.'.format(
                    self.event['teams'][team_id]['name'])
            return True, 'Beitritt zum Event erfolgreich. Admin weist Team zu.'

    def assign_team(self, streamer_name, team_id):
        with self._lock:
            if streamer_name not in self.streamers:
                return False, 'Streamer unbekannt.'
            if team_id and team_id not in self.event['teams']:
                return False, 'Team unbekannt.'
            old = self.streamers[streamer_name].get('team_id')
            if old and old in self.event['teams']:
                m = self.event['teams'][old]['members']
                if streamer_name in m:
                    m.remove(streamer_name)
            self.streamers[streamer_name]['team_id'] = team_id
            if team_id:
                m = self.event['teams'][team_id]['members']
                if streamer_name not in m:
                    m.append(streamer_name)
        return True, 'Team zugewiesen.'

    def remove_streamer(self, name):
        with self._lock:
            if name not in self.streamers:
                return False, 'Streamer nicht gefunden.'
            self.streamers[name]['active'] = False
        return True, 'Streamer deaktiviert.'

    # ── Damage eintragen ──────────────────────────────────────────────────────

    def record_damage(self, streamer_name, damage, key=None):
        with self._lock:
            if self.event['paused']:
                return False, self._snapshot_remaining()

            # Auto-Register (ohne Team)
            if streamer_name not in self.streamers:
                self.streamers[streamer_name] = {
                    'team_id': None, 'damage': 0.0,
                    'last_seen': None, 'active': True}
            elif not self.streamers[streamer_name].get('active', True):
                return False, self._snapshot_remaining()

            # Idempotency (60s Fenster)
            if key:
                now = time.time()
                self._seen_keys = {k: t for k, t in self._seen_keys.items()
                                   if now - t < 60}
                if key in self._seen_keys:
                    return True, self._snapshot_remaining()
                self._seen_keys[key] = now

            damage = float(damage)
            s = self.streamers[streamer_name]
            s['damage']    += damage
            s['last_seen']  = _now_iso()
            self.event['total_dealt'] += damage
            tid = s.get('team_id')
            if tid and tid in self.event['teams']:
                self.event['teams'][tid]['damage'] += damage

            entry = {
                't':         datetime.now().strftime('%H:%M:%S'),
                'streamer':  streamer_name,
                'team_id':   tid,
                'damage':    int(damage),
                'remaining': int(self._global_remaining()),
            }
            self.event_log.append(entry)
            if len(self.event_log) > 200:
                self.event_log.pop(0)

            return True, self._snapshot_remaining()

    # ── Admin-Aktionen ────────────────────────────────────────────────────────

    def set_goal(self, goal):
        with self._lock:
            self.event['goal'] = float(goal)

    def set_pause(self, paused):
        with self._lock:
            self.event['paused'] = bool(paused)

    def reset(self, new_goal=None):
        with self._lock:
            self.event['total_dealt'] = 0.0
            for t in self.event['teams'].values():
                t['damage'] = 0.0
            for s in self.streamers.values():
                s['damage'] = 0.0
                s['last_seen'] = None
            self.event_log.clear()
            self._seen_keys.clear()
            if new_goal is not None:
                self.event['goal'] = float(new_goal)
            self.event['paused'] = False

    def regenerate_invite(self, scope, team_id=None):
        with self._lock:
            if scope == 'event':
                self.event['event_invite'] = _new_token('ev_')
                return self.event['event_invite']
            elif scope == 'team' and team_id in self.event['teams']:
                t = _new_token('tm_')
                self.event['teams'][team_id]['invite_token'] = t
                return t
        return None

    # ── Read-only Snapshots ───────────────────────────────────────────────────

    def _global_remaining(self):
        return max(0.0, self.event['goal'] - self.event['total_dealt'])

    def _snapshot_remaining(self):
        return int(self._global_remaining())

    def to_dict(self, base_url=''):
        with self._lock:
            teams_out = []
            for tid, t in self.event['teams'].items():
                remaining = max(0.0, self.event['goal'] - t['damage']) \
                    if self.event['mode'] == 'versus' else None
                teams_out.append({
                    'id':           tid,
                    'name':         t['name'],
                    'color':        t['color'],
                    'damage':       int(t['damage']),
                    'remaining':    int(remaining) if remaining is not None else None,
                    'members':      list(t['members']),
                    'invite_token': t['invite_token'],
                    'invite_url':   '{}/join/{}'.format(base_url.rstrip('/'),
                                                       t['invite_token']) if base_url else None,
                })

            return {
                'event': {
                    'name':         self.event['name'],
                    'goal':         int(self.event['goal']),
                    'mode':         self.event['mode'],
                    'paused':       self.event['paused'],
                    'total_dealt':  int(self.event['total_dealt']),
                    'remaining':    int(self._global_remaining()),
                    'invite_token': self.event['event_invite'],
                    'invite_url':   '{}/join/{}'.format(base_url.rstrip('/'),
                                                       self.event['event_invite']) if base_url else None,
                },
                'teams':     teams_out,
                'streamers': {
                    n: {
                        'team_id':   s.get('team_id'),
                        'damage':    int(s['damage']),
                        'last_seen': s.get('last_seen'),
                        'active':    s.get('active', True),
                    } for n, s in self.streamers.items()
                },
                'event_log': list(self.event_log[-30:]),
            }


# Alias fuer Imports
ChallengeState = RaceState
