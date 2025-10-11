"""
Business entity fingerprinting for deduplication across data sources.
PRIORITY: P0 - Critical for preventing duplicate leads from multiple sources.

This module provides fingerprinting specifically for businesses discovered from
Yellow Pages, Hamilton Chamber, and Canadian Importers sources.
"""

import hashlib
import re
from typing import Dict, Optional
import structlog

logger = structlog.get_logger(__name__)


def compute_business_fingerprint(
    name: str,
    street: Optional[str] = None,
    city: Optional[str] = None,
    postal: Optional[str] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None
) -> str:
    """
    Compute stable fingerprint for business deduplication.

    Creates a SHA256 hash from normalized business attributes to detect
    duplicates across different data sources (Yellow Pages, Chamber, Importers).

    Args:
        name: Business name (required)
        street: Street address
        city: City name
        postal: Postal code
        phone: Phone number
        website: Website URL

    Returns:
        16-character hex string (first 16 chars of SHA256 hash)

    Examples:
        >>> compute_business_fingerprint("ABC Manufacturing Inc.", "123 Main St", "Hamilton")
        'a3f5d9e2c8b1a4f6'

        >>> # Same business with different formatting
        >>> compute_business_fingerprint("ABC Manufacturing", "123 Main Street", "Hamilton")
        'a3f5d9e2c8b1a4f6'  # Same fingerprint!
    """
    components = []

    # 1. Normalize business name
    if name:
        norm_name = _normalize_name(name)
        components.append(norm_name)
    else:
        logger.warning("fingerprint_missing_name",
                      street=street, city=city, postal=postal)
        components.append("")

    # 2. Normalize street address
    if street:
        norm_street = _normalize_street(street)
        # Extract street number for stronger matching
        street_num = _extract_street_number(street)
        components.append(street_num or "")
        components.append(norm_street)
    else:
        components.extend(["", ""])

    # 3. Normalize city
    if city:
        norm_city = city.lower().strip()
        components.append(norm_city)
    else:
        components.append("")

    # 4. Normalize postal code (first 3 chars)
    if postal:
        norm_postal = postal.upper().replace(" ", "")[:3]
        components.append(norm_postal)
    else:
        components.append("")

    # 5. Normalize phone (last 10 digits)
    if phone:
        phone_digits = re.sub(r'\D', '', phone)
        norm_phone = phone_digits[-10:] if len(phone_digits) >= 10 else phone_digits
        components.append(norm_phone)
    else:
        components.append("")

    # 6. Normalize website domain
    if website:
        norm_website = _normalize_website(website)
        components.append(norm_website)
    else:
        components.append("")

    # Combine and hash
    fingerprint_str = '|'.join(components)
    hash_obj = hashlib.sha256(fingerprint_str.encode('utf-8'))
    fingerprint = hash_obj.hexdigest()[:16]

    logger.debug("fingerprint_computed",
                name=name[:30] if name else None,
                fingerprint=fingerprint,
                components_used=sum(1 for c in components if c))

    return fingerprint


def _normalize_name(name: str) -> str:
    """
    Normalize business name for comparison.

    Removes:
    - Common suffixes (Inc, Ltd, Corp, LLC, Co)
    - Punctuation
    - Extra whitespace

    Examples:
        >>> _normalize_name("ABC Manufacturing Inc.")
        'abc manufacturing'
        >>> _normalize_name("ABC Mfg. Ltd")
        'abc mfg'
    """
    if not name:
        return ""

    name = name.lower()

    # Remove common legal suffixes (more comprehensive list)
    suffixes = [
        'inc', 'ltd', 'limited', 'corp', 'corporation', 'llc',
        'incorporated', 'co', 'company', 'enterprises', 'ent',
        'group', 'holding', 'holdings', 'international', 'intl'
    ]
    for suffix in suffixes:
        # Match whole words with optional period and 's' for plural
        pattern = r'\b' + suffix + r's?\.?\b'
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove '&' and 'and'
    name = name.replace(' and ', ' ').replace(' & ', ' ')

    # Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)

    # Normalize whitespace
    name = ' '.join(name.split())

    return name.strip()


