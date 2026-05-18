# -*- coding: utf-8 -*-
# Mohjos DamageRace -- community damage tracker for World of Tanks 1.x / 2.x.
#
# Install location: World_of_Tanks/mods/<version>/mohjos_damagerace.wotmod
# Config location:  World_of_Tanks/res_mods/<version>/mods/damagerace/config.json
#
# WoT 2.x kept Python 2.7 as the runtime, but renamed two of the hooks we
# rely on:
#   * showShotResults stayed on PlayerAvatar (we use it to remember our
#     last target id).
#   * onArenaPeriodChange became name-mangled to
#     _PlayerAvatar__onArenaPeriodChange.
#   * Per-vehicle HP updates moved off PlayerAvatar entirely, onto the
#     Vehicle entity class as Vehicle.onHealthChanged.
#
# Every hook attaches behind a feature-detection guard so a missing
# attribute on an unfamiliar client never crashes the launcher.

import json
import os
import sys
import tempfile
import threading
import urllib2
import uuid

try:
    import Avatar
    import BigWorld
except Exception:
    Avatar = None
    BigWorld = None

try:
    from Vehicle import Vehicle as _VehicleClass
except Exception:
    _VehicleClass = None

try:
    _INT_TYPES = (int, long)  # noqa: F821 (long only exists on Py2)
except NameError:
    _INT_TYPES = (int,)


_MOD_NAME = 'DamageRace'
_DEBUG_LOG = os.path.join(tempfile.gettempdir(), 'damagerace_debug.log')


def _file_log(level, message):
    try:
        with open(_DEBUG_LOG, 'a') as fh:
            fh.write('[%s] %s\n' % (level, message))
    except Exception:
        pass


def _log_info(message):
    _file_log('INFO', message)
    try:
        BigWorld.logInfo(_MOD_NAME, message, None)
    except Exception:
        pass


def _log_warning(message):
    _file_log('WARN', message)
    try:
        BigWorld.logWarning(_MOD_NAME, message, None)
    except Exception:
        pass


def _log_error(message):
    _file_log('ERROR', message)
    try:
        BigWorld.logError(_MOD_NAME, message, None)
    except Exception:
        pass


_file_log('INFO', 'Module imported. Python=%s BigWorld=%s Avatar=%s Vehicle=%s'
          % (sys.version.split()[0],
             'yes' if BigWorld is not None else 'no',
             'yes' if Avatar is not None else 'no',
             'yes' if _VehicleClass is not None else 'no'))


# ---------------------------------------------------------------------------
# Config discovery.

def _resolve_config_path():
    try:
        cursor = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return None
    for _ in range(12):
        try:
            if os.path.isfile(os.path.join(cursor, 'WorldOfTanks.exe')):
                res_mods = os.path.join(cursor, 'res_mods')
                if os.path.isdir(res_mods):
                    try:
                        versions = sorted(
                            [d for d in os.listdir(res_mods)
                             if os.path.isdir(os.path.join(res_mods, d))
                             and d[:1].isdigit()],
                            reverse=True,
                        )
                    except OSError:
                        versions = []
                    for version in versions:
                        candidate = os.path.join(res_mods, version,
                                                 'mods', 'damagerace',
                                                 'config.json')
                        if os.path.isfile(candidate):
                            return candidate
                return None
        except Exception:
            return None
        parent = os.path.dirname(cursor)
        if parent == cursor:
            return None
        cursor = parent
    return None


_DEFAULT_CONFIG = {
    'server_url':          'https://mohjos-damagerace.duckdns.org',
    'streamer_token':      '',
    'streamer_name':       '',
    'enabled':             True,
    'send_interval_ms':    200,
    'allowed_arena_types': [1, 7],
    'max_damage_per_send': 10000,
}


def _load_config():
    path = _resolve_config_path()
    if not path:
        _log_warning('Could not locate config.json; using defaults.')
        return dict(_DEFAULT_CONFIG)
    try:
        with open(path, 'r') as fh:
            loaded = json.load(fh)
        merged = dict(_DEFAULT_CONFIG)
        merged.update(loaded)
        _log_info('Config loaded from %s' % path)
        return merged
    except Exception as exc:
        _log_warning('Failed to read config (%s); using defaults. Path: %s'
                     % (exc, path))
        return dict(_DEFAULT_CONFIG)


