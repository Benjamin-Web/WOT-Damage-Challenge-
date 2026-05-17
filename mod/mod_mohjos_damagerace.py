# Mohjos DamageRace -- community damage tracker for World of Tanks.
#
# Install location: World_of_Tanks/mods/<version>/mohjos_damagerace.wotmod
# Config location:  World_of_Tanks/res_mods/<version>/mods/damagerace/config.json
#
# The module hooks PlayerAvatar.showShotResults to identify the last target
# the player hit and PlayerAvatar.updateVehicleHealth to compute the actual
# damage delta. Damage events are debounced for `send_interval_ms` and pushed
# to the DamageRace server via BigWorld.fetchURL.

import json
import os
import uuid

import Avatar
import BigWorld

# ---------------------------------------------------------------------------
# Config

_MOD_NAME = 'DamageRace'

_CONFIG_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'mods', 'damagerace', 'config.json',
))

_DEFAULT_CONFIG = {
    'server_url':          'https://mohjos-damagerace.duckdns.org',
    'streamer_token':      '',    # multi-tenant identifier issued at join time
    'streamer_name':       '',    # legacy fallback for single-tenant setups
    'enabled':             True,
    'send_interval_ms':    200,
    'allowed_arena_types': [1, 7],
    'max_damage_per_send': 10000, # sanity clamp; protects against bad reads
}


def _load_config():
    try:
        with open(_CONFIG_PATH, 'r') as fh:
            loaded = json.load(fh)
        merged = dict(_DEFAULT_CONFIG)
        merged.update(loaded)
        BigWorld.logInfo(_MOD_NAME, 'Config loaded from %s' % _CONFIG_PATH, None)
        return merged
    except Exception as exc:
        BigWorld.logWarning(
            _MOD_NAME,
            'Config not found (%s); using defaults. Path: %s'
            % (exc, _CONFIG_PATH),
            None,
        )
        return dict(_DEFAULT_CONFIG)


_cfg = _load_config()

# ---------------------------------------------------------------------------
# Runtime state. Mutable closure containers because Python 2.7 lacks `nonlocal`.

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
# Hook 1: own shot landed on a target.

_orig_show_shot_results = Avatar.PlayerAvatar.showShotResults


def _hook_show_shot_results(self, *args, **kwargs):
    _orig_show_shot_results(self, *args, **kwargs)

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
        BigWorld.logWarning(_MOD_NAME, 'showShotResults hook error: %s' % exc, None)


Avatar.PlayerAvatar.showShotResults = _hook_show_shot_results


# ---------------------------------------------------------------------------
# Hook 2: vehicle health update -> compute damage delta.

_orig_update_vehicle_health = Avatar.PlayerAvatar.updateVehicleHealth


def _hook_update_vehicle_health(self, vehicle_id, health, *args, **kwargs):
    previous = _vehicle_hp_cache.get(vehicle_id)
    _orig_update_vehicle_health(self, vehicle_id, health, *args, **kwargs)

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
        BigWorld.logWarning(_MOD_NAME, 'Clamped implausible damage: %d -> %d'
                            % (damage, cap), None)
        damage = cap

    _pending_damage[0] += damage
    _schedule_send()


Avatar.PlayerAvatar.updateVehicleHealth = _hook_update_vehicle_health


# ---------------------------------------------------------------------------
# Outgoing HTTP.

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

    url = _cfg['server_url'].rstrip('/') + '/damage'
    key = str(uuid.uuid4())
    token = _cfg.get('streamer_token') or _cfg.get('streamer_name') or ''
    payload = json.dumps({
        'streamer_token': token,
        'damage':         damage,
        'key':            key,
    })

    def _on_response(data):
        # `data is None` indicates a network-level failure. Retry after 5s.
        if data is None:
            BigWorld.logWarning(
                _MOD_NAME,
                'HTTP POST failed; retrying %d damage in 5s.' % damage,
                None,
            )
            _pending_damage[0] += damage
            BigWorld.callback(5.0, _do_send)

    try:
        BigWorld.fetchURL(url, _on_response,
                          {'Content-Type': 'application/json'}, payload)
    except TypeError:
        # Older BigWorld signatures accept a header string instead of dict.
        try:
            BigWorld.fetchURL(url, _on_response,
                              'Content-Type: application/json\r\n', payload)
        except Exception:
            # Last-resort GET fallback.
            get_url = '%s?streamer_token=%s&damage=%d&key=%s' % (
                url, token, damage, key,
            )
            try:
                BigWorld.fetchURL(get_url, _on_response)
            except Exception as exc:
                BigWorld.logError(_MOD_NAME,
                                  'fetchURL failed entirely: %s' % exc, None)


# ---------------------------------------------------------------------------
# Battle lifecycle.

_ARENA_PERIOD_BATTLE = 3
_ARENA_PERIOD_AFTERBATTLE = 4

_orig_on_arena_period_change = Avatar.PlayerAvatar.onArenaPeriodChange


def _hook_on_arena_period_change(self, period, *args, **kwargs):
    _orig_on_arena_period_change(self, period, *args, **kwargs)

    if period == _ARENA_PERIOD_BATTLE:
        if not _is_allowed_arena():
            BigWorld.logInfo(_MOD_NAME,
                             'Arena type not allowed; damage will not be tracked.',
                             None)
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
            BigWorld.logWarning(_MOD_NAME, 'HP cache priming failed: %s' % exc, None)

        BigWorld.logInfo(_MOD_NAME, 'Battle started -- DamageRace active.', None)

    elif period >= _ARENA_PERIOD_AFTERBATTLE:
        _in_battle[0] = False
        if _pending_damage[0] > 0:
            _do_send()
        BigWorld.logInfo(_MOD_NAME, 'Battle ended.', None)


Avatar.PlayerAvatar.onArenaPeriodChange = _hook_on_arena_period_change


# ---------------------------------------------------------------------------
# Module init log.

BigWorld.logInfo(
    _MOD_NAME,
    'Mohjos DamageRace loaded | server=%s | name=%s'
    % (_cfg['server_url'], _cfg.get('streamer_name') or '(token only)'),
    None,
)
