from __future__ import annotations

from typing import Optional, Tuple

import httpx


async def geocode_with_nominatim(query: str) -> Optional[Tuple[float, float]]:
    """
    Geocoding sencillo usando Nominatim (OpenStreetMap).

    Pensado para desarrollo/pruebas. En producción conviene respetar
    estrictamente los términos de uso y considerar un proveedor con SLA
    (por ejemplo, Google Geocoding API).
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    headers = {
        "User-Agent": "local-price-scraper/1.0 (example)"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            return None

        first = data[0]
        return float(first["lat"]), float(first["lon"])

