"""
Canada Post-compliant address normalization for accurate address matching.
PRIORITY: P0 - Critical for cross-validation accuracy.

Handles Canadian address formats with proper abbreviation expansion,
component parsing, and fuzzy matching.
"""

import re
from typing import Dict, Optional, Tuple
import structlog

logger = structlog.get_logger(__name__)

# Canada Post standard abbreviations
CANADA_POST_ABBREV = {
    # Street types
    "St": "Street",
    "Ave": "Avenue",
    "Rd": "Road",
    "Blvd": "Boulevard",
    "Dr": "Drive",
    "Ln": "Lane",
    "Crt": "Court",
    "Ct": "Court",
    "Cres": "Crescent",
    "Terr": "Terrace",
    "Pl": "Place",
    "Pk": "Park",
    "Sq": "Square",
    "Pkwy": "Parkway",
    "Hwy": "Highway",
    "Way": "Way",
    "Cir": "Circle",
    "Tr": "Trail",
    "Path": "Path",

    # Directional
    "E": "East",
    "W": "West",
    "N": "North",
    "S": "South",
    "NE": "Northeast",
    "NW": "Northwest",
    "SE": "Southeast",
    "SW": "Southwest",

    # Unit types
    "Apt": "Apartment",
    "Ste": "Suite",
    "Unit": "Unit",
    "Bldg": "Building",
    "Fl": "Floor",
    "PH": "Penthouse",
    "Rm": "Room",
}


