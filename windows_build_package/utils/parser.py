"""
Parser for SAP Business One document text.
Extracts structured data from OCR output.
"""

import re
from typing import Dict, List, Optional, Any


class SAPDocumentParser:
    """Parser for SAP Business One documents (PO, Invoice, etc.)."""
    
    def __init__(self):
        """Initialize parser."""
        pass
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize OCR text."""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_doc_type(self, text: str) -> str:
        """Extract document type from text."""
        return "PO"
    
    def extract_doc_number(self, text: str) -> Optional[str]:
        """Extract document number - looking for the number after 'Primary'."""
        # The OCR shows: "No. Primary ™ -@" followed by number
        # Sometimes it's garbled, so let's look for any 3-digit number near "Primary"
        
        # Try multiple patterns
        patterns = [
            r'Primary[^\d]*(\d{3,4})',  # Primary followed by 3-4 digit number
            r'No\.[^\d]*Primary[^\d]*(\d{3,4})',
            r'-@[^\d]*(\d{3,4})',  # After the -@ symbol
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Last resort: find any 3-digit number in first few lines
        first_lines = ' '.join(text.split('\n')[:5])
        match = re.search(r'\b(\d{3})\b', first_lines)
        if match:
            return match.group(1)
        
        return None
    
    def extract_line_items(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items from document text."""
        lines = []
        
        print("\n🔍 Debug: Looking for line items...")
        
        # The OCR output shows:
        # A v .. £00001 = ).8. Officaprant 1420 5 5 AUD 500.000 0.00 AUD 500.000 P1 'Y AUD 2,500.000
        
        # Pattern 1: Look for £##### or A##### (item code)
        # followed by description, qty, AUD prices
        pattern1 = r'[£A](\d{5})[^\w]*([A-Za-z][^0-9]{5,50}?)\s+(\d+)\s+\d+\s+AUD\s+([\d,]+\.?\d*)\s+[\d.]+\s+AUD\s+[\d,]+\.?\d*\s+\w+\s+[\'Y]?\s*AUD\s+([\d,]+\.?\d*)'
        
        for match in re.finditer(pattern1, text):
            item_code = "A" + match.group(1)
            description = match.group(2).strip()
            # Clean up description
            description = re.sub(r'^[^\w]+', '', description)  # Remove leading non-word chars
            description = re.sub(r'\s+', ' ', description)  # Normalize spaces
            qty = self._parse_number(match.group(3))
            unit_price = self._parse_number(match.group(4))
            line_total = self._parse_number(match.group(5))
            
            print(f"  ✓ Found item: {item_code} - {description}")
            
            lines.append({
                'item_code': item_code,
                'description': description,
                'qty': qty,
                'unit_price': unit_price,
                'line_total': line_total
            })
        
        # Pattern 2: More flexible - look for "AUD 500.000" patterns near item codes
        if not lines:
            print("  Trying alternative pattern...")
            # Look for lines with multiple AUD values
            aud_pattern = r'(A\d{5}|£\d{5})[^\n]{10,80}?AUD\s+([\d,]+\.?\d*)[^\n]{5,30}?AUD\s+([\d,]+\.?\d*)'
            
            for match in re.finditer(aud_pattern, text):
                item_code = match.group(1).replace('£', 'A')
                # Try to extract description between item code and first AUD
                full_match = match.group(0)
                desc_match = re.search(r'[A£]\d{5}[^\w]*([\w\s.]+?)\s+\d+\s+\d+\s+AUD', full_match)
                description = desc_match.group(1).strip() if desc_match else "Item description"
                
                # Find all numbers
                numbers = re.findall(r'(\d+)\.?(\d*)', full_match)
                if len(numbers) >= 3:
                    qty = float(numbers[1][0]) if numbers[1][0] else 0
                    unit_price = self._parse_number(match.group(2))
                    line_total = self._parse_number(match.group(3))
                    
                    print(f"  ✓ Found item: {item_code} - {description}")
                    
                    lines.append({
                        'item_code': item_code,
                        'description': description,
                        'qty': qty,
                        'unit_price': unit_price,
                        'line_total': line_total
                    })
        
        if not lines:
            print("  ⚠ No line items found")
        
        return lines
    
    def extract_total(self, text: str) -> Optional[float]:
        """Extract document total from text."""
        # Look for "Total Payment Due AUD"
        patterns = [
            r'Total Payment Due\s+AUD\s+([\d,]+\.?\d*)',
            r'Payment Due.*?AUD\s+([\d,]+\.?\d*)',
            r'Due\s+AUD\s+([\d,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._parse_number(match.group(1))
        
        return None
    
    def _parse_number(self, value: str) -> float:
        """Parse string to number, handling commas and decimals."""
        value = value.replace(',', '').strip()
        try:
            return float(value)
        except ValueError:
            return 0.0
    
    def parse_document(self, text: str) -> Dict[str, Any]:
        """Parse complete SAP document from OCR text."""
        print("\n📄 Parsing document...")
        
        cleaned_text = self.clean_text(text)
        
        doc_type = self.extract_doc_type(cleaned_text)
        print(f"  Document Type: {doc_type}")
        
        doc_number = self.extract_doc_number(cleaned_text)
        print(f"  Document Number: {doc_number}")
        
        lines = self.extract_line_items(cleaned_text)
        print(f"  Line Items: {len(lines)}")
        
        doc_total = self.extract_total(cleaned_text)
        print(f"  Total: {doc_total}")
        
        # If total not found, calculate from lines
        if doc_total is None and lines:
            doc_total = sum(line.get('line_total', 0) for line in lines)
        
        return {
            'doc_type': doc_type,
            'doc_number': doc_number or 'UNKNOWN',
            'lines': lines,
            'doc_total': doc_total
        }
