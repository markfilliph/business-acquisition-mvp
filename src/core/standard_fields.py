"""
Standard Field Order for All Lead Generation Outputs

This module defines the CANONICAL field order that MUST be used
in all lead generation CSV outputs.

DO NOT MODIFY THIS ORDER without explicit user approval.
"""

# CANONICAL FIELD ORDER - DO NOT CHANGE
STANDARD_FIELD_ORDER = [
    # PRIMARY FIELDS (User's priority order)
    'business_name',
    'phone',
    'website',
    'address',           # Full combined address
    'postal_code',
    'revenue',           # estimated_revenue value
    'sde',               # sde_estimate value
    'employee_count',    # Calculated midpoint from employee_range

    # SECONDARY FIELDS (alphabetical)
    'city',
    'confidence_score',
    'data_source',
    'employee_range',
    'industry',
    'place_types',
    'priority',
    'province',
    'query_type',
    'query_used',
    'rating',
    'revenue_range',
    'review_count',
    'street_address',
    'validation_layers_passed',
]


def get_standard_fieldnames():
    """
    Get the standard field order for CSV output.

    Returns:
        List of field names in canonical order
    """
    return STANDARD_FIELD_ORDER.copy()


def format_lead_for_output(lead_data: dict) -> dict:
    """
    Format a lead dictionary to match standard field names and ensure all fields exist.

    Args:
        lead_data: Dictionary with lead information

    Returns:
        Dictionary with standardized field names, all fields present
    """
    # Map common variations to standard names
    standardized = {}

    # Primary fields
    standardized['business_name'] = lead_data.get('business_name', lead_data.get('name', ''))
    standardized['phone'] = lead_data.get('phone', lead_data.get('phone_number', ''))
    standardized['website'] = lead_data.get('website', lead_data.get('url', ''))

    # Address - combine if needed
    if 'address' in lead_data:
        standardized['address'] = lead_data['address']
    else:
        # Build from components
        address_parts = []
        if lead_data.get('street_address') or lead_data.get('street'):
            address_parts.append(lead_data.get('street_address', lead_data.get('street', '')))
        if lead_data.get('city'):
            address_parts.append(lead_data['city'])
        if lead_data.get('province'):
            address_parts.append(lead_data['province'])
        standardized['address'] = ', '.join(filter(None, address_parts))

    standardized['postal_code'] = lead_data.get('postal_code', '')
    standardized['revenue'] = lead_data.get('revenue', lead_data.get('estimated_revenue', ''))
    standardized['sde'] = lead_data.get('sde', lead_data.get('sde_estimate', ''))

    # Employee count - calculate from range if needed
    if 'employee_count' in lead_data:
        standardized['employee_count'] = lead_data['employee_count']
    else:
        employee_range = lead_data.get('employee_range', '')
        if employee_range and '-' in employee_range:
            try:
                low, high = employee_range.split('-')
                standardized['employee_count'] = (int(low) + int(high)) // 2
            except:
                standardized['employee_count'] = 10  # Default
        else:
            standardized['employee_count'] = 10

    # Secondary fields
    standardized['city'] = lead_data.get('city', '')
    standardized['confidence_score'] = lead_data.get('confidence_score', '85%')
    standardized['data_source'] = lead_data.get('data_source', '')
    standardized['employee_range'] = lead_data.get('employee_range', '')
    standardized['industry'] = lead_data.get('industry', '')
    standardized['place_types'] = lead_data.get('place_types', '')
    standardized['priority'] = lead_data.get('priority', 'HIGH')
    standardized['province'] = lead_data.get('province', 'ON')
    standardized['query_type'] = lead_data.get('query_type', '')
    standardized['query_used'] = lead_data.get('query_used', '')
    standardized['rating'] = lead_data.get('rating', '')
    standardized['revenue_range'] = lead_data.get('revenue_range', '')
    standardized['review_count'] = lead_data.get('review_count', 0)
    standardized['street_address'] = lead_data.get('street_address', lead_data.get('street', ''))
    standardized['validation_layers_passed'] = lead_data.get('validation_layers_passed', 3)

    return standardized


def validate_field_order(fieldnames: list) -> bool:
    """
    Validate that fieldnames match the standard order.

    Args:
        fieldnames: List of field names to validate

    Returns:
        True if matches standard order, False otherwise
    """
    if len(fieldnames) != len(STANDARD_FIELD_ORDER):
        return False

    for i, expected in enumerate(STANDARD_FIELD_ORDER):
        if i >= len(fieldnames) or fieldnames[i] != expected:
            return False

    return True


# Quick reference for developers
FIELD_ORDER_SUMMARY = """
STANDARD FIELD ORDER (DO NOT CHANGE):

PRIMARY FIELDS:
1. business_name
2. phone
3. website
4. address (full combined address)
5. postal_code
6. revenue
7. sde
8. employee_count

SECONDARY FIELDS (alphabetical):
- city, confidence_score, data_source, employee_range, industry,
  place_types, priority, province, query_type, query_used, rating,
  revenue_range, review_count, street_address, validation_layers_passed
"""
