# Practical Pipeline Improvement Plan
**Date:** November 15, 2025  
**Total Dev Time:** 2 hours  
**Manual Review Time:** 50 minutes  
**Monthly Costs:** $0  
**Priority:** Execute this week

---

## Executive Summary

**Current State:** 20 leads, 10 have issues (50% quality)  
**Goal:** 85%+ quality with minimal engineering overhead  
**Approach:** Fix at source, add simple filters, manual verify top leads

### What We're Doing
1. Tighten revenue/employee caps (prevent oversized businesses)
2. Add retail business filter (block Container57-type leads)
3. Add location label filter (block Emerald-type leads)
4. Add warning flags (highlight potential issues)
5. Generate manual review checklist (systematic verification)

### What We're NOT Doing
- ❌ LinkedIn API integrations ($99-399/month)
- ❌ News monitoring automation ($50-150/month)
- ❌ Multi-source validation frameworks
- ❌ Risk detection services
- ❌ Complex employee count validation

**Why Not:** Building automation for 20 leads is like using a flamethrower to light a candle. Manual review is faster, cheaper, and more reliable at this scale.

---

## Problems We're Actually Solving

### Problem 1: Oversized Businesses (30% of pipeline)
**Root Cause:** Revenue cap too loose ($2.6M vs. $1.4M target)  
**Solution:** Tighten caps at source  
**Time:** 10 minutes

### Problem 2: Wrong Business Types (10% of pipeline)
**Examples:** Container57 (retail), Emerald (location label)  
**Solution:** Simple keyword filters  
**Time:** 1 hour

### Problem 3: No Early Warning System
**Issue:** Size mismatches not flagged until manual review  
**Solution:** Add warning flags for manual verification  
**Time:** 10 minutes

### Problem 4: Ad-hoc Manual Review
**Issue:** No systematic process to catch Sasa/Welsh situations  
**Solution:** Structured 5-minute checklist per lead  
**Time:** 40 minutes (dev) + 50 minutes (execution)

---

## Implementation Plan

### Task 1: Tighten Size Filters (10 minutes)

**File:** `src/core/config.py`

**Changes:**
```python
# BEFORE
MAX_EMPLOYEE_COUNT = 30
MAX_REVENUE = 2_600_000  # Implied by accepting $1.2M-$2.6M range

# AFTER
MAX_EMPLOYEE_COUNT = 25  # Stricter cap
MAX_REVENUE = 1_500_000  # $1.5M hard limit (not $2.6M)
MAX_REVIEW_COUNT = 30    # Flag businesses with high visibility

# Reasoning:
# - Target: $1M-$1.4M revenue
# - $1.5M cap gives 7% buffer, not 85% buffer
# - 25 employees aligns with SMB acquisition thesis
# - 30+ reviews suggests chain/brand/larger operation
```

**File:** `src/filters/size_filters.py` (or wherever revenue filtering happens)

```python
def filter_by_size(lead: BusinessLead) -> Tuple[bool, str]:
    """
    Hard caps on business size.
    
    Returns:
        (should_exclude: bool, reason: str)
    """
    # Revenue cap
    if lead.revenue_estimate and lead.revenue_estimate > MAX_REVENUE:
        return True, f"EXCLUDED: Revenue ${lead.revenue_estimate/1_000_000:.1f}M exceeds $1.5M cap"
    
    # Employee cap
    if lead.employee_count and lead.employee_count > MAX_EMPLOYEE_COUNT:
        return True, f"EXCLUDED: {lead.employee_count} employees exceeds 25 employee cap"
    
    return False, "PASSED"
```

**Expected Impact:**
- VP Expert Machining ($1.4M-$2.7M) → EXCLUDED
- Karma Candy (100-200 employees) → EXCLUDED
- G.S. Dunn (likely >$20M revenue) → EXCLUDED
- Felton Brushes ($1.3M-$6.4M) → EXCLUDED
- AVL Manufacturing (300+ employees) → EXCLUDED

**Test:**
```bash
# Run on current 20-lead pipeline
python -m pytest tests/test_size_filters.py -v

# Verify 5-6 oversized businesses get filtered
```

---

### Task 2: Add Retail Business Filter (30 minutes)

**File:** `src/filters/business_type_filters.py`

