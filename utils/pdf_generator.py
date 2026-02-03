"""
PDF Invoice Generator - Creates invoices from scratch using reportlab.
No template overlay needed - generates clean PDFs matching vendor layouts.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from typing import Optional


# Colors matching the template
DARK_BLUE = HexColor("#1a365d")
LIGHT_GRAY = HexColor("#f7fafc")
BORDER_GRAY = HexColor("#e2e8f0")


def generate_invoice_pdf(payload: dict, output_path: str, vendor_config: dict = None) -> None:
    """
    Generate a clean invoice PDF from extracted PO data.

    Args:
        payload: Extracted PO data with header, line_items, totals
        output_path: Path to save the generated PDF
        vendor_config: Optional vendor-specific configuration
    """
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # Extract data
    header = payload.get("header", {})
    line_items = payload.get("line_items", [])
    totals = payload.get("totals", {})

    vendor_name = header.get("vendor_name", "")
    po_number = header.get("po_number", "")
    posting_date = header.get("posting_date", "")
    due_date = header.get("due_date", "")
    currency = header.get("currency", "AUD")

    # Format dates for display
    posting_date_fmt = _format_date(posting_date)
    due_date_fmt = _format_date(due_date)

    # === HEADER SECTION ===
    # Title
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(DARK_BLUE)
    c.drawString(50, height - 60, "Invoice")

    # Vendor info box (left side)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(black)
    c.drawString(50, height - 100, "SHIP TO:")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 118, vendor_name or "Vendor Name")

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#4a5568"))
    # Use vendor address from config if available
    address_lines = [
        "Address 600 EASTERN WAY",
        "BRISBANE QLD 4003",
        "AUSTRALIA"
    ]
    y = height - 135
    for line in address_lines:
        c.drawString(50, y, line)
        y -= 14

    # Invoice info box (right side)
    info_box_x = 400
    info_box_y = height - 60

    c.setFillColor(LIGHT_GRAY)
    c.rect(info_box_x - 10, info_box_y - 120, 180, 130, fill=1, stroke=0)

    c.setFillColor(black)
    c.setFont("Helvetica", 9)

    info_items = [
        ("DATE", posting_date_fmt),
        ("INVOICE DUE DATE", due_date_fmt),
        ("Invoice #", f"INV-{po_number}" if po_number else ""),
        ("PO #", po_number),
        ("Receipt #", ""),
    ]

    y = info_box_y - 20
    for label, value in info_items:
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#718096"))
        c.drawString(info_box_x, y, label)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(black)
        c.drawString(info_box_x, y - 12, str(value) if value else "")
        y -= 28

    # === LINE ITEMS TABLE ===
    table_top = height - 220

    # Table header
    c.setFillColor(DARK_BLUE)
    c.rect(50, table_top - 5, width - 100, 20, fill=1, stroke=0)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)

    col_positions = {
        "description": 55,
        "quantity": 300,
        "price": 370,
        "tax": 440,
        "line_total": 510
    }

    c.drawString(col_positions["description"], table_top, "DESCRIPTION")
    c.drawString(col_positions["quantity"], table_top, "QTY")
    c.drawString(col_positions["price"], table_top, "PRICE")
    c.drawString(col_positions["tax"], table_top, "TAX")
    c.drawString(col_positions["line_total"], table_top, "LINE TOTAL")

    # Table rows
    c.setFillColor(black)
    row_height = 25
    y = table_top - 30

    for i, item in enumerate(line_items[:15]):  # Max 15 items
        # Alternating row background
        if i % 2 == 0:
            c.setFillColor(LIGHT_GRAY)
            c.rect(50, y - 5, width - 100, row_height, fill=1, stroke=0)

        c.setFillColor(black)
        c.setFont("Helvetica", 9)

        item_no = item.get("item_no", "")
        description = item.get("description", "")
        full_desc = f"{item_no} {description}" if item_no else description

        # Truncate long descriptions
        if len(full_desc) > 40:
            full_desc = full_desc[:37] + "..."

        quantity = item.get("quantity", 0)
        unit_price = _get_amount(item.get("unit_price"))
        line_total = _get_amount(item.get("line_total"))

        c.drawString(col_positions["description"], y + 5, full_desc)
        c.drawString(col_positions["quantity"], y + 5, str(int(quantity) if quantity == int(quantity) else quantity))
        c.drawString(col_positions["price"], y + 5, _format_money(unit_price, currency))
        c.drawString(col_positions["tax"], y + 5, "P1")  # Tax category placeholder
        c.drawString(col_positions["line_total"], y + 5, _format_money(line_total, currency))

        y -= row_height

    # === TOTALS SECTION ===
    totals_x = 400
    totals_y = 180

    c.setFillColor(LIGHT_GRAY)
    c.rect(totals_x - 10, totals_y - 80, 180, 120, fill=1, stroke=0)

    c.setFillColor(black)

    total_items = [
        ("Total Before Discount:", _get_amount(totals.get("total_before_discount"))),
        ("Discount:", _get_amount(totals.get("discount"))),
        ("Freight:", _get_amount(totals.get("freight"))),
        ("Tax:", _get_amount(totals.get("tax"))),
    ]

    y = totals_y + 20
    for label, amount in total_items:
        c.setFont("Helvetica", 9)
        c.drawString(totals_x, y, label)
        c.setFont("Helvetica", 10)
        if amount is not None:
            c.drawRightString(totals_x + 155, y, _format_money(amount, currency))
        y -= 18

    # Total Payment Due (highlighted)
    c.setFillColor(DARK_BLUE)
    c.rect(totals_x - 10, totals_y - 75, 180, 25, fill=1, stroke=0)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(totals_x, totals_y - 60, "Total Payment Due:")

    total_due = _get_amount(totals.get("total_payment_due"))
    if total_due is not None:
        c.drawRightString(totals_x + 155, totals_y - 60, _format_money(total_due, currency))

    # === FOOTER ===
    c.setFillColor(HexColor("#a0aec0"))
    c.setFont("Helvetica", 8)
    c.drawString(50, 40, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    c.save()


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
    """Extract amount from money object or return None."""
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
