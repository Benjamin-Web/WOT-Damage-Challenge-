"""
config.py — Mohjos DamageRace Server-Konfiguration
"""
import os

PORT         = int(os.environ.get('PORT', 5000))
INITIAL_GOAL = 100000

# Veranstalter-Login (z.B. Mohjo_beist)
ADMIN_SECRET   = os.environ.get('ADMIN_SECRET',   'changeme123')
# Cookie-Signierung — lang & zufaellig
SESSION_SECRET = os.environ.get('SESSION_SECRET', 'BITTE-AENDERN-langer-zufaelliger-string')

# Public Base-URL fuer Einladungslinks im Admin-Panel
# In Docker via Env setzen: PUBLIC_BASE_URL=http://109.123.244.109:5000
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '')
