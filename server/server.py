"""
server.py — Mohjos DamageRace Multi-Tenant Flask-Server

Auth: Twitch OAuth (gleiche Client-ID wie Heist Bot).
Pro User maximal ein aktives Event.
Streamer registrieren sich ohne Account via Invite-Link/Code.
"""
import os
import sys
import json
import time

from flask import (Flask, request, jsonify, send_from_directory,
                   redirect, make_response)
from flask_cors import CORS

import config as cfg
import twitch_oauth
from db import Database

_BASE       = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(__file__), '..'))
OVERLAY_DIR = os.path.join(_BASE, 'overlay')

app = Flask(__name__, static_folder=OVERLAY_DIR)
CORS(app, supports_credentials=True)

db = Database()

SESSION_COOKIE = 'damagerace_sid'


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _base_url():
    if cfg.PUBLIC_BASE_URL:
        return cfg.PUBLIC_BASE_URL.rstrip('/')
    return request.host_url.rstrip('/')


def _current_sid():
    return request.cookies.get(SESSION_COOKIE)


def _ensure_session_id(resp=None):
    """Gibt Session-ID zurueck, erstellt neue wenn keine vorhanden."""
    sid = _current_sid()
    if sid and db.get_session(sid):
        return sid, resp
    sid = db.create_session()
    if resp is None:
        resp = make_response()
    resp.set_cookie(SESSION_COOKIE, sid, max_age=30*24*3600,
                    httponly=True, samesite='Lax')
    return sid, resp


def _current_user():
    sid = _current_sid()
    if not sid:
        return None
    s = db.get_session(sid)
    if not s or not s.get('twitch_id'):
        return None
    return db.get_user(s['twitch_id'])


# ─── Twitch OAuth ─────────────────────────────────────────────────────────────

@app.route('/auth/twitch/start')
def auth_start():
    """Schritt 1 — leitet Browser zu Twitch OAuth-Seite."""
    sid, resp = _ensure_session_id()
    redirect_uri = _base_url() + '/auth/twitch/callback'
    state = db.create_oauth_state(sid)
    auth_url = twitch_oauth.build_auth_url(redirect_uri, state)
    if resp is None:
        return redirect(auth_url)
    resp.headers['Location'] = auth_url
    resp.status_code = 302
    return resp


@app.route('/auth/twitch/callback')
def auth_callback():
    """Schritt 2 — Twitch ruft uns mit code/token zurueck."""
    state = request.args.get('state')
    if not state:
        return _auth_done_page('Fehlender state-Parameter.', ok=False)

    pending = db.consume_oauth_state(state)
    if not pending:
        return _auth_done_page('Auth-Sitzung abgelaufen oder ungueltig.', ok=False)

    sid = pending['session_id']

    if twitch_oauth.has_secret():
        # Code-Flow
        code = request.args.get('code')
        if not code:
            return _auth_done_page('Kein code von Twitch erhalten.', ok=False)
        try:
            tok = twitch_oauth.exchange_code(code, _base_url() + '/auth/twitch/callback')
            access_token = tok.get('access_token')
            user = twitch_oauth.fetch_user(access_token)
        except Exception as e:
            return _auth_done_page('Twitch-Authentifizierung fehlgeschlagen: ' + str(e), ok=False)
    else:
        # Implicit-Flow: Token kommt im URL-Fragment, JS muss es uns posten
        return _implicit_bridge_page(sid)

    if not user:
        return _auth_done_page('Twitch-Profil konnte nicht geladen werden.', ok=False)

    db.upsert_user(user['twitch_id'], user['twitch_login'],
                   user['display_name'], user.get('avatar_url'))
    db.attach_user_to_session(sid, user['twitch_id'])
    return _auth_done_page('Login erfolgreich. Du kannst dieses Fenster schliessen.', ok=True)


@app.route('/auth/twitch/implicit', methods=['POST'])
def auth_implicit_post():
    """Implicit-Flow: Frontend postet Access-Token aus URL-Fragment."""
    data = request.get_json(force=True, silent=True) or {}
    sid   = data.get('sid')
    token = data.get('access_token')
    if not sid or not token:
        return jsonify({'ok': False, 'error': 'sid + access_token erforderlich'}), 400
    if not db.get_session(sid):
        return jsonify({'ok': False, 'error': 'Session ungueltig'}), 400
    try:
        user = twitch_oauth.fetch_user(token)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400
    if not user:
        return jsonify({'ok': False, 'error': 'User-Lookup fehlgeschlagen'}), 400
    db.upsert_user(user['twitch_id'], user['twitch_login'],
                   user['display_name'], user.get('avatar_url'))
    db.attach_user_to_session(sid, user['twitch_id'])
    return jsonify({'ok': True, 'user': user})


