from __future__ import annotations

import time
from typing import Any

import httpx


_CACHE: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}
_TTL_SECONDS = 900


def get_weather(latitude: float = 42.3314, longitude: float = -83.0458) -> dict[str, Any]:
    cache_key = (latitude, longitude)
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]

    fallback = {
        "source": "demo",
        "api_available": False,
        "message": "External API unavailable — showing cached/demo context.",
        "current": {
            "temperature": 23.0,
            "windspeed": 12.0,
            "weathercode": 1,
            "note": "Demo conditions: mild weather with no expected operational impact.",
        },
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current_weather": True,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        _CACHE[cache_key] = (now, fallback)
        return fallback

    current = payload.get("current_weather", {}) if isinstance(payload, dict) else {}
    data = {
        "source": "open-meteo",
        "api_available": True,
        "message": "Live weather context loaded.",
        "current": {
            "temperature": current.get("temperature"),
            "windspeed": current.get("windspeed"),
            "weathercode": current.get("weathercode"),
            "note": "Weather is supporting context only; deterministic root-cause rules remain primary.",
        },
    }
    _CACHE[cache_key] = (now, data)
    return data
