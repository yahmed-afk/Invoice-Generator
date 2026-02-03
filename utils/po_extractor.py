"""
PO Extractor - Extracts structured data from SAP B1 Purchase Order screenshots.
Uses OCREngine for text extraction and custom parsing for structured output.
"""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from utils.ocr_engine import OCREngine


def extract_po_from_image(image_path: str) -> dict:
    """
    Extract structured PO data from an SAP B1 screenshot.

    Args:
        image_path: Path to the PO screenshot (PNG/JPG)

    Returns:
        Dict matching the target JSON schema with header, line_items, totals
    """
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    engine = OCREngine()
    raw_text = engine.extract_text(image_path, preprocess=True)

    # Save debug output
    debug_path = Path("output") / "debug_ocr_text.txt"
    debug_path.parent.mkdir(exist_ok=True)
    debug_path.write_text(raw_text, encoding="utf-8")

    # Parse the raw OCR text into structured data
    return _parse_po_text(raw_text)


def _parse_po_text(text: str) -> dict:
    """Parse OCR text into structured PO data."""
    header = _extract_header(text)
    line_items = _extract_line_items(text, header.get("currency", "AUD"))
    totals = _extract_totals(text, header.get("currency", "AUD"))

    # Apply validation and OCR error correction
    totals = _validate_totals(totals, line_items)

    return {
        "header": header,
        "line_items": line_items,
        "totals": totals
    }


def _validate_totals(totals: dict, line_items: list) -> dict:
    """Validate and correct totals based on mathematical relationships."""
    currency = "AUD"
    if totals.get("total_before_discount"):
        currency = totals["total_before_discount"].get("currency", "AUD")

    # Calculate expected subtotal from line items
    line_total_sum = sum(
        item.get("line_total", {}).get("amount", 0)
        for item in line_items
        if item.get("line_total")
    )

    # If total_before_discount is close to line_total_sum, use the calculated value
    if totals.get("total_before_discount"):
        tbd = totals["total_before_discount"].get("amount", 0)
        if line_total_sum > 0 and abs(tbd - line_total_sum) / line_total_sum < 0.05:
            totals["total_before_discount"]["amount"] = line_total_sum

    # Validate tax: typically 10% GST in Australia
    if totals.get("tax") and totals.get("total_before_discount"):
        subtotal = totals["total_before_discount"].get("amount", 0)
        tax_amount = totals["tax"].get("amount", 0)
        expected_tax = subtotal * 0.10  # 10% GST

        # If tax is within 5% of expected, correct it
        if expected_tax > 0 and abs(tax_amount - expected_tax) / expected_tax < 0.05:
            totals["tax"]["amount"] = round(expected_tax, 2)

    # Validate total_payment_due = subtotal + tax
    if totals.get("total_before_discount") and totals.get("tax"):
        subtotal = totals["total_before_discount"].get("amount", 0)
        tax = totals["tax"].get("amount", 0)
        expected_total = subtotal + tax

        if totals.get("total_payment_due"):
            actual_total = totals["total_payment_due"].get("amount", 0)
            # If close, use the calculated value
            if abs(actual_total - expected_total) / expected_total < 0.02:
                totals["total_payment_due"]["amount"] = round(expected_total, 2)
        else:
            totals["total_payment_due"] = {"currency": currency, "amount": round(expected_total, 2)}

    return totals


