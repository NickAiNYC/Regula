"""
Regula Health - Rate Engine Tests
Test rate calculation, geographic adjustments, and violation detection
"""

import pytest
from datetime import date
from decimal import Decimal
from redis.asyncio import Redis

from app.services.rate_engine import RateEngine
from app.models import RateDatabase


@pytest.mark.asyncio
async def test_get_mandate_rate_nyc(db_session, test_rates):
    """Test rate calculation with NYC geographic adjustment"""
    engine = RateEngine(db_session, cache=None)
    
    rate, geo_factor = await engine.get_mandate_rate(
        cpt_code="90837",
        service_date=date(2025, 1, 15),
        geo_region="nyc"
    )
    
    assert rate is not None
    assert geo_factor == Decimal("1.065")
    # 158.00 * 1.065 = 168.27
    assert rate == Decimal("168.27")


@pytest.mark.asyncio
async def test_get_mandate_rate_longisland(db_session, test_rates):
    """Test rate calculation with Long Island adjustment"""
    engine = RateEngine(db_session, cache=None)
    
    rate, geo_factor = await engine.get_mandate_rate(
        cpt_code="90837",
        service_date=date(2025, 1, 15),
        geo_region="longisland"
    )
    
    assert rate is not None
    assert geo_factor == Decimal("1.025")
    # 158.00 * 1.025 = 161.95
    assert rate == Decimal("161.95")


@pytest.mark.asyncio
async def test_get_mandate_rate_upstate(db_session, test_rates):
    """Test rate calculation with upstate (no adjustment)"""
    engine = RateEngine(db_session, cache=None)
    
    rate, geo_factor = await engine.get_mandate_rate(
        cpt_code="90837",
        service_date=date(2025, 1, 15),
        geo_region="upstate"
    )
    
    assert rate is not None
    assert geo_factor == Decimal("1.000")
    assert rate == Decimal("158.00")


@pytest.mark.asyncio
async def test_get_mandate_rate_invalid_cpt(db_session, test_rates):
    """Test rate lookup for non-existent CPT code"""
    engine = RateEngine(db_session, cache=None)
    
    rate, geo_factor = await engine.get_mandate_rate(
        cpt_code="99999",
        service_date=date(2025, 1, 15),
        geo_region="nyc"
    )
    
    assert rate is None
    assert geo_factor is None


@pytest.mark.asyncio
async def test_detect_violation_underpaid(db_session, test_rates):
    """Test violation detection for underpaid claim"""
    engine = RateEngine(db_session, cache=None)
    
    result = await engine.detect_violation(
        cpt_code="90837",
        paid_amount=Decimal("130.00"),
        service_date=date(2025, 1, 15),
        geo_region="nyc"
    )
    
    assert result['is_violation'] is True
    assert result['mandate_rate'] == Decimal("168.27")
    assert result['paid_amount'] == Decimal("130.00")
    assert result['delta'] > Decimal("38.00")


@pytest.mark.asyncio
async def test_detect_violation_compliant(db_session, test_rates):
    """Test violation detection for compliant claim"""
    engine = RateEngine(db_session, cache=None)
    
    result = await engine.detect_violation(
        cpt_code="90837",
        paid_amount=Decimal("170.00"),
        service_date=date(2025, 1, 15),
        geo_region="nyc"
    )
    
    assert result['is_violation'] is False
    assert result['mandate_rate'] == Decimal("168.27")
    assert result['delta'] < Decimal("0.00")


@pytest.mark.asyncio
async def test_detect_violation_exact_match(db_session, test_rates):
    """Test violation detection when paid equals mandate"""
    engine = RateEngine(db_session, cache=None)
    
    result = await engine.detect_violation(
        cpt_code="90837",
        paid_amount=Decimal("168.27"),
        service_date=date(2025, 1, 15),
        geo_region="nyc"
    )
    
    assert result['is_violation'] is False
    assert result['delta'] == Decimal("0.00")


@pytest.mark.asyncio
async def test_bulk_check_violations(db_session, test_rates):
    """Test bulk violation checking"""
    engine = RateEngine(db_session, cache=None)
    
    claims_data = [
        {
            'cpt_code': '90837',
            'paid_amount': Decimal('130.00'),
            'dos': date(2025, 1, 15),
            'geo_region': 'nyc'
        },
        {
            'cpt_code': '90834',
            'paid_amount': Decimal('100.00'),
            'dos': date(2025, 1, 15),
            'geo_region': 'nyc'
        }
    ]
    
    results = await engine.bulk_check_violations(claims_data)
    
    assert len(results) == 2
    assert all('is_violation' in r for r in results)
    assert all('mandate_rate' in r for r in results)


@pytest.mark.asyncio
async def test_cola_adjustment_2024(db_session):
    """Test COLA adjustment for 2024 service date"""
    # Add 2024 rate
    rate = RateDatabase(
        cpt_code="90837",
        description="Test",
        category="psychotherapy",
        base_rate_2024=Decimal("153.50"),
        cola_rate_2025=Decimal("158.00"),
        effective_date=date(2024, 1, 1),
        source="Test"
    )
    db_session.add(rate)
    await db_session.commit()
    
    engine = RateEngine(db_session, cache=None)
    
    rate_2024, _ = await engine.get_mandate_rate(
        cpt_code="90837",
        service_date=date(2024, 6, 15),
        geo_region="upstate"
    )
    
    # Should use base_rate_2024
    assert rate_2024 == Decimal("153.50")
