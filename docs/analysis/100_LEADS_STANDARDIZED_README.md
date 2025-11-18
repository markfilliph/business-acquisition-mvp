# 100 Business Leads - Standardized Format

**Generated:** November 17, 2025
**Source File:** NEW_100_LEADS_BY_INDUSTRY_20251116_201005.csv
**Output File:** 100_LEADS_STANDARDIZED_FORMAT.csv
**Format Version:** 1.0 (LOCKED)

---

## Overview

This file contains the same 100 leads from November 16, 2025, but reformatted with the **NEW STANDARDIZED FORMAT** that will be used for ALL future lead generation.

### What Changed?

**ADDED Fields (NEW):**
- ✅ **Estimated Employees (Range)** - e.g., "10-25", "5-10"
- ✅ **Estimated SDE (CAD)** - Seller's Discretionary Earnings with margin (e.g., "$225K (18% margin)")
- ✅ **Estimated Revenue (CAD)** - Annual revenue estimate (e.g., "$1.5M")
- ✅ **Confidence Score** - Data quality percentage (e.g., "83%")

**KEPT Fields (From Original):**
- Business Name
- Address (was "Street Address")
- City
- Province
- Postal Code
- Phone Number (was "Phone")
- Website
- Industry
- Status (derived from Priority)
- Data Sources (was "Data Source")

**REMOVED Fields (No Longer Needed):**
- Place Types
- Review Count (used for estimation, not exported)
- Rating (used for estimation, not exported)
- Warnings (incorporated into Status and Confidence)
- Priority (converted to Status)

---

## File Statistics

| Metric | Value |
|--------|-------|
| **Total Leads** | 100 |
| **Industries** | 5 (20 per industry) |
| **QUALIFIED** | 40 leads (40%) |
| **REVIEW_REQUIRED** | 60 leads (60%) |
| **Format Version** | 1.0 (Standardized) |

---

## Industry Distribution

| Industry | QUALIFIED | REVIEW_REQUIRED | Total |
|----------|-----------|-----------------|-------|
| **Equipment Rental** | 10 | 10 | 20 |
| **Manufacturing** | 8 | 12 | 20 |
| **Printing** | 5 | 15 | 20 |
| **Professional Services** | 9 | 11 | 20 |
| **Wholesale** | 8 | 12 | 20 |
| **TOTAL** | **40** | **60** | **100** |

---

## Field Definitions

### Estimated Employees (Range)

Employee count provided as a range to reflect estimation uncertainty:

- **Methodology:** Based on review count, industry benchmarks, and business size indicators
- **Format:** "X-Y" (e.g., "10-25", "5-10")
- **Common Ranges:**
  - "3-8" - Very small businesses
  - "8-15" - Small businesses
  - "15-30" - Medium-small businesses
  - "30-50" - Medium businesses

### Estimated SDE (CAD)

**SDE = Seller's Discretionary Earnings** - The profit the owner could take home.

Calculated as:
```
SDE = Revenue × Industry Margin
```

**Industry Margins Applied:**
- Manufacturing: 15-18%
- Wholesale: 20%
- Professional Services: 30-35%
- Printing: 18%
- Equipment Rental: 22-25%

**Adjustments:**
- Very small businesses (≤5 employees): +5%
- Larger businesses (≥20 employees): -3%

### Estimated Revenue (CAD)

Annual revenue estimate calculated using:
```
Revenue = Employee Count × $75,000
```

This is a conservative industry average. Actual revenue may vary based on:
- Industry margins
- Business maturity
- Location and market

### Confidence Score

Represents data completeness and quality:

**Factors:**
- ✅ Has phone number
- ✅ Has verified website
- ✅ Has complete address
- ✅ Has postal code
- ✅ Has industry classification
- ✅ Has customer reviews (indicates active business)

**Adjustments:**
- -15% if warnings present (e.g., HIGH_VISIBILITY, NO_WEBSITE)

**Typical Ranges:**
- 90-100%: Excellent data quality
- 70-89%: Good data quality (most leads)
- 50-69%: Fair data quality (needs verification)
- <50%: Poor data quality (high risk)

### Status