```python
"""
Business type exclusion filters.
Removes retail, consumer-facing, and non-B2B businesses.
"""
from typing import Tuple, Optional


class BusinessTypeFilter:
    """Filter out wrong business types."""
    
    def __init__(self):
        self.retail_platforms = [
            'shopify.com',
            'myshopify.com', 
            'bigcartel.com',
            'wix.com/online-store',
            'squarespace.com/commerce'
        ]
        
        self.retail_keywords = [
            'retail', 'shop', 'store', 'boutique', 
            'mall', 'outlet', 'showroom'
        ]
        
        self.consumer_indicators = [
            'online store', 'e-commerce', 'ecommerce',
            'shopping', 'buy online'
        ]
    
    def is_retail_business(self, 
                          business_name: str,
                          industry: Optional[str],
                          website: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Detect retail/consumer-facing businesses.
        
        Returns:
            (is_retail: bool, reason: str)
        """
        # Check website for e-commerce platforms
        if website:
            website_lower = website.lower()
            for platform in self.retail_platforms:
                if platform in website_lower:
                    return True, f"E-commerce platform detected: {platform}"
        
        # Check industry classification
        if industry:
            industry_lower = industry.lower()
            for keyword in self.retail_keywords:
                if keyword in industry_lower:
                    return True, f"Retail industry: contains '{keyword}'"
        
        # Check business name for retail indicators
        name_lower = business_name.lower()
        for keyword in self.retail_keywords:
            if keyword in name_lower:
                # Only flag if ALSO has consumer indicators
                if industry and any(ind in industry.lower() for ind in self.consumer_indicators):
                    return True, f"Retail business: name contains '{keyword}' with consumer focus"
        
        return False, None
```

**Integration:**

```python
# In main enrichment pipeline
type_filter = BusinessTypeFilter()

is_retail, reason = type_filter.is_retail_business(
    lead.business_name,
    lead.industry,
    lead.website
)

if is_retail:
    lead.status = "EXCLUDED"
    lead.exclusion_reason = f"WRONG_TYPE: {reason}"
    continue
```

**Test Cases:**
```python
def test_retail_detection():
    filter = BusinessTypeFilter()
    
    # Should detect
    assert filter.is_retail_business(
        "Container57",
        "Retail",
        "https://60424e-3.myshopify.com/"
    )[0] == True
    
    # Should NOT detect (B2B manufacturing)
    assert filter.is_retail_business(
        "Abarth Machining Inc",
        "Manufacturing",
        "https://abarthmachining.com/"
    )[0] == False
```

**Expected Impact:**
- Container57 → EXCLUDED

---

### Task 3: Add Location Label Filter (30 minutes)

**File:** `src/filters/business_type_filters.py` (add to same file)

```python
class BusinessTypeFilter:
    # ... existing code ...
    
    def __init__(self):
        # ... existing init ...
        
        self.location_keywords = [
            'site', 'facility', 'location', 'building',
            'complex', 'park', 'center', 'plaza'
        ]
    
    def is_location_label(self,
                         business_name: str,
                         website: Optional[str],
                         review_count: Optional[int]) -> Tuple[bool, Optional[str]]:
        """
        Detect location labels vs. actual businesses.
        
        Location labels typically have:
        - Generic facility names ("X Manufacturing Site")
        - No website or website is "N/A"
        - Very few or no reviews
        
        Returns:
            (is_location: bool, reason: str)
        """
        name_lower = business_name.lower()
        
        # Check for location keywords in name
        has_location_keyword = False
        matched_keyword = None
        
        for keyword in self.location_keywords:
            if keyword in name_lower:
                has_location_keyword = True
                matched_keyword = keyword
                break
        
        if not has_location_keyword:
            return False, None
        
        # Location keyword found - check for missing business signals
        has_no_website = (not website or 
                         website.lower() in ['n/a', 'na', 'none', ''])
        has_no_reviews = (review_count is None or review_count <= 1)
        
        # Flag if location keyword + no web presence
        if has_no_website and has_no_reviews:
            return True, f"Location label: contains '{matched_keyword}' with no web presence"
        
        # Flag if location keyword + suspicious name pattern
        suspicious_patterns = [
            'manufacturing site',
            'facility location',
            'industrial site',
            'production facility'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in name_lower:
                return True, f"Location label: name pattern '{pattern}'"
        
        return False, None
```

