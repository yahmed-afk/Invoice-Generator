#!/usr/bin/env python3
"""
Invoice Generator for SAP Business One
Extracts data from SAP PO screenshot and generates a professional invoice PDF.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from utils.ocr_engine import OCREngine
from utils.parser import SAPDocumentParser


class InvoiceGenerator:
    """Generate professional invoices from SAP data."""
    
    def __init__(self, output_dir: str = "output"):
        """Initialize invoice generator."""
        self.ocr_engine = OCREngine()
        self.parser = SAPDocumentParser()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        
    def extract_data_from_screenshot(self, image_path: str) -> Dict[str, Any]:
        """Extract data from SAP screenshot."""
        print(f"📸 Processing screenshot: {image_path}")
        
        # Perform OCR
        raw_text = self.ocr_engine.extract_text(image_path, preprocess=True)
        
        # Parse document
        parsed_data = self.parser.parse_document(raw_text)
        
        print(f"✓ Extracted PO #{parsed_data['doc_number']}")
        print(f"✓ Found {len(parsed_data['lines'])} line items")
        
        return parsed_data
    
    def generate_invoice_pdf(self, data: Dict[str, Any], output_filename: str = None) -> str:
        """
        Generate invoice PDF from extracted data.
        
        Args:
            data: Parsed SAP data
            output_filename: Output PDF filename
            
        Returns:
            Path to generated PDF
        """
        if output_filename is None:
            invoice_number = f"COL{datetime.now().strftime('%Y%m%d%H%M')}"
            output_filename = f"invoice_{invoice_number}.pdf"
        
        output_path = self.output_dir / output_filename
        
        # Create PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        # Container for PDF elements
        elements = []
        
        # Invoice header
        invoice_number = f"COL{datetime.now().strftime('%Y%m%d%H%M')}"
        po_number = data.get('doc_number', 'N/A')
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#000000'),
            spaceAfter=30,
            alignment=TA_LEFT
        )
        elements.append(Paragraph("Invoice", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Header info table (2 columns)
        today = datetime.now().strftime('%m/%d/%y')
        
        header_data = [
            ['SHIP TO:', f'Invoice #: {invoice_number}'],
            ['Acme Associates', f'PO #: {po_number}'],
            ['Address: 600 EASTERN WAY', f'DATE: {today}'],
            ['BRISBANE QLD 4003', f'INVOICE DUE DATE: {today}'],
            ['AUSTRALIA', ''],
        ]
        
        header_table = Table(header_data, colWidths=[4*inch, 2.5*inch])
        header_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(header_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Items section
        elements.append(Paragraph("<b>ITEMS</b>", self.styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Items table
        items_data = [
            ['DESCRIPTION', 'QUANTITY', 'PRICE', 'TAX', 'Line Total']
        ]
        
        for line in data['lines']:
            items_data.append([
                f"{line['item_code']} {line['description']}",
                str(int(line['qty'])),
                f"AUD {line['unit_price']:.2f}",
                'P1',
                f"AUD {line['line_total']:.3f}"
            ])
        
        items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1*inch, 0.7*inch, 1*inch])
        items_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F0F0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            
            # Borders
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
            
            # Alignment
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(items_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Calculate totals
        subtotal = sum(line['line_total'] for line in data['lines'])
        tax = data.get('doc_total', subtotal * 1.1) - subtotal
        total = data.get('doc_total', subtotal + tax)
        
        # Totals section
        totals_data = [
            ['Total Before Discount:', f'AUD {subtotal:.2f}'],
            ['Discount:', '%'],
            ['Freight:', ''],
            ['Tax:', f'AUD {tax:.2f}'],
            ['Total Payment Due:', f'AUD {total:.2f}'],
        ]
        
        totals_table = Table(totals_data, colWidths=[4.5*inch, 2*inch])
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, -1), (-1, -1), 10),
        ]))
        
        elements.append(totals_table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
        
        elements.append(Paragraph(
            "This invoice was generated with the help of Wave Financial Inc.<br/>"
            "To learn more, and create your own free account visit waveapps.com",
            footer_style
        ))
        
        # Build PDF
        doc.build(elements)
        
        return str(output_path)


def main():
    """Main entry point."""
    
    if len(sys.argv) != 2:
        print("Usage: python invoice_generator.py <sap_screenshot_path>")
        print("\nExample:")
        print("  python invoice_generator.py input/sap_po.png")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        sys.exit(1)
    
    try:
        generator = InvoiceGenerator()
        
        # Extract data from screenshot
        data = generator.extract_data_from_screenshot(image_path)
        
        # Generate invoice PDF
        print("\n📄 Generating invoice PDF...")
        pdf_path = generator.generate_invoice_pdf(data)
        
        print(f"✓ Invoice generated: {pdf_path}")
        print("\n🎉 Done!")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
