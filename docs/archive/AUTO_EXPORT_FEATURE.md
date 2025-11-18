# Automatic Export Feature

## Overview

The Smart Business Discovery Pipeline (v3) now **automatically generates timestamped CSV and validation reports** after every lead generation run.

## What Gets Generated

Every time you run `./generate_v3 [count]`, the system will automatically create:

### 1. Timestamped CSV File
**Format**: `data/leads_YYYYMMDD_HHMMSS.csv`

**Contains**:
- Company Name, Status, Phone, Website
- Full Address (Street, City, Postal Code)
- Industry classification
- **Employee Count** (with PASS/FAIL indicators)
- **Revenue Estimate** (calculated from employee count × $50k)
- Latitude/Longitude coordinates
- **Exclusion Reason** (why businesses were rejected)
- Enriched email count, phone count

**Example**: `data/leads_20251013_202726.csv`

### 2. Validation Report
**Format**: `data/validation_report_YYYYMMDD_HHMMSS.txt`

**Contains**:
- Executive summary with totals
- Exclusion breakdown (why businesses failed)
- Detailed listings of first 20 businesses per status (QUALIFIED, REVIEW_REQUIRED, EXCLUDED)
- Validation criteria for each business:
  - Employee count (5-30 employees)
  - Revenue estimate ($1M-$1.4M)
  - Years in business (15+)
  - Geographic location (Hamilton area)
- Failed validation gates for each business
- Statistics: qualification rate, employee count range, etc.

**Example**: `data/validation_report_20251013_202726.txt`

## Strict Validation Criteria

All businesses are validated against these **strict criteria with NO BYPASSES**:

| Criterion | Requirement | Action if Failed |
|-----------|-------------|------------------|
| **Employee Count** | 5-30 employees | AUTO_EXCLUDE if >30 or <5 |
| **Revenue Range** | $1,000,000 - $1,400,000 | AUTO_EXCLUDE if outside range |
| **Years in Business** | 15+ years | AUTO_EXCLUDE if <15 years |
| **Geographic** | Hamilton, ON area (20km) | AUTO_EXCLUDE if outside |
| **Industry** | Manufacturing, wholesale, B2B services | AUTO_EXCLUDE if not whitelisted |

## How to Use

### Basic Usage
```bash
# Generate 30 new leads (CSV + report auto-generated)
./generate_v3 30 --show

# Output will include:
# ✅ CSV Export Complete: data/leads_20251013_202726.csv
# ✅ Validation Report Complete: data/validation_report_20251013_202726.txt
```

### What You'll See

After the pipeline completes, you'll see:

```
================================================================================
📄 AUTO-EXPORT: Generating timestamped files
================================================================================

✅ CSV Export Complete:
   File: data/leads_20251013_202726.csv
   Total: 37 businesses
   Qualified: 0
   Excluded: 27
   Review Required: 10

✅ Validation Report Complete:
   File: data/validation_report_20251013_202726.txt
   Lines: 520
   Total: 37 businesses

================================================================================
📦 EXPORTS SAVED:
   • data/leads_20251013_202726.csv
   • data/validation_report_20251013_202726.txt
================================================================================
```

## Files Location

All exports are saved in the `data/` directory:

```
data/
├── leads_20251013_202726.csv            # Timestamped CSV
├── validation_report_20251013_202726.txt # Timestamped report
├── leads_v3.db                           # Database
└── (previous runs...)
```

## Example Output

### CSV Sample
```csv
Company Name,Status,Employee Count,Revenue Estimate,Exclusion Reason
"ArcelorMittal Dofasco",EXCLUDED,5000,"$250,000,000","employee_gate: Too many employees (5000 > 30)"
"Grant Thornton LLP",EXCLUDED,50,"$2,500,000","employee_gate: Too many employees (50 > 30)"
"Small Manufacturer Co",QUALIFIED,25,"$1,250,000",""
```

### Report Sample
```
EXECUTIVE SUMMARY
----------------------------------------------------------------------------------------------------

Total Businesses Processed: 37
  ✅ QUALIFIED: 0
  ❌ EXCLUDED: 27
  ⚠️  REVIEW_REQUIRED: 10

EXCLUSION BREAKDOWN:
  • Employee count > 30 (too large): 25 businesses
  • Website unreachable/parked: 2 businesses
```

## Benefits

1. **No Manual Export Required**: Files are automatically generated every run
2. **Historical Tracking**: Timestamped files preserve each run's results
3. **Full Transparency**: See exactly why each business was qualified or excluded
4. **Audit Trail**: Track validation criteria enforcement over time
5. **Easy Sharing**: CSV and TXT formats for sharing with team

## Implementation Details

- **Auto-generated on every run**: No need to remember to export
- **Timestamped filenames**: Prevents overwrites, maintains history
- **Async export**: Fast, non-blocking export process
- **Comprehensive data**: All criteria fields included for transparency

## Next Steps

After generation, you can:

1. **Review CSV in Excel/Google Sheets**: Sort, filter by criteria
2. **Read validation report**: Understand why businesses were excluded
3. **Share with team**: Send timestamped files for review
4. **Compare runs**: Track improvements over multiple generations

## Technical Notes

- Export modules: `src/exports/csv_exporter.py`, `src/exports/report_generator.py`
- Integration: `src/pipeline/smart_discovery_pipeline.py` (auto_export method)
- Database: SQLite with full observation/validation tracking
- Format: UTF-8 encoding for all files
