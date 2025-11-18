# Standardized Lead Output Format

## Overview

**IMPORTANT:** This document defines the **LOCKED** output format for ALL lead generation.

The format defined here **MUST NEVER CHANGE** between lead generation runs. All export scripts and pipelines are required to use this standardized format to ensure consistency.

## Required Fields

Every lead export CSV file will ALWAYS contain these exact columns in this order:

| Column Name | Description | Format | Example |
|------------|-------------|--------|---------|
| **Business Name** | Legal or operating business name | Text | "Acme Manufacturing Inc." |
| **Address** | Street address (number + street) | Text | "123 Main Street" |
| **City** | City name | Text | "Hamilton" |
| **Province** | Province code | 2-letter code | "ON" |
| **Postal Code** | Canadian postal code | A1A 1A1 | "L8P 4R5" |
| **Phone Number** | Primary phone number | (XXX) XXX-XXXX | "(905) 555-1234" |
| **Website** | Company website URL | URL | "https://example.com" |
| **Industry** | Primary industry classification | Text | "manufacturing" |
| **Estimated Employees (Range)** | Employee count range | X-Y format | "10-25" |
| **Estimated SDE (CAD)** | Seller's Discretionary Earnings | Currency with margin | "$270K (22% margin)" |
| **Estimated Revenue (CAD)** | Annual revenue estimate | Currency | "$1.2M" |
| **Confidence Score** | Overall data confidence | Percentage | "83%" |
| **Status** | Lead qualification status | Uppercase status | "QUALIFIED" |
| **Data Sources** | Sources used for data | Comma-separated | "Google Business, Web Scraping" |

## Field Details

### Estimated SDE (Seller's Discretionary Earnings)

SDE represents the profit the owner could take home, calculated as:

```
SDE = Revenue - (COGS + Operating Expenses) + Owner Compensation + Non-recurring expenses
```

**Industry-based margins:**
- Manufacturing: 18%
- Wholesale: 20%
- Professional Services: 30%
- Printing: 18%
- Construction: 22%
- Equipment Rental: 25%

**Adjustments:**
- Very small businesses (≤5 employees): +5%
- Larger businesses (≥20 employees): -3%

### Estimated Employees (Range)

Provided as a range to reflect uncertainty:
- Known count: ±2-5 employees around the known value
- Estimated: Industry-based benchmarks or revenue-per-employee calculation

Common ranges:
- "3-8" (very small)
- "8-15" (small)
- "15-30" (medium-small)
- "30-60" (medium)
- "50+" (larger)

### Estimated Revenue (CAD)

Calculated using:
1. Employee count × industry-specific revenue per employee
2. Industry benchmarks from `src/core/config.py`
3. Default: $75,000 per employee if industry unknown

Format: "$1.2M" for millions, "$450K" for thousands

### Confidence Score

Percentage representing data completeness, calculated as:
```
(Number of populated key fields) / (Total key fields) × 100%
```

Key fields checked:
- Phone number
- Website (verified)
- Address
- Postal code
- Employee count
- Industry

## Implementation

### Code Location

**Primary schema definition:**
```
src/core/output_schema.py
```

**Key components:**
- `STANDARD_CSV_HEADERS`: Locked column headers (NEVER modify)
- `StandardLeadOutput`: Pydantic model enforcing required fields
- `calculate_sde_from_revenue()`: SDE calculation logic
- `calculate_employee_range()`: Employee range logic
- `format_currency_cad()`: Currency formatting

### Usage in Export Scripts

All export scripts MUST import and use the standardized schema:

```python
from src.core.output_schema import (
    STANDARD_CSV_HEADERS,
    StandardLeadOutput,
    calculate_employee_range,
    calculate_sde_from_revenue,
    format_currency_cad
)

# Create CSV with standardized headers
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=STANDARD_CSV_HEADERS)
    writer.writeheader()

    # Create standardized output for each lead
    standard_output = StandardLeadOutput(
        business_name=name,
        address=street,
        city=city,
        province="ON",
        postal_code=postal_code,
        phone_number=phone,
        website=website,
        industry=industry,
        estimated_employees_range=employee_range,
        estimated_sde_cad=sde_formatted,
        estimated_revenue_cad=revenue_formatted,
        confidence_score=confidence_formatted,
        status="QUALIFIED",
        data_sources="Google Business, Web Scraping"
    )

    writer.writerow(standard_output.to_dict())
```

## Updated Scripts

The following scripts have been updated to use the standardized format:

1. ✅ `src/exports/csv_exporter.py` - Main CSV exporter
2. ✅ `export_qualified_leads.py` - Root-level export script
3. ✅ `scripts/export/export_detailed_leads.py` - Detailed export script
4. ✅ `src/core/models.py` - Added `to_standard_output()` method to BusinessLead

## Migration Guide

If you have existing export scripts, update them to use the standardized format:

**OLD (inconsistent):**
```python
fieldnames = ['Company Name', 'Phone', 'Website', 'Revenue Estimate']  # ❌ Custom headers
```

**NEW (standardized):**
```python
from src.core.output_schema import STANDARD_CSV_HEADERS, StandardLeadOutput

fieldnames = STANDARD_CSV_HEADERS  # ✅ Always use this
```

## Benefits

✅ **Consistency**: Same format every time, no confusion
✅ **Automation**: Can build tools that expect this exact format
✅ **SDE Calculation**: Industry-specific profit estimates
✅ **Employee Ranges**: Realistic uncertainty representation
✅ **Validation**: Pydantic models ensure data integrity
✅ **Documentation**: Clear field definitions and examples

## Support

For questions or issues with the standardized format:
1. Check this documentation first
2. Review `src/core/output_schema.py` for implementation details
3. Refer to `src/core/config.py` for industry benchmarks

---

**Last Updated:** 2025-11-17
**Version:** 1.0
**Status:** LOCKED - Do not modify without approval