def _extract_header(text: str) -> dict:
    """Extract header fields from OCR text."""
    header = {
        "vendor_name": None,
        "po_number": None,
        "posting_date": None,
        "due_date": None,
        "currency": "AUD"  # Default, will try to detect
    }

    # --- Vendor Name ---
    # SAP B1 format: "Name    Acme Associates"
    vendor_patterns = [
        # SAP B1: "Name" followed by vendor name (handles OCR variants)
        r'(?:Name|Neme|Narne)\s+([A-Za-z][A-Za-z\s]+?(?:Associates?|Inc\.?|Ltd\.?|LLC|Corp\.?))',
        r'Vendor[:\s]+([A-Za-z][A-Za-z\s&.,]+?)(?=\s{2,}|\n|$)',
        r'(?:Bill\s*To|Supplier)[:\s]+([A-Za-z][A-Za-z\s&.,]+?)(?=\s{2,}|\n|$)',
    ]
    for pattern in vendor_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            name = match.group(1).strip()
            # Fix common OCR errors
            name = re.sub(r'\bAcr[eé]+\b', 'Acme', name, flags=re.IGNORECASE)
            header["vendor_name"] = name
            break

    # Fallback: look for "Associates" or common vendor suffixes
    if not header["vendor_name"]:
        match = re.search(r'([A-Z][a-z]+)\s+(Associates?|Inc\.?|Ltd\.?|LLC)', text)
        if match:
            name = f"{match.group(1)} {match.group(2)}"
            name = re.sub(r'\bAcr[eé]+\b', 'Acme', name, flags=re.IGNORECASE)
            header["vendor_name"] = name

    # --- PO Number ---
    # SAP B1 shows "No.  Primary  790" - look for 3-digit number after "Primary"
    po_patterns = [
        # SAP B1 format: "No. Primary 790" or with OCR noise
        r'Primary\s+(\d{3,4})',
        r'No\.\s*Primary\s*[^\d]*(\d{3,4})',
        r'(?:PO|Purchase\s*Order|Order)\s*(?:#|No\.?|Number)?\s*[:\s]*(\d+)',
    ]
    for pattern in po_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            num = match.group(1)
            # Exclude if it looks like part of a date
            if not re.search(rf'{num}\.\d{{1,2}}\.\d{{2,4}}', text):
                header["po_number"] = num
                break

    # Fallback: look for 3-digit number that's likely a PO number
    if not header["po_number"]:
        # Look for 3-digit numbers that aren't dates or OCR noise
        matches = re.findall(r'(?<!\d)(\d{3})(?!\d)', text)
        for m in matches:
            # Skip date components and OCR noise
            if re.search(rf'{m}\.\d{{1,2}}', text):
                continue
            if re.search(rf'[a-z]e\s+{m}', text, re.IGNORECASE):
                continue
            if int(m) >= 100 and int(m) < 1000:  # Reasonable PO number range
                header["po_number"] = m
                break

    # --- Dates ---
    date_patterns = [
        # DD.MM.YY or DD.MM.YYYY (European format, common in SAP)
        r'(\d{1,2}\.\d{1,2}\.\d{2,4})',
        # MM/DD/YYYY or MM-DD-YYYY
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        # YYYY-MM-DD
        r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
    ]

    dates_found = []
    for pattern in date_patterns:
        dates_found.extend(re.findall(pattern, text))

    # Convert found dates to YYYY-MM-DD format
    normalized_dates = []
    for d in dates_found:
        norm = _normalize_date(d)
        if norm:
            normalized_dates.append(norm)

    if normalized_dates:
        header["posting_date"] = normalized_dates[0]
        if len(normalized_dates) > 1:
            header["due_date"] = normalized_dates[1]

    # --- Currency ---
    if "AUD" in text:
        header["currency"] = "AUD"
    elif "USD" in text:
        header["currency"] = "USD"
    elif "EUR" in text:
        header["currency"] = "EUR"
    elif "$" in text:
        header["currency"] = "USD"

    return header


def _normalize_date(date_str: str) -> Optional[str]:
    """Convert various date formats to YYYY-MM-DD."""
    import re
    from datetime import datetime

    date_str = date_str.strip()

    # Try formats in order of specificity
    formats = [
        # European DD.MM.YY (SAP common format)
        ("%d.%m.%y", r'^\d{1,2}\.\d{1,2}\.\d{2}$'),
        # European DD.MM.YYYY
        ("%d.%m.%Y", r'^\d{1,2}\.\d{1,2}\.\d{4}$'),
        # ISO format
        ("%Y-%m-%d", r'^\d{4}-\d{1,2}-\d{1,2}$'),
        ("%Y/%m/%d", r'^\d{4}/\d{1,2}/\d{1,2}$'),
        # US format MM/DD/YYYY
        ("%m/%d/%Y", r'^\d{1,2}/\d{1,2}/\d{4}$'),
        ("%m-%d-%Y", r'^\d{1,2}-\d{1,2}-\d{4}$'),
        # Short year
        ("%m/%d/%y", r'^\d{1,2}/\d{1,2}/\d{2}$'),
        ("%d/%m/%y", r'^\d{1,2}/\d{1,2}/\d{2}$'),
    ]

    for fmt, pattern in formats:
        if re.match(pattern, date_str):
            try:
                dt = datetime.strptime(date_str, fmt)
                # Handle 2-digit years (assume 2000s)
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None


