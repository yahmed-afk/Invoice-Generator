"""
PDF Overlay Generator - Creates clean overlays for existing templates.
Uses background-matched colors instead of white rectangles.
"""

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.pagesizes import letter
from datetime import datetime
from pathlib import Path
from typing import Optional
import io


# Background colors from typical invoice templates
TEMPLATE_BG = HexColor("#FFFFFF")  # White for main areas
TOTALS_BG = HexColor("#FDF6E3")    # Cream/beige for totals area (if needed)


def generate_invoice_from_template(
    payload: dict,
    template_path: str,
    output_path: str,
    layout: dict
) -> None:
    """
    Generate invoice by overlaying data on existing template.

    Args:
        payload: Extracted PO data
        template_path: Path to PDF template
        output_path: Path for output PDF
        layout: Coordinate layout for this template
    """
    # Create overlay
    overlay_buffer = io.BytesIO()
    _build_overlay(payload, template_path, overlay_buffer, layout)
    overlay_buffer.seek(0)

    # Merge overlay onto template
    template_reader = PdfReader(template_path)
    overlay_reader = PdfReader(overlay_buffer)
    writer = PdfWriter()

    base_page = template_reader.pages[0]
    overlay_page = overlay_reader.pages[0]
    base_page.merge_page(overlay_page)
    writer.add_page(base_page)

    with open(output_path, "wb") as f:
        writer.write(f)


def _build_overlay(payload: dict, template_path: str, output_buffer, layout: dict) -> None:
    """Build the overlay PDF with extracted data."""
    # Get template page size
    reader = PdfReader(template_path)
    first_page = reader.pages[0]
    page_width = float(first_page.mediabox.width)
    page_height = float(first_page.mediabox.height)

    c = canvas.Canvas(output_buffer, pagesize=(page_width, page_height))

    header = payload.get("header", {})
    line_items = payload.get("line_items", [])
    totals = payload.get("totals", {})
    currency = header.get("currency", "AUD")

    # Apply masks (use white to cover existing template text)
    masks = layout.get("masks", {})
    for mask_name, mask in masks.items():
        _mask_area(c, mask["x"], mask["y"], mask["w"], mask["h"])

    # Draw header fields
    if "po_number" in layout:
        pos = layout["po_number"]
        _draw_text(c, pos["x"], pos["y"], header.get("po_number", ""), pos.get("size", 10))

    if "date" in layout:
        pos = layout["date"]
        date_str = _format_date(header.get("posting_date", ""))
        _draw_text(c, pos["x"], pos["y"], date_str, pos.get("size", 10))

    if "due_date" in layout:
        pos = layout["due_date"]
        date_str = _format_date(header.get("due_date", ""))
        _draw_text(c, pos["x"], pos["y"], date_str, pos.get("size", 10))

    # Draw line items
    table = layout.get("table", {})
    max_rows = table.get("max_rows", 10)
    row_h = table.get("row_h", 18)
    start_y = table.get("start_y", 500)
    cols = table.get("cols", {})

    for i, item in enumerate(line_items[:max_rows]):
        y = start_y - i * row_h

        # Mask the row area
        _mask_area(c, 50, y - 3, 520, row_h - 2)

        # Draw item data
        desc = item.get("description", "")
        item_no = item.get("item_no", "")
        full_desc = f"{item_no} {desc}".strip()

        qty = item.get("quantity", 0)
        unit_price = _get_amount(item.get("unit_price"))
        line_total = _get_amount(item.get("line_total"))

        if "description" in cols:
            _draw_text(c, cols["description"]["x"], y, full_desc, cols["description"].get("size", 10))
        if "quantity" in cols:
            _draw_text(c, cols["quantity"]["x"], y, str(int(qty)), cols["quantity"].get("size", 10))
        if "price" in cols:
            _draw_text(c, cols["price"]["x"], y, _format_money(unit_price, currency), cols["price"].get("size", 10))
        if "line_total" in cols:
            _draw_text(c, cols["line_total"]["x"], y, _format_money(line_total, currency), cols["line_total"].get("size", 10))

    # Draw totals
    totals_fields = [
        ("total_before_discount", totals.get("total_before_discount")),
        ("discount", totals.get("discount")),
        ("freight", totals.get("freight")),
        ("tax", totals.get("tax")),
        ("total_payment_due", totals.get("total_payment_due")),
    ]

    for field_name, value in totals_fields:
        if field_name in layout and value is not None:
            pos = layout[field_name]
            amount = _get_amount(value)
            align = pos.get("align", "left")
            _draw_text(c, pos["x"], pos["y"], _format_money(amount, currency), pos.get("size", 10), align)

    c.save()


def _mask_area(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    """Mask an area with white background."""
    c.saveState()
    c.setFillColor(white)
    c.setStrokeColor(white)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.restoreState()


def _draw_text(c: canvas.Canvas, x: float, y: float, text: str, size: int = 10, align: str = "left") -> None:
    """Draw text on canvas."""
    if text is None:
        text = ""
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica", size)
    if align == "right":
        c.drawRightString(x, y, str(text))
    else:
        c.drawString(x, y, str(text))


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MM/DD/YY format."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d/%y")
    except:
        return date_str


def _get_amount(money_obj) -> Optional[float]:
    """Extract amount from money object."""
    if money_obj is None:
        return None
    if isinstance(money_obj, dict):
        return money_obj.get("amount")
    return money_obj


def _format_money(amount: Optional[float], currency: str = "") -> str:
    """Format amount as currency string."""
    if amount is None:
        return ""
    return f"{currency} {amount:,.2f}".strip()
