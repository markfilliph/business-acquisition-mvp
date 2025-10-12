# Lead Generation System: Comprehensive Implementation Plan (REVISED)

## Executive Summary

This document outlines a systematic fix for the lead generation pipeline, addressing core issues of data hallucination, weak validation, and insufficient evidence tracking. The diagnosis revealed that despite a "production-ready" architecture, the system is outputting unqualified leads (retail stores, gas stations, auto dealerships) that fail basic category and geography filters.

**Core Problem**: Discovery → Enrichment happens before persistence, hiding failure modes and allowing silent fall-through to exports without evidence or validation gates.

**Revision Note**: This plan has been updated to address production-grade requirements including entity resolution, conflict resolution workflows, retry/backoff patterns, cost controls, human-in-the-loop review, and comprehensive testing of full pipeline end-to-end.

---

## Phase 1: Data Model & Evidence Architecture (Week 1)

### Objective
Establish a single source of truth where EVERY lead is persisted with full evidence trail.

### 1.1 Database Schema Refactoring

**Create normalized tables** (SQLite):

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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_businesses_status ON businesses(status);
CREATE INDEX idx_businesses_fingerprint ON businesses(fingerprint);

-- Evidence ledger (one row per source check)
CREATE TABLE observations (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    field TEXT NOT NULL,           -- e.g., 'phone', 'category', 'revenue'
    value TEXT,
    confidence REAL DEFAULT 1.0,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When source was queried
    http_status INTEGER,           -- HTTP response code
    api_version TEXT,              -- API version used
    error TEXT,                    -- Error message if query failed
    FOREIGN KEY(business_id) REFERENCES businesses(id)
);

CREATE INDEX idx_observations_business_field ON observations(business_id, field);

-- Validation gates results
CREATE TABLE validations (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,         -- e.g., 'category_whitelist', 'geo_radius'
    passed BOOLEAN NOT NULL,
    reason TEXT,
    evidence_ids TEXT,              -- JSON array of observation.id
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(business_id) REFERENCES businesses(id)
);

-- Exclusion reasons (audit trail)
CREATE TABLE exclusions (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_ids TEXT,              -- JSON array of observation.id
    excluded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(business_id) REFERENCES businesses(id)
);

-- Export snapshots
CREATE TABLE exports (
    id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL,
    validation_version INTEGER NOT NULL,
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    export_file TEXT,
    FOREIGN KEY(business_id) REFERENCES businesses(id)
);
```

### 1.2 Pipeline Flow Change

**OLD FLOW** (broken):
```
Discovery → Enrich → Filter → Persist (only keepers) → Export
```

**NEW FLOW** (evidence-based):
```
Discovery → Persist(raw, status=NEW)
          → Enrich(extract only, create observations)
          → Validate(run gates, create validations)
          → Score
          → Qualify/Exclude(update status, create exclusions if failed)
          → Export(only if is_exportable())
```

### 1.3 Code Changes

**Create** `src/core/evidence.py`:
```python
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

@dataclass
class Observation:
    business_id: int
    source_url: str
    field: str
    value: Optional[str]
    confidence: float = 1.0
    observed_at: datetime = None

@dataclass
class Validation:
    business_id: int
    rule_id: str
    passed: bool
    reason: str
    evidence_ids: List[int]
    validated_at: datetime = None

def create_observation(db, obs: Observation) -> int:
    """Insert observation and return ID."""
    pass

def create_validation(db, val: Validation) -> int:
    """Insert validation and return ID."""
    pass
```

**Modify** `src/models/lead.py`:
- Add `status` field (enum: NEW, ENRICHING, QUALIFIED, EXCLUDED, EXPORTED)
- Add `latitude`, `longitude`, `distance_km` fields
- Add `evidence` relationship to observations

---

## Phase 2: Deterministic Category Gating (Week 1-2)

### Objective
Eliminate category hallucinations by implementing two-layer deterministic filtering BEFORE any LLM enrichment.

### 2.1 Define Whitelists & Blacklists

**Create** `src/core/rules.py`:

```python
# Positive whitelist (allowed business types)
TARGET_WHITELIST = {
    # Manufacturing & Industrial
    'manufacturing', 'printing', 'sign_shop', 'industrial_equipment',
    'equipment_rental', 'wholesale_distribution', 'fabrication',

    # Professional Services (B2B)
    'engineering_consulting', 'environmental_consulting',
    'geotechnical_services', 'commercial_services', 'business_consulting',
    'logistics', 'warehousing', 'packaging_services',

    # Specialized services
    'commercial_printing', 'industrial_design', 'trade_services_commercial'
}

# Negative blacklist (explicitly excluded)
CATEGORY_BLACKLIST = {
    # Retail
    'convenience_store', 'gas_station', 'mattress_store', 'furniture_store',
    'car_dealer', 'auto_dealership', 'retail_general', 'boutique', 'outlet',
    'variety_store', 'dollar_store', 'vape_shop', 'liquor_store', 'cannabis',

    # Personal services
    'barber', 'salon', 'nail_salon', 'spa', 'massage', 'tattoo', 'piercing',

    # Food & hospitality
    'restaurant', 'cafe', 'bar', 'food_truck', 'catering_retail',

    # Financial services (franchises)
    'bank_branch', 'insurance_agent', 'financial_advisor_franchise',

    # Skilled trades (per README exclusion)
    'welding', 'hvac', 'roofing', 'plumbing', 'electrical', 'construction',
    'machining', 'carpentry', 'painting_residential',

    # Other excluded
    'funeral_home', 'pawn_shop', 'payday_loans', 'auto_repair', 'towing'
}

