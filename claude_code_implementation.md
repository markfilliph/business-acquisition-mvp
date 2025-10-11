# Claude Code Implementation Plan
## Lead Validation Pipeline - Production Hardening

**Project**: Business Lead Validation & Enrichment System  
**Status**: Week 1 Complete (35% production-ready)  
**Tool**: Claude Code (agentic CLI coding assistant)  
**Timeline**: 4 weeks to production-grade

---

## 🎯 Project Context

**What This Is**:
- Lead validation/enrichment pipeline (SQLite-based)
- Separate from your outreach system (Google Sheets-based)
- Feeds clean, validated leads TO your outreach system

**Current Structure** (per deployment docs):
```
business-lead-pipeline/
├── src/
│   ├── sources/places.py          # ✅ Places API integration
│   ├── models/extraction_schemas.py # ✅ Pydantic models
│   ├── prompts/extraction_prompts.py # ✅ LLM prompts
│   ├── services/llm_service.py    # ✅ OpenAI integration
│   ├── gates/                     # ⚠️ Partially complete
│   └── database/                  # ✅ Basic schema exists
├── scripts/
│   └── expand_type_mappings.py    # ✅ Complete
├── tests/
│   └── test_llm_extraction.py     # ✅ Complete
└── data/
    └── leads_v2.db                # ✅ SQLite database
```

**Dependencies** (inferred from deployment status):
```python
# requirements.txt
openai>=1.0.0           # LLM extraction
anthropic>=0.8.0        # Claude integration (your use)
pydantic>=2.0.0         # Schema validation
sqlite3                 # Database (stdlib)
requests>=2.31.0        # API calls
googlemaps>=4.10.0      # Places API
python-dotenv>=1.0.0    # Config management
tenacity>=8.2.0         # Retry logic (to be added)
redis>=5.0.0            # Caching (optional, or use SQLite)
```

---

## 📋 Claude Code Task Breakdown

### How to Use This Plan with Claude Code

**For each task below**:
1. Copy the **Claude Code Prompt** 
2. Run in terminal: `claude-code "<paste prompt here>"`
3. Review changes, test, commit
4. Move to next task

**Pro Tips**:
- Claude Code handles multi-file changes efficiently
- Always review security-sensitive code (API keys, auth)
- Run tests after each task before moving on
- Commit after each successful task

---

## 🚨 Week 2: P0 Blockers (Critical Path)

### Task 1: Entity Resolution & Fingerprinting

**Priority**: P0 (blocks production)  
**Estimated Effort**: 4 hours  
**Files Created**: 3  
**Files Modified**: 2

**Claude Code Prompt**:
```
Create an entity resolution system for business lead deduplication:

1. Create src/utils/fingerprinting.py:
   - Function: compute_business_fingerprint(name, street, city, postal, phone, url)
   - Normalize inputs (lowercase, strip punctuation, remove common suffixes)
   - Return SHA256 hash of concatenated normalized fields
   - Handle None values gracefully

2. Create src/database/upsert_logic.py:
   - Function: upsert_business(db_conn, business_data)
   - Check if fingerprint exists in database
   - If exists: UPDATE with merged observations
   - If new: INSERT new business record
   - Return (business_id, was_duplicate: bool)

3. Create tests/test_entity_resolution.py:
   - Test: Same business with different formatting is deduplicated
   - Test: "ABC Inc." and "ABC Incorporated" have same fingerprint
   - Test: Different businesses have different fingerprints
   - Test: Upsert merges observations correctly

4. Modify src/database/schema.sql:
   - Add fingerprint VARCHAR(64) to businesses table
   - Add UNIQUE constraint on fingerprint
   - Add index on fingerprint for fast lookups

5. Modify src/orchestrator.py (or wherever businesses are created):
   - Replace INSERT with upsert_business() calls
   - Log duplicate detections with metrics

Requirements:
- Use hashlib.sha256() for fingerprinting
- Normalize: lowercase, strip whitespace, remove "Inc.", "Ltd.", "LLC"
- Phone normalization: digits only (no hyphens/parens)
- URL normalization: remove http://, www., trailing slash
- Include comprehensive error handling
- Add docstrings with examples

Test command: pytest tests/test_entity_resolution.py -v
```

**Definition of Done**:
- [ ] Running on 100-lead sample shows 0 duplicates
- [ ] "ABC Inc" and "ABC Incorporated" deduplicated
- [ ] Tests pass with 100% coverage

