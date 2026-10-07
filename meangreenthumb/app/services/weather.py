"""
Per-zone freeze/frost status check (UC-05), queried by zone code rather
than by user so ~500 users sharing a handful of zones doesn't mean ~500
NOAA calls per cycle -- one call per unique zone instead.

TODO (whoever picks up the real integration): replace this stub with an
actual NOAA alerts API call keyed on zone/region. Keep the return value
the same ("none" | "watch" | "warning") so the scheduler doesn't need to
change when this gets wired up for real.

  "watch"   -> NWS Freeze Watch: lower confidence, typically 24-48 hrs
               of lead time. This is what gets you to the 24-hour notice
               goal -- alert on this, don't wait for "warning".
  "warning" -> NWS Freeze Warning / Frost Advisory: higher confidence,
               typically only 12-24 hrs of lead time.
"""

# Temporary hardcoded stand-in for the real NOAA lookup.
_STUB_STATUS = {
    "8a": "none",
    "10b": "none",
    "7b": "watch",
}


def get_freeze_status(zone_code: str) -> str:
    """Return 'none', 'watch', or 'warning' for the given zone code."""
    return _STUB_STATUS.get(zone_code, "none")
