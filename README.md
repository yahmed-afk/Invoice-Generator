# SAP B1 Invoice Generator

Generate vendor-specific PDF invoices from SAP Business One Purchase Order screenshots.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure tesseract is installed (macOS)
brew install tesseract

# Run the pipeline
python invoice_pipeline.py --image input/po.png
```

## Usage

### Full Pipeline (Screenshot → PDF)

```bash
# Auto-detect vendor from screenshot
python invoice_pipeline.py --image input/po.png

# Specify vendor explicitly
python invoice_pipeline.py --image input/po.png --vendor acme_associates

# Custom output directory
python invoice_pipeline.py --image input/po.png --output-dir results/
```

### From Pre-extracted JSON

```bash
# Skip OCR, use existing JSON
python invoice_pipeline.py --json output/extracted_po.json
```

## Output Files

After running, you'll find in `output/`:
- `<vendor_key>_extracted.json` - Extracted PO data
- `<vendor_key>_invoice.pdf` - Generated invoice PDF
- `debug_ocr_text.txt` - Raw OCR output (for debugging)

## Project Structure

```
├── input/                  # Place PO screenshots here
├── output/                 # Generated files
├── templates/              # Vendor PDF templates
├── utils/
│   ├── ocr_engine.py      # OCR preprocessing & extraction
│   ├── po_extractor.py    # PO screenshot → JSON
│   ├── vendor_registry.py # Vendor config management
│   ├── layouts.py         # PDF coordinate mappings
│   └── vendors.json       # Vendor registry
├── invoice_pipeline.py    # Main CLI tool
└── tests/                 # Test suite
```

## Adding New Vendors

1. Add vendor entry to `utils/vendors.json`
2. Add PDF template to `templates/`
3. Add coordinate layout to `utils/layouts.py`

## Running Tests

```bash
pytest tests/ -v
```
