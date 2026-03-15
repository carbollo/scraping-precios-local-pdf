"""Acceso a búsquedas locales, fuentes, productos y precios."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from .models import LocalSearch, PriceRecord, Product, Source


def get_or_create_source(db: Session, name: str, base_url: Optional[str] = None) -> Source:
    """Obtiene una fuente por nombre o la crea si no existe."""
    source = db.query(Source).filter(Source.name == name).first()
    if source is None:
        source = Source(name=name, base_url=base_url or "")
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def get_or_create_product(db: Session, name: str, category: Optional[str] = None) -> Product:
    """Obtiene un producto por nombre o lo crea si no existe."""
    product = db.query(Product).filter(Product.name == name).first()
    if product is None:
        product = Product(name=name, category=category)
        db.add(product)
        db.commit()
        db.refresh(product)
    return product


def add_price_record(
    db: Session,
    local_search_id: int,
    source_id: int,
    product_id: int,
    price: float,
    currency: str = "EUR",
    establishment_name: Optional[str] = None,
    establishment_lat: Optional[float] = None,
    establishment_lng: Optional[float] = None,
) -> PriceRecord:
    """Añade un registro de precio."""
    record = PriceRecord(
        local_search_id=local_search_id,
        source_id=source_id,
        product_id=product_id,
        price=price,
        currency=currency,
        establishment_name=establishment_name,
        establishment_lat=establishment_lat,
        establishment_lng=establishment_lng,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_local_search(db: Session, search_id: int) -> Optional[LocalSearch]:
    """Obtiene una búsqueda local por id."""
    return db.get(LocalSearch, search_id)


def get_report_data(db: Session, search_id: int) -> dict:
    """
    Agrupa los precios de una búsqueda para el informe:
    - products: lista de { name, prices_by_source: { source_name: price }, min_price, iva_pct, total_con_iva }
    - sources: lista de nombres de fuentes
    - location, radius_km, created_at
    - subtotal, iva_total, total (sumando por producto el mínimo o el primero)
    """
    search = db.get(LocalSearch, search_id)
    if not search:
        return {}

    records = (
        db.query(PriceRecord)
        .filter(PriceRecord.local_search_id == search_id)
        .all()
    )

    # Agrupar por producto: { product_name: { source_name: price } }
    by_product: dict[str, dict[str, float]] = {}
    sources_set: set[str] = set()

    for r in records:
        if not r.product or not r.source:
            continue
        pname = r.product.name
        sname = r.source.name
        sources_set.add(sname)
        if pname not in by_product:
            by_product[pname] = {}
        by_product[pname][sname] = r.price

    sources_list = sorted(sources_set)
    # Precios con IVA ya incluido: no añadir 21% adicional
    rows: list[dict[str, object]] = []
    subtotal = 0.0
    for product_name, prices_by_source in sorted(by_product.items()):
        min_price = 0.0
        min_source_name: Optional[str] = None
        for sname, price in prices_by_source.items():
            if min_source_name is None or price < min_price:
                min_price = price
                min_source_name = sname

        subtotal += min_price
        row = {
            "product_name": product_name,
            "prices_by_source": prices_by_source,
            "best_source_name": min_source_name,
            "min_price": min_price,
            "iva_incl": True,
            "total_con_iva": round(min_price, 2),
        }
        rows.append(row)

    return {
        "search_id": search_id,
        "location": search.location_query,
        "radius_km": search.radius_km,
        "center_lat": search.center_lat,
        "center_lng": search.center_lng,
        "created_at": search.created_at.isoformat() if search.created_at else None,
        "sources": sources_list,
        "products": rows,
        "subtotal": round(subtotal, 2),
        "iva_incl": True,
        "iva_total": 0,
        "total": round(subtotal, 2),
        "currency": "EUR",
    }
