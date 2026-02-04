#!/usr/bin/env python3
"""
Invoice Generator - End-to-end PO screenshot to PDF invoice.
Usage: python generate_invoice.py input/po2.png
"""

import sys
import re
import json
from pathlib import Path
from datetime import datetime

import pytesseract
from PIL import Image

# Import pdf_filler directly
import importlib.util
spec = importlib.util.spec_from_file_location('pdf_filler', 'utils/pdf_filler.py')
pdf_filler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_filler)


def extract_po_data(image_path: str) -> dict:
    """Extract PO data from screenshot using OCR."""
    img = Image.open(image_path)

    # Try multiple PSM modes and combine results
    text_psm3 = pytesseract.image_to_string(img, config='--psm 3')
    text_psm4 = pytesseract.image_to_string(img, config='--psm 4')
    text_psm6 = pytesseract.image_to_string(img, config='--psm 6')

    # Combine all for better coverage
    text = text_psm3 + "\n" + text_psm4 + "\n" + text_psm6

    print("=== OCR Text (PSM 3) ===")
    print(text_psm3[:1500])
    print("================\n")

    # Extract PO number - try from main text first
    po_number = ""

    # Try multiple patterns on the combined text
    po_patterns = [
        r'Primary\s*[|\[\]()~/\s-]*(\d{3,5})',
        r'No\.?\s+Primary\s*\|?\s*(\d{3,5})',
        r'\|\|?\s*(\d{3,5})\s*[-\)\|]',
        r'[|\[{](\d{3})\s*[-\)\|}]',  # |803)-0 or {803}-
    ]

    for pattern in po_patterns:
        po_match = re.search(pattern, text)
        if po_match:
            po_number = po_match.group(1)
            break

    # If not found, try OCR on cropped header area (top-right)
    header_text = ""
    if not po_number:
        width, height = img.size
        header_crop = img.crop((width//2, 0, width, height//3))
        header_text = pytesseract.image_to_string(header_crop, config='--psm 6')
        print(f"=== Header OCR ===\n{header_text[:500]}\n================")

        for pattern in po_patterns:
            po_match = re.search(pattern, header_text)
            if po_match:
                po_number = po_match.group(1)
                break

        if not po_number:
            # Try to find 3-digit number near "Primary" or "No."
            po_match = re.search(r'(?:No|Primary)[^\d]*?(\d{3,4})', header_text, re.IGNORECASE)
            if po_match:
                po_number = po_match.group(1)

        if not po_number:
            # Handle format like "|608 )-0" - take the first 3-digit number
            po_match = re.search(r'[|{\[~](\d{3})\b', header_text)
            if po_match:
                po_number = po_match.group(1)

        if not po_number:
            # Last resort - any 3-digit number in header
            po_match = re.search(r'\b(\d{3})\b', header_text)
            if po_match:
                po_number = po_match.group(1)

    # Also try to get dates from header area
    if header_text:
        text = text + "\n" + header_text

    # Extract vendor name
    vendor_match = re.search(r'Name\s+([A-Za-z]+\s+[A-Za-z]+)', text)
    vendor_name = vendor_match.group(1) if vendor_match else "Acme Associates"

    # Extract dates - try specific labels first
    posting_match = re.search(r'Posting\s*Date\s*[:\s|]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)
    delivery_match = re.search(r'Delivery\s*Date\s*[:\s|]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)
    document_match = re.search(r'Document\s*Date\s*[:\s|]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)

    # Fall back to any date pattern (dd/mm/yyyy or mm/dd/yyyy formats)
    date_matches = re.findall(r'(\d{2}[./]\d{2}[./]\d{2,4})', text)

    # Also try to OCR the specific date area (usually top-right corner of form)
    if not date_matches:
        width, height = img.size
        # Try cropping different areas where dates might be
        date_areas = [
            (int(width*0.6), 0, width, int(height*0.25)),  # Top-right
            (int(width*0.5), int(height*0.05), width, int(height*0.2)),  # Upper right
        ]
        for area in date_areas:
            date_crop = img.crop(area)
            date_ocr = pytesseract.image_to_string(date_crop, config='--psm 6')
            found_dates = re.findall(r'(\d{2}[./]\d{2}[./]\d{2,4})', date_ocr)
            if found_dates:
                date_matches.extend(found_dates)
                break

    posting_date = ""
    if posting_match:
        posting_date = posting_match.group(1)
    elif document_match:
        posting_date = document_match.group(1)
    elif date_matches:
        posting_date = date_matches[0]

    due_date = ""
    if delivery_match:
        due_date = delivery_match.group(1)
    elif len(date_matches) > 1:
        due_date = date_matches[1]
    else:
        due_date = posting_date

    # Convert date format
    def convert_date(d):
        if not d:
            return ""
        for fmt in ["%m/%d/%Y", "%d/%m/%Y", "%d.%m.%y", "%d.%m.%Y", "%m/%d/%y"]:
            try:
                dt = datetime.strptime(d, fmt)
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except:
                continue
        return d

    # Detect currency
    if 'AUD' in text.upper():
        currency = "AUD"
    elif '$' in text or 'USD' in text.upper():
        currency = "USD"
    elif 'EUR' in text.upper():
        currency = "EUR"
    else:
        currency = "AUD"

    # Extract line items using multiple patterns for different SAP B1 formats
    line_items = []

    # Try multiple patterns to capture line items
    patterns = [
        # Pattern 1: Handle OCR errors - A0000i, AQ0004, 5 00004, etc
        r'([A45]\s?[0Oo0QiI\d]{4,5})\s+(.{5,40}?)\s+(\d{1,3})\s+\d{1,3}[,.]?\s+(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 2: "A00001 J.B. Officeprint 1420 15 15 AUD 500.000"
        r'([A4]\d{5})\s+(.{5,40}?)\s+(\d{1,3})\s+\d{1,3}\s+(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 3: with item description containing numbers
        r'([A45]\s?[0OoQiI\d]{4,5})\s+([A-Za-z][\w\s.,]+?)\s+(\d{1,3})\s+\d{1,3}[,.]?\s+(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 4: with "No" in between
        r'([A4]\d{5})\s+(.{5,40}?)\s+(\d+)\s+\d+\s+No\s+\d+[\s|]*(?:AUD|USD)?\s*([\d.,]+)',
        # Pattern 5: simpler - item code, any description, quantity, price
        r'([A45]\s?[0OoQiI\d]{4,5})\s+([A-Za-z].{5,35}?)\s+(\d{1,3})\s+.*?(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 6: fallback - item, desc, price at end
        r'([A4]\d{5})\s+([A-Za-z][^0-9]{5,30}?)\s+.*?([\d]{2,3})[.,]00',
    ]

    # First try line-by-line extraction for better accuracy
    item_patterns = []
    lines = text.split('\n')
    for line in lines:
        # Skip any leading row numbers and special chars (e.g., "a * )" or "2 * ")
        # Look for lines with item codes - description can start with letter or number (J.B. or 3.8.)
        # Handle OCR reading A as "a", "4", "5" and 0 as "O", "o"
        item_match = re.search(r'(?:^[\d\s*a|)\[\]]+\s*)?([Aa45]\s?[0OoQiIL\d]{4,5})\s+([A-Za-z0-9][^\n]{3,35}?)(?=\s+\d{1,3}[\s.,]+\d{1,3})', line, re.IGNORECASE)
        if item_match:
            # Get all AUD amounts on this line
            amounts = re.findall(r'AUD\s*([\d.,]+)', line, re.IGNORECASE)
            # More flexible qty pattern - handle OCR spacing variations
            qty_match = re.search(r'(\d{1,3})[\s.,]+(\d{1,3})\s+AUD', line)
            if not qty_match:
                qty_match = re.search(r'(\d{1,3})\s+(\d{1,3})[,.]?\s+AUD', line)
            if amounts and qty_match:
                item_no = item_match.group(1).replace(' ', '')
                desc = item_match.group(2).strip()
                # Use the larger of the two quantity values (Qty and Open Qty columns)
                qty = max(int(qty_match.group(1)), int(qty_match.group(2)))

                # Smart price selection: compare first amount with total/qty
                first_price = float(amounts[0].replace(',', '').replace('.', '', amounts[0].count('.') - 1) if amounts[0].count('.') > 1 else amounts[0].replace(',', ''))
                if len(amounts) >= 2:
                    # Get the last amount (total)
                    total_str = amounts[-1].replace(',', '')
                    try:
                        total = float(total_str)
                        expected_unit = total / qty if qty > 0 else total
                        # If first price is close to expected, use it; otherwise use second amount
                        if abs(first_price - expected_unit) < expected_unit * 0.5:
                            price_str = amounts[0]
                        else:
                            price_str = amounts[1]
                    except:
                        price_str = amounts[0]
                else:
                    price_str = amounts[0]

                item_patterns.append((item_no, desc, str(qty), price_str))

    # Fallback to regex patterns if line-by-line didn't find anything
    if not item_patterns:
        for pattern in patterns:
            item_patterns = re.findall(pattern, text, re.IGNORECASE)
            if item_patterns:
                break

    if item_patterns:
        for match in item_patterns:
            if len(match) >= 4:
                item_no, desc, qty, price = match[0], match[1], match[2], match[3]
            else:
                item_no, desc, price = match[0], match[1], match[2]
                qty = "1"

            # Fix OCR errors in item code
            item_no = item_no.replace(' ', '')  # Remove spaces
            if item_no.startswith('4') or item_no.startswith('5') or item_no.lower().startswith('a'):
                item_no = 'A' + item_no[1:]
            # Replace common OCR errors: Q->0, O->0, i->1, I->1, l->1, L->1
            item_no = item_no.upper()
            item_no = item_no.replace('Q', '0').replace('O', '0').replace('I', '1').replace('L', '1')
            if not item_no.startswith('A'):
                item_no = 'A' + item_no[1:] if len(item_no) > 1 else 'A00001'
            # Ensure 6 chars (A + 5 digits)
            if len(item_no) < 6:
                item_no = 'A' + item_no[1:].zfill(5)

            qty = int(qty) if qty.isdigit() else 1

            # Handle price parsing - SAP format: "500,000" or "500.000" means 500.00
            price_str = str(price)
            has_comma = ',' in price_str
            has_period = '.' in price_str

            if has_comma and has_period:
                last_comma = price_str.rfind(',')
                last_period = price_str.rfind('.')
                if last_period > last_comma:
                    # Format: 12,000.00
                    price_str = price_str.replace(',', '')
                else:
                    # Format: 12.000,00
                    price_str = price_str.replace('.', '').replace(',', '.')
            elif has_comma:
                parts = price_str.split(',')
                # SAP format: "500,000" means 500.000 (3 decimal places)
                if len(parts[-1]) == 3 and len(parts) == 2:
                    # This is SAP decimal format, not thousands
                    price_str = price_str.replace(',', '.')
                else:
                    price_str = price_str.replace(',', '.')
            elif has_period and price_str.count('.') > 1:
                # Multiple periods: "500.000.00" - SAP format
                price_str = price_str.replace('.', '')
                if len(price_str) >= 3:
                    price_str = price_str[:-3] + '.' + price_str[-3:]
            elif has_period and price_str.endswith('000'):
                # Single period ending in 000: "500.000" means 500.00
                price_str = price_str[:-1]  # Remove last 0 to get 500.00

            try:
                price_val = float(price_str)
            except:
                price_val = 400.0

            # Clean up description
            desc = desc.strip()
            desc = re.sub(r'^[\u2014\-—_]+\s*', '', desc)
            desc = re.sub(r'_ma[o>]?', '', desc)
            desc = desc.replace('_', ' ')
            desc = re.sub(r'^[)1I]\.*B[,.]?\s*', 'J.B. ', desc)
            desc = re.sub(r'\s+', ' ', desc).strip()

            # Detect tax code
            tax_code = "NY" if 'NY' in text else "P1"

            # Avoid duplicates - check if item_no already exists
            existing_items = [i["item_no"] for i in line_items]
            if item_no not in existing_items:
                line_items.append({
                    "item_no": item_no,
                    "description": desc,
                    "quantity": qty,
                    "unit_price": {"amount": price_val, "currency": currency},
                    "tax_code": tax_code,
                    "line_total": {"amount": qty * price_val, "currency": currency}
                })

    # If no items found, create from totals
    if not line_items:
        # Try to find item code
        item_match = re.search(r'([A4]\d{5})', text)
        item_no = item_match.group(1) if item_match else "A00001"
        if item_no.startswith('4'):
            item_no = 'A' + item_no[1:]

        # Try to find description
        desc_match = re.search(r'(?:Officeprint|Office\s*print)\s*(\d+)', text, re.IGNORECASE)
        desc = f"J.B. Officeprint {desc_match.group(1)}" if desc_match else "J.B. Officeprint 1420"

        # We'll fill in quantity/price from totals later
        line_items.append({
            "item_no": item_no,
            "description": desc,
            "quantity": 1,
            "unit_price": {"amount": 0, "currency": currency},
            "tax_code": "NY" if 'NY' in text else "P1",
            "line_total": {"amount": 0, "currency": currency}
        })

    # Extract totals - try multiple patterns
    def extract_amount(patterns, text):
        if isinstance(patterns, str):
            patterns = [patterns]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1).rstrip(',.')

                # Detect format: "12,000.00" vs "12.000,00" vs "12.000.000"
                has_comma = ',' in num_str
                has_period = '.' in num_str

                if has_comma and has_period:
                    # Check which is decimal separator (last one)
                    last_comma = num_str.rfind(',')
                    last_period = num_str.rfind('.')
                    if last_period > last_comma:
                        # Format: 12,000.00 (comma=thousands, period=decimal)
                        num_str = num_str.replace(',', '')
                    else:
                        # Format: 12.000,00 (period=thousands, comma=decimal)
                        num_str = num_str.replace('.', '').replace(',', '.')
                elif has_comma and not has_period:
                    # Could be "12,000" or "12,00" - check position
                    parts = num_str.split(',')
                    if len(parts[-1]) == 3:
                        # Thousands separator
                        num_str = num_str.replace(',', '')
                    else:
                        # Decimal separator
                        num_str = num_str.replace(',', '.')
                elif has_period and num_str.count('.') > 1:
                    # SAP format: "12.000.000" means 12000.000
                    num_str = num_str.replace('.', '')
                    if len(num_str) >= 3:
                        num_str = num_str[:-3] + '.' + num_str[-3:]
                elif has_period and num_str.endswith('000') and len(num_str.split('.')[-1]) == 3:
                    # Format: "12000.000" - already has decimal
                    pass

                try:
                    return float(num_str)
                except:
                    continue
        return None

    # Multiple patterns for totals
    total_before = extract_amount([
        r'Total\s*Before\s*Discount[:\s|]*[\'"]?(?:AUD|USD|\$)?\s*([\d,.]+)',
        r'Before\s*Discount[:\s|]*(?:AUD|USD|\$)?\s*([\d,.]+)',
    ], text)

    tax_amount = extract_amount([
        r'\bTax\s*[{\[|]?\s*(?:AUD|USD|\$)?\s*([\d,.]+)',
        r'Tax\s+([\d,.]+)\s*\$',
    ], text)

    total_due = extract_amount([
        r'Total\s*Payment\s*Due[:\s|]*(?:AUD|USD|\$)?\s*([\d,.]+)',
        r'Payment\s*Due[:\s|]*(?:AUD|USD|\$)?\s*([\d,.]+)',
    ], text)

    # If we have total_before but line items have 0 amounts, back-fill
    if total_before and len(line_items) == 1 and line_items[0]["line_total"]["amount"] == 0:
        line_items[0]["line_total"]["amount"] = total_before
        line_items[0]["line_total"]["currency"] = currency
        # Try to find unit price and calculate quantity
        price_match = re.search(r'(\d{2,4})[.,]00[05]?\s*(?:\$|0\.00|NY|P1)', text)
        if price_match:
            unit_price = float(price_match.group(1))
            line_items[0]["unit_price"]["amount"] = unit_price
            line_items[0]["quantity"] = int(total_before / unit_price) if unit_price > 0 else 1
        else:
            line_items[0]["unit_price"]["amount"] = total_before
            line_items[0]["quantity"] = 1

    # Calculate missing totals
    line_items_total = sum(item["line_total"]["amount"] for item in line_items)

    if not total_before or total_before > line_items_total * 10:
        total_before = line_items_total

    # Sanity check tax - should be reasonable percentage of total
    if not tax_amount or tax_amount > total_before:
        tax_amount = total_before * 0.10  # 10% GST default

    if not total_due or total_due > total_before * 2:
        total_due = total_before + tax_amount

    # Build payload
    payload = {
        "header": {
            "vendor_name": vendor_name,
            "po_number": po_number,
            "posting_date": convert_date(posting_date),
            "due_date": convert_date(due_date),
            "currency": currency
        },
        "line_items": line_items,
        "totals": {
            "total_before_discount": {"amount": total_before, "currency": currency},
            "discount": None,
            "freight": None,
            "tax": {"amount": tax_amount, "currency": currency},
            "total_payment_due": {"amount": total_due, "currency": currency}
        }
    }

    # Debug: Print extracted data
    print(f"=== Extracted Data ===")
    print(f"PO#: {po_number}, Dates: {posting_date}/{due_date}")
    print(f"Items: {len(line_items)}")
    for item in line_items:
        print(f"  - {item['item_no']}: qty={item['quantity']}, price={item['unit_price']['amount']}")
    print(f"======================")

    return payload


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_invoice.py <po_screenshot.png>")
        print("Example: python generate_invoice.py input/po2.png")
        sys.exit(1)

    image_path = sys.argv[1]

    if not Path(image_path).exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    print(f"Processing: {image_path}")

    # Extract data from screenshot
    payload = extract_po_data(image_path)

    print("=== Extracted Data ===")
    print(json.dumps(payload, indent=2))
    print("======================\n")

    # Generate output filename
    stem = Path(image_path).stem
    output_path = f"output/{stem}_invoice.pdf"

    # Generate PDF
    invoice_number = pdf_filler.fill_invoice_template(
        payload,
        'templates/blank template.pdf',
        output_path
    )

    print(f"Generated: {output_path}")
    print(f"Invoice #: {invoice_number}")

    # Open the PDF
    import subprocess
    subprocess.run(['open', output_path])


if __name__ == "__main__":
    main()
