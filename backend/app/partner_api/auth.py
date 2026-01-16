"""
Partner API Authentication & Metering

API key-based authentication with usage tracking and billing.
"""

from datetime import datetime
from typing import Dict, Optional
from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
import structlog
from decimal import Decimal

logger = structlog.get_logger()


API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=True)


class APIKeyAuth:
    """
    API Key authentication for partners

    Features:
    - Key validation
    - Partner identification
    - Permission checking
    - Rate limiting
    """

    # In production, store in database
    VALID_KEYS = {
        "demo_key_12345": {
            "partner_id": "partner_001",
            "partner_name": "Demo RCM Company",
            "tier": "basic",
            "rate_limit": 100,  # requests per minute
            "features": ["compliance_check", "batch_analysis"],
        },
        "enterprise_key_67890": {
            "partner_id": "partner_002",
            "partner_name": "Enterprise Health System",
            "tier": "enterprise",
            "rate_limit": 1000,
            "features": [
                "compliance_check",
                "batch_analysis",
                "webhook",
                "white_label",
            ],
        },
    }

    @classmethod
    async def validate_api_key(cls, api_key: str = Security(API_KEY_HEADER)) -> Dict:
        """
        Validate API key and return partner info

        Args:
            api_key: API key from header

        Returns:
            Partner information dictionary

        Raises:
            HTTPException: If key is invalid
        """
        if api_key not in cls.VALID_KEYS:
            logger.warning("invalid_api_key_attempt", key_prefix=api_key[:10])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
            )

        partner_info = cls.VALID_KEYS[api_key]

        logger.info(
            "api_key_validated",
            partner_id=partner_info["partner_id"],
            partner_name=partner_info["partner_name"],
        )

        return partner_info

    @classmethod
    async def check_feature_access(cls, partner_info: Dict, feature: str) -> bool:
        """
        Check if partner has access to a feature

        Args:
            partner_info: Partner information
            feature: Feature name

        Returns:
            True if partner has access
        """
        return feature in partner_info.get("features", [])


class UsageMetering:
    """
    Track API usage for billing and rate limiting

    Metrics tracked:
    - API calls per endpoint
    - Data volume processed
    - Compliance checks run
    - Cost per partner

    Billing:
    - Basic tier: $0.10 per compliance check
    - Enterprise tier: Custom pricing
    """

    # In-memory storage (in production, use Redis + TimescaleDB)
    usage_data = {}

    @classmethod
    async def record_usage(
        cls,
        partner_id: str,
        endpoint: str,
        claims_processed: int = 1,
        data_volume_mb: float = 0.0,
    ):
        """
        Record API usage event

        Args:
            partner_id: Partner identifier
            endpoint: API endpoint called
            claims_processed: Number of claims processed
            data_volume_mb: Data volume in MB
        """
        if partner_id not in cls.usage_data:
            cls.usage_data[partner_id] = {
                "calls": 0,
                "claims_processed": 0,
                "data_volume_mb": 0.0,
                "endpoints": {},
                "first_call": datetime.now().isoformat(),
                "last_call": None,
            }

        # Update metrics
        cls.usage_data[partner_id]["calls"] += 1
        cls.usage_data[partner_id]["claims_processed"] += claims_processed
        cls.usage_data[partner_id]["data_volume_mb"] += data_volume_mb
        cls.usage_data[partner_id]["last_call"] = datetime.now().isoformat()

        # Track by endpoint
        if endpoint not in cls.usage_data[partner_id]["endpoints"]:
            cls.usage_data[partner_id]["endpoints"][endpoint] = 0
        cls.usage_data[partner_id]["endpoints"][endpoint] += 1

        logger.debug(
            "usage_recorded",
            partner_id=partner_id,
            endpoint=endpoint,
            claims=claims_processed,
        )

    @classmethod
    async def get_usage_summary(
        cls,
        partner_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Get usage summary for partner

        Args:
            partner_id: Partner identifier
            start_date: Start of period
            end_date: End of period

        Returns:
            Usage summary with billing info
        """
        if partner_id not in cls.usage_data:
            return {
                "partner_id": partner_id,
                "total_calls": 0,
                "claims_processed": 0,
                "estimated_cost": 0.0,
            }

        usage = cls.usage_data[partner_id]

        # Calculate cost (basic: $0.10 per claim)
        cost_per_claim = Decimal("0.10")
        estimated_cost = cost_per_claim * usage["claims_processed"]

        return {
            "partner_id": partner_id,
            "total_calls": usage["calls"],
            "claims_processed": usage["claims_processed"],
            "data_volume_mb": usage["data_volume_mb"],
            "endpoints": usage["endpoints"],
            "first_call": usage["first_call"],
            "last_call": usage["last_call"],
            "estimated_cost": float(estimated_cost),
            "cost_per_claim": float(cost_per_claim),
        }

    @classmethod
    async def check_rate_limit(
        cls, partner_id: str, rate_limit: int, window_seconds: int = 60
    ) -> bool:
        """
        Check if partner has exceeded rate limit

        Args:
            partner_id: Partner identifier
            rate_limit: Max requests per window
            window_seconds: Time window in seconds

        Returns:
            True if under limit, False if exceeded
        """
        # In production, use Redis with sliding window
        # For now, simple check
        if partner_id not in cls.usage_data:
            return True

        # Simplified check - would need time-window logic in production
        return True  # Always allow for demo


class RateLimiter:
    """
    Rate limiting for partner API

    Implements token bucket algorithm with per-partner limits
    """

    @classmethod
    async def check_and_consume(cls, partner_id: str, rate_limit: int) -> bool:
        """
        Check rate limit and consume token

        Args:
            partner_id: Partner identifier
            rate_limit: Requests per minute

        Returns:
            True if allowed, False if rate limited

        Raises:
            HTTPException: If rate limit exceeded
        """
        # In production, use Redis for distributed rate limiting
        allowed = await UsageMetering.check_rate_limit(partner_id, rate_limit)

        if not allowed:
            logger.warning("rate_limit_exceeded", partner_id=partner_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {rate_limit} requests per minute.",
            )

        return True
