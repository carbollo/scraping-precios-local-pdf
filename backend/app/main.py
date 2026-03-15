from __future__ import annotations

import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .geo.geocoding import geocode_with_nominatim
from .geo.distance import is_within_radius_km
from .scraping.engine import run_mock_scraping
from .storage.models import (
    Base,
    LocalSearch,
    PriceRecord,
    Product,
    Source,
    init_db,
)
from .storage.repository import get_report_data
from .pdf.comparative_report import build_report_data
from .pdf.generator import generate_comparative_pdf


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

    # Ejecutar scraping (mock que genera precios de ejemplo por producto/fuente)
    run_mock_scraping(db, search)

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


@app.get("/report/{search_id}", response_class=HTMLResponse)
def report_page(request: Request, search_id: int, db: Session = Depends(get_db)):
    """Vista del informe comparativo con tabla y enlace para descargar PDF."""
    data = get_report_data(db, search_id)
    if not data:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    return templates.TemplateResponse(
        "report.html",
        {"request": request, "search_id": search_id, "report": data},
    )


@app.get("/api/reports/{search_id}/pdf")
def download_comparative_pdf(search_id: int, db: Session = Depends(get_db)):
    """Genera y devuelve el PDF del informe comparativo."""
    data = build_report_data(db, search_id)
    if not data:
        raise HTTPException(status_code=404, detail="Búsqueda no encontrada")
    buffer = generate_comparative_pdf(data)
    filename = f"informe-precios-{search_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
def health():
    return {"status": "ok"}

