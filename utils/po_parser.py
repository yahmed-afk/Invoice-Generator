import re

def normalize_vendor_key(vendor_name: str) -> str:
    s = vendor_name.strip().lower()
    s = re.sub(r'[^a-z0-9\s]+', '', s)
    s = re.sub(r'\s+', '_', s)
    return s

def parse_po_screenshot(image_path: str) -> dict:
    """
    TODO: Implement screenshot -> structured JSON extraction.

    For now this returns a stub so the plumbing (vendor/mapping/template) can be tested.
    """
    return {
        "header": {
            "vendor_name": "Acme Associates",
            "po_number": "79",
            "posting_date": "2026-01-27",
            "due_date": "2026-01-27",
            "currency": "AUD"
        },
        "line_items": [
            {
                "line_no": 1,
                "item_no": "A00001",
                "description": "J.B. Officeprint 1420",
                "quantity": 5,
                "unit_price": {"currency": "AUD", "amount": 500.00},
                "line_total": {"currency": "AUD", "amount": 2500.00}
            }
        ],
        "totals": {
            "total_before_discount": {"currency": "AUD", "amount": 2500.00},
            "discount": None,
            "freight": None,
            "tax": {"currency": "AUD", "amount": 250.00},
            "total_payment_due": {"currency": "AUD", "amount": 2750.00}
        }
    }