---

### Task 2: Address Normalization

**Priority**: P0 (blocks production)  
**Estimated Effort**: 5 hours  
**Files Created**: 2  
**Files Modified**: 1

**Claude Code Prompt**:
```
Create a Canada Post-compliant address normalization system:

1. Create src/utils/address_normalizer.py:
   - Function: normalize_address(address_string) -> dict
   - Parse components: street_num, street_name, street_type, unit, city, province, postal
   - Expand abbreviations using CANADA_POST_ABBREV dict:
     * St -> Street, Ave -> Avenue, Rd -> Road, Blvd -> Boulevard
     * Dr -> Drive, Crt -> Court, Cres -> Crescent, etc.
   - Standardize case: Title Case for streets, UPPERCASE for postal
   - Remove extra whitespace and punctuation
   - Return structured dict with all components

2. Create address comparison function: addresses_match(addr1, addr2, fuzzy=True)
   - Normalize both addresses
   - Compare components individually
   - If fuzzy=True, allow minor differences (St vs Street after normalization)
   - Return (match: bool, confidence: float)

3. Create tests/test_address_normalization.py:
   - Test: "123 Main St" == "123 Main Street"
   - Test: "456 King St E, Unit 7" == "456 King Street East #7"
   - Test: Postal code formatting (L8P 4R5 vs L8P4R5)
   - Test: Different addresses return False
   - Test: Case insensitivity

4. Modify src/gates/corroboration.py (or wherever corroboration happens):
   - Use normalize_address() before comparing
   - Use addresses_match() instead of string equality
   - Update tests to verify normalization is used

Constants needed:
CANADA_POST_ABBREV = {
    "St": "Street", "Ave": "Avenue", "Rd": "Road",
    "Blvd": "Boulevard", "Dr": "Drive", "Ln": "Lane",
    "Crt": "Court", "Cres": "Crescent", "Terr": "Terrace",
    "Pl": "Place", "Pk": "Park", "Sq": "Square",
    "E": "East", "W": "West", "N": "North", "S": "South"
}

Use regex for parsing street numbers, unit numbers, postal codes.
Handle edge cases: PO Boxes, rural routes, no street number.

Test command: pytest tests/test_address_normalization.py -v
```

**Definition of Done**:
- [ ] "123 Main St" matches "123 Main Street"
- [ ] Corroboration gate stops false negatives
- [ ] Tests pass with 90%+ confidence on real addresses

---

### Task 3: Website Age Gate (Complete Implementation)

**Priority**: P0 (blocks production)  
**Estimated Effort**: 4 hours  
**Files Created**: 2  
**Files Modified**: 2

**Claude Code Prompt**:
```
Implement complete website age verification using Wayback Machine:

1. Create src/services/wayback_service.py:
   - Function: get_website_age(url) -> dict
   - Call Wayback Machine CDX API: http://web.archive.org/cdx/search/cdx?url={url}&limit=1
   - Parse earliest snapshot timestamp
   - Calculate age in years from earliest to today
   - Return {first_seen: datetime, age_years: float, snapshot_count: int}
   - Handle errors: no snapshots found, API timeout, invalid URL

2. Create parked domain detector: is_parked_domain(url) -> bool
   - Fetch URL content with requests
   - Check for common parking patterns:
     * "This domain is for sale"
     * "GoDaddy" parking page indicators
     * "Namecheap" parking page indicators
     * Redirect to domain marketplace
   - Return True if parked, False otherwise

3. Modify src/gates/website_gate.py:
   - Implement website_gate(business) -> dict
   - Check if website URL exists and is valid
   - Call get_website_age() to get age
   - Call is_parked_domain() to check legitimacy
   - Set website_ok = True if: age >= 3 years AND not parked
   - Store website_age_years in validations table
   - Return validation record with reason

4. Create tests/test_website_gate.py:
   - Test: New domain (< 3 years) fails gate
   - Test: Old domain (> 3 years) passes gate
   - Test: Parked domain fails gate
   - Test: No snapshots in Wayback returns age = 0
   - Mock Wayback API responses

5. Modify src/gates/export_gate.py (or is_exportable function):
   - Add check: if category == "sign_shop", require website_age_years >= 3
   - For all businesses, require website_ok == True to export
   - Log rejection reason if website gate fails

Use environment variable: WAYBACK_API_TIMEOUT = 10 seconds
Include rate limiting: max 1 request/second to Wayback API
Add caching: store results in SQLite for 30 days

Test command: pytest tests/test_website_gate.py -v
```

