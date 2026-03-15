"""Scraping real: obtiene precio desde la URL de cada tienda usando selectores."""
from __future__ import annotations

import re
import time
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .selectors import REAL_SOURCES


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY_SEC = 1.5  # respetar al servidor


def _normalize_price(text: str) -> float | None:
    """Extrae número de precio desde texto (ej. '12,34 €' o '12.34 EUR')."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\s]", "", text.strip())
    cleaned = cleaned.replace(",", ".")
    parts = re.findall(r"\d+\.?\d*", cleaned)
    if not parts:
        return None
    try:
        return float(parts[-1])
    except ValueError:
        return None


def _extract_price(soup: BeautifulSoup, source: dict) -> float | None:
    """Busca el primer elemento que coincida con los selectores y extrae el precio."""
    selectors = source.get("price_selector") or ""
    price_attr = source.get("price_attr")

    for sel in selectors.split(","):
        sel = sel.strip()
        if not sel:
            continue
        try:
            el = soup.select_one(sel)
            if el is None:
                continue
            if price_attr and el.get(price_attr) is not None:
                raw = el.get(price_attr)
            else:
                raw = el.get("content") or el.get_text(strip=True)
            price = _normalize_price(str(raw))
            if price is not None and price > 0:
                return price
        except Exception:
            continue

    # Fallback: buscar en toda la página un número que parezca precio (ej. 12,34 o 19.99)
    for node in soup.find_all(string=re.compile(r"\d+[,.]\d{2}")):
        text = str(node).strip() if node else ""
        price = _normalize_price(text)
        if price is not None and 0.01 < price < 100_000:
            return price
    return None


def fetch_price_from_source(product_query: str, source: dict) -> tuple[float | None, str]:
    """
    Obtiene el precio para un producto desde una fuente (tienda real).
    Devuelve (precio, nombre_tienda). Si no hay precio, (None, nombre_tienda).
    """
    name = source.get("name") or "Desconocida"
    url_template = source.get("search_url") or ""
    if not url_template or "{query}" not in url_template:
        return None, name

    url = url_template.replace("{query}", quote_plus(product_query, safe=""))

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price = _extract_price(soup, source)
        return price, name
    except Exception:
        return None, name


def run_real_scraping(db, search) -> int:
    """
    Ejecuta scraping real: por cada producto y cada fuente configurada obtiene
    el precio desde la web de la tienda y guarda con el nombre real de la tienda.
    """
    from ..storage.repository import add_price_record, get_or_create_product, get_or_create_source

    product_names = [p.strip() for p in search.product_names.split(",") if p.strip()]
    if not product_names or not REAL_SOURCES:
        return 0

    count = 0
    for product_name in product_names:
        product = get_or_create_product(db, product_name)
        for source_config in REAL_SOURCES:
            time.sleep(REQUEST_DELAY_SEC)
            price, store_name = fetch_price_from_source(product_name, source_config)
            if price is None:
                continue
            source = get_or_create_source(db, store_name, base_url=source_config.get("base_url") or "")
            add_price_record(
                db,
                local_search_id=search.id,
                source_id=source.id,
                product_id=product.id,
                price=round(price, 2),
                currency="EUR",
                establishment_name=store_name,
            )
            count += 1
    return count
