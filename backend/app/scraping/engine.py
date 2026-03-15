"""Motor de scraping: ejecuta búsqueda local y guarda precios (con mock de ejemplo)."""
from __future__ import annotations

import random
from typing import List

from sqlalchemy.orm import Session

from ..storage.models import LocalSearch
from ..storage.repository import add_price_record, get_or_create_product, get_or_create_source


def run_mock_scraping(db: Session, search: LocalSearch) -> int:
    """
    Simula scraping para la búsqueda local: genera precios de ejemplo por producto
    y los guarda. Devuelve el número de registros insertados.
    """
    product_names = [p.strip() for p in search.product_names.split(",") if p.strip()]
    if not product_names:
        return 0

    source = get_or_create_source(db, "Ejemplo local", base_url="https://ejemplo.local")
    count = 0

    for name in product_names:
        product = get_or_create_product(db, name)
        # 2–3 “fuentes” simuladas con precios distintos
        for label, delta in [("Tienda A", 0), ("Tienda B", random.uniform(-5, 15)), ("Tienda C", random.uniform(-10, 20))]:
            base = 20.0 + len(name) * 2 + random.uniform(0, 30)
            price = round(max(1.0, base + delta), 2)
            src = get_or_create_source(db, label, base_url="")
            add_price_record(
                db,
                local_search_id=search.id,
                source_id=src.id,
                product_id=product.id,
                price=price,
                currency="EUR",
                establishment_name=f"{label} - {search.location_query}",
            )
            count += 1

    return count
