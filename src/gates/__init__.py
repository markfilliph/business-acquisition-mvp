"""
Gates module for business qualification.

Gates are validation checkpoints that businesses must pass to be exported as leads.
Each gate enforces specific criteria and provides detailed rejection reasons.
"""

from .revenue_gate import revenue_gate, RevenueGateResult
from .geo_gate import geo_gate, GeoGateResult

__all__ = [
    "revenue_gate",
    "RevenueGateResult",
    "geo_gate",
    "GeoGateResult",
]
