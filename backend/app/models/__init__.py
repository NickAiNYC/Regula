"""
Regula Health - Database Models
SQLAlchemy models with multi-tenant Row-Level Security
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Column, String, Numeric, Boolean, DateTime, Date, Text, Integer,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Organization(Base, TimestampMixin):
    """Organization/Tenant model for multi-tenancy"""
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    ein = Column(String(9), unique=True)  # Employer Identification Number
    address = Column(JSONB)
    is_active = Column(Boolean, default=True, nullable=False)
    subscription_tier = Column(String(50))  # solo, group, enterprise
    
    # Relationships
    users = relationship("User", back_populates="organization")
    providers = relationship("Provider", back_populates="organization")


class User(Base, TimestampMixin):
    """User authentication model"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    role = Column(String(50), default="user")  # admin, provider, analyst, auditor
    
    # MFA
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(32))
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_org", "organization_id"),
    )


class Provider(Base, TimestampMixin):
    """Healthcare provider model"""
    __tablename__ = "providers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    npi = Column(String(10), unique=True, nullable=False)  # National Provider Identifier
    name = Column(String(255), nullable=False)
    specialty = Column(String(100))
    geo_region = Column(String(20))  # nyc, longisland, upstate
    
    # Relationships
    organization = relationship("Organization", back_populates="providers")
    claims = relationship("Claim", back_populates="provider")
    
    __table_args__ = (
        Index("idx_provider_npi", "npi"),
        Index("idx_provider_org", "organization_id"),
    )


class Claim(Base, TimestampMixin):
    """Claims processing model with violation detection"""
    __tablename__ = "claims"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("providers.id"), nullable=False)
    
    # EDI 835 data
    claim_id = Column(String(50), nullable=False)
    payer = Column(String(100), nullable=False)
    payer_id = Column(String(50))
    dos = Column(Date, nullable=False)  # Date of service
    cpt_code = Column(String(10), nullable=False)
    units = Column(Integer, default=1)
    
    # Financial
    billed_amount = Column(Numeric(10, 2))
    mandate_rate = Column(Numeric(10, 2), nullable=False)
    paid_amount = Column(Numeric(10, 2), nullable=False)
    delta = Column(Numeric(10, 2), nullable=False)  # mandate_rate - paid_amount
    is_violation = Column(Boolean, nullable=False)
    
    # Geographic adjustment
    geo_adjustment_factor = Column(Numeric(5, 3))  # 1.065 for NYC, 1.025 for LI, 1.0 for upstate
    cola_year = Column(Integer)
    
    # Processing metadata
    processing_date = Column(DateTime(timezone=True))
    edi_file_name = Column(String(255))
    
    # PHI (encrypted)
    patient_name_encrypted = Column(Text)  # AES-256 encrypted
    member_id_hash = Column(String(16))  # One-way hash for deidentification
    
    # Relationships
    provider = relationship("Provider", back_populates="claims")
    appeals = relationship("Appeal", back_populates="claim")
    
    __table_args__ = (
        Index("idx_claim_provider_dos", "provider_id", "dos"),
        Index("idx_claim_payer_violation", "payer", "is_violation"),
        Index("idx_claim_dos", "dos"),
        Index("idx_claim_violation", "is_violation"),
        CheckConstraint("delta = mandate_rate - paid_amount", name="check_delta_calculation"),
    )


class Appeal(Base, TimestampMixin):
    """Appeal tracking for underpayment violations"""
    __tablename__ = "appeals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    
    appeal_type = Column(String(50))  # internal, external, dfs_complaint
    filed_date = Column(Date, nullable=False)
    deadline = Column(Date, nullable=False)
    status = Column(String(50), default="pending")  # pending, approved, denied, withdrawn
    
    recovered_amount = Column(Numeric(10, 2))
    notes = Column(Text)
    documents = Column(JSONB)  # Array of S3 URLs
    
    # Relationships
    claim = relationship("Claim", back_populates="appeals")
    
    __table_args__ = (
        Index("idx_appeal_status", "status"),
        Index("idx_appeal_deadline", "deadline"),
    )


class RateDatabase(Base, TimestampMixin):
    """NY Medicaid rate database with COLA adjustments"""
    __tablename__ = "rate_database"
    
    cpt_code = Column(String(10), primary_key=True)
    description = Column(Text, nullable=False)
    category = Column(String(50))  # psychotherapy, diagnostic, medication_management
    
    # Rates
    base_rate_2024 = Column(Numeric(10, 2), nullable=False)
    cola_rate_2025 = Column(Numeric(10, 2), nullable=False)
    cola_rate_2026 = Column(Numeric(10, 2))
    
    effective_date = Column(Date, nullable=False)
    source = Column(String(255))  # Regulatory citation
    
    __table_args__ = (
        Index("idx_rate_cpt", "cpt_code"),
    )


class AuditLog(Base):
    """Comprehensive audit trail for HIPAA compliance"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    action = Column(String(100), nullable=False)  # CREATE, READ, UPDATE, DELETE
    resource_type = Column(String(50))  # claim, user, appeal
    resource_id = Column(UUID(as_uuid=True))
    
    # Request metadata
    ip_address = Column(INET)
    user_agent = Column(Text)
    request_method = Column(String(10))
    request_path = Column(String(255))
    
    # Change tracking
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    
    metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created", "created_at"),
    )
