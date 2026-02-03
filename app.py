#!/usr/bin/env python3
"""
Invoice Generator - Hugging Face Spaces Version
"""

import os
import sys
from pathlib import Path
import gradio as gr

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_invoice import extract_po_data

# Import pdf_filler
import importlib.util
spec = importlib.util.spec_from_file_location('pdf_filler',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'pdf_filler.py'))
pdf_filler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_filler)

# Ensure folders exist
os.makedirs('uploads', exist_ok=True)
os.makedirs('output', exist_ok=True)

def generate_invoice(image):
    """Process uploaded image and generate PDF invoice."""
    if image is None:
        return None, "Please upload a PO screenshot"

    try:
        # Save uploaded image temporarily
        temp_path = "uploads/temp_po.png"
        image.save(temp_path)

        # Extract data from screenshot
        payload = extract_po_data(temp_path)

        # Generate output path
        output_path = "output/generated_invoice.pdf"

        # Get template path
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'templates',
            'blank template.pdf'
        )

        # Generate PDF
        invoice_number = pdf_filler.fill_invoice_template(
            payload,
            template_path,
            output_path
        )

        # Clean up
        os.remove(temp_path)

        return output_path, f"✅ Invoice {invoice_number} generated successfully!"

    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Invoice Generator", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 📄 Invoice Generator
    Upload a SAP B1 Purchase Order screenshot to generate a PDF invoice.
    """)

    with gr.Row():
        with gr.Column():
            input_image = gr.Image(type="pil", label="Upload PO Screenshot")
            generate_btn = gr.Button("Generate Invoice", variant="primary")

        with gr.Column():
            output_file = gr.File(label="Download Invoice PDF")
            status = gr.Textbox(label="Status", interactive=False)

    generate_btn.click(
        fn=generate_invoice,
        inputs=[input_image],
        outputs=[output_file, status]
    )

    gr.Markdown("""
    ---
    **Instructions:**
    1. Upload a PO screenshot (PNG or JPG)
    2. Click "Generate Invoice"
    3. Download the generated PDF
    """)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
