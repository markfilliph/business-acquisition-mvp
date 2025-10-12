# DATA SOURCE ANALYSIS - Business Lead Generation

**Date:** October 2, 2025
**Status:** Sources Evaluated & Recommendations

---

## 🔍 SOURCES TESTED

### 1. ✅ OpenStreetMap (OSM)
**Status:** WORKING
**Data Quality:** Low-Medium
**Coverage:**
- ✅ Business names: 100%
- ✅ Addresses: 100%
- ❌ Phone: ~10% (very limited)
- ❌ Website: ~25% (limited)
- ❌ Employee count: 0%
- ❌ Years in business: 0%

**Pros:**
- Free, no API key required
- Real-time data
- No rate limits
- No blocking

**Cons:**
- Very incomplete data (designed for maps, not business directories)
- No financial or employee data
- Many businesses missing

---

### 2. ❌ YellowPages.ca
**Status:** BLOCKED (403 Forbidden)
**Anti-Scraping:** YES - Strong protections

**Error:** All requests return HTTP 403
```
yellowpages_request_failed status=403
```

**Would provide:**
- Business name, address, phone
- Website, category
- Sometimes hours, reviews

**Recommendation:** Would need:
- Rotating proxies
- Browser automation (Selenium/Playwright)
- CAPTCHA solving
- Or official API access (if available)

---

### 3. ❌ Hamilton Chamber of Commerce
**Status:** DNS/CONNECTION ERROR
**URL:** business.hamiltonchamber.ca

**Error:**
```
Cannot connect to host business.hamiltonchamber.ca:443
Name or service not known
```

**Issue:** URL may be incorrect or site may be down

**Actual URL to try:** https://www.hamiltonchamber.ca/member-directory/

---

### 4. ❌ Better Business Bureau (BBB)
**Status:** BLOCKED (403 Forbidden)
**Anti-Scraping:** YES

**Error:** HTTP 403 on search pages

**Would provide:**
- Business name, address
- BBB rating/accreditation
- Customer reviews
- Sometimes phone

---

### 5. ❌ Canada411
**Status:** CODE ERROR (missing import)
**Issue:** Missing `quote` import from `urllib.parse`

**Would provide:**
- Business listings
- Phone numbers
- Addresses

---

### 6. ❌ Yelp
**Status:** CODE ERROR + Anti-Scraping
**Issue:** Missing `quote` import + Yelp has strong anti-scraping

**Would provide:**
- Business listings
- Reviews, ratings
- Photos, hours

---

## 💡 RECOMMENDED SOLUTIONS

### Option 1: Use Google Places API (BEST) ⭐
**Status:** Requires API key
**Cost:** Pay-per-use (~$17 per 1000 Place Details requests)

**Provides:**
- Business name, address, phone ✅
- Website ✅
- Google ratings/reviews ✅
- Opening hours ✅
- Photos ✅
- **Sometimes:** Employee count (from Google Business Profile)

**Implementation:**
```python
import googlemaps

gmaps = googlemaps.Client(key='YOUR_API_KEY')

# Search for businesses
places = gmaps.places_nearby(
    location=(43.2557, -79.8711),  # Hamilton
    radius=10000,  # 10km
    type='establishment'
)

# Get details
for place in places['results']:
    details = gmaps.place(place['place_id'])
    # Extract: name, address, phone, website, etc.
```

**Setup:**
1. Get API key from Google Cloud Console
2. Enable Places API
3. Set up billing (free tier: $200/month credit)

---

### Option 2: LinkedIn Sales Navigator API
**Provides:**
- Company data
- Employee count ✅✅✅ (ACCURATE)
- Founding year ✅
- Industry, size
- Key contacts

**Cost:** Enterprise pricing (expensive)

---

### Option 3: Ontario Business Registry
**Source:** https://www.ontario.ca/page/ontario-business-registry
**Provides:**
- Incorporation date ✅
- Business name
- Business number
- Legal status

**Data:** Reliable but limited (no employee count, no revenue)

---

### Option 4: Industry Canada Business Registry
**Source:** https://ised-isde.canada.ca/
**Provides:**
- Federal incorporation data
- Business numbers
- Legal information

