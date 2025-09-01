# Updated Business Acquisition Filtering Criteria

## 🎯 **MANDATORY REQUIREMENTS**

### **Revenue Range (STRICT)**
- **Minimum:** $1.0M CAD annually
- **Maximum:** $1.4M CAD annually
- **Rationale:** Sweet spot for management buyouts, owner-operator businesses

### **Years in Business (STRICT)**
- **Minimum:** 15 years
- **Maximum:** 40 years  
- **Rationale:** Established but not too entrenched, succession planning window

### **Company Size Benchmark: Campbell Glass & Mirror**
- **Employees:** 8-12 employees
- **Revenue:** ~$1.2M CAD
- **SDE:** $250-350K
- **Characteristics:** Long-term employee retention (10-20+ years)
- **Owner Structure:** Manny & Zena Fresco (husband/wife team)

### **Contact Information (MANDATORY)**
- **Phone Number:** Must have verified phone number, OR
- **Email Address:** Must have verified email address, OR  
- **Contact Form:** Professional website with contact form
- **EXCLUDE:** Any prospect without verified contact method

### **Location Requirements**
- **Primary:** Single location operations only
- **Geography:** Hamilton, Burlington, GTA, surrounding Ontario
- **EXCLUDE:** Multi-location, franchise, or chain operations

## 🚫 **EXCLUSION CRITERIA**

### **Industry Exclusions (CONFIGURABLE)**
```python
# Configurable exclusion variable for easy adjustment
EXCLUDE_CREATIVE_ARTISTIC = True  # Set to False to include creative businesses

if EXCLUDE_CREATIVE_ARTISTIC:
    EXCLUDED_INDUSTRIES = [
        "Art studios",
        "Design agencies", 
        "Creative services",
        "Custom artwork",
        "Artistic glasswork",
        "Decorative services",
        "Creative consulting"
    ]
else:
    EXCLUDED_INDUSTRIES = []
```

### **Business Type Exclusions**
- **High-tech/Software companies**
- **Retail/Consumer businesses**
- **Professional services** (lawyers, accountants, consultants)
- **Restaurants/Food service**
- **Creative/Artistic businesses** (when EXCLUDE_CREATIVE_ARTISTIC = True)

### **Size Exclusions**
- **Revenue over $1.4M** (too large)
- **Revenue under $1.0M** (too small/risky)
- **Over 15 employees** (unless exceptional circumstances)
- **Under 5 employees** (too small for acquisition)

### **Contact Exclusions**
- **No phone number AND no email AND no contact form**
- **Dead/broken websites**
- **Disconnected phone numbers**
- **Generic contact info only** (no specific business contact)

## ✅ **IDEAL PROSPECT PROFILE**

### **The Campbell Glass Model:**
- **Revenue:** $1.2M ± $200K
- **Employees:** 8-12 people
- **Years:** 20-35 years in business
- **Ownership:** Family-owned or founder-owned
- **Contact:** Direct phone + email + professional website
- **Location:** Single facility, local market focus
- **Industry:** Manufacturing, fabrication, specialized services
- **Succession:** Owners likely considering retirement/succession planning

### **Scoring Criteria (1-100)**
- **Revenue fit (1.0-1.4M):** 25 points
- **Years in business (15-40):** 20 points  
- **Employee count (8-15):** 15 points
- **Family/founder owned:** 15 points
- **Verified contacts:** 15 points
- **Single location:** 10 points

**Minimum qualifying score:** 75/100

## 📞 **CONTACT VERIFICATION REQUIREMENTS**

### **Phone Number Standards**
- **Format:** (XXX) XXX-XXXX or XXX-XXX-XXXX
- **Type:** Business landline preferred
- **Verification:** Must be active/answering
- **Location:** Local Hamilton/GTA area codes preferred

### **Email Standards** 
- **Format:** info@company.com, contact@company.com, or owner name
- **Domain:** Must match business website domain
- **Type:** Business email, not personal Gmail/Yahoo
- **Verification:** Domain must be active

### **Website Standards**
- **Professional appearance:** Clean, business-focused design
- **Recent updates:** Evidence of current maintenance
- **Contact form:** Functional contact mechanism
- **Business info:** Clear description of services/products

## 🔄 **FILTERING WORKFLOW**

### **Stage 1: Basic Qualification**
1. Check revenue range: $1.0M - $1.4M
2. Verify years in business: 15-40 years
3. Confirm single location
4. Verify contact information exists

### **Stage 2: Contact Verification**
1. Test phone number (if provided)
2. Verify email domain active (if provided)  
3. Check website functionality (if provided)
4. Confirm at least one contact method works

### **Stage 3: Industry Screening**
1. Apply creative/artistic exclusions (if enabled)
2. Check against excluded industry list
3. Verify manufacturing/service focus
4. Confirm B2B customer base

### **Stage 4: Scoring & Ranking**
1. Apply 6-factor scoring model
2. Calculate total score (1-100)
3. Rank prospects by score
4. Select top 10 for outreach

## 🎯 **IMPLEMENTATION VARIABLES**

```python
# Revenue filters (CAD)
MIN_REVENUE = 1000000  # $1.0M
MAX_REVENUE = 1400000  # $1.4M

# Age filters (years)
MIN_YEARS = 15
MAX_YEARS = 40

# Size filters (employees) 
MIN_EMPLOYEES = 5
MAX_EMPLOYEES = 15

# Contact requirements
REQUIRE_PHONE_OR_EMAIL = True
REQUIRE_WEBSITE = False  # Can be contact form instead

# Industry exclusions
EXCLUDE_CREATIVE_ARTISTIC = True  # Configurable toggle

# Geographic focus
TARGET_REGIONS = ["Hamilton", "Burlington", "GTA", "Southern Ontario"]

# Minimum qualification score
MIN_SCORE = 75
```

## 📊 **SUCCESS METRICS**

### **Quality Indicators:**
- **100% contact verification** (phone or email working)
- **90% revenue range compliance** ($1.0M-$1.4M)
- **100% age range compliance** (15-40 years)
- **80% family/founder owned** (succession opportunities)

### **Quantity Targets:**
- **10 qualified prospects** minimum for campaign
- **3 Tier 1** prospects (scores 90+)
- **4 Tier 2** prospects (scores 80-89)
- **3 Tier 3** prospects (scores 75-79)

**This filtering framework ensures we only pursue verified, contactable prospects that perfectly fit our acquisition criteria, using Campbell Glass as our size benchmark.**