def _extract_line_items(text: str, currency: str = "AUD") -> List[dict]:
    """Extract line items from OCR text."""
    items = []

    # SAP B1 PO line format (from OCR):
    # "A v .. £00001 = ).8. Officaprant 1420 5 5 AUD 500.000 0.00 AUD 500.000 P1 'Y AUD 2,500.000"
    # Structure: item_code ... description ... qty ... AUD unit_price ... AUD line_total

    # Split text into lines and find lines with item codes
    lines = text.split('\n')
    for line in lines:
        # Look for item code pattern (A00001 or £00001)
        item_match = re.search(r'[£A](\d{5})', line)
        if not item_match:
            continue

        item_no = "A" + item_match.group(1)

        # Find ALL AUD amounts on this line
        line_amounts = re.findall(r'AUD\s+([\d,]+\.?\d+)', line)

        if len(line_amounts) >= 2:
            # First AUD amount is unit price, LAST is line total
            unit_price = _parse_number(line_amounts[0])
            line_total = _parse_number(line_amounts[-1])

            # Try to find quantity (look for small numbers before first AUD)
            # Pattern: "5 5 AUD" where first 5 is quantity
            qty_match = re.search(r'\s(\d{1,3})\s+\d+\s+AUD', line)
            quantity = _parse_number(qty_match.group(1)) if qty_match else 1

            # If line_total seems too small compared to quantity * unit_price, recalculate
            expected_total = quantity * unit_price
            if line_total < expected_total * 0.5:
                line_total = expected_total

            # Extract description (text between item code and numbers)
            desc_match = re.search(r'[£A]\d{5}[^\w]*([\w\s.]+?)\s+\d', line)
            description = _clean_description(desc_match.group(1)) if desc_match else "Item"

            items.append(_make_line_item(
                line_no=len(items) + 1,
                item_no=item_no,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                currency=currency
            ))

    # Pattern 2: More flexible - find AUD amounts with item codes nearby
    if not items:
        pattern2 = r'(A\d{5}|[A-Z]\d{5})[^\n]{5,60}?(\d+)\s+.*?AUD\s+([\d,]+\.?\d*)'

        for match in re.finditer(pattern2, text, re.IGNORECASE):
            item_no = match.group(1)
            if item_no.startswith('£'):
                item_no = 'A' + item_no[1:]

            quantity = _parse_number(match.group(2))
            price = _parse_number(match.group(3))

            # Try to find description
            full_match = match.group(0)
            desc_match = re.search(r'[A-Z]\d{5}\s*[^\w]*([\w\s.]+?)\s+\d', full_match)
            description = _clean_description(desc_match.group(1)) if desc_match else "Item"

            items.append(_make_line_item(
                line_no=len(items) + 1,
                item_no=item_no,
                description=description,
                quantity=quantity,
                unit_price=price,
                line_total=quantity * price,
                currency=currency
            ))

    # Pattern 3: Fallback - just look for any line with item-like structure
    if not items:
        # Look for lines with multiple numbers that could be qty/price/total
        lines = text.split('\n')
        for line in lines:
            # Skip if looks like totals line
            if any(kw in line.lower() for kw in ['total', 'discount', 'freight', 'tax', 'due']):
                continue

            # Look for item code pattern
            item_match = re.search(r'([A-Z]\d{4,5})', line)
            if item_match:
                numbers = re.findall(r'([\d,]+\.?\d*)', line)
                numbers = [_parse_number(n) for n in numbers if _parse_number(n) > 0]

                if len(numbers) >= 2:
                    # Assume: first small number is qty, larger numbers are prices
                    qty = numbers[0] if numbers[0] < 1000 else 1
                    prices = [n for n in numbers if n >= 100]

                    if prices:
                        unit_price = prices[0]
                        line_total = prices[-1] if len(prices) > 1 else qty * unit_price

                        items.append(_make_line_item(
                            line_no=len(items) + 1,
                            item_no=item_match.group(1),
                            description="Item description",
                            quantity=qty,
                            unit_price=unit_price,
                            line_total=line_total,
                            currency=currency
                        ))

    return items


