# Original 20-Lead Batch (October 2025)

This folder contains the original 20 business leads generated in October 2025 and the subsequent filter implementation analysis from November 2025.

## Timeline

- **October 16, 2025** - Initial lead generation from Google Places API
- **November 15, 2025** - Filter system implementation and retrospective analysis
- **November 16, 2025** - Files archived to this folder

## Contents

### Original Lead Data (October 16, 2025)

1. **google_places_SMARTLY_ENRICHED.csv** - Original 20 leads with smart enrichment
   - Revenue estimates (employee-based, multi-factor)
   - Employee counts (Google Places location data)
   - Industry classifications
   - Contact information

2. **google_places_FULLY_ENRICHED.csv** - Fully enriched version
   - Additional enrichment fields
   - Domain age lookups
   - Website validation

3. **FINAL_20_LEADS_SUMMARY.md** - Initial summary report
   - Overview of 20 leads
   - Quality assessment
   - Next steps

4. **CORRECTED_LEADS_SUMMARY.md** - Corrected analysis
   - Revenue estimate corrections
   - Employee count adjustments
   - Updated quality flags

5. **LEADS_SUMMARY_20251016_194208.md** - Timestamped summary
   - Original generation timestamp
   - Source attribution
   - Data quality metrics

### Filter Analysis (November 15, 2025)

6. **FILTER_VERDICT_COMPARISON_REPORT.md** - Comprehensive comparison
   - Lead-by-lead filter results vs manual verdict
   - Filter accuracy metrics (85% overall, 100% retail, 100% location)
   - Identified data quality issues (Google Places employee counts)
   - Exclusion breakdown (5 excluded, 15 passed)

7. **FILTER_RESULTS_SUMMARY.txt** - Quick reference summary
   - Filter performance stats
   - Pass/fail breakdown
   - Key findings

8. **MANUAL_REVIEW_CHECKLIST.txt** - Generated review tasks
   - 15 leads requiring manual review
   - 5-minute checklist per lead
   - Total estimated time: 75 minutes

## Key Findings

### Quality Issues Identified

1. **Container57** - Shopify retail store (should exclude)
2. **Emerald Manufacturing Site** - Location label, not business (should exclude)
3. **VP Expert Machining** - Revenue $2.0M > $1.5M cap (should exclude)
4. **Welsh Industrial** - Revenue $2.0M > $1.5M cap (should exclude)
5. **Stoney Creek Machine** - Revenue $1.9M > $1.5M cap (should exclude)

### Filter Performance

- **Size Filters**: 50% accuracy (3/6 oversized caught, limited by Google Places data quality)
- **Retail Filter**: 100% accuracy (1/1 caught - Container57)
- **Location Label Filter**: 100% accuracy (1/1 caught - Emerald Site)
- **Warning System**: 92% accuracy (11/12 edge cases flagged)
- **Overall**: 85% accuracy (17/20 correct verdicts)

### Data Quality Lessons

**Google Places Employee Limitation:**
- Returns LOCATION headcount, not company-wide
- Example: Karma Candy shows 16 employees (Hamilton location) vs 100-200 actual (SignalHire)
- Manual LinkedIn verification required for accurate sizing

**High Review Count = Red Flag:**
- 20+ reviews often indicates chains, franchises, or large operations
- Examples: Karma Candy (76 reviews), Ontario Ravioli (68 reviews)
- Added HIGH_VISIBILITY warning flag

### Improvements Made

Based on this analysis, the following improvements were implemented:

1. **Stricter Size Filters**
   - Revenue cap: $2M → $1.5M
   - Employee cap: 30 → 25

2. **Retail Business Filter**
   - Detects Shopify, BigCartel, Wix stores
   - Checks industry classifications
   - 100% accuracy on test data

3. **Location Label Filter**
   - Flags "Site", "Facility", "Complex" keywords
   - Requires website OR reviews to pass
   - 100% accuracy on test data

4. **Warning System**
   - HIGH_VISIBILITY (20+ reviews)
   - UPPER_RANGE (revenue >$1.2M)
   - VERIFY_SIZE (high employees + reviews)
   - NO_WEBSITE (harder due diligence)
   - NEW_BUSINESS / ESTABLISHED

5. **Manual Review Checklist Generator**
   - 5-minute systematic verification
   - Compliance check
   - LinkedIn employee validation
   - BBB profile lookup

## Verdict Summary

### Core A-List (6 leads - should keep)
- Abarth Machining Inc
- Stolk Machine Shop Ltd
- All Tool Manufacturing Inc
- Millen Manufacturing Inc
- North Star Technical Inc
- G.S. Dunn Ltd (with size warning)

### Exclude (5 leads)
- Container57 (retail)
- Emerald Manufacturing Site (location label)
- VP Expert Machining (too large)
- Welsh Industrial (too large)
- Stoney Creek Machine (too large)

### Review Required (9 leads - edge cases)
- Karma Candy Inc (high reviews, verify size)
- Ontario Ravioli (high reviews, verify size)
- Advantage Machining (upper revenue range)
- Felton Brushes (upper revenue range)
- Chapman Steel (potential size issue)
- Sasa (health violations)
- Denninger's (franchise concern)
- G.S. Dunn (global presence)
- Sweet & Simple Co (limited data)

## Usage

These files serve as:
1. **Historical reference** - Original lead generation baseline
2. **Filter validation** - Test dataset for filter accuracy
3. **Training data** - Known good/bad examples for future improvements
4. **Lessons learned** - Data quality insights for next batches

## Related Files

- Test suite: `tests/filters/`
- Filter implementation: `src/filters/`
- New 40-lead batch: `data/outputs/NEW_LEADS_40_20251116_121724.csv`

---

**Archived:** November 16, 2025
**Original Generation:** October 16, 2025
**Filter Analysis:** November 15, 2025