_cfg = _load_config()

_in_battle = [False]
_last_shot_target_id = [None]
_vehicle_hp_cache = {}
_pending_damage = [0]
_send_timer = [None]


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
        player = _player()
        if player and hasattr(player, 'arena') and hasattr(player.arena, 'guiType'):
            return player.arena.guiType in allowed
    except Exception:
        pass
    return True


# ---------------------------------------------------------------------------
# Outgoing HTTP.

def _schedule_send():
    if _send_timer[0] is not None:
        try:
            BigWorld.cancelCallback(_send_timer[0])
        except Exception:
            pass
    try:
        interval = float(_cfg.get('send_interval_ms', 200)) / 1000.0
        _send_timer[0] = BigWorld.callback(interval, _do_send)
    except Exception as exc:
        _log_warning('callback scheduling failed: %s' % exc)


def _do_send():
    _send_timer[0] = None
    damage = _pending_damage[0]
    if damage <= 0:
        return
    _pending_damage[0] = 0

    try:
        url = _cfg['server_url'].rstrip('/') + '/damage'
        key = str(uuid.uuid4())
        token = _cfg.get('streamer_token') or _cfg.get('streamer_name') or ''
        payload = json.dumps({
            'streamer_token': token,
            'damage':         damage,
            'key':            key,
        })
    except Exception as exc:
        _log_error('payload build failed: %s' % exc)
        return

    def _worker():
        try:
            req = urllib2.Request(
                url,
                data=payload,
                headers={'Content-Type': 'application/json'},
            )
            resp = urllib2.urlopen(req, timeout=5)
            body = resp.read()
            _file_log('TRACE', 'urllib2 status=%s body=%r'
                      % (resp.getcode(), body[:200]))
            _log_info('Posted damage=%d' % damage)
        except Exception as exc:
            _file_log('ERROR', 'urllib2 POST failed: %s' % exc)
            # Re-queue on the main thread.
            def _requeue():
                _pending_damage[0] += damage
                try:
                    BigWorld.callback(5.0, _do_send)
                except Exception:
                    pass
            try:
                BigWorld.callback(0.0, _requeue)
            except Exception:
                pass

    t = threading.Thread(target=_worker)
    t.daemon = True
    t.start()


# ---------------------------------------------------------------------------
# Hook installation.

_ARENA_PERIOD_BATTLE = 3
_ARENA_PERIOD_AFTERBATTLE = 4

# WoT 2.x renamed onArenaPeriodChange to a name-mangled private method.
# Try the public name first (older clients) and fall back to the mangled
# variant.
_ARENA_PERIOD_ATTRS = ('onArenaPeriodChange',
                       '_PlayerAvatar__onArenaPeriodChange')


def _find_attr(target, names):
    for name in names:
        if hasattr(target, name):
            return name
    return None


def _extract_shot_target(args):
    """Pull the vehicle id out of WoT's showShotResults arguments.

    WoT 2.x calls the hook with a single PyArrayDataInstance whose entries
    are dict-like objects exposing a `vehicleID` field. Legacy clients
    pass (shooter_id, target_id, ...). We accept both."""
    if not args:
        return None
    if len(args) >= 2 and isinstance(args[0], _INT_TYPES):
        player = _player()
        if player is None or args[0] != player.playerVehicleID:
            return None
        return args[1]
    head = args[0]
    if not head:
        return None
    try:
        entry = head[0]
    except Exception:
        return None
    for accessor in (
        lambda e: e['vehicleID'],
        lambda e: getattr(e, 'vehicleID'),
        lambda e: e.get('vehicleID'),
    ):
        try:
            value = accessor(entry)
        except Exception:
            continue
        if isinstance(value, _INT_TYPES):
            return value
    return None


