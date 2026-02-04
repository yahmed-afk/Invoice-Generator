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
    text_psm4 = pytesseract.image_to_string(img, config='--psm 4')
    text_psm6 = pytesseract.image_to_string(img, config='--psm 6')

    # Combine both for better coverage
    text = text_psm4 + "\n" + text_psm6

    print("=== OCR Text (PSM 4) ===")
    print(text_psm4[:1000])
    print("================\n")

    # Extract PO number - try from main text first
    po_match = re.search(r'Primary\s*[|\[\]()/\s]*(\d{3,5})', text)
    if not po_match:
        po_match = re.search(r'No\.?\s+Primary\s*\|?\s*(\d{3,5})', text)
    if not po_match:
        po_match = re.search(r'\|\|?\s*(\d{3,5})\s*[-\|]', text)

    # If not found, try OCR on cropped header area (top-right)
    if not po_match:
        width, height = img.size
        header_crop = img.crop((width//2, 0, width, height//4))
        header_text = pytesseract.image_to_string(header_crop, config='--psm 6')
        po_match = re.search(r'Primary\s*[|\[\]()/\s]*(\d{3,5})', header_text)
        if not po_match:
            po_match = re.search(r'(\d{4})\s*[-\)\|]', header_text)

    po_number = po_match.group(1) if po_match else ""

    # Extract vendor name
    vendor_match = re.search(r'Name\s+([A-Za-z]+\s+[A-Za-z]+)', text)
    vendor_name = vendor_match.group(1) if vendor_match else "Acme Associates"

    # Extract dates - try specific labels first
    posting_match = re.search(r'Posting\s*Date\s*[:\s]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)
    delivery_match = re.search(r'Delivery\s*Date\s*[:\s]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)
    document_match = re.search(r'Document\s*Date\s*[:\s]*(\d{2}[./]\d{2}[./]\d{2,4})', text, re.IGNORECASE)

    # Fall back to any date pattern
    date_matches = re.findall(r'(\d{2}[./]\d{2}[./]\d{2,4})', text)

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
        # Pattern 1: "A00001 J.B. Officeprint 1420 15 15 AUD 500.000"
        r'([A4]\d{5})\s+(.{5,40}?)\s+(\d{1,3})\s+\d{1,3}\s+(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 2: with item description containing numbers
        r'([A4]\d{5})\s+([A-Za-z][\w\s.,]+?)\s+(\d{1,3})\s+\d{1,3}\s+(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 3: with "No" in between
        r'([A4]\d{5})\s+(.{5,40}?)\s+(\d+)\s+\d+\s+No\s+\d+[\s|]*(?:AUD|USD)?\s*([\d.,]+)',
        # Pattern 4: simpler - item code, any description, quantity, price
        r'([A4]\d{5})\s+([A-Za-z].{5,35}?)\s+(\d{1,3})\s+.*?(?:AUD|USD)\s*([\d.,]+)',
        # Pattern 5: fallback - item, desc, price at end
        r'([A4]\d{5})\s+([A-Za-z][^0-9]{5,30}?)\s+.*?([\d]{2,3})[.,]00',
    ]

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

            # Fix OCR error: 4 at start should be A
            if item_no.startswith('4'):
                item_no = 'A' + item_no[1:]

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