# Name pattern blacklist (regex)
NAME_BLACKLIST_PATTERNS = [
    r'variety|mart|mattress|hyundai|toyota|honda|ford|chevrolet',
    r'nails?|salon|barber|spa|beauty',
    r'gas|petro|shell|esso|convenience',
    r'tobacco|vape|cannabis|liquor',
    r'pawn|payday|outlet',
    r'restaurant|cafe|bistro|grill|pizza',
    r'funeral|memorial',
    r'edward\s+jones|state\s+farm|allstate'  # franchise financial
]
```

### 2.2 Implement Category Gate

**Create** `src/services/validation_service.py`:

```python
import re
from typing import Tuple, Optional
from src.core.rules import CATEGORY_BLACKLIST, TARGET_WHITELIST, NAME_BLACKLIST_PATTERNS

class ValidationService:

    def category_gate(self, business: dict, place_types: list) -> Tuple[bool, str]:
        """
        Returns (passed, reason).
        Checks:
        1. Name pattern blacklist
        2. Place type blacklist
        3. Place type whitelist
        """
        name = business.get('name', '').lower()

        # Check 1: Name patterns
        for pattern in NAME_BLACKLIST_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                return False, f"Name matches blacklist pattern: {pattern}"

        # Check 2: Place types against blacklist
        for ptype in place_types:
            if ptype in CATEGORY_BLACKLIST:
                return False, f"Category blacklisted: {ptype}"

        # Check 3: Must have at least one whitelisted type
        if not any(ptype in TARGET_WHITELIST for ptype in place_types):
            return False, f"No whitelisted category found in: {place_types}"

        return True, "Category validated"

    def geo_gate(self, business: dict, centroid_lat: float, centroid_lng: float, max_radius_km: float) -> Tuple[bool, str]:
        """Validate geographic constraints."""
        pass

    def website_gate(self, url: str, min_age_years: int = 3) -> Tuple[bool, str]:
        """Validate website exists, is not parked, has age signal."""
        pass

    def corroboration_gate(self, observations: list, field: str, min_sources: int = 2) -> Tuple[bool, str]:
        """Validate field has N independent sources."""
        pass

    def revenue_gate(self, business: dict) -> Tuple[bool, str]:
        """Validate revenue estimate has confidence + benchmark."""
        pass
```

### 2.3 Integrate External Places APIs

**Create** `src/sources/places.py`:

```python
import aiohttp
from typing import List, Optional

class PlacesService:
    """Multi-source place type lookup."""

    async def get_google_place_types(self, name: str, address: str) -> List[str]:
        """Query Google Places API for business types."""
        pass

    async def get_yelp_categories(self, name: str, address: str) -> List[str]:
        """Query Yelp API for categories."""
        pass

    async def get_osm_tags(self, name: str, address: str) -> List[str]:
        """Query OpenStreetMap for tags."""
        pass

    async def get_merged_types(self, name: str, address: str) -> List[str]:
        """
        Query all sources, normalize, merge.
        Returns union of all types found.
        """
        pass
```

---

## Phase 3: Multi-Source Corroboration (Week 2)

### Objective
Require 2-of-N source agreement for critical fields (address, phone, postal, category) to eliminate fabrication.

### 3.1 Corroboration Policy

| Field | Min Sources | Allowed Sources | Failure Action |
|-------|-------------|-----------------|----------------|
| `address` | 2 | Website, Yelp, MapQuest, Google Places, BBB | Block export |
| `phone` | 2 | Website, Yelp, Google Places, BBB | Block export |
| `postal_code` | 2 | Website, Canada Post lookup, Yelp, BBB | Block export |
| `category` | 1 (authoritative) + 1 (content) | Google Places + website keywords | Block export |
| `website` | 1 (must resolve HTTP 200) | Direct check + Wayback age | Block export |
| `founding_year` | 1 (optional) | Website About page, BBB, LinkedIn | Leave null if missing |
| `staff_count` | 1 (optional) | LinkedIn, Facebook, website Careers page | Leave null if missing |

### 3.2 Implementation

**Modify** `ValidationService.corroboration_gate()`:

```python
def corroboration_gate(self, observations: list, field: str, min_sources: int = 2) -> Tuple[bool, str]:
    """
    Check if field has min_sources independent observations with matching values.

    Returns:
        (True, reason) if field corroborated
        (False, reason) if field conflicts or insufficient sources
    """
    field_obs = [o for o in observations if o.field == field]

    if len(field_obs) < min_sources:
        return False, f"Insufficient sources for {field}: {len(field_obs)} < {min_sources}"

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
            return True, f"{field} corroborated by {len(obs_list)} sources: {norm_val}"

    return False, f"{field} has conflicting values: {list(value_groups.keys())}"

def normalize_value(value: str, field: str) -> str:
    """Normalize values for comparison (e.g., phone formatting, postal uppercase)."""
    if field == 'phone':
        return re.sub(r'\D', '', value)  # digits only
    elif field == 'postal_code':
        return value.upper().replace(' ', '')
    elif field == 'address':
        return value.lower().strip().replace('.', '')
    return value.strip()
