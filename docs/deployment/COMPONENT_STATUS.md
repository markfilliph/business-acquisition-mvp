# Component Status Analysis

**Date**: October 12, 2025
**Purpose**: Identify which components use validated v2 gates vs deprecated validation

---

## ✅ PRODUCTION COMPONENTS (Using New Gates)

### Main Pipeline
- **File**: `generate_v2` → `src/pipeline/evidence_based_generator.py`
- **Status**: ✅ **ACTIVE - PRODUCTION**
- **Validation**: Uses NEW gate system
  - Category Gate (`src/gates/category_gate.py`)
  - Revenue Gate (`src/gates/revenue_gate.py`)
  - Geo Gate (`src/gates/geo_gate.py`)
  - Website Age Gate (`src/services/wayback_service.py`)
- **Validation Service**: `src/services/new_validation_service.py`
- **Test Coverage**: 98/98 tests passing
- **Usage**: `./generate_v2 [count] --show`

### Supporting Tools
- **Review Queue**: `scripts/review_queue.py` - HITL for borderline leads
- **Metrics Dashboard**: `scripts/metrics_dashboard.py` - Observability
- **Gate Tests**: `tests/test_category_gate.py`, `test_revenue_gate.py`, `test_geo_gate.py`
- **Acceptance Tests**: `tests/test_acceptance_simple.py` (11 criteria)

---

## ❌ DEPRECATED COMPONENTS (Using Old Validation)

### Old Pipeline Components

#### 1. Orchestrator Pipeline
- **Files**:
  - `./generate` (bash script)
  - `cli/generate.py`
  - `src/agents/orchestrator.py`
- **Status**: ❌ **DEPRECATED**
- **Validation**: Uses OLD `BusinessValidationService`
  - Does NOT use new gates
  - Does NOT enforce 60% revenue confidence
  - Does NOT use HITL review queue
- **Issue**: Bypasses new strict validation gates
- **Recommendation**: **Archive** to `scripts/legacy/old_pipelines/`

#### 2. Quick Generator
- **File**: `src/pipeline/quick_generator.py`
- **Status**: ❌ **DEPRECATED**
- **Validation**: Uses OLD `BusinessValidationService`
  - Does NOT use new gates
  - Custom exclusion lists (not gate-based)
  - No HITL review
- **Issue**: Inconsistent with production validation
- **Recommendation**: **Archive** to `scripts/legacy/old_pipelines/`

---

## Validation Service Comparison

### OLD: `BusinessValidationService` (src/services/validation_service.py)
```python
# Used by: orchestrator.py, quick_generator.py
- General validation rules
- No explicit gates
- No revenue confidence threshold
- No HITL review mechanism
- Not aligned with deployment verification
```

### NEW: `ValidationService` (src/services/new_validation_service.py)
```python
# Used by: evidence_based_generator.py
- Explicit gate system (category, revenue, geo)
- 60% revenue confidence threshold
- HITL review for borderline cases
- Website age validation (15+ years)
- Evidence-based with multi-source corroboration
```

---

## Impact Analysis

### Components Still Using Old Validation

1. **`./generate`** → `cli/generate.py` → `orchestrator.py`
   - Generates leads bypassing new gates
   - Could produce leads that shouldn't pass
   - Inconsistent with deployment verification

2. **`quick_generator.py`**
   - Fast mode without proper gates
   - Custom filtering, not gate-based
   - No revenue confidence enforcement

3. **`orchestrator.py`**
   - Core dependency of old `./generate`
   - Used by `cli/generate.py`
   - Not compatible with new gate system

---

## Recommended Actions

### Immediate (High Priority)

1. ✅ **Archive to `scripts/legacy/old_pipelines/`**:
   - `./generate` (bash script)
   - `cli/generate.py`
   - `src/agents/orchestrator.py`
   - `src/pipeline/quick_generator.py`

2. ✅ **Update Documentation**:
   - `README.md` - Show only `generate_v2`
   - Create `PRODUCTION_DEPLOYMENT.md` guide
   - Add deprecation notices

3. ✅ **Update Shell Scripts**:
   - Remove or update `./generate`
   - Remove or update `./auto-feed`
   - Remove or update `./quickstart`

### Validation Service Path Forward

**Option A**: Keep both validation services
- Mark `BusinessValidationService` as deprecated
- All new code must use new `ValidationService`

**Option B**: Retire old validation service
- Move `validation_service.py` to legacy
- Remove all dependencies on old service
- Force migration to gate system

**Recommendation**: **Option B** - Complete migration to new system

---

## Testing Requirements

After archiving deprecated components:

1. ✅ Run gate tests: `pytest tests/test_*_gate.py`
2. ✅ Run acceptance tests: `pytest tests/test_acceptance_simple.py`
3. ✅ Verify no imports of archived files
4. ✅ Test production pipeline: `./generate_v2 5 --show`

---

## Single Source of Truth

**PRODUCTION PIPELINE**: `./generate_v2`
- Uses NEW gates
- Enforces all deployment verification criteria
- 98 tests passing
- Ready for production deployment

**All other generators**: DEPRECATED and archived

---

**Status**: Analysis complete - Ready for cleanup phase 2
