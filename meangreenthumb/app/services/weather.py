"""Weather service: UC-04 (forecast + cache fallback) and UC-05 (freeze/frost status).

Everything is keyed by 5-digit ZIP code to match the SDD (ZipWeatherStatus).
NWS has no ZIP lookup, so a ZIP is resolved to lat/lon once (zippopotam.us) and
NWS is queried by point.
"""
import json
import logging
import re
from datetime import datetime
from functools import lru_cache
from typing import Literal, Optional

import requests

from app import db
from app.models import WeatherCache

logger = logging.getLogger(__name__)

# NWS requires an identifying User-Agent. Put a real contact here before deploying.
USER_AGENT = "MeanGreenThumb/1.0 (http://127.0.0.1:5000/; contact:)"
NWS = "https://api.weather.gov"
TIMEOUT = 10
ZIP_RE = re.compile(r"^\d{5}$")

StatusType = Literal["none", "watch", "warning"]
WARNING_EVENTS = {"Freeze Warning", "Frost Advisory", "Hard Freeze Warning"}
WATCH_EVENTS = {"Freeze Watch", "Hard Freeze Watch"}


class WeatherUnavailable(Exception):
    """NOAA (or the ZIP lookup) could not be reached or returned bad data."""


@lru_cache(maxsize=2048)
def _coords(zip_code: str) -> tuple:
    try:
        resp = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=TIMEOUT)
        resp.raise_for_status()
        place = resp.json()["places"][0]
        # NWS /points rejects more than 4 decimal places
        return round(float(place["latitude"]), 4), round(float(place["longitude"]), 4)
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise WeatherUnavailable(f"ZIP lookup failed for {zip_code}") from exc


def _nws_get(url: str, params: Optional[dict] = None) -> dict:
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise WeatherUnavailable(f"NWS request failed: {url}") from exc


# ---------------------------------------------------------------- UC-05 ----
def _fetch_freeze_alerts(zip_code: str) -> list:
    lat, lon = _coords(zip_code)
    data = _nws_get(f"{NWS}/alerts/active", {"point": f"{lat},{lon}"})
    alerts = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if props.get("status") != "Actual":  # skip Test alerts
            continue
        if props.get("event") in WARNING_EVENTS | WATCH_EVENTS:
            alerts.append(props)
    return alerts


def get_freeze_status(zip_code: str) -> Optional[StatusType]:
    """'none' | 'watch' | 'warning', or None if it could not be determined.

    None means UNKNOWN, not "no freeze": callers must skip and retry next cycle.
    """
    try:
        events = {a["event"] for a in _fetch_freeze_alerts(zip_code)}
    except WeatherUnavailable as exc:
        logger.error("Freeze status unavailable for %s: %s", zip_code, exc)
        return None
    if events & WARNING_EVENTS:
        return "warning"
    if events & WATCH_EVENTS:
        return "watch"
    return "none"


def get_alert_details(zip_code: str) -> Optional[list]:
    """Active freeze/frost alerts for the Alert Details screen; None if unavailable."""
    try:
        return [
            {
                "event": a["event"],
                "headline": a.get("headline"),
                "onset": a.get("onset") or a.get("effective"),
                "expires": a.get("expires") or a.get("ends"),
                "area": a.get("areaDesc"),
                "description": a.get("description"),
            }
            for a in _fetch_freeze_alerts(zip_code)
        ]
    except WeatherUnavailable as exc:
        logger.error("Alert details unavailable for %s: %s", zip_code, exc)
        return None


# ---------------------------------------------------------------- UC-04 ----
def _precip(period: dict):
    return (period.get("probabilityOfPrecipitation") or {}).get("value")


def _fetch_forecast(zip_code: str) -> dict:
    lat, lon = _coords(zip_code)
    point = _nws_get(f"{NWS}/points/{lat},{lon}")["properties"]
    hourly = _nws_get(point["forecastHourly"])["properties"]["periods"][0]
    periods = _nws_get(point["forecast"])["properties"]["periods"][:10]  # 5 days, day+night
    return {
        "current": {
            "temperature": hourly["temperature"],
            "unit": hourly["temperatureUnit"],
            "summary": hourly["shortForecast"],
            "precip_chance": _precip(hourly),
        },
        "daily": [
            {
                "name": p["name"],
                "temperature": p["temperature"],
                "unit": p["temperatureUnit"],
                "summary": p["shortForecast"],
                "precip_chance": _precip(p),
            }
            for p in periods
        ],
        "fetched_at": datetime.utcnow().isoformat(timespec="minutes"),
    }


def _save_cache(zip_code: str, data: dict) -> None:
    row = db.session.get(WeatherCache, zip_code)
    if row is None:
        row = WeatherCache(zip_code=zip_code)
        db.session.add(row)
    row.payload = json.dumps(data)
    row.fetched_at = datetime.utcnow()
    db.session.commit()


def _load_cache(zip_code: str) -> Optional[dict]:
    row = db.session.get(WeatherCache, zip_code)
    return json.loads(row.payload) if row else None


def get_forecast(zip_code: str) -> dict:
    """Current conditions + 5-day forecast, with 'outdated' set when served from cache.

    Raises WeatherUnavailable only if NOAA fails AND nothing is cached.
    """
    try:
        data = _fetch_forecast(zip_code)
    except (WeatherUnavailable, KeyError, IndexError) as exc:
        cached = _load_cache(zip_code)
        if cached is None:
            raise WeatherUnavailable(f"No forecast or cache for {zip_code}") from exc
        cached["outdated"] = True
        return cached
    _save_cache(zip_code, data)
    data["outdated"] = False
    return data