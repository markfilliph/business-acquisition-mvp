"""
Evidence tracking models and database operations.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class Observation:
    """Single observation from a data source."""
    business_id: int
    source_url: str
    field: str
    value: Optional[str]
    confidence: float = 1.0
    observed_at: Optional[datetime] = None
    queried_at: Optional[datetime] = None
    http_status: Optional[int] = None
    api_version: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            'business_id': self.business_id,
            'source_url': self.source_url,
            'field': self.field,
            'value': self.value,
            'confidence': self.confidence,
            'observed_at': self.observed_at.isoformat() if self.observed_at else None,
            'queried_at': self.queried_at.isoformat() if self.queried_at else None,
            'http_status': self.http_status,
            'api_version': self.api_version,
            'error': self.error
        }


@dataclass
class Validation:
    """Result of a validation gate."""
    business_id: int
    rule_id: str
    passed: bool
    reason: str
    evidence_ids: List[int] = field(default_factory=list)
    validated_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            'business_id': self.business_id,
            'rule_id': self.rule_id,
            'passed': self.passed,
            'reason': self.reason,
            'evidence_ids': json.dumps(self.evidence_ids),
            'validated_at': self.validated_at.isoformat() if self.validated_at else None
        }


@dataclass
class Exclusion:
    """Record of why a business was excluded."""
    business_id: int
    rule_id: str
    reason: str
    evidence_ids: List[int] = field(default_factory=list)
    excluded_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            'business_id': self.business_id,
            'rule_id': self.rule_id,
            'reason': self.reason,
            'evidence_ids': json.dumps(self.evidence_ids),
            'excluded_at': self.excluded_at.isoformat() if self.excluded_at else None
        }


async def create_observation(db, obs: Observation) -> int:
    """
    Insert observation and return ID.

    Args:
        db: Database connection
        obs: Observation object

    Returns:
        Observation ID
    """
    data = obs.to_dict()

    cursor = await db.execute(
        """INSERT INTO observations
        (business_id, source_url, field, value, confidence, observed_at, queried_at, http_status, api_version, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['business_id'],
            data['source_url'],
            data['field'],
            data['value'],
            data['confidence'],
            data['observed_at'],
            data['queried_at'],
            data['http_status'],
            data['api_version'],
            data['error']
        )
    )

    await db.commit()
    return cursor.lastrowid


async def create_validation(db, val: Validation) -> int:
    """
    Insert validation and return ID.

    Args:
        db: Database connection
        val: Validation object

    Returns:
        Validation ID
    """
    data = val.to_dict()

    cursor = await db.execute(
        """INSERT INTO validations
        (business_id, rule_id, passed, reason, evidence_ids, validated_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            data['business_id'],
            data['rule_id'],
            data['passed'],
            data['reason'],
            data['evidence_ids'],
            data['validated_at']
        )
    )

    await db.commit()
    return cursor.lastrowid


async def create_exclusion(db, exc: Exclusion) -> int:
    """
    Insert exclusion and return ID.

    Args:
        db: Database connection
        exc: Exclusion object

    Returns:
        Exclusion ID
    """
    data = exc.to_dict()

    cursor = await db.execute(
        """INSERT INTO exclusions
        (business_id, rule_id, reason, evidence_ids, excluded_at)
        VALUES (?, ?, ?, ?, ?)""",
        (
            data['business_id'],
            data['rule_id'],
            data['reason'],
            data['evidence_ids'],
            data['excluded_at']
        )
    )

    await db.commit()
    return cursor.lastrowid


async def get_observations(db, business_id: int, field: Optional[str] = None) -> List[Observation]:
    """
    Get observations for a business.

    Args:
        db: Database connection
        business_id: Business ID
        field: Optional field filter

    Returns:
        List of Observation objects
    """
    if field:
        cursor = await db.execute(
            "SELECT * FROM observations WHERE business_id = ? AND field = ? ORDER BY observed_at DESC",
            (business_id, field)
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM observations WHERE business_id = ? ORDER BY observed_at DESC",
            (business_id,)
        )

    rows = await cursor.fetchall()

    observations = []
    for row in rows:
        obs = Observation(
            business_id=row['business_id'],
            source_url=row['source_url'],
            field=row['field'],
            value=row['value'],
            confidence=row['confidence'],
            observed_at=datetime.fromisoformat(row['observed_at']) if row['observed_at'] else None,
            queried_at=datetime.fromisoformat(row['queried_at']) if row['queried_at'] else None,
            http_status=row['http_status'],
            api_version=row['api_version'],
            error=row['error']
        )
        observations.append(obs)

    return observations


async def get_validations(db, business_id: int) -> List[Validation]:
    """Get all validations for a business."""
    cursor = await db.execute(
        "SELECT * FROM validations WHERE business_id = ? ORDER BY validated_at DESC",
        (business_id,)
    )

    rows = await cursor.fetchall()

    validations = []
    for row in rows:
        val = Validation(
            business_id=row['business_id'],
            rule_id=row['rule_id'],
            passed=bool(row['passed']),
            reason=row['reason'],
            evidence_ids=json.loads(row['evidence_ids']) if row['evidence_ids'] else [],
            validated_at=datetime.fromisoformat(row['validated_at']) if row['validated_at'] else None
        )
        validations.append(val)

    return validations


async def get_exclusions(db, business_id: int) -> List[Exclusion]:
    """Get all exclusions for a business."""
    cursor = await db.execute(
        "SELECT * FROM exclusions WHERE business_id = ? ORDER BY excluded_at DESC",
        (business_id,)
    )

    rows = await cursor.fetchall()

    exclusions = []
    for row in rows:
        exc = Exclusion(
            business_id=row['business_id'],
            rule_id=row['rule_id'],
            reason=row['reason'],
            evidence_ids=json.loads(row['evidence_ids']) if row['evidence_ids'] else [],
            excluded_at=datetime.fromisoformat(row['excluded_at']) if row['excluded_at'] else None
        )
        exclusions.append(exc)

    return exclusions