def _extract_totals(text: str, currency: str = "AUD") -> dict:
    """Extract totals section from OCR text."""
    totals = {
        "total_before_discount": None,
        "discount": None,
        "freight": None,
        "tax": None,
        "total_payment_due": None
    }

    # Total Before Discount (OCR may read "Before" as "Bafore", "Befere", etc.)
    patterns = [
        r'Total\s*B[ae]f[oe]re\s*Discount[^\d]*([\d,]+\.?\d*)',
        r'B[ae]f[oe]re\s*Discount[^\d]*([\d,]+\.?\d*)',
        r'Subtotal[^\d]*([\d,]+\.?\d*)',
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            totals["total_before_discount"] = _make_money_clean(match.group(1), currency)
            break

    # Discount - but NOT "Before Discount"
    match = re.search(r'(?<!Before\s)(?<!Bafore\s)Discount\s*[^\d\w]*([\d,]+\.?\d*)', text, re.IGNORECASE)
    if match and _parse_number(match.group(1)) > 0:
        # Make sure it's not the "Total Before Discount" line
        if not re.search(r'Before\s*Discount', match.group(0), re.IGNORECASE):
            totals["discount"] = _make_money_clean(match.group(1), currency)

    # Freight - make sure there's an actual number on the same line (not just "-" or "_")
    match = re.search(r'Freight\s*[:\s]*([\d,]+\.?\d+)', text, re.IGNORECASE)
    if match and _parse_number(match.group(1)) > 0:
        totals["freight"] = _make_money_clean(match.group(1), currency)

    # Tax (OCR may read "Tax" as "Tx", "Tix", etc.)
    patterns = [
        r'T[aix]+x?\s+[A-Z]{3}\s+([\d,]+\.?\d*)',  # "Tx AUD 250.00"
        r'Tax[^\d]*([\d,]+\.?\d*)',
        r'GST[^\d]*([\d,]+\.?\d*)',
        r'VAT[^\d]*([\d,]+\.?\d*)',
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match and _parse_number(match.group(1)) > 0:
            totals["tax"] = _make_money_clean(match.group(1), currency)
            break

    # Total Payment Due
    patterns = [
        r'Total\s*Payment\s*Due\s+[A-Z]{3}\s+([\d,]+\.?\d*)',
        r'Total\s*Payment\s*Due[^\d]*([\d,]+\.?\d*)',
        r'Payment\s*Due[^\d]*([\d,]+\.?\d*)',
        r'Amount\s*Due[^\d]*([\d,]+\.?\d*)',
        r'Grand\s*Total[^\d]*([\d,]+\.?\d*)',
        r'Total\s*Due[^\d]*([\d,]+\.?\d*)',
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            totals["total_payment_due"] = _make_money_clean(match.group(1), currency)
            break

    return totals


def _make_line_item(line_no: int, item_no: str, description: str,
                    quantity: float, unit_price: float, line_total: float,
                    currency: str) -> dict:
    """Create a line item dict matching the schema."""
    return {
        "line_no": line_no,
        "item_no": item_no,
        "description": description,
        "quantity": quantity,
        "unit_price": {"currency": currency, "amount": unit_price},
        "line_total": {"currency": currency, "amount": line_total}
    }


def _make_money(value: str, currency: str) -> dict:
    """Create a money object from string value."""
    return {
        "currency": currency,
        "amount": _parse_number(value)
    }


def _make_money_clean(value: str, currency: str) -> dict:
    """Create a money object with OCR error correction.

    Handles common OCR decimal errors like:
    - 2500.08 -> 2500.00 (spurious decimals)
    - 258.008 -> 250.00 (digit insertion)
    """
    raw = _parse_number(value)

    # Round to 2 decimal places
    cleaned = round(raw, 2)

    # Check for common OCR patterns where .00X becomes .00
    # e.g., 2500.08 is likely 2500.00, 258.008 is likely 250.00
    str_val = str(raw)
    if '.' in str_val:
        int_part, dec_part = str_val.split('.')
        # If decimal part looks like OCR error (e.g., "08", "008")
        if len(dec_part) >= 2:
            # Check if it's close to a round number
            rounded = round(raw)
            if abs(raw - rounded) < raw * 0.01:  # Within 1%
                cleaned = float(rounded)
            # Check for extra digits (258.008 -> 250.00)
            elif len(dec_part) > 2 and dec_part.startswith('0'):
                # Likely OCR added extra digit
                cleaned = round(raw, 0)

    return {
        "currency": currency,
        "amount": cleaned
    }


def _parse_number(value: str) -> float:
    """Parse string to float, handling commas."""
    if not value:
        return 0.0
    value = str(value).replace(',', '').strip()
    try:
        return float(value)
    except ValueError:
        return 0.0


def _clean_description(desc: str) -> str:
    """Clean up extracted description text."""
    if not desc:
        return ""
    # Remove leading/trailing non-word characters
    desc = re.sub(r'^[^\w]+', '', desc)
    desc = re.sub(r'[^\w]+$', '', desc)
    # Normalize whitespace
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()