**Definition of Done**:
- [ ] Sign shops < 3 years old blocked from export
- [ ] Parked domains detected and blocked
- [ ] Wayback API integration tested with real domains

---

### Task 4: Orchestrator Resilience (Retries + Circuit Breaker)

**Priority**: P0 (blocks production)  
**Estimated Effort**: 5 hours  
**Files Created**: 2  
**Files Modified**: 3

**Claude Code Prompt**:
```
Add production-grade resilience to the orchestrator with retries and circuit breakers:

1. Create src/utils/resilience.py:
   - Decorator: @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0)
   - Implements exponential backoff with jitter
   - Retries on: requests.RequestException, Timeout, ConnectionError
   - Does NOT retry on: 400 errors, 401 auth failures, 404 not found
   - Logs each retry attempt with backoff duration

   - Class: CircuitBreaker(failure_threshold=5, recovery_timeout=60)
   - States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
   - Opens after N consecutive failures
   - Stays open for recovery_timeout seconds
   - Attempts one test call in HALF_OPEN state
   - Returns to CLOSED if test succeeds, OPEN if fails
   - Logs state transitions

2. Create tests/test_resilience.py:
   - Test retry decorator with mock flapping API
   - Test circuit breaker opens after 5 failures
   - Test circuit breaker recovers after timeout
   - Test jitter adds randomness to backoff
   - Test non-retryable errors (400, 401) fail immediately

3. Modify src/sources/places.py:
   - Wrap Places API calls with @retry_with_backoff
   - Wrap in CircuitBreaker instance
   - Log when circuit breaker opens/closes
   - Return None when circuit open (don't crash)

4. Modify src/services/llm_service.py:
   - Wrap OpenAI calls with @retry_with_backoff
   - Handle rate limit errors (429) with longer backoff
   - Log retry attempts and circuit breaker state

5. Modify src/orchestrator.py:
   - Initialize circuit breakers for each external service
   - Track failed enrichments separately (don't lose data)
   - Set business status to DEFERRED if circuit open
   - Log summary: X succeeded, Y failed, Z deferred

Dependencies to add to requirements.txt:
- tenacity>=8.2.0 (for retry logic)

Configuration (add to .env):
- RETRY_MAX_ATTEMPTS=3
- RETRY_BASE_DELAY=1.0
- CIRCUIT_BREAKER_THRESHOLD=5
- CIRCUIT_BREAKER_TIMEOUT=60

Test command: pytest tests/test_resilience.py -v
```

**Definition of Done**:
- [ ] API failures automatically retry with backoff
- [ ] Circuit breaker prevents cascade failures
- [ ] Deferred status set when circuit open
- [ ] No silent data loss on network errors

---

### Task 5: Rate Limiting & Quota Management

**Priority**: P0 (blocks production)  
**Estimated Effort**: 4 hours  
**Files Created**: 2  
**Files Modified**: 3

**Claude Code Prompt**:
```
Implement token bucket rate limiting for all external APIs:

1. Create src/utils/rate_limiter.py:
   - Class: TokenBucketLimiter(rate_per_second, burst_size)
   - Method: acquire() -> bool (returns True if token available)
   - Method: wait() (blocks until token available)
   - Uses threading.Lock for thread safety
   - Refills tokens at steady rate
   - Allows bursts up to burst_size

   - Class: RateLimitRegistry (singleton pattern)
   - Manages multiple limiters by API name
   - Factory method: get_limiter(api_name) -> TokenBucketLimiter
   - Loads limits from config/environment

2. Create tests/test_rate_limiting.py:
   - Test: Can't exceed rate limit (10 requests/sec blocked on 11th)
   - Test: Burst allows temporary spike
   - Test: Tokens refill over time
   - Test: Multiple limiters don't interfere
   - Test: Thread safety with concurrent requests

3. Modify src/sources/places.py:
   - Create limiter: places_limiter = RateLimitRegistry.get_limiter("google_places")
   - Call places_limiter.acquire() before each API call
   - If quota exhausted, return None and log "quota exceeded"
   - Set observation status to DEFERRED if quota hit

4. Modify src/services/llm_service.py:
   - Create limiter: llm_limiter = RateLimitRegistry.get_limiter("openai")
   - Rate limit: 50 requests/minute for OpenAI
   - If quota exhausted, set extraction status to DEFERRED
   - Track skipped extractions in metrics

5. Modify src/orchestrator.py:
   - Count DEFERRED businesses separately
   - Log: "X businesses deferred due to quota limits"
   - Add to weekly report: quota usage by API

Configuration (add to .env):
- GOOGLE_PLACES_RATE_LIMIT=10  # per second
- OPENAI_RATE_LIMIT=50          # per minute
- YELP_RATE_LIMIT=5             # per second

Test command: pytest tests/test_rate_limiting.py -v
```

