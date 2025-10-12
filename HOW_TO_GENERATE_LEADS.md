# How to Generate Leads - Clear Instructions

**Last Updated**: October 12, 2025
**System Version**: v2.0 (Evidence-Based with Strict Gates)

---

## ✅ THE ONLY PRODUCTION COMMAND

```bash
./generate_v2 [count] [--show]
```

**That's it!** This is the ONLY command you should use to generate leads.

### Examples

```bash
# Generate 20 leads (default)
./generate_v2

# Generate 50 leads
./generate_v2 50

# Generate 10 leads with detailed progress
./generate_v2 10 --show
```

---

## 🔍 What This Command Does (Step by Step)

### Execution Path

```
./generate_v2
    ↓
src/pipeline/evidence_based_generator.py
    ↓
EvidenceBasedLeadGenerator.generate_leads()
    ↓
ValidationService (new_validation_service.py)
    ↓
5 Strict Gates
```

### Pipeline Flow

1. **Discovery** (OpenStreetMap + Multiple Sources)
   - Fetches businesses from real sources
   - NO sample/fake data
   - Multiplier: 15x (e.g., fetch 300 to get 20 qualified)

2. **Deduplication** (Fingerprinting)
   - Computes fingerprint (name + address hash)
   - Blocks duplicates immediately
   - Status: `DISCOVERED`

3. **Geocoding**
   - Updates latitude/longitude
   - Status: `GEOCODED`

4. **Enrichment** (Observations)
   - Creates observations from sources
   - Phone, address, website (OpenStreetMap)
   - Place types (Google Places API)
   - Status: `ENRICHED`

5. **Validation** (5 Strict Gates)
   - **Gate 1: Category Gate**
   - **Gate 2: Geo Gate**
   - **Gate 3: Corroboration Gate**
   - **Gate 4: Website Age Gate**
   - **Gate 5: Revenue Gate**
   - Status: `QUALIFIED`, `EXCLUDED`, or `REVIEW_REQUIRED`

---

## 🚪 The 5 Validation Gates (In Order)

### Gate 1: Category Gate
**File**: `src/gates/category_gate.py`
**Used by**: `new_validation_service.py` line 244

**Checks**:
1. ❌ Name blacklist patterns (franchises, chains)
2. ❌ Category blacklist (retail, restaurants, etc.)
3. ⚠️  Review-required categories (funeral homes, franchises, etc.)
4. ✅ Must have at least one TARGET industry

**Outcomes**:
- ✅ **PASS**: Has whitelisted category (manufacturing, wholesale, professional services, printing, equipment rental)
- ⚠️  **REVIEW_REQUIRED**: Borderline category (e.g., funeral_home, franchise_office)
- ❌ **EXCLUDED**: Blacklisted or no whitelisted category

### Gate 2: Geo Gate
**File**: `src/gates/geo_gate.py`
**Used by**: `new_validation_service.py` line 268

**Checks**:
1. Must have latitude/longitude
2. Must be within 25km radius of Hamilton
3. City must be in allowed list: Hamilton, Dundas, Ancaster, Stoney Creek, Waterdown

**Outcomes**:
- ✅ **PASS**: Within radius AND city allowed
- ❌ **EXCLUDED**: Outside radius OR city not allowed

### Gate 3: Corroboration Gate
**Used by**: `new_validation_service.py` line 292

**Checks**:
- Address: Must have 2+ sources agreeing
- Phone: Must have 2+ sources agreeing
- Postal code: Must have 2+ sources agreeing

**Outcomes**:
- ✅ **PASS**: 2+ sources agree on values
- ⚠️  **REVIEW_REQUIRED**: 1-vs-1 conflict (needs human review)
- ❌ **EXCLUDED**: No sources or multiple conflicts

### Gate 4: Website Age Gate
**Service**: `src/services/wayback_service.py`
**Used by**: `new_validation_service.py` line 307

**Checks**:
- Website must be reachable (not parked)
- Website age must be 15+ years (via Wayback Machine)

**Outcomes**:
- ✅ **PASS**: Website age ≥ 15 years
- ⚠️  **REVIEW_REQUIRED**: Borderline age (14.5-15 years)
- ❌ **EXCLUDED**: Website unreachable or < 14.5 years

### Gate 5: Revenue Gate
**File**: `src/gates/revenue_gate.py`
**Used by**: `new_validation_service.py` line 330

**Checks**:
- Revenue confidence must be ≥ 60%
- Must have underlying evidence:
  - Staff count signal OR
  - Category benchmark
- Revenue must be in target range ($1M - $1.4M)

**Outcomes**:
- ✅ **PASS**: Confidence ≥ 0.6 AND has evidence
- ❌ **EXCLUDED**: Low confidence OR no evidence OR out of range

