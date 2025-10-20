# Reliable Lead Generation Strategy

**Problem:** Current 15 leads have 27% false positives (non-profits, franchises, restaurants)
**Goal:** Build a reliable pipeline that generates 20-30 high-quality acquisition targets per month
**Target Industries:** Wholesale, Distribution, Manufacturing, Professional Services (NOT restaurants, skilled trades, retail chains)

---

## 🚨 Current Data Quality Issues

### Analysis Results (from scripts/analyze_lead_quality.py)
- **Total leads:** 15
- **Rejected:** 4 (27%) - Non-profits, franchises, restaurants
- **Questionable:** 5 more restaurants/bars (33%)
- **True viable leads:** ~5-6 (33-40%)

### Root Causes
1. **Wrong data source:** Google Places API returns ALL businesses (restaurants, bars, clubs)
2. **No franchise detection:** Multi-location businesses slip through
3. **No business type validation:** Restaurants/bars not flagged as high-risk
4. **Single source dependency:** Only using Google Places

---

## 🎯 Reliable Lead Generation Plan (4-Week Implementation)

### Week 1: Fix Current Data Quality (Priority 1)

#### Task 1A: Franchise/Corporate Detector
**File:** `scripts/franchise_detector.py`

**Detection methods:**
1. **URL patterns:** `/locations/`, `/find-a-store/`, `/branches/`
2. **Website scraping:** Look for "locations" page with multiple addresses
3. **Business name patterns:** "Ltd", "Inc", "Corporation", "Group"
4. **Phone patterns:** 1-800 numbers (national operations)
5. **Domain patterns:** corporate.com vs smallbusiness.com

**Output:** `is_franchise: bool`, `confidence: float`, `reason: str`

#### Task 1B: Business Type Classifier
**File:** `scripts/business_type_classifier.py`

**Categories:**
- ✅ **TARGET:** Wholesale, Distribution, Manufacturing, B2B Services
- ⚠️ **RISKY:** Restaurants, Retail, Food Service (require manual review)
- ❌ **EXCLUDE:** Non-profits, Government, Skilled Trades, Franchises

**Logic:**
- Parse business name + industry + website content
- Check against keyword lists
- Return classification + confidence score

---

### Week 2: Add High-Quality Data Sources (Priority 1)

**Problem:** Google Places API is too broad (finds restaurants, bars, clubs)
**Solution:** Target industry-specific directories

#### NEW Data Source #1: Canadian Business Directory (Canada411)
**Target:** `scripts/scraper_canada411.py`

**Why it's better:**
- Can filter by business category (wholesale, manufacturing)
- Shows employee count estimates
- Lists established businesses (not startups)

**Search filters:**
- Category: "Wholesale", "Distribution", "Manufacturing"
- Location: Hamilton, ON
- Established: 2010 or earlier (15+ years)

**Expected yield:** 50-100 businesses

#### NEW Data Source #2: Yellow Pages Canada
**Target:** `scripts/scraper_yellowpages.py`

**Why it's better:**
- Industry-specific categories
- Business age indicators
- Less cluttered with restaurants/retail

**Search filters:**
- Categories: "Wholesale Food", "Wholesale Goods", "Manufacturing", "Industrial Supplies"
- Location: Hamilton + surrounding areas
- Filter out: Individual consultants, home-based businesses

**Expected yield:** 30-60 businesses

#### NEW Data Source #3: Canadian Importers Database
**Target:** `scripts/scraper_importers_db.py`

**Why it's better:**
- Focuses on wholesale/distribution businesses
- These businesses have inventory, logistics, infrastructure (valuable)
- Already B2B focused (not consumer-facing)

**Source:** Canadian Importers Database (CIMB) or similar trade directories

**Expected yield:** 20-40 businesses

#### NEW Data Source #4: Hamilton Chamber of Commerce
**Target:** `scripts/scraper_hamilton_chamber.py`

**Why it's better:**
- Established businesses (members pay fees)
- Can filter by member category
- Often includes business age, employee count

**Expected yield:** 30-50 businesses

---

### Week 3: Build Validation & Scoring Pipeline (Priority 2)

#### Task 3A: Multi-Stage Validation Pipeline
**File:** `scripts/validation_pipeline.py`

**Stage 1: Data Collection**
- Run all scrapers (Canada411, Yellow Pages, Importers, Chamber)
- Collect 150-250 raw business records

**Stage 2: Deduplication**
- Match businesses across sources (same name + address)
- Merge data (take best phone, website, etc.)
- Expected: 100-150 unique businesses

