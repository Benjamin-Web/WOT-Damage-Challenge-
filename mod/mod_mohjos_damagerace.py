# mod_mohjos_damagerace.py
# Mohjos DamageRace — Community Damage Tracker for World of Tanks
# Ablageort: World_of_Tanks/mods/  (als mohjos_damagerace.wotmod)
# Config:    World_of_Tanks/res_mods/<version>/mods/damagerace/config.json

import os
import json
import uuid

import BigWorld
import Avatar

# ─── CONFIG ───────────────────────────────────────────────────────────────────

_MOD_NAME = 'DamageRace'

_CONFIG_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'mods', 'damagerace', 'config.json'
))

_DEFAULT_CONFIG = {
    'server_url': 'https://mohjos-damagerace.duckdns.org',
    'streamer_token': '',          # Eindeutiger Token vom Server (Multi-Tenant)
    'streamer_name':  '',          # Fallback fuer Single-Tenant-Mode
    'enabled': True,
    'send_interval_ms': 200,
    'allowed_arena_types': [1, 7],
}


def _load_config():
    try:
        with open(_CONFIG_PATH, 'r') as fh:
            loaded = json.load(fh)
        result = dict(_DEFAULT_CONFIG)
        result.update(loaded)
        BigWorld.logInfo(_MOD_NAME,
            'Config geladen: %s' % _CONFIG_PATH, None)
        return result
    except Exception as exc:
        BigWorld.logWarning(_MOD_NAME,
            'Config nicht gefunden (%s), nutze Defaults. Pfad: %s'
            % (exc, _CONFIG_PATH), None)
        return dict(_DEFAULT_CONFIG)


_cfg = _load_config()

# ─── STATE ────────────────────────────────────────────────────────────────────

_in_battle = [False]
_last_shot_target_id = [None]
_vehicle_hp_cache = {}
_pending_damage = [0]
_send_timer = [None]

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _player():
    try:
        return BigWorld.player()
    except Exception:
        return None


def _is_allowed_arena():
    allowed = _cfg.get('allowed_arena_types', [])
    if not allowed:
        return True
    try:
        p = _player()
        if p and hasattr(p, 'arena') and hasattr(p.arena, 'guiType'):
            return p.arena.guiType in allowed
    except Exception:
        pass
    return True


# ─── HOOK 1: showShotResults — eigener Schuss hat getroffen ───────────────────

_orig_showShotResults = Avatar.PlayerAvatar.showShotResults


def _hook_showShotResults(self, *args, **kwargs):
    _orig_showShotResults(self, *args, **kwargs)

    if not _in_battle[0] or not _cfg.get('enabled', True):
        return
    if not _is_allowed_arena():
        return

    try:
        if len(args) < 2:
            return
        shooter_id = args[0]
        target_id  = args[1]

        p = _player()
        if p is None or shooter_id != p.playerVehicleID:
            return

        _last_shot_target_id[0] = target_id
        target_entity = BigWorld.entities.get(target_id)
        if target_entity is not None and hasattr(target_entity, 'health'):
            _vehicle_hp_cache[target_id] = target_entity.health

    except Exception as exc:
        BigWorld.logWarning(_MOD_NAME, 'showShotResults hook error: %s' % exc, None)


Avatar.PlayerAvatar.showShotResults = _hook_showShotResults

# ─── HOOK 2: updateVehicleHealth — HP-Aenderung eines Fahrzeugs ───────────────

_orig_updateVehicleHealth = Avatar.PlayerAvatar.updateVehicleHealth


def _hook_updateVehicleHealth(self, vehicle_id, health, *args, **kwargs):
    old_hp = _vehicle_hp_cache.get(vehicle_id)
    _orig_updateVehicleHealth(self, vehicle_id, health, *args, **kwargs)

    if not _in_battle[0] or not _cfg.get('enabled', True):
        return
    if vehicle_id != _last_shot_target_id[0]:
        return
    if old_hp is None:
        _vehicle_hp_cache[vehicle_id] = health
        return

    _vehicle_hp_cache[vehicle_id] = health
    damage = int(old_hp) - int(health)

    if damage <= 0:
        return

    _pending_damage[0] += damage
    _schedule_send()