**Test Cases:**
```python
def test_location_label_detection():
    filter = BusinessTypeFilter()
    
    # Should detect
    assert filter.is_location_label(
        "Emerald Manufacturing Site",
        None,
        1
    )[0] == True
    
    # Should NOT detect (real business with website)
    assert filter.is_location_label(
        "North Star Technical Inc",
        "https://northstartech.com/",
        11
    )[0] == False
```

**Expected Impact:**
- Emerald Manufacturing Site → EXCLUDED

---

### Task 4: Add Warning Flags (10 minutes)

**File:** `src/models/business_lead.py` (or wherever BusinessLead is defined)

```python
class BusinessLead:
    # ... existing fields ...
    
    warnings: List[str] = []  # Add this field
    
    def add_warning(self, warning_code: str, message: str):
        """Add non-fatal warning that requires manual review."""
        self.warnings.append(f"{warning_code}: {message}")
```

**File:** `src/enrichment/warning_generator.py` (new file)

```python
"""
Generate warnings for leads that need manual verification.
Non-fatal - leads pass through but flagged for review.
"""
from typing import List
from models.business_lead import BusinessLead


def generate_warnings(lead: BusinessLead) -> List[str]:
    """
    Add warning flags for potential issues.
    
    Warnings are NOT exclusions - they're "hey, double-check this"
    """
    warnings = []
    
    # Warning 1: High review count (may indicate larger business)
    if lead.review_count and lead.review_count > 20:
        warnings.append(
            "HIGH_VISIBILITY: 20+ reviews suggests larger operation or chain. "
            "Verify this is single-location SMB."
        )
    
    # Warning 2: Revenue approaching upper limit
    if lead.revenue_estimate and lead.revenue_estimate > 1_200_000:
        warnings.append(
            f"UPPER_RANGE: Revenue ${lead.revenue_estimate/1_000_000:.1f}M near $1.5M cap. "
            "Confirm size fits acquisition thesis."
        )
    
    # Warning 3: Employee count + reviews suggest possible undercount
    if (lead.employee_count and lead.employee_count > 15 and
        lead.review_count and lead.review_count > 20):
        warnings.append(
            "VERIFY_SIZE: High employee count + high reviews may indicate "
            "Google Places showing location headcount only. Cross-check company-wide size."
        )
    
    # Warning 4: No website (harder due diligence)
    if not lead.website or lead.website.lower() in ['n/a', 'none', '']:
        warnings.append(
            "NO_WEBSITE: Limited online presence makes due diligence harder. "
            "Prioritize leads with websites."
        )
    
    # Warning 5: Very old or very new business
    if lead.years_in_business:
        if lead.years_in_business < 2:
            warnings.append(
                "NEW_BUSINESS: Less than 2 years old. Higher risk profile."
            )
        elif lead.years_in_business > 40:
            warnings.append(
                "ESTABLISHED: 40+ years old. May have succession opportunities."
            )
    
    return warnings


def apply_warnings(lead: BusinessLead) -> BusinessLead:
    """Apply warnings to lead."""
    warnings = generate_warnings(lead)
    for warning in warnings:
        lead.add_warning("MANUAL_REVIEW", warning)
    return lead
```

**Integration:**
```python
# In enrichment pipeline, after all filters
lead = apply_warnings(lead)

# Leads with warnings still pass through but flagged
if lead.warnings:
    logger.info(f"{lead.business_name}: {len(lead.warnings)} warnings", 
                warnings=lead.warnings)
```

**Expected Impact:**
- Stoney Creek Machine (10-28 employees, high range) → WARNING
- Ontario Ravioli (food + retail hybrid) → WARNING  
- All leads near $1.5M cap → WARNING

---

### Task 5: Manual Review Checklist Generator (40 minutes)

**File:** `src/tools/review_checklist.py` (new file)