def _normalize_street(street: str) -> str:
    """
    Normalize street name for comparison.

    Removes:
    - Street type abbreviations (St, Ave, Rd, etc.)
    - Directional indicators (E, W, N, S)
    - Punctuation
    - Unit/suite numbers

    Examples:
        >>> _normalize_street("123 Main St E")
        'main'
        >>> _normalize_street("123 Main Street East Unit 5")
        'main'
    """
    if not street:
        return ""

    street = street.lower()

    # Remove street type abbreviations
    street_types = [
        'street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr',
        'boulevard', 'blvd', 'lane', 'ln', 'court', 'ct', 'crt',
        'place', 'pl', 'terrace', 'terr', 'parkway', 'pkwy', 'way'
    ]
    for street_type in street_types:
        pattern = r'\b' + street_type + r'\.?\b'
        street = re.sub(pattern, '', street, flags=re.IGNORECASE)

    # Remove directional indicators
    directions = ['east', 'west', 'north', 'south', 'e', 'w', 'n', 's']
    for direction in directions:
        pattern = r'\b' + direction + r'\.?\b'
        street = re.sub(pattern, '', street, flags=re.IGNORECASE)

    # Remove unit/suite indicators
    unit_indicators = ['unit', 'suite', 'ste', 'apt', 'apartment', '#']
    for indicator in unit_indicators:
        pattern = r'\b' + indicator + r'\.?\s*\d*'
        street = re.sub(pattern, '', street, flags=re.IGNORECASE)

    # Remove punctuation and numbers (except street number which is extracted separately)
    street = re.sub(r'[^\w\s]', '', street)
    street = re.sub(r'\d+', '', street)

    # Normalize whitespace
    street = ' '.join(street.split())

    return street.strip()


def _extract_street_number(address: str) -> Optional[str]:
    """
    Extract street number from address.

    Examples:
        >>> _extract_street_number("123 Main St")
        '123'
        >>> _extract_street_number("456-B Oak Avenue")
        '456'
    """
    if not address:
        return None

    # Match leading digits
    match = re.match(r'^(\d+)', address.strip())
    return match.group(1) if match else None


def _normalize_website(url: str) -> str:
    """
    Normalize website URL to domain only.

    Removes:
    - Protocol (http://, https://)
    - www prefix
    - Trailing slash
    - Path components

    Examples:
        >>> _normalize_website("https://www.example.com/")
        'example.com'
        >>> _normalize_website("http://example.com/page")
        'example.com'
    """
    if not url:
        return ""

    url = url.lower().strip()

    # Remove protocol
    url = re.sub(r'^https?://', '', url)

    # Remove www prefix
    url = re.sub(r'^www\.', '', url)

    # Remove trailing slash
    url = url.rstrip('/')

    # Extract domain only (remove path)
    domain_match = re.match(r'^([^/]+)', url)
    domain = domain_match.group(1) if domain_match else url

    return domain


def businesses_are_duplicates(
    business1: Dict,
    business2: Dict,
    strict: bool = False
) -> bool:
    """
    Determine if two business records are duplicates.

    Args:
        business1: First business record
        business2: Second business record
        strict: If True, require exact fingerprint match.
                If False, also check fuzzy name + address match.

    Returns:
        True if businesses are likely duplicates

    Examples:
        >>> b1 = {"name": "ABC Inc.", "street": "123 Main St", "city": "Hamilton"}
        >>> b2 = {"name": "ABC Incorporated", "street": "123 Main Street", "city": "Hamilton"}
        >>> businesses_are_duplicates(b1, b2)
        True
    """
    # Compute fingerprints
    fp1 = compute_business_fingerprint(
        business1.get('name', ''),
        business1.get('street', ''),
        business1.get('city', ''),
        business1.get('postal_code', ''),
        business1.get('phone', ''),
        business1.get('website', '')
    )

    fp2 = compute_business_fingerprint(
        business2.get('name', ''),
        business2.get('street', ''),
        business2.get('city', ''),
        business2.get('postal_code', ''),
        business2.get('phone', ''),
        business2.get('website', '')
    )

    # Exact fingerprint match
    if fp1 == fp2:
        return True

    # Fuzzy matching (if not strict)
    if not strict:
        # Same normalized name + same city + (same street number OR same phone)
        name1 = _normalize_name(business1.get('name', ''))
        name2 = _normalize_name(business2.get('name', ''))

        if not name1 or not name2 or name1 != name2:
            return False

        city1 = (business1.get('city', '') or '').lower().strip()
        city2 = (business2.get('city', '') or '').lower().strip()

        if city1 != city2:
            return False

        # Check street number OR phone
        street_num1 = _extract_street_number(business1.get('street', '') or '')
        street_num2 = _extract_street_number(business2.get('street', '') or '')

        if street_num1 and street_num2 and street_num1 == street_num2:
            return True

        # Check phone
        phone1 = re.sub(r'\D', '', business1.get('phone', '') or '')[-10:]
        phone2 = re.sub(r'\D', '', business2.get('phone', '') or '')[-10:]

        if phone1 and phone2 and phone1 == phone2:
            return True

    return False
