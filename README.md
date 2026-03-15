# Scraping de precios locales (50 km) y PDF contable

Aplicación web para buscar precios de productos/servicios en una zona (radio 50 km), ver un informe comparativo y descargar un PDF contable con IVA y totales.

## Cómo ejecutar en local

Desde la **raíz del proyecto**:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
playwright install chromium   # para extraer listado de gasolineras desde dieselogasolina.com
uvicorn backend.app.main:app --reload
```

Abre http://localhost:8000 . Introduce ubicación y productos (separados por coma), pulsa "Buscar precios en la zona" y luego "Ver informe comparativo y descargar PDF".

## Despliegue en Railway

1. Conectar el repositorio a Railway (nuevo proyecto desde GitHub).
2. Añadir el add-on **PostgreSQL**; Railway crea la variable `DATABASE_URL` automáticamente.
3. En Variables de entorno no hace falta añadir nada más si usas PostgreSQL (la app usa `DATABASE_URL`).
4. El **Procfile** arranca: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. Railway ejecuta desde la raíz del repo.
5. Deploy: cada push a la rama conectada despliega. La URL pública se ve en el panel.

**Nota:** En Railway el disco es efímero; sin PostgreSQL los datos se pierden al reiniciar. El `requirements.txt` debe estar guardado en **UTF-8**; si pip falla con "Invalid requirement" y caracteres raros, el archivo puede estar en UTF-16 (rescríbelo en UTF-8).

## Estructura

- `backend/app/main.py`: FastAPI, rutas, geocoding, rate limit, historial y fuentes.
- `backend/app/scraping/scraper.py`: Scraping real (tiendas en `selectors.py`).
- `backend/app/storage/`: Modelos y repositorio (búsquedas, fuentes, productos, precios).
- `backend/app/pdf/`: Informe comparativo y generación del PDF con ReportLab.
- `frontend/templates/`: Plantillas HTML (index, report, sources, history).