Avatar.PlayerAvatar.updateVehicleHealth = _hook_updateVehicleHealth

# ─── HTTP-VERSAND ─────────────────────────────────────────────────────────────

def _schedule_send():
    if _send_timer[0] is not None:
        try:
            BigWorld.cancelCallback(_send_timer[0])
        except Exception:
            pass
    interval = _cfg.get('send_interval_ms', 200) / 1000.0
    _send_timer[0] = BigWorld.callback(interval, _do_send)


def _do_send():
    _send_timer[0] = None
    damage = _pending_damage[0]
    if damage <= 0:
        return
    _pending_damage[0] = 0

    url   = _cfg['server_url'].rstrip('/') + '/damage'
    key   = str(uuid.uuid4())
    token = _cfg.get('streamer_token') or _cfg.get('streamer_name') or ''
    payload = json.dumps({
        'streamer_token': token,
        'damage':         damage,
        'key':            key,
    })

    def _on_response(data):
        if data is None:
            BigWorld.logWarning(_MOD_NAME,
                'HTTP POST fehlgeschlagen, Damage (%d) wird erneut versucht.' % damage, None)
            _pending_damage[0] += damage
            BigWorld.callback(5.0, _do_send)

    try:
        BigWorld.fetchURL(url, _on_response,
                          {'Content-Type': 'application/json'}, payload)
    except TypeError:
        try:
            BigWorld.fetchURL(url, _on_response,
                              'Content-Type: application/json\r\n', payload)
        except Exception:
            # Fallback: GET mit Query-Parametern
            get_url = '%s?streamer_token=%s&damage=%d&key=%s' % (
                url, token, damage, key)
            try:
                BigWorld.fetchURL(get_url, _on_response)
            except Exception as exc:
                BigWorld.logError(_MOD_NAME, 'fetchURL total failure: %s' % exc, None)


# ─── BATTLE LIFECYCLE ─────────────────────────────────────────────────────────

_ARENA_PERIOD_BATTLE     = 3
_ARENA_PERIOD_AFTERBATTLE = 4

_orig_onArenaPeriodChange = Avatar.PlayerAvatar.onArenaPeriodChange


def _hook_onArenaPeriodChange(self, period, *args, **kwargs):
    _orig_onArenaPeriodChange(self, period, *args, **kwargs)

    if period == _ARENA_PERIOD_BATTLE:
        if not _is_allowed_arena():
            BigWorld.logInfo(_MOD_NAME,
                'Arena-Typ nicht erlaubt — Damage wird nicht gezaehlt.', None)
            return
        _in_battle[0] = True
        _vehicle_hp_cache.clear()
        _last_shot_target_id[0] = None

        try:
            p = _player()
            if p and hasattr(p, 'arena'):
                for veh_id in p.arena.vehicles:
                    ent = BigWorld.entities.get(veh_id)
                    if ent is not None and hasattr(ent, 'health'):
                        _vehicle_hp_cache[veh_id] = ent.health
        except Exception as exc:
            BigWorld.logWarning(_MOD_NAME, 'HP-Cache Fehler: %s' % exc, None)

        BigWorld.logInfo(_MOD_NAME, 'Kampf gestartet — DamageRace aktiv.', None)

    elif period >= _ARENA_PERIOD_AFTERBATTLE:
        _in_battle[0] = False
        if _pending_damage[0] > 0:
            _do_send()
        BigWorld.logInfo(_MOD_NAME, 'Kampf beendet.', None)


Avatar.PlayerAvatar.onArenaPeriodChange = _hook_onArenaPeriodChange

# ─── INIT ─────────────────────────────────────────────────────────────────────

BigWorld.logInfo(_MOD_NAME,
    'Mohjos DamageRace geladen | Server: %s | Spieler: %s'
    % (_cfg['server_url'], _cfg['streamer_name']),
    None)
