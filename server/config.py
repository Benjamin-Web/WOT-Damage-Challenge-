"""
config.py — Mohjos DamageRace Server-Konfiguration
"""
import os

PORT         = int(os.environ.get('PORT', 5000))

# Public Base-URL fuer Invite-Links + OAuth-Redirect
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'https://mohjos-damagerace.duckdns.org')
