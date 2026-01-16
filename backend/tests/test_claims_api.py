"""
Regula Health - Claims API Tests
Test EDI upload, claims listing, and violation detection
"""

import pytest
from httpx import AsyncClient
from datetime import date
from decimal import Decimal

from app.models import User, Provider, Organization


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test API health check endpoint"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_claim_upload_success(
    client: AsyncClient,
    auth_headers: dict,
    test_provider: Provider,
    test_rates
):
    """Test successful EDI file upload"""
    edi_content = """ST*835*0001~
N1*PR*TestPayer~
CLP*TEST001*1*158.00*130.00*0.00~
SVC*HC:90837*158.00*130.00**1~
DTM*472*20250115~
SE*5*0001~"""
    
    files = {'file': ('test.835', edi_content.encode(), 'text/plain')}
    response = await client.post(
        '/api/v1/claims/upload',
        files=files,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['claims_processed'] > 0
    assert 'file_name' in data
    assert data['violations_found'] >= 0


@pytest.mark.asyncio
async def test_claim_upload_unauthorized(client: AsyncClient):
    """Test EDI upload without authentication"""
    files = {'file': ('test.835', b'test content', 'text/plain')}
    response = await client.post('/api/v1/claims/upload', files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_claims(
    client: AsyncClient,
    auth_headers: dict,
    test_provider: Provider
):
    """Test listing claims with pagination"""
    response = await client.get(
        '/api/v1/claims',
        headers=auth_headers,
        params={'page': 1, 'per_page': 10}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert 'claims' in data
    assert 'total' in data
    assert 'page' in data
    assert isinstance(data['claims'], list)


@pytest.mark.asyncio
async def test_list_claims_with_filters(
    client: AsyncClient,
    auth_headers: dict
):
    """Test claims listing with filters"""
    response = await client.get(
        '/api/v1/claims',
        headers=auth_headers,
        params={
            'payer': 'Aetna',
            'is_violation': True,
            'page': 1,
            'per_page': 50
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data['claims'], list)


@pytest.mark.asyncio
async def test_get_claim_by_id(
    client: AsyncClient,
    auth_headers: dict,
    db_session,
    test_provider: Provider
):
    """Test retrieving a specific claim"""
    from app.models import Claim
    import uuid
    
    # Create a test claim
    claim = Claim(
        id=uuid.uuid4(),
        provider_id=test_provider.id,
        claim_id="TEST123",
        payer="Test Payer",
        dos=date(2025, 1, 15),
        cpt_code="90837",
        mandate_rate=Decimal("158.00"),
        paid_amount=Decimal("130.00"),
        delta=Decimal("28.00"),
        is_violation=True
    )
    db_session.add(claim)
    await db_session.commit()
    
    response = await client.get(
        f'/api/v1/claims/{claim.id}',
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data['claim_id'] == "TEST123"
    assert data['is_violation'] is True


@pytest.mark.asyncio
async def test_upload_malformed_edi(
    client: AsyncClient,
    auth_headers: dict
):
    """Test upload of malformed EDI file"""
    files = {'file': ('bad.835', b'INVALID EDI CONTENT', 'text/plain')}
    response = await client.post(
        '/api/v1/claims/upload',
        files=files,
        headers=auth_headers
    )
    
    # Should handle gracefully
    assert response.status_code in [200, 400]
