"""
build_wotmod.py — Baut mohjobeist_beastsync.wotmod

Voraussetzung: Python 2.7 muss installiert sein.
Aufruf: python2.7 build_wotmod.py
"""

import os
import sys
import py_compile
import zipfile
import shutil
import tempfile

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
SOURCE_PY     = os.path.join(SCRIPT_DIR, 'mod_mohjobeist_beastsync.py')
DIST_DIR      = os.path.join(SCRIPT_DIR, '..', 'dist')
OUTPUT        = os.path.join(DIST_DIR, 'mohjobeist_beastsync.wotmod')
INTERNAL_PATH = 'res/scripts/client/gui/mods/mod_mohjobeist_beastsync.pyc'


def build():
    if not os.path.exists(SOURCE_PY):
        print('FEHLER: Quelldatei nicht gefunden: %s' % SOURCE_PY)
        sys.exit(1)

    if sys.version_info[0] != 2 or sys.version_info[1] < 7:
        print('WARNUNG: Python 2.7 benoetigt! Aktuell: %s' % sys.version)
        print('')

    tmp_dir  = tempfile.mkdtemp()
    pyc_path = os.path.join(tmp_dir, 'mod_mohjobeist_beastsync.pyc')

    try:
        print('Kompiliere %s ...' % SOURCE_PY)
        py_compile.compile(SOURCE_PY, pyc_path, doraise=True)
        print('  OK')

        if not os.path.exists(DIST_DIR):
            os.makedirs(DIST_DIR)

        print('Paketiere %s ...' % OUTPUT)
        with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(pyc_path, INTERNAL_PATH)
        print('  OK: %s' % OUTPUT)

        print('')
        print('Fertig! Naechste Schritte:')
        print('  1. dist/mohjobeist_beastsync.wotmod  →  World_of_Tanks/mods/')
        print('  2. Config-Vorlage (mod/config.example.json) kopieren nach:')
        print('     World_of_Tanks/res_mods/<version>/mods/beastsync/config.json')

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    build()
