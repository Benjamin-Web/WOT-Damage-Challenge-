"""Runtime configuration for the DamageRace server."""
import os

PORT = int(os.environ.get("PORT", 5000))

# Public base URL used to build redirect targets and invite links. Required
# behind a reverse proxy because Flask cannot deduce the public scheme/host
# from the upstream socket.
PUBLIC_BASE_URL = os.environ.get(
    "PUBLIC_BASE_URL",
    "https://mohjos-damagerace.duckdns.org",
)
