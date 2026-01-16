"""
Partner API Endpoints

REST API endpoints for partner integrations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import date, datetime
from decimal import Decimal

from .auth import APIKeyAuth, UsageMetering, RateLimiter
from ..payer_adapters import get_payer_adapter, PayerAdapterError
from ..risk_engine import PredictiveUnderpaymentScorer, AppealSuccessOptimizer

import structlog

logger = structlog.get_logger()

router = APIRouter()


# Request/Response Models

class ClaimCheckRequest(BaseModel):
    """Request to check a single claim"""
    claim_id: str = Field(..., description="Unique claim identifier")
    payer: str = Field(..., description="Payer name (e.g., 'Aetna', 'Medicare')")
    cpt_code: str = Field(..., description="CPT procedure code")
    paid_amount: float = Field(..., description="Amount paid by payer")
    service_date: str = Field(..., description="Date of service (ISO format)")
    geo_region: Optional[str] = Field(None, description="Geographic region")
    modifiers: Optional[List[str]] = Field(None, description="CPT modifiers")


class BatchCheckRequest(BaseModel):
    """Request to check multiple claims"""
    claims: List[ClaimCheckRequest] = Field(..., description="List of claims to check")
    callback_url: Optional[str] = Field(None, description="Webhook URL for results")


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check"""
    claim_id: str
    is_violation: bool
    allowed_amount: Optional[float]
    paid_amount: float
    underpayment: Optional[float]
    violation_codes: List[str]
    reason: Optional[str]
    risk_score: Optional[float]


# Endpoints

@router.post("/compliance/check", response_model=ComplianceCheckResponse)
async def check_claim_compliance(
    request: ClaimCheckRequest,
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Check a single claim for compliance violations
    
    Performs:
    1. Payer adapter lookup
    2. Underpayment detection
    3. Risk scoring
    
    **Rate Limit**: Varies by tier (Basic: 100/min, Enterprise: 1000/min)
    
    **Cost**: $0.10 per check (Basic tier)
    """
    # Check rate limit
    await RateLimiter.check_and_consume(
        partner_info["partner_id"],
        partner_info["rate_limit"]
    )
    
    # Check feature access
    if not await APIKeyAuth.check_feature_access(partner_info, "compliance_check"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compliance check not available in your plan"
        )
    
    try:
        # Get payer adapter
        adapter = get_payer_adapter(request.payer)
        
        # Detect underpayment
        service_date = datetime.fromisoformat(request.service_date).date()
        violation = await adapter.detect_underpayment(
            cpt_code=request.cpt_code,
            paid_amount=Decimal(str(request.paid_amount)),
            service_date=service_date,
            modifiers=request.modifiers,
            geo_region=request.geo_region
        )
        
        # Get risk score
        scorer = PredictiveUnderpaymentScorer()
        risk_analysis = await scorer.score_claim({
            "claim_id": request.claim_id,
            "payer": request.payer,
            "cpt_code": request.cpt_code,
            "paid_amount": request.paid_amount,
            "service_date": service_date,
            "expected_amount": float(violation.get("allowed_amount", 0))
        })
        
        # Record usage
        await UsageMetering.record_usage(
            partner_id=partner_info["partner_id"],
            endpoint="compliance_check",
            claims_processed=1
        )
        
        return ComplianceCheckResponse(
            claim_id=request.claim_id,
            is_violation=violation["is_violation"],
            allowed_amount=float(violation["allowed_amount"]) if violation["allowed_amount"] else None,
            paid_amount=request.paid_amount,
            underpayment=float(violation["delta"]) if violation["delta"] else None,
            violation_codes=violation.get("violation_codes", []),
            reason=violation.get("reason"),
            risk_score=risk_analysis.get("risk_score")
        )
        
    except PayerAdapterError as e:
        logger.warning("payer_adapter_error", error=str(e), payer=request.payer)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payer not supported: {request.payer}"
        )
    except Exception as e:
        logger.error("compliance_check_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing compliance check"
        )


@router.post("/compliance/batch", response_model=Dict)
async def batch_compliance_check(
    request: BatchCheckRequest,
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Check multiple claims in a single request
    
    **Async Processing**: Large batches (>100 claims) are processed asynchronously.
    Results delivered via webhook if callback_url provided.
    
    **Rate Limit**: 10 batch requests per minute
    
    **Cost**: $0.08 per claim (volume discount)
    """
    # Check feature access
    if not await APIKeyAuth.check_feature_access(partner_info, "batch_analysis"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Batch analysis not available in your plan"
        )
    
    # Limit batch size
    if len(request.claims) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size limited to 1000 claims"
        )
    
    # Process small batches synchronously
    if len(request.claims) <= 100:
        results = []
        for claim_req in request.claims:
            try:
                result = await check_claim_compliance(claim_req, partner_info)
                results.append(result.dict())
            except HTTPException as e:
                results.append({
                    "claim_id": claim_req.claim_id,
                    "error": e.detail
                })
        
        # Record usage
        await UsageMetering.record_usage(
            partner_id=partner_info["partner_id"],
            endpoint="batch_check",
            claims_processed=len(request.claims)
        )
        
        return {
            "status": "completed",
            "claims_processed": len(request.claims),
            "results": results
        }
    
    # Large batches: queue for async processing
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # In production, queue to Celery/Redis
    logger.info(
        "batch_queued",
        batch_id=batch_id,
        partner_id=partner_info["partner_id"],
        count=len(request.claims)
    )
    
    return {
        "status": "queued",
        "batch_id": batch_id,
        "claims_count": len(request.claims),
        "estimated_completion": "5-10 minutes",
        "callback_url": request.callback_url
    }


