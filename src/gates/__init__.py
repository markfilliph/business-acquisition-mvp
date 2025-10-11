"""
Gates module for business qualification.

Gates are validation checkpoints that businesses must pass to be exported as leads.
Each gate enforces specific criteria and provides detailed rejection reasons.
"""

from .revenue_gate import revenue_gate, RevenueGateResult

__all__ = ["revenue_gate", "RevenueGateResult"]
