"""
twitch_oauth.py — Twitch OAuth Helper (Authorization Code Flow mit Client-Secret).

Verwendet die gleiche Client-ID wie der Heist Bot.
Client-Secret muss in der ENV TWITCH_CLIENT_SECRET stehen (server-only).

Wenn kein Client-Secret gesetzt ist, faellt der Server auf Implicit-Grant zurueck:
Der Browser oeffnet die Auth-URL, Twitch redirected mit Token im URL-Fragment,
und eine kleine JS-Seite postet den Token ans Backend.
"""
import os
import urllib.parse
import urllib.request
import json

CLIENT_ID     = os.environ.get('TWITCH_CLIENT_ID',
                               '5ns5vekvgz8wb6wudfsos1nvzsa4sq')  # gleiche wie Heist Bot
CLIENT_SECRET = os.environ.get('TWITCH_CLIENT_SECRET', '')
SCOPES        = 'user:read:email'

AUTH_URL = 'https://id.twitch.tv/oauth2/authorize'
TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
USERS_URL = 'https://api.twitch.tv/helix/users'


def has_secret():
    return bool(CLIENT_SECRET)


def build_auth_url(redirect_uri, state, response_type=None):
    rt = response_type or ('code' if has_secret() else 'token')
    q = urllib.parse.urlencode({
        'client_id':     CLIENT_ID,
        'redirect_uri':  redirect_uri,
        'response_type': rt,
        'scope':         SCOPES,
        'state':         state,
        'force_verify':  'false',
    })
    return '{}?{}'.format(AUTH_URL, q)


def exchange_code(code, redirect_uri):
    """Authorization Code Flow: tauscht code gegen access_token."""
    data = urllib.parse.urlencode({
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code':          code,
        'grant_type':    'authorization_code',
        'redirect_uri':  redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def fetch_user(access_token):
    """Holt das Twitch-Profil zum Access-Token."""
    req = urllib.request.Request(USERS_URL)
    req.add_header('Authorization', 'Bearer ' + access_token)
    req.add_header('Client-Id', CLIENT_ID)
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read().decode())
    data = body.get('data') or []
    if not data:
        return None
    u = data[0]
    return {
        'twitch_id':    u.get('id'),
        'twitch_login': u.get('login'),
        'display_name': u.get('display_name') or u.get('login'),
        'avatar_url':   u.get('profile_image_url'),
    }
