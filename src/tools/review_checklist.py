"""
Generate systematic manual review checklists for top leads.
Because Googling is faster than building automation.

PRACTICAL PLAN: Task 5
5-minute systematic verification per lead.
"""
from typing import List, Optional
from pathlib import Path
from ..core.models import BusinessLead


class ManualReviewChecklist:
    """Generate review tasks for lead verification."""

    def generate_checklist(self, lead: BusinessLead) -> str:
        """
        Create 5-minute manual review checklist for a lead.

        Checklist covers:
        1. Still operating (1 min)
        2. Compliance & risk (1 min)
        3. Business type (1 min)
        4. Validate size (1 min)
        5. Quick due diligence (1 min)

        Args:
            lead: BusinessLead object to review

        Returns:
            Formatted checklist string
        """
        # Get lead data
        website = lead.contact.website or "NO WEBSITE - check directory listings"
        warnings_str = ""
        if lead.warnings:
            warnings_str = "\n⚠️ SYSTEM WARNINGS:\n"
            for warning in lead.warnings:
                warnings_str += f"  - {warning}\n"

        checklist = f"""
=== MANUAL REVIEW: {lead.business_name} ===
Priority: {'HIGH' if not lead.warnings else 'MEDIUM'}
Estimated Time: 5 minutes

STEP 1: Verify Still Operating (1 min)
  [ ] Google: "{lead.business_name} closed"
  [ ] Check Google Maps: Recent reviews (last 3 months)?
  [ ] Website accessible: {website}

  Red Flags: "Permanently closed", "Out of business", auction notices

STEP 2: Check Compliance & Risk (1 min)
  [ ] Google: "{lead.business_name} Hamilton violations"
  [ ] Google: "{lead.business_name} Hamilton health"
  [ ] Google News: "{lead.business_name}" (filter: past year)

  Red Flags: Health closures, lawsuits, distress sales, negative press

STEP 3: Verify Business Type (1 min)
  [ ] Website: Primarily B2B or consumer retail?
  [ ] Customer base: Industrial/commercial or retail consumers?
  [ ] If food business: Restaurant/retail or manufacturing?

  Red Flags: Retail storefront, consumer e-commerce, franchise

STEP 4: Validate Size (1 min)
  [ ] LinkedIn company page: How many employees listed?
  [ ] Website "About" page: Company size mentioned?
  [ ] Multiple locations mentioned anywhere?

  Red Flags: 50+ employees on LinkedIn, "offices in X cities", "global"

STEP 5: Quick Due Diligence (1 min)
  [ ] BBB profile or rating
  [ ] Any public financial disclosures?
  [ ] Google: "{lead.business_name} for sale" (already on market?)

  Red Flags: F rating, bankruptcy filings, actively listed for sale

---
DECISION:
  [ ] PROCEED - Clean lead, ready for outreach
  [ ] FLAG - Minor concerns, proceed with caution
  [ ] EXCLUDE - Deal-breaker issue found

Notes:
_________________________________________________________________
_________________________________________________________________

{warnings_str}
QUICK SEARCH QUERIES:
  - "{lead.business_name}" Hamilton manufacturing
  - "{lead.business_name}" reviews
  - "{lead.business_name}" employees linkedin
  - site:linkedin.com/company "{lead.business_name}"
"""

        return checklist

    def generate_batch_checklist(self,
                                 leads: List[BusinessLead],
                                 filename: str = "manual_review_checklist.txt") -> str:
        """
        Generate checklist file for multiple leads.

        Prioritizes:
        1. Leads with no warnings (cleanest)
        2. Leads with warnings (need extra scrutiny)

        Args:
            leads: List of BusinessLead objects
            filename: Output filename (default: manual_review_checklist.txt)

        Returns:
            Path to generated file
        """
        # Sort: no warnings first (highest priority)
        sorted_leads = sorted(leads, key=lambda x: len(x.warnings))

        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write("=" * 70 + "\n")
            f.write("MANUAL REVIEW CHECKLIST - BATCH\n")
            f.write(f"Total Leads: {len(leads)}\n")
            f.write(f"Estimated Time: {len(leads) * 5} minutes ({len(leads) * 5 / 60:.1f} hours)\n")
            f.write("=" * 70 + "\n\n")

            for i, lead in enumerate(sorted_leads, 1):
                f.write(f"\n{'=' * 70}\n")
                f.write(f"LEAD {i} of {len(leads)}\n")
                f.write(self.generate_checklist(lead))
                f.write("\n")

        return str(output_path)


def export_review_checklist(leads: List[BusinessLead],
                            output_path: str = "data/outputs/manual_review_checklist.txt") -> str:
    """
    Export manual review checklist for leads.

    Usage:
        clean_leads = [lead for lead in pipeline if lead.status == "QUALIFIED"]
        export_review_checklist(clean_leads[:15])  # Top 15 leads

    Args:
        leads: List of BusinessLead objects to review
        output_path: Output file path (default: data/outputs/manual_review_checklist.txt)

    Returns:
        Path to generated checklist file
    """
    checker = ManualReviewChecklist()
    filename = checker.generate_batch_checklist(leads, output_path)

    print(f"\n✅ Review checklist generated: {filename}")
    print(f"📋 {len(leads)} leads to review")
    print(f"⏱️  Estimated time: {len(leads) * 5} minutes\n")

    return filename


def export_prioritized_checklists(leads: List[BusinessLead],
                                  output_dir: str = "data/outputs/") -> dict:
    """
    Export two separate checklists: high-priority and needs-review.

    High-priority: No warnings, review first
    Needs-review: Has warnings, extra scrutiny

    Args:
        leads: List of BusinessLead objects
        output_dir: Output directory (default: data/outputs/)

    Returns:
        Dict with paths to both files
    """
    # Separate leads
    high_priority = [lead for lead in leads if not lead.warnings]
    needs_review = [lead for lead in leads if lead.warnings]

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    paths = {}

    # Generate high-priority checklist
    if high_priority:
        high_priority_path = str(output_dir_path / "review_HIGH_PRIORITY.txt")
        paths['high_priority'] = export_review_checklist(high_priority, high_priority_path)

    # Generate needs-review checklist
    if needs_review:
        needs_review_path = str(output_dir_path / "review_NEEDS_REVIEW.txt")
        paths['needs_review'] = export_review_checklist(needs_review, needs_review_path)

    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"  High Priority (no warnings): {len(high_priority)} leads")
    print(f"  Needs Review (has warnings): {len(needs_review)} leads")
    print(f"  Total: {len(leads)} leads\n")

    return paths


# ===================================================================
# Example Usage
# ===================================================================

def example_usage():
    """
    Example of how to use the checklist generator in your pipeline.
    """
    # After pipeline runs and filters clean data
    from ..core.models import BusinessLead, LeadStatus

    # Get your top leads (already passed all filters)
    # top_leads = [lead for lead in pipeline if lead.status == LeadStatus.QUALIFIED]
    # top_leads = sorted(top_leads, key=lambda x: x.lead_score.total_score, reverse=True)[:15]

    # Option 1: Single checklist for all leads
    # export_review_checklist(top_leads, "data/outputs/manual_review_checklist.txt")

    # Option 2: Separate high-priority and needs-review
    # export_prioritized_checklists(top_leads, "data/outputs/")

    # Now spend 5 min per lead systematically checking
    pass
