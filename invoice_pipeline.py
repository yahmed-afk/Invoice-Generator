#!/usr/bin/env python3
"""
Invoice Pipeline - End-to-end SAP B1 PO screenshot to PDF invoice generation.

Usage:
    python invoice_pipeline.py --image input/po.png
    python invoice_pipeline.py --image input/po.png --vendor acme_associates
    python invoice_pipeline.py --json output/extracted_po.json
"""

import argparse
import json
import sys
from pathlib import Path

from utils.po_extractor import extract_po_from_image
from utils.vendor_registry import normalize_vendor_key, load_vendor_config, find_vendor_by_name
from utils.pdf_filler import fill_invoice_template


def main():
    parser = argparse.ArgumentParser(
        description="Generate vendor invoice PDF from SAP B1 PO screenshot"
    )
    parser.add_argument(
        "--image", "-i",
        help="Path to PO screenshot image (PNG/JPG)"
    )
    parser.add_argument(
        "--json", "-j",
        help="Path to pre-extracted JSON (skip OCR extraction)"
    )
    parser.add_argument(
        "--vendor", "-v",
        help="Override vendor key (default: auto-detect from vendor_name)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="output",
        help="Output directory (default: output/)"
    )
    parser.add_argument(
        "--po-number", "-p",
        help="Override PO number (if OCR fails to detect)"
    )

    args = parser.parse_args()

    if not args.image and not args.json:
        parser.error("Either --image or --json is required")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Step 1: Extract or load PO data
    if args.json:
        print(f"Loading pre-extracted JSON: {args.json}")
        payload = load_json(args.json)
    else:
        print(f"Extracting PO data from: {args.image}")
        payload = extract_po_from_image(args.image)

    # Step 2: Determine vendor key
    if args.vendor:
        vendor_key = args.vendor
    else:
        vendor_name = payload.get("header", {}).get("vendor_name", "")
        # Try fuzzy matching first, fall back to normalized key
        vendor_key = find_vendor_by_name(vendor_name)
        if vendor_key:
            print(f"Matched vendor: {vendor_key} (from '{vendor_name}')")
        else:
            vendor_key = normalize_vendor_key(vendor_name)
            print(f"Auto-detected vendor key: {vendor_key}")

    # Add vendor_key to payload
    payload["vendor_key"] = vendor_key

    # Override PO number if specified
    if args.po_number:
        payload["header"]["po_number"] = args.po_number
        print(f"Using PO number override: {args.po_number}")

    # Step 3: Validate vendor config and template
    try:
        vendor_cfg = load_vendor_config(vendor_key)
    except KeyError as e:
        print(f"ERROR: {e}")
        print("Available vendors in registry:")
        from utils.vendor_registry import get_all_vendors
        for k, v in get_all_vendors().items():
            print(f"  - {k}: {v.get('display_name', 'N/A')}")
        sys.exit(1)

    template_path = vendor_cfg.get("template_path")
    if not template_path or not Path(template_path).exists():
        print(f"ERROR: Template not found: {template_path}")
        print("Available templates:")
        templates_dir = Path("templates")
        if templates_dir.exists():
            for f in templates_dir.glob("*.pdf"):
                print(f"  - {f}")
        sys.exit(1)

    # Step 4: Save extracted JSON
    json_path = output_dir / f"{vendor_key}_extracted.json"
    save_json(payload, json_path)
    print(f"Saved extracted data: {json_path}")

    # Step 5: Generate invoice PDF by filling blank template
    invoice_path = output_dir / f"{vendor_key}_invoice.pdf"
    invoice_number = fill_invoice_template(payload, template_path, str(invoice_path))

    print(f"Generated invoice: {invoice_path}")
    print(f"Invoice number: {invoice_number}")
    print("\nDone!")

    return 0


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
