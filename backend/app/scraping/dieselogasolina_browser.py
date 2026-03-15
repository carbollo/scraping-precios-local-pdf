"""
Extrae el listado de gasolineras con precios desde la web dieselogasolina.com
usando Playwright (la tabla se rellena por JavaScript).
"""
from __future__ import annotations

import re
from typing import Any

# Mapeo abreviaturas que puede mostrar la web -> nombre canónico nuestro
PRECIO_LABEL_TO_CANONICAL = {
    "sp95": "Sin Plomo 95",
    "sin plomo 95": "Sin Plomo 95",
    "gasolina 95": "Sin Plomo 95",
    "sp98": "Sin Plomo 98",
    "sin plomo 98": "Sin Plomo 98",
    "gasolina 98": "Sin Plomo 98",
    "ga": "Gasóleo A",
    "gasoleo a": "Gasóleo A",
    "gasóleo a": "Gasóleo A",
    "ga+": "Gasóleo A+",
    "gasoleo a+": "Gasóleo A+",
    "gasóleo a+": "Gasóleo A+",
    "gasoleo premium": "Gasóleo A+",
    "gb": "Gasóleo B",
    "gasoleo b": "Gasóleo B",
    "glp": "GLP",
    "autogas": "GLP",
}


def _normalize_price_text(text: str) -> float | None:
    """Extrae un precio de texto tipo '1,749' o '1.75 €'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\s]", "", text.strip()).replace(",", ".")
    m = re.search(r"(\d+\.?\d*)", cleaned)
    if not m:
        return None
    try:
        f = float(m.group(1))
        return round(f, 3) if 0.3 < f < 10.0 else None
    except ValueError:
        return None


def _parse_precios_cell(text: str) -> dict[str, float]:
    """Parsea la celda 'Precios' que puede contener 'SP95: 1,749  SP98: 1,899  GA: 1,749' etc."""
    result = {}
    if not text:
        return result
    # Patrones: "SP95: 1,749" o "Gasóleo A: 1.65" o "Sin plomo 95  1,749"
    # Buscar bloques que contengan posible etiqueta + número
    for key_canonical, canonical in PRECIO_LABEL_TO_CANONICAL.items():
        # Patrón: key seguido de : o espacios y luego número
        pat = re.compile(
            r"\b" + re.escape(key_canonical) + r"\s*[:\s]+\s*([\d.,]+)",
            re.IGNORECASE,
        )
        m = pat.search(text)
        if m:
            p = _normalize_price_text(m.group(1))
            if p is not None:
                result[canonical] = p
    # También buscar abreviaturas tipo "SP95" "GA" "GA+" seguidas de precio
    abrev = [
        ("sp95", "Sin Plomo 95"),
        ("sp98", "Sin Plomo 98"),
        ("ga\\+", "Gasóleo A+"),
        ("ga", "Gasóleo A"),
        ("gb", "Gasóleo B"),
        ("glp", "GLP"),
    ]
    for ab, canonical in abrev:
        if canonical in result:
            continue
        pat = re.compile(r"\b" + ab + r"\s*[:\s]+\s*([\d.,]+)", re.IGNORECASE)
        m = pat.search(text)
        if m:
            p = _normalize_price_text(m.group(1))
            if p is not None:
                result[canonical] = p
    return result


def fetch_gas_stations_from_dieselogasolina_page(
    url: str,
    *,
    timeout_ms: int = 25_000,
    wait_after_load_ms: int = 2_000,
) -> list[dict[str, Any]]:
    """
    Abre la URL de dieselogasolina.com (ej. gasolineras-en-malaga-localidad-alhaurin-de-la-torre.html),
    espera a que cargue el listado por JavaScript y extrae nombre, dirección y precios por gasolinera.

    Devuelve lista de:
      { "name": str, "address": str, "prices": { "Sin Plomo 95": 1.75, ... } }
    Si Playwright no está instalado o falla, devuelve [].
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    result: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Esperar a que aparezcan filas en la tabla (la web carga "Estamos cargando..." y luego rellena)
                page.wait_for_selector(
                    "table tbody tr",
                    timeout=timeout_ms,
                    state="visible",
                )
                page.wait_for_timeout(wait_after_load_ms)

                rows = page.query_selector_all("table tbody tr")
                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 5:
                        continue
                    localidad = (cells[0].inner_text() or "").strip()
                    direccion = (cells[1].inner_text() or "").strip()
                    empresa = (cells[4].inner_text() or "").strip() if len(cells) > 4 else ""
                    precios_text = (cells[5].inner_text() or "").strip() if len(cells) > 5 else ""
                    # Saltar fila de cabecera si se repite en tbody
                    if localidad and localidad.lower() in ("localidad", "direccion", "dirección"):
                        continue
                    name = empresa or direccion or localidad or "Gasolinera"
                    address = direccion or localidad or ""
                    prices = _parse_precios_cell(precios_text)
                    if name and (prices or address):
                        result.append({
                            "name": name,
                            "address": address,
                            "prices": prices,
                        })
            finally:
                browser.close()
    except Exception:
        result = []
    return result
