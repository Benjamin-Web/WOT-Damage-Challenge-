"""Twitch OAuth helpers.

Supports the Authorization Code flow when a client secret is configured and
falls back to the Implicit flow otherwise. Implicit flow requires a small
JavaScript bridge page to forward the fragment-encoded access token to the
server (see server.implicit_bridge).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = os.environ.get(
    "TWITCH_CLIENT_ID", "5ns5vekvgz8wb6wudfsos1nvzsa4sq",
)
CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET", "")

AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
USERS_URL = "https://api.twitch.tv/helix/users"

SCOPES = "user:read:email"
USER_AGENT = "MohjosDamageRace/1.0"

_HTTP_TIMEOUT = 15


class TwitchError(RuntimeError):
    """Raised when Twitch returns an error response."""


def has_secret() -> bool:
    return bool(CLIENT_SECRET)


def build_auth_url(redirect_uri: str, state: str,
                   response_type: str | None = None) -> str:
    response_type = response_type or ("code" if has_secret() else "token")
    params = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": response_type,
        "scope":         SCOPES,
        "state":         state,
        "force_verify":  "false",
    })
    return f"{AUTH_URL}?{params}"


def _open(req: urllib.request.Request):
    """Open a request and surface Twitch's error body for diagnostics."""
    try:
        return urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        raise TwitchError(f"{exc.code} {exc.reason}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise TwitchError(str(exc.reason)) from exc


def exchange_code(code: str, redirect_uri: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with _open(req) as resp:
        return json.loads(resp.read().decode())


def fetch_user(access_token: str) -> dict | None:
    req = urllib.request.Request(USERS_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Client-Id", CLIENT_ID)
    req.add_header("User-Agent", USER_AGENT)
    with _open(req) as resp:
        body = json.loads(resp.read().decode())
    rows = body.get("data") or []
    if not rows:
        return None
    row = rows[0]
    return {
        "twitch_id":    row.get("id"),
        "twitch_login": row.get("login"),
        "display_name": row.get("display_name") or row.get("login"),
        "avatar_url":   row.get("profile_image_url"),
    }