def _implicit_bridge_page(sid):
    html = '''<!doctype html>
<meta charset="utf-8"><title>Login...</title>
<body style="background:#0d0d14;color:#f3f4f6;font-family:Inter,system-ui;text-align:center;padding:80px;">
<h2 style="color:#ffd700;">Twitch-Login wird abgeschlossen...</h2>
<p>Bitte warten.</p>
<script>
(async function(){
  const m = window.location.hash.match(/access_token=([^&]+)/);
  if (!m) { document.body.innerHTML = '<h2 style="color:#cf6679;">Kein Token erhalten.</h2>'; return; }
  const token = m[1];
  const r = await fetch('/auth/twitch/implicit', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({sid: %r, access_token: token})
  });
  const d = await r.json();
  if (d.ok) {
    document.body.innerHTML = '<h2 style="color:#00e676;">Login erfolgreich.</h2><p>Du kannst dieses Fenster schliessen.</p>';
    setTimeout(()=>window.close(), 1500);
  } else {
    document.body.innerHTML = '<h2 style="color:#cf6679;">Fehler: '+d.error+'</h2>';
  }
})();
</script></body>''' % sid
    return html


def _auth_done_page(msg, ok=True):
    color = '#00e676' if ok else '#cf6679'
    return '''<!doctype html>
<meta charset="utf-8"><title>DamageRace Login</title>
<body style="background:#0d0d14;color:#f3f4f6;font-family:Inter,system-ui;text-align:center;padding:80px;">
<h2 style="color:%s;">%s</h2>
<script>setTimeout(()=>{ try{ window.close(); }catch(_){} }, 1500);</script>
</body>''' % (color, msg)


@app.route('/auth/me')
def auth_me():
    u = _current_user()
    sid, resp = _ensure_session_id()
    body = {'authenticated': u is not None, 'user': u, 'sid': sid}
    out = jsonify(body)
    if resp is not None:
        out.set_cookie(SESSION_COOKIE, sid, max_age=30*24*3600, httponly=True, samesite='Lax')
    return out


@app.route('/auth/logout', methods=['POST', 'GET'])
def auth_logout():
    sid = _current_sid()
    if sid:
        db.delete_session(sid)
    resp = redirect('/login')
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# ─── Damage (mod sendet hierhin) ─────────────────────────────────────────────

@app.route('/damage', methods=['POST', 'GET'])
def post_damage():
    if request.method == 'POST':
        data  = request.get_json(force=True, silent=True) or {}
        token = data.get('streamer_token') or data.get('token') or data.get('streamer')
        raw   = data.get('damage', 0)
        key   = data.get('key')
    else:
        token = (request.args.get('streamer_token') or
                 request.args.get('token') or
                 request.args.get('streamer'))
        raw   = request.args.get('damage', 0)
        key   = request.args.get('key')

    if not token:
        return jsonify({'ok': False, 'error': 'streamer_token required'}), 400
    try:
        damage = int(float(raw))
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'error': 'invalid damage'}), 400
    if damage <= 0:
        return jsonify({'ok': False, 'error': 'damage must be positive'}), 400

    ok, remaining = db.record_damage(token, damage, key=key)
    return jsonify({'ok': ok, 'remaining': remaining})


# ─── Event-Status (oeffentlich, per Slug fuer Overlay) ────────────────────────

@app.route('/status/<slug>')
@app.route('/api/event/<slug>')
def status_by_slug(slug):
    ev = db.get_event_by_slug(slug)
    if not ev:
        return jsonify({'error': 'Event nicht gefunden'}), 404
    return jsonify(db.get_event_state(ev['id'], base_url=_base_url()))


# ─── Eigenes Event (Admin) ────────────────────────────────────────────────────

@app.route('/api/my-event')
def api_my_event():
    u = _current_user()
    if not u:
        return jsonify({'authenticated': False}), 401
    ev = db.get_event_by_owner(u['twitch_id'])
    if not ev:
        return jsonify({'authenticated': True, 'user': u, 'event': None})
    return jsonify({'authenticated': True, 'user': u,
                    **db.get_event_state(ev['id'], base_url=_base_url())})


@app.route('/api/event', methods=['POST'])
def api_create_event():
    u = _current_user()
    if not u:
        return jsonify({'ok': False, 'error': 'Login erforderlich'}), 401
    data  = request.get_json(force=True, silent=True) or {}
    name  = (data.get('name') or 'Mohjos DamageRace').strip()
    goal  = int(data.get('goal') or 100000)
    mode  = data.get('mode') or 'coop'
    teams = data.get('teams') or [{'name': 'Team 1'}, {'name': 'Team 2'}]
    db.create_or_replace_event(u['twitch_id'], name, goal, mode, teams,
                               twitch_login=u['twitch_login'])
    ev = db.get_event_by_owner(u['twitch_id'])
    return jsonify({'ok': True, **db.get_event_state(ev['id'], base_url=_base_url())})