---

## 🎯 Final Status Assignment

After all 5 gates:

- **QUALIFIED** ✅
  - All 5 gates PASSED
  - Ready for outreach
  - Saved to database with status='QUALIFIED'

- **REVIEW_REQUIRED** ⚠️
  - Failed at least one gate with 'REVIEW_REQUIRED' action
  - Needs human review (use `python scripts/review_queue.py`)
  - Examples: borderline category, 1-vs-1 data conflict, borderline website age

- **EXCLUDED** ❌
  - Failed at least one gate with 'AUTO_EXCLUDE' action
  - Permanently excluded
  - Exclusion reason recorded in database

---

## 📊 Expected Results

### Typical Run (./generate_v2 20)

```
🎯 Evidence-Based Lead Generation (Production System)
======================================================================
Target: 20 qualified leads
Database: data/leads_v2.db
Validation: Category + Geo + Corroboration + Website + Revenue
======================================================================

🔍 Step 1/4: Discovering 300 businesses from OpenStreetMap...
📊 Discovered 300 raw businesses

[Processing each business through 4 steps...]

🎉 Target reached! 20 qualified leads

======================================================================
📊 Pipeline Statistics
======================================================================
Discovered:        280 (20 duplicates)
Geocoded:          280
Enriched:          280
Qualified:         20 ✅
Excluded:          240
  - Category:      150  (retail, restaurants, etc.)
  - Geography:     30   (outside radius or wrong city)
  - Corroboration: 20   (data conflicts)
  - Website Age:   10   (too new)
  - Revenue:       30   (low confidence or no evidence)
Review Required:   20
Duplicates:        20
======================================================================

Qualification Rate: 7.1%
Target: <10% (retail leakage prevention working if <10%)
```

### Key Metrics

- **Qualification Rate**: 5-10% (strict gates working correctly)
- **⚠️ If >10%**: Gates may not be strict enough
- **⚠️ If <2%**: May need to adjust criteria

---

## 🚫 What NOT to Use (Deprecated)

These are archived and should NOT be used:

❌ `./generate` (old script, uses deprecated orchestrator)
❌ `cli/generate.py` (bypasses new gates)
❌ `quick_generator.py` (doesn't use gate system)
❌ `orchestrator.py` (uses old BusinessValidationService)
❌ ANY script in `scripts/legacy/old_pipelines/`

**Why?** They use the OLD validation service which:
- ✗ No 60% revenue confidence threshold
- ✗ No category gate with HITL review
- ✗ No geo gate dual enforcement
- ✗ No website age validation (15+ years)
- ✗ No evidence-based corroboration

---

## 🔍 Where is Everything?

### Production Code

```
src/pipeline/evidence_based_generator.py
    ├── Uses: ValidationService (new_validation_service.py)
    ├── Uses: BusinessDataAggregator (integrations/)
    ├── Uses: PlacesService (sources/places.py)
    └── Validates with 5 gates

src/services/new_validation_service.py
    ├── category_gate() → src/gates/category_gate.py
    ├── geo_gate() → src/gates/geo_gate.py
    ├── corroboration_gate() → internal logic
    ├── website_gate() → src/services/wayback_service.py
    └── revenue_gate() → src/gates/revenue_gate.py

src/gates/
    ├── category_gate.py (target whitelist, blacklist, review list)
    ├── revenue_gate.py (60% threshold, evidence requirement)
    └── geo_gate.py (radius + city allowlist)
```

### Configuration

```
src/core/config.py
    ├── Business criteria (revenue range, age, employees)
    ├── Geographic settings (radius, allowed cities)
    └── Validation thresholds

src/core/rules.py
    ├── TARGET_WHITELIST (allowed industries)
    ├── CATEGORY_BLACKLIST (excluded industries)
    ├── REVIEW_REQUIRED_CATEGORIES (need HITL)
    └── GEO_CONFIG (Hamilton centroid, radius)
```

### Database

```
data/leads_v2.db
    ├── businesses (main table)
    ├── observations (evidence from sources)
    ├── validations (gate results)
    └── exclusions (rejection reasons)
```

---

## 🎯 Summary

**To generate leads**:
```bash
./generate_v2 [count] --show
```

**This runs**:
1. evidence_based_generator.py
2. ValidationService with 5 strict gates
3. Results saved to data/leads_v2.db

**All gates must pass** for QUALIFIED status.

**Review borderline cases**:
```bash
python scripts/review_queue.py
```

**View metrics**:
```bash
python scripts/metrics_dashboard.py
```

---

**Status**: Clear execution path documented ✅
**No ambiguity**: Only one production command
**No old systems**: All deprecated components archived
