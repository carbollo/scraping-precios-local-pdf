"""Generación del PDF del informe comparativo con ReportLab."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generate_comparative_pdf(data: dict[str, Any]) -> BytesIO:
    """
    Genera un PDF con el informe comparativo.
    data: resultado de get_report_data (location, radius_km, sources, products, subtotal, iva_total, total, etc.)
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(
        "<b>Informe comparativo de precios (zona local)</b>",
        styles["Title"],
    )
    story.append(title)
    story.append(Spacer(1, 0.5 * cm))

    location = data.get("location", "")
    radius = data.get("radius_km", 50)
    created = data.get("created_at", "")[:10] if data.get("created_at") else ""

    info = Paragraph(
        f"Ubicación: {location} | Radio: {radius} km | Fecha: {created}",
        styles["Normal"],
    )
    story.append(info)
    story.append(Spacer(1, 1 * cm))

    sources = data.get("sources", [])
    products = data.get("products", [])
    currency = data.get("currency", "EUR")

    # Tabla: Producto | Fuente1 | Fuente2 | ... | Tienda (mín.) | IVA (%) | Total con IVA
    headers = ["Producto / Servicio"] + sources + ["Tienda (mín.)", "IVA (%)", f"Total ({currency})"]
    table_data = [headers]

    for row in products:
        pname = row.get("product_name", "")
        prices_by_source = row.get("prices_by_source", {})
        best_source = row.get("best_source_name") or "-"
        iva_pct = row.get("iva_pct", 21)
        total_con_iva = row.get("total_con_iva", 0)
        cells = [pname]
        for s in sources:
            cells.append(str(prices_by_source.get(s, "-")))
        cells.append(str(best_source))
        cells.append(str(iva_pct))
        cells.append(str(total_con_iva))
        table_data.append(cells)

    # Fila de totales (usar Paragraph para negrita)
    subtotal = data.get("subtotal", 0)
    iva_total = data.get("iva_total", 0)
    total = data.get("total", 0)
    total_row = [Paragraph("<b>SUBTOTAL</b>", styles["Normal"])] + [""] * len(sources) + [""] + [""] + [f"{subtotal:.2f}"]
    table_data.append(total_row)
    total_row2 = [Paragraph("<b>IVA</b>", styles["Normal"])] + [""] * len(sources) + [""] + [""] + [f"{iva_total:.2f}"]
    table_data.append(total_row2)
    total_row3 = [Paragraph("<b>TOTAL</b>", styles["Normal"])] + [""] * len(sources) + [""] + [""] + [f"{total:.2f}"]
    table_data.append(total_row3)

    t = Table(table_data, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer
