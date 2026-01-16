"""
Regula Health - Claims API Endpoints
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, UploadFile, File, Query, BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from redis.asyncio import Redis
import structlog
from uuid import UUID
from decimal import Decimal
import time

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models import User, Claim, Provider
from app.schemas import (
    ClaimResponse, ClaimListResponse, EDIUploadResponse,
    ClaimFilter, ErrorResponse
)
from app.services.edi_parser import edi_parser
from app.services.rate_engine import RateEngine

router = APIRouter(prefix="/claims", tags=["Claims"])
logger = structlog.get_logger()


async def get_redis():
    """Get Redis connection"""
    from contextlib import asynccontextmanager
    redis = Redis.from_url("redis://localhost:6379/0", decode_responses=False)
    try:
        yield redis
    finally:
        await redis.aclose()


@router.post("/upload", response_model=EDIUploadResponse)
async def upload_edi_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Upload and process EDI 835 file
    
    Parses Electronic Remittance Advice files and detects parity violations.
    Performance target: 10,000+ claims/second
    """
    start_time = time.time()
    
    # Read file content
    content = await file.read()
    file_content = content.decode('utf-8')
    
    # Parse EDI file
    parsed_claims = await edi_parser.parse_file(file_content)
    
    if not parsed_claims:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No claims found in EDI file"
        )
    
    # Get first provider for this org (in production, map by NPI)
    stmt = select(Provider).where(
        Provider.organization_id == current_user.organization_id
    ).limit(1)
    result = await db.execute(stmt)
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No provider found. Please create a provider first."
        )
    
    # Process claims with rate engine
    rate_engine = RateEngine(db, redis)
    violations_count = 0
    
    for claim_data in parsed_claims:
        # Skip if no date of service
        if not claim_data.get("dos"):
            continue
        
        # Detect violation
        violation_info = await rate_engine.detect_violation(
            cpt_code=claim_data["cpt_code"],
            paid_amount=claim_data["paid_amount"],
            service_date=claim_data["dos"],
            geo_region=provider.geo_region or "upstate"
        )
        
        # Only save if rate was found
        if violation_info["mandate_rate"] is not None:
            claim = Claim(
                provider_id=provider.id,
                claim_id=claim_data["claim_id"],
                payer=claim_data["payer"],
                payer_id=claim_data.get("payer_id"),
                dos=claim_data["dos"],
                cpt_code=claim_data["cpt_code"],
                units=claim_data.get("units", 1),
                billed_amount=claim_data.get("billed_amount"),
                mandate_rate=violation_info["mandate_rate"],
                paid_amount=claim_data["paid_amount"],
                delta=violation_info["delta"],
                is_violation=violation_info["is_violation"],
                geo_adjustment_factor=violation_info["geo_adjustment_factor"],
                edi_file_name=file.filename
            )
            db.add(claim)
            
            if violation_info["is_violation"]:
                violations_count += 1
    
    await db.commit()
    
    processing_time = time.time() - start_time
    
    logger.info(
        "edi_file_processed",
        user_id=str(current_user.id),
        file_name=file.filename,
        claims_processed=len(parsed_claims),
        violations_found=violations_count,
        processing_time_seconds=processing_time
    )
    
    return EDIUploadResponse(
        message=f"Successfully processed {len(parsed_claims)} claims",
        file_name=file.filename,
        claims_processed=len(parsed_claims),
        violations_found=violations_count,
        processing_time_seconds=round(processing_time, 2)
    )


@router.get("", response_model=ClaimListResponse)
async def get_claims(
    payer: Optional[str] = None,
    cpt_code: Optional[str] = None,
    dos_start: Optional[date] = None,
    dos_end: Optional[date] = None,
    is_violation: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get claims with filtering and pagination
    
    Returns claims for the current user's organization.
    """
    # Build query filters
    filters = []
    
    # Filter by organization (multi-tenancy)
    stmt = select(Provider.id).where(
        Provider.organization_id == current_user.organization_id
    )
    result = await db.execute(stmt)
    provider_ids = [row[0] for row in result.fetchall()]
    
    if provider_ids:
        filters.append(Claim.provider_id.in_(provider_ids))
    else:
        # No providers = no claims
        return ClaimListResponse(claims=[], total=0, page=page, per_page=per_page, has_next=False)
    
    # Apply filters
    if payer:
        filters.append(Claim.payer.ilike(f"%{payer}%"))
    if cpt_code:
        filters.append(Claim.cpt_code == cpt_code)
    if dos_start:
        filters.append(Claim.dos >= dos_start)
    if dos_end:
        filters.append(Claim.dos <= dos_end)
    if is_violation is not None:
        filters.append(Claim.is_violation == is_violation)
    
    # Count total
    count_stmt = select(func.count(Claim.id)).where(and_(*filters))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    # Get paginated claims
    offset = (page - 1) * per_page
    claims_stmt = (
        select(Claim)
        .where(and_(*filters))
        .order_by(Claim.dos.desc())
        .offset(offset)
        .limit(per_page)
    )
    claims_result = await db.execute(claims_stmt)
    claims = claims_result.scalars().all()
    
    has_next = (offset + per_page) < total
    
    return ClaimListResponse(
        claims=claims,
        total=total,
        page=page,
        per_page=per_page,
        has_next=has_next
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific claim by ID"""
    stmt = select(Claim).where(Claim.id == claim_id)
    result = await db.execute(stmt)
    claim = result.scalar_one_or_none()
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found"
        )
    
    # Verify user has access (multi-tenancy check)
    provider_stmt = select(Provider).where(Provider.id == claim.provider_id)
    provider_result = await db.execute(provider_stmt)
    provider = provider_result.scalar_one()
    
    if provider.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return claim
