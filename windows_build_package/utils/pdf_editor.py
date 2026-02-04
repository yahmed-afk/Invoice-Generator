"""
PDF Editor - Directly edits PDF content to replace text values.
Uses pikepdf for content stream manipulation.
"""

import pikepdf
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import zlib


def generate_invoice_number() -> str:
    """Generate a unique invoice number."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"INV-{timestamp}-{unique_id}"


def edit_invoice_pdf(
    payload: dict,
    template_path: str,
    output_path: str,
) -> str:
    """
    Edit PDF template by replacing text values directly in content stream.

    Args:
        payload: Extracted PO data
        template_path: Path to PDF template
        output_path: Path for output PDF

    Returns:
        Generated invoice number
    """
    # Generate new invoice number
    invoice_number = generate_invoice_number()

    # Extract values from payload
    header = payload.get("header", {})
    line_items = payload.get("line_items", [])
    totals = payload.get("totals", {})

    po_number = header.get("po_number", "")
    posting_date = _format_date(header.get("posting_date", ""))
    due_date = _format_date(header.get("due_date", ""))
    currency = header.get("currency", "AUD")

    # Build replacement map for template values
    replacements = {
        # Header replacements (template value -> new value)
        "01/28/26": posting_date if posting_date else "01/28/26",
        "COL237561876": invoice_number,
        "794": str(po_number) if po_number else "794",
        "9076": "",  # Receipt number - clear it

        # Line item replacements
        "A00001 J.B. Officeprint 1420 4 AUD 500.00 P1 AUD 2000.000": _format_line_item(line_items[0] if line_items else {}, currency),

        # Totals replacements
        "AUD 2000.00": _format_money(_get_amount(totals.get("total_before_discount")), currency),
        "AUD 200.00": _format_money(_get_amount(totals.get("tax")), currency),
        "AUD 2200.00": _format_money(_get_amount(totals.get("total_payment_due")), currency),
    }

    # Open and edit PDF
    with pikepdf.open(template_path, allow_overwriting_input=True) as pdf:
        page = pdf.pages[0]

        # Get the content stream
        if "/Contents" in page:
            contents = page["/Contents"]

            # Handle single or multiple content streams
            if isinstance(contents, pikepdf.Array):
                # Multiple streams - process each
                for i, stream_ref in enumerate(contents):
                    stream = pdf.get_object(stream_ref.objgen)
                    _replace_in_stream(stream, replacements)
            else:
                # Single stream
                stream = contents
                _replace_in_stream(stream, replacements)

        # Save the modified PDF
        pdf.save(output_path)

    return invoice_number


def _replace_in_stream(stream, replacements: dict) -> None:
    """Replace text in a PDF content stream."""
    try:
        # Get raw stream data
        data = stream.read_bytes()

        # Try to decode (might be compressed)
        try:
            decoded = zlib.decompress(data)
            was_compressed = True
        except:
            decoded = data
            was_compressed = False

        # Convert to string for manipulation
        text = decoded.decode('latin-1', errors='replace')

        # Perform replacements
        modified = False
        for old_val, new_val in replacements.items():
            if old_val and old_val in text:
                text = text.replace(old_val, new_val)
                modified = True

        if modified:
            # Convert back to bytes
            new_data = text.encode('latin-1', errors='replace')

            # Recompress if it was compressed
            if was_compressed:
                new_data = zlib.compress(new_data)

            # Write back to stream
            stream.write(new_data, filter=pikepdf.Name("/FlateDecode") if was_compressed else None)

    except Exception as e:
        print(f"Warning: Could not process stream: {e}")


def _format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MM/DD/YY format."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%m/%d/%y")
    except:
        return date_str


def _format_line_item(item: dict, currency: str) -> str:
    """Format a line item for PDF."""
    if not item:
        return ""

    item_no = item.get("item_no", "")
    desc = item.get("description", "")
    qty = int(item.get("quantity", 0))
    unit_price = _get_amount(item.get("unit_price"))
    line_total = _get_amount(item.get("line_total"))

    # Format to match template style
    return f"{item_no} {desc} {qty} {currency} {unit_price:.2f} P1 {currency} {line_total:.3f}"


def _get_amount(money_obj) -> float:
    """Extract amount from money object."""
    if money_obj is None:
        return 0.0
    if isinstance(money_obj, dict):
        return money_obj.get("amount", 0.0)
    return float(money_obj)


def _format_money(amount: float, currency: str = "") -> str:
    """Format amount as currency string."""
    if amount is None or amount == 0:
        return ""
    return f"{currency} {amount:.2f}".strip()
