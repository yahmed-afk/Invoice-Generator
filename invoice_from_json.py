import json
from pathlib import Path
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import white
from reportlab.lib.pagesizes import letter


# --- UTIL ---
def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if cur is None:
            return default
        cur = cur.get(k)
    return cur if cur is not None else default

def money_amount(m):
    # m can be None or {"currency": "...", "amount": ...}
    if not m:
        return None
    return m.get("amount")

def fmt_money(amount, currency=""):
    if amount is None:
        return ""
    # keep 2 decimals
    return f"{currency} {amount:,.2f}".strip()

def fmt_date(s: str) -> str:
    # Accepts "YYYY-MM-DD" from our payload; returns "MM/DD/YYYY"
    if not s:
        return ""
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%m/%d/%Y")
    except Exception:
        return s


# --- TEMPLATE REGISTRY ---
def resolve_vendor(vendor_key: str, registry_path: str = "utils/vendors.json") -> dict:
    reg = load_json(registry_path)
    if vendor_key not in reg:
        raise KeyError(f"Vendor key '{vendor_key}' not found in {registry_path}. Available: {list(reg.keys())}")
    return reg[vendor_key]


# --- ACME PLACEMENT (coordinates) ---
# These coordinates will need calibration to match your PDF template exactly.
# We start with placeholders; you will adjust by trial once you see the output.
ACME_LAYOUT = {
    "page": 0,

        "masks": {
        "po_number":  {"x": 445, "y": 612, "w": 140, "h": 16},
        "date":       {"x": 445, "y": 642, "w": 140, "h": 16},
        "due_date":   {"x": 445, "y": 627, "w": 140, "h": 16},

        "totals_box": {"x": 420, "y": 135, "w": 170, "h": 110}
    },


    # Header fields
    "po_number":  {"x": 470, "y": 620, "size": 10},
    "date":       {"x": 470, "y": 650, "size": 10},
    "due_date":   {"x": 470, "y": 635, "size": 10},

    # Table area (top row start)
    "table": {
        "start_x": 55,
        "start_y": 505,
        "row_h": 18,
        "max_rows": 12,
        "cols": {
            "description": {"x": 55,  "size": 10},
            "quantity":    {"x": 340, "size": 10},
            "price":       {"x": 415, "size": 10},
            "line_total":  {"x": 500, "size": 10}
        }
    },

    # Totals
    "total_before_discount": {"x": 500, "y": 215, "size": 10},
    "discount":              {"x": 500, "y": 200, "size": 10},
    "freight":               {"x": 500, "y": 185, "size": 10},
    "tax":                   {"x": 500, "y": 170, "size": 10},
    "total_payment_due":     {"x": 500, "y": 145, "size": 12},
}


def draw_text(c: canvas.Canvas, x: float, y: float, text: str, size: int = 10):
    if text is None:
        text = ""
    c.setFont("Helvetica", size)
    c.drawString(x, y, str(text))
    
def whiteout(c: canvas.Canvas, x: float, y: float, w: float, h: float):
    """
    Draw a white rectangle to cover existing template text before writing new text.
    """
    c.saveState()
    c.setFillColor(white)
    c.setStrokeColor(white)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.restoreState()



