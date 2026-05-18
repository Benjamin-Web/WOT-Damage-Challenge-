"""Bundle the DamageRace desktop client into a single-file Windows executable.

Prerequisites (install once into your Python 3.x environment):

    pip install pyinstaller customtkinter

Usage:

    python build_exe.py

The resulting binary is written to ``dist/DamageRace.exe``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE_NAME = "DamageRace"
SPEC_FILE = f"{EXE_NAME}.spec"


def run(cmd: list[str]) -> None:
    print("\n>>> " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"ERROR: build failed with exit code {result.returncode}.")
        sys.exit(result.returncode)


def clean_artifacts() -> None:
    for directory in ("build", "__pycache__"):
        path = os.path.join(ROOT, directory)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    spec_path = os.path.join(ROOT, SPEC_FILE)
    if os.path.isfile(spec_path):
        os.remove(spec_path)


def ensure_wotmod() -> None:
    wotmod = os.path.join(ROOT, "dist", "mohjos_damagerace.wotmod")
    if os.path.isfile(wotmod):
        return
    print("WARNING: dist/mohjos_damagerace.wotmod missing.")
    print("         Run first: C:\\Python27\\python.exe mod\\build_wotmod.py")
    os.makedirs(os.path.dirname(wotmod), exist_ok=True)
    # Embed an empty placeholder so PyInstaller doesn't fail; participants will
    # see a clear install error if the binary ever ships without the mod.
    open(wotmod, "wb").close()


def build_installer() -> None:
    sep = os.pathsep
    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name",          EXE_NAME,
        "--add-data",      f"installer_config.json{sep}.",
        "--add-data",      f"dist/mohjos_damagerace.wotmod{sep}dist",
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "webview",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "installer.updater",
        "--hidden-import", "installer.bridge",
        "--hidden-import", "obsws_python",
        "--collect-data",  "customtkinter",
        "--collect-data",  "webview",
        "--collect-submodules", "webview",
        "installer_gui.py",
    ])


def main() -> None:
    print("=== Mohjos DamageRace — desktop client build ===")
    clean_artifacts()
    ensure_wotmod()
    build_installer()
    clean_artifacts()
    print(f"\n=== Done ===\ndist/{EXE_NAME}.exe  <- distribute to streamers")


if __name__ == "__main__":
    main()
