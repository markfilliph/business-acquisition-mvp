# Standard Field Order for All Lead Generation Outputs

**⚠️ CRITICAL: This field order is MANDATORY for all lead generation scripts.**

**DO NOT MODIFY without explicit user approval.**

---

## Standard Field Order

ALL CSV outputs from lead generation MUST use this EXACT field order:

### PRIMARY FIELDS (1-8)
1. `business_name` - Business name
2. `phone` - Phone number
3. `website` - Website URL
4. `address` - Full combined address (street, city, province)
5. `postal_code` - Canadian postal code
6. `revenue` - Estimated annual revenue (numeric)
7. `sde` - Seller's Discretionary Earnings estimate (numeric)
8. `employee_count` - Employee count (calculated midpoint of range)

### SECONDARY FIELDS (9-23, alphabetical)
9. `city` - City
10. `confidence_score` - Data confidence score
11. `data_source` - Source of the data
12. `employee_range` - Employee range (e.g., "7-16")
13. `industry` - Industry classification
14. `place_types` - Google Place types
15. `priority` - Lead priority level
16. `province` - Province/state
17. `query_type` - Type of search query used
18. `query_used` - Actual search query
19. `rating` - Google rating
20. `revenue_range` - Revenue range estimate
21. `review_count` - Number of reviews
22. `street_address` - Street address only
23. `validation_layers_passed` - Number of validation layers passed

---

## Implementation

### For ALL New Scripts:

```python
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.standard_fields import get_standard_fieldnames, format_lead_for_output

# When creating a lead dictionary:
lead_raw = {
    'business_name': 'ABC Company',
    'phone': '(905) 555-1234',
    'website': 'https://example.com',
    # ... other fields ...
}

# Standardize field order
lead = format_lead_for_output(lead_raw)

# When writing CSV:
fieldnames = get_standard_fieldnames()
writer = csv.DictWriter(f, fieldnames=fieldnames)
writer.writeheader()
writer.writerows(leads)
```

---

## Scripts Updated

✅ **UPDATED (using standard):**
- `src/core/standard_fields.py` - Standard definition module
- `scripts/generate_100_hot_leads_optimized.py` - Main generation script
- `consolidate_hot_leads_20.py` - Consolidation script
- `deduplicate_and_clean_consolidated.py` - Cleaning script
- `reorganize_clean_leads.py` - Reorganization script

⏳ **TO BE UPDATED (if used):**
- `scripts/generate_leads_phase2_fixed.py`
- `scripts/generate_all_100_leads_fixed.py`
- `generate_20_per_industry_final.py`
- Any custom generation scripts

---

## Why This Matters

### Problem:
- Field order was inconsistent across different generation runs
- Made it difficult to compare files
- Caused user frustration

### Solution:
- Single source of truth: `src/core/standard_fields.py`
- All scripts import and use the same standard
- Consistent output every time

---

## Field Calculations

### `address` (Combined Address)
```python
address_parts = []
if street_address:
    address_parts.append(street_address)
if city:
    address_parts.append(city)
if province:
    address_parts.append(province)
address = ', '.join(address_parts)
```

### `employee_count` (Midpoint Calculation)
```python
if '-' in employee_range:
    low, high = employee_range.split('-')
    employee_count = (int(low) + int(high)) // 2
else:
    employee_count = 10  # Default
```

### `sde` (Seller's Discretionary Earnings)
```python
sde = int(revenue * 0.15)  # 15% of revenue
```

---

## Validation

To validate field order compliance:

```python
from src.core.standard_fields import validate_field_order

# Check if CSV has correct field order
with open('leads.csv', 'r') as f:
    reader = csv.DictReader(f)
    is_valid = validate_field_order(reader.fieldnames)

    if not is_valid:
        print("❌ Field order does not match standard!")
    else:
        print("✅ Field order is correct")
```

---

## Common Mistakes to Avoid

### ❌ DON'T:
```python
# Don't use arbitrary field order
fieldnames = list(lead.keys())  # WRONG!

# Don't use old field names
lead['estimated_revenue'] = revenue  # WRONG! Use 'revenue'
lead['sde_estimate'] = sde  # WRONG! Use 'sde'
```

### ✅ DO:
```python
# Always use standard field order
fieldnames = get_standard_fieldnames()

# Always use standard field names
lead = format_lead_for_output(raw_data)
```

---

## Testing

Before committing changes, verify field order:

```bash
# Check first line of any generated CSV
head -1 data/outputs/HOT_LEADS_*.csv

# Should always be:
# business_name,phone,website,address,postal_code,revenue,sde,employee_count,...
```

---

## Questions?

If you need to modify the field order:
1. **DON'T** modify it in individual scripts
2. **DO** modify `src/core/standard_fields.py`
3. **DO** get user approval first
4. **DO** update this documentation

---

**Last Updated:** 2025-11-19
**Maintained By:** Lead Generation System
**Status:** ✅ Active and Enforced
