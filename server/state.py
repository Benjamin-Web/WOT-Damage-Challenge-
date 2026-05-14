import threading
import time
from datetime import datetime, timezone


class ChallengeState:
    def __init__(self):
        self._lock = threading.Lock()
        self.goal = 100000.0
        self.total_dealt = 0.0
        self.paused = False
        self.streamers = {}          # name -> {damage, last_seen, active}
        self.event_log = []
        self._seen_keys = {}         # idempotency: key -> timestamp

    def configure(self, goal, streamer_names):
        with self._lock:
            self.goal = float(goal)
            for name in streamer_names:
                if name not in self.streamers:
                    self.streamers[name] = {
                        'damage': 0.0, 'last_seen': None, 'active': True}

    # ── Streamer verwalten ────────────────────────────────────────────────────

    def add_streamer(self, name):
        name = name.strip()
        if not name:
            return False, 'Name darf nicht leer sein.'
        with self._lock:
            if name in self.streamers:
                # Reaktivieren falls vorher deaktiviert
                self.streamers[name]['active'] = True
                return True, 'Streamer reaktiviert.'
            self.streamers[name] = {'damage': 0.0, 'last_seen': None, 'active': True}
        return True, 'Streamer hinzugefuegt.'

    def remove_streamer(self, name):
        with self._lock:
            if name not in self.streamers:
                return False, 'Streamer nicht gefunden.'
            # Nur deaktivieren (Damage-History behalten)
            self.streamers[name]['active'] = False
        return True, 'Streamer deaktiviert.'

    def is_registered(self, name):
        with self._lock:
            entry = self.streamers.get(name)
            return entry is not None and entry.get('active', True)

    # ── Damage eintragen ──────────────────────────────────────────────────────

    def record_damage(self, streamer_name, damage, key=None):
        """Gibt (success, remaining) zurueck."""
        with self._lock:
            if self.paused:
                return False, self._remaining()

            # Auto-Register: unbekannte Streamer werden beim ersten Damage eingetragen
            # (verhindert, dass der Veranstalter jeden Namen vorab tippen muss)
            if streamer_name not in self.streamers:
                self.streamers[streamer_name] = {
                    'damage': 0.0, 'last_seen': None, 'active': True}
            elif not self.streamers[streamer_name].get('active', True):
                return False, self._remaining()

            # Idempotency
            if key:
                now = time.time()
                self._seen_keys = {k: t for k, t in self._seen_keys.items()
                                   if now - t < 60}
                if key in self._seen_keys:
                    return True, self._remaining()
                self._seen_keys[key] = now

            damage = float(damage)
            self.total_dealt += damage
            self.streamers[streamer_name]['damage'] += damage
            self.streamers[streamer_name]['last_seen'] = (
                datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

            entry = {
                't':         datetime.now().strftime('%H:%M:%S'),
                'streamer':  streamer_name,
                'damage':    int(damage),
                'remaining': int(self._remaining()),
            }
            self.event_log.append(entry)
            if len(self.event_log) > 200:
                self.event_log.pop(0)

            return True, self._remaining()

    # ── Reset / Helpers ───────────────────────────────────────────────────────

    def reset(self, new_goal=None):
        with self._lock:
            self.total_dealt = 0.0
            for name in self.streamers:
                self.streamers[name]['damage'] = 0.0
                self.streamers[name]['last_seen'] = None
            self.event_log.clear()
            self._seen_keys.clear()
            if new_goal is not None:
                self.goal = float(new_goal)
            self.paused = False

    def _remaining(self):
        return max(0.0, self.goal - self.total_dealt)

    def to_dict(self):
        with self._lock:
            return {
                'remaining':   int(self._remaining()),
                'goal':        int(self.goal),
                'total_dealt': int(self.total_dealt),
                'paused':      self.paused,
                'streamers':   {
                    name: dict(info)
                    for name, info in self.streamers.items()
                },
                'event_log': list(self.event_log[-30:]),
            }
