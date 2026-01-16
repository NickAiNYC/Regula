"""
Regula Health - Rate Calculation Engine
Compliance checking against NY Medicaid parity rates
Performance target: <5ms per lookup (including cache miss)
"""

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Tuple
import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RateDatabase, Claim
from app.core.config import settings

logger = structlog.get_logger()


class RateEngine:
    """
    Calculate compliant rates and detect violations
    
    Features:
    - Redis caching for performance
    - Geographic adjustments (NYC 1.065x, LI 1.025x, Upstate 1.0x)
    - COLA tracking (2025: 2.84%, 2026: TBD)
    - Sub-5ms lookup performance
    """
    
    # Geographic multipliers
    GEO_MULTIPLIERS = {
        "nyc": Decimal("1.065"),
        "longisland": Decimal("1.025"),
        "upstate": Decimal("1.000"),
    }
    
    # COLA (Cost of Living Adjustment) percentages
    COLA_ADJUSTMENTS = {
        2024: Decimal("1.000"),
        2025: Decimal("1.0284"),  # 2.84% increase
        2026: Decimal("1.0284"),  # TBD - using 2025 for now
    }
    
    def __init__(self, db: AsyncSession, cache: Optional[Redis] = None):
        self.db = db
        self.cache = cache
    
    async def get_mandate_rate(
        self,
        cpt_code: str,
        service_date: date,
        geo_region: str = "upstate"
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        Calculate compliant rate for a service
        
        Logic:
        1. Check Redis cache for rate
        2. If miss, query PostgreSQL rates table
        3. Apply geographic multiplier based on region
        4. Apply COLA adjustment for service date
        5. Cache result (TTL: 24 hours)
        6. Return rate and geo_factor
        
        Args:
            cpt_code: CPT procedure code
            service_date: Date of service
            geo_region: Geographic region (nyc, longisland, upstate)
            
        Returns:
            Tuple of (mandate_rate, geo_adjustment_factor) or (None, None) if not found
        """
        # Generate cache key
        cache_key = f"rate:{cpt_code}:{service_date.year}:{geo_region}"
        
        # Try cache first
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug("rate_cache_hit", cpt_code=cpt_code)
                parts = cached.decode().split(":")
                return Decimal(parts[0]), Decimal(parts[1])
        
        # Cache miss - query database
        stmt = select(RateDatabase).where(RateDatabase.cpt_code == cpt_code)
        result = await self.db.execute(stmt)
        rate_record = result.scalar_one_or_none()
        
        if not rate_record:
            logger.warning("rate_not_found", cpt_code=cpt_code)
            return None, None
        
        # Get base rate for service year
        base_rate = self._get_base_rate(rate_record, service_date)
        
        # Apply geographic adjustment
        geo_factor = self.GEO_MULTIPLIERS.get(geo_region.lower(), Decimal("1.000"))
        adjusted_rate = base_rate * geo_factor
        
        # Round to 2 decimal places
        final_rate = adjusted_rate.quantize(Decimal("0.01"))
        
        # Cache the result
        if self.cache:
            cache_value = f"{final_rate}:{geo_factor}"
            await self.cache.setex(
                cache_key,
                settings.CACHE_TTL,
                cache_value
            )
        
        logger.debug(
            "rate_calculated",
            cpt_code=cpt_code,
            base_rate=float(base_rate),
            geo_factor=float(geo_factor),
            final_rate=float(final_rate)
        )
        
        return final_rate, geo_factor
    
    def _get_base_rate(self, rate_record: RateDatabase, service_date: date) -> Decimal:
        """
        Get base rate with COLA adjustment
        
        Args:
            rate_record: Rate database record
            service_date: Date of service
            
        Returns:
            Base rate with COLA applied
        """
        year = service_date.year
        
        # Select appropriate rate based on year
        if year >= 2026 and rate_record.cola_rate_2026:
            return rate_record.cola_rate_2026
        elif year >= 2025:
            return rate_record.cola_rate_2025
        else:
            return rate_record.base_rate_2024
    
    async def detect_violation(
        self,
        cpt_code: str,
        paid_amount: Decimal,
        service_date: date,
        geo_region: str = "upstate"
    ) -> Dict:
        """
        Check if payment violates NY Medicaid parity
        
        Args:
            cpt_code: CPT procedure code
            paid_amount: Amount actually paid by insurer
            service_date: Date of service
            geo_region: Geographic region
            
        Returns:
            Dictionary with violation details
        """
        mandate_rate, geo_factor = await self.get_mandate_rate(
            cpt_code, service_date, geo_region
        )
        
        if mandate_rate is None:
            return {
                "is_violation": False,
                "mandate_rate": None,
                "delta": None,
                "geo_adjustment_factor": None,
                "reason": "Rate not found in database"
            }
        
        # Calculate underpayment
        delta = mandate_rate - paid_amount
        
        # Violation if paid less than mandate (with 0.01 tolerance for rounding)
        is_violation = delta > Decimal("0.01")
        
        return {
            "is_violation": is_violation,
            "mandate_rate": mandate_rate,
            "delta": delta,
            "geo_adjustment_factor": geo_factor,
            "paid_amount": paid_amount
        }
    
    async def bulk_check_violations(
        self,
        claims_data: list[Dict]
    ) -> list[Dict]:
        """
        Efficiently check multiple claims for violations
        
        Args:
            claims_data: List of claim dictionaries with cpt_code, paid_amount, dos, geo_region
            
        Returns:
            List of enriched claim dictionaries with violation info
        """
        results = []
        
        for claim in claims_data:
            violation_info = await self.detect_violation(
                cpt_code=claim["cpt_code"],
                paid_amount=claim["paid_amount"],
                service_date=claim["dos"],
                geo_region=claim.get("geo_region", "upstate")
            )
            
            results.append({
                **claim,
                **violation_info
            })
        
        return results


async def get_rate_engine(db: AsyncSession, cache: Optional[Redis] = None) -> RateEngine:
    """Dependency injection for rate engine"""
    return RateEngine(db, cache)
