"""
PDF Filler - Fills blank PDF templates with extracted data.
No white boxes - just adds text at specified coordinates.
"""

import io
import uuid
from datetime import datetime
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white


def generate_invoice_number() -> str:
    """Generate a unique invoice number."""
    timestamp = datetime.now().strftime("%y%m%d%H%M")
    unique_id = uuid.uuid4().hex[:3].upper()
    return f"INV-{timestamp}-{unique_id}"


def fill_invoice_template(
    payload: dict,
    template_path: str,
    output_path: str,
) -> str:
    """
    Fill a blank PDF template with invoice data.

    Args:
        payload: Extracted PO data
        template_path: Path to blank PDF template
        output_path: Path for output PDF

    Returns:
        Generated invoice number
    """
    # Generate new invoice number
    invoice_number = generate_invoice_number()

    # Get template page size
    reader = PdfReader(template_path)
    page = reader.pages[0]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    # Create overlay with data
    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

    # Extract data from payload
    header = payload.get("header", {})
    line_items = payload.get("line_items", [])
    totals = payload.get("totals", {})
    currency = header.get("currency", "AUD")

    # Page is 612 x ~792 points
    # Coordinates from pdfplumber analysis (converted from top-down to bottom-up)

    # === HEADER SECTION (white area, right side) ===
    # Values go BELOW their labels, right-aligned at same x position
    # Labels end at x~590, values right-aligned to 590
    # Values positioned ~18pt below each label for clear separation

    # PO # value (label at y=602, value well below)
    po_number = header.get("po_number", "")
    _draw_text(c, 590, 583, str(po_number), 8, align="right")

    # Invoice# value (label at y=579, value well below)
    _draw_text(c, 590, 560, invoice_number, 7, align="right")

    # DATE value (label at y=556, value well below)
    posting_date = _format_date(header.get("posting_date", ""))
    _draw_text(c, 590, 537, posting_date, 8, align="right")

    # Invoice Due Date value (label at y=526, value well below)
    due_date = _format_date(header.get("due_date", ""))
    _draw_text(c, 590, 507, due_date, 8, align="right")

    # === LINE ITEMS TABLE ===
    # Column header positions from template (x0-x1):
    #   "Line #": 20-43 (center=32)
    #   "ITEMS": 69-94 (left=70)
    #   "DESCRIPTION": 145-200 (left=145)
    #   "QUANTITY": 343-384 (center=363)
    #   "PRICE": 419-444 (left=420)
    #   "TAX Category": 482-535 (center=508)
    #   "Line Total": 558-596 (right=593)

    table_start_y = 448  # First data row below headers (with spacing from headers)
    row_height = 20  # Good spacing between rows

    for i, item in enumerate(line_items[:10]):
        y = table_start_y - (i * row_height)

        item_no = item.get("item_no", "")
        description = item.get("description", "")

        qty = item.get("quantity", 0)
        unit_price = _get_amount(item.get("unit_price"))
        tax_code = item.get("tax_code", "P1")
        line_total = _get_amount(item.get("line_total"))

        # Column positions aligned with template headers
        _draw_text(c, 32, y, str(i + 1), 8, align="center")       # Line # (centered)
        _draw_text(c, 70, y, item_no, 8)                          # ITEMS (left)
        _draw_text(c, 145, y, description[:22], 8)                # DESCRIPTION (left)
        _draw_text(c, 363, y, str(int(qty)), 8, align="center")   # QUANTITY (centered)
        _draw_text(c, 432, y, _format_money(unit_price, currency), 8, align="center")  # PRICE (centered)
        _draw_text(c, 508, y, tax_code, 8, align="center")        # TAX Category (centered)
        _draw_text(c, 593, y, _format_money(line_total, currency), 8, align="right")   # Line Total (right)

    # === TOTALS SECTION (bottom teal area) ===
    # White bold text, values positioned right after labels
    # Label x1 positions: TBD=468, Discount=422, Freight=391, Tax=373, TPD=453

    # Total Before Discount
    tbd = _get_amount(totals.get("total_before_discount"))
    _draw_text(c, 472, 197, _format_money(tbd, currency), 9, bold=True, color=white)

    # Discount
    discount = _get_amount(totals.get("discount"))
    if discount:
        _draw_text(c, 426, 175, _format_money(discount, currency), 9, bold=True, color=white)

    # Freight
    freight = _get_amount(totals.get("freight"))
    if freight:
        _draw_text(c, 395, 153, _format_money(freight, currency), 9, bold=True, color=white)

    # Tax
    tax = _get_amount(totals.get("tax"))
    _draw_text(c, 377, 131, _format_money(tax, currency), 9, bold=True, color=white)

    # Total Payment Due
    total_due = _get_amount(totals.get("total_payment_due"))
    _draw_text(c, 457, 109, _format_money(total_due, currency), 10, bold=True, color=white)

    c.save()

    # Merge overlay onto template
    overlay_buffer.seek(0)
    overlay_reader = PdfReader(overlay_buffer)
    writer = PdfWriter()

    base_page = reader.pages[0]
    overlay_page = overlay_reader.pages[0]
    base_page.merge_page(overlay_page)
    writer.add_page(base_page)

    with open(output_path, "wb") as f:
        writer.write(f)

    return invoice_number


def _draw_text(c: canvas.Canvas, x: float, y: float, text: str,
               size: int = 10, align: str = "left", bold: bool = False,
               color=None) -> None:
    """Draw text on canvas."""
    if text is None:
        text = ""
    if color is None:
        color = black
    c.setFillColor(color)
    font = "Helvetica-Bold" if bold else "Helvetica"
    c.setFont(font, size)
    if align == "right":
        c.drawRightString(x, y, str(text))
    elif align == "center":
        c.drawCentredString(x, y, str(text))
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
    return float(money_obj)


def _format_money(amount: Optional[float], currency: str = "") -> str:
    """Format amount as currency string."""
    if amount is None:
        return ""
    return f"{currency} {amount:,.2f}".strip()
