import os
import sys
from functools import wraps

from flask import (Flask, request, jsonify, send_from_directory,
                   session, redirect, url_for)
from flask_cors import CORS

import config as cfg
from state import ChallengeState

_BASE       = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(__file__), '..'))
OVERLAY_DIR = os.path.join(_BASE, 'overlay')

app            = Flask(__name__, static_folder=OVERLAY_DIR)
app.secret_key = cfg.SESSION_SECRET
CORS(app, supports_credentials=True)

state = ChallengeState()
state.configure(cfg.INITIAL_GOAL, cfg.STREAMER_NAMES)


# ─── Auth-Helpers ─────────────────────────────────────────────────────────────

def _logged_in():
    return session.get('authenticated') is True


def _api_auth(data):
    """API-Calls: entweder Browser-Session oder secret-Parameter."""
    if _logged_in():
        return True
    if not cfg.ADMIN_SECRET:
        return True
    return data.get('secret') == cfg.ADMIN_SECRET


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _logged_in():
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


# ─── Login / Logout ───────────────────────────────────────────────────────────

@app.route('/login', methods=['GET'])
def login_page():
    if _logged_in():
        return redirect('/admin')
    return send_from_directory(OVERLAY_DIR, 'login.html')


@app.route('/login', methods=['POST'])
def login_post():
    data     = request.get_json(force=True, silent=True) or {}
    password = data.get('password', '')
    if password == cfg.ADMIN_SECRET:
        session.permanent = True
        session['authenticated'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Falsches Passwort'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ─── Mod-Endpunkt (oeffentlich) ───────────────────────────────────────────────

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
    return jsonify({'ok': ok, 'remaining': remaining})


# ─── Status (oeffentlich — OBS braucht das) ───────────────────────────────────

@app.route('/status')
def get_status():
    return jsonify(state.to_dict())


# ─── Admin-API (Session oder secret-Parameter) ────────────────────────────────

@app.route('/admin/set', methods=['POST'])
def admin_set():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
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
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    state.paused = bool(data.get('paused', True))
    return jsonify({'ok': True, 'paused': state.paused})


@app.route('/admin/streamers', methods=['POST'])
def admin_streamers():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403

    action = data.get('action')
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


@app.route('/admin/check-auth')
def check_auth():
    return jsonify({'authenticated': _logged_in()})


# ─── Static pages ─────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/overlay')
def serve_overlay():
    return send_from_directory(OVERLAY_DIR, 'index.html')


@app.route('/admin')
@login_required
def serve_admin():
    return send_from_directory(OVERLAY_DIR, 'admin.html')


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'remaining': state.to_dict()['remaining']})


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== BeastSync | Mohjo_beist ===')
    print('Admin:   http://localhost:{}/admin'.format(cfg.PORT))
    print('Overlay: http://localhost:{}/overlay'.format(cfg.PORT))
    print('===============================')
    app.run(host='0.0.0.0', port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)