```python
"""
Generate systematic manual review checklists for top leads.
Because Googling is faster than building automation.
"""
from typing import List, Dict
from models.business_lead import BusinessLead


class ManualReviewChecklist:
    """Generate review tasks for lead verification."""
    
    def generate_checklist(self, lead: BusinessLead) -> str:
        """
        Create 5-minute manual review checklist for a lead.
        
        Returns formatted checklist string.
        """
        checklist = f"""
=== MANUAL REVIEW: {lead.business_name} ===
Priority: {'HIGH' if not lead.warnings else 'MEDIUM'}
Estimated Time: 5 minutes

STEP 1: Verify Still Operating (1 min)
  [ ] Google: "{lead.business_name} closed"
  [ ] Check Google Maps: Recent reviews (last 3 months)?
  [ ] Website accessible: {lead.website or 'NO WEBSITE - check directory listings'}
  
  Red Flags: "Permanently closed", "Out of business", auction notices
  
STEP 2: Check Compliance & Risk (1 min)
  [ ] Google: "{lead.business_name} Hamilton violations"
  [ ] Google: "{lead.business_name} Hamilton health"
  [ ] Google News: "{lead.business_name}" (filter: past year)
  
  Red Flags: Health closures, lawsuits, distress sales, negative press

STEP 3: Verify Business Type (1 min)
  [ ] Website: Primarily B2B or consumer retail?
  [ ] Customer base: Industrial/commercial or retail consumers?
  [ ] If food business: Restaurant/retail or manufacturing?
  
  Red Flags: Retail storefront, consumer e-commerce, franchise

STEP 4: Validate Size (1 min)
  [ ] LinkedIn company page: How many employees listed?
  [ ] Website "About" page: Company size mentioned?
  [ ] Multiple locations mentioned anywhere?
  
  Red Flags: 50+ employees on LinkedIn, "offices in X cities", "global"

STEP 5: Quick Due Diligence (1 min)
  [ ] BBB profile or rating
  [ ] Any public financial disclosures?
  [ ] Google: "{lead.business_name} for sale" (already on market?)
  
  Red Flags: F rating, bankruptcy filings, actively listed for sale

---
DECISION:
  [ ] PROCEED - Clean lead, ready for outreach
  [ ] FLAG - Minor concerns, proceed with caution  
  [ ] EXCLUDE - Deal-breaker issue found
  
Notes:
_________________________________________________________________
_________________________________________________________________

"""
        
        # Add context-specific checks based on warnings
        if lead.warnings:
            checklist += "\n⚠️ SYSTEM WARNINGS:\n"
            for warning in lead.warnings:
                checklist += f"  - {warning}\n"
            checklist += "\n"
        
        # Add lead-specific search queries
        checklist += f"\nQUICK SEARCH QUERIES:\n"
        checklist += f'  - "{lead.business_name}" Hamilton manufacturing\n'
        checklist += f'  - "{lead.business_name}" reviews\n'
        checklist += f'  - "{lead.business_name}" employees linkedin\n'
        
        if lead.owner_name:
            checklist += f'  - "{lead.owner_name}" {lead.business_name}\n'
        
        return checklist
    
    def generate_batch_checklist(self, 
                                 leads: List[BusinessLead],
                                 filename: str = "manual_review_checklist.txt"):
        """
        Generate checklist file for multiple leads.
        
        Prioritizes:
        1. Leads with no warnings (cleanest)
        2. Leads with warnings (need extra scrutiny)
        """
        # Sort: no warnings first (highest priority)
        sorted_leads = sorted(leads, key=lambda x: len(x.warnings))
        
        with open(filename, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("MANUAL REVIEW CHECKLIST - BATCH\n")
            f.write(f"Total Leads: {len(leads)}\n")
            f.write(f"Estimated Time: {len(leads) * 5} minutes ({len(leads) * 5 / 60:.1f} hours)\n")
            f.write("=" * 70 + "\n\n")
            
            for i, lead in enumerate(sorted_leads, 1):
                f.write(f"\n{'=' * 70}\n")
                f.write(f"LEAD {i} of {len(leads)}\n")
                f.write(self.generate_checklist(lead))
                f.write("\n")
        
        return filename


def export_review_checklist(leads: List[BusinessLead], 
                            output_path: str = "review_checklist.txt"):
    """
    Export manual review checklist for leads.
    
    Usage:
        clean_leads = [lead for lead in pipeline if lead.status == "QUALIFIED"]
        export_review_checklist(clean_leads[:15])  # Top 15 leads
    """
    checker = ManualReviewChecklist()
    filename = checker.generate_batch_checklist(leads, output_path)
    
    print(f"\n✅ Review checklist generated: {filename}")
    print(f"📋 {len(leads)} leads to review")
    print(f"⏱️  Estimated time: {len(leads) * 5} minutes\n")
    
    return filename
```

