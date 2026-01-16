"""
Regula Health - Pydantic Schemas
Request/response validation with type safety
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from uuid import UUID


# ============================================================================
# Authentication Schemas
# ============================================================================

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: Optional[str] = None
    exp: Optional[int] = None


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    mfa_code: Optional[str] = Field(None, min_length=6, max_length=6)


class UserRegister(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)
    organization_name: str = Field(..., min_length=2, max_length=255)
    ein: Optional[str] = Field(None, min_length=9, max_length=9)


class UserResponse(BaseModel):
    """User response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    role: str
    is_active: bool
    organization_id: UUID
    created_at: datetime


# ============================================================================
# Organization Schemas
# ============================================================================

class OrganizationBase(BaseModel):
    """Base organization schema"""
    name: str = Field(..., min_length=2, max_length=255)
    ein: Optional[str] = Field(None, min_length=9, max_length=9)
    address: Optional[Dict[str, Any]] = None


class OrganizationResponse(OrganizationBase):
    """Organization response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_active: bool
    subscription_tier: Optional[str]
    created_at: datetime


# ============================================================================
# Provider Schemas
# ============================================================================

class ProviderBase(BaseModel):
    """Base provider schema"""
    npi: str = Field(..., min_length=10, max_length=10)
    name: str = Field(..., min_length=2, max_length=255)
    specialty: Optional[str] = None
    geo_region: Optional[str] = Field(None, pattern="^(nyc|longisland|upstate)$")


class ProviderCreate(ProviderBase):
    """Provider creation request"""
    pass


class ProviderResponse(ProviderBase):
    """Provider response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    organization_id: UUID
    created_at: datetime


# ============================================================================
# Claim Schemas
# ============================================================================

class ClaimBase(BaseModel):
    """Base claim schema"""
    claim_id: str = Field(..., max_length=50)
    payer: str = Field(..., max_length=100)
    dos: date
    cpt_code: str = Field(..., max_length=10)
    billed_amount: Optional[Decimal] = None
    paid_amount: Decimal = Field(..., gt=0)


class ClaimResponse(ClaimBase):
    """Claim response with violation detection"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    provider_id: UUID
    mandate_rate: Decimal
    delta: Decimal
    is_violation: bool
    geo_adjustment_factor: Optional[Decimal]
    processing_date: Optional[datetime]
    created_at: datetime


class ClaimListResponse(BaseModel):
    """Paginated claim list response"""
    claims: List[ClaimResponse]
    total: int
    page: int
    per_page: int
    has_next: bool


class ClaimFilter(BaseModel):
    """Claim filtering parameters"""
    payer: Optional[str] = None
    cpt_code: Optional[str] = None
    dos_start: Optional[date] = None
    dos_end: Optional[date] = None
    is_violation: Optional[bool] = None
    min_delta: Optional[Decimal] = None


# ============================================================================
# Appeal Schemas
# ============================================================================

class AppealBase(BaseModel):
    """Base appeal schema"""
    appeal_type: str = Field(..., pattern="^(internal|external|dfs_complaint)$")
    notes: Optional[str] = None


class AppealCreate(AppealBase):
    """Appeal creation request"""
    claim_id: UUID


class AppealResponse(AppealBase):
    """Appeal response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    claim_id: UUID
    filed_date: date
    deadline: date
    status: str
    recovered_amount: Optional[Decimal]
    created_at: datetime


# ============================================================================
# Dashboard/Analytics Schemas
# ============================================================================

class DashboardMetrics(BaseModel):
    """Dashboard summary metrics"""
    total_claims: int
    violations: int
    violation_rate: float = Field(..., ge=0, le=100)
    total_recoverable: Decimal
    avg_underpayment: Decimal
    top_violators: List[Dict[str, Any]]
    recent_claims: List[ClaimResponse]


class PayerStats(BaseModel):
    """Payer-specific statistics"""
    payer: str
    total_claims: int
    violations: int
    violation_rate: float
    total_recoverable: Decimal


class TimeSeriesData(BaseModel):
    """Time series data for charts"""
    date: date
    violations: int
    recoverable: Decimal


# ============================================================================
# EDI Upload Schemas
# ============================================================================

class EDIUploadResponse(BaseModel):
    """EDI file upload response"""
    message: str
    file_name: str
    claims_processed: int
    violations_found: int
    processing_time_seconds: float


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    error_code: Optional[str] = None
