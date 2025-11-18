# Phase 2 Lead Generation - Deployment Guide

**Status:** ✅ Production-Ready
**Version:** 2.0
**Expected Qualification Rate:** 62-65%
**Cost Savings:** 25-30% vs Phase 1

---

## Quick Start

### Generate 50 Manufacturing Leads
```bash
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry manufacturing
```

### Generate Leads for Other Industries
```bash
# Wholesale
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry wholesale

# Printing
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry printing

# Equipment Rental
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry equipment_rental

# Professional Services
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry professional_services

# Machining (specialized manufacturing)
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry machining
```

---

## What Phase 2 Does

### 1. Pre-Qualification (BEFORE Enrichment)
Filters out bad leads before wasting API calls:
- ❌ Chains/franchises (Mondelez, Costco, Sunbelt, etc.)
- ❌ Too few reviews (<2) - Not established
- ❌ Too many reviews (>500) - Likely a chain
- ❌ No website - Not B2B ready
- ❌ Manufacturing in office buildings - Location mismatch

### 2. Smart Search Queries
Uses refined, size-indicating queries instead of broad searches:
- "metal fabrication Hamilton ON" instead of just "manufacturing"
- "independent printing Hamilton ON" to avoid chains
- "local equipment rental Hamilton ON" for SMBs

### 3. Post-Filtering
Final quality checks after pre-qualification:
- Size filters (not too small, not too large)
- Retail detection (no e-commerce platforms)
- Location label detection (no "site" or placeholder listings)

### 4. Priority Assignment
- **HIGH Priority:** No warnings, ready for immediate outreach
- **MEDIUM Priority:** Has warnings, needs manual review before outreach

---

## Output Files

Each run creates 2 files in `data/outputs/`:

### 1. Qualified Leads CSV
**Filename:** `PHASE2_LEADS_{industry}_{timestamp}.csv`

**Contains:**
- Business Name
- Full Address (Street, City, Province, Postal Code)
- Phone & Website
- Industry Classification
- Review Count & Rating
- Warnings (if any)
- Priority (HIGH/MEDIUM)

**Example:**
```csv
Business Name,Street Address,City,Province,Postal Code,Phone,Website,Industry,Review Count,Rating,Warnings,Priority
Denninger's Manufacturing Facility,285 Kenilworth Ave N,Hamilton,ON,L8H 4R9,(905) 549-8555,http://www.denningers.com/,manufacturing,7,4.4,None,HIGH
Karma Candy Inc,181 Barton St E,Hamilton,ON,L8L 2W8,(905) 527-8100,http://www.karmacandy.ca/,manufacturing,77,3.9,HIGH_VISIBILITY: 20+ reviews suggests larger operation,MEDIUM
```

### 2. Rejections CSV
**Filename:** `PHASE2_REJECTIONS_{industry}_{timestamp}.csv`

**Contains:**
- Business Name
- Website
- Industry
- Rejection Stage (PRE_QUALIFICATION or POST_FILTER)
- Rejection Reason

**Example:**
```csv
Business Name,Website,Industry,Rejection Stage,Rejection Reason
Mondelez Canada,http://www.mondelezinternational.com/,manufacturing,PRE_QUALIFICATION,Chain keyword: 'mondelez'
The Cotton Factory,http://www.cottonfactory.ca/,manufacturing,PRE_QUALIFICATION,Too many reviews (784), likely chain
Container57,http://container57.myshopify.com/,manufacturing,POST_FILTER,RETAIL: E-commerce platform detected: shopify.com
```

---

## Understanding the Results

### Expected Performance

**Typical Run (50 target leads):**
```
Total discovered:        80 businesses
Pre-qualified:           54 businesses (67.5%)
Rejected pre-qual:       22 businesses (27.5%)
Final qualified:         50 businesses (62.5%)

API calls saved:         22 (27.5% efficiency)
```

### Priority Breakdown

**HIGH Priority (30%):**
- No warnings
- Ready for immediate outreach
- Clean data, established businesses
- **Action:** Start outreach immediately

**MEDIUM Priority (70%):**
- Has warnings (usually HIGH_VISIBILITY from review count)
- Needs manual review
- **Action:** Review warnings, verify if acceptable