**Usage:**
```python
# After pipeline runs and filters clean data
from tools.review_checklist import export_review_checklist

# Get your top leads (already passed all filters)
top_leads = [lead for lead in pipeline if lead.status == "QUALIFIED"]
top_leads = sorted(top_leads, key=lambda x: x.quality_score, reverse=True)[:15]

# Generate checklist
export_review_checklist(top_leads, "outputs/manual_review_checklist.txt")

# Now spend 5 min per lead systematically checking
```

**Expected Output:** Text file with systematic 5-minute checklist for each lead

---

## Testing Plan (30 minutes)

### Test 1: Run Filters on Current Pipeline
```bash
# Test on your existing 20 leads
python scripts/test_new_filters.py --input data/current_pipeline.csv

# Expected results:
# EXCLUDED: 7-8 businesses (oversized + retail + location)
# CLEAN: 11-12 businesses
# WARNINGS: 3-4 businesses
```

**Create test script:**
```python
# scripts/test_new_filters.py
"""Test new filters on existing pipeline."""
import pandas as pd
from filters.size_filters import filter_by_size
from filters.business_type_filters import BusinessTypeFilter
from enrichment.warning_generator import apply_warnings

def test_pipeline(input_csv: str):
    df = pd.read_csv(input_csv)
    
    type_filter = BusinessTypeFilter()
    results = {
        'excluded_size': [],
        'excluded_retail': [],
        'excluded_location': [],
        'clean': [],
        'warnings': []
    }
    
    for _, row in df.iterrows():
        lead_name = row['business_name']
        
        # Test size filter
        excluded, reason = filter_by_size(row)
        if excluded:
            results['excluded_size'].append((lead_name, reason))
            continue
        
        # Test retail filter
        is_retail, reason = type_filter.is_retail_business(
            row['business_name'],
            row.get('industry'),
            row.get('website')
        )
        if is_retail:
            results['excluded_retail'].append((lead_name, reason))
            continue
        
        # Test location filter
        is_location, reason = type_filter.is_location_label(
            row['business_name'],
            row.get('website'),
            row.get('review_count')
        )
        if is_location:
            results['excluded_location'].append((lead_name, reason))
            continue
        
        # Passed all filters - check warnings
        warnings = generate_warnings(row)
        if warnings:
            results['warnings'].append((lead_name, warnings))
        else:
            results['clean'].append(lead_name)
    
    # Print results
    print("\n=== FILTER TEST RESULTS ===")
    print(f"\n❌ Excluded (Size): {len(results['excluded_size'])}")
    for name, reason in results['excluded_size']:
        print(f"  - {name}: {reason}")
    
    print(f"\n❌ Excluded (Retail): {len(results['excluded_retail'])}")
    for name, reason in results['excluded_retail']:
        print(f"  - {name}: {reason}")
    
    print(f"\n❌ Excluded (Location): {len(results['excluded_location'])}")
    for name, reason in results['excluded_location']:
        print(f"  - {name}: {reason}")
    
    print(f"\n⚠️  With Warnings: {len(results['warnings'])}")
    for name, warnings in results['warnings']:
        print(f"  - {name}: {len(warnings)} warnings")
    
    print(f"\n✅ Clean Leads: {len(results['clean'])}")
    for name in results['clean']:
        print(f"  - {name}")
    
    print(f"\n📊 SUMMARY:")
    print(f"  Total: {len(df)}")
    print(f"  Clean: {len(results['clean'])} ({len(results['clean'])/len(df)*100:.0f}%)")
    print(f"  Warnings: {len(results['warnings'])} ({len(results['warnings'])/len(df)*100:.0f}%)")
    print(f"  Excluded: {len(results['excluded_size']) + len(results['excluded_retail']) + len(results['excluded_location'])} ({(len(results['excluded_size']) + len(results['excluded_retail']) + len(results['excluded_location']))/len(df)*100:.0f}%)")

if __name__ == "__main__":
    import sys
    test_pipeline(sys.argv[1])
```