@router.get("/usage", response_model=Dict)
async def get_usage_stats(
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Get API usage statistics and billing information
    
    Returns:
    - Total API calls
    - Claims processed
    - Cost breakdown
    - Rate limit status
    """
    usage = await UsageMetering.get_usage_summary(partner_info["partner_id"])
    
    return {
        "partner_id": partner_info["partner_id"],
        "partner_name": partner_info["partner_name"],
        "tier": partner_info["tier"],
        "rate_limit": f"{partner_info['rate_limit']} requests/minute",
        "usage": usage
    }


@router.get("/payers", response_model=Dict)
async def list_supported_payers(
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Get list of supported payers
    
    Returns payer names and their capabilities
    """
    from ..payer_adapters import PayerAdapterFactory
    
    supported_payers = PayerAdapterFactory.list_supported_payers()
    
    return {
        "supported_payers": supported_payers,
        "total_count": len(supported_payers),
        "categories": {
            "medicare": ["cms_medicare"],
            "medicaid": ["ny_medicaid"],
            "commercial": ["aetna"]
        }
    }


@router.post("/webhook/register", response_model=Dict)
async def register_webhook(
    webhook_url: str,
    events: List[str],
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Register webhook for event notifications
    
    **Available Events**:
    - `violation.detected` - New compliance violation found
    - `batch.completed` - Batch processing completed
    - `appeal.filed` - Appeal submitted to payer
    - `appeal.resolved` - Appeal decision received
    
    **Enterprise Feature**: Webhooks only available on Enterprise tier
    """
    # Check feature access
    if not await APIKeyAuth.check_feature_access(partner_info, "webhook"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhooks not available in your plan. Upgrade to Enterprise."
        )
    
    # In production, store in database
    webhook_id = f"webhook_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    logger.info(
        "webhook_registered",
        partner_id=partner_info["partner_id"],
        webhook_id=webhook_id,
        url=webhook_url,
        events=events
    )
    
    return {
        "webhook_id": webhook_id,
        "url": webhook_url,
        "events": events,
        "status": "active",
        "created_at": datetime.now().isoformat()
    }


@router.get("/appeal/analyze", response_model=Dict)
async def analyze_appeal_opportunity(
    claim_id: str,
    underpayment_amount: float,
    payer: str,
    cpt_code: str,
    partner_info: Dict = Depends(APIKeyAuth.validate_api_key)
):
    """
    Analyze appeal success probability and ROI
    
    Returns:
    - Success probability
    - Expected recovery
    - ROI ratio
    - Recommended strategy
    """
    optimizer = AppealSuccessOptimizer()
    
    claim_data = {
        "claim_id": claim_id,
        "payer": payer,
        "cpt_code": cpt_code
    }
    
    violation_data = {
        "delta": Decimal(str(underpayment_amount))
    }
    
    analysis = await optimizer.analyze_appeal_opportunity(
        claim_data, violation_data
    )
    
    # Record usage
    await UsageMetering.record_usage(
        partner_id=partner_info["partner_id"],
        endpoint="appeal_analysis",
        claims_processed=1
    )
    
    return analysis
