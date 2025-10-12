# Implementation Plan Updates - Senior Dev Review Applied

## Critical Changes to Apply to IMPLEMENTATION_PLAN.md

This document contains all required changes based on the senior dev review. Apply these systematically to the main implementation plan.

---

## 1. DATABASE SCHEMA UPDATES (Phase 1.1)

### Replace businesses table definition with:

```sql
-- Core business record (canonical)
CREATE TABLE businesses (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,  -- Stable hash for de-duplication
    normalized_name TEXT NOT NULL,
    original_name TEXT,
    street TEXT,
    city TEXT,
    postal_code TEXT,
    province TEXT,
    phone TEXT,
    website TEXT,
    latitude REAL,
    longitude REAL,
    distance_km REAL,
    status TEXT DEFAULT 'DISCOVERED',  -- DISCOVERED, GEOCODED, ENRICHED, VALIDATED, QUALIFIED, EXCLUDED, REVIEW_REQUIRED, EXPORTED
    manual_override BOOLEAN DEFAULT FALSE,
    override_reason TEXT,
    override_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_businesses_status ON businesses(status);
CREATE INDEX idx_businesses_fingerprint ON businesses(fingerprint);
```

### Update observations table to include:

```sql
-- Evidence ledger (enhanced with source metadata)
CREATE TABLE observations (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT,
    confidence REAL DEFAULT 1.0,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    http_status INTEGER,
    api_version TEXT,
    error TEXT,
    FOREIGN KEY(business_id) REFERENCES businesses(id)
);

CREATE INDEX idx_observations_business_field ON observations(business_id, field);
```

### Add validation version tracking table:

```sql
-- Validation version tracking
CREATE TABLE validation_versions (
    version INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    config_snapshot TEXT,  -- JSON of rules at this version
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 2. NEW MODULE: Entity Resolution & Normalization (Phase 1.4 - NEW)

**Create** `src/core/normalization.py`:

```python
"""
Entity resolution and fingerprinting for de-duplication.
PRIORITY: P0 - Must implement in Week 1 before any enrichment.
"""

import hashlib
import re
from typing import Dict, Optional

