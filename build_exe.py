"""
build_exe.py — Baut beide .exe Dateien mit PyInstaller.

Voraussetzungen:
    pip install pyinstaller flask flask-cors

Aufruf:
    python build_exe.py

Ergebnis in dist/:
    DamageChallenge-Server.exe    (Veranstalter)
    DamageChallenge-Install.exe   (jeder Streamer)
"""

import os
import sys
import shutil
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print('\n>>> ' + ' '.join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print('FEHLER! Build abgebrochen.')
        sys.exit(result.returncode)


def clean():
    for d in ['build', '__pycache__']:
        if os.path.isdir(os.path.join(ROOT, d)):
            shutil.rmtree(os.path.join(ROOT, d))
    for spec in ['DamageChallenge-Server.spec', 'DamageChallenge-Install.spec']:
        p = os.path.join(ROOT, spec)
        if os.path.isfile(p):
            os.remove(p)


def build_server():
    """Server-Exe: Flask + tkinter, inkl. overlay/ und server/ als Ressourcen."""
    data_args = [
        '--add-data', 'overlay' + os.pathsep + 'overlay',
        '--add-data', 'server'  + os.pathsep + 'server',
    ]
    run([
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',                          # kein Konsolenfenster
        '--name', 'DamageChallenge-Server',
        '--icon', _icon('server'),
        *data_args,
        '--hidden-import', 'flask',
        '--hidden-import', 'flask_cors',
        '--hidden-import', 'engineio',
        'server_gui.py',
    ])


def build_installer():
    """Installer-Exe: tkinter Wizard, inkl. fertigem .wotmod."""
    # .wotmod muss vorher mit build_wotmod.py erzeugt worden sein
    wotmod = os.path.join(ROOT, 'dist', 'mohjobeist_beastsync.wotmod')
    if not os.path.isfile(wotmod):
        print('WARNUNG: dist/mohjobeist_beastsync.wotmod nicht gefunden.')
        print('         Fuehre zuerst: python2.7 mod/build_wotmod.py aus')
        print('         Installer wird ohne Mod gebaut (Platzhalter).')
        # Platzhalter-Datei erstellen damit PyInstaller nicht abbricht
        os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
        with open(wotmod, 'wb') as f:
            f.write(b'PLACEHOLDER')

    run([
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'DamageChallenge-Install',
        '--icon', _icon('install'),
        '--add-data', 'dist/mohjobeist_beastsync.wotmod' + os.pathsep + 'dist',
        'installer_gui.py',
    ])


def _icon(name):
    """Icon-Pfad; falls nicht vorhanden, keinen Icon-Parameter verwenden."""
    ico = os.path.join(ROOT, 'assets', name + '.ico')
    if os.path.isfile(ico):
        return ico
    # PyInstaller akzeptiert keinen leeren --icon; Default-Icon verwenden
    return 'NONE'


if __name__ == '__main__':
    print('=== Damage Challenge — Exe Build ===')
    clean()
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)

    build_server()
    build_installer()

    # Spec-Dateien aufraumen
    clean()

    print('\n=== FERTIG ===')
    print('dist/DamageChallenge-Server.exe   ← Veranstalter')
    print('dist/DamageChallenge-Install.exe  ← Jeder Streamer')
