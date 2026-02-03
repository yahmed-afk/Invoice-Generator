#!/usr/bin/env python3
"""
Invoice Generator - Web Application
Upload a PO screenshot and download the generated PDF invoice.
"""

import os
import sys
from pathlib import Path
from flask import Flask, render_template_string, request, send_file, jsonify
from werkzeug.utils import secure_filename

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_invoice import extract_po_data

# Import pdf_filler
import importlib.util
spec = importlib.util.spec_from_file_location('pdf_filler',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'pdf_filler.py'))
pdf_filler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdf_filler)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice Generator</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
        }
        h1 {
            color: #1a1a2e;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .upload-area {
            border: 3px dashed #ddd;
            border-radius: 15px;
            padding: 40px 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 20px;
        }
        .upload-area:hover, .upload-area.dragover {
            border-color: #4CAF50;
            background: #f8fff8;
        }
        .upload-area.has-file {
            border-color: #4CAF50;
            background: #f0fff0;
        }
        .upload-icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        .upload-text {
            color: #666;
            margin-bottom: 10px;
        }
        .upload-hint {
            color: #999;
            font-size: 12px;
        }
        .file-name {
            color: #4CAF50;
            font-weight: 600;
            margin-top: 10px;
            word-break: break-all;
        }
        input[type="file"] {
            display: none;
        }
        .btn {
            width: 100%;
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn-primary {
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
        }
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(76, 175, 80, 0.4);
        }
        .btn-primary:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .status {
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
        }
        .status.loading {
            display: block;
            background: #e3f2fd;
            color: #1976d2;
        }
        .status.success {
            display: block;
            background: #e8f5e9;
            color: #2e7d32;
        }
        .status.error {
            display: block;
            background: #ffebee;
            color: #c62828;
        }
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #1976d2;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .preview-img {
            max-width: 100%;
            max-height: 200px;
            margin-top: 15px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Invoice Generator</h1>
        <p class="subtitle">Upload a PO screenshot to generate a PDF invoice</p>

        <form id="uploadForm" enctype="multipart/form-data">
            <div class="upload-area" id="uploadArea">
                <div class="upload-icon">📄</div>
                <div class="upload-text">Drop your PO screenshot here</div>
                <div class="upload-hint">or click to browse (PNG, JPG)</div>
                <div class="file-name" id="fileName"></div>
                <img class="preview-img" id="previewImg" style="display:none;">
                <input type="file" id="fileInput" name="file" accept="image/*">
            </div>

            <button type="submit" class="btn btn-primary" id="submitBtn" disabled>
                Generate Invoice
            </button>
        </form>

        <div class="status" id="status"></div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const previewImg = document.getElementById('previewImg');
        const submitBtn = document.getElementById('submitBtn');
        const status = document.getElementById('status');
        const form = document.getElementById('uploadForm');

        // Click to upload
        uploadArea.addEventListener('click', () => fileInput.click());

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                handleFile(e.dataTransfer.files[0]);
            }
        });

        // File selected
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                handleFile(e.target.files[0]);
            }
        });

        function handleFile(file) {
            fileName.textContent = file.name;
            uploadArea.classList.add('has-file');
            submitBtn.disabled = false;

            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }

        // Form submit
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            submitBtn.disabled = true;
            status.className = 'status loading';
            status.innerHTML = '<span class="spinner"></span>Processing image with OCR...';

            try {
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = response.headers.get('X-Filename') || 'invoice.pdf';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();

                    status.className = 'status success';
                    status.textContent = '✓ Invoice generated and downloaded!';
                } else {
                    const error = await response.json();
                    throw new Error(error.error || 'Failed to generate invoice');
                }
            } catch (err) {
                status.className = 'status error';
                status.textContent = '✗ ' + err.message;
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use PNG or JPG.'}), 400

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Extract data from screenshot
        payload = extract_po_data(filepath)

        # Generate output path
        stem = Path(filename).stem
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{stem}_invoice.pdf")

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

        # Clean up uploaded file
        os.remove(filepath)

        # Send the PDF
        return send_file(
            output_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{invoice_number}.pdf'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*50)
    print("  Invoice Generator Web App")
    print("="*50)
    print("\n  Open in your browser:")
    print("  http://localhost:8080")
    print("\n  Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=8080)