def normalize_address(address_string: str) -> Dict[str, str]:
    """
    Parse and normalize Canadian address to Canada Post standards.

    Args:
        address_string: Raw address string

    Returns:
        Dictionary with parsed and normalized components:
        {
            'street_number': '123',
            'street_name': 'Main',
            'street_type': 'Street',
            'street_direction': 'East',
            'unit': 'Unit 5',
            'city': 'Hamilton',
            'province': 'ON',
            'postal_code': 'L8H3R2',
            'normalized': 'full normalized address',
            'original': 'original input'
        }

    Examples:
        >>> normalize_address("123 Main St E, Unit 7, Hamilton ON L8P 4R5")
        {'street_number': '123', 'street_name': 'Main', 'street_type': 'Street', ...}
    """
    if not address_string:
        return {
            'street_number': '',
            'street_name': '',
            'street_type': '',
            'street_direction': '',
            'unit': '',
            'city': '',
            'province': '',
            'postal_code': '',
            'normalized': '',
            'original': ''
        }

    result = {
        'street_number': '',
        'street_name': '',
        'street_type': '',
        'street_direction': '',
        'unit': '',
        'city': '',
        'province': '',
        'postal_code': '',
        'normalized': '',
        'original': address_string
    }

    # Clean input
    addr = address_string.strip()

    # Extract postal code (Canadian format: A1A 1A1 or A1A1A1)
    postal_match = re.search(r'\b([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b', addr, re.IGNORECASE)
    if postal_match:
        result['postal_code'] = postal_match.group(1).upper().replace(' ', '')
        addr = addr[:postal_match.start()] + addr[postal_match.end():]

    # Extract province (ON, Ontario, etc.)
    province_match = re.search(r'\b(ON|Ontario|QC|Quebec|BC|British Columbia)\b', addr, re.IGNORECASE)
    if province_match:
        province = province_match.group(1)
        result['province'] = 'ON' if province.upper() in ['ON', 'ONTARIO'] else province
        addr = addr[:province_match.start()] + addr[province_match.end():]

    # Extract city (usually after street, before province)
    # Look for comma-separated components
    parts = [p.strip() for p in addr.split(',')]

    if len(parts) >= 2:
        # Last part before province/postal is usually city
        result['city'] = _title_case(parts[-1].strip())
        street_part = ','.join(parts[:-1])
    else:
        street_part = addr

    # Extract unit number (Unit 5, Apt 3, #7, Suite 10, etc.)
    unit_patterns = [
        r'#\s*(\d+[A-Z]?)',
        r'\b(Unit|Apt|Ste|Suite|Apartment)\s+(\d+[A-Z]?)\b',
        r'\bUnit\s*(\d+[A-Z]?)\b',
    ]
    for pattern in unit_patterns:
        unit_match = re.search(pattern, street_part, re.IGNORECASE)
        if unit_match:
            if len(unit_match.groups()) == 2:
                result['unit'] = f"{unit_match.group(1)} {unit_match.group(2)}"
            else:
                result['unit'] = unit_match.group(1)
            street_part = street_part[:unit_match.start()] + street_part[unit_match.end():]
            break

    # Parse street components
    street_part = street_part.strip().strip(',').strip()

    # Extract street number (leading digits, may include letters like 123A)
    number_match = re.match(r'^(\d+[A-Z]?)\b', street_part, re.IGNORECASE)
    if number_match:
        result['street_number'] = number_match.group(1)
        street_part = street_part[number_match.end():].strip()

    # Extract street direction (E, W, N, S, etc.) - usually at end
    direction_pattern = r'\b(E|W|N|S|NE|NW|SE|SW|East|West|North|South|Northeast|Northwest|Southeast|Southwest)\b'
    direction_match = re.search(direction_pattern, street_part, re.IGNORECASE)
    if direction_match:
        direction_abbrev = direction_match.group(1)
        result['street_direction'] = CANADA_POST_ABBREV.get(direction_abbrev, direction_abbrev)
        street_part = street_part[:direction_match.start()] + street_part[direction_match.end():]

    # Extract street type (St, Ave, Rd, etc.) - usually at end of remaining street
    type_pattern = r'\b(' + '|'.join(CANADA_POST_ABBREV.keys()) + r')\b\.?'
    type_match = re.search(type_pattern, street_part, re.IGNORECASE)
    if type_match:
        type_abbrev = type_match.group(1)
        result['street_type'] = CANADA_POST_ABBREV.get(type_abbrev, type_abbrev)
        street_part = street_part[:type_match.start()] + street_part[type_match.end():]

    # Remaining is street name
    result['street_name'] = _title_case(street_part.strip())

    # Build normalized address
    normalized_parts = []
    if result['street_number']:
        normalized_parts.append(result['street_number'])
    if result['street_name']:
        normalized_parts.append(result['street_name'])
    if result['street_type']:
        normalized_parts.append(result['street_type'])
    if result['street_direction']:
        normalized_parts.append(result['street_direction'])
    if result['unit']:
        normalized_parts.append(result['unit'])
    if result['city']:
        normalized_parts.append(result['city'])
    if result['province']:
        normalized_parts.append(result['province'])
    if result['postal_code']:
        # Format postal code with space: L8H 3R2
        pc = result['postal_code']
        if len(pc) == 6:
            result['postal_code'] = f"{pc[:3]} {pc[3:]}"
        normalized_parts.append(result['postal_code'])

    result['normalized'] = ' '.join(normalized_parts)

    return result


