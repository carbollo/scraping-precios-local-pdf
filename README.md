# Scraping de precios locales (50 km) y PDF contable

Aplicación web para buscar precios de productos/servicios en una zona (radio 50 km), ver un informe comparativo y descargar un PDF contable con IVA y totales.

## Cómo ejecutar en local

Desde la **raíz del proyecto**:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Abre http://localhost:8000 . Introduce ubicación y productos (separados por coma), pulsa "Buscar precios en la zona" y luego "Ver informe comparativo y descargar PDF".

## Despliegue en Railway

- Conectar el repositorio a Railway.
- Añadir PostgreSQL (add-on) y usar la variable `DATABASE_URL` que proporciona Railway.
- El `Procfile` arranca con: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`.

## Estructura

- `backend/app/main.py`: FastAPI, rutas y geocoding.
- `backend/app/scraping/engine.py`: Motor de scraping (mock con precios de ejemplo).
- `backend/app/storage/`: Modelos y repositorio (búsquedas, fuentes, productos, precios).
- `backend/app/pdf/`: Informe comparativo y generación del PDF con ReportLab.
- `frontend/templates/`: Plantillas HTML (index, report).
