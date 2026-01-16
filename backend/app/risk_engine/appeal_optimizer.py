"""
Appeal Success Optimizer

ML-powered analysis of historical appeal outcomes to:
- Predict likelihood of appeal success
- Recommend optimal appeal strategies
- Prioritize high-value appeals
- Generate compelling clinical narratives

Features:
- Success probability scoring
- Strategy recommendation engine
- ROI calculation (appeal cost vs expected recovery)
- LLM-powered narrative generation
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import structlog

logger = structlog.get_logger()


class AppealSuccessOptimizer:
    """
    Optimize appeal strategy using historical outcome data
    
    Analyzes patterns:
    - Payer-specific success rates
    - Reason code effectiveness
    - Adjuster/reviewer patterns
    - Documentation quality factors
    - Appeal timing (days since denial)
    
    Output:
    - Success probability (0-100%)
    - Recommended strategy
    - Expected ROI
    - Priority score
    """
    
    # Success rate thresholds
    HIGH_SUCCESS_THRESHOLD = 70.0  # 70%+
    MEDIUM_SUCCESS_THRESHOLD = 40.0  # 40-70%
    
    def __init__(self):
        self.historical_data = {}
        self.payer_success_rates = {}
    
    async def analyze_appeal_opportunity(
        self,
        claim_data: Dict,
        violation_data: Dict,
        provider_context: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze appeal opportunity and recommend strategy
        
        Args:
            claim_data: Original claim information
            violation_data: Detected violation details
            provider_context: Provider-specific historical data
            
        Returns:
            Dictionary with:
            - should_appeal: bool
            - success_probability: float (0-100)
            - expected_recovery: Decimal
            - appeal_cost_estimate: Decimal
            - roi_ratio: float
            - priority_score: int (1-10)
            - recommended_strategy: str
            - required_documents: List[str]
            - narrative_template: str
        """
        payer = claim_data.get("payer", "")
        underpayment_amount = violation_data.get("delta", Decimal("0"))
        
        # 1. Calculate success probability
        success_probability = await self._calculate_success_probability(
            claim_data, violation_data, provider_context
        )
        
        # 2. Estimate appeal costs
        appeal_cost = self._estimate_appeal_cost(claim_data, success_probability)
        
        # 3. Calculate expected value and ROI
        expected_recovery = underpayment_amount * (Decimal(str(success_probability)) / Decimal("100"))
        roi_ratio = float(expected_recovery / appeal_cost) if appeal_cost > 0 else 0.0
        
        # 4. Determine if appeal is worthwhile
        should_appeal = self._should_pursue_appeal(
            success_probability, roi_ratio, underpayment_amount
        )
        
        # 5. Calculate priority score
        priority_score = self._calculate_priority_score(
            success_probability, underpayment_amount, roi_ratio
        )
        
        # 6. Recommend strategy
        strategy = self._recommend_strategy(
            success_probability, claim_data, violation_data
        )
        
        # 7. Identify required documents
        required_docs = self._get_required_documents(claim_data, violation_data)
        
        # 8. Generate narrative template
        narrative = self._generate_appeal_narrative(
            claim_data, violation_data, strategy
        )
        
        result = {
            "should_appeal": should_appeal,
            "success_probability": round(success_probability, 1),
            "expected_recovery": float(expected_recovery),
            "appeal_cost_estimate": float(appeal_cost),
            "roi_ratio": round(roi_ratio, 2),
            "priority_score": priority_score,
            "recommended_strategy": strategy,
            "required_documents": required_docs,
            "narrative_template": narrative,
            "analysis_date": datetime.now().isoformat()
        }
        
        logger.info(
            "appeal_analysis_complete",
            claim_id=claim_data.get("claim_id"),
            should_appeal=should_appeal,
            success_probability=success_probability,
            priority=priority_score
        )
        
        return result
    
    async def prioritize_appeals(
        self,
        pending_violations: List[Dict]
    ) -> List[Dict]:
        """
        Prioritize multiple appeals by expected value and success probability
        
        Args:
            pending_violations: List of violation dictionaries
            
        Returns:
            Sorted list with priority scores and recommendations
        """
        analyzed = []
        
        for violation in pending_violations:
            analysis = await self.analyze_appeal_opportunity(
                claim_data=violation.get("claim", {}),
                violation_data=violation
            )
            
            analyzed.append({
                "claim_id": violation.get("claim", {}).get("claim_id"),
                "underpayment": violation.get("delta"),
                **analysis
            })
        
        # Sort by priority score (descending)
        analyzed.sort(key=lambda x: x["priority_score"], reverse=True)
        
        logger.info("appeals_prioritized", total=len(analyzed))
        return analyzed
    
    async def _calculate_success_probability(
        self,
        claim_data: Dict,
        violation_data: Dict,
        provider_context: Optional[Dict]
    ) -> float:
        """
        Calculate probability of appeal success
        
        Factors:
        1. Payer-specific success rates (40% weight)
        2. Violation type/magnitude (30% weight)
        3. Documentation quality (20% weight)
        4. Timing factors (10% weight)
        """
        # Base probability (start at 50%)
        probability = 50.0
        
        # Factor 1: Payer history (40% weight)
        payer = claim_data.get("payer", "")
        payer_success_rate = self.payer_success_rates.get(payer, 0.50)
        probability += (payer_success_rate - 0.50) * 40
        
        # Factor 2: Violation characteristics (30% weight)
        violation_codes = violation_data.get("violation_codes", [])
        
        # Clear regulatory violations have higher success rates
        if "NY_PARITY_VIOLATION" in violation_codes:
            probability += 15  # Strong legal basis
        elif "MEDICARE_UNDERPAYMENT" in violation_codes:
            probability += 10  # Clear fee schedule
        
        # Larger underpayments get more scrutiny (both ways)
        delta = float(violation_data.get("delta", 0))
        if delta > 100:
            probability += 5  # Worth payer's time to review
        elif delta > 500:
            probability -= 5  # May trigger extra scrutiny
        
        # Factor 3: Documentation quality (20% weight)
        if claim_data.get("has_medical_records"):
            probability += 10
        if claim_data.get("has_prior_auth"):
            probability += 5
        
        # Factor 4: Timing (10% weight)
        days_since_payment = claim_data.get("days_since_payment", 30)
        if days_since_payment < 60:
            probability += 5  # Fresh claims easier to appeal
        elif days_since_payment > 180:
            probability -= 10  # Stale claims harder
        
        # Cap at realistic bounds
        probability = max(10.0, min(95.0, probability))
        
        return probability
    
    def _estimate_appeal_cost(
        self,
        claim_data: Dict,
        success_probability: float
    ) -> Decimal:
        """
        Estimate cost of pursuing appeal
        
        Costs include:
        - Staff time (review, writing, submission)
        - Document gathering/copying
        - Postage/fax
        - Follow-up calls
        """
        base_cost = Decimal("50.00")  # Minimum (internal appeal)
        
        # More complex appeals cost more
        if claim_data.get("requires_peer_review"):
            base_cost += Decimal("150.00")
        
        if success_probability < 40:
            base_cost += Decimal("50.00")  # Extra effort for difficult cases
        
        # External appeals are more expensive
        if claim_data.get("appeal_level") == "external":
            base_cost += Decimal("200.00")
        
        return base_cost
    
    def _should_pursue_appeal(
        self,
        success_probability: float,
        roi_ratio: float,
        underpayment_amount: Decimal
    ) -> bool:
        """
        Decide if appeal is worth pursuing
        
        Criteria:
        1. ROI > 2.0 (expect to recover 2x cost)
        2. OR underpayment > $500 (high dollar value)
        3. OR success probability > 80% (very likely to win)
        4. AND success probability > 20% (minimum threshold)
        """
        # Minimum success threshold
        if success_probability < 20:
            return False
        
        # High-value claims always appeal
        if underpayment_amount > Decimal("500"):
            return True
        
        # High success rate always appeal
        if success_probability > 80:
            return True
        
        # Good ROI
        if roi_ratio > 2.0:
            return True
        
        return False
    
    def _calculate_priority_score(
        self,
        success_probability: float,
        underpayment_amount: Decimal,
        roi_ratio: float
    ) -> int:
        """
        Calculate priority score (1-10, higher = more urgent)
        
        Formula: Weighted combination of success probability, amount, and ROI
        """
        score = 0.0
        
        # Success probability (0-4 points)
        score += (success_probability / 100.0) * 4.0
        
        # Underpayment amount (0-3 points)
        if underpayment_amount > Decimal("1000"):
            score += 3.0
        elif underpayment_amount > Decimal("500"):
            score += 2.0
        elif underpayment_amount > Decimal("250"):
            score += 1.0
        
        # ROI ratio (0-3 points)
        if roi_ratio > 5.0:
            score += 3.0
        elif roi_ratio > 3.0:
            score += 2.0
        elif roi_ratio > 2.0:
            score += 1.0
        
        # Convert to 1-10 scale
        priority = int(round(score))
        return max(1, min(10, priority))
    
    def _recommend_strategy(
        self,
        success_probability: float,
        claim_data: Dict,
        violation_data: Dict
    ) -> str:
        """
        Recommend optimal appeal strategy
        """
        violation_codes = violation_data.get("violation_codes", [])
        
        # Regulatory violations: Cite law
        if "NY_PARITY_VIOLATION" in violation_codes:
            return (
                "REGULATORY_CITATION: File formal DFS complaint citing "
                "L.2024 c.57, Part AA (2025 Medicaid Parity Mandate). "
                "Include rate calculation worksheet and statutory references."
            )
        
        # Medicare: Reference fee schedule
        if "MEDICARE_UNDERPAYMENT" in violation_codes:
            return (
                "FEE_SCHEDULE_REFERENCE: File redetermination request with "
                "Medicare Physician Fee Schedule documentation. Include locality "
                "code and RVU calculations."
            )
        
        # High probability: Standard appeal
        if success_probability > self.HIGH_SUCCESS_THRESHOLD:
            return (
                "STANDARD_APPEAL: File internal appeal with medical records and "
                "clear explanation of underpayment. High likelihood of success."
            )
        
        # Medium probability: Enhanced documentation
        if success_probability > self.MEDIUM_SUCCESS_THRESHOLD:
            return (
                "ENHANCED_DOCUMENTATION: Gather comprehensive medical records, "
                "peer review letter, and clinical guidelines supporting medical "
                "necessity. May require multiple rounds."
            )
        
        # Low probability: Consider negotiation
        return (
            "NEGOTIATION: Consider direct payer contact for informal resolution "
            "before formal appeal. Success probability is lower; may not be cost-effective."
        )
    
    def _get_required_documents(
        self,
        claim_data: Dict,
        violation_data: Dict
    ) -> List[str]:
        """
        Identify documents needed for appeal
        """
        docs = [
            "Original claim submission",
            "Explanation of Benefits (EOB) or ERA",
            "Rate calculation worksheet"
        ]
        
        # Add violation-specific documents
        violation_codes = violation_data.get("violation_codes", [])
        
        if "NY_PARITY_VIOLATION" in violation_codes:
            docs.extend([
                "NY DFS Complaint Form",
                "L.2024 c.57, Part AA statutory citation",
                "NY Medicaid rate schedule documentation"
            ])
        
        if "MEDICARE_UNDERPAYMENT" in violation_codes:
            docs.extend([
                "Medicare Redetermination Request Form",
                "Medicare Physician Fee Schedule documentation",
                "Locality code verification"
            ])
        
        # Medical necessity documents
        if claim_data.get("diagnosis_codes"):
            docs.extend([
                "Medical records supporting diagnosis",
                "Treatment plan documentation",
                "Progress notes for service date"
            ])
        
        return docs
    
    def _generate_appeal_narrative(
        self,
        claim_data: Dict,
        violation_data: Dict,
        strategy: str
    ) -> str:
        """
        Generate appeal letter narrative template
        
        In production, this would use LLM (GPT-4, Claude) to generate
        personalized, compelling narratives.
        """
        cpt_code = claim_data.get("cpt_code", "")
        dos = claim_data.get("service_date", "")
        payer = claim_data.get("payer", "")
        allowed_amount = violation_data.get("allowed_amount", 0)
        paid_amount = violation_data.get("paid_amount", 0)
        delta = violation_data.get("delta", 0)
        
        narrative = f"""
APPEAL REQUEST - UNDERPAYMENT

RE: Claim #{claim_data.get('claim_id', 'N/A')}
Service Date: {dos}
CPT Code: {cpt_code}
Provider: {claim_data.get('provider_name', '[Provider Name]')}

Dear {payer} Appeals Department,

I am writing to appeal the underpayment of the above-referenced claim. The service was 
provided on {dos} and properly coded as CPT {cpt_code}.

ISSUE:
Your organization reimbursed ${paid_amount:.2f} for this service. However, the applicable 
rate for this service is ${allowed_amount:.2f}, resulting in an underpayment of ${delta:.2f}.

SUPPORTING DOCUMENTATION:
- Original claim submission
- Explanation of Benefits showing payment of ${paid_amount:.2f}
- Rate documentation showing correct payment of ${allowed_amount:.2f}
- Medical records supporting medical necessity

REQUESTED ACTION:
Please process an additional payment of ${delta:.2f} to properly reimburse this claim 
according to the applicable fee schedule.

We appreciate your prompt attention to this matter. Please contact us if you require 
additional information.

Sincerely,
[Provider Name]
[Contact Information]
"""
        
        return narrative.strip()
