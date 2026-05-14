"""
build_exe.py — Baut DamageChallenge-Install.exe mit PyInstaller.

Voraussetzungen:
    pip install pyinstaller flask flask-cors customtkinter

Aufruf:
    python build_exe.py

Ergebnis: dist/DamageChallenge-Install.exe
"""

import os
import sys
import shutil
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("\n>>> " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print("FEHLER! Build abgebrochen.")
        sys.exit(r.returncode)


def clean():
    for d in ["build", "__pycache__"]:
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    for spec in ["DamageChallenge-Install.spec"]:
        p = os.path.join(ROOT, spec)
        if os.path.isfile(p):
            os.remove(p)


def build_installer():
    wotmod = os.path.join(ROOT, "dist", "mohjobeist_beastsync.wotmod")
    if not os.path.isfile(wotmod):
        print("WARNUNG: dist/mohjobeist_beastsync.wotmod fehlt.")
        print("         Zuerst ausführen: python2.7 mod/build_wotmod.py")
        os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
        open(wotmod, "wb").close()  # Platzhalter

    sep = os.pathsep  # ; auf Windows, : auf Linux

    run([
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",      "DamageChallenge-Install",
        "--add-data",  f"installer_config.json{sep}.",
        "--add-data",  f"dist/mohjobeist_beastsync.wotmod{sep}dist",
        "--hidden-import", "customtkinter",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--collect-data",  "customtkinter",
        "installer_gui.py",
    ])


if __name__ == "__main__":
    print("=== BeastSync — Installer Build ===")
    clean()
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    build_installer()
    clean()
    print("\n=== FERTIG ===")
    print("dist/DamageChallenge-Install.exe  ← an Streamer verteilen")
