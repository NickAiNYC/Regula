"""
Base Payer Adapter - Abstract interface for multi-payer support
"""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from enum import Enum
import structlog

logger = structlog.get_logger()


class PayerType(Enum):
    """Payer classification"""

    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    COMMERCIAL = "commercial"
    MEDICAID_MANAGED = "medicaid_managed"
    MEDICARE_ADVANTAGE = "medicare_advantage"


class PayerAdapterError(Exception):
    """Base exception for payer adapter errors"""

    pass


class BasePayerAdapter(ABC):
    """
    Abstract base class for all payer adapters

    Each payer (Medicare, Medicaid, Commercial) has unique:
    - Rate structures & fee schedules
    - Geographic adjustments
    - Rules (NCCI edits, MUEs, bundling)
    - Compliance requirements
    - Remittance formats

    Adapters standardize these differences into a common interface.
    """

    def __init__(self, payer_name: str, payer_type: PayerType):
        self.payer_name = payer_name
        self.payer_type = payer_type
        self.logger = logger.bind(payer=payer_name, payer_type=payer_type.value)

    @abstractmethod
    async def get_allowed_amount(
        self,
        cpt_code: str,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs,
    ) -> Optional[Decimal]:
        """
        Calculate the allowed/expected payment amount for a service

        Args:
            cpt_code: CPT procedure code
            service_date: Date of service
            modifiers: CPT modifiers (e.g., ['GT', '59'])
            geo_region: Geographic region/locality
            **kwargs: Additional payer-specific parameters

        Returns:
            Allowed amount or None if not covered
        """
        pass

    @abstractmethod
    async def detect_underpayment(
        self,
        cpt_code: str,
        paid_amount: Decimal,
        service_date: date,
        modifiers: Optional[List[str]] = None,
        geo_region: Optional[str] = None,
        **kwargs,
    ) -> Dict:
        """
        Detect if payment is below allowed amount (underpayment/violation)

        Args:
            cpt_code: CPT procedure code
            paid_amount: Amount actually paid by payer
            service_date: Date of service
            modifiers: CPT modifiers
            geo_region: Geographic region/locality
            **kwargs: Additional payer-specific parameters

        Returns:
            Dictionary with:
            - is_violation: bool
            - allowed_amount: Decimal
            - paid_amount: Decimal
            - delta: Decimal (underpayment amount)
            - reason: Optional[str]
            - violation_codes: List[str] (e.g., ['UNDERPAYMENT', 'NCCI_EDIT'])
        """
        pass

    @abstractmethod
    async def validate_claim(self, claim_data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate claim against payer-specific rules

        Args:
            claim_data: Dictionary with claim information

        Returns:
            Tuple of (is_valid, error_messages)
        """
        pass

    @abstractmethod
    async def apply_edits(
        self,
        cpt_code: str,
        service_date: date,
        diagnosis_codes: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict:
        """
        Apply payer-specific edits (NCCI, MUEs, LCD/NCD)

        Args:
            cpt_code: CPT procedure code
            service_date: Date of service
            diagnosis_codes: ICD-10 diagnosis codes
            **kwargs: Additional parameters

        Returns:
            Dictionary with:
            - passed: bool
            - edits_applied: List[str]
            - violations: List[Dict]
        """
        pass

    @abstractmethod
    def get_appeal_requirements(self) -> Dict:
        """
        Get payer-specific appeal requirements

        Returns:
            Dictionary with:
            - internal_deadline: int (days)
            - external_deadline: int (days)
            - required_documents: List[str]
            - submission_method: str (portal, fax, mail)
            - portal_url: Optional[str]
        """
        pass

    @abstractmethod
    def get_regulatory_citations(self) -> List[Dict]:
        """
        Get applicable regulatory citations for this payer

        Returns:
            List of dictionaries with:
            - citation: str (e.g., "42 CFR 447.361")
            - description: str
            - url: Optional[str]
        """
        pass

    def supports_telehealth(self, cpt_code: str, service_date: date) -> bool:
        """
        Check if payer covers telehealth for this service

        Args:
            cpt_code: CPT procedure code
            service_date: Date of service

        Returns:
            True if telehealth is covered
        """
        # Default: no telehealth support (override in subclasses)
        return False

    def get_geographic_adjustment_factor(
        self, geo_region: str, service_date: date
    ) -> Decimal:
        """
        Get geographic adjustment factor for region

        Args:
            geo_region: Geographic region identifier
            service_date: Date of service

        Returns:
            Geographic adjustment multiplier
        """
        # Default: no adjustment (override in subclasses)
        return Decimal("1.000")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(payer='{self.payer_name}', type='{self.payer_type.value}')>"