def compute_fingerprint(business: Dict) -> str:
    """
    Compute stable fingerprint for business de-duplication.

    Combines:
    - Normalized name (strip Inc/Ltd/Corp, lowercase, no punct)
    - Street number + normalized street name
    - City + postal first 3 chars
    - Phone digits (if available)

    Returns: SHA256 hash (first 16 chars for readability)
    """
    # Normalize name
    name = business.get('name', '').lower()
    name = re.sub(r'\b(inc|ltd|corp|incorporated|limited|corporation)\b', '', name)
    name = re.sub(r'[^\w\s]', '', name).strip()

    # Normalize street
    street = business.get('street', '').lower()
    street = re.sub(r'\b(street|st|avenue|ave|road|rd|drive|dr|boulevard|blvd)\b', '', street)
    street = re.sub(r'[^\w\s\d]', '', street).strip()

    # Extract street number
    street_match = re.match(r'^(\d+)', street)
    street_num = street_match.group(1) if street_match else ''

    # City + postal prefix
    city = business.get('city', '').lower().strip()
    postal = business.get('postal_code', '').upper().replace(' ', '')[:3]

    # Phone digits only
    phone = business.get('phone', '')
    phone_digits = re.sub(r'\D', '', phone)

    # Combine components
    components = [name, street_num, street, city, postal, phone_digits]
    fingerprint_str = '|'.join(c for c in components if c)

    # Hash
    hash_obj = hashlib.sha256(fingerprint_str.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def normalize_name(name: str) -> str:
    """Normalize business name for comparison."""
    name = name.lower()
    name = re.sub(r'\b(inc|ltd|corp|incorporated|limited|corporation|llc)\b', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return ' '.join(name.split())


def normalize_address(address: str) -> Dict[str, str]:
    """
    Parse and normalize address into components.
    Returns: {street_number, street_name, city, postal}
    """
    # Expand abbreviations
    address = re.sub(r'\bSt\b', 'Street', address, flags=re.IGNORECASE)
    address = re.sub(r'\bAve\b', 'Avenue', address, flags=re.IGNORECASE)
    address = re.sub(r'\bRd\b', 'Road', address, flags=re.IGNORECASE)
    address = re.sub(r'\bDr\b', 'Drive', address, flags=re.IGNORECASE)
    address = re.sub(r'\bBlvd\b', 'Boulevard', address, flags=re.IGNORECASE)

    # TODO: Integrate with libpostal or Canada Post API for robust parsing
    return {
        'normalized': address.lower().strip().replace('.', ''),
        'original': address
    }


def upsert_business(db, business_data: Dict) -> tuple[int, bool]:
    """
    Idempotent business insert/update.

    Returns: (business_id, is_new)
    """
    fingerprint = compute_fingerprint(business_data)

    existing = db.execute(
        "SELECT id FROM businesses WHERE fingerprint = ?",
        (fingerprint,)
    ).fetchone()

    if existing:
        # Update existing
        db.execute(
            "UPDATE businesses SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (existing['id'],)
        )
        return existing['id'], False
    else:
        # Insert new
        cursor = db.execute(
            """INSERT INTO businesses
            (fingerprint, normalized_name, original_name, street, city, postal_code, phone, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'DISCOVERED')""",
            (
                fingerprint,
                normalize_name(business_data.get('name', '')),
                business_data.get('name'),
                business_data.get('street'),
                business_data.get('city'),
                business_data.get('postal_code'),
                business_data.get('phone'),
            )
        )
        return cursor.lastrowid, True
```

---

## 3. PLACES TYPE MAPPING (Phase 2.3 Enhancement)

**Add to** `src/sources/places.py`:

```python
"""
PRIORITY: P0 - Must build mapping tables by scraping 100 sample businesses in Week 1.
"""

# Canonical type vocabulary (aligned with whitelist/blacklist)
GOOGLE_TO_CANONICAL = {
    'accounting': 'business_consulting',
    'business_consultant': 'business_consulting',
    'consultant': 'business_consulting',
    'car_dealer': 'car_dealer',
    'car_dealership': 'auto_dealership',
    'convenience_store': 'convenience_store',
    'gas_station': 'gas_station',
    'store': 'retail_general',
    'food': 'restaurant',
    'restaurant': 'restaurant',
    # ... MUST BUILD COMPLETE MAPPING (200+ entries)
}

YELP_TO_CANONICAL = {
    'business-consulting': 'business_consulting',
    'auto-dealers': 'car_dealer',
    'convenience-stores': 'convenience_store',
    # ... COMPLETE MAPPING REQUIRED
}

OSM_TO_CANONICAL = {
    'office=consulting': 'business_consulting',
    'shop=car': 'car_dealer',
    'shop=convenience': 'convenience_store',
    # ... COMPLETE MAPPING REQUIRED
}

def map_place_types(raw_types: list[str], source: str) -> set[str]:
    """Map raw place types from source to canonical vocabulary."""
    mapping = {
        'google': GOOGLE_TO_CANONICAL,
        'yelp': YELP_TO_CANONICAL,
        'osm': OSM_TO_CANONICAL,
    }.get(source, {})

    canonical = set()
    for raw_type in raw_types:
        if raw_type in mapping:
            canonical.add(mapping[raw_type])
        else:
            # Log unmapped types for manual review
            logger.warning(f"Unmapped {source} type: {raw_type}")

    return canonical
```

**ACTION REQUIRED**: Before Week 1 ends, run:
```bash
python3 scripts/build_type_mappings.py --sample-size 100 --output src/sources/type_mappings.json
```

---

## 4. CONFLICT RESOLUTION & HITL (Phase 3.5 - NEW)

**Add new phase between Phase 3 and Phase 4**:

### Phase 3.5: Conflict Resolution & Human-in-the-Loop (Week 2)

#### Objective
Handle data conflicts gracefully with manual review queue instead of auto-excluding valid leads.

#### 3.5.1 Conflict Detection

**Modify** `ValidationService.corroboration_gate()`:

```python
def corroboration_gate(self, observations: list, field: str, min_sources: int = 2) -> Tuple[bool, str, Optional[str]]:
    """
    Returns: (passed, reason, conflict_action)
    conflict_action: None | 'REVIEW_REQUIRED' | 'AUTO_EXCLUDE'
    """
    field_obs = [o for o in observations if o.field == field]

    if len(field_obs) < min_sources:
        if len(field_obs) == 1:
            # Single source - mark for review, don't auto-exclude
            return False, f"Only 1 source for {field}", 'REVIEW_REQUIRED'
        return False, f"No sources for {field}", 'AUTO_EXCLUDE'

    # Group by normalized value
    value_groups = {}
    for obs in field_obs:
        norm_val = normalize_value(obs.value, field)
        if norm_val not in value_groups:
            value_groups[norm_val] = []
        value_groups[norm_val].append(obs)

    # Check for consensus
    for norm_val, obs_list in value_groups.items():
        if len(obs_list) >= min_sources:
            return True, f"{field} corroborated", None

    # 1-vs-1 conflict - needs human review
    if len(field_obs) == 2 and len(value_groups) == 2:
        # Persist exclusion with both conflicting observation IDs
        conflict_info = {
            'field': field,
            'values': list(value_groups.keys()),
            'observation_ids': [obs.id for obs in field_obs]
        }
        return False, f"{field} has 1-vs-1 conflict", 'REVIEW_REQUIRED'

    # Multiple conflicts - likely bad data
    return False, f"{field} has {len(value_groups)} conflicting values", 'AUTO_EXCLUDE'
```

#### 3.5.2 Manual Review Queue

**Create** `scripts/review_queue.py`:

```python
"""
CLI tool for reviewing conflicted leads.
"""

def show_conflicts():
    """Display leads with status=REVIEW_REQUIRED."""
    review_leads = db.execute(
        "SELECT * FROM businesses WHERE status = 'REVIEW_REQUIRED' ORDER BY created_at"
    ).fetchall()

    for idx, lead in enumerate(review_leads):
        print(f"\n{'='*80}")
        print(f"[{idx+1}/{len(review_leads)}] {lead['original_name']}")
        print(f"{'='*80}")

        # Show all observations
        obs = db.execute(
            "SELECT * FROM observations WHERE business_id = ? ORDER BY field, source_url",
            (lead['id'],)
        ).fetchall()

        grouped_obs = {}
        for o in obs:
            if o['field'] not in grouped_obs:
                grouped_obs[o['field']] = []
            grouped_obs[o['field']].append(o)

        for field, field_obs in grouped_obs.items():
            print(f"\n{field.upper()}:")
            for o in field_obs:
                print(f"  [{o['source_url']}] {o['value']}")

        # Prompt for action
        print("\nActions:")
        print("  q - Qualify (mark as QUALIFIED)")
        print("  x - Exclude (mark as EXCLUDED)")
        print("  e - Re-enrich (fetch data again)")
        print("  s - Skip to next")
        print("  quit - Exit")

        action = input("\nAction: ").strip().lower()

        if action == 'q':
            db.execute(
                "UPDATE businesses SET status = 'QUALIFIED', manual_override = TRUE, override_reason = ?, override_by = ? WHERE id = ?",
                (f"Manual review - qualified despite conflicts", "human_reviewer", lead['id'])
            )
            print("✓ Marked as QUALIFIED")
        elif action == 'x':
            db.execute(
                "UPDATE businesses SET status = 'EXCLUDED' WHERE id = ?",
                (lead['id'],)
            )
            # Create exclusion record
            db.execute(
                "INSERT INTO exclusions (business_id, rule_id, reason) VALUES (?, ?, ?)",
                (lead['id'], 'manual_review', 'Manually excluded after conflict review')
            )
            print("✗ Marked as EXCLUDED")
        elif action == 'e':
            # Reset to DISCOVERED to trigger re-enrichment
            db.execute(
                "UPDATE businesses SET status = 'DISCOVERED' WHERE id = ?",
                (lead['id'],)
            )
            print("↻ Queued for re-enrichment")
        elif action == 'quit':
            break

        db.commit()

if __name__ == '__main__':
    show_conflicts()
```

---

## 5. REVENUE GATE STRICT POLICY (Phase 5.3 Update)

**DECISION REQUIRED**: Replace permissive logic with strict policy.

**Replace** `revenue_gate()` implementation:

```python
def revenue_gate(self, business: dict) -> Tuple[bool, str]:
    """
    STRICT POLICY (for M&A acquisition use case):
    Require confidence >= 0.6 AND (staff signal OR category benchmark).
    No warnings, no permissive passes.
    """
    revenue = business.get('revenue_estimate', {})

    if not revenue or not revenue.get('revenue_min'):
        return False, "No revenue estimate"

    # Check confidence threshold
    confidence = revenue.get('confidence', 0)
    if confidence < 0.6:
        return False, f"Revenue confidence too low ({confidence:.2f} < 0.6)"

    # Require underlying signals
    has_staff = business.get('staff_count') is not None
    has_benchmark = business.get('category') in INDUSTRY_BENCHMARKS

    if not (has_staff or has_benchmark):
        return False, "No staff signal or category benchmark to support revenue estimate"

    return True, f"Revenue estimate acceptable (confidence {confidence:.2f}, methodology: {revenue.get('methodology')})"
```

**Update** export config:

```python
DEFAULT_EXPORT_CONFIG = {
    'TARGET_WHITELIST': TARGET_WHITELIST,
    'MAX_RADIUS_KM': 20,
    'MIN_WEBSITE_AGE_YEARS': 3,
    'MIN_CORROBORATION_SOURCES': 2,
    'MIN_REVENUE_CONFIDENCE': 0.6,  # STRICT: no exceptions
    'REQUIRE_STAFF_OR_BENCHMARK': True  # NEW: enforce signals
}
```

---

## 6. RETRY/BACKOFF/CIRCUIT BREAKER (Phase 2-6 Enhancement)

**PRIORITY: P1 - Add to all network calls in Week 2**

**Create** `src/core/resilience.py`:

```python
"""
Network resilience patterns: retry, backoff, circuit breaker.
"""

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiohttp
from collections import defaultdict
from datetime import datetime, timedelta

class CircuitBreaker:
    """Simple circuit breaker for API calls."""

    def __init__(self, failure_threshold=3, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.failures = defaultdict(int)
        self.opened_at = {}

    def is_open(self, service: str) -> bool:
        """Check if circuit is open (service unavailable)."""
        if service not in self.opened_at:
            return False

        # Check if recovery timeout passed
        if datetime.now() > self.opened_at[service] + timedelta(seconds=self.recovery_timeout):
            # Try half-open state
            self.failures[service] = 0
            del self.opened_at[service]
            return False

        return True

    def record_success(self, service: str):
        """Record successful call."""
        self.failures[service] = 0
        if service in self.opened_at:
            del self.opened_at[service]

    def record_failure(self, service: str):
        """Record failed call."""
        self.failures[service] += 1

        if self.failures[service] >= self.failure_threshold:
            self.opened_at[service] = datetime.now()
            logger.warning(f"Circuit breaker opened for {service} after {self.failures[service]} failures")

# Global circuit breaker instance
circuit_breaker = CircuitBreaker()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError))
)
async def call_with_retry(func, *args, service_name='unknown', **kwargs):
    """
    Wrap async function with retry logic and circuit breaker.

    Usage:
        result = await call_with_retry(
            places.get_google_data,
            business_name, address,
            service_name='google_places'
        )
    """
    if circuit_breaker.is_open(service_name):
        raise Exception(f"Circuit breaker open for {service_name}")

    try:
        result = await func(*args, **kwargs)
        circuit_breaker.record_success(service_name)
        return result
    except Exception as e:
        circuit_breaker.record_failure(service_name)
        raise
