# Data Collection Guide - Your Tasks (3 Hours)

**Goal:** Collect 150-250 Hamilton-area manufacturers/wholesalers from FREE sources
**Time Required:** 2-3 hours
**Tools Built:** ✅ Franchise detector, ✅ Validation pipeline (ready to use!)

---

## 📋 TASK 1: TrilliumGIS - Ontario Manufacturers (1.5-2 hours)

### What is TrilliumGIS?
- **FREE government-supported** directory of 20,000+ Ontario manufacturers
- Interactive map interface
- Shows company details, products, employee count

### Step-by-Step Instructions

#### Step 1: Register for FREE Account
1. Go to: https://www.trilliumgis.com/ (or search "TrilliumGIS Ontario manufacturers")
2. Click "Register" or "Sign Up"
3. Fill in basic details (name, email, company - you can say "Business Consultant")
4. Verify email and log in

#### Step 2: Search Hamilton Area
1. Once logged in, you'll see an interactive map of Ontario
2. **Zoom** to Hamilton, Ontario area
3. Look for filters or search options:
   - Location/City: "Hamilton"
   - Or manually click on Hamilton area on map

#### Step 3: Filter by Business Size (If Available)
- Look for filters like:
  - Employee Count: 5-50 employees
  - Company Size: Small to Medium
- If no size filter, that's OK - we'll filter later

#### Step 4: Collect Company Data
For each company in Hamilton area, collect:
- ✅ **Business Name** (required)
- ✅ **Address** (street, city)
- ✅ **Industry/Product Type** (required)
- ✅ **Phone Number**
- ✅ **Website** (if available)
- ✅ **Employee Count** (if shown)
- ✅ **Year Founded** (if shown)

#### Step 5: Export or Manual Collection

**Option A: If TrilliumGIS has "Export" feature (BEST)**
1. Select all Hamilton-area companies
2. Click "Export to CSV" or "Download"
3. Save as: `data/trilliumgis_manufacturers.csv`

**Option B: Manual Collection (if no export)**
1. Open a spreadsheet (Excel or Google Sheets)
2. Create columns:
   ```
   business_name | street | city | province | phone | website | industry | employees | year_founded | source
   ```
3. Copy data for each company (aim for 50-100)
4. Save as CSV: `data/trilliumgis_manufacturers.csv`

### Expected Format
```csv
business_name,street,city,province,phone,website,industry,employees,year_founded,source
ABC Manufacturing,123 Main St,Hamilton,ON,(905) 555-1234,https://abcmfg.com,Industrial Equipment,25,1995,TrilliumGIS
XYZ Wholesale,456 King St,Hamilton,ON,(905) 555-5678,https://xyzwholesale.ca,Food Distribution,15,2000,TrilliumGIS
```

### Tips
- Focus on Hamilton, Dundas, Ancaster, Stoney Creek
- Look for: Manufacturing, Wholesale, Distribution, Industrial
- **Avoid:** Restaurants, retail stores, skilled trades
- Target older businesses if you can see founding dates

### Expected Yield
- **100-200 manufacturers** in Hamilton area
- **Goal:** Collect at least 50-100

---

## 📋 TASK 2: Canadian Importers Database (10 minutes!) ⚡ AUTOMATED

### What is Canadian Importers Database?
- **FREE government database** (Innovation, Science and Economic Development Canada)
- Lists companies importing goods into Canada
- Importers = usually wholesale/distribution businesses (EXACTLY what you want!)

### ⚡ SEMI-AUTOMATED PROCESS (Much Faster!)

I've built a processor script that automatically filters the data for Hamilton. You just download ONE file!

### Step-by-Step Instructions

#### Step 1: Download the CSV File
1. Go to: **https://open.canada.ca/data/en/dataset/2e7c5a58-986f-402c-9dec-a45e0dadf8dd**
2. Look for: **"Major Importers by city"** CSV file
3. Click the download link
4. Save to: `/mnt/d/AI_Automated_Potential_Business_outreach/data/canadian_importers_raw.csv`

#### Step 2: Run the Processor Script (AUTOMATED!)
```bash
python scripts/process_canadian_importers.py
```

That's it! The script will:
- ✅ Load the CSV (handles bilingual French/English columns)
- ✅ Filter for Hamilton, Dundas, Ancaster, Stoney Creek, Burlington, Waterdown
- ✅ Filter for Ontario only
- ✅ Remove duplicates
- ✅ Standardize columns
- ✅ Export to: `data/canadian_importers_hamilton.csv`

### Expected Output Format
```csv
business_name,city,province,postal_code,product,country,industry,source
Hamilton Import Co,Hamilton,ON,L8P 1A1,Food products,USA,Wholesale Importer,Canadian Importers Database
Great Lakes Distribution,Hamilton,ON,L8N 2Z7,Industrial supplies,China,Wholesale Importer,Canadian Importers Database
```

### Expected Yield
- **30-100+ Hamilton-area importers** (depends on database year)
- **Time Required:** 10 minutes (vs 1 hour manual!)
- **Data Quality:** Government-verified importers

