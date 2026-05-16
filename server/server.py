"""
server.py — Mohjos DamageRace Flask-Server

Endpunkte:
  /              Overlay (oeffentlich, fuer OBS)
  /overlay       Overlay (alias)
  /admin         Admin-Panel (Login erforderlich)
  /login         Login-Seite (GET/POST)
  /logout        Logout
  /join/<token>  Beitritts-Seite (Streamer)
  /api/event     GET = aktueller Stand (oeffentlich)
  /damage        POST/GET = Mod meldet Damage
  /api/invite/<token>  GET = Invite-Info (fuer Join-Page)
  /api/join     POST = Streamer beitritt via Token
  /admin/event  POST = neues Event erstellen
  /admin/set    POST = Ziel setzen / Reset
  /admin/pause  POST = Pause toggeln
  /admin/streamer  POST = Team zuweisen / entfernen
  /admin/invite/regenerate  POST = Invite-Token neu generieren
  /health
"""
import os
import sys
from functools import wraps

from flask import (Flask, request, jsonify, send_from_directory,
                   session, redirect)
from flask_cors import CORS

import config as cfg
from state import RaceState

_BASE       = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(__file__), '..'))
OVERLAY_DIR = os.path.join(_BASE, 'overlay')

app            = Flask(__name__, static_folder=OVERLAY_DIR)
app.secret_key = cfg.SESSION_SECRET
CORS(app, supports_credentials=True)

state = RaceState()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base_url():
    if cfg.PUBLIC_BASE_URL:
        return cfg.PUBLIC_BASE_URL.rstrip('/')
    return request.host_url.rstrip('/')


def _logged_in():
    return session.get('authenticated') is True


def _api_auth(data):
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

    if not streamer:
        return jsonify({'ok': False, 'error': 'streamer required'}), 400

    try:
        damage = int(float(raw))
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'invalid damage'}), 400

    if damage <= 0:
        return jsonify({'ok': False, 'error': 'damage must be positive'}), 400

    ok, remaining = state.record_damage(streamer, damage, key=key)
    return jsonify({'ok': ok, 'remaining': remaining})


# ─── Status / Event-Info ──────────────────────────────────────────────────────

@app.route('/api/event')
@app.route('/status')
def get_status():
    return jsonify(state.to_dict(base_url=_base_url()))


# ─── Invite + Join ────────────────────────────────────────────────────────────

@app.route('/join/<token>')
def join_page(token):
    # Token in Session schreiben, damit join.html ihn lesen kann (oder per URL)
    return send_from_directory(OVERLAY_DIR, 'join.html')


@app.route('/api/invite/<token>')
def api_invite_info(token):
    kind, info = state.resolve_invite(token)
    if not kind:
        return jsonify({'ok': False, 'error': 'Einladungslink ungueltig'}), 404
    return jsonify({'ok': True, 'kind': kind, 'info': info})


@app.route('/api/join', methods=['POST'])
def api_join():
    data     = request.get_json(force=True, silent=True) or {}
    token    = (data.get('token') or '').strip()
    streamer = (data.get('streamer') or '').strip()
    if not token or not streamer:
        return jsonify({'ok': False, 'error': 'token + streamer erforderlich'}), 400
    ok, msg = state.join_via_invite(token, streamer)
    return jsonify({'ok': ok, 'message': msg})


# ─── Admin-API ────────────────────────────────────────────────────────────────

@app.route('/admin/event', methods=['POST'])
def admin_event():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    name  = data.get('name', 'Mohjos DamageRace')
    goal  = data.get('goal', 100000)
    mode  = data.get('mode', 'coop')
    teams = data.get('teams', [{'name': 'Team 1'}, {'name': 'Team 2'}])
    state.create_event(name, goal, mode, teams)
    return jsonify({'ok': True, 'state': state.to_dict(base_url=_base_url())})


@app.route('/admin/set', methods=['POST'])
def admin_set():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    new_goal = data.get('goal')
    if bool(data.get('reset', False)):
        state.reset(new_goal=new_goal)
    elif new_goal is not None:
        state.set_goal(new_goal)
    return jsonify({'ok': True, 'state': state.to_dict(base_url=_base_url())})


@app.route('/admin/pause', methods=['POST'])
def admin_pause():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    state.set_pause(bool(data.get('paused', True)))
    return jsonify({'ok': True, 'paused': state.event['paused']})


@app.route('/admin/streamer', methods=['POST'])
def admin_streamer():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    action = data.get('action')
    name   = (data.get('name') or '').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'name required'}), 400
    if action == 'assign':
        ok, msg = state.assign_team(name, data.get('team_id'))
    elif action == 'remove':
        ok, msg = state.remove_streamer(name)
    else:
        return jsonify({'ok': False, 'error': 'unknown action'}), 400
    return jsonify({'ok': ok, 'message': msg,
                    'state': state.to_dict(base_url=_base_url())})


@app.route('/admin/invite/regenerate', methods=['POST'])
def admin_invite_regen():
    data = request.get_json(force=True, silent=True) or {}
    if not _api_auth(data):
        return jsonify({'ok': False, 'error': 'unauthorized'}), 403
    scope   = data.get('scope', 'event')
    team_id = data.get('team_id')
    token   = state.regenerate_invite(scope, team_id=team_id)
    if not token:
        return jsonify({'ok': False, 'error': 'invalid scope/team_id'}), 400
    return jsonify({'ok': True, 'token': token,
                    'state': state.to_dict(base_url=_base_url())})


@app.route('/admin/check-auth')
def check_auth():
    return jsonify({'authenticated': _logged_in()})


# ─── Static / Pages ───────────────────────────────────────────────────────────

@app.route('/')
@app.route('/overlay')
def serve_overlay():
    return send_from_directory(OVERLAY_DIR, 'index.html')


@app.route('/admin')
@login_required
def serve_admin():
    return send_from_directory(OVERLAY_DIR, 'admin.html')


@app.route('/brand.css')
def serve_brand():
    return send_from_directory(OVERLAY_DIR, 'brand.css')


@app.route('/health')
def health():
    return jsonify({'status': 'ok',
                    'remaining': state.to_dict()['event']['remaining']})


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== Mohjos DamageRace ===')
    print('Admin:   http://localhost:{}/admin'.format(cfg.PORT))
    print('Overlay: http://localhost:{}/overlay'.format(cfg.PORT))
    print('=========================')
    app.run(host='0.0.0.0', port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)
