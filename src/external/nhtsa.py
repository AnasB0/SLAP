from __future__ import annotations

import time
from typing import Any

import httpx


_CACHE: dict[tuple[str, str, int], tuple[float, dict[str, Any]]] = {}
_TTL_SECONDS = 900


def get_nhtsa_recalls(make: str, model: str, year: int) -> dict[str, Any]:
    cache_key = (make.lower(), model.lower(), year)
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached and now - cached[0] < _TTL_SECONDS:
        return cached[1]

    url = "https://api.nhtsa.gov/recalls/recallsByVehicle"
    params = {"make": make, "model": model, "modelYear": year}
    fallback = {
        "source": "demo",
        "api_available": False,
        "message": "External API unavailable — showing cached/demo context.",
        "results": [],
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        _CACHE[cache_key] = (now, fallback)
        return fallback

    results = payload.get("results", []) if isinstance(payload, dict) else []
    data = {
        "source": "nhtsa",
        "api_available": True,
        "message": "Live recall context loaded.",
        "results": [
            {
                "campaign": item.get("NHTSACampaignNumber", "N/A"),
                "component": item.get("Component", "N/A"),
                "summary": item.get("Summary", "No summary available."),
            }
            for item in results[:5]
        ],
    }
    _CACHE[cache_key] = (now, data)
    return data
