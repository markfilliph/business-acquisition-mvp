# Deployment Checklist - Evidence-Based Lead Generation

## Current Status: Week 1 - Day 1 Complete ✅

Based on **IMPLEMENTATION_PLAN_UPDATES.md** Section 10: Updated Rollout Plan

---

## ✅ Week 1 Completed (Day 1)

- [x] **P0: Database schema** - `migrations/001_evidence_schema.sql` ✅
- [x] **P0: normalization.py** - Entity fingerprinting + de-duplication ✅
- [x] **P0: evidence.py, rules.py** - Evidence tracking + business rules ✅
- [x] **P0: validation_service.py** - Category + geo + corroboration gates ✅
- [x] **P0: Golden tests** - `tests/test_golden_cases.py` (30+ test cases) ✅
- [x] **P1: REVIEW_REQUIRED status** - Conflict detection logic ✅
- [x] **P1: resilience.py** - Circuit breaker + retry ✅

---

## ⚠️ Week 1 Remaining (Critical - Must Complete Before Deployment)

### **P0: Build Places Type Mapping Tables** (2-3 days)
**Status**: INCOMPLETE ⚠️
**Current**: Only ~50 mappings in `src/sources/places.py`
**Required**: 200+ mappings

**Action Required**:
```bash
# Step 1: Create scraper to collect sample data
python3 scripts/build_type_mappings.py --sample-size 100 --output src/sources/type_mappings.json

# Step 2: Manually review and expand mappings
# Edit src/sources/places.py to add all mappings
```

**Why Critical**: Without complete type mappings, category_gate() will miss retail/gas/auto businesses because their Google/Yelp types won't map to our CATEGORY_BLACKLIST.

---

### **P0: Implement LLM Extraction** (2 days)
**Status**: NOT STARTED ⚠️
**Required Files**:
- `src/models/extraction_schemas.py` - Pydantic schemas ✅ (stub in plan)
- `src/prompts/extraction_prompts.py` - Anti-hallucination prompts ✅ (stub in plan)
- `src/services/llm_service.py` - OpenAI integration with guardrails ❌ NOT CREATED

**Action Required**:
```bash
# Create LLM service with strict extraction
# Test on 20 real websites (founding_year, staff_count)
python3 tests/test_llm_extraction.py
```

**Why Critical**: Revenue gate requires staff_count or benchmark. Without LLM extraction, we can't get staff signals, so revenue_gate will fail all leads.

---

## 🚫 DEPLOYMENT BLOCKERS

**Cannot deploy until these are resolved**:

1. **Places Type Mappings Incomplete**
   - Risk: Retail/gas/auto leakage (90%+ of bad leads)
   - Impact: System will QUALIFY junk leads
   - Fix: 2-3 days to scrape 100 businesses + build mappings

2. **LLM Extraction Missing**
   - Risk: Revenue gate fails (no staff signals)
   - Impact: 0% qualification rate (everything excluded)
   - Fix: 2 days to implement + test

3. **No Test on Real Data**
   - Risk: Unknown failure modes
   - Impact: Production failures
   - Fix: 1 day to run on 100 leads

---

## 📋 Deployment Strategy (Per Implementation Plan)

### **Immediate Next Steps (Before ANY deployment)**:

#### Day 2-3: Complete Type Mappings
```bash
# 1. Create mapping builder script
touch scripts/build_type_mappings.py

# 2. Scrape 100 real businesses from Hamilton
./generate 100 --show > sample_businesses.txt

# 3. Extract unique place types
grep "place_types" sample_businesses.txt | sort -u > unique_types.txt

# 4. Manually map each type to canonical vocabulary
# Add to src/sources/places.py:
#   GOOGLE_TO_CANONICAL = { ... 200+ mappings ... }
```

#### Day 4-5: Implement LLM Extraction
```bash
# 1. Create LLM service
touch src/services/llm_service.py

# 2. Add OpenAI integration with guardrails
# - Token limits (max 1000 tokens)
# - Cost tracking
# - Null-rate monitoring

# 3. Test on 20 real websites
python3 -m pytest tests/test_llm_extraction.py -v
```