@app.route('/api/event/set', methods=['POST'])
def api_event_set():
    u = _current_user()
    if not u:
        return jsonify({'ok': False, 'error': 'Login erforderlich'}), 401
    ev = db.get_event_by_owner(u['twitch_id'])
    if not ev:
        return jsonify({'ok': False, 'error': 'Kein aktives Event'}), 404
    data = request.get_json(force=True, silent=True) or {}
    if data.get('reset'):
        db.reset_event(ev['id'], new_goal=data.get('goal'))
    elif data.get('goal') is not None:
        db.set_event_goal(ev['id'], data['goal'])
    return jsonify({'ok': True, **db.get_event_state(ev['id'], base_url=_base_url())})


@app.route('/api/event/pause', methods=['POST'])
def api_event_pause():
    u = _current_user()
    if not u:
        return jsonify({'ok': False, 'error': 'Login erforderlich'}), 401
    ev = db.get_event_by_owner(u['twitch_id'])
    if not ev:
        return jsonify({'ok': False, 'error': 'Kein aktives Event'}), 404
    data = request.get_json(force=True, silent=True) or {}
    db.set_event_paused(ev['id'], bool(data.get('paused', True)))
    return jsonify({'ok': True})


@app.route('/api/event/invite/regenerate', methods=['POST'])
def api_event_regen():
    u = _current_user()
    if not u:
        return jsonify({'ok': False, 'error': 'Login erforderlich'}), 401
    ev = db.get_event_by_owner(u['twitch_id'])
    if not ev:
        return jsonify({'ok': False, 'error': 'Kein aktives Event'}), 404
    data    = request.get_json(force=True, silent=True) or {}
    scope   = data.get('scope', 'event')
    team_id = data.get('team_id')
    if scope == 'event':
        db.regenerate_event_invite(ev['id'])
    elif scope == 'team' and team_id is not None:
        db.regenerate_team_invite(int(team_id))
    return jsonify({'ok': True, **db.get_event_state(ev['id'], base_url=_base_url())})


@app.route('/api/event/delete', methods=['POST'])
def api_event_delete():
    u = _current_user()
    if not u:
        return jsonify({'ok': False, 'error': 'Login erforderlich'}), 401
    ev = db.get_event_by_owner(u['twitch_id'])
    if ev:
        db.delete_event(ev['id'])
    return jsonify({'ok': True})


# ─── Invite + Join (oeffentlich) ──────────────────────────────────────────────

@app.route('/api/invite/<token>')
def api_invite_info(token):
    kind, info = db.resolve_invite(token)
    if not kind:
        return jsonify({'ok': False, 'error': 'Einladungslink ungueltig'}), 404
    if kind == 'event':
        return jsonify({'ok': True, 'kind': 'event',
                        'event_name': info['name'],
                        'event_slug': info['slug']})
    return jsonify({'ok': True, 'kind': 'team',
                    'team_name': info['name'], 'team_color': info['color'],
                    'event_name': info['e_name'], 'event_slug': info['e_slug']})


@app.route('/api/join', methods=['POST'])
def api_join():
    data     = request.get_json(force=True, silent=True) or {}
    token    = (data.get('token') or data.get('invite_code') or '').strip()
    wot_name = (data.get('wot_name') or data.get('streamer') or '').strip()
    if not token or not wot_name:
        return jsonify({'ok': False, 'error': 'token + wot_name erforderlich'}), 400
    result, msg = db.join_via_invite(token, wot_name)
    if not result:
        return jsonify({'ok': False, 'error': msg}), 400
    return jsonify({
        'ok': True,
        'streamer_token': result['streamer_token'],
        'event': {
            'name': result['event']['name'],
            'slug': result['event']['slug'],
        },
        'team': {
            'name':  result['team']['name'],
            'color': result['team']['color'],
        } if result['team'] else None,
        'server_url': _base_url(),
    })


# ─── Static Pages ─────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/login')
def serve_login():
    if _current_user():
        return redirect('/admin')
    return send_from_directory(OVERLAY_DIR, 'login.html')


@app.route('/admin')
def serve_admin():
    if not _current_user():
        return redirect('/login')
    return send_from_directory(OVERLAY_DIR, 'admin.html')


@app.route('/overlay/<slug>')
def serve_overlay(slug):
    ev = db.get_event_by_slug(slug)
    if not ev:
        return 'Event nicht gefunden', 404
    return send_from_directory(OVERLAY_DIR, 'index.html')


@app.route('/join/<token>')
def serve_join(token):
    return send_from_directory(OVERLAY_DIR, 'join.html')


@app.route('/brand.css')
def serve_brand():
    return send_from_directory(OVERLAY_DIR, 'brand.css')


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== Mohjos DamageRace (Multi-Tenant) ===')
    print('  http://localhost:{}/'.format(cfg.PORT))
    print('  Twitch OAuth: ' + ('Code-Flow' if twitch_oauth.has_secret() else 'Implicit-Flow'))
    print('========================================')
    app.run(host='0.0.0.0', port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)