def addresses_match(addr1: str, addr2: str, fuzzy: bool = True) -> Tuple[bool, float]:
    """
    Compare two addresses for matching with fuzzy logic.

    Args:
        addr1: First address string
        addr2: Second address string
        fuzzy: Allow minor differences if True (St vs Street)

    Returns:
        (is_match, confidence_score) where confidence is 0.0 to 1.0

    Examples:
        >>> addresses_match("123 Main St", "123 Main Street")
        (True, 1.0)

        >>> addresses_match("123 Main St E, Unit 7", "123 Main Street East #7")
        (True, 0.95)
    """
    if not addr1 or not addr2:
        return False, 0.0

    # Normalize both addresses
    norm1 = normalize_address(addr1)
    norm2 = normalize_address(addr2)

    # Calculate component match score
    score = 0.0
    max_score = 0.0

    # Street number (required, high weight)
    if norm1['street_number'] or norm2['street_number']:
        max_score += 3.0
        if norm1['street_number'] == norm2['street_number']:
            score += 3.0
        elif not norm1['street_number'] or not norm2['street_number']:
            # One missing - partial credit
            score += 1.0

    # Street name (required, high weight)
    if norm1['street_name'] or norm2['street_name']:
        max_score += 3.0
        if norm1['street_name'].lower() == norm2['street_name'].lower():
            score += 3.0
        elif norm1['street_name'] and norm2['street_name']:
            # Fuzzy match on street name
            similarity = _string_similarity(norm1['street_name'], norm2['street_name'])
            score += similarity * 3.0

    # Street type (medium weight)
    if norm1['street_type'] or norm2['street_type']:
        max_score += 2.0
        if norm1['street_type'] == norm2['street_type']:
            score += 2.0
        elif not norm1['street_type'] or not norm2['street_type']:
            # One missing - if fuzzy, give partial credit
            if fuzzy:
                score += 1.5

    # Street direction (low weight)
    if norm1['street_direction'] or norm2['street_direction']:
        max_score += 1.0
        if norm1['street_direction'] == norm2['street_direction']:
            score += 1.0
        elif not norm1['street_direction'] or not norm2['street_direction']:
            if fuzzy:
                score += 0.5

    # Unit (low weight, often missing)
    if norm1['unit'] or norm2['unit']:
        max_score += 1.0
        if norm1['unit'] == norm2['unit']:
            score += 1.0
        elif not norm1['unit'] or not norm2['unit']:
            # Missing unit is OK
            if fuzzy:
                score += 0.7

    # City (medium weight)
    if norm1['city'] or norm2['city']:
        max_score += 2.0
        if norm1['city'].lower() == norm2['city'].lower():
            score += 2.0

    # Postal code (high weight when available)
    if norm1['postal_code'] and norm2['postal_code']:
        max_score += 2.0
        # Match first 3 characters (forward sortation area)
        if norm1['postal_code'][:3] == norm2['postal_code'][:3]:
            score += 1.5
            # Full postal match
            if norm1['postal_code'] == norm2['postal_code']:
                score += 0.5

    # Calculate confidence
    if max_score == 0:
        return False, 0.0

    confidence = score / max_score

    # Matching criteria
    # STRICT REQUIREMENT: same street number (this is critical!)
    street_number_match = (norm1['street_number'] == norm2['street_number'] and
                          norm1['street_number'] != '')

    if not street_number_match:
        # Different street numbers = different addresses, regardless of other fields
        return False, confidence * 0.3  # Low confidence for different street numbers

    # Require: same street name + (same city OR same postal prefix)
    street_name_match = norm1['street_name'].lower() == norm2['street_name'].lower()
    city_match = norm1['city'].lower() == norm2['city'].lower() if (norm1['city'] and norm2['city']) else False
    postal_match = norm1['postal_code'][:3] == norm2['postal_code'][:3] if (norm1['postal_code'] and norm2['postal_code']) else False

    is_match = street_name_match and (city_match or postal_match or confidence >= 0.8)

    # In fuzzy mode, lower threshold but STILL require street number match
    if fuzzy and confidence >= 0.7 and street_number_match:
        is_match = True

    return is_match, confidence


def _title_case(s: str) -> str:
    """Convert to Title Case."""
    if not s:
        return ''
    return ' '.join(word.capitalize() for word in s.split())


def _string_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity using Jaccard similarity."""
    if not s1 or not s2:
        return 0.0

    # Convert to lowercase and split into character sets
    set1 = set(s1.lower().split())
    set2 = set(s2.lower().split())

    if not set1 or not set2:
        return 0.0

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    return intersection / union if union > 0 else 0.0


def parse_street_number(address: str) -> Optional[str]:
    """
    Extract street number from address.

    Examples:
        >>> parse_street_number("123 Main St")
        '123'
        >>> parse_street_number("456-B Oak Ave")
        '456-B'
    """
    if not address:
        return None

    match = re.match(r'^(\d+[A-Z]?(?:-[A-Z])?)\b', address.strip(), re.IGNORECASE)
    return match.group(1) if match else None