**Definition of Done**:
- [ ] API calls respect rate limits
- [ ] DEFERRED status set when quota exceeded
- [ ] Weekly report shows quota usage metrics
- [ ] No unexpected API bills

---

## ⚠️ Week 3: P1 Critical Gaps

### Task 6: Centralized Config Management

**Priority**: P1  
**Estimated Effort**: 2 hours

**Claude Code Prompt**:
```
Create 12-factor config management with Pydantic validation:

1. Create src/config.py:
   - Class: AppConfig(BaseSettings) using pydantic-settings
   - Fields for all API keys (GOOGLE_PLACES_API_KEY, OPENAI_API_KEY, etc.)
   - Fields for thresholds (REVENUE_CONFIDENCE_THRESHOLD=0.6, GEO_RADIUS_KM=15, etc.)
   - Fields for rate limits
   - Validation: fail fast on startup if required keys missing
   - Load from .env file using python-dotenv

2. Create .env.example:
   - Template with all required variables
   - Comments explaining each variable
   - Safe defaults where applicable

3. Modify all files using config:
   - Replace hardcoded API keys with config.GOOGLE_PLACES_API_KEY
   - Replace magic numbers with config.REVENUE_CONFIDENCE_THRESHOLD
   - Import: from src.config import config (singleton)

4. Create tests/test_config.py:
   - Test: Missing required key raises ValidationError
   - Test: Invalid threshold (negative) raises error
   - Test: Config loads from .env correctly

Add to requirements.txt: pydantic-settings>=2.0.0

Test command: pytest tests/test_config.py -v
```

---

### Task 7: Strict Revenue Gate Enforcement

**Priority**: P1  
**Estimated Effort**: 2 hours

**Claude Code Prompt**:
```
Implement strict revenue gate requirements per validator feedback:

1. Modify src/gates/revenue_gate.py:
   - Update revenue_gate(business) function
   - Requirements for export:
     * confidence >= 0.6 (from config.REVENUE_CONFIDENCE_THRESHOLD)
     * AND (staff_count is not None OR benchmark_match is True)
   - Remove any "warn and pass" logic
   - Log rejection reason: "confidence too low" or "no staff/benchmark signal"

2. Create tests/test_revenue_gate.py:
   - Test: confidence=0.5 fails even with staff_count
   - Test: confidence=0.7 + staff_count passes
   - Test: confidence=0.7 + benchmark passes
   - Test: confidence=0.7 + neither fails
   - Test: rejection reason logged correctly

3. Create acceptance test: tests/test_acceptance_revenue.py:
   - Run on golden test set (known bad cases)
   - Assert: 0 businesses with confidence < 0.6 exported
   - Assert: 0 businesses without staff/benchmark exported

Test command: pytest tests/test_revenue_gate.py tests/test_acceptance_revenue.py -v
```

---

### Task 8: Geo Allowlist (Dual Enforcement)

**Priority**: P1  
**Estimated Effort**: 2 hours

**Claude Code Prompt**:
```
Implement dual geo enforcement (radius AND city allowlist):

1. Modify src/gates/geo_gate.py:
   - Add ALLOWED_CITIES = ["Hamilton", "Ancaster", "Dundas", "Stoney Creek", "Waterdown"]
   - Update geo_gate(business) function:
     * Check 1: within radius (existing haversine logic)
     * Check 2: city in ALLOWED_CITIES
     * Both must pass for geo_ok = True
   - Log rejection reason: "outside radius" or "city not allowed"

2. Create tests/test_geo_gate.py:
   - Test: Inside radius + allowed city = pass
   - Test: Inside radius + disallowed city = fail
   - Test: Outside radius + allowed city = fail
   - Test: Outside radius + disallowed city = fail

3. Create acceptance test: tests/test_acceptance_geo.py:
   - Run on golden test set
   - Assert: 0 businesses outside allowed cities exported

Move ALLOWED_CITIES to config.py for easy updates.

Test command: pytest tests/test_geo_gate.py tests/test_acceptance_geo.py -v
```

