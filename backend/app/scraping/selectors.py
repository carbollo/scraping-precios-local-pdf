"""Configuración de fuentes reales: nombre de la tienda, URL de búsqueda y selectores."""
from __future__ import annotations

# Cada fuente es una tienda real: nombre que se muestra en el informe y cómo extraer el precio.
# name: nombre real de la tienda (aparece en el PDF/informe).
# search_url: URL de búsqueda, use {query} donde va el texto (se reemplaza por el producto).
# price_selector: selector CSS para el elemento que contiene el precio (primer resultado).
# price_attr: atributo con el precio (ej. "data-price") o None para usar el texto del elemento.
REAL_SOURCES = [
    {
        "name": "Leroy Merlin",
        "base_url": "https://www.leroymerlin.es",
        "search_url": "https://www.leroymerlin.es/busqueda/?q={query}",
        "price_selector": "[data-product-price], .product-price .value, .price-value, [itemprop='price']",
        "price_attr": None,  # texto del nodo o content si itemprop=price
    },
    {
        "name": "Bricodepot",
        "base_url": "https://www.bricodepot.es",
        "search_url": "https://www.bricodepot.es/busqueda/?q={query}",
        "price_selector": ".product-price, [data-price], .price, [itemprop='price']",
        "price_attr": None,
    },
    {
        "name": "Bauhaus",
        "base_url": "https://www.bauhaus.info",
        "search_url": "https://www.bauhaus.info/es/search?text={query}",
        "price_selector": ".price, [data-price], [itemprop='price']",
        "price_attr": None,
    },
]
