"""Construcción de datos para el informe comparativo (usa repository.get_report_data)."""
from __future__ import annotations

from ..storage.repository import get_report_data


def build_report_data(db, search_id: int) -> dict:
    """Devuelve el diccionario de datos listo para el PDF o la vista."""
    return get_report_data(db, search_id)