---

## 📋 OPTIONAL TASK 3: Scott's Directories FREE Trial (30-45 minutes)

### What is Scott's Directories?
- **Premium B2B database** with FREE TRIAL
- Best quality data (verified, updated monthly)
- Hamilton-specific manufacturing directory

### Worth Doing If:
- You want the highest quality data
- You can complete during trial period
- You have time

### Step-by-Step Instructions

#### Step 1: Sign Up for Free Trial
1. Go to: https://www.scottsdirectories.com/
2. Click "Free Trial" or "Try Free"
3. Fill in registration (name, email, company)
4. They may ask for credit card (cancel before trial ends if you don't want to pay)

#### Step 2: Search Hamilton Manufacturers
1. Once in trial, go to Search
2. Filters:
   - **Location:** Hamilton, Ontario
   - **Categories:** Manufacturing, Wholesale, Distribution
   - **Employee Count:** 5-50 (if available)
   - **Year Established:** 2010 or earlier (if available)

#### Step 3: Export Data
1. Select all results
2. Click "Export to CSV" or "Download"
3. Save as: `data/scotts_directory_hamilton.csv`

### Expected Yield
- **50-100 verified Hamilton businesses**
- Highest quality (phone, email, revenue estimates included)

---

## 📁 File Organization

After collection, you should have:

```
data/
├── trilliumgis_manufacturers.csv          (50-100 records)
├── canadian_importers_hamilton.csv        (30-60 records)
├── scotts_directory_hamilton.csv          (optional, 50-100 records)
└── (your existing files)
```

### Minimum Required Columns in Each CSV:
- `business_name` - Company name (REQUIRED)
- `street` or `address` - Street address
- `city` - City name
- `province` - ON
- `phone` - Phone number (if available)
- `website` - Website URL (if available)
- `industry` - Business type/industry

**Don't worry if some columns are missing - the validation pipeline will handle it!**

---

## ✅ What to Do When You're Done

### Step 1: Notify Me
Send a message: "Data collection complete - I have X files"

### Step 2: I'll Run the Validation Pipeline
```bash
# I'll run this command:
python scripts/validation_pipeline_v2.py \
  --sources data/trilliumgis_manufacturers.csv data/canadian_importers_hamilton.csv \
  --output data/QUALIFIED_LEADS_BATCH_1.csv
```

### Step 3: Pipeline Will:
1. ✅ Load all your data
2. ✅ Standardize column names
3. ✅ Remove duplicates
4. ✅ Filter out non-profits, restaurants, retail
5. ✅ Check for franchises (using detector we built)
6. ✅ Score each lead (0-100)
7. ✅ Rank and export top 20-30 qualified leads

### Expected Output:
**`data/QUALIFIED_LEADS_BATCH_1.csv`** - 20-30 ready-to-contact businesses

---

## 🎯 Success Criteria

### Good Collection:
- ✅ 50+ businesses from TrilliumGIS
- ✅ 20+ businesses from Importers DB
- ✅ Mix of manufacturing, wholesale, distribution
- ✅ Hamilton/Dundas/Ancaster area
- ✅ Most have websites and phone numbers

### Great Collection:
- ✅ 100+ businesses from TrilliumGIS
- ✅ 30+ businesses from Importers DB
- ✅ Included year founded / employee count data
- ✅ Diverse industries (not all same type)

---

## ❓ Troubleshooting

### Q: TrilliumGIS requires company affiliation?
**A:** Say you're a "Business Consultant" or "Market Researcher"

### Q: Can't find export feature in TrilliumGIS?
**A:** Manual copy-paste to spreadsheet is OK. Aim for 50-100 companies.

### Q: Canadian Importers Database has no Hamilton results?
**A:** Try broader search (Golden Horseshoe, Southern Ontario) then filter manually for Hamilton addresses

### Q: Don't have time for all sources?
**A:** Priority order:
   1. TrilliumGIS (BEST for manufacturers)
   2. Canadian Importers (BEST for wholesale/distribution)
   3. Scott's Directories (optional nice-to-have)

### Q: My CSV has different column names?
**A:** That's OK! The validation pipeline automatically maps common variations like:
   - "Company" → "business_name"
   - "Address" → "street"
   - "Category" → "industry"

---

## 📞 Quick Help

**If you get stuck:**
1. Take a screenshot of where you're stuck
2. Send me a message
3. I'll help you through it

**When you're done:**
- Put all CSV files in the `data/` folder
- Let me know
- I'll run the validation pipeline and we'll review the results together

---

## ⏱️ Time Estimate

- **TrilliumGIS:** 1.5-2 hours (100+ companies)
- **Importers DB:** 1 hour (30-60 companies)
- **Scott's Trial:** 30-45 min (optional)

**Total:** 2.5-3 hours for ~130-160 raw leads
**After validation:** 20-30 qualified leads

---

**Ready to start? Begin with TrilliumGIS first (biggest source). Good luck! 🚀**
