"""
NY Medicaid Adapter

Refactored adapter for NY State Medicaid with parity mandate compliance.
Leverages existing rate_engine.py logic while conforming to BasePayerAdapter interface.

Key Features:
- 2025 Medicaid Parity Mandate (L.2024 c.57, Part AA)
- Geographic adjustments (NYC 1.065x, Long Island 1.025x, Upstate 1.0x)
- COLA tracking (2025: 2.84% increase)
- Behavioral health focus
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .base import BasePayerAdapter, PayerType


class NYMedicaidAdapter(BasePayerAdapter):
    """
    New York State Medicaid adapter

    Implements the 2025 Medicaid Parity Mandate requiring insurance carriers
    to reimburse behavioral health services at the same rate as Medicaid.

    Regulatory Foundation:
    - L.2024 c.57, Part AA (2025 Parity Mandate)
    - NY Mental Hygiene Law § 13.09
    - 10 NYCRR § 86-4.18
    """

    # Geographic multipliers (inherited from existing rate_engine.py)
    GEO_MULTIPLIERS = {
        "nyc": Decimal("1.065"),
        "longisland": Decimal("1.025"),
        "upstate": Decimal("1.000"),
    }

    # COLA adjustments
    COLA_ADJUSTMENTS = {
        2024: Decimal("1.000"),
        2025: Decimal("1.0284"),  # 2.84% increase
        2026: Decimal("1.0284"),  # TBD
    }

    def __init__(self):
        super().__init__(payer_name="NY Medicaid", payer_type=PayerType.MEDICAID)

    async def get_allowed_amount(
        self,
        cpt_code: str,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs,
    ) -> Optional[Decimal]:
        """
        Calculate NY Medicaid allowed amount (mandate rate)

        Formula: Base Rate (2024) × COLA (2025+) × Geographic Adjustment
        """
        # Get base rate (in production, query rate database)
        base_rate = await self._get_base_rate(cpt_code, service_date)
        if not base_rate:
            self.logger.warning("ny_medicaid_rate_not_found", cpt_code=cpt_code)
            return None

        # Apply COLA adjustment
        cola_factor = self._get_cola_factor(service_date)
        rate_with_cola = base_rate * cola_factor

        # Apply geographic adjustment
        geo_factor = self.get_geographic_adjustment_factor(
            geo_region or "upstate", service_date
        )
        final_rate = rate_with_cola * geo_factor

        return final_rate.quantize(Decimal("0.01"))

    async def detect_underpayment(
        self,
        cpt_code: str,
        paid_amount: Decimal,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """Detect NY Medicaid parity violations"""
        allowed_amount = await self.get_allowed_amount(
            cpt_code, service_date, modifiers, geo_region
        )

        if allowed_amount is None:
            return {
                "is_violation": False,
                "allowed_amount": None,
                "paid_amount": paid_amount,
                "delta": None,
                "reason": "CPT code not found in NY Medicaid rate database",
                "violation_codes": [],
            }

        delta = allowed_amount - paid_amount
        is_violation = delta > Decimal("0.01")  # Tolerance for rounding

        violation_codes = []
        if is_violation:
            violation_codes.append("NY_PARITY_VIOLATION")

        return {
            "is_violation": is_violation,
            "allowed_amount": allowed_amount,
            "paid_amount": paid_amount,
            "delta": delta,
            "reason": (
                "Payment below NY Medicaid parity mandate rate"
                if is_violation
                else None
            ),
            "violation_codes": violation_codes,
            "geo_adjustment_factor": self.get_geographic_adjustment_factor(
                geo_region or "upstate", service_date
            ),
        }

    async def validate_claim(self, claim_data: Dict) -> Tuple[bool, List[str]]:
        """Validate claim against NY Medicaid requirements"""
        errors = []

        required_fields = ["cpt_code", "service_date", "payer"]
        for field in required_fields:
            if field not in claim_data or not claim_data[field]:
                errors.append(f"Missing required field: {field}")

        # NY Medicaid specific validation
        if "geo_region" in claim_data:
            region = claim_data["geo_region"].lower()
            if region not in self.GEO_MULTIPLIERS:
                errors.append(f"Invalid geographic region: {region}")

        is_valid = len(errors) == 0
        return is_valid, errors

    async def apply_edits(
        self,
        cpt_code: str,
        service_date: date,
        diagnosis_codes: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict:
        """
        Apply NY Medicaid edits

        NY Medicaid has fewer edit restrictions than Medicare for behavioral health
        """
        violations = []
        edits_applied = ["NY_MEDICAID_BASIC"]

        # Check service is covered under behavioral health
        if not self._is_behavioral_health_service(cpt_code):
            violations.append(
                {
                    "code": "NOT_BEHAVIORAL_HEALTH",
                    "message": f"CPT {cpt_code} is not a covered behavioral health service",
                }
            )

        passed = len(violations) == 0
        return {
            "passed": passed,
            "edits_applied": edits_applied,
            "violations": violations,
        }

    def get_appeal_requirements(self) -> Dict:
        """NY Medicaid appeal requirements"""
        return {
            "internal_deadline": 60,  # 60 days for internal appeal
            "external_deadline": 45,  # 45 days for external appeal
            "required_documents": [
                "NY DFS Complaint Form",
                "Explanation of Benefits (EOB)",
                "Provider statement with regulatory citations",
                "Rate calculation worksheet",
            ],
            "submission_method": "portal",  # NY DFS Consumer Portal or mail
            "portal_url": "https://www.dfs.ny.gov/complaint",
        }

    def get_regulatory_citations(self) -> List[Dict]:
        """NY Medicaid parity regulatory citations"""
        return [
            {
                "citation": "L.2024 c.57, Part AA",
                "description": "2025 Medicaid Parity Mandate for Behavioral Health",
                "url": "https://legislation.nysenate.gov/pdf/bills/2023/S8300",
            },
            {
                "citation": "NY Mental Hygiene Law § 13.09",
                "description": "Rate Setting for Mental Health Services",
                "url": "https://www.nysenate.gov/legislation/laws/MHY/13.09",
            },
            {
                "citation": "10 NYCRR § 86-4.18",
                "description": "Behavioral Health Reimbursement Standards",
                "url": "https://regs.health.ny.gov/content/section-86-418-clinic-rates",
            },
            {
                "citation": "NY Insurance Law § 3224-a",
                "description": "External Appeal Process",
                "url": "https://www.nysenate.gov/legislation/laws/ISC/3224-A",
            },
        ]

    def supports_telehealth(self, cpt_code: str, service_date: date) -> bool:
        """NY Medicaid has expanded telehealth coverage for behavioral health"""
        # Post-COVID, NY expanded telehealth permanently
        behavioral_health_codes = [
            "90791",
            "90792",
            "90832",
            "90834",
            "90837",
            "90839",
            "90840",
            "90845",
            "90846",
            "90847",
            "90849",
            "90853",
        ]
        return cpt_code in behavioral_health_codes

    def get_geographic_adjustment_factor(
        self, geo_region: str, service_date: date
    ) -> Decimal:
        """Get NY Medicaid geographic adjustment"""
        return self.GEO_MULTIPLIERS.get(geo_region.lower(), Decimal("1.000"))

    # Helper methods

    async def _get_base_rate(
        self, cpt_code: str, service_date: date
    ) -> Optional[Decimal]:
        """
        Get base rate from NY Medicaid rate database
        In production, this queries the rate_database table
        """
        # Sample behavioral health rates (2024 base)
        rates_database = {
            "90791": Decimal("157.29"),  # Psychiatric diagnostic eval
            "90792": Decimal(
                "187.29"
            ),  # Psychiatric diagnostic eval with medical services
            "90832": Decimal("78.65"),  # Psychotherapy, 30 min
            "90834": Decimal("117.98"),  # Psychotherapy, 45 min
            "90837": Decimal("157.31"),  # Psychotherapy, 60 min
            "90839": Decimal("117.98"),  # Psychotherapy for crisis, first 60 min
            "90840": Decimal(
                "59.00"
            ),  # Psychotherapy for crisis, each additional 30 min
            "90845": Decimal("78.65"),  # Psychoanalysis
            "90846": Decimal("94.38"),  # Family psychotherapy without patient
            "90847": Decimal("110.11"),  # Family psychotherapy with patient
            "90849": Decimal("78.65"),  # Multiple family group psychotherapy
            "90853": Decimal("94.38"),  # Group psychotherapy
        }

        base_rate = rates_database.get(cpt_code)

        # Apply COLA if 2025+
        if base_rate and service_date.year >= 2025:
            cola_factor = self._get_cola_factor(service_date)
            return base_rate * cola_factor

        return base_rate

    def _get_cola_factor(self, service_date: date) -> Decimal:
        """Get COLA adjustment factor for year"""
        return self.COLA_ADJUSTMENTS.get(service_date.year, Decimal("1.000"))

    def _is_behavioral_health_service(self, cpt_code: str) -> bool:
        """Check if CPT code is a behavioral health service"""
        # Behavioral health CPT codes typically start with 90xxx or 96xxx
        return cpt_code.startswith("90") or cpt_code.startswith("96")
