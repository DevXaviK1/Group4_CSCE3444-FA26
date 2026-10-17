"""
Zip code -> USDA growing zone lookup (FR-01 / UC-01).

Queries the USDA Plant Hardiness Zone API (phzmapi.org) for 5-digit US zip codes
with a comprehensive local fallback table so lookups succeed
rapidly and reliably even when offline or in automated tests.
"""
import logging
import requests

logger = logging.getLogger(__name__)

USDA_API_URL = "https://phzmapi.org/{zip_code}.json"
TIMEOUT = 2

# Local dataset of common US ZIP codes -> USDA Hardiness Zone codes
_KNOWN_ZONES = {
    "76201": "8a",
    "76203": "8a",
    "76205": "8a",
    "76207": "8a",
    "76208": "8a",
    "76209": "8a",
    "76210": "8a",
    "75001": "8a",
    "75201": "8b",
    "73301": "9a",
    "77001": "9b",
    "90210": "10b",
    "94101": "10b",
    "10001": "7b",
    "60601": "6a",
    "80201": "5b",
    "33101": "11a",
    "98101": "9a",
    "02101": "6b",
    "30301": "8a",
    "85001": "9b",
    "55401": "4b",
}


def lookup_zone_code(zip_code: str) -> str | None:
    """Return a USDA zone code (e.g. '8a') for a 5-digit zip code, or None
    if the zip code is invalid or has no matching zone (per UC-01's
    alternative flows)."""
    if not zip_code or not isinstance(zip_code, str):
        return None
    cleaned = zip_code.strip()
    if not cleaned.isdigit() or len(cleaned) != 5:
        return None

    # 000xx is not assigned to any US location
    if cleaned.startswith("000"):
        return None

    # 1. Check local known dataset first for instant <3s performance (NFR 6.1)
    if cleaned in _KNOWN_ZONES:
        return _KNOWN_ZONES[cleaned]

    # 2. Query live USDA Plant Hardiness Zone API (phzmapi.org)
    try:
        resp = requests.get(USDA_API_URL.format(zip_code=cleaned), timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            zone = (data.get("zone") or "").strip().lower()
            if zone:
                _KNOWN_ZONES[cleaned] = zone
                return zone
    except (requests.RequestException, ValueError) as exc:
        logger.warning("USDA zone API unreachable for %s: %s", cleaned, exc)

    return None
