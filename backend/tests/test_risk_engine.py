"""
Tests for Risk Engine modules
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from app.risk_engine import (
    PredictiveUnderpaymentScorer,
    AnomalyDetector,
    AppealSuccessOptimizer
)


class TestPredictiveUnderpaymentScorer:
    """Test predictive underpayment scorer"""
    
    @pytest.fixture
    def scorer(self):
        return PredictiveUnderpaymentScorer()
    
    @pytest.mark.asyncio
    async def test_score_claim(self, scorer):
        """Test scoring a single claim"""
        claim_data = {
            "claim_id": "TEST-001",
            "payer": "Aetna",
            "cpt_code": "90837",
            "billed_amount": 200.00,
            "expected_amount": 157.00,
            "service_date": date(2025, 1, 15)
        }
        
        result = await scorer.score_claim(claim_data)
        
        assert "risk_score" in result
        assert "risk_category" in result
        assert "contributing_factors" in result
        assert "recommendation" in result
        
        assert 0 <= result["risk_score"] <= 100
        assert result["risk_category"] in ["low", "medium", "high", "critical"]
    
    @pytest.mark.asyncio
    async def test_score_batch(self, scorer):
        """Test scoring multiple claims"""
        claims = [
            {"claim_id": f"TEST-{i}", "payer": "Aetna", "cpt_code": "90837"}
            for i in range(5)
        ]
        
        results = await scorer.score_batch(claims)
        
        assert len(results) == 5
        assert all("risk_score" in r for r in results)
    
    def test_get_model_info(self, scorer):
        """Test getting model metadata"""
        info = scorer.get_model_info()
        
        assert "version" in info
        assert "feature_count" in info
        assert "fallback_mode" in info


class TestAnomalyDetector:
    """Test anomaly detection"""
    
    @pytest.fixture
    def detector(self):
        return AnomalyDetector()
    
    @pytest.mark.asyncio
    async def test_detect_provider_anomalies(self, detector):
        """Test detecting provider anomalies"""
        claims_data = [
            {
                "cpt_code": "90837",
                "paid_amount": 100.00,
                "service_date": date(2025, 1, i)
            }
            for i in range(1, 31)
        ]
        
        result = await detector.detect_provider_anomalies(
            provider_id="PROV-001",
            claims_data=claims_data
        )
        
        assert "has_anomalies" in result
        assert "anomalies" in result
        assert "risk_level" in result
        assert "recommendations" in result
        
        assert result["risk_level"] in ["low", "medium", "high"]
    
    @pytest.mark.asyncio
    async def test_volume_anomaly_detection(self, detector):
        """Test volume anomaly detection"""
        # Simulate spike in claims
        claims = [{"cpt_code": "90837"} for _ in range(100)]
        
        baseline = {
            "avg_volumes_by_cpt": {"90837": 30},
            "std_volumes_by_cpt": {"90837": 5}
        }
        
        anomalies = detector._detect_volume_anomalies(claims, baseline)
        
        # Should detect spike
        assert len(anomalies) > 0


class TestAppealSuccessOptimizer:
    """Test appeal success optimizer"""
    
    @pytest.fixture
    def optimizer(self):
        return AppealSuccessOptimizer()
    
    @pytest.mark.asyncio
    async def test_analyze_appeal_opportunity(self, optimizer):
        """Test analyzing appeal opportunity"""
        claim_data = {
            "claim_id": "CLAIM-001",
            "payer": "Aetna",
            "cpt_code": "90837",
            "service_date": date(2025, 1, 15)
        }
        
        violation_data = {
            "delta": Decimal("32.49"),
            "allowed_amount": Decimal("162.49"),
            "paid_amount": Decimal("130.00")
        }
        
        result = await optimizer.analyze_appeal_opportunity(
            claim_data, violation_data
        )
        
        assert "should_appeal" in result
        assert "success_probability" in result
        assert "expected_recovery" in result
        assert "roi_ratio" in result
        assert "priority_score" in result
        assert "recommended_strategy" in result
        
        assert 0 <= result["success_probability"] <= 100
        assert 1 <= result["priority_score"] <= 10
    
    @pytest.mark.asyncio
    async def test_prioritize_appeals(self, optimizer):
        """Test prioritizing multiple appeals"""
        violations = [
            {
                "claim": {"claim_id": f"CLAIM-{i}", "payer": "Aetna"},
                "delta": Decimal(f"{50 + i*10}.00")
            }
            for i in range(5)
        ]
        
        results = await optimizer.prioritize_appeals(violations)
        
        assert len(results) == 5
        
        # Should be sorted by priority (descending)
        priorities = [r["priority_score"] for r in results]
        assert priorities == sorted(priorities, reverse=True)
    
    @pytest.mark.asyncio
    async def test_high_value_appeal(self, optimizer):
        """Test that high-value appeals are recommended"""
        claim_data = {"claim_id": "CLAIM-001", "payer": "Medicare"}
        violation_data = {"delta": Decimal("500.00")}
        
        result = await optimizer.analyze_appeal_opportunity(
            claim_data, violation_data
        )
        
        # High value should be recommended
        assert result["should_appeal"] == True
        assert result["priority_score"] >= 7
    
    @pytest.mark.asyncio
    async def test_low_value_appeal(self, optimizer):
        """Test that low-value appeals may not be recommended"""
        claim_data = {"claim_id": "CLAIM-001", "payer": "Aetna"}
        violation_data = {"delta": Decimal("5.00")}
        
        result = await optimizer.analyze_appeal_opportunity(
            claim_data, violation_data
        )
        
        # Low value and low probability might not be worth appealing
        if not result["should_appeal"]:
            assert result["roi_ratio"] < 2.0 or result["success_probability"] < 30
