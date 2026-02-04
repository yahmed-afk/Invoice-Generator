"""
PDF Layout Definitions - Coordinate mappings for vendor invoice templates.

Each layout defines:
- masks: Areas to white-out before drawing (prevents double text)
- field positions: x, y coordinates and font sizes for header/totals
- table: Column positions and row spacing for line items
"""

LAYOUTS = {
    "acme_associates": {
        "page": 0,
        "page_size": (612, 792),

        # Masks to cover existing template values (white rectangles)
        # Positioned precisely over the value areas
        "masks": {
            # Right side header info
            "date":           {"x": 470, "y": 665, "w": 100, "h": 14},
            "due_date":       {"x": 470, "y": 635, "w": 100, "h": 14},
            "invoice_number": {"x": 470, "y": 605, "w": 100, "h": 14},
            "po_number":      {"x": 470, "y": 575, "w": 100, "h": 14},
            "receipt_number": {"x": 470, "y": 545, "w": 100, "h": 14},
            # Line items area
            "line_items":     {"x": 50, "y": 440, "w": 520, "h": 25},
            # Totals values (right side)
            "totals_values":  {"x": 470, "y": 200, "w": 110, "h": 90},
        },

        # Header field positions (where to draw new values)
        "date":       {"x": 475, "y": 668, "size": 10},
        "due_date":   {"x": 475, "y": 638, "size": 10},
        "po_number":  {"x": 475, "y": 578, "size": 10},

        # Line items table configuration
        "table": {
            "start_y": 455,
            "row_h": 20,
            "max_rows": 10,
            "cols": {
                "description": {"x": 55,  "size": 9},
                "quantity":    {"x": 285, "size": 9},
                "price":       {"x": 340, "size": 9},
                "tax_code":    {"x": 420, "size": 9},
                "line_total":  {"x": 490, "size": 9},
            }
        },

        # Totals section positions (right-aligned values)
        "total_before_discount": {"x": 520, "y": 270, "size": 10, "align": "right"},
        "discount":              {"x": 520, "y": 252, "size": 10, "align": "right"},
        "freight":               {"x": 520, "y": 234, "size": 10, "align": "right"},
        "tax":                   {"x": 520, "y": 216, "size": 10, "align": "right"},
        "total_payment_due":     {"x": 520, "y": 198, "size": 11, "align": "right"},
    }
}


def get_layout(vendor_key: str) -> dict:
    """
    Get the PDF layout configuration for a vendor.

    Args:
        vendor_key: Normalized vendor key (e.g., "acme_associates")

    Returns:
        Layout configuration dict

    Raises:
        KeyError: If no layout defined for vendor
    """
    if vendor_key not in LAYOUTS:
        available = list(LAYOUTS.keys())
        raise KeyError(
            f"No layout defined for vendor '{vendor_key}'. "
            f"Available layouts: {available}"
        )
    return LAYOUTS[vendor_key]
