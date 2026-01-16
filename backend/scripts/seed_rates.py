"""
Seed Rate Database with NY Medicaid 2025 Rates
Run with: python -m scripts.seed_rates
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.models import RateDatabase
from datetime import date
from decimal import Decimal


# NY Medicaid 2025 Behavioral Health Rates (with 2.84% COLA)
# Source: NYS OMH Rate Schedule 2025
RATE_DATA = [
    {
        "cpt_code": "90837",
        "description": "Psychotherapy, 60 minutes",
        "category": "psychotherapy",
        "base_rate_2024": Decimal("153.50"),
        "cola_rate_2025": Decimal("158.00"),
        "effective_date": date(2025, 1, 1),
        "source": "NYS OMH Rate Schedule 2025",
    },
    {
        "cpt_code": "90834",
        "description": "Psychotherapy, 45 minutes",
        "category": "psychotherapy",
        "base_rate_2024": Decimal("107.00"),
        "cola_rate_2025": Decimal("110.00"),
        "effective_date": date(2025, 1, 1),
        "source": "NYS OMH Rate Schedule 2025",
    },
    {
        "cpt_code": "90832",
        "description": "Psychotherapy, 30 minutes",
        "category": "psychotherapy",
        "base_rate_2024": Decimal("71.50"),
        "cola_rate_2025": Decimal("73.50"),
        "effective_date": date(2025, 1, 1),
        "source": "NYS OMH Rate Schedule 2025",
    },
    {
        "cpt_code": "90791",
        "description": "Psychiatric Diagnostic Evaluation",
        "category": "diagnostic",
        "base_rate_2024": Decimal("170.00"),
        "cola_rate_2025": Decimal("175.00"),
        "effective_date": date(2025, 1, 1),
        "source": "NYS OMH Rate Schedule 2025",
    },
]


async def seed_rates(db: AsyncSession):
    """Seed rate database with NY Medicaid 2025 rates"""

    print("Seeding rate database...")

    for rate_data in RATE_DATA:
        rate = RateDatabase(**rate_data)
        db.add(rate)
        print(f"  Added {rate.cpt_code}: {rate.description}")

    await db.commit()
    print(f"\nSuccessfully seeded {len(RATE_DATA)} rates!")


async def main():
    """Main entry point"""
    async with AsyncSessionLocal() as db:
        try:
            await seed_rates(db)
        except Exception as e:
            print(f"Error seeding rates: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
