"""
Zip code -> USDA growing zone lookup (UC-01).

TODO (whoever picks up FR-01): replace this stub with a real call to the
USDA Plant Hardiness Zone data source. For now this returns a hardcoded
zone so the rest of the app has something to build against.

Keep the function signature the same (zip_code in, zone_code out or None)
so nothing else has to change when the real lookup is wired in.
"""

# Temporary hardcoded stand-in for the real USDA lookup.
_STUB_ZONES = {
    "76201": "8a",
    "76205": "8a",
    "75001": "8a",
    "90210": "10b",
    "10001": "7b",
}


def lookup_zone_code(zip_code: str) -> str | None:
    """Return a USDA zone code (e.g. '8a') for a 5-digit zip code, or None
    if the zip code is invalid or has no matching zone (per UC-01's
    alternative flows)."""
    if not zip_code or not zip_code.isdigit() or len(zip_code) != 5:
        return None
    return _STUB_ZONES.get(zip_code)