---

### Task 9: HTTP & API Response Caching

**Priority**: P1  
**Estimated Effort**: 4 hours

**Claude Code Prompt**:
```
Implement SQLite-based API response caching:

1. Create src/utils/cache.py:
   - Class: APICache(db_path="data/api_cache.db")
   - Method: get(key) -> value or None
   - Method: set(key, value, ttl_seconds=2592000)  # 30 days default
   - Method: invalidate(key)
   - Method: get_stats() -> {hits: int, misses: int, hit_rate: float}
   - Uses SQLite with schema: (key TEXT PRIMARY KEY, value TEXT, expires_at INTEGER)
   - Auto-cleanup expired entries on startup

2. Create cache decorator: @cached(ttl_seconds=2592000, key_func=None)
   - Wraps functions to cache results
   - key_func generates cache key from function args
   - Stores JSON-serialized results

3. Modify src/sources/places.py:
   - Wrap get_place_details() with @cached decorator
   - Cache key: f"places:{name}:{address}" (normalized)
   - TTL: 30 days
   - Log cache hits/misses

4. Modify src/services/llm_service.py:
   - Cache LLM extractions by URL
   - Cache key: f"llm_extract:{url_hash}"
   - TTL: 90 days (extractions rarely change)

5. Create tests/test_cache.py:
   - Test: Second call returns cached value
   - Test: Expired entries not returned
   - Test: Cache stats accurate
   - Test: Thread safety

6. Add cache metrics to weekly report:
   - Places API cache hit rate
   - LLM extraction cache hit rate
   - Cost savings from caching

Test command: pytest tests/test_cache.py -v
```

---

### Task 10: HITL Review Queue

**Priority**: P1  
**Estimated Effort**: 4 hours

**Claude Code Prompt**:
```
Create human-in-the-loop review queue for borderline cases:

1. Modify src/database/schema.sql:
   - Add status value: REVIEW_REQUIRED
   - Add review_reason TEXT to businesses table
   - Add reviewed_by TEXT, reviewed_at TIMESTAMP

2. Modify src/gates/category_gate.py:
   - Add REVIEW_REQUIRED_CATEGORIES = ["funeral_home", "franchise_office"]
   - If category in list, set status = REVIEW_REQUIRED
   - Set review_reason = "borderline category: {category}"

3. Create scripts/review_queue.py:
   - CLI tool for analysts to review leads
   - Commands:
     * list - Show all REVIEW_REQUIRED leads
     * approve {business_id} --reason "..." - Set to QUALIFIED
     * reject {business_id} --reason "..." - Set to EXCLUDED
     * stats - Show queue size and processing stats
   - Requires analyst to provide reason for all decisions
   - Logs all actions with timestamp

4. Modify src/gates/export_gate.py:
   - Export gate excludes REVIEW_REQUIRED status
   - Only QUALIFIED businesses exported
   - Log: "X businesses in review queue, not exported"

5. Create tests/test_review_queue.py:
   - Test: Funeral home auto-set to REVIEW_REQUIRED
   - Test: Export gate excludes REVIEW_REQUIRED
   - Test: Approve command changes status to QUALIFIED
   - Test: All actions logged with reason

Usage example:
./scripts/review_queue.py list
./scripts/review_queue.py approve 123 --reason "Verified family-owned operation"

Test command: pytest tests/test_review_queue.py -v
```

---

### Task 11: Observability Dashboard

**Priority**: P1  
**Estimated Effort**: 5 hours

