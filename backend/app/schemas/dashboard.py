"""
Enhanced Dashboard Schemas

Schemas for the production-grade analytics dashboard
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Executive Metrics Schemas
# ============================================================================


class TrendData(BaseModel):
    """Trend information for metrics"""

    value: float
    direction: str = Field(..., pattern="^(up|down|neutral)$")
    benchmark: Optional[str] = None


class ExecutiveMetricCard(BaseModel):
    """Individual executive metric card"""

    label: str
    value: str  # Formatted string (e.g., "$427,850" or "12,473")
    raw_value: float  # Numeric value for calculations
    trend: Optional[TrendData] = None
    processing: bool = False  # Real-time indicator
    sparkline: Optional[List[float]] = None  # 30-day mini-chart data


class RecoveryPipelineMetrics(BaseModel):
    """Recovery pipeline breakdown"""

    in_appeal: Decimal
    recovered: Decimal
    success_rate: float = Field(..., ge=0, le=100)
    pending_count: int


class ExecutiveMetrics(BaseModel):
    """Executive command center metrics"""

    total_recoverable: ExecutiveMetricCard
    claims_processed: ExecutiveMetricCard
    underpayment_violations: ExecutiveMetricCard
    recovery_pipeline: RecoveryPipelineMetrics


# ============================================================================
# Geographic Violation Schemas
# ============================================================================


class GeographicViolation(BaseModel):
    """Geographic region violation data"""

    region: str = Field(..., pattern="^(NYC|LONG_ISLAND|UPSTATE)$")
    rate_multiplier: Decimal
    violation_count: int
    total_amount: Decimal
    violation_rate: float
    top_payers: List[Dict[str, Any]]
    provider_count: int


class GeographicBreakdown(BaseModel):
    """Full geographic violation breakdown"""

    regions: List[GeographicViolation]
    total_violations: int
    total_amount: Decimal


# ============================================================================
# Payer Performance Schemas
# ============================================================================


class PayerPerformance(BaseModel):
    """Payer performance metrics"""

    payer_name: str
    total_claims: int
    violations: int
    violation_rate: float = Field(..., ge=0, le=100)
    total_recoverable: Decimal
    avg_variance: Decimal
    severity_score: Optional[float] = Field(None, ge=0, le=100)
    trend_12mo: Optional[List[Dict[str, Any]]] = None


class PayerPerformanceMatrix(BaseModel):
    """Payer performance matrix response"""

    payers: List[PayerPerformance]
    total_payers: int
    filters_applied: Dict[str, Any]


# ============================================================================
# Claims Explorer Schemas
# ============================================================================


class ClaimDetail(BaseModel):
    """Detailed claim information"""

    id: str
    claim_id: str
    dos: date
    patient_id: str  # Anonymized
    cpt_code: str
    cpt_description: Optional[str]
    provider: str
    payer: str
    billed_amount: Decimal
    mandate_rate: Decimal
    paid_amount: Decimal
    variance: Decimal
    status: str
    geo_region: Optional[str]
    rate_multiplier: Optional[Decimal]
    cola_adjustment: Optional[Decimal]
    appeal_status: Optional[str]


class ClaimsExplorerResponse(BaseModel):
    """Claims explorer paginated response"""

    claims: List[ClaimDetail]
    total: int
    page: int
    per_page: int
    has_next: bool
    summary: Dict[str, Any]


# ============================================================================
# Recovery Analytics Schemas
# ============================================================================


class MonthlyRecoveryTrend(BaseModel):
    """Monthly recovery trend data"""

    month: str  # YYYY-MM format
    recoverable_identified: Decimal
    amount_recovered: Decimal
    recovery_rate: float
    gap_amount: Decimal


class CPTPerformance(BaseModel):
    """CPT code performance bubble chart data"""

    cpt_code: str
    description: str
    violation_frequency: int
    avg_underpayment: Decimal
    total_recoverable: Decimal
    payer_category: str


class RecoveryFunnelStage(BaseModel):
    """Recovery funnel stage data"""

    stage: str
    count: int
    conversion_rate: float
    avg_days: Optional[float]


class RecoveryAnalytics(BaseModel):
    """Comprehensive recovery analytics"""

    monthly_trends: List[MonthlyRecoveryTrend]
    cpt_performance: List[CPTPerformance]
    recovery_funnel: List[RecoveryFunnelStage]
    forecast_3mo: List[Dict[str, Any]]


# ============================================================================
# Enhanced Dashboard Response
# ============================================================================


class EnhancedDashboardResponse(BaseModel):
    """Complete enhanced dashboard data"""

    executive_metrics: ExecutiveMetrics
    geographic_breakdown: GeographicBreakdown
    top_payers: List[PayerPerformance]
    recent_violations: List[ClaimDetail]
    recovery_analytics: RecoveryAnalytics
    processing_stats: Dict[str, Any]
    timestamp: datetime
