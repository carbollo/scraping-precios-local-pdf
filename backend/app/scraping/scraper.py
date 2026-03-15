"""Scraping real: obtiene precio desde la URL de cada tienda usando selectores."""
from __future__ import annotations

import re
import time
import unicodedata
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from .selectors import DIESELOGASOLINA_URL, FUEL_PRODUCT_ALIASES, REAL_SOURCES
from . import minetur_api


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


def _normalize_fuel_product_name(user_input: str) -> str | None:
    """Devuelve el nombre canónico del combustible si matchea (ej. 'gasolina 95' -> 'Sin Plomo 95')."""
    key = user_input.strip().lower()
    if not key:
        return None
    if key in FUEL_PRODUCT_ALIASES:
        return FUEL_PRODUCT_ALIASES[key]
    for alias, canonical in FUEL_PRODUCT_ALIASES.items():
        if alias in key or key in alias:
            return canonical
    return None


# Mapeo comunidad/región -> nombre de provincia como en dieselogasolina.com
_PROVINCE_ALIAS = {
    "community of madrid": "Madrid",
    "comunidad de madrid": "Madrid",
    "andalusia": "Málaga",
    "andalucía": "Málaga",
    "comunitat valenciana": "Valencia",
    "comunidad valenciana": "Valencia",
    "catalonia": "Barcelona",
    "cataluña": "Barcelona",
    "euskadi": "Bizkaia",
    "país vasco": "Bizkaia",
    "galicia": "A Coruña",
    "aragón": "Zaragoza",
    "aragon": "Zaragoza",
}


def _slug_province(province: str) -> str:
    """Normaliza nombre de provincia para comparar con cabeceras (sin acentos, minúsculas)."""
    if not province:
        return ""
    s = province.strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.replace(" ", "").replace("-", "")


def _resolve_province_for_fuel(province: str | None, location_query: str | None) -> str | None:
    """Devuelve el nombre de provincia a usar para dieselogasolina (Madrid, Málaga, etc.)."""
    if not province and not location_query:
        return None
    raw = (province or location_query or "").strip()
    if not raw:
        return None
    key = raw.lower()
    if key in _PROVINCE_ALIAS:
        return _PROVINCE_ALIAS[key]
    for alias, name in _PROVINCE_ALIAS.items():
        if alias in key or key in alias:
            return name
    return raw


