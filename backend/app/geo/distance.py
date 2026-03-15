from __future__ import annotations

import math


def haversine_distance_km(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Distancia aproximada en km entre dos puntos (lat/lng)."""
    r = 6371.0  # radio de la Tierra en km

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def is_within_radius_km(
    center_lat: float, center_lng: float, point_lat: float, point_lng: float, radius_km: float
) -> bool:
    """Devuelve True si el punto está dentro del radio indicado."""
    return haversine_distance_km(center_lat, center_lng, point_lat, point_lng) <= radius_km

