FROM python:3.11-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements_web.txt .
RUN pip install --no-cache-dir -r requirements_web.txt

# Copy app files
COPY web_app.py .
COPY generate_invoice.py .
COPY utils/ utils/
COPY templates/ templates/

# Create output directory
RUN mkdir -p output uploads

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "web_app:app", "--bind", "0.0.0.0:8080"]