def _slug_for_url(text: str) -> str:
    """Normaliza texto para URL: minúsculas, sin acentos, espacios a guiones."""
    if not text:
        return ""
    s = unicodedata.normalize("NFD", text.strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace(" ", "-").replace("_", "-")


def build_dieselogasolina_search_url(
    province_region: str | None, location_query: str | None
) -> str | None:
    """
    Genera la URL de búsqueda de gasolineras en dieselogasolina.com para esa zona
    (ej. gasolineras-en-malaga-localidad-alhaurin-de-la-torre.html).
    Así el usuario puede abrirla en el navegador y ver el mapa/listado como en la web.
    """
    province = _resolve_province_for_fuel(province_region, location_query)
    if not province:
        return None
    base = DIESELOGASOLINA_URL.rstrip("/")
    prov_slug = _slug_for_url(province)
    if not prov_slug:
        return None
    # Si la búsqueda es una localidad concreta (no solo provincia), añadir localidad
    loc = (location_query or "").strip()
    if loc and loc.lower() != province.lower() and _slug_for_url(loc) != prov_slug:
        loc_slug = _slug_for_url(loc)
        if loc_slug:
            return f"{base}/gasolineras-en-{prov_slug}-localidad-{loc_slug}.html"
    return f"{base}/gasolineras-en-{prov_slug}.html"


def fetch_dieselogasolina_prices(province: str | None = None) -> dict[str, dict[str, float]]:
    """
    Obtiene precios desde dieselogasolina.com.
    - Si province está indicada (ej. "Madrid", "Málaga"): usa la tabla "Un vistazo rápido"
      por provincias y devuelve solo precios de esa zona.
    - Si no: devuelve tabla por marcas (REPSOL, CEPSA, ...) o precio medio España.
    """
    result: dict[str, dict[str, float]] = {}
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(DIESELOGASOLINA_URL)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return result

    province_slug = _slug_province(province) if province else ""

    # Tabla por provincias (Un vistazo rápido): filas = combustibles, columnas = provincias
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        provinces_in_table: list[str] = []
        for cell in header_cells[1:]:
            text = cell.get_text(strip=True)
            if not text or len(text) > 30:
                continue
            link = cell.find("a")
            if link and link.get("href") and "gasolineras-en-" in link.get("href", ""):
                provinces_in_table.append(text)
            elif text.upper() in ("MADRID", "BARCELONA", "VALENCIA", "SEVILLA", "ZARAGOZA", "TOLEDO", "MURCIA", "BIZKAIA", "GUADALAJARA", "A CORUÑA", "MÁLAGA", "MALAGA"):
                provinces_in_table.append(text)
            else:
                provinces_in_table.append(text)
        if not provinces_in_table:
            continue
        # Si pedimos una provincia, comprobar si está en esta tabla
        col_index = -1
        if province_slug:
            for i, p in enumerate(provinces_in_table):
                if _slug_province(p) == province_slug or province_slug in _slug_province(p) or _slug_province(p) in province_slug:
                    col_index = i
                    break
            if col_index < 0:
                continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            product_name = cells[0].get_text(strip=True)
            if not product_name or len(product_name) > 50:
                continue
            prices_by_source: dict[str, float] = {}
            for i, cell in enumerate(cells[1:], start=0):
                if province_slug and i != col_index:
                    continue
                price = _normalize_price(cell.get_text(strip=True))
                if price is None or not (0.3 < price < 10.0):
                    continue
                name = provinces_in_table[i] if i < len(provinces_in_table) else (province or "Zona")
                prices_by_source[name] = price
            if prices_by_source and product_name:
                result[product_name] = prices_by_source
        if result:
            return result

    # Tabla por marcas (REPSOL, CEPSA, ...) - solo si no pedíamos provincia
    if not province_slug:
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_cells = rows[0].find_all(["th", "td"])
            brands: list[str] = []
            for cell in header_cells[1:]:
                text = cell.get_text(strip=True).upper()
                if text and text not in ("CONVENCIONALES", "LOWCOST", "HOY", "AYER", "MAX.HISTÓRICO", "") and len(text) < 25:
                    brands.append(text)
                img = cell.find("img")
                if img and img.get("alt"):
                    alt = img.get("alt", "").strip().upper()
                    if alt and alt not in brands:
                        brands.append(alt)
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                product_name = cells[0].get_text(strip=True)
                if not product_name or len(product_name) > 50:
                    continue
                prices_by_brand: dict[str, float] = {}
                for i, cell in enumerate(cells[1:], start=0):
                    price = _normalize_price(cell.get_text(strip=True))
                    if price is None or not (0.3 < price < 10.0):
                        continue
                    if i < len(brands):
                        prices_by_brand[brands[i]] = price
                    else:
                        prices_by_brand[f"Col{i}"] = price
                if prices_by_brand and product_name:
                    result[product_name] = prices_by_brand
            if len(result) >= 2 and any(len(v) > 1 for v in result.values()):
                break
    # Fallback: tabla Hoy (precio medio España)
    if not result:
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    product_name = cells[0].get_text(strip=True)
                    price = _normalize_price(cells[1].get_text(strip=True))
                    if product_name and price and 0.3 < price < 10.0 and len(product_name) < 50:
                        result[product_name] = {"DieseloGasolina.com": price}
            if result:
                break
    return result


def run_real_scraping(db, search) -> int:
    """
    Ejecuta scraping real: por cada producto y cada fuente configurada obtiene
    el precio desde la web de la tienda y guarda con el nombre real de la tienda.
    Para combustibles: usa API Minetur (gasolineras con precios por ubicación en 50 km)
    o, si falla, dieselogasolina.com por provincia/marcas.
    """
    from ..storage.repository import add_price_record, get_or_create_product, get_or_create_source

    product_names = [p.strip() for p in search.product_names.split(",") if p.strip()]
    if not product_names:
        return 0

    count = 0
    center_lat = getattr(search, "center_lat", None)
    center_lng = getattr(search, "center_lng", None)
    radius_km = getattr(search, "radius_km", 50.0) or 50.0

    # Productos que son combustibles (para API Minetur)
    fuel_canonicals = []
    for p in product_names:
        c = _normalize_fuel_product_name(p)
        if c and c not in fuel_canonicals:
            fuel_canonicals.append(c)

    # 1) Combustibles: intentar API Minetur (gasolineras con precios por estación en el radio)
    if fuel_canonicals and center_lat is not None and center_lng is not None:
        time.sleep(REQUEST_DELAY_SEC)
        stations = minetur_api.get_gas_stations_near(
            center_lat, center_lng, radius_km, canonical_products=fuel_canonicals
        )
        if stations:
            for st in stations:
                st_name = st.get("name") or "Gasolinera"
                source = get_or_create_source(db, st_name, base_url=DIESELOGASOLINA_URL)
                for product_canonical, price in st.get("prices", {}).items():
                    # Encontrar el product_name original que corresponde a este canónico
                    product_name = product_canonical
                    for p in product_names:
                        if _normalize_fuel_product_name(p) == product_canonical:
                            product_name = p
                            break
                    product = get_or_create_product(db, product_name)
                    add_price_record(
                        db,
                        local_search_id=search.id,
                        source_id=source.id,
                        product_id=product.id,
                        price=round(price, 2),
                        currency="EUR",
                        establishment_name=st_name,
                        establishment_lat=st.get("lat"),
                        establishment_lng=st.get("lng"),
                    )
                    count += 1
        # Si Minetur no devolvió estaciones, usar dieselogasolina por provincia
        if count == 0:
            province = _resolve_province_for_fuel(
                getattr(search, "province_region", None),
                getattr(search, "location_query", None),
            )
            fuel_prices = fetch_dieselogasolina_prices(province=province)
            if fuel_prices:
                for product_name in product_names:
                    canonical = _normalize_fuel_product_name(product_name)
                    if not canonical:
                        continue
                    row = fuel_prices.get(canonical)
                    if not row:
                        for key in fuel_prices:
                            if canonical.lower() in key.lower() or key.lower() in product_name.lower():
                                row = fuel_prices[key]
                                break
                    if not row:
                        continue
                    product = get_or_create_product(db, product_name)
                    for brand_name, price in row.items():
                        source = get_or_create_source(db, brand_name, base_url=DIESELOGASOLINA_URL)
                        add_price_record(
                            db,
                            local_search_id=search.id,
                            source_id=source.id,
                            product_id=product.id,
                            price=round(price, 2),
                            currency="EUR",
                            establishment_name=brand_name,
                        )
                        count += 1
    elif fuel_canonicals:
        # Sin coordenadas: solo dieselogasolina por provincia
        time.sleep(REQUEST_DELAY_SEC)
        province = _resolve_province_for_fuel(
            getattr(search, "province_region", None),
            getattr(search, "location_query", None),
        )
        fuel_prices = fetch_dieselogasolina_prices(province=province)
        if fuel_prices:
            for product_name in product_names:
                canonical = _normalize_fuel_product_name(product_name)
                if not canonical:
                    continue
                row = fuel_prices.get(canonical)
                if not row:
                    for key in fuel_prices:
                        if canonical.lower() in key.lower() or key.lower() in product_name.lower():
                            row = fuel_prices[key]
                            break
                if not row:
                    continue
                product = get_or_create_product(db, product_name)
                for brand_name, price in row.items():
                    source = get_or_create_source(db, brand_name, base_url=DIESELOGASOLINA_URL)
                    add_price_record(
                        db,
                        local_search_id=search.id,
                        source_id=source.id,
                        product_id=product.id,
                        price=round(price, 2),
                        currency="EUR",
                        establishment_name=brand_name,
                    )
                    count += 1

    # 2) Resto de fuentes (Leroy Merlin, Bricodepot, etc.): solo para productos que NO son combustibles
    # (evitar buscar "Sin plomo 95" en tiendas de bricolaje y que devuelvan aceites u otros productos)
    if REAL_SOURCES:
        for product_name in product_names:
            if _normalize_fuel_product_name(product_name) is not None:
                continue  # combustibles solo vienen de Minetur/dieselogasolina
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
