"""
OCR Engine for SAP Business One screenshot processing.
Handles image preprocessing and text extraction.
"""

import cv2
import numpy as np
from PIL import Image
import pytesseract
from typing import Optional


class OCREngine:
    """OCR engine with preprocessing capabilities for better text extraction."""
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize OCR engine.
        
        Args:
            tesseract_cmd: Path to tesseract executable (auto-detected if None)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """
        Preprocess image for better OCR results.
        
        Args:
            image_path: Path to input image
            
        Returns:
            Preprocessed image as numpy array
        """
        # Read image
        img = cv2.imread(image_path)
        
        if img is None:
            raise ValueError(f"Could not read image from {image_path}")
        
        # Resize image to improve OCR (scale up by 2x)
        height, width = img.shape[:2]
        img = cv2.resize(img, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges sharp
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Apply OTSU thresholding
        _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh
    
    def extract_text(self, image_path: str, preprocess: bool = True) -> str:
        """
        Extract text from image using OCR.

        Args:
            image_path: Path to input image
            preprocess: Whether to preprocess image

        Returns:
            Extracted text as string
        """
        try:
            # Try both preprocessed and original image
            results = []

            # Original image (sometimes preserves more detail)
            pil_img_orig = Image.open(image_path)

            # Preprocessed image
            if preprocess:
                processed_img = self.preprocess_image(image_path)
                pil_img_processed = Image.fromarray(processed_img)
            else:
                pil_img_processed = pil_img_orig

            # Try multiple OCR configurations on both images
            configs = [
                r'--oem 3 --psm 6',   # Uniform block of text
                r'--oem 3 --psm 4',   # Single column
                r'--oem 3 --psm 3',   # Fully automatic page segmentation
            ]

            for pil_img in [pil_img_orig, pil_img_processed]:
                for config in configs:
                    text = pytesseract.image_to_string(pil_img, config=config)
                    results.append(text)

            # Combine results - use the longest one as base but merge unique content
            results.sort(key=len, reverse=True)
            best_text = results[0] if results else ""

            return best_text

        except Exception as e:
            raise RuntimeError(f"OCR extraction failed: {str(e)}")
    
    def extract_text_with_boxes(self, image_path: str, preprocess: bool = True) -> dict:
        """
        Extract text with bounding box information for structured parsing.
        
        Args:
            image_path: Path to input image
            preprocess: Whether to preprocess image
            
        Returns:
            Dictionary containing text and bounding box data
        """
        try:
            if preprocess:
                processed_img = self.preprocess_image(image_path)
                pil_img = Image.fromarray(processed_img)
            else:
                pil_img = Image.open(image_path)
            
            # Get detailed OCR data
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            
            return data
            
        except Exception as e:
            raise RuntimeError(f"OCR extraction with boxes failed: {str(e)}")
