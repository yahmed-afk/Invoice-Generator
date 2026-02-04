#!/usr/bin/env python3
"""
Invoice Generator - Simple Clean UI
"""

import os
import sys
import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_invoice import extract_po_data

import importlib.util
spec = importlib.util.spec_from_file_location('pdf_filler',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'pdf_filler.py'))
pdf_filler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_filler)

os.makedirs('uploads', exist_ok=True)
os.makedirs('output', exist_ok=True)

def generate_invoice(image):
    if image is None:
        raise gr.Error("Please upload a PO screenshot first")

    try:
        temp_path = "uploads/temp_po.png"
        image.save(temp_path)

        # Debug: Check if tesseract is available
        import subprocess
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
            print(f"Tesseract version: {result.stdout[:100]}")
        except Exception as te:
            print(f"Tesseract check failed: {te}")

        payload = extract_po_data(temp_path)

        # Debug: Print extracted data
        print(f"Extracted payload: {payload}")

        output_path = "output/generated_invoice.pdf"

        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'templates',
            'blank template.pdf'
        )

        invoice_number = pdf_filler.fill_invoice_template(
            payload,
            template_path,
            output_path
        )

        os.remove(temp_path)

        return output_path

    except Exception as e:
        import traceback
        print(f"Error: {traceback.format_exc()}")
        raise gr.Error(f"Failed to generate invoice: {str(e)}")

css = """
.gradio-container {
    max-width: 600px !important;
    margin: auto !important;
}
h1 {
    text-align: center;
    color: #2c3e50;
    margin-bottom: 0.5em;
}
.subtitle {
    text-align: center;
    color: #7f8c8d;
    margin-bottom: 2em;
}
"""

with gr.Blocks(css=css, title="Invoice Generator") as demo:
    gr.HTML("<h1>Invoice Generator</h1>")
    gr.HTML("<p class='subtitle'>Upload a PO screenshot to generate a PDF invoice</p>")

    with gr.Column():
        input_image = gr.Image(
            type="pil",
            label="Drop your PO screenshot here or click to browse",
            height=250
        )

        generate_btn = gr.Button(
            "Generate Invoice",
            variant="primary",
            size="lg"
        )

        output_file = gr.File(label="Your Invoice")

    generate_btn.click(
        fn=generate_invoice,
        inputs=[input_image],
        outputs=[output_file]
    )

if __name__ == "__main__":
    demo.launch()