**QUALIFIED (40 leads):**
- HIGH priority from original dataset
- No warnings flagged
- Ready for immediate outreach
- Confidence typically 80%+

**REVIEW_REQUIRED (60 leads):**
- MEDIUM priority from original dataset
- Has warnings (e.g., HIGH_VISIBILITY, NO_WEBSITE)
- Needs manual review before outreach
- Confidence typically 60-80%

---

## Estimation Methodology

### Employee Count Estimation

Based on Google review count (proxy for business visibility/size):

| Review Count | Estimated Employees |
|--------------|-------------------|
| 0-9 reviews | 5 employees |
| 10-29 reviews | 12 employees |
| 30-99 reviews | 20 employees |
| 100-299 reviews | 30 employees |
| 300+ reviews | 40 employees |

**Note:** This is a conservative estimate. Actual employee counts may vary.

### Revenue Estimation

```
Revenue = Employee Count × $75,000 per employee
```

This $75K multiplier is a conservative industry average for SMBs in Hamilton, ON.

### SDE Estimation

SDE (Seller's Discretionary Earnings) represents the cash flow available to the owner:

```
SDE = Revenue × Industry-Specific Margin
```

**Why SDE Matters:**
- More accurate than just revenue for valuation
- Accounts for industry profitability differences
- Shows actual earning potential for buyers

---

## Data Quality Notes

### High Quality Indicators
- Phone number present (100% of leads)
- Website present (95% of leads)
- Physical address (100% of leads)
- Active reviews (indicates operating business)

### Areas for Verification
- **Postal Codes:** Many missing (marked as "Unknown")
- **Employee Counts:** Estimates based on reviews, not verified
- **Revenue/SDE:** Calculated estimates, not actual financials
- **Warnings:** 60% of leads have warnings requiring review

### Recommended Next Steps

**For QUALIFIED Leads (40):**
1. ✅ Ready for immediate outreach
2. ✅ Verify contact information
3. ✅ Initial discovery call
4. ✅ Confirm business metrics

**For REVIEW_REQUIRED Leads (60):**
1. ⚠️ Review warnings carefully
2. ⚠️ Verify not a chain/franchise
3. ⚠️ Confirm single-location SMB
4. ⚠️ Check website exists and matches business
5. ✅ Move to QUALIFIED if checks pass

---

## Usage

### Opening the File

```bash
# View in terminal (first 10 leads)
head -n 11 data/outputs/100_LEADS_STANDARDIZED_FORMAT.csv | column -t -s ','

# Open in Excel/Google Sheets
# Simply double-click the CSV file or import it
```

### Filtering Leads

```python
import csv

# Get only QUALIFIED leads
with open('100_LEADS_STANDARDIZED_FORMAT.csv', 'r') as f:
    reader = csv.DictReader(f)
    qualified = [row for row in reader if row['Status'] == 'QUALIFIED']

print(f"Found {len(qualified)} QUALIFIED leads ready for outreach")
```

### Sorting by Confidence

```python
import csv

# Get leads sorted by confidence
with open('100_LEADS_STANDARDIZED_FORMAT.csv', 'r') as f:
    reader = csv.DictReader(f)
    leads = sorted(reader, key=lambda x: int(x['Confidence Score'].rstrip('%')), reverse=True)

# Top 10 highest confidence leads
for i, lead in enumerate(leads[:10], 1):
    print(f"{i}. {lead['Business Name']} - {lead['Confidence Score']}")
```

---

## Future Updates

This standardized format is **LOCKED** and will be used for ALL future lead generation. Benefits:

✅ **Consistency:** Same fields every time
✅ **Automation:** Can build tools expecting this exact format
✅ **SDE/Revenue:** Business valuation metrics included
✅ **Employee Ranges:** Realistic uncertainty representation
✅ **Confidence Scoring:** Data quality transparency

---

## Questions?

For questions about:
- **Format specification:** See `STANDARDIZED_OUTPUT_FORMAT.md`
- **Implementation:** See `src/core/output_schema.py`
- **Testing:** Run `test_standardized_output.py`

---

**Last Updated:** November 17, 2025
**Format Version:** 1.0
**Status:** Production Ready ✅
