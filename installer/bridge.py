"""JavaScript-to-Python bridge exposed inside the pywebview window.

Each method on ``WebviewBridge`` becomes a callable on ``window.pywebview.api``
inside the embedded admin dashboard. Methods must:

* Be safe to call from a UI handler (return a plain dict / JSON-serializable).
* Catch their own exceptions and return a structured error rather than
  raising — pywebview surfaces Python exceptions as opaque JS errors.
* Avoid blocking the GUI for more than a few seconds.

Settings (OBS password etc.) are persisted via the callbacks the parent
hands in, so the bridge stays decoupled from the GUI file's storage code.
"""
from __future__ import annotations

import logging
from typing import Callable

log = logging.getLogger("damagerace.bridge")

OBS_DEFAULT_HOST = "localhost"
OBS_DEFAULT_PORT = 4455
OVERLAY_WIDTH = 300
OVERLAY_HEIGHT = 180


class WebviewBridge:
    """Bridge between the admin web UI (pywebview window) and local OS access.

    ``settings_get`` / ``settings_set`` are callbacks the caller passes in so
    we don't bake a particular settings-file shape into the bridge.
    """

    def __init__(self, settings_get: Callable[[str], str | None],
                 settings_set: Callable[[str, str], None],
                 install_mod: Callable[[str, str], tuple] | None = None,
                 find_wot: Callable[[], str] | None = None) -> None:
        self._settings_get = settings_get
        self._settings_set = settings_set
        self._install_mod = install_mod
        self._find_wot = find_wot

    # ── WoT mod auto-install ─────────────────────────────────────────────────

    def install_mod(self, streamer_token: str, wot_name: str,
                    wot_path: str | None = None) -> dict:
        """Copy the .wotmod file into the local WoT install and write the
        config.json with ``streamer_token`` + ``wot_name``. Returns:

        * ``{"ok": True, "path": "<wot path>", "version": "<x.y.z>"}``
        * ``{"ok": False, "error": "wot_not_found", "needs_path": True}``
          when the WoT install can't be auto-detected.
        * ``{"ok": False, "error": "<key>", "detail": "<msg>"}`` otherwise.
        """
        if not streamer_token or not wot_name:
            return {"ok": False, "error": "missing_args"}
        if not self._install_mod or not self._find_wot:
            return {"ok": False, "error": "installer_unavailable"}
        path = (wot_path or self._settings_get("wot_path") or "").strip()
        if not path or not self._is_valid_wot(path):
            path = self._find_wot() or ""
        if not path or not self._is_valid_wot(path):
            return {"ok": False, "error": "wot_not_found", "needs_path": True}
        ok, detail = self._install_mod(path, wot_name, streamer_token)
        if not ok:
            return {"ok": False, "error": "install_failed", "detail": detail}
        self._settings_set("wot_path", path)
        return {"ok": True, "path": path, "version": detail}

    @staticmethod
    def _is_valid_wot(path: str) -> bool:
        import os
        return bool(path) and os.path.isfile(os.path.join(path, "WorldOfTanks.exe"))

    # ── OBS Browser-Source automation ────────────────────────────────────────

    def add_obs_source(self, url: str, password: str | None = None,
                       source_name: str = "DamageRace Overlay") -> dict:
        """Create a Browser Source in the current OBS scene that points at
        ``url``. Returns one of:

        * ``{"ok": True, "scene": "...", "input": "..."}`` on success.
        * ``{"ok": False, "needs_password": True}`` when auth is required.
        * ``{"ok": False, "error": "<short message>"}`` on any other failure.

        Stores the password in user-settings on the first successful auth so
        future calls don't prompt again.
        """
        if not url:
            return {"ok": False, "error": "missing_url"}
        try:
            import obsws_python as obs
        except ImportError:
            return {"ok": False, "error": "obsws_python not installed"}

        pw = password or self._settings_get("obs_password") or ""
        try:
            client = obs.ReqClient(host=OBS_DEFAULT_HOST,
                                   port=OBS_DEFAULT_PORT,
                                   password=pw, timeout=5)
        except Exception as exc:  # connection refused, auth failure, etc.
            msg = str(exc).lower()
            if "auth" in msg or "password" in msg or "challenge" in msg:
                return {"ok": False, "needs_password": True}
            if "refus" in msg or "timed out" in msg or "connection" in msg:
                return {"ok": False, "error": "obs_not_reachable"}
            log.warning("OBS connect failed: %s", exc)
            return {"ok": False, "error": "obs_connect_failed"}

        try:
            scene_resp = client.get_current_program_scene()
            scene = (getattr(scene_resp, "current_program_scene_name", None)
                     or getattr(scene_resp, "scene_name", None))
            if not scene:
                return {"ok": False, "error": "no_active_scene"}

            input_name = source_name
            client.create_input(
                scene_name=scene,
                input_name=input_name,
                input_kind="browser_source",
                input_settings={
                    "url": url,
                    "width": OVERLAY_WIDTH,
                    "height": OVERLAY_HEIGHT,
                    "reroute_audio": False,
                    "shutdown": True,
                },
                scene_item_enabled=True,
            )
            if password:
                self._settings_set("obs_password", password)
            return {"ok": True, "scene": scene, "input": input_name}
        except Exception as exc:
            msg = str(exc)
            if "exists" in msg.lower() or "input already" in msg.lower():
                return {"ok": True, "scene": scene, "input": source_name,
                        "note": "source_already_present"}
            log.warning("OBS create_input failed: %s", exc)
            return {"ok": False, "error": "obs_create_failed",
                    "detail": msg[:200]}
