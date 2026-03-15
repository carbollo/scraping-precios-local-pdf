from __future__ import annotations

import unicodedata
from typing import Optional, Tuple

import httpx


def _normalize_province(name: str) -> str:
    """Minúsculas, sin acentos, para comparar con columnas de dieselogasolina."""
    if not name:
        return ""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.lower().strip()


async def geocode_with_nominatim(query: str) -> Optional[Tuple[float, float, Optional[str]]]:
    """
    Geocoding con Nominatim (OpenStreetMap).
    Devuelve (lat, lon, provincia) si hay addressdetails; provincia viene de county o state.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "local-price-scraper/1.0 (example)"}

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if not data:
        return None

    first = data[0]
    lat = float(first["lat"])
    lon = float(first["lon"])
    addr = first.get("address") or {}
    # En España: county suele ser la provincia (Málaga, Madrid); state la comunidad
    province = addr.get("county") or addr.get("state") or addr.get("municipality")
    return lat, lon, province

