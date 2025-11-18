# Production Deployment Guide

**System**: Business Acquisition Lead Generation v2.0
**Status**: Production Ready ✅
**Last Updated**: October 12, 2025

---

## 🚀 Quick Start (Production)

### Single Command Lead Generation

```bash
# Generate 20 leads (default)
./generate_v2

# Generate specific count
./generate_v2 50

# Generate with detailed progress
./generate_v2 10 --show
```

**That's it!** This is your single production pipeline.

---

## 📊 What This Pipeline Does

### 1. Discovery
- Fetches businesses from OpenStreetMap, Yellow Pages, Canadian Importers
- Real-time data only (no sample/fake data)
- Multiplier applied to ensure sufficient candidates

### 2. Deduplication
- Fingerprint-based (name + address)
- Blocks duplicates immediately
- Prevents reprocessing

### 3. Enrichment
- Creates observations from multiple sources
- Google Places API for business types
- Confidence scores for all data

### 4. Validation (Strict Gates)
```
✓ Category Gate     → Target industries only, HITL review for borderline
✓ Revenue Gate      → 60% confidence threshold + evidence required
✓ Geo Gate          → Radius check + city allowlist (dual enforcement)
✓ Website Age Gate  → 15+ years via Wayback Machine
```

### 5. Status Assignment
- **QUALIFIED**: Passed all gates
- **EXCLUDED**: Failed one or more gates
- **REVIEW_REQUIRED**: Borderline category needing human review

---

## 🎯 Production Criteria (Enforced by Gates)

| Criterion | Value | Enforcement |
|-----------|-------|-------------|
| **Revenue** | $1M - $1.4M | 60% confidence + evidence |
| **Business Age** | 15+ years | Wayback Machine verification |
| **Location** | Hamilton area | Radius (25km) + city allowlist |
| **Industries** | Manufacturing, wholesale, professional services, printing, equipment rental | Category gate + HITL |
| **Employee Count** | Typically 5-50 | Used for revenue evidence |

---

## 🛠️ Supporting Tools

### Human-in-the-Loop Review Queue

```bash
python scripts/review_queue.py
```

- Review borderline leads flagged by category gate
- Approve or reject with reasoning
- Audit trail maintained

### Metrics Dashboard

```bash
python scripts/metrics_dashboard.py
```

- Gate pass/fail rates
- API usage and cache hit rates
- Weekly trend analysis
- Automated recommendations

---

## 📂 Output & Database

### Database
- **Location**: `data/leads_v2.db`
- **Tables**: businesses, observations, validations, exclusions
- **Status Field**:
  - `DISCOVERED` → Initial entry
  - `GEOCODED` → Coordinates added
  - `ENRICHED` → Observations created
  - `QUALIFIED` → Passed all gates ✅
  - `EXCLUDED` → Failed gates ❌
  - `REVIEW_REQUIRED` → Needs HITL ⚠️

### Exports
Automated exports created after each run:
- CSV format (simple)
- JSON format (detailed with metadata)
- Summary report (text)

---

## 🧪 Validation & Testing

### Run Tests Before Deployment

```bash
# Gate tests
./venv/bin/python -m pytest tests/test_category_gate.py -v
./venv/bin/python -m pytest tests/test_revenue_gate.py -v
./venv/bin/python -m pytest tests/test_geo_gate.py -v

# Acceptance criteria (11 production readiness tests)
./venv/bin/python -m pytest tests/test_acceptance_simple.py -v
```

**Expected**: 98/98 tests passing

### Integration Test

```bash
# Generate 5 leads with detailed output
./generate_v2 5 --show
```

**Verify**:
- ✅ 0 retail businesses in QUALIFIED status
- ✅ All gates enforcing (see rejection stats)
- ✅ No duplicates
- ✅ Evidence tracked for all observations

---

## ⚠️ What NOT to Use (Deprecated)

These have been archived to `scripts/legacy/old_pipelines/`:

❌ **DO NOT USE**:
- `./generate` - Old script using deprecated orchestrator
- `cli/generate.py` - Bypasses new gates
- `quick_generator.py` - Doesn't use gate system
- `orchestrator.py` - Uses old validation service
- `lead_generation_pipeline.py` - Had sample data generation
- `rag_validator.py` - RAG-based validation (too complex)
- `local_llm_generator.py` - LLM-based validation (too subjective)
- `auto_feed.py` - Depends on deprecated components

