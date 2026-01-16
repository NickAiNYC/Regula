"""
Regula Intelligence - Payer Adapter Framework

Multi-payer support for national revenue integrity across:
- CMS Medicare
- 50+ State Medicaid plans
- Top 20 commercial payers (UnitedHealth, Aetna, etc.)

Each adapter handles unique:
- Fee schedules
- Rules (NCCI edits, MUEs)
- Remittance formats (EDI 835, EOBs)
"""

from .base import BasePayerAdapter, PayerAdapterError, PayerType
from .cms_medicare import CMSMedicareAdapter
from .ny_medicaid import NYMedicaidAdapter
from .aetna_commercial import AetnaCommercialAdapter
from .factory import PayerAdapterFactory, get_payer_adapter

__all__ = [
    "BasePayerAdapter",
    "PayerAdapterError",
    "PayerType",
    "CMSMedicareAdapter",
    "NYMedicaidAdapter",
    "AetnaCommercialAdapter",
    "PayerAdapterFactory",
    "get_payer_adapter",
]
