"""Cliente para la API de precios de carburantes del Ministerio (EstacionesTerrestres)."""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..geo.distance import is_within_radius_km

MINETUR_URL = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/"
    "PreciosCarburantes/EstacionesTerrestres/"
)

# Mapeo: nombre canónico nuestro -> posibles claves en el JSON del Ministerio
# (el API puede devolver "Precio Gasolina 95 E5" o "Precio_x0020_Gasolina_x0020_95_x0020_E5")
PRODUCT_TO_MINETUR_KEYS = {
    "Sin Plomo 95": [
        "Precio Gasolina 95 E5",
        "Precio_x0020_Gasolina_x0020_95_x0020_E5",
        "PrecioGasolina95E5",
    ],
    "Sin Plomo 98": [
        "Precio Gasolina 98 E5",
        "Precio_x0020_Gasolina_x0020_98_x0020_E5",
        "PrecioGasolina98E5",
    ],
    "Gasóleo A": [
        "Precio Gasoleo A",
        "Precio_x0020_Gasoleo_x0020_A",
        "PrecioGasoleoA",
    ],
    "Gasóleo A+": [
        "Precio Gasoleo Premium",
        "Precio_x0020_Gasoleo_x0020_Premium",
        "PrecioGasoleoPremium",
    ],
    "Gasóleo B": [
        "Precio Gasoleo B",
        "Precio_x0020_Gasoleo_x0020_B",
    ],
    "GLP": [
        "Precio Gases licuados del petróleo",
        "Precio GLP",
        "Precio_x0020_GLP",
    ],
}


def _float_safe(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if 0.3 < val < 10.0:
            return float(val)
        return None
    s = str(val).strip().replace(",", ".")
    m = re.search(r"(\d+\.?\d*)", s)
    if not m:
        return None
    try:
        f = float(m.group(1))
        return f if 0.3 < f < 10.0 else None
    except ValueError:
        return None


def _lat_lng_safe(station: dict) -> tuple[float | None, float | None]:
    lat = station.get("Latitud") or station.get("latitud")
    lng = (
        station.get("Longitud")
        or station.get("longitud")
        or station.get("Longitud (WGS84)")
    )
    if lat is None or lng is None:
        return None, None
    try:
        return float(str(lat).replace(",", ".")), float(str(lng).replace(",", "."))
    except (ValueError, TypeError):
        return None, None


def _extract_price_for_product(station: dict, canonical_product: str) -> float | None:
    keys = PRODUCT_TO_MINETUR_KEYS.get(canonical_product, [])
    for key in keys:
        if key in station and station[key] not in (None, ""):
            return _float_safe(station[key])
    return None


def fetch_estaciones_terrestres(timeout: float = 25.0) -> list[dict]:
    """
    Descarga el listado completo de estaciones terrestres con precios (JSON).
    Devuelve lista de diccionarios; cada uno puede tener Rótulo, Dirección, Localidad, Latitud, Longitud y campos Precio_*.
    """
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(
                MINETUR_URL,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Algunos endpoints devuelven {"ListaEESSPrecio": [...]}
        for key in ("ListaEESSPrecio", "listaEESSPrecio", "data", "result"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def get_gas_stations_near(
    center_lat: float,
    center_lng: float,
    radius_km: float = 50.0,
    canonical_products: list[str] | None = None,
) -> list[dict]:
    """
    Obtiene gasolineras con precios en un radio (km) del punto dado.
    Cada elemento devuelto: {
      "name": str,       # Rótulo o Dirección
      "address": str,
      "lat": float, "lng": float,
      "prices": { "Sin Plomo 95": 1.75, ... }  # solo productos con precio
    }
    """
    stations_raw = fetch_estaciones_terrestres()
    products = canonical_products or list(PRODUCT_TO_MINETUR_KEYS)
    result = []

    for raw in stations_raw:
        lat, lng = _lat_lng_safe(raw)
        if lat is None or lng is None:
            continue
        if not is_within_radius_km(center_lat, center_lng, lat, lng, radius_km):
            continue

        name = (raw.get("Rótulo") or raw.get("Rotulo") or raw.get("Dirección") or "").strip()
        if not name:
            name = (raw.get("Direccion") or raw.get("Localidad") or "Gasolinera").strip()
        address = (raw.get("Dirección") or raw.get("Direccion") or "").strip()
        if address and raw.get("Localidad"):
            address = f"{address}, {raw.get('Localidad')}"

        prices = {}
        for prod in products:
            p = _extract_price_for_product(raw, prod)
            if p is not None:
                prices[prod] = round(p, 3)

        result.append({
            "name": name or "Gasolinera",
            "address": address or name,
            "lat": lat,
            "lng": lng,
            "prices": prices,
        })

    return result
