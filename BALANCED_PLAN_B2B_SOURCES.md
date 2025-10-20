# Balanced Lead Generation Plan - B2B Sources

**Goal:** 20-30 qualified leads in 1-2 weeks using B2B-focused directories (NO Yellow Pages)
**Target:** Wholesale, Distribution, Manufacturing businesses in Hamilton, ON

---

## 🎯 Data Sources - B2B Focused

### ✅ Source #1: Canada411 (Already Planned)
**Type:** Commercial business directory
**Cost:** Free (web scraping) or API access
**Coverage:** All Canadian businesses
**Why useful:** Can filter by business category and location

**Pros:**
- Comprehensive coverage
- Shows years in business
- Contact information included

**Cons:**
- Still includes some consumer-facing businesses
- Need good filtering

---

### 🌟 Source #2: TrilliumGIS - Ontario Manufacturers Directory (FREE!)
**Website:** https://www.mentorworks.ca/blog/government-funding/ontario-manufacturers-directory/
**Type:** Government-supported interactive map
**Cost:** 100% FREE (requires free registration)
**Coverage:** 20,000+ Ontario manufacturers & research institutions

**Why this is EXCELLENT:**
✅ **B2B ONLY** - Manufacturing/industrial focus (no restaurants/bars/retail)
✅ **FREE** - Government funded, no scraping needed
✅ **HIGH QUALITY** - Verified manufacturers with real facilities
✅ **INTERACTIVE MAP** - Can filter by Hamilton area specifically
✅ **Company details** - Size, products, contact info

**Expected yield:** 100-200 Hamilton-area manufacturers

**Search strategy:**
1. Register for free account
2. Filter map to Hamilton/Burlington/Ancaster area
3. Filter by company size (5-30 employees)
4. Export list or manually collect top 50-100
5. Cross-reference with age (15+ years)

---

### 🌟 Source #3: Canadian Importers Database (FREE!)
**Website:** https://ised-isde.canada.ca/site/canadian-importers-database/en/canadian-importers-database
**Type:** Government of Canada database
**Cost:** 100% FREE
**Coverage:** Companies importing goods into Canada

**Why this is EXCELLENT:**
✅ **B2B FOCUSED** - Importers = Wholesale/Distribution businesses
✅ **GOVERNMENT VERIFIED** - Official records, not user-generated
✅ **REVENUE INDICATOR** - Import volume suggests business size
✅ **ESTABLISHED BUSINESSES** - Must be licensed to import

**Expected yield:** 30-60 Hamilton-area importers/wholesalers

**Search strategy:**
1. Search by city: Hamilton, ON
2. Look for food, goods, equipment importers
3. Filter by product categories matching our targets
4. Cross-reference with business registry for age

**Perfect for:** Wholesale food (like Fiddes), distribution companies

---

### 💰 Source #4: Scott's Directories - Hamilton Manufacturing (Paid Trial)
**Website:** https://www.scottsdirectories.com/canada-b2b-database/ontario/hamilton/manufacturing-directory
**Type:** Premium commercial database
**Cost:** FREE TRIAL available, then subscription
**Coverage:** 945,000+ Canadian B2B companies (with Hamilton-specific subset)

**Why this is EXCELLENT:**
✅ **HIGHEST QUALITY** - Verified, updated monthly
✅ **DETAILED PROFILES** - Employee count, revenue range, year founded, contacts
✅ **SEARCH FILTERS** - Can filter exactly what we need
✅ **FREE TRIAL** - Can extract data during trial period

**Expected yield:** 50-100 Hamilton manufacturers/wholesalers

**Search strategy:**
1. Sign up for free trial
2. Search: Hamilton, ON
3. Filters: Manufacturing, Wholesale, Distribution
4. Size: 5-30 employees
5. Founded: 2010 or earlier (15+ years)
6. Export to CSV during trial

**Alternative:** Canadian Company Capabilities (CCC) - 60,000 businesses, also free

---

## 📊 Data Source Comparison

| Source | Cost | B2B Focus | Quality | Yield | Effort |
|--------|------|-----------|---------|-------|--------|
| Canada411 | Free | Medium | Medium | 50-100 | Medium |
| **TrilliumGIS** | **FREE** | **VERY HIGH** | **HIGH** | **100-200** | **LOW** ⭐ |
| **Importers DB** | **FREE** | **VERY HIGH** | **VERY HIGH** | **30-60** | **LOW** ⭐ |
| Scott's Directories | Trial/Paid | Very High | Very High | 50-100 | Low |

**Recommendation:** Focus on TrilliumGIS + Importers DB (both FREE and high quality)

---

## 🛠️ Implementation Plan (1-2 Weeks)

### **Week 1: Build Core Tools**

#### Day 1-2: Franchise Detector
**File:** `scripts/franchise_detector.py`

```python
# Features:
- Check URL for /locations/, /find-a-store/
- Scrape website for multiple addresses
- Check phone number (1-800 = corporate)
- Look for "franchise" keyword
- Return: is_franchise (bool), confidence (float), reason (str)
```

**Usage:**
```bash
python scripts/franchise_detector.py --url "https://atlantic.ca/locations/"
# Output: is_franchise=True, confidence=0.95, reason="URL contains /locations/"
```