**Stage 3: Exclusion Filters**
- Franchise detector (remove if confidence > 70%)
- Business type classifier (remove restaurants, retail, skilled trades)
- Non-profit detector (BIA, associations, clubs)
- Expected: 60-90 businesses remain

**Stage 4: Revenue Estimation**
- Use existing revenue estimation logic
- Filter: Revenue Midpoint $1M - $1.5M
- Expected: 20-40 businesses remain

**Stage 5: Enrichment**
- Years in business (must be 15+)
- Employee count (5-30)
- Website validation (must have working site)
- Expected: 15-25 qualified leads

**Stage 6: Scoring & Ranking**
- Score 0-100 based on criteria
- Rank by acquisition potential
- Output top 20 leads

#### Task 3B: Lead Scoring Algorithm
**File:** `scripts/lead_scorer_v2.py`

**Scoring rubric (0-100 points):**

| Criteria | Points | Logic |
|----------|--------|-------|
| **Industry Fit** | 0-25 | Wholesale/Distribution: 25, Manufacturing: 20, Services: 15, Other: 10 |
| **Business Age** | 0-20 | 25+ years: 20, 20-25: 15, 15-20: 10 |
| **Revenue Sweet Spot** | 0-20 | Midpoint $1.2-1.4M: 20, $1.0-1.2M: 15, $1.4-1.5M: 10 |
| **Revenue Confidence** | 0-10 | High confidence: 10, Medium: 7, Low: 3 |
| **Employee Count** | 0-10 | 10-25: 10, 5-10: 7, 25-30: 5 |
| **Website Quality** | 0-10 | Professional site: 10, Basic site: 5, Facebook only: 2 |
| **Data Completeness** | 0-5 | All fields: 5, Missing 1-2: 3, Missing 3+: 0 |
| **Multi-Source Verified** | 0-10 | Found in 3+ sources: 10, 2 sources: 5, 1 source: 0 |

**Total:** 100 points

**Lead tiers:**
- **A-Tier (80-100):** Immediate outreach priority
- **B-Tier (60-79):** Strong candidates, verify first
- **C-Tier (40-59):** Possible with more research
- **D-Tier (<40):** Low priority

---

### Week 4: Automation & Monitoring (Priority 3)

#### Task 4A: Automated Lead Generation
**File:** `scripts/automated_lead_gen.py`

**Schedule:** Run weekly (every Monday 6am)

**Workflow:**
1. Run all scrapers in parallel
2. Feed data through validation pipeline
3. Score and rank leads
4. Export top 20 to CSV
5. Send email notification with summary

**Configuration:** `config/lead_gen_config.yaml`
```yaml
schedule:
  frequency: weekly
  day: monday
  time: "06:00"

scrapers:
  canada411: true
  yellowpages: true
  importers_db: true
  hamilton_chamber: true
  google_places: false  # Disable - too noisy

filters:
  min_years: 15
  max_employees: 30
  revenue_min: 1000000
  revenue_max: 1500000
  revenue_strategy: midpoint  # strict | midpoint | min

  exclude_industries:
    - restaurants
    - bars
    - retail
    - skilled_trades

  target_industries:
    - wholesale
    - distribution
    - manufacturing
    - professional_services

scoring:
  min_score: 60  # B-tier or better

output:
  format: csv
  path: data/weekly_leads/
  notification_email: your@email.com
```

#### Task 4B: Data Quality Monitoring
**File:** `scripts/monitor_lead_quality.py`

**Metrics to track:**
- **Lead volume:** How many leads generated per week?
- **Acceptance rate:** % of leads that pass all filters
- **False positive rate:** % of leads flagged as non-targets upon manual review
- **Source quality:** Which scrapers produce best leads?
- **Industry distribution:** Are we getting too many of one type?

**Weekly report:**
```
===========================================
WEEKLY LEAD GENERATION REPORT
Week of: October 20-27, 2025
===========================================

VOLUME:
  • Raw leads collected: 187
  • After deduplication: 142
  • After validation: 68
  • After scoring (>60): 23
  • Top tier (>80): 7

SOURCE BREAKDOWN:
  • Canada411: 47 leads (33% acceptance rate)
  • Yellow Pages: 39 leads (41% acceptance rate) ⭐ BEST
  • Importers DB: 31 leads (58% acceptance rate) ⭐ BEST
  • Hamilton Chamber: 25 leads (52% acceptance rate)

INDUSTRY DISTRIBUTION:
  • Wholesale: 9 (39%)
  • Distribution: 6 (26%)
  • Manufacturing: 5 (22%)
  • Services: 3 (13%)

FALSE POSITIVES FOUND:
  • Franchises detected: 19
  • Restaurants detected: 12
  • Non-profits detected: 8
  • Revenue out of range: 27

ACTION ITEMS:
  ✓ Yellow Pages & Importers DB performing best - increase frequency
  ✗ Canada411 high false positive rate - review filters
  ✓ Good industry distribution - no changes needed

NEXT WEEK GOAL: 25+ qualified leads
===========================================
```