### Common Warnings

**HIGH_VISIBILITY:**
```
"HIGH_VISIBILITY: 20+ reviews suggests larger operation or chain. Verify this is single-location SMB."
```
**What it means:** Business has many reviews (20-200 range)
**Action:** Quick check - is it a chain or just popular local business?

**Example:**
- Karma Candy (77 reviews) - Local candy manufacturer, NOT a chain ✅
- Wholesale Club (379 reviews) - National chain, correctly filtered ❌

---

## Daily Operations

### Recommended Daily Workflow

**Morning (30 minutes):**
```bash
# Generate 25 leads in your target industry
./venv/bin/python scripts/generate_leads_phase2.py --target 25 --industry manufacturing

# Output: PHASE2_LEADS_manufacturing_YYYYMMDD_HHMMSS.csv
```

**Afternoon (1-2 hours):**
1. Open the qualified leads CSV
2. Start with HIGH priority leads (outreach immediately)
3. Review MEDIUM priority leads:
   - Check websites
   - Verify not a chain
   - Assess if fits criteria
4. Begin outreach

**Weekly:**
```bash
# Generate mixed industries (20 each)
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry manufacturing
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry wholesale
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry printing

# Result: 60 qualified leads across 3 industries
```

---

## Performance Tracking

### Metrics to Monitor

Track these for each batch:

**1. Qualification Rate**
```
Qualified Leads / Total Discovered × 100
Target: 60-65%
```

**2. Pre-Qualification Pass Rate**
```
Pre-Qualified / Total Discovered × 100
Target: 65-70%
```

**3. API Efficiency**
```
Rejected Pre-Qual / Total Discovered × 100
Target: 25-30% savings
```

**4. Priority Distribution**
```
HIGH Priority / Total Qualified × 100
Target: 25-35%
```

**5. Outreach Conversion**
```
Responses / Outreach Attempts × 100
Track over time (business metric)
```

---

## Troubleshooting

### Issue: Low Qualification Rate (<50%)

**Possible Causes:**
1. Industry-specific - Some industries naturally harder
2. Google Places returning different results
3. Filters too aggressive

**Solutions:**
```bash
# Check rejections file
cat data/outputs/PHASE2_REJECTIONS_*.csv

# Look for patterns
# If many "Too few reviews" → Lower review threshold
# If many chains → Working as designed
# If many "No website" → May need to relax for certain industries
```

### Issue: Too Many MEDIUM Priority Leads

**Cause:** Most businesses have 20+ reviews

**Solution:**
- This is expected! 70% MEDIUM is normal
- Focus manual review time efficiently
- HIGH_VISIBILITY warning usually means "verify it's local"

### Issue: Not Finding Enough Leads

**Cause:** Industry may be small in Hamilton area

**Solutions:**
```bash
# Increase target
./venv/bin/python scripts/generate_leads_phase2.py --target 100 --industry manufacturing

# Or try related industries
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry machining
```

---

## Cost Analysis

### API Call Breakdown (per 100 qualified leads)

**Old Pipeline (Phase 1):**
- Discover: ~222 businesses
- Enrich: 222 API calls
- Qualify: 100 leads
- **Cost:** 222 API calls

**Phase 2 Pipeline:**
- Discover: ~160 businesses
- Pre-filter: ~108 pass (52 rejected)
- Enrich: 108 API calls
- Qualify: 100 leads
- **Cost:** 108 API calls

**Savings:** 114 API calls (51% reduction)

### Monthly Cost Projection

**Target: 1,000 qualified leads/month**

| Pipeline | API Calls | Cost (@$0.10/call) | Savings |
|----------|-----------|-------------------|---------|
| Phase 1 | 2,222 | $222 | - |
| Phase 2 | 1,088 | $109 | $113/month |

**Annual Savings:** $1,356

---

## Advanced Usage

### Custom Target Sizes

**Small Test Batch:**
```bash
./venv/bin/python scripts/generate_leads_phase2.py --target 10 --industry manufacturing
```

**Large Production Batch:**
```bash
./venv/bin/python scripts/generate_leads_phase2.py --target 100 --industry manufacturing
```

