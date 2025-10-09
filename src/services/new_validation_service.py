"""
Evidence-based validation service with deterministic gates.
Replaces old validation_service.py with new implementation plan.
"""

import re
from typing import Tuple, List, Optional, Dict
from datetime import datetime
import structlog

from ..core.rules import (
    TARGET_WHITELIST,
    CATEGORY_BLACKLIST,
    NAME_BLACKLIST_PATTERNS,
    REVIEW_REQUIRED_CATEGORIES,
    GEO_CONFIG
)
from ..core.normalization import normalize_value, compare_addresses
from ..core.evidence import Observation, Validation, Exclusion

logger = structlog.get_logger(__name__)


class ValidationService:
    """
    Evidence-based validation with multiple gates.
    Each gate returns (passed, reason, optional_action).
    """

    def __init__(self):
        self.logger = logger

    def category_gate(self, business: dict, place_types: List[str]) -> Tuple[bool, str, Optional[str]]:
        """
        Deterministic category validation.

        Checks:
        1. Name pattern blacklist
        2. Place type blacklist
        3. Place type whitelist
        4. Review-required categories

        Returns:
            (passed, reason, action)
            action: None | 'REVIEW_REQUIRED' | 'AUTO_EXCLUDE'
        """
        name = business.get('name', '').lower()

        # Check 1: Name patterns
        for pattern in NAME_BLACKLIST_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                self.logger.info("category_gate_failed_name_pattern",
                               business_name=name,
                               pattern=pattern)
                return False, f"Name matches blacklist pattern: {pattern}", 'AUTO_EXCLUDE'

        # Check 2: Place types against blacklist
        for ptype in place_types:
            if ptype in CATEGORY_BLACKLIST:
                self.logger.info("category_gate_failed_blacklist",
                               business_name=name,
                               category=ptype)
                return False, f"Category blacklisted: {ptype}", 'AUTO_EXCLUDE'

        # Check 3: Review-required categories
        for ptype in place_types:
            if ptype in REVIEW_REQUIRED_CATEGORIES:
                reason = REVIEW_REQUIRED_CATEGORIES[ptype]
                self.logger.info("category_gate_review_required",
                               business_name=name,
                               category=ptype,
                               reason=reason)
                return False, f"Category requires review: {ptype} ({reason})", 'REVIEW_REQUIRED'

        # Check 4: Must have at least one whitelisted type
        whitelisted = [pt for pt in place_types if pt in TARGET_WHITELIST]
        if not whitelisted:
            self.logger.info("category_gate_failed_no_whitelist",
                           business_name=name,
                           place_types=place_types)
            return False, f"No whitelisted category found in: {place_types}", 'AUTO_EXCLUDE'

        self.logger.info("category_gate_passed",
                       business_name=name,
                       whitelisted_types=whitelisted)
        return True, f"Category validated: {whitelisted[0]}", None

    def geo_gate(self, business: dict, config: dict = None) -> Tuple[bool, str, Optional[str]]:
        """
        Geographic validation with radius and city allowlist.

        Returns:
            (passed, reason, action)
        """
        if config is None:
            config = GEO_CONFIG

        lat = business.get('latitude')
        lng = business.get('longitude')

        if lat is None or lng is None:
            return False, "Business not geocoded", 'REVIEW_REQUIRED'

        # Calculate distance
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0  # Earth radius in km

        lat1, lng1 = radians(lat), radians(lng)
        lat2, lng2 = radians(config['centroid_lat']), radians(config['centroid_lng'])

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance_km = R * c

        # Store distance
        business['distance_km'] = distance_km

        # Check radius
        if distance_km > config['max_radius_km']:
            return False, f"Outside target radius: {distance_km:.1f}km > {config['max_radius_km']}km", 'AUTO_EXCLUDE'

        # Check city allowlist
        city = business.get('city', '').strip()
        if city and city not in config.get('allowed_cities', []):
            return False, f"City '{city}' not in allowed list: {config.get('allowed_cities', [])}", 'AUTO_EXCLUDE'

        return True, f"Within target radius: {distance_km:.1f}km", None

    def corroboration_gate(self, observations: List[Observation], field: str, min_sources: int = 2) -> Tuple[bool, str, Optional[str]]:
        """
        Check if field has min_sources independent observations with matching values.

        Returns:
            (passed, reason, action)
            action: 'REVIEW_REQUIRED' for 1-vs-1 conflicts
        """
        field_obs = [o for o in observations if o.field == field]

        if len(field_obs) < min_sources:
            if len(field_obs) == 1:
                # Single source - mark for review
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
                return True, f"{field} corroborated by {len(obs_list)} sources: {norm_val}", None

        # 1-vs-1 conflict - needs human review
        if len(field_obs) == 2 and len(value_groups) == 2:
            values = list(value_groups.keys())
            return False, f"{field} has 1-vs-1 conflict: {values[0]} vs {values[1]}", 'REVIEW_REQUIRED'

        # Multiple conflicts - likely bad data
        return False, f"{field} has {len(value_groups)} conflicting values: {list(value_groups.keys())}", 'AUTO_EXCLUDE'

    def website_gate(self, business: dict, min_age_years: int = 3) -> Tuple[bool, str, Optional[str]]:
        """
        Validate website exists, is not parked, has age signal.

        Args:
            business: Business dict with website_ok, website_age_years fields
            min_age_years: Minimum website age

        Returns:
            (passed, reason, action)
        """
        website_ok = business.get('website_ok', False)
        website_age = business.get('website_age_years', 0)

        if not website_ok:
            return False, "Website not validated (unreachable or parked)", 'AUTO_EXCLUDE'

        if website_age < min_age_years:
            if website_age >= min_age_years - 0.5:
                # Borderline (2.5-3.0 years) - review
                return False, f"Website borderline age ({website_age:.1f} years)", 'REVIEW_REQUIRED'
            return False, f"Website too new ({website_age:.1f} < {min_age_years} years)", 'AUTO_EXCLUDE'

        return True, f"Website validated (age: {website_age:.1f} years)", None

    def revenue_gate(self, business: dict) -> Tuple[bool, str, Optional[str]]:
        """
        STRICT revenue validation.
        Requires confidence >= 0.6 AND (staff signal OR benchmark).

        Returns:
            (passed, reason, action)
        """
        revenue = business.get('revenue_estimate', {})

        if not revenue or not revenue.get('revenue_min'):
            return False, "No revenue estimate", 'AUTO_EXCLUDE'

        confidence = revenue.get('confidence', 0)
        if confidence < 0.6:
            return False, f"Revenue confidence too low ({confidence:.2f} < 0.6)", 'AUTO_EXCLUDE'

        # Require underlying signals
        has_staff = business.get('staff_count') is not None
        has_benchmark = business.get('category_benchmark') is not None

        if not (has_staff or has_benchmark):
            return False, "No staff signal or category benchmark to support revenue estimate", 'AUTO_EXCLUDE'

        methodology = revenue.get('methodology', 'unknown')
        return True, f"Revenue estimate acceptable (confidence {confidence:.2f}, methodology: {methodology})", None

    async def validate_business(self, db, business_id: int, place_types: List[str]) -> Tuple[str, List[str]]:
        """
        Run all validation gates for a business.

        Returns:
            (status, reasons)
            status: 'QUALIFIED', 'EXCLUDED', 'REVIEW_REQUIRED'
            reasons: List of failure reasons
        """
        from ..core.evidence import get_observations, create_validation, create_exclusion

        # Get business data
        cursor = await db.execute("SELECT * FROM businesses WHERE id = ?", (business_id,))
        row = await cursor.fetchone()

        if not row:
            return 'EXCLUDED', ['Business not found']

        business = dict(row)
        reasons = []
        validations = []

        # Gate 1: Category
        passed, reason, action = self.category_gate(business, place_types)
        validations.append(Validation(
            business_id=business_id,
            rule_id='category_gate',
            passed=passed,
            reason=reason,
            validated_at=datetime.utcnow()
        ))

        if not passed:
            reasons.append(reason)
            if action == 'REVIEW_REQUIRED':
                return 'REVIEW_REQUIRED', reasons
            elif action == 'AUTO_EXCLUDE':
                # Create exclusion
                await create_exclusion(db, Exclusion(
                    business_id=business_id,
                    rule_id='category_gate',
                    reason=reason,
                    excluded_at=datetime.utcnow()
                ))
                return 'EXCLUDED', reasons

        # Gate 2: Geography
        passed, reason, action = self.geo_gate(business)
        validations.append(Validation(
            business_id=business_id,
            rule_id='geo_gate',
            passed=passed,
            reason=reason,
            validated_at=datetime.utcnow()
        ))

        if not passed:
            reasons.append(reason)
            if action == 'AUTO_EXCLUDE':
                await create_exclusion(db, Exclusion(
                    business_id=business_id,
                    rule_id='geo_gate',
                    reason=reason,
                    excluded_at=datetime.utcnow()
                ))
                return 'EXCLUDED', reasons

        # Gate 3: Corroboration (check critical fields)
        observations = await get_observations(db, business_id)

        for field in ['address', 'phone', 'postal_code']:
            passed, reason, action = self.corroboration_gate(observations, field)
            validations.append(Validation(
                business_id=business_id,
                rule_id=f'corroboration_{field}',
                passed=passed,
                reason=reason,
                validated_at=datetime.utcnow()
            ))

            if not passed:
                reasons.append(reason)
                if action == 'REVIEW_REQUIRED':
                    return 'REVIEW_REQUIRED', reasons

        # Gate 4: Website
        passed, reason, action = self.website_gate(business)
        validations.append(Validation(
            business_id=business_id,
            rule_id='website_gate',
            passed=passed,
            reason=reason,
            validated_at=datetime.utcnow()
        ))

        if not passed:
            reasons.append(reason)
            if action == 'REVIEW_REQUIRED':
                return 'REVIEW_REQUIRED', reasons
            elif action == 'AUTO_EXCLUDE':
                await create_exclusion(db, Exclusion(
                    business_id=business_id,
                    rule_id='website_gate',
                    reason=reason,
                    excluded_at=datetime.utcnow()
                ))
                return 'EXCLUDED', reasons

        # Gate 5: Revenue
        passed, reason, action = self.revenue_gate(business)
        validations.append(Validation(
            business_id=business_id,
            rule_id='revenue_gate',
            passed=passed,
            reason=reason,
            validated_at=datetime.utcnow()
        ))

        if not passed:
            reasons.append(reason)
            await create_exclusion(db, Exclusion(
                business_id=business_id,
                rule_id='revenue_gate',
                reason=reason,
                excluded_at=datetime.utcnow()
            ))
            return 'EXCLUDED', reasons

        # All gates passed
        # Save validations
        from ..core.evidence import create_validation
        for val in validations:
            await create_validation(db, val)

        return 'QUALIFIED', []