```

### 3.3 Data Collection Changes

**Modify enrichment flow** to always create observations:

```python
async def enrich_business(business_id: int):
    """
    Enrich a business by querying multiple sources.
    Create observation records for EVERY field from EVERY source.
    """
    business = db.get_business(business_id)

    # Update status
    db.update_business(business_id, status='ENRICHING')

    # Query sources
    google_data = await places.get_google_data(business.name, business.address)
    yelp_data = await yelp.get_data(business.name, business.address)
    website_data = await scrape_website(business.website) if business.website else None

    # Create observations for each source
    if google_data:
        create_observation(db, Observation(
            business_id=business_id,
            source_url='https://maps.google.com',
            field='phone',
            value=google_data.get('phone'),
            confidence=1.0
        ))
        create_observation(db, Observation(
            business_id=business_id,
            source_url='https://maps.google.com',
            field='address',
            value=google_data.get('address'),
            confidence=1.0
        ))
        # ... more fields

    # Similar for yelp_data, website_data, etc.

    return business_id
```

---

## Phase 4: Geographic Validation (Week 2)

### Objective
Enforce hard geographic boundaries using coordinates and distance calculations.

### 4.1 Geocoding Integration

**Add to** `src/services/geocoding_service.py`:

```python
import aiohttp
from typing import Optional, Tuple

class GeocodingService:
    """Geocode addresses and calculate distances."""

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """
        Geocode address to (lat, lng).
        Uses Nominatim (OSM) or Google Geocoding API.
        """
        pass

    def distance_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate haversine distance in km."""
        from math import radians, sin, cos, sqrt, atan2

        R = 6371.0  # Earth radius in km

        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c
```

### 4.2 Geo Gate Implementation

**Add to** `ValidationService`:

```python
def geo_gate(self, business: dict, centroid_lat: float, centroid_lng: float, max_radius_km: float) -> Tuple[bool, str]:
    """
    Validate business is within geographic radius.

    Config (Hamilton/Ancaster target):
        centroid_lat = 43.2557  # Ancaster, ON
        centroid_lng = -79.9537
        max_radius_km = 20
    """
    if not business.get('latitude') or not business.get('longitude'):
        return False, "Business not geocoded"

    dist = self.geocoding.distance_km(
        centroid_lat, centroid_lng,
        business['latitude'], business['longitude']
    )

    business['distance_km'] = dist  # Store for later use

    if dist > max_radius_km:
        return False, f"Outside target radius: {dist:.1f}km > {max_radius_km}km"

    return True, f"Within target radius: {dist:.1f}km"
```

### 4.3 Pipeline Integration

**Modify orchestrator** to geocode immediately after discovery:

```python
async def process_discovered_lead(lead_data: dict):
    # 1. Persist raw
    business_id = db.insert_business(lead_data, status='NEW')

    # 2. Geocode
    lat, lng = await geocoding.geocode(lead_data['address'])
    if lat and lng:
        db.update_business(business_id, latitude=lat, longitude=lng)

    # 3. Continue enrichment...
```

---

## Phase 5: Revenue & Staff Estimation (Week 3)

### Objective
Replace single-point "guesses" with ranges + confidence scores grounded in benchmarks.

### 5.1 Data Collection

**Create** `src/services/company_size_service.py`:

```python
class CompanySizeService:
    """Estimate company size from multiple signals."""

    async def get_linkedin_size(self, company_name: str) -> Optional[str]:
        """Query LinkedIn for employee count band (1-10, 11-50, etc.)."""
        pass

    async def get_facebook_team_size(self, company_name: str) -> Optional[int]:
        """Check Facebook page for team photos, About section."""
        pass

    async def scrape_careers_page(self, url: str) -> Optional[int]:
        """Parse Careers/Jobs page for open positions (proxy for size)."""
        pass

    async def parse_about_page(self, url: str) -> Optional[dict]:
        """
        Extract signals from About page:
        - Team size mentions
        - Founding year
        - Location count
        """
        pass
```

### 5.2 Benchmark Integration

**Create** `src/core/benchmarks.py`:

```python
# Ontario/Canada industry benchmarks (from StatsCan, industry reports)
INDUSTRY_BENCHMARKS = {
    'printing': {
        'staff_p50': 8,
        'staff_p75': 15,
        'revenue_per_employee': 120000,  # CAD
        'sde_margin': 0.15
    },
    'manufacturing': {
        'staff_p50': 12,
        'staff_p75': 25,
        'revenue_per_employee': 150000,
        'sde_margin': 0.12
    },
    'engineering_consulting': {
        'staff_p50': 6,
        'staff_p75': 12,
        'revenue_per_employee': 180000,
        'sde_margin': 0.20
    },
    # ... more categories
}

def estimate_revenue_range(category: str, staff_count: Optional[int], confidence: float) -> dict:
    """
    Returns revenue range with confidence.

    Example output:
    {
        'revenue_min': 960000,
        'revenue_max': 1800000,
        'confidence': 0.6,
        'methodology': 'staff_count * benchmark_revenue_per_employee'
    }
    """
    if category not in INDUSTRY_BENCHMARKS:
        return {'revenue_min': None, 'revenue_max': None, 'confidence': 0.0, 'methodology': 'no_benchmark'}

    benchmark = INDUSTRY_BENCHMARKS[category]

    if staff_count:
        # Use actual staff count
        revenue_mid = staff_count * benchmark['revenue_per_employee']
        revenue_min = revenue_mid * 0.8
        revenue_max = revenue_mid * 1.2
        conf = confidence  # Inherit from staff count confidence
    else:
        # Use P50/P75 estimates
        staff_p50 = benchmark['staff_p50']
        staff_p75 = benchmark['staff_p75']
        revenue_min = staff_p50 * benchmark['revenue_per_employee']
        revenue_max = staff_p75 * benchmark['revenue_per_employee']
        conf = 0.3  # Low confidence without actual staff count

    return {
        'revenue_min': int(revenue_min),
        'revenue_max': int(revenue_max),
        'confidence': conf,
        'methodology': 'staff_based' if staff_count else 'industry_benchmark'
    }
```

### 5.3 Revenue Gate

**Add to** `ValidationService`:

```python
def revenue_gate(self, business: dict) -> Tuple[bool, str]:
    """
    Require:
    1. Either staff signal OR category benchmark
    2. Confidence >= 0.6 OR explicit user override
    """
    revenue = business.get('revenue_estimate', {})

    if not revenue or not revenue.get('revenue_min'):
        return False, "No revenue estimate"

    if revenue.get('confidence', 0) < 0.6:
        if business.get('staff_count') or business.get('category_benchmark'):
            # Has signals but low confidence - allow with warning
            return True, f"Revenue estimate low confidence ({revenue['confidence']:.2f}) but has underlying signals"
        else:
            return False, f"Revenue confidence too low ({revenue['confidence']:.2f}) and no staff/benchmark data"

    return True, f"Revenue estimate acceptable (confidence {revenue['confidence']:.2f})"
```

---

## Phase 6: LLM Usage Hardening (Week 3)

### Objective
Restrict LLM to extraction-only with strict anti-hallucination prompts and citation requirements.

### 6.1 Extraction Schemas

**Create** `src/models/extraction_schemas.py`:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class CompanyExtraction(BaseModel):
    """Schema for extracting company info from website."""

    founding_year: Optional[int] = Field(None, description="Year company was founded, if explicitly stated")
    team_size_mentioned: Optional[int] = Field(None, description="Number of employees if mentioned")
    location_count: Optional[int] = Field(None, description="Number of locations/branches if mentioned")
    source_url: str = Field(..., description="URL where information was found")

    @validator('founding_year')
    def validate_year(cls, v):
        if v is not None and (v < 1900 or v > 2025):
            raise ValueError("Founding year out of reasonable range")
        return v

class ServiceExtraction(BaseModel):
    """Schema for extracting services offered."""

    services: list[str] = Field(default_factory=list, description="List of services explicitly mentioned")
    b2b_signals: list[str] = Field(default_factory=list, description="Phrases indicating B2B focus")
    source_url: str = Field(..., description="URL where information was found")
```

### 6.2 Anti-Hallucination Prompt Template

**Create** `src/prompts/extraction_prompts.py`:

```python
COMPANY_INFO_EXTRACTION = """
You are extracting structured company information from a website.