#### Day 3-4: Data Collection
**Manual collection from free sources:**

**TrilliumGIS (2 hours):**
1. Register at TrilliumGIS
2. Search Hamilton area manufacturers
3. Filter by size (5-30 employees if available)
4. Export or manually collect top 100 companies
5. Save to: `data/trilliumgis_manufacturers.csv`

**Canadian Importers Database (1 hour):**
1. Go to https://ised-isde.canada.ca/app/ixb/cid-bdic/importingCountry.html
2. Search by city: Hamilton
3. Export results to CSV
4. Save to: `data/canadian_importers_hamilton.csv`

**Optional - Scott's Directories Trial (1 hour):**
1. Sign up for free trial
2. Search Hamilton manufacturers/wholesalers
3. Export during trial
4. Save to: `data/scotts_directory_hamilton.csv`

**Expected total:** 150-250 raw business records

#### Day 5: Build Validation Pipeline
**File:** `scripts/validation_pipeline_v2.py`

**Pipeline stages:**
1. Load data from all sources
2. Deduplicate (match by name + address)
3. Run franchise detector
4. Run business type classifier (from earlier)
5. Filter revenue range (if available)
6. Filter years in business (15+)
7. Score and rank
8. Export top 20-30

```bash
python scripts/validation_pipeline_v2.py \
  --input data/trilliumgis_manufacturers.csv data/canadian_importers_hamilton.csv \
  --output data/VALIDATED_LEADS_BATCH_1.csv \
  --min-score 60
```

### **Week 2: Validation & Enrichment**

#### Day 6-7: Manual Verification
- Review top 30 leads
- Check websites manually
- Verify not franchises/chains
- Confirm revenue range estimates
- Mark 20-25 as "qualified"

#### Day 8-9: Enrichment
- Run enrichment tool on top 20
- Find owner names (LinkedIn, website)
- Find email addresses
- Score succession readiness

#### Day 10: Output & Ready for Outreach
- Export final 20-25 qualified leads
- Generate lead summaries
- Create outreach priority list

---

## 🚀 Quick Start: Next 48 Hours

### **TODAY: Collect Free Data**

**Task 1: TrilliumGIS (2 hours)**
```bash
# Manual steps:
1. Go to TrilliumGIS website
2. Register for FREE account
3. Search Hamilton area
4. Collect top 100 manufacturers
5. Save to spreadsheet

# Expected result:
data/trilliumgis_manufacturers.csv
- 100+ Ontario manufacturers
- Company name, address, products, size
```

**Task 2: Canadian Importers Database (1 hour)**
```bash
# Manual steps:
1. Go to https://ised-isde.canada.ca/site/canadian-importers-database/en
2. Search Hamilton, ON
3. Export results
4. Save to CSV

# Expected result:
data/canadian_importers_hamilton.csv
- 30-60 importing businesses (wholesale/distribution)
- Government verified
```

### **TOMORROW: Build Tools**

**Task 3: Franchise Detector (3 hours)**
```bash
# I'll create this script for you
python scripts/franchise_detector.py --batch data/trilliumgis_manufacturers.csv
```

**Task 4: Run Validation Pipeline (1 hour)**
```bash
# Combine sources + validate
python scripts/validation_pipeline_v2.py \
  --sources data/trilliumgis_manufacturers.csv data/canadian_importers_hamilton.csv \
  --output data/QUALIFIED_LEADS_BATCH_1.csv
```

---

## 📈 Expected Outcomes

### After Week 1:
- **Raw leads collected:** 150-250
- **After deduplication:** 100-150
- **After validation (franchise detection, etc.):** 50-80
- **After revenue/age filtering:** 20-30 qualified leads

### Lead Quality Prediction:
- **TrilliumGIS leads:** 70-80% quality (B2B focused)
- **Importers DB leads:** 80-90% quality (wholesalers by definition)
- **Combined:** 75-85% quality rate

**Much better than Google Places API (40% quality)**

---

## 💰 Cost Analysis

| Source | Cost | Leads | Cost per Lead |
|--------|------|-------|---------------|
| TrilliumGIS | $0 | 100+ | $0 |
| Importers DB | $0 | 30-60 | $0 |
| Scott's Trial | $0 | 50+ (during trial) | $0 |
| **TOTAL** | **$0** | **180-210** | **$0** |

**After filtering:** 20-30 qualified leads for $0

Compare to:
- Lead broker: $50-100 per lead = $1,000-3,000 for 20-30 leads
- Google Ads: $20-50 per click = highly variable
- LinkedIn Sales Navigator: $80/month + time

---

## ✅ Action Items for You

**Choose one:**

**Option A: DIY Data Collection (3-4 hours today)**
- Register for TrilliumGIS yourself
- Search Hamilton manufacturers
- Export to CSV
- Send me the CSV, I'll build the tools

**Option B: I Build Everything (1-2 days)**
- I create automated scrapers for all sources
- I build franchise detector
- I build validation pipeline
- You just review final 20-30 leads

**Option C: Hybrid (Recommended)**
- You collect TrilliumGIS + Importers DB manually (3 hours today)
- I build franchise detector + validation pipeline (tomorrow)
- Together we process and validate (day 3)

**Which option works best for you?**
