#!/usr/bin/env python3
"""
Human-in-the-Loop (HITL) Review Queue CLI
PRIORITY: P1 - Critical for quality control on borderline cases.

Task 10: HITL Review Queue
CLI tool for analysts to review leads that require human judgment.

Usage:
    python scripts/review_queue.py list
    python scripts/review_queue.py approve <business_id> --reason "Legitimate manufacturing business"
    python scripts/review_queue.py reject <business_id> --reason "Funeral home - not target market"
    python scripts/review_queue.py stats
"""

import sys
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import LeadStatus
from src.database.connection import DatabaseManager
from src.core.config import config

logger = structlog.get_logger(__name__)


class ReviewQueue:
    """Manage human review queue for borderline business leads."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def list_pending_reviews(self, limit: int = 50):
        """
        List all leads requiring review.

        Args:
            limit: Maximum number of leads to display
        """
        try:
            leads = await self.db.get_leads_by_status(LeadStatus.REVIEW_REQUIRED, limit=limit)

            if not leads:
                print("✅ No leads pending review")
                return

            print(f"\n📋 Leads Pending Review ({len(leads)})\n")
            print("=" * 120)
            print(f"{'ID':<8} {'Business Name':<35} {'Industry':<20} {'Review Reason':<40}")
            print("=" * 120)

            for lead in leads:
                business_id = lead.get('id')
                name = lead.get('business_name', '')[:32] + '...' if len(lead.get('business_name', '')) > 35 else (lead.get('business_name') or '')
                industry = (lead.get('industry') or 'Unknown')[:19]
                reason = (lead.get('review_reason') or 'Not specified')[:39]

                print(f"{business_id:<8} {name:<35} {industry:<20} {reason:<40}")

            print("=" * 120)
            print(f"\nTotal: {len(leads)} leads")
            print("\nNext steps:")
            print("  • Review each lead manually")
            print("  • Approve: python scripts/review_queue.py approve <id> --reason '<reason>'")
            print("  • Reject:  python scripts/review_queue.py reject <id> --reason '<reason>'\n")

        except Exception as e:
            logger.error("list_pending_reviews_failed", error=str(e))
            print(f"❌ Error listing reviews: {e}")
            sys.exit(1)

    async def approve_lead(self, business_id: int, reason: str, analyst: str = "analyst"):
        """
        Approve a lead (move to QUALIFIED).

        Args:
            business_id: Business database ID
            reason: Reason for approval
            analyst: Analyst name (defaults to "analyst")
        """
        if not reason or len(reason.strip()) < 10:
            print("❌ Error: Approval reason must be at least 10 characters")
            sys.exit(1)

        try:
            async with self.db.get_connection() as db:
                # Check if lead exists and is in review status
                cursor = await db.execute(
                    "SELECT id, business_name, status FROM leads WHERE id = ?",
                    (business_id,)
                )
                lead = await cursor.fetchone()

                if not lead:
                    print(f"❌ Error: Business ID {business_id} not found")
                    sys.exit(1)

                if lead[2] != LeadStatus.REVIEW_REQUIRED.value:
                    print(f"❌ Error: Business '{lead[1]}' is not in review status (current: {lead[2]})")
                    sys.exit(1)

                # Update lead status to QUALIFIED
                await db.execute(
                    """
                    UPDATE leads
                    SET status = ?,
                        reviewed_by = ?,
                        reviewed_at = ?,
                        review_decision = 'approved',
                        review_notes = ?
                    WHERE id = ?
                    """,
                    (LeadStatus.QUALIFIED.value, analyst, datetime.utcnow(), reason, business_id)
                )

                await db.commit()

                # Log activity
                await db.execute(
                    """
                    INSERT INTO lead_activities (lead_unique_id, activity_type, activity_description, activity_data)
                    SELECT unique_id, 'review_approved', ?, ?
                    FROM leads WHERE id = ?
                    """,
                    (
                        f"Approved by {analyst}",
                        f'{{"reason": "{reason}", "analyst": "{analyst}"}}',
                        business_id
                    )
                )

                await db.commit()

                print(f"✅ Approved: '{lead[1]}' (ID: {business_id})")
                print(f"   Analyst: {analyst}")
                print(f"   Reason: {reason}")
                print(f"   Status: REVIEW_REQUIRED → QUALIFIED")

                logger.info(
                    "lead_approved",
                    business_id=business_id,
                    business_name=lead[1],
                    analyst=analyst,
                    reason=reason
                )

        except Exception as e:
            logger.error("approve_lead_failed", business_id=business_id, error=str(e))
            print(f"❌ Error approving lead: {e}")
            sys.exit(1)

    async def reject_lead(self, business_id: int, reason: str, analyst: str = "analyst"):
        """
        Reject a lead (move to DISQUALIFIED).

        Args:
            business_id: Business database ID
            reason: Reason for rejection
            analyst: Analyst name (defaults to "analyst")
        """
        if not reason or len(reason.strip()) < 10:
            print("❌ Error: Rejection reason must be at least 10 characters")
            sys.exit(1)

        try:
            async with self.db.get_connection() as db:
                # Check if lead exists and is in review status
                cursor = await db.execute(
                    "SELECT id, business_name, status FROM leads WHERE id = ?",
                    (business_id,)
                )
                lead = await cursor.fetchone()

                if not lead:
                    print(f"❌ Error: Business ID {business_id} not found")
                    sys.exit(1)

                if lead[2] != LeadStatus.REVIEW_REQUIRED.value:
                    print(f"❌ Error: Business '{lead[1]}' is not in review status (current: {lead[2]})")
                    sys.exit(1)

                # Update lead status to DISQUALIFIED
                await db.execute(
                    """
                    UPDATE leads
                    SET status = ?,
                        reviewed_by = ?,
                        reviewed_at = ?,
                        review_decision = 'rejected',
                        review_notes = ?
                    WHERE id = ?
                    """,
                    (LeadStatus.DISQUALIFIED.value, analyst, datetime.utcnow(), reason, business_id)
                )

                await db.commit()

                # Log activity
                await db.execute(
                    """
                    INSERT INTO lead_activities (lead_unique_id, activity_type, activity_description, activity_data)
                    SELECT unique_id, 'review_rejected', ?, ?
                    FROM leads WHERE id = ?
                    """,
                    (
                        f"Rejected by {analyst}",
                        f'{{"reason": "{reason}", "analyst": "{analyst}"}}',
                        business_id
                    )
                )

                await db.commit()

                print(f"❌ Rejected: '{lead[1]}' (ID: {business_id})")
                print(f"   Analyst: {analyst}")
                print(f"   Reason: {reason}")
                print(f"   Status: REVIEW_REQUIRED → DISQUALIFIED")

                logger.info(
                    "lead_rejected",
                    business_id=business_id,
                    business_name=lead[1],
                    analyst=analyst,
                    reason=reason
                )

        except Exception as e:
            logger.error("reject_lead_failed", business_id=business_id, error=str(e))
            print(f"❌ Error rejecting lead: {e}")
            sys.exit(1)

    async def get_stats(self):
        """Get review queue statistics."""
        try:
            async with self.db.get_connection() as db:
                # Count by status
                cursor = await db.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM leads
                    WHERE status IN ('review_required', 'qualified', 'disqualified')
                    GROUP BY status
                    """
                )
                status_counts = {row[0]: row[1] for row in await cursor.fetchall()}

                # Count reviewed leads
                cursor = await db.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM leads
                    WHERE reviewed_at IS NOT NULL
                    """
                )
                reviewed_count = (await cursor.fetchone())[0]

                # Get review reasons breakdown
                cursor = await db.execute(
                    """
                    SELECT review_reason, COUNT(*) as count
                    FROM leads
                    WHERE status = 'review_required'
                    GROUP BY review_reason
                    ORDER BY count DESC
                    LIMIT 10
                    """
                )
                reason_breakdown = await cursor.fetchall()

                # Get analyst activity
                cursor = await db.execute(
                    """
                    SELECT reviewed_by, COUNT(*) as count, review_decision
                    FROM leads
                    WHERE reviewed_by IS NOT NULL
                    GROUP BY reviewed_by, review_decision
                    ORDER BY count DESC
                    """
                )
                analyst_activity = await cursor.fetchall()

                # Print statistics
                print("\n📊 Review Queue Statistics\n")
                print("=" * 80)
                print("\nQueue Status:")
                print(f"  • Pending Review: {status_counts.get('review_required', 0)}")
                print(f"  • Approved (Qualified): {status_counts.get('qualified', 0)}")
                print(f"  • Rejected (Disqualified): {status_counts.get('disqualified', 0)}")
                print(f"  • Total Reviewed: {reviewed_count}")

                if reason_breakdown:
                    print("\nReview Reasons (Top 10):")
                    for reason, count in reason_breakdown:
                        print(f"  • {reason or 'Not specified'}: {count}")

                if analyst_activity:
                    print("\nAnalyst Activity:")
                    for analyst, count, decision in analyst_activity:
                        print(f"  • {analyst}: {count} {decision}")

                print("=" * 80 + "\n")

        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            print(f"❌ Error getting stats: {e}")
            sys.exit(1)


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Human-in-the-Loop Review Queue for Lead Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List all leads pending review')
    list_parser.add_argument('--limit', type=int, default=50, help='Maximum leads to display')

    # Approve command
    approve_parser = subparsers.add_parser('approve', help='Approve a lead')
    approve_parser.add_argument('business_id', type=int, help='Business ID to approve')
    approve_parser.add_argument('--reason', required=True, help='Reason for approval')
    approve_parser.add_argument('--analyst', default='analyst', help='Analyst name')

    # Reject command
    reject_parser = subparsers.add_parser('reject', help='Reject a lead')
    reject_parser.add_argument('business_id', type=int, help='Business ID to reject')
    reject_parser.add_argument('--reason', required=True, help='Reason for rejection')
    reject_parser.add_argument('--analyst', default='analyst', help='Analyst name')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show review queue statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize database
    from src.core.config import config as app_config
    # Create a simple config object that DatabaseManager expects
    class DBConfig:
        def __init__(self):
            self.path = app_config.DATABASE_PATH
            self.connection_timeout = app_config.DATABASE_TIMEOUT

    db_manager = DatabaseManager(DBConfig())
    await db_manager.initialize()

    # Create review queue
    queue = ReviewQueue(db_manager)

    # Execute command
    if args.command == 'list':
        await queue.list_pending_reviews(limit=args.limit)
    elif args.command == 'approve':
        await queue.approve_lead(args.business_id, args.reason, args.analyst)
    elif args.command == 'reject':
        await queue.reject_lead(args.business_id, args.reason, args.analyst)
    elif args.command == 'stats':
        await queue.get_stats()


if __name__ == '__main__':
    asyncio.run(main())