CRITICAL RULES:
1. ONLY extract information that is EXPLICITLY STATED on the page
2. If information is not present, return null for that field
3. NEVER infer, estimate, or guess
4. NEVER compute or derive values
5. You MUST provide the source_url where you found each piece of information

Website URL: {url}
Website Content: {content}

Extract the following fields according to the schema.
If a field is not explicitly present, return null.

Example of CORRECT behavior:
- Page says "Founded in 2005" → founding_year: 2005
- Page says "Our team of 12 engineers" → team_size_mentioned: 12
- Page does not mention founding year → founding_year: null

Example of INCORRECT behavior (DO NOT DO THIS):
- Page shows modern design → founding_year: 2015 ❌ (inference)
- Page shows 5 staff photos → team_size_mentioned: 5 ❌ (counting photos, not explicit statement)
- Page says nothing about team → team_size_mentioned: 8 ❌ (guess)

Return JSON matching the CompanyExtraction schema.
"""

def build_extraction_prompt(url: str, content: str, schema_name: str) -> str:
    """Build extraction prompt with anti-hallucination instructions."""
    pass
```

### 6.3 LLM Service Integration

**Modify** `src/services/llm_service.py`:

```python
from pydantic import ValidationError

class LLMService:

    async def extract_structured(self, url: str, content: str, schema: type[BaseModel]) -> Optional[BaseModel]:
        """
        Extract structured data using LLM with strict validation.

        Returns None if extraction fails or validation fails.
        """
        prompt = build_extraction_prompt(url, content, schema.__name__)

        response = await self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        try:
            data = json.loads(response.choices[0].message.content)
            validated = schema(**data)

            # Create observations for each non-null field
            for field, value in validated.dict(exclude_none=True).items():
                if field != 'source_url':
                    create_observation(db, Observation(
                        business_id=business_id,
                        source_url=validated.source_url,
                        field=field,
                        value=str(value),
                        confidence=0.8  # LLM extraction has inherent uncertainty
                    ))

            return validated

        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"LLM extraction failed validation: {e}")
            return None
```

---

## Phase 7: Export Gate & Exportability (Week 4)

### Objective
Implement a single function that determines if a record is eligible for export, preventing "oops" records from slipping out.

### 7.1 Exportability Logic

**Create** `src/core/export_policy.py`:

```python
from typing import Tuple

def is_exportable(business: dict, validations: list, config: dict) -> Tuple[bool, str]:
    """
    Determine if a business record is eligible for export.

    Requirements:
    1. Status = QUALIFIED
    2. All validation gates passed
    3. Category in whitelist
    4. Within geographic radius
    5. Website OK and aged >= 3 years
    6. Corroboration score >= 2 for critical fields
    7. Revenue estimate confidence >= 0.6

    Returns:
        (True, "") if exportable
        (False, reason) if not exportable
    """

    # Check 1: Status
    if business.get('status') != 'QUALIFIED':
        return False, f"Status is {business.get('status')}, not QUALIFIED"

    # Check 2: All gates passed
    failed_validations = [v for v in validations if not v['passed']]
    if failed_validations:
        reasons = [v['rule_id'] for v in failed_validations]
        return False, f"Failed validation gates: {', '.join(reasons)}"

    # Check 3: Category
    if business.get('category') not in config['TARGET_WHITELIST']:
        return False, f"Category {business.get('category')} not in whitelist"

    # Check 4: Geography
    if business.get('distance_km', 999) > config['MAX_RADIUS_KM']:
        return False, f"Distance {business.get('distance_km')}km exceeds {config['MAX_RADIUS_KM']}km"

    # Check 5: Website
    if not business.get('website_ok'):
        return False, "Website not validated"
    if business.get('website_age_years', 0) < config['MIN_WEBSITE_AGE_YEARS']:
        return False, f"Website too new ({business.get('website_age_years')} years)"

    # Check 6: Corroboration
    if business.get('corroboration_score', 0) < config['MIN_CORROBORATION_SOURCES']:
        return False, f"Insufficient corroboration ({business.get('corroboration_score')} sources)"

    # Check 7: Revenue confidence
    revenue_conf = business.get('revenue_estimate', {}).get('confidence', 0)
    if revenue_conf < config['MIN_REVENUE_CONFIDENCE']:
        return False, f"Revenue confidence too low ({revenue_conf:.2f})"

    return True, ""

# Default config
DEFAULT_EXPORT_CONFIG = {
    'TARGET_WHITELIST': TARGET_WHITELIST,
    'MAX_RADIUS_KM': 20,
    'MIN_WEBSITE_AGE_YEARS': 3,
    'MIN_CORROBORATION_SOURCES': 2,
    'MIN_REVENUE_CONFIDENCE': 0.6
}
```

### 7.2 Export Script Update

**Modify** `scripts/export_leads.py`:

```python
from src.core.export_policy import is_exportable, DEFAULT_EXPORT_CONFIG

def export_qualified_leads(output_path: str):
    """
    Export only leads that pass is_exportable check.
    """
    # Get all QUALIFIED leads
    qualified = db.get_businesses(status='QUALIFIED')

    exportable = []
    blocked = []

    for business in qualified:
        validations = db.get_validations(business['id'])

        can_export, reason = is_exportable(business, validations, DEFAULT_EXPORT_CONFIG)

        if can_export:
            exportable.append(business)

            # Record export
            db.insert_export(Export(
                business_id=business['id'],
                validation_version=get_current_validation_version(),
                export_file=output_path
            ))
        else:
            blocked.append({
                'business': business,
                'reason': reason
            })
            logger.warning(f"Blocked export: {business['name']} - {reason}")

    # Write exportable to CSV
    write_csv(output_path, exportable)

    # Write blocked report
    write_blocked_report(f"{output_path}.blocked.json", blocked)

    logger.info(f"Exported {len(exportable)} leads, blocked {len(blocked)}")
```

---

## Phase 8: Testing & Quality Gates (Week 4)

### Objective
Lock in quality with regression tests for known failure cases.

### 8.1 Golden Test Cases

**Create** `tests/test_validation_gates.py`:

```python
import pytest
from src.services.validation_service import ValidationService

# Test data from diagnosis
GOLDEN_FAILURES = [
    {
        'name': 'Eastgate Variety',
        'address': '1505 Main St E, Hamilton',
        'place_types': ['convenience_store', 'variety_store'],
        'expected_gate': 'category',
        'expected_pass': False,
        'expected_reason_contains': 'blacklist'
    },
    {
        'name': 'Pioneer',
        'address': '603 King St E, Hamilton',
        'place_types': ['gas_station', 'convenience_store'],
        'expected_gate': 'category',
        'expected_pass': False,
        'expected_reason_contains': 'gas_station'
    },
    {
        'name': 'Performance Improvements',
        'place_types': ['auto_parts', 'retail'],
        'expected_gate': 'category',
        'expected_pass': False,
        'expected_reason_contains': 'retail'
    },
    {
        'name': 'Worldwide Mattress Outlet',
        'place_types': ['mattress_store', 'retail'],
        'expected_gate': 'category',
        'expected_pass': False,
        'expected_reason_contains': 'mattress'
    },
    {
        'name': 'Mountain Hyundai',
        'place_types': ['car_dealer'],
        'expected_gate': 'category',
        'expected_pass': False,
        'expected_reason_contains': 'dealer'
    }
]

GOLDEN_PASSES = [
    {
        'name': 'Landtek Limited',
        'address': '1234 Industrial Dr, Hamilton',
        'place_types': ['engineering_consulting', 'geotechnical_services'],
        'expected_gate': 'category',
        'expected_pass': True
    },
    {
        'name': 'Dee Signs',
        'address': '123 Main St, Burlington',
        'place_types': ['sign_shop', 'commercial_printing'],
        'latitude': 43.3255,
        'longitude': -79.7990,
        'expected_gates': ['category', 'geo'],
        'expected_passes': [True, False],  # Category OK, geo fails (Burlington outside Hamilton radius)
        'expected_reason_contains': ['radius']
    }
]

@pytest.mark.parametrize("case", GOLDEN_FAILURES)
def test_known_failures_blocked(case):
    """Ensure known bad leads are blocked."""
    validator = ValidationService()

    passed, reason = validator.category_gate(
        business={'name': case['name']},
        place_types=case['place_types']
    )

    assert passed == case['expected_pass'], f"Expected {case['name']} to fail category gate"
    assert case['expected_reason_contains'] in reason.lower(), f"Expected reason to contain '{case['expected_reason_contains']}'"

@pytest.mark.parametrize("case", GOLDEN_PASSES)
def test_known_passes_allowed(case):
    """Ensure valid leads pass gates."""
    validator = ValidationService()

    passed, reason = validator.category_gate(
        business={'name': case['name']},
        place_types=case['place_types']
    )

    assert passed == case['expected_pass'], f"Expected {case['name']} to pass category gate, got: {reason}"
```

### 8.2 Corroboration Tests

**Add to** `tests/test_corroboration.py`:

```python
def test_postal_code_mismatch_fails():
    """
    Test case: Pardon Applications of Canada
    - One source says L4P (wrong)
    - Another says L8P 4W7 (correct)
    - Should fail corroboration
    """
    observations = [
        Observation(business_id=1, source_url='source1', field='postal_code', value='L4P 1A1'),
        Observation(business_id=1, source_url='source2', field='postal_code', value='L8P 4W7')
    ]

    validator = ValidationService()
    passed, reason = validator.corroboration_gate(observations, 'postal_code', min_sources=2)

    assert not passed, "Mismatched postal codes should fail corroboration"
    assert 'conflicting' in reason.lower()

def test_address_corroboration_passes():
    """
    Test case: Two sources agree on address.
    """
    observations = [
        Observation(business_id=1, source_url='website', field='address', value='123 Main St, Hamilton, ON'),
        Observation(business_id=1, source_url='yelp', field='address', value='123 Main Street, Hamilton ON')
    ]

    validator = ValidationService()
    passed, reason = validator.corroboration_gate(observations, 'address', min_sources=2)

    assert passed, f"Matching addresses should pass: {reason}"
```

### 8.3 No-Guess Policy Tests

**Add to** `tests/test_llm_extraction.py`:

```python
def test_llm_returns_null_when_missing():
    """
    Test that LLM extraction returns null for missing fields.
    """
    content = """
    <html>
    <body>
        <h1>About Acme Corp</h1>
        <p>We provide excellent engineering services.</p>
    </body>
    </html>
    """

    llm = LLMService()
    result = await llm.extract_structured(
        url='https://acme.com/about',
        content=content,
        schema=CompanyExtraction
    )

    assert result.founding_year is None, "Should return null for missing founding year"
    assert result.team_size_mentioned is None, "Should return null for missing team size"

def test_llm_rejects_inferred_values():
    """
    Test that LLM does not infer values from indirect signals.
    """
    content = """
    <html>
    <body>
        <h1>Our Team</h1>
        <img src="team1.jpg" />
        <img src="team2.jpg" />
        <img src="team3.jpg" />
    </body>
    </html>
    """

    llm = LLMService()
    result = await llm.extract_structured(
        url='https://acme.com/team',
        content=content,
        schema=CompanyExtraction
    )

    # Should NOT infer team_size=3 from 3 images
    assert result.team_size_mentioned is None, "Should not infer team size from images"
```

---

## Phase 9: Reporting & Observability (Week 5)

### Objective
Build dashboards and reports to monitor validation quality and tune rules rapidly.

### 9.1 Validation Report Script

**Create** `scripts/validation_report.py`:

```python
import json
from datetime import datetime, timedelta
from collections import Counter

def generate_validation_report(days: int = 7):
    """
    Generate HTML report of validation results.

    Sections:
    1. Summary stats (total leads, pass rate, top exclusion reasons)
    2. Failed validations by rule
    3. Category distribution (allowed vs blocked)
    4. Geographic distribution
    5. Corroboration failures
    """

    since = datetime.now() - timedelta(days=days)

    # Get all businesses processed since cutoff
    businesses = db.get_businesses_since(since)
    validations = db.get_validations_since(since)
    exclusions = db.get_exclusions_since(since)

    # Summary
    total = len(businesses)
    qualified = len([b for b in businesses if b['status'] == 'QUALIFIED'])
    excluded = len([b for b in businesses if b['status'] == 'EXCLUDED'])
    pass_rate = qualified / total if total > 0 else 0

    # Top exclusion reasons
    exclusion_reasons = Counter([e['reason'] for e in exclusions])

    # Failed validations by rule
    failed_by_rule = Counter([v['rule_id'] for v in validations if not v['passed']])

    # Build HTML report
    html = f"""
    <html>
    <head><title>Validation Report - {datetime.now().date()}</title></head>
    <body>
        <h1>Lead Validation Report</h1>
        <p>Period: {since.date()} to {datetime.now().date()}</p>

        <h2>Summary</h2>
        <ul>
            <li>Total leads processed: {total}</li>
            <li>Qualified: {qualified} ({pass_rate:.1%})</li>
            <li>Excluded: {excluded}</li>
        </ul>

        <h2>Top Exclusion Reasons</h2>
        <ol>
            {''.join(f'<li>{reason}: {count}</li>' for reason, count in exclusion_reasons.most_common(10))}
        </ol>

        <h2>Failed Validations by Rule</h2>
        <table border="1">
            <tr><th>Rule</th><th>Failures</th></tr>
            {''.join(f'<tr><td>{rule}</td><td>{count}</td></tr>' for rule, count in failed_by_rule.most_common())}
        </table>
    </body>
    </html>
    """

    output_path = f"output/validation_report_{datetime.now().strftime('%Y%m%d')}.html"
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Report saved to {output_path}")
```

### 9.2 Real-time Monitoring

**Add to** `src/agents/orchestrator.py`:

```python
class OrchestrationMetrics:
    """Track pipeline metrics in real-time."""

    def __init__(self):
        self.discovered = 0
        self.enriched = 0
        self.qualified = 0
        self.excluded = 0
        self.exclusion_reasons = Counter()

    def log_exclusion(self, reason: str):
        self.excluded += 1
        self.exclusion_reasons[reason] += 1

    def print_summary(self):
        print(f"""
        Pipeline Summary:
        - Discovered: {self.discovered}
        - Enriched: {self.enriched}
        - Qualified: {self.qualified}
        - Excluded: {self.excluded}

        Top Exclusion Reasons:
        {self.exclusion_reasons.most_common(5)}
        """)
```

---

## Phase 10: CLI & Developer Experience (Week 5)

### Objective
Update CLI commands to reflect new evidence-based workflow.

### 10.1 New CLI Commands

**Update** `generate` script:

```bash
#!/bin/bash
# generate - discover and persist raw leads (no filtering)

PYTHONPATH=/mnt/d/AI_Automated_Potential_Business_outreach python3 scripts/discover_leads.py "$@"
```

**Update** `quickstart` script:

```bash
#!/bin/bash
# quickstart - full pipeline (discover → enrich → validate → export)

PYTHONPATH=/mnt/d/AI_Automated_Potential_Business_outreach python3 scripts/run_full_pipeline.py "$@"
```

**Add** `validate` script:

```bash
#!/bin/bash
# validate - run validation gates on existing leads

PYTHONPATH=/mnt/d/AI_Automated_Potential_Business_outreach python3 scripts/validate_leads.py "$@"
```

**Add** `report` script:

```bash
#!/bin/bash
# report - generate validation quality report

PYTHONPATH=/mnt/d/AI_Automated_Potential_Business_outreach python3 scripts/validation_report.py "$@"
```

### 10.2 Updated Orchestrator

**Rewrite** `src/agents/orchestrator.py`:

```python
class LeadOrchestrator:
    """
    Main pipeline orchestrator.

    Flow:
    1. discover() → persist raw leads (status=NEW)
    2. enrich() → query sources, create observations (status=ENRICHING)
    3. validate() → run gates, create validations (status=QUALIFIED or EXCLUDED)
    4. score() → calculate quality score
    5. export() → write to CSV/CRM (only is_exportable=True)
    """

    async def run_full_pipeline(self, count: int):
        metrics = OrchestrationMetrics()

        # 1. Discover
        logger.info(f"Discovering {count} leads...")
        lead_ids = await self.discover(count)
        metrics.discovered = len(lead_ids)

        # 2. Enrich
        logger.info(f"Enriching {len(lead_ids)} leads...")
        for lead_id in lead_ids:
            await self.enrich(lead_id)
            metrics.enriched += 1

        # 3. Validate
        logger.info(f"Validating {len(lead_ids)} leads...")
        for lead_id in lead_ids:
            qualified = await self.validate(lead_id)
            if qualified:
                metrics.qualified += 1
            else:
                exclusions = db.get_exclusions(lead_id)
                for exc in exclusions:
                    metrics.log_exclusion(exc['reason'])

        # 4. Score
        logger.info("Scoring qualified leads...")
        await self.score_qualified()

        # 5. Export
        logger.info("Exporting qualified leads...")
        export_path = await self.export()

        metrics.print_summary()
        logger.info(f"Pipeline complete. Export: {export_path}")

    async def discover(self, count: int) -> list[int]:
        """Discover leads and persist as status=NEW."""
        pass

    async def enrich(self, lead_id: int):
        """Enrich lead by querying sources and creating observations."""
        pass

    async def validate(self, lead_id: int) -> bool:
        """Run validation gates and update status."""
        pass

    async def score_qualified(self):
        """Calculate quality scores for QUALIFIED leads."""
        pass

    async def export(self) -> str:
        """Export leads that pass is_exportable check."""
        pass
```

---

## Success Criteria & Acceptance Tests

### Acceptance Test 1: Zero Retail Leakage
```
GIVEN a list of 100 discovered leads
WHEN the pipeline runs
THEN zero leads with types in CATEGORY_BLACKLIST should reach QUALIFIED status
```

### Acceptance Test 2: Corroboration Enforcement
```
GIVEN a lead with conflicting postal codes (L4P vs L8P)
WHEN corroboration gate runs
THEN the lead should be EXCLUDED with reason "postal_code has conflicting values"
```

### Acceptance Test 3: Geographic Boundary
```
GIVEN a lead in Burlington (20+ km from Hamilton centroid)
WHEN geo gate runs with max_radius_km=20
THEN the lead should be EXCLUDED with reason "Outside target radius"
```

### Acceptance Test 4: No-Guess Revenue
```
GIVEN a lead with no staff count and no category benchmark
WHEN revenue gate runs
THEN the lead should be EXCLUDED with reason "No revenue estimate"
```

### Acceptance Test 5: Export Gate
```
GIVEN 50 QUALIFIED leads where 10 have website_age_years < 3
WHEN export runs
THEN only 40 leads should be exported
AND blocked report should show 10 leads with reason "Website too new"
```

---

## Rollout Plan

### Week 1
- [ ] Implement database schema changes
- [ ] Create `evidence.py`, `rules.py`, `validation_service.py`
- [ ] Update `lead.py` model with new fields
- [ ] Write category gate + tests for golden failures
- [ ] Integrate Places API for category lookup

### Week 2
- [ ] Implement corroboration gate + tests
- [ ] Add geocoding service
- [ ] Implement geo gate + tests
- [ ] Update enrichment flow to create observations
- [ ] Test full discovery → enrich → validate flow

### Week 3
- [ ] Add company size service (LinkedIn, Facebook scraping)
- [ ] Create benchmarks.py with industry data
- [ ] Implement revenue gate + tests
- [ ] Harden LLM prompts with anti-hallucination rules
- [ ] Add extraction schemas

### Week 4
- [ ] Implement `is_exportable()` policy
- [ ] Update export script with export gate
- [ ] Write comprehensive test suite (golden tests, corroboration, no-guess)
- [ ] Run regression tests against sample leads
- [ ] Generate validation report

### Week 5
- [ ] Update CLI scripts (`generate`, `quickstart`, `validate`, `report`)
- [ ] Rewrite orchestrator with new flow
- [ ] Add real-time metrics tracking
- [ ] Documentation updates
- [ ] User acceptance testing

### Week 6 (Buffer)
- [ ] Performance tuning (async optimizations, caching)
- [ ] Edge case handling
- [ ] Production deployment
- [ ] Monitoring & alerting setup

---

## Appendix A: Quick Reference - Known Issues from Diagnosis

| Lead Name | Issue | Fix |
|-----------|-------|-----|
| Eastgate Variety | Convenience store (retail) passed category filter | Add to `CATEGORY_BLACKLIST`, add name pattern `r'variety'` |
| Pioneer (603 King E) | Gas station passed category filter | Add to `CATEGORY_BLACKLIST`, enforce Places API types |
| Performance Improvements | Auto parts retail passed filter | Add `auto_parts`, `aftermarket` to blacklist |
| Worldwide Mattress Outlet | Mattress retail passed filter | Add name pattern `r'mattress'`, `r'outlet'` |
| Mountain Hyundai | Car dealership passed filter | Add `car_dealer`, add name patterns for brands |
| Dee Signs | Burlington location outside Hamilton | Enforce geo gate with coordinate check |
| Pardon Applications | Postal code mismatch (L4P vs L8P) | Implement corroboration gate for postal |
| Weir's Lane Lavender | Retail/agr-tourism passed filter | Add `agr_tourism`, `farm_shop` to blacklist |

---

## Appendix B: File Structure After Implementation

```
src/
├── core/
│   ├── evidence.py          # NEW: Observation, Validation models
│   ├── rules.py             # NEW: Whitelists, blacklists
│   ├── benchmarks.py        # NEW: Industry benchmarks
│   └── export_policy.py     # NEW: is_exportable logic
├── models/
│   ├── lead.py              # MODIFIED: Add status, lat/lng, distance
│   └── extraction_schemas.py # NEW: Pydantic schemas for LLM
├── services/
│   ├── validation_service.py # NEW: All validation gates
│   ├── geocoding_service.py  # NEW: Geocoding + distance calc
│   ├── company_size_service.py # NEW: Staff estimation
│   └── llm_service.py        # MODIFIED: Anti-hallucination prompts
├── sources/
│   └── places.py            # NEW: Google/Yelp/OSM integration
├── prompts/
│   └── extraction_prompts.py # NEW: LLM prompt templates
└── agents/
    └── orchestrator.py      # REWRITTEN: New pipeline flow

tests/
├── test_validation_gates.py # NEW: Golden test cases
├── test_corroboration.py    # NEW: Corroboration tests
└── test_llm_extraction.py   # NEW: No-guess policy tests

scripts/
├── discover_leads.py        # MODIFIED: Persist raw immediately
├── validate_leads.py        # NEW: Run validation gates
├── validation_report.py     # NEW: Generate quality reports
└── export_leads.py          # MODIFIED: Use export gate

migrations/
└── 001_add_evidence_tables.sql  # NEW: Schema migration
```

---

## Appendix C: Configuration Reference

**Geographic Configuration** (Hamilton/Ancaster target):
```python
GEO_CONFIG = {
    'centroid_lat': 43.2557,    # Ancaster, ON
    'centroid_lng': -79.9537,
    'max_radius_km': 20,
    'allowed_cities': ['Hamilton', 'Ancaster', 'Dundas', 'Stoney Creek', 'Waterdown']
}
```

**Validation Configuration**:
```python
VALIDATION_CONFIG = {
    'min_corroboration_sources': 2,
    'min_website_age_years': 3,
    'min_revenue_confidence': 0.6,
    'require_staff_signal_or_benchmark': True
}
```

**API Keys Required**:
- Google Places API (for category lookup + geocoding)
- Yelp Fusion API (for business data)
- OpenStreetMap/Nominatim (free geocoding backup)
- LinkedIn API (optional, for company size)
- Wayback Machine API (for website age)

---

## Next Steps

1. **Review & Approve**: Review this plan with stakeholders
2. **Sprint Planning**: Break into 2-week sprints
3. **Setup**: Create GitHub issues for each phase
4. **Development**: Start with Phase 1 (Data Model)
5. **Testing**: Run golden tests after each phase
6. **Deployment**: Progressive rollout with validation reports

**Estimated Timeline**: 5-6 weeks full implementation
**Risk Level**: Low (additive changes, no breaking changes to existing exports)
**Dependencies**: Google Places API access, Yelp API access
