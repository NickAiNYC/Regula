"""
Regula Health - Test Configuration
Pytest configuration and fixtures for testing
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from datetime import date
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from app.db.session import Base, get_db
from app.models import Organization, User, Provider, RateDatabase
from app.core.security import get_password_hash
import uuid


# Test database URL (in-memory SQLite for speed)
TEST_DATABASE_URL = "******memory"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_engine():
    """Create test database engine"""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create test organization"""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Behavioral Health",
        ein="123456789",
        is_active=True,
        subscription_tier="enterprise",
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create test user"""
    user = User(
        id=uuid.uuid4(),
        organization_id=test_organization.id,
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_superuser=False,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_provider(
    db_session: AsyncSession, test_organization: Organization
) -> Provider:
    """Create test provider"""
    provider = Provider(
        id=uuid.uuid4(),
        organization_id=test_organization.id,
        npi="1234567890",
        name="Dr. Test Provider",
        specialty="Psychiatry",
        geo_region="nyc",
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


@pytest.fixture
async def test_rates(db_session: AsyncSession):
    """Seed test rate database"""
    rates = [
        RateDatabase(
            cpt_code="90837",
            description="Psychotherapy, 60 minutes",
            category="psychotherapy",
            base_rate_2024=Decimal("153.50"),
            cola_rate_2025=Decimal("158.00"),
            effective_date=date(2025, 1, 1),
            source="Test Data",
        ),
        RateDatabase(
            cpt_code="90834",
            description="Psychotherapy, 45 minutes",
            category="psychotherapy",
            base_rate_2024=Decimal("107.00"),
            cola_rate_2025=Decimal("110.00"),
            effective_date=date(2025, 1, 1),
            source="Test Data",
        ),
    ]

    for rate in rates:
        db_session.add(rate)

    await db_session.commit()
    return rates


@pytest.fixture
def edi_fixture() -> str:
    """Sample EDI 835 file content"""
    return """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250115*1200*^*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20250115*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*500.00*C*ACH*CTX*01*123456789*DA*12345*9876543210**01*987654321*DA*54321*20250120~
N1*PR*Aetna Behavioral Health~
N3*123 Insurance Way~
N4*Hartford*CT*06101~
CLP*CLAIM001*1*500.00*450.00*0.00*12*CLM123*11*1~
NM1*QC*1*DOE*JOHN****MI*MEM123456~
DTM*472*20250115~
SVC*HC:90837*500.00*450.00**1~
DTM*472*20250115~
CLP*CLAIM002*1*350.00*300.00*0.00*12*CLM124*11*1~
NM1*QC*1*SMITH*JANE****MI*MEM789012~
DTM*472*20250116~
SVC*HC:90834*350.00*300.00**1~
DTM*472*20250116~
SE*20*0001~
GE*1*1~
IEA*1*000000001~"""


@pytest.fixture
async def auth_headers(test_user: User) -> dict:
    """Generate authentication headers for test user"""
    from app.core.security import create_access_token

    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}
