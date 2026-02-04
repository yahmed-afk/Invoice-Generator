#!/usr/bin/env python3
"""
SAP Business One TRAILD Testing Automation Tool
Extracts structured data from SAP screenshot images.

Usage:
    python main.py <image_path>
    
Example:
    python main.py input/po_screenshot.png
"""

import sys
import json
import os
from pathlib import Path
from typing import Dict, Any

from utils.ocr_engine import OCREngine
from utils.parser import SAPDocumentParser


class SAPDocumentExtractor:
    """Main orchestrator for SAP document extraction."""
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize extractor.
        
        Args:
            output_dir: Directory to save output files
        """
        self.ocr_engine = OCREngine()
        self.parser = SAPDocumentParser()
        self.output_dir = Path(output_dir)
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def extract_from_image(self, image_path: str) -> Dict[str, Any]:
        """
        Extract structured data from SAP screenshot.
        
        Args:
            image_path: Path to screenshot image
            
        Returns:
            Extracted document data as dictionary
        """
        print(f"Processing image: {image_path}")
        print("-" * 60)
        
        # Step 1: Perform OCR
        print("Step 1: Performing OCR...")
        try:
            raw_text = self.ocr_engine.extract_text(image_path, preprocess=True)
            print(f"  ✓ Extracted {len(raw_text)} characters")
            
            # Save raw OCR text for debugging
            debug_path = self.output_dir / "debug_ocr_text.txt"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(raw_text)
            print(f"  ✓ Saved raw OCR text to {debug_path}")
            
        except Exception as e:
            print(f"  ✗ OCR failed: {str(e)}")
            raise
        
        # Step 2: Parse document structure
        print("\nStep 2: Parsing document structure...")
        try:
            parsed_data = self.parser.parse_document(raw_text)
            print(f"  ✓ Document Type: {parsed_data['doc_type']}")
            print(f"  ✓ Document Number: {parsed_data['doc_number']}")
            print(f"  ✓ Found {len(parsed_data['lines'])} line items")
            print(f"  ✓ Document Total: {parsed_data['doc_total']}")
            
        except Exception as e:
            print(f"  ✗ Parsing failed: {str(e)}")
            raise
        
        return parsed_data
    
    def save_json(self, data: Dict[str, Any], filename: str = "output.json") -> str:
        """
        Save parsed data to JSON file.
        
        Args:
            data: Parsed document data
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        output_path = self.output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(output_path)
    
    def print_summary(self, data: Dict[str, Any]) -> None:
        """
        Print formatted summary of extracted data.
        
        Args:
            data: Parsed document data
        """
        print("\n" + "=" * 60)
        print("EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Document Type: {data['doc_type']}")
        print(f"Document Number: {data['doc_number']}")
        print(f"\nLine Items ({len(data['lines'])} total):")
        print("-" * 60)
        
        for i, line in enumerate(data['lines'], 1):
            print(f"{i}. {line['item_code']} - {line['description']}")
            print(f"   Qty: {line['qty']}, Unit Price: ${line['unit_price']:.2f}, "
                  f"Line Total: ${line['line_total']:.2f}")
        
        print("-" * 60)
        print(f"Document Total: ${data['doc_total']:.2f}" if data['doc_total'] else "Document Total: N/A")
        print("=" * 60)


def check_tesseract_installation() -> bool:
    """
    Check if Tesseract OCR is installed and accessible.
    
    Returns:
        True if Tesseract is available, False otherwise
    """
    import subprocess
    
    try:
        result = subprocess.run(
            ['tesseract', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def print_usage():
    """Print usage information."""
    print("SAP Business One TRAILD Testing Tool")
    print("=" * 60)
    print("Usage:")
    print("  python main.py <image_path>")
    print("\nExample:")
    print("  python main.py input/po_screenshot.png")
    print("  python main.py /Users/john/Desktop/invoice.png")
    print("\nOutput:")
    print("  - JSON printed to console")
    print("  - output/output.json (saved file)")
    print("  - output/debug_ocr_text.txt (raw OCR text)")
    print("=" * 60)


def main():
    """Main entry point."""
    
    # Check arguments
    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    # Validate image path
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    
    # Check Tesseract installation
    if not check_tesseract_installation():
        print("=" * 60)
        print("ERROR: Tesseract OCR not found!")
        print("=" * 60)
        print("Please install Tesseract OCR:")
        print("  brew install tesseract")
        print("\nThen install Python dependencies:")
        print("  pip install -r requirements.txt")
        print("=" * 60)
        sys.exit(1)
    
    try:
        # Initialize extractor
        extractor = SAPDocumentExtractor()
        
        # Extract data
        parsed_data = extractor.extract_from_image(image_path)
        
        # Save to JSON
        output_path = extractor.save_json(parsed_data)
        print(f"\n✓ Saved JSON to: {output_path}")
        
        # Print summary
        extractor.print_summary(parsed_data)
        
        # Print JSON to console
        print("\nJSON Output:")
        print("-" * 60)
        print(json.dumps(parsed_data, indent=2))
        print("-" * 60)
        
        print("\n✓ Processing complete!")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
