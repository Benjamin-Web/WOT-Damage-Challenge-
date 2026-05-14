import os
import sys

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import config as cfg
from state import ChallengeState

_BASE       = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(__file__), '..'))
OVERLAY_DIR = os.path.join(_BASE, 'overlay')

app   = Flask(__name__, static_folder=OVERLAY_DIR)
CORS(app)
state = ChallengeState()
state.configure(cfg.INITIAL_GOAL, cfg.STREAMER_NAMES)


def _auth(data):
    if not cfg.ADMIN_SECRET:
        return True
    return data.get('secret') == cfg.ADMIN_SECRET


# ─── Mod-Endpunkte ────────────────────────────────────────────────────────────

@app.route('/damage', methods=['POST', 'GET'])
def post_damage():
    if request.method == 'POST':
        data     = request.get_json(force=True, silent=True) or {}
        streamer = str(data.get('streamer', '')).strip()
        raw      = data.get('damage', 0)
        key      = data.get('key')
    else:
        streamer = request.args.get('streamer', '').strip()
        raw      = request.args.get('damage', 0)
        key      = request.args.get('key')

    try:
        damage = int(float(raw))
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'invalid damage'}), 400

    if damage <= 0:
        return jsonify({'ok': False, 'error': 'damage must be positive'}), 400

    ok, remaining = state.record_damage(streamer, damage, key=key)
    if not ok:
        return jsonify({'ok': False, 'error': 'rejected', 'remaining': remaining})
    return jsonify({'ok': True, 'remaining': remaining})


# ─── OBS / Status ─────────────────────────────────────────────────────────────

@app.route('/status')
def get_status():
    return jsonify(state.to_dict())


# ─── Admin ────────────────────────────────────────────────────────────────────

@app.route('/admin/set', methods=['POST'])
def admin_set():
    data = request.get_json(force=True, silent=True) or {}
    if not _auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    new_goal = data.get('goal')
    if bool(data.get('reset', False)):
        state.reset(new_goal=new_goal)
    elif new_goal is not None:
        with state._lock:
            state.goal = float(new_goal)

    return jsonify({'ok': True, 'state': state.to_dict()})


@app.route('/admin/pause', methods=['POST'])
def admin_pause():
    data = request.get_json(force=True, silent=True) or {}
    if not _auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    state.paused = bool(data.get('paused', True))
    return jsonify({'ok': True, 'paused': state.paused})


@app.route('/admin/streamers', methods=['POST'])
def admin_streamers():
    """Streamer hinzufuegen oder entfernen — live, kein Serverneustart noetig."""
    data = request.get_json(force=True, silent=True) or {}
    if not _auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    action = data.get('action')   # 'add' | 'remove'
    name   = str(data.get('name', '')).strip()

    if not name:
        return jsonify({'ok': False, 'error': 'name required'}), 400

    if action == 'add':
        ok, msg = state.add_streamer(name)
    elif action == 'remove':
        ok, msg = state.remove_streamer(name)
    else:
        return jsonify({'ok': False, 'error': 'action must be add or remove'}), 400

    return jsonify({'ok': ok, 'message': msg, 'state': state.to_dict()})


# ─── Static pages ─────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/overlay')
def serve_overlay():
    return send_from_directory(OVERLAY_DIR, 'index.html')


@app.route('/admin')
def serve_admin():
    return send_from_directory(OVERLAY_DIR, 'admin.html')


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== BeastSync | Mohjo_beist ===')
    print('Ziel:          {:,}'.format(int(cfg.INITIAL_GOAL)))
    print('Admin-Panel:   http://localhost:{}/admin'.format(cfg.PORT))
    print('OBS-Overlay:   http://localhost:{}/overlay'.format(cfg.PORT))
    print('===============================')
    app.run(host='0.0.0.0', port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)
