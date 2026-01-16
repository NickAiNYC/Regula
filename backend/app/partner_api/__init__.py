"""
Regula Intelligence - Partner API

Separate FastAPI service for B2B integrations.
Enables RCM companies, EHR vendors, and consultancies to embed
Regula's compliance engine.

Features:
- API key authentication
- Usage metering & billing
- Rate limiting
- Webhook notifications
- White-label capabilities
"""

from .main import create_partner_app
from .auth import APIKeyAuth, UsageMetering
from .endpoints import compliance_check, batch_analysis, webhook_register

__all__ = [
    "create_partner_app",
    "APIKeyAuth",
    "UsageMetering",
]