**Why deprecated?**
They use the old `BusinessValidationService` which does NOT enforce:
- 60% revenue confidence threshold
- Category gate with HITL review
- Geo gate dual enforcement
- Website age validation

---

## 🔧 Configuration

### Environment Variables (`.env`)

```bash
# Database
DATABASE_PATH=data/leads_v2.db

# API Keys (required for production)
GOOGLE_MAPS_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here  # Optional, for LLM extraction
YELP_API_KEY=your_key_here     # Optional

# Rate Limits (adjust to your quotas)
GOOGLE_PLACES_RATE_LIMIT=10
OPENAI_RATE_LIMIT=50

# Environment
ENVIRONMENT=production
DEBUG=false
```

### Gate Configuration (`src/core/config.py`)

Already configured with validated values:
- Revenue confidence threshold: 0.6 (60%)
- Geo radius: 25km from Hamilton
- Allowed cities: Hamilton, Dundas, Ancaster, Stoney Creek, Waterdown
- Website age minimum: 15 years

---

## 📈 Expected Performance

### Processing Rates
- **Fetch**: 200 businesses/minute from OSM
- **Enrichment**: 60 businesses/minute with Places API
- **Validation**: 1000+ businesses/minute (gates are fast)

### Qualification Rate
- **Expected**: 5-10% (strict gates working correctly)
- **⚠️ If >10%**: Gates may not be strict enough
- **⚠️ If <2%**: May need to adjust criteria or data sources

### Cache Hit Rates
- **Places API**: 50%+ expected (30-day TTL)
- **LLM Extractions**: 70%+ expected (90-day TTL)
- **Cost Savings**: ~50% API cost reduction

---

## 🚨 Troubleshooting

### No Leads Qualified

1. Check gate rejection stats in output
2. Most common: `category_blocked` or `geo_blocked`
3. Review borderline cases: `python scripts/review_queue.py`

### High API Costs

1. Check cache hit rate: `python scripts/metrics_dashboard.py`
2. Verify cache database exists: `ls -la data/api_cache.db`
3. Increase cache TTL if needed (config.py)

### Retail Leakage (Retail businesses passing)

1. **This should NEVER happen** with new gates
2. Run acceptance test: `pytest tests/test_acceptance_simple.py::TestDefinitionOfDone::test_manufacturing_passes_category_gate`
3. Check category gate configuration
4. Report as critical bug

---

## 📊 Monitoring & Observability

### Key Metrics to Watch

1. **Gate Pass Rates**
   - Category: ~40% pass (60% blocked/review)
   - Revenue: ~30% pass (70% fail confidence/evidence)
   - Geo: ~80% pass (20% outside area)

2. **Quality Indicators**
   - Duplicate rate: <1%
   - Retail leakage: 0% (must be zero!)
   - HITL review queue: 10-15% of discoveries

3. **System Health**
   - API response times: <2s average
   - Cache hit rate: >50%
   - Error rate: <5%

### Weekly Review

```bash
python scripts/metrics_dashboard.py
```

Generates report with:
- Trend analysis
- Recommendations
- Cost tracking
- Performance metrics

---

## ✅ Production Readiness Checklist

Before going live:

- [ ] Update `.env` with production API keys
- [ ] Run all tests: `pytest tests/ -v`
- [ ] Verify 98/98 tests passing
- [ ] Test with 100 leads: `./generate_v2 100 --show`
- [ ] Confirm 0 retail leakage in results
- [ ] Backup existing database: `cp data/leads_v2.db data/leads_v2.backup.$(date +%Y%m%d).db`
- [ ] Set environment to production: `ENVIRONMENT=production`
- [ ] Disable debug mode: `DEBUG=false`
- [ ] Review borderline cases: `python scripts/review_queue.py`
- [ ] Check metrics: `python scripts/metrics_dashboard.py`

---

## 📞 Support & Documentation

- **Full Documentation**: See `README.md`
- **Implementation Details**: See `DEPLOYMENT_VERIFICATION.md`
- **Component Status**: See `COMPONENT_STATUS.md`
- **Legacy Components**: See `scripts/legacy/old_pipelines/README.md`

---

**Production Command**: `./generate_v2 [count] --show`

**Everything else**: Archived or deprecated

**Status**: ✅ Ready for deployment
