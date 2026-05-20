# -*- coding: utf-8 -*-
"""Build the mohjos_damagerace.wotmod archive.

WoT (1.x and 2.x) ignores .py files inside a .wotmod and only executes
.pyc bytecode under res/scripts/client/gui/mods/. The bytecode magic has
to match the interpreter shipped with WoT, which is still Python 2.7.

Usage:

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
INTERNAL_PY   = 'res/scripts/client/gui/mods/mod_mohjos_damagerace.py'
INTERNAL_PYC  = 'res/scripts/client/gui/mods/mod_mohjos_damagerace.pyc'

MOD_ID      = 'com.mohjos.damagerace'
MOD_NAME    = 'Mohjos DamageRace'
MOD_VERSION = '1.0.1'
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
        print('ERROR: Python 2.7 is required to produce WoT-compatible '
              'bytecode. Current interpreter: %s' % sys.version)
        sys.exit(1)

    tmp_dir = tempfile.mkdtemp()
    pyc_path = os.path.join(tmp_dir, 'mod_mohjos_damagerace.pyc')

    try:
        print('Compiling %s' % SOURCE_PY)
        py_compile.compile(SOURCE_PY, pyc_path, doraise=True)
        print('  OK')

        if not os.path.exists(DIST_DIR):
            os.makedirs(DIST_DIR)

        print('Packaging %s' % OUTPUT)
        # ZIP_STORED -- some WoT loaders reject deflated archives.
        with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_STORED) as zf:
            zf.writestr('meta.xml', META_XML)
            zf.write(SOURCE_PY, INTERNAL_PY)     # source for reference
            zf.write(pyc_path,  INTERNAL_PYC)    # actual entry point
        print('  OK: %s' % OUTPUT)

        print('')
        print('Done. Install dist/mohjos_damagerace.wotmod into:')
        print('    <WoT>/mods/<version>/mohjos_damagerace.wotmod')

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    build()