### Test 2: Validate Against Known Cases
```python
# tests/test_filters.py
"""Unit tests for new filters."""
import pytest
from filters.size_filters import filter_by_size
from filters.business_type_filters import BusinessTypeFilter

def test_oversized_filtering():
    """Karma Candy should be excluded (100-200 employees)."""
    excluded, _ = filter_by_size({'employee_count': 150})
    assert excluded == True

def test_retail_filtering():
    """Container57 should be excluded (Shopify store)."""
    filter = BusinessTypeFilter()
    is_retail, _ = filter.is_retail_business(
        "Container57",
        "Retail",
        "https://60424e-3.myshopify.com/"
    )
    assert is_retail == True

def test_location_filtering():
    """Emerald Manufacturing Site should be excluded."""
    filter = BusinessTypeFilter()
    is_location, _ = filter.is_location_label(
        "Emerald Manufacturing Site",
        None,
        1
    )
    assert is_location == True

def test_clean_lead():
    """Abarth Machining should pass all filters."""
    # Size check
    excluded, _ = filter_by_size({'employee_count': 10, 'revenue_estimate': 1_000_000})
    assert excluded == False
    
    # Type check
    filter = BusinessTypeFilter()
    is_retail, _ = filter.is_retail_business("Abarth Machining Inc", "Manufacturing", "https://abarth.com/")
    assert is_retail == False
    
    is_location, _ = filter.is_location_label("Abarth Machining Inc", "https://abarth.com/", 3)
    assert is_location == False

# Run tests
# pytest tests/test_filters.py -v
```

---

## Manual Review Process (50 minutes)

After filters run, you'll have ~11-13 clean leads. Time to manually verify your top 10-12.

**Process:**
1. Generate review checklist: `export_review_checklist(top_leads)`
2. Print checklist or open in text editor
3. Spend 5 minutes per lead systematically checking:
   - Still operating?
   - Any compliance issues?
   - Actually B2B industrial/service?
   - Size matches data?
   - Any deal-breaker red flags?
4. Mark each lead: PROCEED / FLAG / EXCLUDE

**Time Breakdown:**
- 10 leads × 5 minutes = 50 minutes
- Or 15 leads × 5 minutes = 75 minutes

**This is faster and more reliable than:**
- Building LinkedIn API integration (2+ hours + $99/month)
- Building news monitoring (2+ hours + $50/month)
- Building risk detection service (2+ hours + maintenance)

---

## Implementation Schedule

### Day 1: Core Filters (2 hours)
- ☐ Task 1: Tighten size filters (10 min)
- ☐ Task 2: Add retail filter (30 min)
- ☐ Task 3: Add location filter (30 min)
- ☐ Task 4: Add warning flags (10 min)
- ☐ Task 5: Build checklist generator (40 min)

### Day 2: Testing (30 minutes)
- ☐ Run test script on current pipeline
- ☐ Verify expected exclusions
- ☐ Run unit tests
- ☐ Fix any bugs

### Day 3: Execute Manual Review (50-75 minutes)
- ☐ Generate checklist for top 10-15 leads
- ☐ Systematically review each lead (5 min each)
- ☐ Mark final decisions
- ☐ Export cleaned A-list

**Total Time Investment:**
- Dev: 2.5 hours
- Manual review: 1 hour
- **Total: 3.5 hours**

**vs. Original Plan:** 13.5 hours + ongoing API costs

---

## Expected Results

### Before (Current State)
```
Total: 20 leads
Clean: 10 leads (50%)
Issues: 10 leads (50%)
  - Oversized: 6
  - Wrong type: 2
  - Risk flags: 2
```

### After (With New Filters)
```
Total: 20 leads
Auto-Excluded: 7-8 leads (35-40%)
  - Size: 5-6
  - Retail: 1
  - Location: 1

Clean Pipeline: 12-13 leads (60-65%)
  - No warnings: 8-9 leads (40-45%)
  - With warnings: 3-4 leads (15-20%)

After Manual Review: 10-11 leads (50-55%)
  - High quality A-list ready for outreach
```

**Quality Improvement:** 50% → 85%+ with minimal overhead

---

## File Structure

New/modified files:
```
src/
  core/
    config.py                    # Modified: tighter caps
  filters/
    size_filters.py              # Modified: enforce hard caps
    business_type_filters.py     # New: retail + location filters
  enrichment/
    warning_generator.py         # New: non-fatal warnings
  tools/
    review_checklist.py          # New: manual review system
  models/
    business_lead.py             # Modified: add warnings field

scripts/
  test_new_filters.py           # New: test harness

tests/
  test_filters.py               # New: unit tests

outputs/
  manual_review_checklist.txt   # Generated: review tasks
```

