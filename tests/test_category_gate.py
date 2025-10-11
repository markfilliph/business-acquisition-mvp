"""
Tests for category gate with HITL review queue.
Validates that borderline categories are flagged for human review.
"""

import pytest
from src.gates.category_gate import (
    category_gate,
    CategoryGateResult,
    REVIEW_REQUIRED_CATEGORIES,
    get_review_categories,
    add_review_category,
    remove_review_category
)
from src.core.models import LeadStatus


class TestCategoryGateBasics:
    """Test basic category gate functionality."""

    def test_borderline_category_requires_review(self):
        """Test that funeral home requires review."""
        result = category_gate("funeral_home")

        assert result.requires_review is True
        assert result.passes is False
        assert result.suggested_status == LeadStatus.REVIEW_REQUIRED
        assert "funeral_home" in result.review_reason.lower()

    def test_clear_category_passes(self):
        """Test that manufacturing passes automatically."""
        result = category_gate("manufacturing")

        assert result.requires_review is False
        assert result.passes is True
        assert result.suggested_status is None
        assert result.review_reason is None

    def test_franchise_office_requires_review(self):
        """Test that franchise office requires review."""
        result = category_gate("franchise_office")

        assert result.requires_review is True
        assert result.suggested_status == LeadStatus.REVIEW_REQUIRED


class TestCategoryGateNormalization:
    """Test category name normalization."""

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        result1 = category_gate("FUNERAL_HOME")
        result2 = category_gate("Funeral_Home")
        result3 = category_gate("funeral_home")

        assert result1.requires_review is True
        assert result2.requires_review is True
        assert result3.requires_review is True

    def test_spaces_normalized_to_underscores(self):
        """Test that spaces are normalized to underscores."""
        result = category_gate("funeral home")

        assert result.requires_review is True
        assert result.suggested_status == LeadStatus.REVIEW_REQUIRED


class TestCategoryGateWithBusinessTypes:
    """Test category gate with business types list."""

    def test_business_type_triggers_review(self):
        """Test that business type in REVIEW_REQUIRED triggers review."""
        result = category_gate(
            industry="services",
            business_types=["funeral_home", "catering"]
        )

        assert result.requires_review is True
        assert "funeral_home" in result.review_reason.lower()

    def test_multiple_business_types_first_match_wins(self):
        """Test that first matching business type triggers review."""
        result = category_gate(
            industry="services",
            business_types=["catering", "funeral_home", "real_estate_agent"]
        )

        assert result.requires_review is True
        assert result.category == "funeral_home"

    def test_no_matching_business_types_passes(self):
        """Test that non-matching business types pass."""
        result = category_gate(
            industry="manufacturing",
            business_types=["printing", "metal_fabrication"]
        )

        assert result.requires_review is False
        assert result.passes is True


class TestReviewRequiredCategories:
    """Test REVIEW_REQUIRED_CATEGORIES list."""

    def test_review_categories_list_contains_expected(self):
        """Test that review categories list contains expected categories."""
        categories = get_review_categories()

        assert "funeral_home" in categories
        assert "franchise_office" in categories
        assert "real_estate_agent" in categories
        assert "insurance_agent" in categories

    def test_add_review_category(self):
        """Test adding a category to review list."""
        # Save original list
        original_count = len(get_review_categories())

        # Add new category
        add_review_category("tattoo_parlor")

        # Verify added
        assert "tattoo_parlor" in get_review_categories()
        assert len(get_review_categories()) == original_count + 1

        # Verify it triggers review
        result = category_gate("tattoo_parlor")
        assert result.requires_review is True

        # Cleanup
        remove_review_category("tattoo_parlor")

    def test_remove_review_category(self):
        """Test removing a category from review list."""
        # Add temporary category
        add_review_category("test_category")
        assert "test_category" in get_review_categories()

        # Remove it
        remove_review_category("test_category")
        assert "test_category" not in get_review_categories()

        # Verify it no longer triggers review
        result = category_gate("test_category")
        assert result.requires_review is False


class TestCategoryGateResult:
    """Test CategoryGateResult dataclass."""

    def test_result_to_dict(self):
        """Test that result converts to dict correctly."""
        result = CategoryGateResult(
            passes=False,
            requires_review=True,
            category="funeral_home",
            review_reason="Borderline category",
            suggested_status=LeadStatus.REVIEW_REQUIRED
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is False
        assert result_dict["requires_review"] is True
        assert result_dict["category"] == "funeral_home"
        assert result_dict["review_reason"] == "Borderline category"
        assert result_dict["suggested_status"] == "review_required"

    def test_result_without_optional_fields(self):
        """Test result with optional fields as None."""
        result = CategoryGateResult(
            passes=True,
            requires_review=False,
            category="manufacturing",
            review_reason=None,
            suggested_status=None
        )

        result_dict = result.to_dict()

        assert result_dict["passes"] is True
        assert result_dict["review_reason"] is None
        assert result_dict["suggested_status"] is None


class TestCategoryGateEdgeCases:
    """Test edge cases."""

    def test_empty_industry(self):
        """Test handling of empty industry."""
        result = category_gate("")

        assert result.requires_review is False
        assert result.passes is True

    def test_none_industry(self):
        """Test handling of None industry."""
        result = category_gate(None)

        assert result.requires_review is False
        assert result.passes is True

    def test_whitespace_only_industry(self):
        """Test handling of whitespace-only industry."""
        result = category_gate("   ")

        assert result.requires_review is False
        assert result.passes is True


class TestCategoryGateGoldenCases:
    """Test golden cases for HITL review."""

    def test_golden_case_funeral_home(self):
        """Golden case: Funeral home should require review."""
        result = category_gate("funeral_home")

        assert result.requires_review is True
        assert result.passes is False
        assert result.suggested_status == LeadStatus.REVIEW_REQUIRED
        assert "funeral_home" in result.review_reason.lower()

    def test_golden_case_franchise_office(self):
        """Golden case: Franchise office should require review."""
        result = category_gate("franchise_office")

        assert result.requires_review is True
        assert result.suggested_status == LeadStatus.REVIEW_REQUIRED

    def test_golden_case_manufacturing_passes(self):
        """Golden case: Manufacturing should pass automatically."""
        result = category_gate("manufacturing")

        assert result.requires_review is False
        assert result.passes is True
        assert result.suggested_status is None

    def test_golden_case_printing_passes(self):
        """Golden case: Printing should pass automatically."""
        result = category_gate("printing")

        assert result.requires_review is False
        assert result.passes is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
