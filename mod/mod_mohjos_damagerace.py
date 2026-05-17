# Mohjos DamageRace -- community damage tracker for World of Tanks.
#
# Install location: World_of_Tanks/mods/<version>/mohjos_damagerace.wotmod
# Config location:  World_of_Tanks/res_mods/<version>/mods/damagerace/config.json
#
# This file is shipped as plain Python source inside the .wotmod archive so
# WoT compiles it with its own interpreter (Python 3.8 on 2.x clients, 2.7
# on 1.x clients). All module-level work is guarded so a defective install
# never crashes the game.

import json
import os
import uuid

try:
    import Avatar
    import BigWorld
except Exception:  # pragma: no cover - only meaningful inside WoT
    Avatar = None
    BigWorld = None


_MOD_NAME = 'DamageRace'


def _log_info(message):
    try:
        BigWorld.logInfo(_MOD_NAME, message, None)
    except Exception:
        pass


def _log_warning(message):
    try:
        BigWorld.logWarning(_MOD_NAME, message, None)
    except Exception:
        pass


def _log_error(message):
    try:
        BigWorld.logError(_MOD_NAME, message, None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Config discovery.

def _resolve_config_path():
    """Walk up from this file until we reach a directory that contains
    WorldOfTanks.exe, then return the newest matching config under
    res_mods/<version>/mods/damagerace/config.json."""
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

# Mutable closure containers; classic WoT mod pattern that stays compatible
# with both Python 2.7 (1.x clients) and 3.8 (2.x clients).
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

    def _on_response(data):
        if data is None:
            _log_warning('HTTP POST failed; retrying %d damage in 5s.' % damage)
            _pending_damage[0] += damage
            try:
                BigWorld.callback(5.0, _do_send)
            except Exception:
                pass

    try:
        BigWorld.fetchURL(url, _on_response,
                          {'Content-Type': 'application/json'}, payload)
    except TypeError:
        try:
            BigWorld.fetchURL(url, _on_response,
                              'Content-Type: application/json\r\n', payload)
        except Exception:
            get_url = '%s?streamer_token=%s&damage=%d&key=%s' % (
                url, token, damage, key,
            )
            try:
                BigWorld.fetchURL(get_url, _on_response)
            except Exception as exc:
                _log_error('fetchURL failed entirely: %s' % exc)
    except Exception as exc:
        _log_error('fetchURL crashed: %s' % exc)


# ---------------------------------------------------------------------------
# Hook installation. Every patch is wrapped so a missing attribute on a
# given WoT release degrades gracefully instead of crashing the launcher.

_ARENA_PERIOD_BATTLE = 3
_ARENA_PERIOD_AFTERBATTLE = 4


def _install_hooks():
    if Avatar is None or BigWorld is None:
        return

    if not hasattr(Avatar, 'PlayerAvatar'):
        _log_error('Avatar.PlayerAvatar missing; aborting hook install.')
        return

    player_avatar = Avatar.PlayerAvatar

    if hasattr(player_avatar, 'showShotResults'):
        orig_show_shot_results = player_avatar.showShotResults

        def hook_show_shot_results(self, *args, **kwargs):
            orig_show_shot_results(self, *args, **kwargs)
            if not _in_battle[0] or not _cfg.get('enabled', True):
                return
            if not _is_allowed_arena():
                return
            try:
                if len(args) < 2:
                    return
                shooter_id, target_id = args[0], args[1]
                player = _player()
                if player is None or shooter_id != player.playerVehicleID:
                    return
                _last_shot_target_id[0] = target_id
                target = BigWorld.entities.get(target_id)
                if target is not None and hasattr(target, 'health'):
                    _vehicle_hp_cache[target_id] = target.health
            except Exception as exc:
                _log_warning('showShotResults hook error: %s' % exc)

        player_avatar.showShotResults = hook_show_shot_results

    if hasattr(player_avatar, 'updateVehicleHealth'):
        orig_update_health = player_avatar.updateVehicleHealth

        def hook_update_health(self, vehicle_id, health, *args, **kwargs):
            previous = _vehicle_hp_cache.get(vehicle_id)
            orig_update_health(self, vehicle_id, health, *args, **kwargs)
            if not _in_battle[0] or not _cfg.get('enabled', True):
                return
            if vehicle_id != _last_shot_target_id[0]:
                return
            if previous is None:
                _vehicle_hp_cache[vehicle_id] = health
                return
            _vehicle_hp_cache[vehicle_id] = health
            try:
                damage = int(previous) - int(health)
            except (TypeError, ValueError):
                return
            if damage <= 0:
                return
            cap = _cfg.get('max_damage_per_send', 10000)
            if cap and damage > cap:
                _log_warning('Clamped implausible damage: %d -> %d'
                             % (damage, cap))
                damage = cap
            _pending_damage[0] += damage
            _schedule_send()

        player_avatar.updateVehicleHealth = hook_update_health

    if hasattr(player_avatar, 'onArenaPeriodChange'):
        orig_period_change = player_avatar.onArenaPeriodChange

        def hook_period_change(self, period, *args, **kwargs):
            orig_period_change(self, period, *args, **kwargs)
            if period == _ARENA_PERIOD_BATTLE:
                if not _is_allowed_arena():
                    _log_info('Arena type not allowed; damage will not be tracked.')
                    return
                _in_battle[0] = True
                _vehicle_hp_cache.clear()
                _last_shot_target_id[0] = None
                try:
                    player = _player()
                    if player and hasattr(player, 'arena'):
                        for vehicle_id in player.arena.vehicles:
                            entity = BigWorld.entities.get(vehicle_id)
                            if entity is not None and hasattr(entity, 'health'):
                                _vehicle_hp_cache[vehicle_id] = entity.health
                except Exception as exc:
                    _log_warning('HP cache priming failed: %s' % exc)
                _log_info('Battle started -- DamageRace active.')
            elif period >= _ARENA_PERIOD_AFTERBATTLE:
                _in_battle[0] = False
                if _pending_damage[0] > 0:
                    _do_send()
                _log_info('Battle ended.')

        player_avatar.onArenaPeriodChange = hook_period_change


try:
    _install_hooks()
    _log_info('Mohjos DamageRace loaded | server=%s | name=%s'
              % (_cfg.get('server_url', ''),
                 _cfg.get('streamer_name') or '(token only)'))
except Exception as exc:
    _log_error('Mod initialization failed: %s' % exc)
