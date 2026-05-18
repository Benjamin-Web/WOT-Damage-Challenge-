"""DamageRace HTTP server.

Exposes:

    /auth/twitch/*    Twitch OAuth (code flow if a secret is configured,
                      implicit flow otherwise).
    /api/*            JSON API used by the admin dashboard and desktop app.
    /damage           Damage ingestion endpoint called by the in-game mod.
    /status/<slug>    Public read-only state used by the OBS overlay.
    /overlay/<slug>   OBS browser-source page.
    /join/<token>     Public landing page for invite links.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Callable

from flask import (
    Flask, Response, jsonify, make_response, redirect, request,
    send_from_directory,
)
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

import config as cfg
import i18n
import twitch_oauth
from db import MAX_TEAMS, MIN_TEAMS, Database

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("damagerace")

_BASE_DIR = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(__file__), ".."))
OVERLAY_DIR = os.path.join(_BASE_DIR, "overlay")

SESSION_COOKIE = "damagerace_sid"
LANG_COOKIE = "damagerace_lang"
SESSION_MAX_AGE = 30 * 24 * 3600
VALID_MODES = ("coop", "versus")

app = Flask(__name__, static_folder=OVERLAY_DIR)
# Trust the X-Forwarded-* headers Caddy sets so request.scheme / .host are correct
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
CORS(app, supports_credentials=True)

db = Database()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_url() -> str:
    if cfg.PUBLIC_BASE_URL:
        return cfg.PUBLIC_BASE_URL.rstrip("/")
    return request.host_url.rstrip("/")


def _current_sid() -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def _request_lang() -> str:
    cookie = request.cookies.get(LANG_COOKIE)
    if cookie:
        return i18n.normalize(cookie)
    header = request.headers.get("Accept-Language", "")
    return i18n.normalize(header)


def _ensure_session(resp: Response | None = None) -> tuple[str, Response | None]:
    sid = _current_sid()
    if sid and db.get_session(sid):
        return sid, resp
    sid = db.create_session()
    if resp is None:
        resp = make_response()
    resp.set_cookie(SESSION_COOKIE, sid, max_age=SESSION_MAX_AGE,
                    httponly=True, samesite="Lax")
    return sid, resp


def _current_user() -> dict | None:
    sid = _current_sid()
    if not sid:
        return None
    session = db.get_session(sid)
    if not session or not session.get("twitch_id"):
        return None
    return db.get_user(session["twitch_id"])


def _t(key: str, **params: object) -> str:
    return i18n.t(key, _request_lang(), **params)


def _error(key: str, status: int = 400, **params: object):
    return jsonify({"ok": False, "error": _t(key, **params)}), status


def _require_user() -> dict | None:
    """Return the current user. Routes guard with `if not user: return _error(...)`."""
    return _current_user()


def _read_json() -> dict:
    return request.get_json(force=True, silent=True) or {}


def _route_safe(handler: Callable):
    """Decorator that converts unhandled exceptions into HTTP 500 + JSON."""
    def wrapped(*args: Any, **kwargs: Any):
        try:
            return handler(*args, **kwargs)
        except Exception:
            log.exception("Unhandled error in %s", handler.__name__)
            return jsonify({"ok": False, "error": "internal_error"}), 500
    wrapped.__name__ = handler.__name__
    return wrapped


# ── Twitch OAuth ──────────────────────────────────────────────────────────────

@app.route("/auth/twitch/start")
def auth_start():
    # The desktop client passes its own session id via ?sid= so the user
    # ends up attached to that session, which the client polls afterwards.
    explicit_sid = request.args.get("sid")
    if explicit_sid and db.get_session(explicit_sid):
        sid, resp = explicit_sid, None
    else:
        sid, resp = _ensure_session()
    redirect_uri = _base_url() + "/auth/twitch/callback"
    state = db.create_oauth_state(sid)
    auth_url = twitch_oauth.build_auth_url(redirect_uri, state)
    if resp is None:
        return redirect(auth_url)
    resp.headers["Location"] = auth_url
    resp.status_code = 302
    return resp


@app.route("/auth/twitch/callback")
def auth_callback():
    state = request.args.get("state")
    if not state:
        return _auth_done_page(_t("auth.state_missing"), ok=False)

    pending = db.consume_oauth_state(state)
    if not pending:
        return _auth_done_page(_t("auth.state_invalid"), ok=False)

    sid = pending["session_id"]

    if not twitch_oauth.has_secret():
        return _implicit_bridge_page(sid)

    code = request.args.get("code")
    if not code:
        return _auth_done_page(_t("auth.code_missing"), ok=False)

    try:
        tokens = twitch_oauth.exchange_code(
            code, _base_url() + "/auth/twitch/callback",
        )
        user = twitch_oauth.fetch_user(tokens.get("access_token", ""))
    except twitch_oauth.TwitchError as exc:
        log.warning("Twitch token exchange failed: %s", exc)
        return _auth_done_page(_t("auth.exchange_failed", detail=str(exc)), ok=False)
    except Exception:
        log.exception("Unexpected error during OAuth callback")
        return _auth_done_page(_t("auth.exchange_failed", detail="internal"), ok=False)

    if not user:
        return _auth_done_page(_t("auth.profile_failed"), ok=False)

    db.upsert_user(user["twitch_id"], user["twitch_login"],
                   user["display_name"], user.get("avatar_url"))
    db.attach_user_to_session(sid, user["twitch_id"])
    log.info("User authenticated: twitch_id=%s login=%s",
             user["twitch_id"], user["twitch_login"])
    return _auth_done_page(_t("auth.success"), ok=True)


@app.route("/auth/twitch/implicit", methods=["POST"])
def auth_implicit_post():
    data = _read_json()
    sid = data.get("sid")
    access_token = data.get("access_token")
    if not sid or not access_token:
        return _error("auth.session_invalid")
    if not db.get_session(sid):
        return _error("auth.session_invalid")
    try:
        user = twitch_oauth.fetch_user(access_token)
    except twitch_oauth.TwitchError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if not user:
        return _error("auth.profile_failed")
    db.upsert_user(user["twitch_id"], user["twitch_login"],
                   user["display_name"], user.get("avatar_url"))
    db.attach_user_to_session(sid, user["twitch_id"])
    return jsonify({"ok": True, "user": user})


@app.route("/auth/me")
def auth_me():
    user = _current_user()
    sid, resp = _ensure_session()
    body = {"authenticated": user is not None, "user": user, "sid": sid}
    out = jsonify(body)
    if resp is not None:
        out.set_cookie(SESSION_COOKIE, sid, max_age=SESSION_MAX_AGE,
                       httponly=True, samesite="Lax")
    return out


@app.route("/auth/logout", methods=["POST", "GET"])
def auth_logout():
    sid = _current_sid()
    if sid:
        db.delete_session(sid)
    resp = redirect("/login")
    resp.delete_cookie(SESSION_COOKIE)
    return resp


def _implicit_bridge_page(sid: str) -> str:
    return (
        '<!doctype html><meta charset="utf-8"><title>Login...</title>'
        '<body style="background:#0d0d14;color:#f3f4f6;font-family:Inter,system-ui;'
        'text-align:center;padding:80px;">'
        '<h2 style="color:#ffd700;">Twitch login in progress…</h2>'
        '<script>(async()=>{'
        'const m=location.hash.match(/access_token=([^&]+)/);'
        'if(!m){document.body.innerHTML='
        "'<h2 style=\"color:#cf6679;\">No token received.</h2>';return;}"
        f"const r=await fetch('/auth/twitch/implicit',"
        "{method:'POST',headers:{'Content-Type':'application/json'},"
        f"body:JSON.stringify({{sid:{sid!r},access_token:m[1]}})}});"
        "const d=await r.json();"
        "document.body.innerHTML=d.ok"
        "?'<h2 style=\"color:#00e676;\">Login complete.</h2>'"
        ":'<h2 style=\"color:#cf6679;\">Error: '+d.error+'</h2>';"
        "if(d.ok)setTimeout(()=>window.close(),1500);})();</script></body>"
    )


def _auth_done_page(msg: str, ok: bool = True) -> str:
    color = "#00e676" if ok else "#cf6679"
    return (
        f'<!doctype html><meta charset="utf-8"><title>DamageRace Login</title>'
        f'<body style="background:#0d0d14;color:#f3f4f6;font-family:Inter,system-ui;'
        f'text-align:center;padding:80px;">'
        f'<h2 style="color:{color};">{msg}</h2>'
        f'<script>setTimeout(()=>{{try{{window.close()}}catch(_){{}}}},1500);'
        f'</script></body>'
    )


# ── Damage ingestion ──────────────────────────────────────────────────────────

@app.route("/damage", methods=["POST", "GET"])
@_route_safe
def post_damage():
    if request.method == "POST":
        payload = _read_json()
        token = payload.get("streamer_token") or payload.get("token") or payload.get("streamer")
        raw_damage = payload.get("damage", 0)
        key = payload.get("key")
    else:
        token = (request.args.get("streamer_token")
                 or request.args.get("token")
                 or request.args.get("streamer"))
        raw_damage = request.args.get("damage", 0)
        key = request.args.get("key")

    if not token:
        return _error("damage.token_required")
    try:
        damage = int(float(raw_damage))
    except (TypeError, ValueError):
        return _error("damage.invalid")
    if damage <= 0:
        return _error("damage.must_be_positive")

    ok, remaining = db.record_damage(token, damage, key=key)
    if not ok and remaining == 0:
        return _error("damage.streamer_unknown", status=404)
    return jsonify({"ok": ok, "remaining": remaining})


# ── Public event state ────────────────────────────────────────────────────────

@app.route("/status/<slug>")
@app.route("/api/event/<slug>")
@_route_safe
def status_by_slug(slug: str):
    event = db.get_event_by_slug(slug)
    if not event:
        return _error("event.not_found", status=404)
    return jsonify(db.get_event_state(event["id"], base_url=_base_url()))


# ── Owner API ─────────────────────────────────────────────────────────────────

@app.route("/api/my-event")
@_route_safe
def api_my_event():
    user = _require_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    event = db.get_event_by_owner(user["twitch_id"])
    if not event:
        return jsonify({"authenticated": True, "user": user, "event": None})
    return jsonify({
        "authenticated": True,
        "user": user,
        **db.get_event_state(event["id"], base_url=_base_url()),
    })


def _validate_event_payload(data: dict) -> tuple[dict | None, tuple]:
    name = (data.get("name") or "Mohjos DamageRace").strip()
    if not name:
        return None, _error("event.name_invalid")
    try:
        goal = int(data.get("goal") or 100_000)
    except (TypeError, ValueError):
        return None, _error("event.goal_invalid")
    if goal <= 0:
        return None, _error("event.goal_invalid")

    mode = (data.get("mode") or "coop").strip().lower()
    if mode not in VALID_MODES:
        return None, _error("event.mode_invalid")

    teams = data.get("teams")
    if teams is None:
        teams = [{"name": "Team 1"}, {"name": "Team 2"}]
    if not isinstance(teams, list) or not (MIN_TEAMS <= len(teams) <= MAX_TEAMS):
        return None, _error("event.teams_invalid")

    clean_teams = []
    for spec in teams:
        if not isinstance(spec, dict):
            return None, _error("event.teams_invalid")
        clean_teams.append({
            "name":  (spec.get("name") or "").strip(),
            "color": (spec.get("color") or "#ffd700").strip(),
        })
    return {"name": name, "goal": goal, "mode": mode, "teams": clean_teams}, ()


@app.route("/api/event", methods=["POST"])
@_route_safe
def api_create_event():
    user = _require_user()
    if not user:
        return _error("auth.required", status=401)
    payload, err = _validate_event_payload(_read_json())
    if payload is None:
        return err
    db.create_or_replace_event(
        user["twitch_id"], payload["name"], payload["goal"], payload["mode"],
        payload["teams"], twitch_login=user["twitch_login"],
    )
    event = db.get_event_by_owner(user["twitch_id"])
    return jsonify({"ok": True, **db.get_event_state(event["id"], base_url=_base_url())})


@app.route("/api/event/set", methods=["POST"])
@_route_safe
def api_event_set():
    user = _require_user()
    if not user:
        return _error("auth.required", status=401)
    event = db.get_event_by_owner(user["twitch_id"])
    if not event:
        return _error("event.none", status=404)
    data = _read_json()
    if data.get("reset"):
        db.reset_event(event["id"], new_goal=data.get("goal"))
    elif data.get("goal") is not None:
        try:
            goal = int(data["goal"])
        except (TypeError, ValueError):
            return _error("event.goal_invalid")
        if goal <= 0:
            return _error("event.goal_invalid")
        db.set_event_goal(event["id"], goal)
    return jsonify({"ok": True, **db.get_event_state(event["id"], base_url=_base_url())})


@app.route("/api/event/pause", methods=["POST"])
@_route_safe
def api_event_pause():
    user = _require_user()
    if not user:
        return _error("auth.required", status=401)
    event = db.get_event_by_owner(user["twitch_id"])
    if not event:
        return _error("event.none", status=404)
    data = _read_json()
    db.set_event_paused(event["id"], bool(data.get("paused", True)))
    return jsonify({"ok": True})


@app.route("/api/event/invite/regenerate", methods=["POST"])
@_route_safe
def api_event_regen():
    user = _require_user()
    if not user:
        return _error("auth.required", status=401)
    event = db.get_event_by_owner(user["twitch_id"])
    if not event:
        return _error("event.none", status=404)
    data = _read_json()
    scope = data.get("scope", "event")
    if scope == "event":
        db.regenerate_event_invite(event["id"])
    elif scope == "team" and data.get("team_id") is not None:
        try:
            team_id = int(data["team_id"])
        except (TypeError, ValueError):
            return _error("event.invalid_payload")
        db.regenerate_team_invite(team_id)
    return jsonify({"ok": True, **db.get_event_state(event["id"], base_url=_base_url())})


@app.route("/api/event/delete", methods=["POST"])
@_route_safe
def api_event_delete():
    user = _require_user()
    if not user:
        return _error("auth.required", status=401)
    event = db.get_event_by_owner(user["twitch_id"])
    if event:
        db.delete_event(event["id"])
    return jsonify({"ok": True})


def _owner_event():
    user = _require_user()
    if not user:
        return None, _error("auth.required", status=401)
    event = db.get_event_by_owner(user["twitch_id"])
    if not event:
        return None, _error("event.none", status=404)
    return event, None


def _parse_team_id(raw):
    if raw in (None, "", 0, "0"):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return "invalid"


@app.route("/api/event/streamer/add", methods=["POST"])
@_route_safe
def api_streamer_add():
    event, err = _owner_event()
    if err:
        return err
    data = _read_json()
    team_id = _parse_team_id(data.get("team_id"))
    if team_id == "invalid":
        return _error("roster.team_not_in_event")
    result, err_key = db.add_streamer(event["id"], team_id,
                                      data.get("wot_name", ""))
    if err_key:
        return _error(err_key)
    return jsonify({"ok": True, "streamer": result,
                    **db.get_event_state(event["id"], base_url=_base_url())})


@app.route("/api/event/streamer/move", methods=["POST"])
@_route_safe
def api_streamer_move():
    event, err = _owner_event()
    if err:
        return err
    data = _read_json()
    team_id = _parse_team_id(data.get("team_id"))
    if team_id == "invalid":
        return _error("roster.team_not_in_event")
    err_key = db.move_streamer(event["id"], data.get("wot_name", ""), team_id)
    if err_key:
        return _error(err_key, status=404 if err_key == "roster.streamer_unknown" else 400)
    return jsonify({"ok": True,
                    **db.get_event_state(event["id"], base_url=_base_url())})


@app.route("/api/event/streamer/remove", methods=["POST"])
@_route_safe
def api_streamer_remove():
    event, err = _owner_event()
    if err:
        return err
    data = _read_json()
    err_key = db.remove_streamer(event["id"], data.get("wot_name", ""))
    if err_key:
        return _error(err_key, status=404)
    return jsonify({"ok": True,
                    **db.get_event_state(event["id"], base_url=_base_url())})


# ── Public invite + join ──────────────────────────────────────────────────────

@app.route("/api/invite/<token>")
@_route_safe
def api_invite_info(token: str):
    kind, info = db.resolve_invite(token)
    if not kind or not info:
        return _error("invite.invalid", status=404)
    if kind == "event":
        return jsonify({
            "ok": True, "kind": "event",
            "event_name": info["name"],
            "event_slug": info["slug"],
        })
    return jsonify({
        "ok": True, "kind": "team",
        "team_name":  info["name"],
        "team_color": info["color"],
        "event_name": info["e_name"],
        "event_slug": info["e_slug"],
    })


@app.route("/api/join", methods=["POST"])
@_route_safe
def api_join():
    data = _read_json()
    token = (data.get("token") or data.get("invite_code") or "").strip()
    wot_name = (data.get("wot_name") or data.get("streamer") or "").strip()
    if not token or not wot_name:
        return _error("invite.fields_required")

    result, err_key = db.join_via_invite(token, wot_name)
    if not result:
        status = 404 if err_key == "invite.invalid" else 400
        return _error(err_key or "invite.invalid", status=status)

    return jsonify({
        "ok": True,
        "streamer_token": result["streamer_token"],
        "event": {"name": result["event"]["name"],
                  "slug": result["event"]["slug"]},
        "team":  ({"name":  result["team"]["name"],
                   "color": result["team"]["color"]} if result["team"] else None),
        "server_url": _base_url(),
    })


# ── Static pages ──────────────────────────────────────────────────────────────

@app.route("/")
@app.route("/login")
def serve_login():
    if _current_user():
        return redirect("/admin")
    return send_from_directory(OVERLAY_DIR, "login.html")


@app.route("/admin")
def serve_admin():
    if not _current_user():
        return redirect("/login")
    return send_from_directory(OVERLAY_DIR, "admin.html")


@app.route("/overlay/<slug>")
def serve_overlay(slug: str):
    event = db.get_event_by_slug(slug)
    if not event:
        return _t("event.not_found"), 404
    return send_from_directory(OVERLAY_DIR, "index.html")


@app.route("/join/<token>")
def serve_join(token: str):
    return send_from_directory(OVERLAY_DIR, "join.html")


@app.route("/brand.css")
def serve_brand():
    return send_from_directory(OVERLAY_DIR, "brand.css")


@app.route("/i18n.js")
def serve_i18n():
    return send_from_directory(OVERLAY_DIR, "i18n.js")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    flow = "code" if twitch_oauth.has_secret() else "implicit"
    log.info("Starting DamageRace on port %d (OAuth flow=%s)", cfg.PORT, flow)
    app.run(host="0.0.0.0", port=cfg.PORT, debug=False,
            threaded=True, use_reloader=False)
