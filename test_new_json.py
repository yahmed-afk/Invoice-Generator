import json
from pathlib import Path
from utils.po_parser import parse_po_screenshot, normalize_vendor_key

def main():
    # change this to your real screenshot name inside input/
    img_path = Path("input") / "po.png"

    payload = parse_po_screenshot(str(img_path))

    vendor_name = payload["header"]["vendor_name"]
    vendor_key = normalize_vendor_key(vendor_name)

    out = {
        "vendor_key": vendor_key,
        **payload
    }

    Path("output").mkdir(exist_ok=True)
    out_path = Path("output") / "extracted_po.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"Saved: {out_path}")
    print(f"Vendor name: {vendor_name}")
    print(f"Vendor key: {vendor_key}")

if __name__ == "__main__":
    main()
