# Historical Lead Data Archive

This folder contains all historical lead generation attempts and experiments from August-November 2025.

## Archive Organization

### oct2025_early/
**Dates:** October 13-15, 2025
**Purpose:** Initial testing and exploration of lead generation pipeline

**Contents:**
- Multiple test runs with different configurations
- Validation reports showing early filtering attempts
- Qualified leads from initial pipeline runs
- Summary reports documenting quality issues

**Key Files:**
- `LEAD_SUMMARY_REPORT.txt` - Early quality analysis
- `STRICT_VALIDATION_REPORT.txt` - Strict filtering experiments
- `leads_20251013_*.csv` - First test runs
- `leads_20251015_*.csv` - Multiple iterations (8 runs on Oct 15)
- `validation_report_*.txt` - Validation results for each run

**Notes:** High iteration count shows pipeline was being tuned and tested.

---

### oct2025_mid/
**Dates:** October 16, 2025
**Purpose:** 20-lead batch generation (the "original 20 leads")

**Contents:**
- Google Places API lead generation
- OpenStreetMap business data
- Qualified leads from semi-automated pipeline
- Hot leads JSON export

**Key Files:**
- `google_places_leads_20251016_194208.csv` - Original Google Places fetch
- `google_places_leads_enriched_20251016_214122.csv` - Enriched version
- `20_real_leads_openstreetmap_20251016_094200.csv` - OSM data
- `FINAL_20_QUALIFIED_LEADS_20251016_220131.csv` - Final qualified set
- `enriched_hot_leads.json` - Top leads in JSON format

**Notes:** This was the baseline 20-lead batch that later received filter analysis (now in `data/outputs/original_20_leads_oct2025/`).

---

### oct2025_late/
**Dates:** October 17-20, 2025
**Purpose:** Post-20-lead refinement and quality improvement

**Contents:**
- Lead quality analysis
- Additional qualification attempts
- Mid-point checkpoints
- Validation reports

**Key Files:**
- `LEAD_QUALITY_ANALYSIS.csv` - Quality scoring of leads
- `leads_20251017_173144.csv` - Large batch (28KB)
- `QUALIFIED_LEADS_BATCH_20251020_132800.csv` - Later qualification run
- `draft_emails.txt` - Outreach email templates
- `temp_importers_by_city.csv` - Canadian importers data experiment

**Notes:** Shows attempts to improve lead quality through stricter filtering.

---

### nov2025_early/
**Dates:** October 30 - November 3, 2025
**Purpose:** Validation experiments and candidate selection

**Contents:**
- LinkedIn verification candidates
- Improved revenue estimates
- Final validation attempts
- Large summary report (38KB)

**Key Files:**
- `CANDIDATES_FOR_LINKEDIN_VERIFICATION.csv` - Leads needing LinkedIn check
- `FINAL_15_QUALIFIED_LEADS_IMPROVED_REVENUE.csv` - Revenue-corrected leads
- `FINAL_VALIDATED_LEADS_20251103_165454.csv` - Last validation run before filter implementation
- `LEADS_SUMMARY_REPORT.txt` - Comprehensive 38KB analysis

**Notes:** Final attempts to manually validate leads before implementing automated filters.

---

## Timeline Summary

```
Aug 2025:    Initial acquisition profiles defined
Oct 13-15:   Pipeline testing and iteration (8+ test runs)
Oct 16:      20-lead batch generation ← Baseline dataset
Oct 17-20:   Quality refinement attempts
Oct 30-Nov 3: Validation experiments
Nov 15:      Filter system implemented ← Major milestone
Nov 16:      40 new leads generated with filters ← Current
```

## What Happened Next

After analyzing the Oct 16 20-lead batch quality issues:
- **Nov 15, 2025:** Implemented comprehensive filter system
  - Size filters (revenue $1.5M cap, 25 employees)
  - Retail detection filter (100% accuracy)
  - Location label filter (100% accuracy)
  - Warning system (92% accuracy)

- **Nov 16, 2025:** Generated 40 new leads with filters
  - 98.3% pass rate (vs 75% in original batch)
  - Only 2 exclusions (Container57, Emerald Site - same as before)
  - 19 HIGH priority, 21 MEDIUM priority

## Key Learnings from Historical Data

1. **Data Quality Issues:** Google Places employee counts are location-specific, not company-wide
2. **High Review Count = Red Flag:** 20+ reviews often indicate chains/franchises
3. **Shopify Stores:** Easy to detect (URL pattern), always retail
4. **Location Labels:** "Site", "Facility" keywords with no website = not real businesses
5. **Manual Review Burden:** Without filters, 50% of leads required deep manual review

## Current State

All historical data archived here. Current pipeline uses:
- `data/outputs/NEW_LEADS_40_20251116_121724.csv` - Latest 40 leads
- `data/outputs/original_20_leads_oct2025/` - Original 20-lead batch with filter analysis
- `src/filters/` - Production filter system
- `tests/filters/` - Comprehensive test suite (56 tests, all passing)

---

**Total Historical Files:** 50+ CSVs, reports, and validation files
**Date Range:** August 31 - November 3, 2025
**Purpose:** Learning, testing, validation experiments
**Status:** Archived for reference, superseded by filter system
