#!/usr/bin/env python3
"""
Interactive Invoice Generator
Allows manual verification of extracted data before generating invoice.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER


def get_manual_data():
    """Get data from user input."""
    print("\n" + "="*60)
    print("MANUAL DATA ENTRY")
    print("="*60)
    print("Enter the data from your SAP screenshot:")
    print()
    
    doc_number = input("PO Number (e.g., 790): ").strip()
    
    lines = []
    print("\nEnter line items (press Enter with empty item code when done):")
    
    line_num = 1
    while True:
        print(f"\n--- Line Item #{line_num} ---")
        item_code = input("  Item Code (e.g., A00001): ").strip()
        
        if not item_code:
            break
        
        description = input("  Description: ").strip()
        qty = float(input("  Quantity: ").strip())
        unit_price = float(input("  Unit Price (AUD): ").strip())
        line_total = qty * unit_price
        
        lines.append({
            'item_code': item_code,
            'description': description,
            'qty': qty,
            'unit_price': unit_price,
            'line_total': line_total
        })
        
        line_num += 1
    
    subtotal = sum(line['line_total'] for line in lines)
    tax = float(input(f"\nTax Amount (AUD) [calculated: {subtotal * 0.1:.2f}]: ").strip() or subtotal * 0.1)
    total = subtotal + tax
    
    return {
        'doc_type': 'PO',
        'doc_number': doc_number,
        'lines': lines,
        'doc_total': total,
        'tax': tax,
        'subtotal': subtotal
    }


def generate_invoice_pdf(data: dict, output_dir: str = "output") -> str:
    """Generate professional invoice PDF."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    invoice_number = f"COL{datetime.now().strftime('%Y%m%d%H%M%S')}"
    pdf_file = output_path / f"invoice_{invoice_number}.pdf"
    
    doc = SimpleDocTemplate(
        str(pdf_file),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=colors.black,
        spaceAfter=20
    )
    elements.append(Paragraph("Invoice", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Header
    today = datetime.now().strftime('%m/%d/%y')
    header_data = [
        ['SHIP TO:', f'PO #'],
        ['Acme Associates', data['doc_number']],
        ['600 EASTERN WAY', ''],
        ['BRISBANE QLD 4003', f'DATE'],
        ['AUSTRALIA', today],
        ['', f'GRPO #'],
        ['', '9071'],
        ['', f'Invoice#'],
        ['', invoice_number],
        ['', f'INVOICE DUE DATE'],
        ['', today],
    ]
    
    header_table = Table(header_data, colWidths=[4*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Items header
    elements.append(Paragraph("<b>ITEMS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    # Items table
    items_data = [['DESCRIPTION', 'QUANTITY', 'PRICE', 'TAX', 'Line Total']]
    
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Totals
    subtotal = data['subtotal']
    tax = data.get('tax', 0)
    total = data['doc_total']
    
    totals_data = [
        ['', '', '', 'Total Before Discount:', f'AUD {subtotal:.2f}'],
        ['', '', '', 'Discount:', '%'],
        ['', '', '', 'Freight:', ''],
        ['', '', '', 'Tax:', f'AUD {tax:.2f}'],
        ['', '', '', 'Total Payment Due:', f'AUD {total:.2f}'],
    ]
    
    totals_table = Table(totals_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1.7*inch, 1.3*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('LINEABOVE', (3, -1), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(totals_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer = Paragraph(
        "This invoice was generated with the help of Wave Financial Inc.<br/>"
        "To learn more, and create your own free account visit waveapps.com",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    )
    elements.append(footer)
    
    doc.build(elements)
    
    return str(pdf_file)


def main():
    print("="*60)
    print("INVOICE GENERATOR - Interactive Mode")
    print("="*60)
    
    # Get data manually
    data = get_manual_data()
    
    # Show summary
    print("\n" + "="*60)
    print("DATA SUMMARY:")
    print("="*60)
    print(json.dumps(data, indent=2))
    
    confirm = input("\nGenerate invoice with this data? (y/n): ").strip().lower()
    
    if confirm == 'y':
        pdf_path = generate_invoice_pdf(data)
        print(f"\n✓ Invoice generated: {pdf_path}")
        print("🎉 Done!")
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
