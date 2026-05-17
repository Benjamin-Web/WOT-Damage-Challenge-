# -*- coding: utf-8 -*-
"""Build the mohjos_damagerace.wotmod archive.

Requires Python 2.7 because the compiled .pyc has to match the WoT runtime
bytecode magic. Usage:

    C:\\Python27\\python.exe mod\\build_wotmod.py
"""
import os
import py_compile
import shutil
import sys
import tempfile
import zipfile

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
SOURCE_PY     = os.path.join(SCRIPT_DIR, 'mod_mohjos_damagerace.py')
DIST_DIR      = os.path.join(SCRIPT_DIR, '..', 'dist')
OUTPUT        = os.path.join(DIST_DIR, 'mohjos_damagerace.wotmod')
INTERNAL_PATH = 'res/scripts/client/gui/mods/mod_mohjos_damagerace.pyc'

MOD_ID      = 'com.mohjos.damagerace'
MOD_NAME    = 'Mohjos DamageRace'
MOD_VERSION = '1.0.0'
MOD_DESC    = 'Community Damage Race tracker for World of Tanks.'

META_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<root>\n'
    '  <id>%s</id>\n'
    '  <version>%s</version>\n'
    '  <name>%s</name>\n'
    '  <description>%s</description>\n'
    '</root>\n'
) % (MOD_ID, MOD_VERSION, MOD_NAME, MOD_DESC)


def build():
    if not os.path.exists(SOURCE_PY):
        print('ERROR: Source file not found: %s' % SOURCE_PY)
        sys.exit(1)

    if sys.version_info[0] != 2 or sys.version_info[1] < 7:
        print('WARNING: Python 2.7 required. Current: %s' % sys.version)

    tmp_dir = tempfile.mkdtemp()
    pyc_path = os.path.join(tmp_dir, 'mod_mohjos_damagerace.pyc')

    try:
        print('Compiling %s' % SOURCE_PY)
        py_compile.compile(SOURCE_PY, pyc_path, doraise=True)
        print('  OK')

        if not os.path.exists(DIST_DIR):
            os.makedirs(DIST_DIR)

        print('Packaging %s' % OUTPUT)
        with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_STORED) as zf:
            zf.writestr('meta.xml', META_XML)
            zf.write(pyc_path, INTERNAL_PATH)
        print('  OK: %s' % OUTPUT)

        print('')
        print('Done. Next steps:')
        print('  1. dist/mohjos_damagerace.wotmod -> World_of_Tanks/mods/<version>/')
        print('  2. Config in: World_of_Tanks/res_mods/<version>/mods/damagerace/config.json')

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    build()
