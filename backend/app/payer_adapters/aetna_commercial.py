"""
Aetna Commercial Adapter

Handles Aetna commercial insurance plans with negotiated rates
and proprietary claim edits.

Key Features:
- Provider contract rate lookups
- Commercial plan variations (PPO, HMO, EPO)
- Negotiated fee schedules
- Prior authorization checking
- Network status validation
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .base import BasePayerAdapter, PayerType


class AetnaCommercialAdapter(BasePayerAdapter):
    """
    Aetna Commercial Insurance adapter
    
    Aetna is one of the largest commercial health insurers in the US.
    Commercial plans have negotiated rates that vary by:
    - Provider contracts
    - Plan type (PPO vs HMO)
    - Network tier (in-network vs out-of-network)
    - Geographic region
    
    Unlike Medicare/Medicaid, commercial rates are contract-based,
    not publicly available fee schedules.
    """
    
    # Sample rate multipliers (actual rates are contract-specific)
    RATE_MULTIPLIERS = {
        "ppo_in_network": Decimal("0.85"),      # 85% of billed charges
        "ppo_out_network": Decimal("0.60"),     # 60% of billed charges
        "hmo_in_network": Decimal("0.90"),      # 90% of billed charges
        "hmo_out_network": Decimal("0.00"),     # Not covered
    }
    
    def __init__(self):
        super().__init__(payer_name="Aetna", payer_type=PayerType.COMMERCIAL)
    
    async def get_allowed_amount(
        self,
        cpt_code: str,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs
    ) -> Optional[Decimal]:
        """
        Calculate Aetna allowed amount
        
        Commercial payers use negotiated rates, not fee schedules.
        In production, this would query:
        1. Provider contract database
        2. Plan-specific fee schedule
        3. Network status
        """
        # Extract plan-specific parameters
        plan_type = kwargs.get("plan_type", "ppo_in_network")
        billed_charges = kwargs.get("billed_charges")
        provider_contract_rate = kwargs.get("contract_rate")
        
        # If provider has specific contract rate, use it
        if provider_contract_rate:
            return Decimal(str(provider_contract_rate)).quantize(Decimal("0.01"))
        
        # Otherwise, estimate based on plan type and billed charges
        if billed_charges:
            multiplier = self.RATE_MULTIPLIERS.get(plan_type, Decimal("0.80"))
            allowed = Decimal(str(billed_charges)) * multiplier
            return allowed.quantize(Decimal("0.01"))
        
        # Fallback to standard commercial rates (% of Medicare)
        medicare_equivalent = await self._estimate_medicare_rate(cpt_code, service_date)
        if medicare_equivalent:
            # Commercial typically pays 110-130% of Medicare
            commercial_rate = medicare_equivalent * Decimal("1.20")
            return commercial_rate.quantize(Decimal("0.01"))
        
        self.logger.warning("aetna_rate_not_determined", cpt_code=cpt_code)
        return None
    
    async def detect_underpayment(
        self,
        cpt_code: str,
        paid_amount: Decimal,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """Detect Aetna underpayment"""
        allowed_amount = await self.get_allowed_amount(
            cpt_code, service_date, modifiers, geo_region, **kwargs
        )
        
        if allowed_amount is None:
            return {
                "is_violation": False,
                "allowed_amount": None,
                "paid_amount": paid_amount,
                "delta": None,
                "reason": "Unable to determine Aetna allowed amount (contract rate needed)",
                "violation_codes": []
            }
        
        delta = allowed_amount - paid_amount
        is_violation = delta > Decimal("0.01")
        
        violation_codes = []
        if is_violation:
            violation_codes.append("COMMERCIAL_UNDERPAYMENT")
            
            # Check if this violates parity (if behavioral health in NY)
            if kwargs.get("is_behavioral_health") and kwargs.get("state") == "NY":
                violation_codes.append("NY_PARITY_VIOLATION")
        
        return {
            "is_violation": is_violation,
            "allowed_amount": allowed_amount,
            "paid_amount": paid_amount,
            "delta": delta,
            "reason": "Payment below contracted allowed amount" if is_violation else None,
            "violation_codes": violation_codes,
            "plan_type": kwargs.get("plan_type", "unknown")
        }
    
    async def validate_claim(self, claim_data: Dict) -> Tuple[bool, List[str]]:
        """Validate claim against Aetna requirements"""
        errors = []
        
        required_fields = ["cpt_code", "service_date", "member_id"]
        for field in required_fields:
            if field not in claim_data or not claim_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Check network status
        if "network_status" in claim_data:
            if claim_data["network_status"] not in ["in_network", "out_network"]:
                errors.append("Invalid network status")
        
        # Check prior authorization for certain services
        if self._requires_prior_auth(claim_data.get("cpt_code")):
            if not claim_data.get("prior_auth_number"):
                errors.append("Prior authorization required but not provided")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    async def apply_edits(
        self,
        cpt_code: str,
        service_date: date,
        diagnosis_codes: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """Apply Aetna-specific claim edits"""
        violations = []
        edits_applied = ["AETNA_COMMERCIAL_BASIC"]
        
        # Prior authorization check
        if self._requires_prior_auth(cpt_code) and not kwargs.get("prior_auth_number"):
            violations.append({
                "code": "PRIOR_AUTH_REQUIRED",
                "message": f"CPT {cpt_code} requires prior authorization"
            })
            edits_applied.append("PRIOR_AUTH_CHECK")
        
        # Network adequacy check
        network_status = kwargs.get("network_status", "in_network")
        plan_type = kwargs.get("plan_type", "ppo")
        if plan_type == "hmo" and network_status == "out_network":
            violations.append({
                "code": "OUT_OF_NETWORK_HMO",
                "message": "HMO plan does not cover out-of-network services"
            })
            edits_applied.append("NETWORK_CHECK")
        
        # Medical necessity (basic check)
        if diagnosis_codes and not self._supports_medical_necessity(cpt_code, diagnosis_codes):
            violations.append({
                "code": "MEDICAL_NECESSITY",
                "message": "Diagnosis codes do not support medical necessity"
            })
            edits_applied.append("MEDICAL_NECESSITY_CHECK")
        
        passed = len(violations) == 0
        return {
            "passed": passed,
            "edits_applied": edits_applied,
            "violations": violations
        }
    
    def get_appeal_requirements(self) -> Dict:
        """Aetna appeal requirements"""
        return {
            "internal_deadline": 180,  # 180 days for internal appeal
            "external_deadline": 60,   # 60 days for external review
            "required_documents": [
                "Aetna Appeal Form",
                "Explanation of Benefits (EOB)",
                "Medical records",
                "Provider letter of medical necessity"
            ],
            "submission_method": "portal",  # Aetna Provider Portal or fax
            "portal_url": "https://www.aetna.com/healthcare-professionals/appeals.html"
        }
    
    def get_regulatory_citations(self) -> List[Dict]:
        """Aetna regulatory citations (ERISA, ACA, state mandates)"""
        return [
            {
                "citation": "ERISA § 503",
                "description": "Claims Procedure Regulations",
                "url": "https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/erisa"
            },
            {
                "citation": "ACA § 1557",
                "description": "Nondiscrimination in Health Programs",
                "url": "https://www.hhs.gov/civil-rights/for-individuals/section-1557/index.html"
            },
            {
                "citation": "Mental Health Parity Act",
                "description": "Equal Coverage for Mental Health Services",
                "url": "https://www.cms.gov/cciio/programs-and-initiatives/other-insurance-protections/mhpaea_factsheet"
            }
        ]
    
    def supports_telehealth(self, cpt_code: str, service_date: date) -> bool:
        """Aetna expanded telehealth coverage"""
        # Aetna covers telehealth for most behavioral health services
        telehealth_eligible = [
            "90791", "90792", "90832", "90834", "90837",
            "90839", "90840", "90846", "90847", "90853",
            "99201", "99202", "99203", "99204", "99205"
        ]
        return cpt_code in telehealth_eligible
    
    # Helper methods
    
    async def _estimate_medicare_rate(self, cpt_code: str, service_date: date) -> Optional[Decimal]:
        """Estimate Medicare equivalent rate (commercial is typically 110-130% of Medicare)"""
        # Sample Medicare rates for behavioral health
        medicare_rates = {
            "90791": Decimal("157.29"),
            "90792": Decimal("187.29"),
            "90832": Decimal("78.65"),
            "90834": Decimal("117.98"),
            "90837": Decimal("157.31"),
            "90853": Decimal("94.38"),
        }
        return medicare_rates.get(cpt_code)
    
    def _requires_prior_auth(self, cpt_code: Optional[str]) -> bool:
        """Check if CPT code requires prior authorization"""
        if not cpt_code:
            return False
        
        # Services typically requiring prior auth
        prior_auth_codes = [
            "90792",  # Psychiatric eval with medical services
            "90839",  # Psychotherapy for crisis
            "96110",  # Developmental screening
            "97151",  # Adaptive behavior assessment
        ]
        return cpt_code in prior_auth_codes
    
    def _supports_medical_necessity(
        self,
        cpt_code: str,
        diagnosis_codes: List[str]
    ) -> bool:
        """Basic medical necessity check"""
        # In production, this would query LCD/medical policy database
        # For now, assume behavioral health codes are covered
        return cpt_code.startswith("90") or cpt_code.startswith("96")