```

**Apply to all network calls**:

```python
# Example: in enrichment flow
async def enrich_business(business_id: int):
    business = db.get_business(business_id)

    # With retry + circuit breaker
    try:
        google_data = await call_with_retry(
            places.get_google_data,
            business.name, business.address,
            service_name='google_places'
        )
    except Exception as e:
        logger.error(f"Failed to enrich from Google Places: {e}")
        # Create observation with error
        create_observation(db, Observation(
            business_id=business_id,
            source_url='https://maps.google.com',
            field='_error',
            value=None,
            error=str(e),
            http_status=0
        ))
```

---

## 7. HTTP CACHING & COST CONTROLS (Phase 2-6 Enhancement)

**PRIORITY: P1 - Add in Week 2**

**Create** `src/core/http_cache.py`:

```python
"""
HTTP caching with 30-day TTL for API responses.
"""

import aiohttp
from aiohttp_client_cache import CachedSession, SQLiteBackend
from datetime import timedelta

# Create cached session with SQLite backend
cache_backend = SQLiteBackend(
    cache_name='data/http_cache.db',
    expire_after=timedelta(days=30),
    allowed_methods=['GET', 'POST']
)

cached_session = CachedSession(cache=cache_backend)

async def get_cached(url: str, **kwargs):
    """Make HTTP GET with caching."""
    async with cached_session.get(url, **kwargs) as response:
        return await response.json()
