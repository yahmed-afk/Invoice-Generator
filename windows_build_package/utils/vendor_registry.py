"""
Vendor Registry - Functions for vendor key normalization and config loading.
"""

import re
import json
from pathlib import Path
from typing import Dict, Optional


def normalize_vendor_key(vendor_name: str) -> str:
    """
    Convert vendor display name to a normalized key.

    Examples:
        "Acme Associates" -> "acme_associates"
        "ABC Corp, Inc." -> "abc_corp_inc"

    Args:
        vendor_name: The vendor's display name

    Returns:
        Normalized vendor key (lowercase, underscores, alphanumeric only)
    """
    if not vendor_name:
        return "unknown_vendor"

    s = vendor_name.strip().lower()
    # Remove special characters except spaces
    s = re.sub(r'[^a-z0-9\s]+', '', s)
    # Replace spaces with underscores
    s = re.sub(r'\s+', '_', s)
    # Remove consecutive underscores
    s = re.sub(r'_+', '_', s)
    # Remove leading/trailing underscores
    s = s.strip('_')

    return s or "unknown_vendor"


def load_vendor_config(vendor_key: str, registry_path: str = "utils/vendors.json") -> dict:
    """
    Load vendor configuration from the registry.

    Args:
        vendor_key: Normalized vendor key (e.g., "acme_associates")
        registry_path: Path to vendors.json file

    Returns:
        Vendor configuration dict with template_path, mapping_path, etc.

    Raises:
        KeyError: If vendor_key not found in registry
        FileNotFoundError: If registry file doesn't exist
    """
    registry_file = Path(registry_path)
    if not registry_file.exists():
        raise FileNotFoundError(f"Vendor registry not found: {registry_path}")

    registry = json.loads(registry_file.read_text(encoding="utf-8"))

    if vendor_key not in registry:
        available = list(registry.keys())
        raise KeyError(
            f"Vendor key '{vendor_key}' not found in registry. "
            f"Available vendors: {available}"
        )

    return registry[vendor_key]


def get_all_vendors(registry_path: str = "utils/vendors.json") -> Dict[str, dict]:
    """
    Load all vendor configurations.

    Args:
        registry_path: Path to vendors.json file

    Returns:
        Dict mapping vendor_key -> config
    """
    registry_file = Path(registry_path)
    if not registry_file.exists():
        return {}

    return json.loads(registry_file.read_text(encoding="utf-8"))


def find_vendor_by_name(vendor_name: str, registry_path: str = "utils/vendors.json") -> Optional[str]:
    """
    Find vendor key by matching display name.

    Args:
        vendor_name: Vendor name to search for
        registry_path: Path to vendors.json

    Returns:
        Matching vendor_key or None if not found
    """
    registry = get_all_vendors(registry_path)
    normalized = normalize_vendor_key(vendor_name)

    # Direct match
    if normalized in registry:
        return normalized

    # Try matching by display_name
    for key, config in registry.items():
        display = config.get("display_name", "")
        if normalize_vendor_key(display) == normalized:
            return key

    # Fuzzy match - try to find close matches (OCR often misreads characters)
    for key in registry.keys():
        if _fuzzy_match(normalized, key):
            return key

    return None


def _fuzzy_match(s1: str, s2: str, threshold: float = 0.8) -> bool:
    """
    Check if two strings are similar enough (handles OCR errors).
    Uses simple character-based similarity.
    """
    if not s1 or not s2:
        return False

    # Quick check for substring
    if s1 in s2 or s2 in s1:
        return True

    # Character-level similarity (Jaccard-like)
    set1 = set(s1.lower())
    set2 = set(s2.lower())
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return False

    similarity = intersection / union
    return similarity >= threshold