**Claude Code Prompt**:
```
Create metrics dashboard for monitoring pipeline health:

1. Create src/utils/metrics.py:
   - Class: MetricsCollector (singleton)
   - Methods to track:
     * increment(metric_name, value=1, tags={})
     * gauge(metric_name, value, tags={})
     * histogram(metric_name, value, tags={})
   - Store in SQLite: metrics table (timestamp, name, value, tags_json)

2. Instrument existing code:
   - src/gates/*.py: Track pass/fail rates per gate
   - src/sources/places.py: Track API call latency, errors
   - src/services/llm_service.py: Track null_rate, hallucination_rate
   - src/orchestrator.py: Track overall pipeline metrics

3. Create scripts/metrics_dashboard.py:
   - Weekly report generation
   - Sections:
     * Overall: X leads processed, Y exported, Z excluded
     * Gate Performance: Category (90% pass), Geo (75% pass), etc.
     * API Health: Places (95% success, 45ms avg), LLM (88% success)
     * Top Failures: 10 most common rejection reasons
     * Precision/Recall: Confusion matrix vs golden test set
     * Cost Summary: API spend by service
   - Output: Markdown report + CSV for trends

4. Create golden set comparison:
   - Store golden test results in data/golden_results.json
   - Compare current run vs golden set
   - Calculate: precision, recall, F1 score per rule
   - Flag: rules with >10% precision drop

5. Create tests/test_metrics.py:
   - Test: Metrics stored correctly
   - Test: Dashboard generates without errors
   - Test: Precision/recall calculated correctly

Run: ./scripts/metrics_dashboard.py --period weekly

Test command: pytest tests/test_metrics.py -v
```

---

### Task 12: Explicit Acceptance Tests

**Priority**: P1  
**Estimated Effort**: 2 hours

**Claude Code Prompt**:
```
Create explicit acceptance tests for validator requirements:

1. Create tests/test_acceptance_corroboration.py:
   - Test: "Only export leads with ≥2 corroborated fields"
   - Create business with only 1 address observation
   - Assert: is_exportable() returns False
   - Assert: Reason includes "insufficient corroboration"

2. Create tests/test_acceptance_retail.py:
   - Test: "Zero retail leakage"
   - Load golden bad cases (Eastgate Variety, gas stations, etc.)
   - Run through full pipeline
   - Assert: 0 retail businesses have status QUALIFIED
   - Assert: All blocked by category_gate

3. Create tests/test_acceptance_fabrication.py:
   - Test: "No fabricated fields"
   - Run LLM extraction on website with partial data
   - Assert: Missing fields are None, not hallucinated
   - Assert: All non-None fields have source_url in observation

4. Create tests/test_acceptance_export_gate.py:
   - Test: "Strict exportability"
   - Create business failing each gate (category, geo, revenue, etc.)
   - Assert: Each correctly excluded
   - Assert: Blocked report contains rejection reason

5. Integrate into CI:
   - Add pytest.ini marker: @pytest.mark.acceptance
   - Configure CI to fail if any acceptance test fails
   - Run on every merge to main

Run: pytest -m acceptance -v

These tests define your "Definition of Done" for production.
```

---

## 🗓️ Revised Claude Code Sprint Schedule

### Week 2 (Oct 14-18): P0 Foundation
**Monday-Tuesday**: Tasks 1-2 (Entity Resolution + Address Norm)  
**Wednesday-Thursday**: Tasks 3-4 (Website Age + Resilience)  
**Friday**: Task 5 (Rate Limiting) + Integration Testing

**Weekly Goal**: 0 duplicates, 0 silent failures on 100-lead test

---

### Week 3 (Oct 21-25): P1 Quality
**Monday**: Tasks 6-7 (Config + Revenue Gate)  
**Tuesday**: Task 8 (Geo Allowlist)  
**Wednesday-Thursday**: Tasks 9-10 (Caching + HITL)  
**Friday**: Integration testing + fixes

**Weekly Goal**: <5% borderline cases, 60%+ cache hit rate

---

### Week 4 (Oct 28-Nov 1): P1 Observability
**Monday-Wednesday**: Task 11 (Observability Dashboard)  
**Thursday**: Task 12 (Acceptance Tests)  
**Friday**: Full production dry-run on 500 leads

**Weekly Goal**: All acceptance tests pass, metrics dashboard live

---

### Week 5 (Nov 4-8): Polish & Production
**Monday-Tuesday**: Fix any issues from 500-lead run  
**Wednesday**: Documentation, runbooks  
**Thursday**: Security audit, PII policy  
**Friday**: 🚀 Production deployment

---

## 📊 Claude Code Efficiency Tips

### Batch Related Tasks
Claude Code works best when you combine related changes:
```bash
# GOOD: One prompt for entity resolution (all related files)
claude-code "Create entity resolution: fingerprinting.py, upsert_logic.py, tests, schema migration"

# LESS EFFICIENT: Separate prompts per file
claude-code "Create fingerprinting.py"
claude-code "Create upsert_logic.py"
```