#### Day 6: Integration Test
```bash
# Run on 100 real leads
./generate_v2 100 --show > week1_test_results.txt

# Analyze results
sqlite3 data/leads_v2.db "SELECT status, COUNT(*) FROM businesses GROUP BY status;"

# Expected:
# DISCOVERED: 100
# QUALIFIED: 5-10  (90-95% rejection rate is CORRECT)
# EXCLUDED: 85-90
# REVIEW_REQUIRED: 5-10
```

---

## 🎯 Definition of Done (Week 1)

**System is ready for Week 2 when**:

- [ ] Places type mappings cover 200+ types (verify with `wc -l` on GOOGLE_TO_CANONICAL)
- [ ] LLM extraction tested on 20 websites, 70%+ success rate
- [ ] 100-lead test run shows:
  - [ ] 0 duplicates (fingerprinting works)
  - [ ] >80% exclusion rate (filtering works)
  - [ ] 0 retail/gas/auto in QUALIFIED (category gate works)
  - [ ] <10 REVIEW_REQUIRED (conflict detection works)
- [ ] Golden tests pass: `python3 tests/test_golden_cases.py` (all green)

---

## 🔧 Current Deployment Command (NOT READY FOR PRODUCTION)

```bash
# DO NOT USE YET - Missing type mappings & LLM extraction
./generate_v2 5 --show

# Will fail because:
# 1. Places API returns types not in our 50-entry mapping → unmapped
# 2. Revenue gate requires staff_count → LLM service doesn't exist
# 3. No real-world testing done
```

---

## ✅ Safe Testing Command (What You CAN Do Now)

```bash
# Test fingerprinting on sample data
python3 << 'EOF'
from src.core.normalization import compute_fingerprint

# Test duplicate detection
b1 = {'name': 'ABC Inc.', 'street': '123 Main St', 'city': 'Hamilton', 'postal_code': 'L8H3R2'}
b2 = {'name': 'ABC', 'street': '123 Main Street', 'city': 'Hamilton', 'postal_code': 'L8H 3R2'}

fp1 = compute_fingerprint(b1)
fp2 = compute_fingerprint(b2)

print(f"Business 1: {fp1}")
print(f"Business 2: {fp2}")
print(f"Match: {fp1 == fp2}")  # Should be True
EOF

# Test category gate
python3 << 'EOF'
from src.services.new_validation_service import ValidationService

validator = ValidationService()

# Test known failure
business = {'name': 'Eastgate Variety'}
place_types = ['convenience_store']
passed, reason, action = validator.category_gate(business, place_types)

print(f"Passed: {passed}")  # Should be False
print(f"Reason: {reason}")  # Should contain "blacklist"
print(f"Action: {action}")  # Should be AUTO_EXCLUDE
EOF
```

---

## 📊 Week 1 Progress

| Task | Status | Blocker? | ETA |
|------|--------|----------|-----|
| Database schema | ✅ Complete | No | - |
| Normalization | ✅ Complete | No | - |
| Evidence tracking | ✅ Complete | No | - |
| Business rules | ✅ Complete | No | - |
| Validation service | ✅ Complete | No | - |
| Golden tests | ✅ Complete | No | - |
| **Type mappings** | ⚠️ 25% | **YES** | 2-3 days |
| **LLM extraction** | ❌ 0% | **YES** | 2 days |
| **Integration test** | ❌ 0% | **YES** | 1 day |

**Overall Week 1**: 70% complete
**Time to production-ready**: 5-6 days remaining

---

## 🚀 Correct Deployment File

**Based on IMPLEMENTATION_PLAN_UPDATES.md, the deployment file is**:

**Primary**: `src/pipeline/evidence_based_generator.py`
**CLI Script**: `./generate_v2`

**BUT** - These are not production-ready until Week 1 P0 blockers are resolved.

---

## 📝 Summary

**What we have**: Core foundation (70% of Week 1)
**What we need**: Type mappings + LLM extraction (30% of Week 1)
**When we can deploy**: After 5-6 more days of work
**Current deployment status**: **BLOCKED** ⛔

**Next action**: Build `scripts/build_type_mappings.py` to scrape 100 businesses and expand mapping tables.