---

## 🛠️ Implementation Priority

### **PHASE 1: Fix Current Issues (This Week)**
1. ✅ Lead quality analyzer - DONE
2. 🔄 Franchise detector (Task 1A)
3. 🔄 Business type classifier (Task 1B)
4. 🔄 Re-run current leads through new filters

**Expected outcome:** Identify true viable leads from current 15

### **PHASE 2: New Data Sources (Week 2-3)**
1. 🔄 Canada411 scraper
2. 🔄 Yellow Pages scraper
3. 🔄 Importers database scraper
4. 🔄 Hamilton Chamber scraper

**Expected outcome:** 100-150 new raw leads

### **PHASE 3: Pipeline & Automation (Week 3-4)**
1. 🔄 Validation pipeline
2. 🔄 Scoring system v2
3. 🔄 Automated generation
4. 🔄 Quality monitoring

**Expected outcome:** 20-30 qualified leads per week automatically

---

## 📊 Success Metrics

### Current State (Before Implementation)
- **Lead sources:** 1 (Google Places API)
- **Leads per week:** ~15
- **Quality rate:** 33-40% (5-6 viable out of 15)
- **Manual effort:** High (manual filtering required)

### Target State (After Implementation)
- **Lead sources:** 4-5 (Canada411, Yellow Pages, Importers, Chamber)
- **Leads per week:** 20-30 qualified
- **Quality rate:** 70-80% (automated filtering)
- **Manual effort:** Low (review only, no filtering)

### Key Performance Indicators
- **Volume:** 80-120 qualified leads per month
- **Quality:** 70%+ acceptance rate after manual review
- **Efficiency:** <2 hours/week manual work
- **Cost:** <$100/month for API access (if needed)

---

## 🚀 Quick Start: Next 48 Hours

**Option 1: Fix Current Leads (Low effort, immediate value)**
```bash
# 1. Build franchise detector
claude-code "Create scripts/franchise_detector.py that checks websites for /locations/ URL patterns, scrapes for multiple addresses, and flags multi-location businesses"

# 2. Run on current 15 leads
python scripts/franchise_detector.py --input data/FINAL_15_QUALIFIED_LEADS_IMPROVED_REVENUE.csv

# 3. Manual review of remaining leads
# Focus outreach on the 2-3 most viable
```

**Option 2: Add One New Data Source (Medium effort, more leads)**
```bash
# 1. Build Canada411 scraper (easiest to scrape)
claude-code "Create scripts/scraper_canada411.py that searches Canada411.ca for Hamilton businesses in categories: wholesale, distribution, manufacturing. Filter by 15+ years old, export to CSV"

# 2. Run scraper
python scripts/scraper_canada411.py --category "Wholesale" --location "Hamilton, ON"

# 3. Run quality analyzer on results
python scripts/analyze_lead_quality.py --input data/canada411_leads.csv
```

**Option 3: Build Full Pipeline (High effort, best long-term)**
Follow the 4-week plan above. I can help implement each component step-by-step.

---

## 💡 Recommendations

### Immediate (Do now):
1. **Run franchise detector** on your current 15 leads
2. **Manual research** on top 2-3 leads (Fiddes, Traynor's, maybe 1 more)
3. **Test outreach** with those 2-3 before building more

### Short-term (Next 2 weeks):
1. **Add 1-2 new data sources** (Canada411 + Yellow Pages)
2. **Build validation pipeline** to automatically filter
3. **Get to 20-30 qualified leads** in pipeline

### Long-term (Month 2-3):
1. **Automate weekly generation** (set and forget)
2. **Track conversion metrics** (which sources → meetings → deals)
3. **Expand geographically** if Hamilton saturated (Mississauga, Burlington, Oakville)

---

## ❓ Decision Point: What's Your Preferred Approach?

**A) Conservative (2-3 days work)**
- Fix current 15 leads with better filtering
- Focus on top 2-3 for manual outreach
- Learn from first conversations before scaling

**B) Balanced (1-2 weeks work)**
- Add 1-2 new data sources
- Build basic validation pipeline
- Get to 20-30 leads before outreach

**C) Aggressive (3-4 weeks work)**
- Build full automated pipeline
- 4-5 data sources
- 50-100 leads per month automatically
- Scale outreach in parallel

**Which path makes sense for you?**