### Provide Context Files
Help Claude Code by referencing existing files:
```bash
claude-code "Modify src/gates/revenue_gate.py to enforce strict thresholds. 
Existing logic is in src/gates/category_gate.py for reference on gate structure."
```

### Iterative Refinement
Review Claude Code's output, then refine:
```bash
# First pass
claude-code "Create address normalizer"

# Review output, then refine
claude-code "Improve address_normalizer.py: add support for PO Boxes and rural routes"
```

### Test-Driven Prompts
Ask for tests first to clarify requirements:
```bash
claude-code "Write tests for entity resolution showing desired behavior, 
then implement fingerprinting.py to make tests pass"
```

---

## 🔧 Environment Setup (One-Time)

**Before starting Week 2, run**:

```bash
# Create .env from validator requirements
cat > .env << EOF
# API Keys
GOOGLE_PLACES_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
YELP_API_KEY=your_key_here

# Rate Limits (requests per period)
GOOGLE_PLACES_RATE_LIMIT=10
OPENAI_RATE_LIMIT=50
YELP_RATE_LIMIT=5

# Thresholds
REVENUE_CONFIDENCE_THRESHOLD=0.6
WEBSITE_MIN_AGE_YEARS=3
GEO_RADIUS_KM=15

# Allowed Cities (comma-separated)
ALLOWED_CITIES=Hamilton,Ancaster,Dundas,Stoney Creek,Waterdown

# Retry Config
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY=1.0
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60

# Cache TTLs (seconds)
PLACES_CACHE_TTL=2592000  # 30 days
LLM_CACHE_TTL=7776000     # 90 days
EOF

# Update requirements.txt
cat >> requirements.txt << EOF
# Week 2 additions
tenacity>=8.2.0           # Retry logic
pydantic-settings>=2.0.0  # Config management

# Week 3 additions
python-dotenv>=1.0.0      # .env loading
EOF

# Install dependencies
pip install -r requirements.txt
```

---

## 🎯 Success Metrics (Weekly Checkpoints)

### Week 2 Exit Criteria
- [ ] pytest tests/ passes 100%
- [ ] 100-lead test shows 0 duplicates
- [ ] API failure recovery demonstrated
- [ ] Rate limiter prevents quota overrun

### Week 3 Exit Criteria
- [ ] Cache hit rate >60%
- [ ] Review queue functional
- [ ] All gates enforce strict thresholds
- [ ] Config loaded from .env

### Week 4 Exit Criteria
- [ ] Metrics dashboard generates weekly report
- [ ] All 12 acceptance tests pass
- [ ] 500-lead dry-run successful
- [ ] Precision/recall meet targets

### Week 5 Go-Live Criteria
- [ ] Definition of Done: 4/4 complete
- [ ] Zero retail leakage on 500 leads
- [ ] 100% evidence coverage
- [ ] Blocked report explains all exclusions
- [ ] Runbook and documentation complete

---

## 🚨 Common Claude Code Pitfalls

**Avoid**:
- ❌ Asking for "production-grade" without specifics (Claude Code needs concrete requirements)
- ❌ Not providing existing file references (leads to inconsistent patterns)
- ❌ Skipping tests (Claude Code generates better code when tests guide it)
- ❌ Batch too many unrelated changes (harder to review, debug)

**Do**:
- ✅ Be specific: "Add retry with exponential backoff, max 3 attempts"
- ✅ Reference patterns: "Follow the structure in category_gate.py"
- ✅ Start with tests: "Write tests showing desired behavior first"
- ✅ Review incrementally: Check each file Claude Code generates

---

## 💡 Next Immediate Action

**Run this command to start Week 2**:

```bash
# Task 1: Entity Resolution (highest ROI)
claude-code "Create entity resolution system for business lead deduplication:

1. Create src/utils/fingerprinting.py with compute_business_fingerprint()
2. Create src/database/upsert_logic.py with upsert_business()
3. Create comprehensive tests in tests/test_entity_resolution.py
4. Modify schema to add fingerprint column with unique constraint
5. Update orchestrator to use upsert instead of insert

Use SHA256 hashing, normalize all inputs (lowercase, strip punctuation), 
handle None gracefully. Include docstrings and error handling."
```

**Then review, test, commit, and move to Task 2.**

---

**Generated**: October 10, 2025  
**Tool**: Claude Code (agentic CLI)  
**Timeline**: 4 weeks to production  
**Current Status**: Ready to start Week 2 P0 tasks