def _install_player_avatar_hooks():
    if Avatar is None or not hasattr(Avatar, 'PlayerAvatar'):
        _log_error('Avatar.PlayerAvatar unavailable; player hooks skipped.')
        return

    cls = Avatar.PlayerAvatar

    # showShotResults -- remember the last enemy id we hit.
    if hasattr(cls, 'showShotResults'):
        orig = cls.showShotResults

        def hook_show_shot_results(self, *args, **kwargs):
            orig(self, *args, **kwargs)
            if not _in_battle[0] or not _cfg.get('enabled', True):
                return
            if not _is_allowed_arena():
                return
            try:
                target_id = _extract_shot_target(args)
                if target_id is not None:
                    _last_shot_target_id[0] = target_id
                    _file_log('INFO', 'Shot landed on target=%s' % target_id)
            except Exception as exc:
                _log_warning('showShotResults hook error: %s' % exc)

        cls.showShotResults = hook_show_shot_results
        _log_info('Hook installed: PlayerAvatar.showShotResults')
    else:
        _log_warning('PlayerAvatar.showShotResults missing.')

    # Arena period change -- battle start / end.
    arena_attr = _find_attr(cls, _ARENA_PERIOD_ATTRS)
    if arena_attr:
        orig_period = getattr(cls, arena_attr)

        def hook_arena_period(self, period, *args, **kwargs):
            orig_period(self, period, *args, **kwargs)
            try:
                if period == _ARENA_PERIOD_BATTLE:
                    if not _is_allowed_arena():
                        _log_info('Arena type filtered out.')
                        return
                    _in_battle[0] = True
                    _vehicle_hp_cache.clear()
                    _last_shot_target_id[0] = None
                    _log_info('Battle started -- DamageRace active.')
                elif period >= _ARENA_PERIOD_AFTERBATTLE:
                    _in_battle[0] = False
                    if _pending_damage[0] > 0:
                        _do_send()
                    _log_info('Battle ended.')
            except Exception as exc:
                _log_warning('arena period hook error: %s' % exc)

        setattr(cls, arena_attr, hook_arena_period)
        _log_info('Hook installed: PlayerAvatar.%s' % arena_attr)
    else:
        _log_warning('PlayerAvatar.onArenaPeriodChange variants missing.')


def _install_vehicle_hooks():
    if _VehicleClass is None:
        _log_warning('Vehicle class unavailable; damage tracking limited.')
        return

    if hasattr(_VehicleClass, 'onHealthChanged'):
        orig = _VehicleClass.onHealthChanged

        def hook_on_health_changed(self, new_health, *args, **kwargs):
            previous = _vehicle_hp_cache.get(self.id)
            orig(self, new_health, *args, **kwargs)
            try:
                _file_log('TRACE',
                          'onHealthChanged vehicle=%s prev=%s new=%s lastTarget=%s'
                          % (self.id, previous, new_health, _last_shot_target_id[0]))
                _vehicle_hp_cache[self.id] = new_health
                if not _in_battle[0] or not _cfg.get('enabled', True):
                    return
                if self.id != _last_shot_target_id[0]:
                    return
                if previous is None:
                    return
                damage = int(previous) - int(new_health)
                if damage <= 0:
                    return
                cap = _cfg.get('max_damage_per_send', 10000)
                if cap and damage > cap:
                    _log_warning('Clamped implausible damage: %d -> %d'
                                 % (damage, cap))
                    damage = cap
                _pending_damage[0] += damage
                _file_log('INFO', 'Recorded damage=%d on target=%s'
                          % (damage, self.id))
                _schedule_send()
            except Exception as exc:
                _log_warning('onHealthChanged hook error: %s' % exc)

        _VehicleClass.onHealthChanged = hook_on_health_changed
        _log_info('Hook installed: Vehicle.onHealthChanged')
    else:
        _log_warning('Vehicle.onHealthChanged missing.')


try:
    _install_player_avatar_hooks()
    _install_vehicle_hooks()
    _log_info('Mohjos DamageRace loaded | server=%s | name=%s'
              % (_cfg.get('server_url', ''),
                 _cfg.get('streamer_name') or '(token only)'))
except Exception as exc:
    _log_error('Mod initialization failed: %s' % exc)