### Multiple Industries in One Run

**Option 1: Shell Script**
```bash
#!/bin/bash
# generate_all_industries.sh

for industry in manufacturing wholesale printing equipment_rental professional_services
do
    echo "Generating leads for $industry..."
    ./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry $industry
    sleep 5  # Rate limiting between batches
done
```

**Option 2: Sequential Commands**
```bash
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry manufacturing && \
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry wholesale && \
./venv/bin/python scripts/generate_leads_phase2.py --target 20 --industry printing
```

---

## Data Management

### File Organization

**Keep Last 30 Days:**
```bash
# Move old files to archive
mkdir -p data/outputs/archive/2025-11
mv data/outputs/PHASE2_LEADS_*_202511*.csv data/outputs/archive/2025-11/
```

**Combine Multiple Batches:**
```bash
# Combine all manufacturing leads from November
cat data/outputs/PHASE2_LEADS_manufacturing_202511*.csv > data/outputs/COMBINED_MANUFACTURING_NOV2025.csv
```

---

## Integration with CRM

### Import to Excel/Google Sheets
1. Open CSV file in Excel
2. Data → Text to Columns → Comma delimited
3. Format as table
4. Sort by Priority (HIGH first)

### Import to CRM
Most CRMs support CSV import with these standard fields:
- Business Name → Company Name
- Phone → Phone Number
- Website → Website URL
- Street Address, City, Province, Postal Code → Address fields

---

## Best Practices

### 1. Run During Off-Peak Hours
```bash
# Schedule for early morning (less API contention)
crontab -e

# Run at 6 AM daily
0 6 * * * cd /path/to/project && ./venv/bin/python scripts/generate_leads_phase2.py --target 25 --industry manufacturing
```

### 2. Version Control Your Results
```bash
# Create a leads branch
git checkout -b leads/2025-11

# Add results (but not .csv to main branch, use .gitignore)
git add docs/analysis/
git commit -m "Phase 2 results for November 2025"
```

### 3. Monitor Rejection Patterns
```bash
# Weekly review of rejections
grep -h "Chain keyword" data/outputs/PHASE2_REJECTIONS_*.csv | sort | uniq -c

# Identify new chains to add to filter
```

### 4. A/B Test Lead Quality
- Week 1: Use Phase 2 leads, track response rate
- Compare to previous leads
- Adjust if needed

---

## Next Steps

### Week 1: Initial Production Run
```bash
# Day 1: Manufacturing (your core)
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry manufacturing

# Day 2: Wholesale
./venv/bin/python scripts/generate_leads_phase2.py --target 30 --industry wholesale

# Day 3: Equipment Rental
./venv/bin/python scripts/generate_leads_phase2.py --target 30 --industry equipment_rental

# Total: 110 qualified leads
```

### Week 2-4: Validate & Iterate
- Track outreach response rates
- Note any patterns in qualified leads
- Adjust filters if needed

### Month 2: Scale Up
- Increase to 200+ leads/week
- Automate with cron jobs
- Build feedback loop

---

## Support

**Documentation:**
- This guide: `docs/guides/PHASE2_DEPLOYMENT_GUIDE.md`
- Results analysis: `docs/analysis/PHASE2_FINAL_RESULTS.md`
- Risk analysis: `docs/analysis/PHASE3_RISKS_ANALYSIS.md`

**Script Location:**
- `scripts/generate_leads_phase2.py`

**Data Location:**
- Output: `data/outputs/PHASE2_LEADS_*.csv`
- Rejections: `data/outputs/PHASE2_REJECTIONS_*.csv`

---

## Summary

**Phase 2 is now your production pipeline.**

**Key Benefits:**
- ✅ 62.5% qualification rate (vs 45% in Phase 1)
- ✅ 27.5% API cost savings
- ✅ Automatic chain detection
- ✅ Better lead quality
- ✅ Production-ready and tested

**Get Started:**
```bash
./venv/bin/python scripts/generate_leads_phase2.py --target 50 --industry manufacturing
```

**Expected Result:** 50 qualified leads, ready for outreach, in 2-3 minutes.

Good luck! 🚀
