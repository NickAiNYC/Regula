"""
Recovery & Reconciliation Tracker

Track recovered payments and calculate platform ROI (Recovery Yield).

Features:
- Match recovered payments to original claims
- Calculate recovery rate and ROI
- Track payment timing
- Generate recovery reports
- Client success metrics

Key Metric: "Regula Recovery Yield" = Total Recovered / Total Underpaid
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict
import structlog

logger = structlog.get_logger()


class RecoveryTracker:
    """
    Track and reconcile recovered payments

    Maintains:
    - Recovery status for each appeal
    - Payment matching logic
    - ROI calculations
    - Client success metrics

    Dashboard Metrics:
    - Total Recoverable: Sum of all underpayments
    - Total Recovered: Sum of successful appeals
    - Recovery Yield: Recovered / Recoverable (target: 85%+)
    - Average Days to Recovery: Time from appeal to payment
    - ROI: (Recovered - Costs) / Costs
    """

    def __init__(self):
        self.recoveries = []
        self.pending_appeals = []

    async def record_recovery(
        self,
        claim_id: str,
        original_underpayment: Decimal,
        recovered_amount: Decimal,
        payer: str,
        recovery_date: date,
        appeal_id: Optional[str] = None,
        method: str = "appeal",
    ) -> Dict:
        """
        Record a successful payment recovery

        Args:
            claim_id: Original claim identifier
            original_underpayment: Amount originally underpaid
            recovered_amount: Amount recovered
            payer: Payer who issued recovery
            recovery_date: Date payment received
            appeal_id: Appeal tracking ID
            method: Recovery method (appeal, negotiation, correction)

        Returns:
            Recovery record
        """
        recovery = {
            "recovery_id": f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "claim_id": claim_id,
            "appeal_id": appeal_id,
            "original_underpayment": float(original_underpayment),
            "recovered_amount": float(recovered_amount),
            "recovery_rate": (
                float((recovered_amount / original_underpayment) * 100)
                if original_underpayment > 0
                else 0
            ),
            "payer": payer,
            "recovery_date": recovery_date.isoformat(),
            "method": method,
            "status": "reconciled",
            "recorded_at": datetime.now().isoformat(),
        }

        self.recoveries.append(recovery)

        logger.info(
            "recovery_recorded",
            claim_id=claim_id,
            recovered_amount=float(recovered_amount),
            recovery_rate=recovery["recovery_rate"],
        )

        return recovery

    async def match_payment_to_appeal(
        self, payment_data: Dict, pending_appeals: List[Dict]
    ) -> Optional[Dict]:
        """
        Match incoming payment to an outstanding appeal

        Uses:
        - Claim ID matching
        - Amount matching (with tolerance)
        - Payer matching
        - Date proximity

        Args:
            payment_data: Incoming payment information
            pending_appeals: List of pending appeals

        Returns:
            Matched appeal or None
        """
        claim_id = payment_data.get("claim_id")
        amount = Decimal(str(payment_data.get("amount", 0)))
        payer = payment_data.get("payer")

        # Try exact claim ID match first
        for appeal in pending_appeals:
            if appeal.get("claim_id") == claim_id:
                # Verify amount is close (within 5%)
                expected = Decimal(str(appeal.get("expected_recovery", 0)))
                if expected > 0:
                    variance = abs(amount - expected) / expected
                    if variance < 0.05:  # Within 5%
                        logger.info(
                            "payment_matched", claim_id=claim_id, amount=float(amount)
                        )
                        return appeal

        # Try fuzzy matching by amount and payer
        for appeal in pending_appeals:
            if appeal.get("payer") == payer:
                expected = Decimal(str(appeal.get("expected_recovery", 0)))
                if expected > 0:
                    variance = abs(amount - expected) / expected
                    if variance < 0.02:  # Within 2% (stricter without claim ID)
                        logger.info(
                            "payment_fuzzy_matched",
                            appeal_id=appeal.get("appeal_id"),
                            amount=float(amount),
                        )
                        return appeal

        logger.warning("payment_unmatched", amount=float(amount), payer=payer)
        return None

    async def get_recovery_metrics(
        self,
        provider_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """
        Calculate recovery metrics for dashboard

        Args:
            provider_id: Filter by provider
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Dictionary with recovery metrics
        """
        # Filter recoveries by criteria
        filtered_recoveries = self.recoveries

        if start_date:
            filtered_recoveries = [
                r
                for r in filtered_recoveries
                if datetime.fromisoformat(r["recovery_date"]).date() >= start_date
            ]

        if end_date:
            filtered_recoveries = [
                r
                for r in filtered_recoveries
                if datetime.fromisoformat(r["recovery_date"]).date() <= end_date
            ]

        if not filtered_recoveries:
            return {
                "total_recoverable": 0,
                "total_recovered": 0,
                "recovery_yield": 0,
                "recovery_count": 0,
                "avg_recovery_amount": 0,
                "avg_recovery_rate": 0,
                "payer_breakdown": {},
            }

        # Calculate metrics
        total_underpaid = sum(
            Decimal(str(r["original_underpayment"])) for r in filtered_recoveries
        )
        total_recovered = sum(
            Decimal(str(r["recovered_amount"])) for r in filtered_recoveries
        )

        recovery_yield = (
            (total_recovered / total_underpaid * 100) if total_underpaid > 0 else 0
        )

        avg_recovery_amount = total_recovered / len(filtered_recoveries)
        avg_recovery_rate = sum(r["recovery_rate"] for r in filtered_recoveries) / len(
            filtered_recoveries
        )

        # Payer breakdown
        payer_stats = defaultdict(
            lambda: {"count": 0, "recovered": Decimal("0"), "underpaid": Decimal("0")}
        )
        for r in filtered_recoveries:
            payer = r["payer"]
            payer_stats[payer]["count"] += 1
            payer_stats[payer]["recovered"] += Decimal(str(r["recovered_amount"]))
            payer_stats[payer]["underpaid"] += Decimal(str(r["original_underpayment"]))

        payer_breakdown = {
            payer: {
                "count": stats["count"],
                "recovered": float(stats["recovered"]),
                "underpaid": float(stats["underpaid"]),
                "yield": float(
                    (stats["recovered"] / stats["underpaid"] * 100)
                    if stats["underpaid"] > 0
                    else 0
                ),
            }
            for payer, stats in payer_stats.items()
        }

        return {
            "total_recoverable": float(total_underpaid),
            "total_recovered": float(total_recovered),
            "recovery_yield": float(recovery_yield),
            "recovery_count": len(filtered_recoveries),
            "avg_recovery_amount": float(avg_recovery_amount),
            "avg_recovery_rate": float(avg_recovery_rate),
            "payer_breakdown": payer_breakdown,
            "period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        }

    async def calculate_roi(
        self,
        provider_id: str,
        platform_costs: Decimal,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict:
        """
        Calculate ROI for the platform

        ROI = (Total Recovered - Platform Costs - Appeal Costs) / (Platform Costs + Appeal Costs)

        Args:
            provider_id: Provider identifier
            platform_costs: Subscription or platform fees
            start_date: Start of date range
            end_date: End of date range

        Returns:
            ROI analysis
        """
        metrics = await self.get_recovery_metrics(provider_id, start_date, end_date)

        total_recovered = Decimal(str(metrics["total_recovered"]))

        # Estimate appeal costs (in production, track actual costs)
        appeal_cost_per_claim = Decimal("75.00")  # Average cost per appeal
        total_appeal_costs = appeal_cost_per_claim * metrics["recovery_count"]

        total_costs = platform_costs + total_appeal_costs

        net_recovery = total_recovered - total_costs
        roi_ratio = (net_recovery / total_costs) if total_costs > 0 else 0
        roi_percentage = roi_ratio * 100

        return {
            "provider_id": provider_id,
            "total_recovered": float(total_recovered),
            "platform_costs": float(platform_costs),
            "appeal_costs": float(total_appeal_costs),
            "total_costs": float(total_costs),
            "net_recovery": float(net_recovery),
            "roi_ratio": float(roi_ratio),
            "roi_percentage": float(roi_percentage),
            "recovery_count": metrics["recovery_count"],
            "avg_recovery_per_dollar_spent": (
                float(total_recovered / total_costs) if total_costs > 0 else 0
            ),
            "period": metrics["period"],
        }

    async def get_pending_appeals_summary(self) -> Dict:
        """
        Get summary of pending appeals (not yet recovered)

        Returns:
            Summary of outstanding appeals
        """
        if not self.pending_appeals:
            return {
                "pending_count": 0,
                "total_outstanding": 0,
                "avg_days_pending": 0,
                "by_payer": {},
            }

        total_outstanding = sum(
            Decimal(str(a.get("expected_recovery", 0))) for a in self.pending_appeals
        )

        # Calculate average days pending
        today = date.today()
        days_pending = []
        for appeal in self.pending_appeals:
            submitted = datetime.fromisoformat(appeal.get("submitted_at")).date()
            days = (today - submitted).days
            days_pending.append(days)

        avg_days = sum(days_pending) / len(days_pending) if days_pending else 0

        # Group by payer
        by_payer = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
        for appeal in self.pending_appeals:
            payer = appeal.get("payer", "Unknown")
            by_payer[payer]["count"] += 1
            by_payer[payer]["amount"] += Decimal(
                str(appeal.get("expected_recovery", 0))
            )

        payer_summary = {
            payer: {"count": stats["count"], "amount": float(stats["amount"])}
            for payer, stats in by_payer.items()
        }

        return {
            "pending_count": len(self.pending_appeals),
            "total_outstanding": float(total_outstanding),
            "avg_days_pending": round(avg_days, 1),
            "by_payer": payer_summary,
        }

    async def generate_recovery_report(
        self, provider_id: str, start_date: date, end_date: date
    ) -> Dict:
        """
        Generate comprehensive recovery report

        Returns:
            Full recovery analysis for reporting period
        """
        metrics = await self.get_recovery_metrics(provider_id, start_date, end_date)

        # Assume platform costs (in production, query from billing)
        platform_costs = Decimal("299.00")  # Monthly subscription
        roi = await self.calculate_roi(
            provider_id, platform_costs, start_date, end_date
        )

        pending = await self.get_pending_appeals_summary()

        return {
            "provider_id": provider_id,
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "recovery_metrics": metrics,
            "roi_analysis": roi,
            "pending_appeals": pending,
            "generated_at": datetime.now().isoformat(),
        }
