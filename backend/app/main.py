from __future__ import annotations

import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .geo.geocoding import geocode_with_nominatim
from .geo.distance import is_within_radius_km
from .storage.models import (
    Base,
    LocalSearch,
    PriceRecord,
    Product,
    Source,
    init_db,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

init_db(engine)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend", "templates")
templates = Jinja2Templates(directory=templates_dir)


app = FastAPI(title="Scraping local de precios (50 km)")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class LocalSearchRequest(BaseModel):
    location: str
    products: List[str]
    radius_km: float = 50.0


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )


@app.post("/api/local-search")
async def create_local_search(
    payload: LocalSearchRequest, db: Session = Depends(get_db)
):
    # Geocoding de la ubicación
    coords = await geocode_with_nominatim(payload.location)
    if not coords:
        raise HTTPException(status_code=400, detail="No se pudo geocodificar la ubicación")

    center_lat, center_lng = coords

    # Crear registro de búsqueda local
    search = LocalSearch(
        location_query=payload.location,
        center_lat=center_lat,
        center_lng=center_lng,
        radius_km=payload.radius_km,
        product_names=",".join(payload.products),
    )
    db.add(search)
    db.commit()
    db.refresh(search)

    # De momento no implementamos scraping real; dejamos hook para futuro.
    # Aquí se llamaría a un motor que consulta APIs/directorios y guarda PriceRecord.

    return {"search_id": search.id, "center_lat": center_lat, "center_lng": center_lng}


@app.get("/api/local-search/{search_id}/prices")
def list_prices_for_search(
    search_id: int,
    db: Session = Depends(get_db),
):
    search = db.get(LocalSearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")

    # Obtener registros ya guardados para esta búsqueda (cuando exista scraping)
    records = (
        db.query(PriceRecord)
        .filter(PriceRecord.local_search_id == search_id)
        .all()
    )

    def to_dict(r: PriceRecord):
        return {
            "id": r.id,
            "product": r.product.name if r.product else None,
            "source": r.source.name if r.source else None,
            "price": r.price,
            "currency": r.currency,
            "establishment_name": r.establishment_name,
            "scraped_at": r.scraped_at.isoformat(),
        }

    return {
        "search_id": search_id,
        "location": search.location_query,
        "radius_km": search.radius_km,
        "center_lat": search.center_lat,
        "center_lng": search.center_lng,
        "items": [to_dict(r) for r in records],
    }


@app.get("/health")
def health():
    return {"status": "ok"}

