"""
Smoke test for PO extractor.
Verifies that extraction produces required fields from a sample screenshot.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from utils.po_extractor import extract_po_from_image
from utils.vendor_registry import normalize_vendor_key


SAMPLE_IMAGE = Path("input/po.png")


@pytest.fixture
def extracted_data():
    """Extract data from sample PO image."""
    if not SAMPLE_IMAGE.exists():
        pytest.skip(f"Sample image not found: {SAMPLE_IMAGE}")
    return extract_po_from_image(str(SAMPLE_IMAGE))


class TestExtractorSmoke:
    """Smoke tests for PO extractor."""

    def test_returns_dict(self, extracted_data):
        """Extraction returns a dictionary."""
        assert isinstance(extracted_data, dict)

    def test_has_header(self, extracted_data):
        """Result contains header section."""
        assert "header" in extracted_data
        assert isinstance(extracted_data["header"], dict)

    def test_header_has_required_fields(self, extracted_data):
        """Header contains required fields."""
        header = extracted_data["header"]
        required = ["vendor_name", "po_number", "posting_date"]
        for field in required:
            assert field in header, f"Missing header field: {field}"

    def test_has_line_items(self, extracted_data):
        """Result contains line_items array."""
        assert "line_items" in extracted_data
        assert isinstance(extracted_data["line_items"], list)

    def test_line_items_have_required_fields(self, extracted_data):
        """Each line item has required fields."""
        items = extracted_data["line_items"]
        if not items:
            pytest.skip("No line items extracted")

        required = ["item_no", "description", "quantity", "unit_price", "line_total"]
        for i, item in enumerate(items):
            for field in required:
                assert field in item, f"Line item {i} missing field: {field}"

    def test_unit_price_is_money_object(self, extracted_data):
        """unit_price is a money object with currency and amount."""
        items = extracted_data["line_items"]
        if not items:
            pytest.skip("No line items extracted")

        for i, item in enumerate(items):
            up = item.get("unit_price")
            assert isinstance(up, dict), f"Line {i}: unit_price should be dict"
            assert "currency" in up, f"Line {i}: unit_price missing currency"
            assert "amount" in up, f"Line {i}: unit_price missing amount"

    def test_has_totals(self, extracted_data):
        """Result contains totals section."""
        assert "totals" in extracted_data
        assert isinstance(extracted_data["totals"], dict)

    def test_totals_has_required_fields(self, extracted_data):
        """Totals contains required fields."""
        totals = extracted_data["totals"]
        required = ["total_before_discount", "total_payment_due"]
        for field in required:
            assert field in totals, f"Missing totals field: {field}"


class TestVendorRegistry:
    """Tests for vendor registry functions."""

    def test_normalize_vendor_key_basic(self):
        """Basic vendor key normalization."""
        assert normalize_vendor_key("Acme Associates") == "acme_associates"
        assert normalize_vendor_key("ABC Corp, Inc.") == "abc_corp_inc"

    def test_normalize_vendor_key_special_chars(self):
        """Handles special characters."""
        assert normalize_vendor_key("Test & Co.") == "test_co"
        assert normalize_vendor_key("O'Brien's Shop") == "obriens_shop"

    def test_normalize_vendor_key_empty(self):
        """Handles empty/None input."""
        assert normalize_vendor_key("") == "unknown_vendor"
        assert normalize_vendor_key(None) == "unknown_vendor"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