def build_overlay_pdf(payload: dict, vendor_key: str, overlay_path: str) -> None:
    """
    Creates a 1-page overlay PDF (transparent text layer) matching the template page size.
    """
    # Read template size if possible; fallback to letter.
    vendor_cfg = resolve_vendor(vendor_key)
    template_path = vendor_cfg["template_path"]
    reader = PdfReader(template_path)
    first_page = reader.pages[0]
    w = float(first_page.mediabox.width)
    h = float(first_page.mediabox.height)

    c = canvas.Canvas(overlay_path, pagesize=(w, h))

        # --- Mask template text so overlay does NOT look duplicated ---
    m = ACME_LAYOUT.get("masks", {})
    whiteout(c, m["po_number"]["x"], m["po_number"]["y"], m["po_number"]["w"], m["po_number"]["h"])
    whiteout(c, m["date"]["x"], m["date"]["y"], m["date"]["w"], m["date"]["h"])
    whiteout(c, m["due_date"]["x"], m["due_date"]["y"], m["due_date"]["w"], m["due_date"]["h"])
    whiteout(c, m["totals_box"]["x"], m["totals_box"]["y"], m["totals_box"]["w"], m["totals_box"]["h"])


    currency = safe_get(payload, "header", "currency", default="") or ""

    # Header
    po_number = safe_get(payload, "header", "po_number", default="")
    posting_date = fmt_date(safe_get(payload, "header", "posting_date", default=""))
    due_date = fmt_date(safe_get(payload, "header", "due_date", default=""))

    draw_text(c, ACME_LAYOUT["po_number"]["x"], ACME_LAYOUT["po_number"]["y"], po_number, ACME_LAYOUT["po_number"]["size"])
    draw_text(c, ACME_LAYOUT["date"]["x"], ACME_LAYOUT["date"]["y"], posting_date, ACME_LAYOUT["date"]["size"])
    draw_text(c, ACME_LAYOUT["due_date"]["x"], ACME_LAYOUT["due_date"]["y"], due_date, ACME_LAYOUT["due_date"]["size"])

    # Lines
    lines = payload.get("line_items", [])
    table = ACME_LAYOUT["table"]
    max_rows = table["max_rows"]

    for i, line in enumerate(lines[:max_rows]):
        y = table["start_y"] - i * table["row_h"] 
        
        whiteout(c, 50, y - 3, 540, 16)

        desc = line.get("description", "")
        qty = line.get("quantity", "")
        price = money_amount(line.get("unit_price"))
        lt = money_amount(line.get("line_total"))

        draw_text(c, table["cols"]["description"]["x"], y, desc, table["cols"]["description"]["size"])
        draw_text(c, table["cols"]["quantity"]["x"], y, qty, table["cols"]["quantity"]["size"])
        draw_text(c, table["cols"]["price"]["x"], y, fmt_money(price, currency), table["cols"]["price"]["size"])
        draw_text(c, table["cols"]["line_total"]["x"], y, fmt_money(lt, currency), table["cols"]["line_total"]["size"])

    # Totals
    totals = payload.get("totals", {})
    draw_text(c, ACME_LAYOUT["total_before_discount"]["x"], ACME_LAYOUT["total_before_discount"]["y"],
              fmt_money(money_amount(totals.get("total_before_discount")), currency), ACME_LAYOUT["total_before_discount"]["size"])
    draw_text(c, ACME_LAYOUT["discount"]["x"], ACME_LAYOUT["discount"]["y"],
              fmt_money(money_amount(totals.get("discount")), currency), ACME_LAYOUT["discount"]["size"])
    draw_text(c, ACME_LAYOUT["freight"]["x"], ACME_LAYOUT["freight"]["y"],
              fmt_money(money_amount(totals.get("freight")), currency), ACME_LAYOUT["freight"]["size"])
    draw_text(c, ACME_LAYOUT["tax"]["x"], ACME_LAYOUT["tax"]["y"],
              fmt_money(money_amount(totals.get("tax")), currency), ACME_LAYOUT["tax"]["size"])
    draw_text(c, ACME_LAYOUT["total_payment_due"]["x"], ACME_LAYOUT["total_payment_due"]["y"],
              fmt_money(money_amount(totals.get("total_payment_due")), currency), ACME_LAYOUT["total_payment_due"]["size"])

    c.showPage()
    c.save()


def merge_overlay(template_path: str, overlay_path: str, out_path: str):
    template_reader = PdfReader(template_path)
    overlay_reader = PdfReader(overlay_path)
    writer = PdfWriter()

    base_page = template_reader.pages[0]
    overlay_page = overlay_reader.pages[0]
    base_page.merge_page(overlay_page)
    writer.add_page(base_page)

    with open(out_path, "wb") as f:
        writer.write(f)


def main():
    # Use the JSON generated by your test step
    extracted_path = Path("output") / "extracted_po.json"
    if not extracted_path.exists():
        raise FileNotFoundError("output/extracted_po.json not found. Run: python test_new_json.py")

    payload = load_json(str(extracted_path))
    vendor_key = payload.get("vendor_key")
    if not vendor_key:
        # fallback if vendor_key not embedded
        vendor_name = safe_get(payload, "header", "vendor_name", default="")
        from utils.po_parser import normalize_vendor_key
        vendor_key = normalize_vendor_key(vendor_name)

    vendor_cfg = resolve_vendor(vendor_key)
    template_path = vendor_cfg["template_path"]

    Path("output").mkdir(exist_ok=True)
    overlay_path = str(Path("output") / f"{vendor_key}_overlay.pdf")
    out_path = str(Path("output") / f"{vendor_key}_invoice.pdf")

    build_overlay_pdf(payload, vendor_key, overlay_path)
    merge_overlay(template_path, overlay_path, out_path)

    print(f"Template: {template_path}")
    print(f"Overlay:  {overlay_path}")
    print(f"Output:   {out_path}")


if __name__ == "__main__":
    main()
