# -*- coding: utf-8 -*-
"""Build the mohjos_damagerace.wotmod archive.

We ship the .py source file rather than a precompiled .pyc so the WoT
client compiles the module with its own Python (3.8 on 2.x clients, 2.7
on legacy 1.x clients). This avoids the bytecode magic mismatch that
crashes WoT when the .pyc is built with the wrong interpreter.

Usage:

    python mod\\build_wotmod.py
"""
from __future__ import print_function

import os
import shutil
import sys
import tempfile
import zipfile

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
SOURCE_PY     = os.path.join(SCRIPT_DIR, 'mod_mohjos_damagerace.py')
DIST_DIR      = os.path.join(SCRIPT_DIR, '..', 'dist')
OUTPUT        = os.path.join(DIST_DIR, 'mohjos_damagerace.wotmod')
INTERNAL_PATH = 'res/scripts/client/gui/mods/mod_mohjos_damagerace.py'

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

    if not os.path.exists(DIST_DIR):
        os.makedirs(DIST_DIR)

    print('Packaging %s' % OUTPUT)
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_STORED) as zf:
        zf.writestr('meta.xml', META_XML)
        zf.write(SOURCE_PY, INTERNAL_PATH)
    print('  OK: %s' % OUTPUT)

    print('')
    print('Done. Next steps:')
    print('  1. dist/mohjos_damagerace.wotmod -> World_of_Tanks/mods/<version>/')
    print('  2. Config in: World_of_Tanks/res_mods/<version>/mods/damagerace/config.json')


if __name__ == '__main__':
    build()