```

**Add rate limiting**:

```python
"""
Token bucket rate limiter.
"""

import asyncio
from collections import defaultdict

class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int, per: float):
        """
        Args:
            rate: Number of calls allowed
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.allowance = defaultdict(lambda: rate)
        self.last_check = defaultdict(lambda: asyncio.get_event_loop().time())

    async def acquire(self, key: str = 'default'):
        """Acquire permission to make a call."""
        current = asyncio.get_event_loop().time()
        time_passed = current - self.last_check[key]
        self.last_check[key] = current

        self.allowance[key] += time_passed * (self.rate / self.per)
        if self.allowance[key] > self.rate:
            self.allowance[key] = self.rate

        if self.allowance[key] < 1.0:
            sleep_time = (1.0 - self.allowance[key]) * (self.per / self.rate)
            await asyncio.sleep(sleep_time)
            self.allowance[key] = 0.0
        else:
            self.allowance[key] -= 1.0

# Global rate limiters
google_places_limiter = RateLimiter(rate=100, per=86400)  # 100/day
yelp_limiter = RateLimiter(rate=5000, per=86400)  # 5000/day (free tier)
```

**Cost tracking**:

```python
# Add to orchestrator metrics
class OrchestrationMetrics:
    def __init__(self):
        # ... existing fields
        self.api_calls = defaultdict(int)
        self.api_costs = defaultdict(float)

    def log_api_call(self, service: str, cost: float = 0.0):
        self.api_calls[service] += 1
        self.api_costs[service] += cost

    def print_summary(self):
        print(f"""
        Pipeline Summary:
        ...

        API Usage:
        {dict(self.api_calls)}

        Estimated Costs:
        {dict(self.api_costs)}
        """)
```

---

## 8. LLM EXTRACTION GUARDRAILS (Phase 6.3 Enhancement)

**Add to** `llm_service.py`:

```python
async def extract_structured(self, url: str, content: str, schema: type[BaseModel], business_id: int) -> Optional[BaseModel]:
    """Enhanced with token limits, cost tracking, null-rate monitoring."""

    prompt = build_extraction_prompt(url, content, schema.__name__)

    try:
        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1000,  # Cap output
            metadata={'business_id': business_id, 'purpose': 'extraction'}
        )

        # Track costs
        tokens_used = response.usage.total_tokens
        cost = (tokens_used / 1000) * 0.03  # $0.03 per 1K tokens
        metrics.log_api_call('openai_gpt4', cost)

        data = json.loads(response.choices[0].message.content)
        validated = schema(**data)

        # Track null rate
        null_count = sum(1 for v in validated.dict(exclude_none=False).values() if v is None)
        null_rate = null_count / len(validated.dict())

        if null_rate > 0.7:
            logger.warning(f"LLM extraction high null rate ({null_rate:.1%}) for {url}")
            # Alert if sustained
            if self.null_rate_tracker.add(null_rate) > 0.7:
                alert("LLM extraction returning >70% nulls - check prompt regression")

        # Create observations
        for field, value in validated.dict(exclude_none=True).items():
            if field != 'source_url':
                create_observation(db, Observation(
                    business_id=business_id,
                    source_url=validated.source_url,
                    field=field,
                    value=str(value),
                    confidence=0.8
                ))

        return validated

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        return None
```

---

## 9. FULL PIPELINE END-TO-END TESTS (Phase 8 Enhancement)

**Add to** `tests/test_pipeline_e2e.py`:

```python
"""
End-to-end pipeline tests with full export validation.
PRIORITY: P2 - Add in Week 4
"""

import pytest
from src.agents.orchestrator import LeadOrchestrator

# Full golden test cases with ALL fields
GOLDEN_FULL_PIPELINE = [
    {
        'name': 'Valid Manufacturing Co',
        'street': '123 Industrial Dr',
        'city': 'Hamilton',
        'postal_code': 'L8H 3R2',
        'phone': '905-555-1234',
        'website': 'https://validmfg.com',
        'place_types': ['manufacturing', 'industrial_equipment'],
        'latitude': 43.2557,
        'longitude': -79.9537,
        'observations': {
            'phone': [
                {'source': 'website', 'value': '905-555-1234'},
                {'source': 'yelp', 'value': '(905) 555-1234'},
            ],
            'address': [
                {'source': 'website', 'value': '123 Industrial Dr, Hamilton ON'},
                {'source': 'google', 'value': '123 Industrial Drive, Hamilton, ON'},
            ]
        },
        'website_age_years': 5,
        'staff_count': 12,
        'revenue_confidence': 0.65,
        'expected_exportable': True
    },
    {
        'name': 'Borderline Sign Shop',
        'place_types': ['sign_shop'],
        'website_age_years': 2.5,  # Below 3-year threshold
        'revenue_confidence': 0.7,
        'expected_exportable': False,
        'expected_block_reason': 'Website too new'
    }
]

@pytest.mark.asyncio
@pytest.mark.parametrize("case", GOLDEN_FULL_PIPELINE)
async def test_full_pipeline_e2e(case):
    """Test complete pipeline from discovery to export."""

    orchestrator = LeadOrchestrator()

    # 1. Insert business
    business_id = orchestrator.discover_one(case)

    # 2. Enrich (mock observations)
    for field, obs_list in case.get('observations', {}).items():
        for obs in obs_list:
            create_observation(db, Observation(
                business_id=business_id,
                source_url=obs['source'],
                field=field,
                value=obs['value']
            ))

    # 3. Validate
    await orchestrator.validate(business_id)

    # 4. Check exportability
    business = db.get_business(business_id)
    validations = db.get_validations(business_id)

    can_export, reason = is_exportable(business, validations, DEFAULT_EXPORT_CONFIG)

    assert can_export == case['expected_exportable'], \
        f"Expected exportable={case['expected_exportable']}, got {can_export}: {reason}"

    if not can_export and 'expected_block_reason' in case:
        assert case['expected_block_reason'].lower() in reason.lower()
```

---

## 10. UPDATED ROLLOUT PLAN

### Week 1 (REVISED - Critical Foundation)
- [ ] **P0: Implement database schema** (businesses, observations, validations with new fields)
- [ ] **P0: Create `normalization.py`** with fingerprinting + idempotent upsert
- [ ] **P0: Build Places type mapping tables** (scrape 100 samples, create mappings)
- [ ] **P0: Implement LLM extraction + anti-hallucination tests** (move from Week 3)
- [ ] **P0: Create `evidence.py`, `rules.py`, `validation_service.py`**
- [ ] **P0: Write category gate + golden failure tests**
- [ ] **P1: Add REVIEW_REQUIRED status** + conflict detection logic

### Week 2 (Validation + Resilience)
- [ ] **P1: Add retry/backoff/circuit breaker** to all network calls
- [ ] **P1: Implement HTTP caching** (30-day TTL) + rate limiters
- [ ] **P1: Implement website_gate** (HTTP 200, parked detection, Wayback age)
- [ ] **P1: Implement corroboration gate** with conflict resolution
- [ ] **P1: Add geocoding service + geo gate**
- [ ] **P1: Create manual review queue** (`scripts/review_queue.py`)
- [ ] **P2: Test discovery → geocode → enrich → validate flow** on 100 leads

### Week 3 (Revenue + LLM Hardening)
- [ ] **P1: Create benchmarks.py** with industry data (incl. source + date)
- [ ] **P1: Implement strict revenue gate** (confidence ≥ 0.6 + signal required)
- [ ] **P2: Add company size service** (skip LinkedIn scraping, use Clearbit/ZoomInfo API)
- [ ] **P2: Add LLM guardrails** (token limits, cost tracking, null-rate monitoring)
- [ ] **P3: Test LLM extraction** on 20 real websites

### Week 4 (Export Gate + Testing)
- [ ] **P1: Implement `is_exportable()` policy** with strict checks
- [ ] **P1: Update export script** with blocked report
- [ ] **P1: Add validation_version tracking** + bump on rule changes
- [ ] **P2: Write full pipeline end-to-end tests** (10 golden cases)
- [ ] **P2: Run regression tests** on 500-lead batch
- [ ] **P2: Generate validation report** with per-rule precision/recall

### Week 5 (Incremental Validation + Reporting)
- [ ] **P1: Run 100-lead test** with category+geo gates only → analyze exclusion breakdown
- [ ] **P2: Update CLI scripts** (`generate`, `quickstart`, `validate`, `report`)
- [ ] **P2: Rewrite orchestrator** with new flow + metrics
- [ ] **P2: Add observability** (per-rule trends, top failing patterns)
- [ ] **P3: Documentation updates**

### Week 6-7 (Production Hardening + Buffer)
- [ ] **P2: Add integration tests** for Places/Yelp API contracts (run weekly)
- [ ] **P2: Add CI/CD** (ruff/black/mypy + pre-commit hooks)
- [ ] **P2: Performance tuning** (async optimizations, batch operations)
- [ ] **P3: Security audit** (no PII in observations, secrets in env)
- [ ] **P3: Production deployment**
- [ ] **P3: Monitoring & alerting**

---

## 11. UPDATED SUCCESS CRITERIA

### Acceptance Test 1: Zero Retail Leakage (Scaled)
```
GIVEN 500 discovered leads (not 100)
WHEN the pipeline runs
THEN zero leads with types in CATEGORY_BLACKLIST should reach QUALIFIED status
AND export report shows retail exclusion rate > 80%
```

### Acceptance Test 6: Corroboration with Review Queue (NEW)
```
GIVEN a lead with 1-vs-1 postal conflict (source A: L4P, source B: L8P)
WHEN corroboration gate runs
THEN the lead should have status='REVIEW_REQUIRED'
AND manual review queue should show both conflicting values with source URLs
```

### Acceptance Test 7: Only Export Corroborated Leads (NEW)
```
GIVEN 100 QUALIFIED leads where 20 have corroboration_score < 2
WHEN export runs
THEN only 80 leads should be exported
AND blocked report shows "Insufficient corroboration" for 20 leads
```

### Acceptance Test 8: API Cost Control (NEW)
```
GIVEN a 100-lead pipeline run
WHEN enrichment completes
THEN total API costs should be < $10
AND cached responses should be used for duplicate lookups
```

---

## 12. UPDATED FILE STRUCTURE

```
src/
├── core/
│   ├── evidence.py          # Observation, Validation models
│   ├── rules.py             # Whitelists, blacklists
│   ├── normalization.py     # NEW: Fingerprinting, entity resolution
│   ├── resilience.py        # NEW: Retry, circuit breaker
│   ├── http_cache.py        # NEW: HTTP caching + rate limiting
│   ├── benchmarks.py        # Industry benchmarks
│   └── export_policy.py     # is_exportable logic
├── models/
│   ├── lead.py              # MODIFIED: Add fingerprint, status enum
│   └── extraction_schemas.py # Pydantic schemas for LLM
├── services/
│   ├── validation_service.py # All validation gates
│   ├── geocoding_service.py  # Geocoding + distance calc
│   ├── company_size_service.py # Staff estimation (Clearbit API, not LinkedIn scraping)
│   └── llm_service.py        # MODIFIED: Guardrails, cost tracking
├── sources/
│   ├── places.py            # Google/Yelp/OSM integration
│   └── type_mappings.py     # NEW: Canonical type mappings
├── prompts/
│   └── extraction_prompts.py # LLM prompt templates
└── agents/
    └── orchestrator.py      # REWRITTEN: New flow + metrics

tests/
├── test_validation_gates.py # Golden test cases
├── test_corroboration.py    # Corroboration tests
├── test_llm_extraction.py   # No-guess policy tests
├── test_normalization.py    # NEW: Entity resolution tests
├── test_pipeline_e2e.py     # NEW: Full pipeline end-to-end tests
└── integration/
    └── test_api_contracts.py # NEW: Places/Yelp contract tests (weekly)

scripts/
├── discover_leads.py        # MODIFIED: Use fingerprinting
├── build_type_mappings.py   # NEW: Scrape samples, build mappings
├── review_queue.py          # NEW: Manual conflict resolution
├── validate_leads.py        # Run validation gates
├── validation_report.py     # MODIFIED: Add precision/recall per rule
└── export_leads.py          # MODIFIED: Use export gate

migrations/
├── 001_add_evidence_tables.sql
└── 002_add_fingerprint_and_review.sql  # NEW: Fingerprint + REVIEW_REQUIRED status
```

---

## 13. CONFIGURATION UPDATES

**Add to** `config.py`:

```python
# Cost Controls
API_COST_LIMITS = {
    'google_places_daily_budget': 5.00,  # USD
    'openai_daily_budget': 10.00,
}

# Resilience
CIRCUIT_BREAKER_CONFIG = {
    'failure_threshold': 3,
    'recovery_timeout': 300,  # seconds
}

RATE_LIMITS = {
    'google_places': {'rate': 100, 'per': 86400},  # 100/day
    'yelp': {'rate': 5000, 'per': 86400},
}

# HITL Review
REVIEW_CATEGORIES = {
    'funeral_home': 'REVIEW_REQUIRED',  # Never auto-export
    'franchise_office': 'REVIEW_REQUIRED',
}

# Validation Version (bump on every rule change)
CURRENT_VALIDATION_VERSION = 1
```

---

## 14. PRIORITY PUNCH-LIST

**Must complete before coding Phase 2:**

1. ✅ **Fingerprinting + idempotent upsert** (`normalization.py`) - 2 days
2. ✅ **Build Places type mapping tables** (scrape 100 samples) - 3 days
3. ✅ **Add REVIEW_REQUIRED status** + manual review queue - 2 days
4. ✅ **Pick strict revenue policy** (Option A: confidence ≥ 0.6 + signal) - 1 hour
5. ✅ **Implement LLM extraction** in Week 1 (not Week 3) - 2 days

**Must complete before coding Phase 3:**

6. ✅ **Add retry/backoff to all network calls** - 1 day
7. ✅ **Add HTTP caching** (30-day TTL) - 1 day
8. ✅ **Implement website_gate** (HTTP 200, Wayback age) - 2 days

**Must complete before export:**

9. ✅ **Add validation_version tracking** - 0.5 day
10. ✅ **Expand golden tests to full export pipeline** - 2 days
11. ✅ **Add per-rule precision/recall to reports** - 1 day

**Total additional effort: +18 days → Revised timeline: 6-7 weeks**

---

## IMPLEMENTATION NOTES

1. **Entity Resolution**: Test fingerprinting on 20 known duplicates before committing schema
2. **Type Mappings**: Start with 50 samples, iterate if coverage < 80%
3. **Review Queue**: Build CLI first (1 day), web UI later if needed
4. **Revenue Gate**: Document decision in README: "Strict policy for M&A acquisition use case"
5. **LLM Testing**: Run extraction on 20 websites Week 1, not Week 3, to validate anti-hallucination prompt
6. **Incremental Validation**: After Week 1, run category gate alone on 100 leads to validate filtering before building other gates

---

## END OF UPDATES DOCUMENT

Apply these changes systematically to IMPLEMENTATION_PLAN.md, replacing or enhancing existing sections as indicated.
