"""
CMS Medicare Adapter

Handles Medicare fee schedules, NCCI edits, and compliance rules
for the federal Medicare program.

Key Features:
- Medicare Physician Fee Schedule (MPFS) lookups
- Geographic Practice Cost Index (GPCI) adjustments
- NCCI (National Correct Coding Initiative) edit checks
- MUE (Medically Unlikely Edits) validation
- LCD/NCD (Local/National Coverage Determination) checks
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .base import BasePayerAdapter, PayerType, PayerAdapterError


class CMSMedicareAdapter(BasePayerAdapter):
    """
    CMS Medicare adapter for national Medicare coverage
    
    Medicare is the federal health insurance program for:
    - Adults 65 and older
    - Younger people with disabilities
    - People with End-Stage Renal Disease (ESRD)
    
    Fee Schedule: Medicare Physician Fee Schedule (MPFS)
    Updates: Annually, with quarterly adjustments
    """
    
    # Medicare Locality codes (sample - full implementation would use database)
    MEDICARE_LOCALITIES = {
        "manhattan": "00",
        "nyc": "00",
        "rest_of_ny": "01",
        "poughkeepsie": "02",
        "queens": "03",
    }
    
    def __init__(self):
        super().__init__(payer_name="CMS Medicare", payer_type=PayerType.MEDICARE)
        self.conversion_factor = Decimal("33.06")  # 2025 CF
    
    async def get_allowed_amount(
        self,
        cpt_code: str,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs
    ) -> Optional[Decimal]:
        """
        Calculate Medicare allowed amount using MPFS formula
        
        Formula: (Work RVU × Work GPCI) + (PE RVU × PE GPCI) + (MP RVU × MP GPCI) × CF
        
        Where:
        - RVU = Relative Value Unit
        - GPCI = Geographic Practice Cost Index
        - CF = Conversion Factor
        """
        # Get RVUs for CPT code (in production, query from MPFS database)
        rvus = await self._get_rvus(cpt_code, service_date)
        if not rvus:
            self.logger.warning("medicare_cpt_not_found", cpt_code=cpt_code)
            return None
        
        # Get GPCI values for locality
        locality_code = self._get_locality_code(geo_region)
        gpci = await self._get_gpci(locality_code, service_date)
        
        # Calculate allowed amount
        work_component = rvus["work_rvu"] * gpci["work_gpci"]
        pe_component = rvus["pe_rvu"] * gpci["pe_gpci"]
        mp_component = rvus["mp_rvu"] * gpci["mp_gpci"]
        
        total_rvu = work_component + pe_component + mp_component
        allowed_amount = total_rvu * self.conversion_factor
        
        # Apply modifier adjustments
        if modifiers:
            allowed_amount = self._apply_modifier_adjustments(allowed_amount, modifiers)
        
        return allowed_amount.quantize(Decimal("0.01"))
    
    async def detect_underpayment(
        self,
        cpt_code: str,
        paid_amount: Decimal,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """Detect Medicare underpayment"""
        allowed_amount = await self.get_allowed_amount(
            cpt_code, service_date, modifiers, geo_region
        )
        
        if allowed_amount is None:
            return {
                "is_violation": False,
                "allowed_amount": None,
                "paid_amount": paid_amount,
                "delta": None,
                "reason": "CPT code not found in Medicare fee schedule",
                "violation_codes": []
            }
        
        delta = allowed_amount - paid_amount
        is_violation = delta > Decimal("0.01")  # Tolerance for rounding
        
        violation_codes = []
        if is_violation:
            violation_codes.append("MEDICARE_UNDERPAYMENT")
        
        return {
            "is_violation": is_violation,
            "allowed_amount": allowed_amount,
            "paid_amount": paid_amount,
            "delta": delta,
            "reason": "Payment below Medicare allowed amount" if is_violation else None,
            "violation_codes": violation_codes
        }
    
    async def validate_claim(self, claim_data: Dict) -> Tuple[bool, List[str]]:
        """Validate claim against Medicare requirements"""
        errors = []
        
        # Required fields
        required_fields = ["cpt_code", "service_date", "diagnosis_codes"]
        for field in required_fields:
            if field not in claim_data or not claim_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Diagnosis code validation (ICD-10)
        if "diagnosis_codes" in claim_data:
            for dx in claim_data["diagnosis_codes"]:
                if not self._is_valid_icd10(dx):
                    errors.append(f"Invalid ICD-10 code: {dx}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    async def apply_edits(
        self,
        cpt_code: str,
        service_date: date,
        diagnosis_codes: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """
        Apply Medicare edits (NCCI, MUEs, LCD/NCD)
        """
        violations = []
        edits_applied = []
        
        # NCCI Edit Check (National Correct Coding Initiative)
        ncci_result = await self._check_ncci_edits(cpt_code, kwargs.get("other_cpt_codes", []))
        if not ncci_result["passed"]:
            violations.extend(ncci_result["violations"])
        edits_applied.append("NCCI")
        
        # MUE Check (Medically Unlikely Edits)
        units = kwargs.get("units", 1)
        mue_result = await self._check_mue(cpt_code, units, service_date)
        if not mue_result["passed"]:
            violations.append(mue_result["violation"])
        edits_applied.append("MUE")
        
        # LCD/NCD Check (Coverage Determination)
        if diagnosis_codes:
            lcd_result = await self._check_lcd(cpt_code, diagnosis_codes, service_date)
            if not lcd_result["passed"]:
                violations.append(lcd_result["violation"])
            edits_applied.append("LCD")
        
        passed = len(violations) == 0
        return {
            "passed": passed,
            "edits_applied": edits_applied,
            "violations": violations
        }
    
    def get_appeal_requirements(self) -> Dict:
        """Medicare appeal requirements"""
        return {
            "internal_deadline": 120,  # 120 days for redetermination
            "external_deadline": 180,  # 180 days for reconsideration
            "required_documents": [
                "Medicare Redetermination Request Form",
                "Medical records supporting medical necessity",
                "Provider statement explaining disagreement"
            ],
            "submission_method": "portal",  # Medicare Portal or mail
            "portal_url": "https://www.cms.gov/Medicare/Appeals-and-Grievances"
        }
    
    def get_regulatory_citations(self) -> List[Dict]:
        """Medicare regulatory citations"""
        return [
            {
                "citation": "42 CFR Part 414",
                "description": "Medicare Physician Fee Schedule",
                "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-414"
            },
            {
                "citation": "42 CFR Part 405",
                "description": "Medicare Appeals Process",
                "url": "https://www.ecfr.gov/current/title-42/chapter-IV/subchapter-B/part-405"
            },
            {
                "citation": "Social Security Act § 1848",
                "description": "Payment for Physicians' Services",
                "url": "https://www.ssa.gov/OP_Home/ssact/title18/1848.htm"
            }
        ]
    
    def supports_telehealth(self, cpt_code: str, service_date: date) -> bool:
        """Check if Medicare covers telehealth for this service"""
        # Post-COVID, Medicare expanded telehealth coverage
        # In production, query telehealth-eligible CPT database
        telehealth_codes = ["90791", "90832", "90834", "90837", "99201", "99202", "99203"]
        return cpt_code in telehealth_codes
    
    # Helper methods
    
    async def _get_rvus(self, cpt_code: str, service_date: date) -> Optional[Dict]:
        """Get RVUs from Medicare Physician Fee Schedule"""
        # In production, query MPFS database
        # This is sample data for behavioral health codes
        rvus_database = {
            "90791": {"work_rvu": Decimal("2.96"), "pe_rvu": Decimal("1.47"), "mp_rvu": Decimal("0.25")},
            "90832": {"work_rvu": Decimal("1.46"), "pe_rvu": Decimal("0.72"), "mp_rvu": Decimal("0.12")},
            "90834": {"work_rvu": Decimal("2.19"), "pe_rvu": Decimal("1.09"), "mp_rvu": Decimal("0.18")},
            "90837": {"work_rvu": Decimal("2.96"), "pe_rvu": Decimal("1.47"), "mp_rvu": Decimal("0.25")},
            "90853": {"work_rvu": Decimal("1.83"), "pe_rvu": Decimal("1.10"), "mp_rvu": Decimal("0.15")},
        }
        return rvus_database.get(cpt_code)
    
    async def _get_gpci(self, locality_code: str, service_date: date) -> Dict:
        """Get GPCI values for locality"""
        # In production, query GPCI database by locality and year
        # Sample data for NYC (locality 00)
        gpci_database = {
            "00": {"work_gpci": Decimal("1.094"), "pe_gpci": Decimal("1.264"), "mp_gpci": Decimal("0.879")},
            "01": {"work_gpci": Decimal("1.011"), "pe_gpci": Decimal("1.088"), "mp_gpci": Decimal("0.652")},
        }
        return gpci_database.get(locality_code, {
            "work_gpci": Decimal("1.000"),
            "pe_gpci": Decimal("1.000"),
            "mp_gpci": Decimal("1.000")
        })
    
    def _get_locality_code(self, geo_region: Optional[str]) -> str:
        """Map region to Medicare locality code"""
        if not geo_region:
            return "00"  # Default to NYC
        return self.MEDICARE_LOCALITIES.get(geo_region.lower(), "00")
    
    def _apply_modifier_adjustments(self, base_amount: Decimal, modifiers: List[str]) -> Decimal:
        """Apply modifier adjustments to allowed amount"""
        adjusted = base_amount
        
        # Common Medicare modifiers
        modifier_adjustments = {
            "26": Decimal("0.40"),  # Professional component only
            "TC": Decimal("0.60"),  # Technical component only
            "50": Decimal("1.50"),  # Bilateral procedure
            "59": Decimal("1.00"),  # Distinct procedural service
            "GT": Decimal("1.00"),  # Telehealth
            "95": Decimal("1.00"),  # Telehealth (new)
        }
        
        for modifier in modifiers:
            if modifier in modifier_adjustments:
                adjusted = base_amount * modifier_adjustments[modifier]
        
        return adjusted
    
    async def _check_ncci_edits(self, cpt_code: str, other_codes: List[str]) -> Dict:
        """Check NCCI edits for code combinations"""
        # In production, query NCCI edit tables
        # Sample implementation
        return {"passed": True, "violations": []}
    
    async def _check_mue(self, cpt_code: str, units: int, service_date: date) -> Dict:
        """Check Medically Unlikely Edits"""
        # In production, query MUE database
        # Sample MUE limits for behavioral health
        mue_limits = {
            "90791": 1,  # Initial eval - max 1 per day
            "90832": 3,
            "90834": 3,
            "90837": 2,
        }
        
        limit = mue_limits.get(cpt_code, 999)
        if units > limit:
            return {
                "passed": False,
                "violation": {
                    "code": "MUE_EXCEEDED",
                    "message": f"Units ({units}) exceed MUE limit ({limit}) for {cpt_code}"
                }
            }
        
        return {"passed": True}
    
    async def _check_lcd(
        self,
        cpt_code: str,
        diagnosis_codes: List[str],
        service_date: date
    ) -> Dict:
        """Check Local Coverage Determination"""
        # In production, query LCD database
        # Sample implementation - behavioral health is generally covered
        return {"passed": True}
    
    def _is_valid_icd10(self, code: str) -> bool:
        """Validate ICD-10 code format"""
        # Basic validation - in production, query ICD-10 database
        import re
        pattern = r'^[A-Z][0-9]{2}\.?[0-9A-Z]{0,4}$'
        return bool(re.match(pattern, code.upper()))