---

### Option 5: Manual Enhancement Workflow
**Use existing OSM leads + manual research**

For each lead:
1. Visit website → Extract "About Us" for:
   - Employee count clues ("team of X")
   - Founding year ("since YYYY", "established YYYY")
2. LinkedIn company page → Employee count
3. Google Business Profile → Reviews, photos, hours
4. Phone outreach → Verify data directly

---

## 📊 CURRENT BEST APPROACH

### Hybrid Solution:

1. **Generate leads from OSM** (free, works now)
   - Get: name, address, sometimes phone/website

2. **Enrich with Google Places API** (paid but worth it)
   - Add: verified phone, website, ratings, hours

3. **Website scraping** (for leads with websites)
   - Extract: "Since YYYY", "Team of X employees"
   - Look for: About Us, Team, History pages

4. **LinkedIn lookup** (manual or API if available)
   - Get: Employee count from LinkedIn company page

5. **Manual verification** (for top 20-50 leads)
   - Call to verify phone
   - Visit website to confirm active
   - Research on Google

---

## 🎯 ACTION PLAN FOR 20 HIGH-QUALITY LEADS

### Phase 1: Data Collection (Automated)
```bash
# Use existing OSM leads
python3 src/pipeline/quick_generator.py 50
# Generates 50 leads with basic data
```

### Phase 2: Google Places Enhancement (Semi-Automated)
```python
# For each OSM lead:
# 1. Search Google Places by name + address
# 2. Get Place ID
# 3. Fetch Place Details (phone, website, etc.)
# 4. Merge with OSM data
```

### Phase 3: Website Scraping (Automated)
```python
# For leads with websites:
# 1. Fetch website HTML
# 2. Search for patterns:
#    - "since 19XX" or "since 20XX"
#    - "team of X" or "X employees"
#    - "founded in YYYY"
# 3. Extract and save
```

### Phase 4: Manual Research (Top 20)
```
For each of the top 20 qualified leads:
1. Visit LinkedIn company page
   → Note employee count
2. Visit website About page
   → Verify founding year
3. Google the business
   → Check recent news, verify still operating
4. Call business (optional)
   → Verify contact info
```

---

## 💰 COST ANALYSIS

### Google Places API:
- **Cost:** ~$17 per 1000 Place Details requests
- **For 20 leads:** $0.34 (negligible)
- **For 100 leads:** $1.70
- **For 1000 leads:** $17

**Verdict:** Worth it for quality data

### LinkedIn Sales Navigator:
- **Cost:** $99/month (individual) to $1000s/month (enterprise)
- **Verdict:** Expensive, only if scaling to 1000s of leads

### Manual Research:
- **Cost:** Your time (~5-10 min per lead)
- **For 20 leads:** 2-3 hours
- **Verdict:** Worth it for critical missing data

---

## ✅ RECOMMENDATION

**For 20 qualified leads RIGHT NOW:**

1. Use the 20 leads already generated from OSM ✅
2. Get Google Places API key (free $200 credit)
3. Enhance those 20 leads with Google data
4. Manually research the top 20 on LinkedIn/websites
5. Result: 20 leads with maximum verified data

**Files already generated:**
- `output/quick_leads_20251002_085947.json` - 20 OSM leads
- `output/NEW_20_LEADS_SUMMARY_20251002.txt` - Summary

**Next step:**
1. Get Google API key
2. Create enhancement script
3. Run enhancement on existing 20 leads
4. Manual verification

---

## 📝 CONCLUSION

**Reality:** Professional business data is:
- Protected by anti-scraping measures (YellowPages, BBB, Yelp)
- Expensive to access (LinkedIn, paid APIs)
- Requires manual effort for completeness

**Best path forward:**
- OSM for initial discovery (free, works)
- Google Places for enrichment (cheap, worth it)
- Website scraping for specific fields
- Manual research for critical data
- Quality over quantity

**We already have 20 real, validated businesses from OSM. The missing piece is employee count and years - best obtained through Google Places API + manual research.**
