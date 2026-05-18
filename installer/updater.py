"""Self-update mechanism for the DamageRace desktop client.

The flow is two-stage because Windows refuses to overwrite a running EXE:

1. The current EXE polls the GitHub Releases API. If a newer tag exists,
   it downloads the new EXE into ``%TEMP%`` and shows a modal prompting
   the user to install. On confirmation it spawns the freshly downloaded
   EXE with ``--replace <path-to-current-exe>`` and exits.

2. The newly downloaded EXE — booted with the ``--replace`` flag —
   waits a moment for the old process to release the file, copies itself
   over the original install path, spawns that copy with no flags, and
   exits.

Update checks are only meaningful for frozen builds; in dev (running
``python installer_gui.py``) the module short-circuits.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("damagerace.updater")

ASSET_NAME = "DamageRace.exe"
USER_AGENT = "DamageRace-Updater"
REPLACE_FLAG = "--replace"


def _parse_semver(tag: str) -> tuple[int, ...]:
    """``v1.2.3`` → ``(1, 2, 3)``. Non-numeric segments become 0."""
    cleaned = tag.lstrip("vV").split("-")[0]
    parts = []
    for part in cleaned.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts) or (0,)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _fetch_latest(repo: str) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
        log.info("Update check skipped: %s", exc)
        return None


def _download(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        log.warning("Update download failed: %s", exc)
        return False


def check_for_update(repo: str, current_version: str) -> dict | None:
    """Return ``{'tag': str, 'download_url': str}`` if a newer release exists."""
    if not _is_frozen():
        log.debug("Skipping update check in dev build.")
        return None
    data = _fetch_latest(repo)
    if not data:
        return None
    latest_tag = data.get("tag_name") or ""
    if _parse_semver(latest_tag) <= _parse_semver(current_version):
        return None
    asset_url = None
    for asset in data.get("assets") or []:
        if asset.get("name") == ASSET_NAME:
            asset_url = asset.get("browser_download_url")
            break
    if not asset_url:
        log.warning("Latest release %s has no %s asset.", latest_tag, ASSET_NAME)
        return None
    return {"tag": latest_tag, "download_url": asset_url}


def apply_update(download_url: str) -> bool:
    """Download the new EXE, spawn it with --replace pointing at the
    currently running EXE, and return True so the caller can exit."""
    current_exe = sys.executable if _is_frozen() else None
    if not current_exe:
        return False
    tmp_dir = os.environ.get("TEMP") or os.path.expanduser("~")
    new_exe = os.path.join(tmp_dir, f"DamageRace-update-{int(time.time())}.exe")
    if not _download(download_url, new_exe):
        return False
    try:
        subprocess.Popen([new_exe, REPLACE_FLAG, current_exe],
                         close_fds=True, creationflags=0x00000008)  # DETACHED_PROCESS
        return True
    except OSError as exc:
        log.warning("Could not launch updater: %s", exc)
        return False


def handle_replace_flag() -> None:
    """If invoked with ``--replace <target>``, perform the copy-over then
    relaunch the target. Call this as the very first thing in ``__main__``."""
    if len(sys.argv) < 3 or sys.argv[1] != REPLACE_FLAG:
        return
    target = sys.argv[2]
    log.info("Replace mode active; copying self -> %s", target)
    # Give the old process a moment to release the file handle.
    for attempt in range(20):
        try:
            shutil.copy2(sys.executable, target)
            break
        except OSError:
            time.sleep(0.5)
    else:
        log.error("Update copy failed after retries; bailing.")
        sys.exit(1)
    try:
        subprocess.Popen([target], close_fds=True, creationflags=0x00000008)
    except OSError as exc:
        log.error("Could not launch updated EXE: %s", exc)
    sys.exit(0)


def check_in_background(repo: str, current_version: str,
                        on_available) -> None:
    """Run ``check_for_update`` in a daemon thread; call ``on_available(info)``
    on the calling thread's behalf — the caller is responsible for marshalling
    back to the GUI thread (e.g. via ``Tk.after``)."""
    def _worker():
        info = check_for_update(repo, current_version)
        if info:
            on_available(info)
    threading.Thread(target=_worker, daemon=True).start()
