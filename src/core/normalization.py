"""
Entity resolution and fingerprinting for de-duplication.
PRIORITY: P0 - Critical for preventing duplicate leads.
"""

import hashlib
import re
from typing import Dict, Optional, Tuple


def compute_fingerprint(business: Dict) -> str:
    """
    Compute stable fingerprint for business de-duplication.

    Combines:
    - Normalized name (strip Inc/Ltd/Corp, lowercase, no punct)
    - Street number + normalized street name
    - City + postal first 3 chars
    - Phone digits (if available)

    Returns: SHA256 hash (first 16 chars for readability)
    """
    # Normalize name
    name = business.get('name', '').lower()
    name = re.sub(r'\b(inc|ltd|corp|incorporated|limited|corporation|llc)\b', '', name)
    name = re.sub(r'[^\w\s]', '', name).strip()

    # Normalize street
    street = business.get('street', '').lower()
    street = re.sub(r'\b(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd|lane|ln)\b', '', street)
    street = re.sub(r'[^\w\s\d]', '', street).strip()

    # Extract street number
    street_match = re.match(r'^(\d+)', street)
    street_num = street_match.group(1) if street_match else ''

    # City + postal prefix
    city = business.get('city', '').lower().strip()
    postal_raw = business.get('postal_code', '') or ''  # Handle None
    postal = postal_raw.upper().replace(' ', '')[:3] if postal_raw else ''

    # Phone digits only
    phone = business.get('phone', '')
    phone_digits = re.sub(r'\D', '', phone)[-10:] if phone else ''  # Last 10 digits

    # Combine components
    components = [name, street_num, street, city, postal, phone_digits]
    fingerprint_str = '|'.join(c for c in components if c)

    # Hash
    hash_obj = hashlib.sha256(fingerprint_str.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def normalize_name(name: str) -> str:
    """Normalize business name for comparison."""
    if not name:
        return ''

    name = name.lower()
    # Remove common suffixes
    name = re.sub(r'\b(inc|ltd|corp|incorporated|limited|corporation|llc|co)\b\.?', '', name)
    # Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)
    # Normalize whitespace
    return ' '.join(name.split())


def normalize_address(address: str) -> Dict[str, str]:
    """
    Parse and normalize address into components.
    Returns: {normalized, original}
    """
    if not address:
        return {'normalized': '', 'original': ''}

    normalized = address.lower().strip()

    # Expand common abbreviations
    abbreviations = {
        r'\bst\b\.?': 'street',
        r'\bave\b\.?': 'avenue',
        r'\brd\b\.?': 'road',
        r'\bdr\b\.?': 'drive',
        r'\bblvd\b\.?': 'boulevard',
        r'\bln\b\.?': 'lane',
        r'\bct\b\.?': 'court',
        r'\bpl\b\.?': 'place',
        r'\bpkwy\b\.?': 'parkway',
        r'\bapt\b\.?': 'apartment',
        r'\bste\b\.?': 'suite',
        r'\bunit\b\.?': 'unit',
    }

    for abbrev, full in abbreviations.items():
        normalized = re.sub(abbrev, full, normalized, flags=re.IGNORECASE)

    # Remove punctuation except spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return {
        'normalized': normalized,
        'original': address
    }


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to digits only.
    Returns: Last 10 digits (North American format)
    """
    if not phone:
        return ''

    # Extract digits only
    digits = re.sub(r'\D', '', phone)

    # Return last 10 digits (strip country code if present)
    return digits[-10:] if len(digits) >= 10 else digits


def normalize_postal_code(postal: str) -> str:
    """
    Normalize Canadian postal code.
    Returns: Uppercase, no spaces (e.g., L8H3R2)
    """
    if not postal:
        return ''

    postal = postal.upper().replace(' ', '').strip()

    # Validate format (Canadian: A1A1A1)
    if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal):
        return postal

    return postal


def normalize_website(url: str) -> str:
    """
    Normalize website URL for comparison.
    Returns: lowercase domain without protocol or www
    """
    if not url:
        return ''

    url = url.lower().strip()

    # Remove protocol
    url = re.sub(r'^https?://', '', url)
    # Remove www
    url = re.sub(r'^www\.', '', url)
    # Remove trailing slash
    url = url.rstrip('/')
    # Extract domain only (remove path)
    domain_match = re.match(r'^([^/]+)', url)

    return domain_match.group(1) if domain_match else url


def normalize_value(value: str, field: str) -> str:
    """
    Normalize values for comparison based on field type.

    Args:
        value: The value to normalize
        field: Field type (phone, postal_code, address, etc.)

    Returns:
        Normalized value
    """
    if not value:
        return ''

    if field == 'phone':
        return normalize_phone(value)
    elif field == 'postal_code':
        return normalize_postal_code(value)
    elif field == 'address':
        return normalize_address(value)['normalized']
    elif field == 'website':
        return normalize_website(value)
    elif field == 'name':
        return normalize_name(value)
    else:
        # Generic normalization
        return value.strip().lower()


def compare_addresses(addr1: str, addr2: str) -> Tuple[bool, float]:
    """
    Compare two addresses for similarity.

    Returns: (is_match, confidence_score)
    """
    if not addr1 or not addr2:
        return False, 0.0

    norm1 = normalize_address(addr1)['normalized']
    norm2 = normalize_address(addr2)['normalized']

    # Exact match
    if norm1 == norm2:
        return True, 1.0

    # Extract street number for both
    num1 = re.match(r'^(\d+)', norm1)
    num2 = re.match(r'^(\d+)', norm2)

    # If street numbers don't match, likely different addresses
    if num1 and num2 and num1.group(1) != num2.group(1):
        return False, 0.0

    # Calculate token overlap
    tokens1 = set(norm1.split())
    tokens2 = set(norm2.split())

    if not tokens1 or not tokens2:
        return False, 0.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)

    jaccard_similarity = len(intersection) / len(union)

    # Consider match if similarity > 0.7
    is_match = jaccard_similarity > 0.7

    return is_match, jaccard_similarity


def extract_street_number(address: str) -> Optional[str]:
    """Extract street number from address."""
    if not address:
        return None

    match = re.match(r'^(\d+)', address.strip())
    return match.group(1) if match else None