---

## Maintenance

### When to Update Filters

**Add exclusion keywords** when you see repeat patterns:
- Found 3+ franchises? Add franchise detection
- Found 2+ chains? Add chain detection  
- Seeing repair shops instead of manufacturing? Add keyword

**Tighten size caps** if getting too many large businesses:
- Currently: 25 employees, $1.5M revenue
- If still too many: 20 employees, $1.2M revenue

**Add warning conditions** based on manual review findings:
- Keep finding issues with certain industries? Add industry warnings
- Specific address patterns causing problems? Add location warnings

### Monthly Review (15 minutes)
1. Look at last month's pipeline
2. Note any patterns in excluded/problematic leads  
3. Adjust filters if >3 leads with same issue
4. Update warning conditions based on manual review notes

**Key Principle:** Don't build automation until you see the same problem 5+ times. Otherwise, you're solving hypothetical problems.

---

## What We're NOT Building (And Why)

### LinkedIn API Integration
**Estimated effort:** 2+ hours  
**Monthly cost:** $99-399  
**Why skip:** 5 minutes on LinkedIn manually gets same data

### News Monitoring Automation
**Estimated effort:** 2+ hours  
**Monthly cost:** $50-150  
**Why skip:** Google News search takes 30 seconds per lead

### Multi-Source Validation Framework
**Estimated effort:** 4+ hours  
**Why skip:** For 20 leads? Just Google it manually

### Risk Detection Service
**Estimated effort:** 2+ hours  
**Why skip:** Systematic manual checklist catches everything

### Employee Count Cross-Validation
**Estimated effort:** 2+ hours  
**Why skip:** Warning flag + 1 minute LinkedIn check = problem solved

**Total avoided:** 12+ hours dev time + $150-550/month

---

## Success Criteria

After implementation, you should have:

✅ **Clean A-List:** 10-12 high-quality leads ready for outreach  
✅ **No Retail:** Container57-type businesses automatically excluded  
✅ **No Location Labels:** Emerald-type entries automatically excluded  
✅ **No Oversized:** Karma Candy, G.S. Dunn, AVL automatically excluded  
✅ **Warning System:** Potential issues flagged for manual verification  
✅ **Review Process:** Systematic 5-minute checklist per lead  
✅ **Zero Recurring Costs:** No API subscriptions needed  
✅ **Maintainable:** Simple filters that anyone can update

**Quality Target:** 85%+ clean leads (vs. current 50%)  
**Time Investment:** 3.5 hours total  
**Ongoing Maintenance:** 15 minutes/month

---

## Quick Reference

### Commands
```bash
# Run test on current pipeline
python scripts/test_new_filters.py data/current_pipeline.csv

# Run unit tests
pytest tests/test_filters.py -v

# Generate manual review checklist
python -c "from tools.review_checklist import export_review_checklist; export_review_checklist(top_leads)"
```

### Decision Tree: Should I Automate This?

```
Have I seen this problem 5+ times?
  ├─ No → Manual process (Google search)
  └─ Yes → Is it a 5-minute fix?
            ├─ Yes → Add simple filter
            └─ No → Still manual until problem frequency justifies dev time
```

**Remember:** At 20 leads, manual processes are your friend. Don't over-engineer.

---

## Questions?

**Q: What if I want to scale to 200 leads?**  
A: Then revisit automation. At 200 leads, LinkedIn API makes sense. At 20, it doesn't.

**Q: Shouldn't we prevent bad data at the source?**  
A: Yes! Look at your Google Places search query. Are you filtering by category? Using the right search terms? Fix the input before building complex output validation.

**Q: What about [specific edge case]?**  
A: Has it happened more than once? If not, handle it manually when it comes up.

**Q: This seems too simple.**  
A: That's the point. Simple systems work better at small scale. Build complexity when scale demands it, not before.

---

**Bottom Line:** Spend 3.5 hours building simple filters + manual verification instead of 13.5 hours building enterprise automation for a 20-lead pipeline.

Make sense? Let's ship this.
