"""
Tests for Payer Adapter Framework
"""

import pytest
from datetime import date
from decimal import Decimal

from app.payer_adapters import (
    get_payer_adapter,
    PayerAdapterFactory,
    CMSMedicareAdapter,
    NYMedicaidAdapter,
    AetnaCommercialAdapter,
    PayerAdapterError,
)


class TestPayerAdapterFactory:
    """Test payer adapter factory functionality"""

    def test_get_adapter_medicare(self):
        """Test getting Medicare adapter"""
        adapter = get_payer_adapter("Medicare")
        assert isinstance(adapter, CMSMedicareAdapter)
        assert adapter.payer_name == "CMS Medicare"

    def test_get_adapter_ny_medicaid(self):
        """Test getting NY Medicaid adapter"""
        adapter = get_payer_adapter("NY Medicaid")
        assert isinstance(adapter, NYMedicaidAdapter)
        assert adapter.payer_name == "NY Medicaid"

    def test_get_adapter_aetna(self):
        """Test getting Aetna adapter"""
        adapter = get_payer_adapter("Aetna")
        assert isinstance(adapter, AetnaCommercialAdapter)
        assert adapter.payer_name == "Aetna"

    def test_get_adapter_invalid_payer(self):
        """Test error handling for invalid payer"""
        with pytest.raises(PayerAdapterError):
            get_payer_adapter("NonexistentPayer")

    def test_list_supported_payers(self):
        """Test listing supported payers"""
        payers = PayerAdapterFactory.list_supported_payers()
        assert "cms_medicare" in payers
        assert "ny_medicaid" in payers
        assert "aetna" in payers

    def test_is_supported(self):
        """Test checking if payer is supported"""
        assert PayerAdapterFactory.is_supported("Medicare")
        assert PayerAdapterFactory.is_supported("Aetna")
        assert not PayerAdapterFactory.is_supported("InvalidPayer")


class TestCMSMedicareAdapter:
    """Test CMS Medicare adapter"""

    @pytest.fixture
    def adapter(self):
        return CMSMedicareAdapter()

    @pytest.mark.asyncio
    async def test_get_allowed_amount(self, adapter):
        """Test calculating Medicare allowed amount"""
        service_date = date(2025, 1, 15)
        amount = await adapter.get_allowed_amount(
            cpt_code="90837", service_date=service_date, geo_region="nyc"
        )

        assert amount is not None
        assert isinstance(amount, Decimal)
        assert amount > 0

    @pytest.mark.asyncio
    async def test_detect_underpayment(self, adapter):
        """Test detecting Medicare underpayment"""
        service_date = date(2025, 1, 15)
        result = await adapter.detect_underpayment(
            cpt_code="90837",
            paid_amount=Decimal("100.00"),
            service_date=service_date,
            geo_region="nyc",
        )

        assert "is_violation" in result
        assert "allowed_amount" in result
        assert "paid_amount" in result

    def test_supports_telehealth(self, adapter):
        """Test telehealth coverage check"""
        assert adapter.supports_telehealth("90837", date(2025, 1, 15))
        assert not adapter.supports_telehealth("99999", date(2025, 1, 15))

    def test_get_appeal_requirements(self, adapter):
        """Test getting appeal requirements"""
        reqs = adapter.get_appeal_requirements()
        assert "internal_deadline" in reqs
        assert "portal_url" in reqs
        assert reqs["internal_deadline"] == 120

    def test_get_regulatory_citations(self, adapter):
        """Test getting regulatory citations"""
        citations = adapter.get_regulatory_citations()
        assert len(citations) > 0
        assert "citation" in citations[0]
        assert "description" in citations[0]


class TestNYMedicaidAdapter:
    """Test NY Medicaid adapter"""

    @pytest.fixture
    def adapter(self):
        return NYMedicaidAdapter()

    @pytest.mark.asyncio
    async def test_get_allowed_amount(self, adapter):
        """Test calculating NY Medicaid mandate rate"""
        service_date = date(2025, 1, 15)
        amount = await adapter.get_allowed_amount(
            cpt_code="90837", service_date=service_date, geo_region="nyc"
        )

        assert amount is not None
        assert isinstance(amount, Decimal)
        assert amount > 0

    @pytest.mark.asyncio
    async def test_geographic_adjustment(self, adapter):
        """Test geographic adjustment factors"""
        service_date = date(2025, 1, 15)

        # NYC should have highest rate
        nyc_amount = await adapter.get_allowed_amount(
            "90837", service_date, geo_region="nyc"
        )

        # Upstate should have lower rate
        upstate_amount = await adapter.get_allowed_amount(
            "90837", service_date, geo_region="upstate"
        )

        assert nyc_amount > upstate_amount

    @pytest.mark.asyncio
    async def test_detect_parity_violation(self, adapter):
        """Test detecting parity mandate violation"""
        service_date = date(2025, 1, 15)
        result = await adapter.detect_underpayment(
            cpt_code="90837",
            paid_amount=Decimal("130.00"),
            service_date=service_date,
            geo_region="nyc",
        )

        if result["is_violation"]:
            assert "NY_PARITY_VIOLATION" in result["violation_codes"]

    def test_get_regulatory_citations(self, adapter):
        """Test getting NY parity citations"""
        citations = adapter.get_regulatory_citations()

        # Should include parity mandate
        citation_texts = [c["citation"] for c in citations]
        assert any("L.2024 c.57" in c for c in citation_texts)


class TestAetnaCommercialAdapter:
    """Test Aetna commercial adapter"""

    @pytest.fixture
    def adapter(self):
        return AetnaCommercialAdapter()

    @pytest.mark.asyncio
    async def test_get_allowed_amount_with_contract(self, adapter):
        """Test getting allowed amount with contract rate"""
        service_date = date(2025, 1, 15)
        amount = await adapter.get_allowed_amount(
            cpt_code="90837", service_date=service_date, contract_rate=150.00
        )

        assert amount == Decimal("150.00")

    @pytest.mark.asyncio
    async def test_get_allowed_amount_without_contract(self, adapter):
        """Test getting allowed amount without contract"""
        service_date = date(2025, 1, 15)
        amount = await adapter.get_allowed_amount(
            cpt_code="90837",
            service_date=service_date,
            billed_charges=200.00,
            plan_type="ppo_in_network",
        )

        assert amount is not None
        assert amount > 0

    @pytest.mark.asyncio
    async def test_detect_underpayment(self, adapter):
        """Test detecting commercial underpayment"""
        service_date = date(2025, 1, 15)
        result = await adapter.detect_underpayment(
            cpt_code="90837",
            paid_amount=Decimal("120.00"),
            service_date=service_date,
            contract_rate=150.00,
        )

        assert "is_violation" in result
        assert result["is_violation"]
        assert result["delta"] == Decimal("30.00")

    def test_supports_telehealth(self, adapter):
        """Test Aetna telehealth coverage"""
        assert adapter.supports_telehealth("90837", date(2025, 1, 15))
