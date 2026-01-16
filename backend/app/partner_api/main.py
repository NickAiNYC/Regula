"""
Partner API - Main Application

FastAPI application for partner integrations.
Separate from main API with its own authentication and rate limiting.
"""

from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import structlog

from .auth import APIKeyAuth, UsageMetering
from .endpoints import router as partner_router

logger = structlog.get_logger()


def create_partner_app() -> FastAPI:
    """
    Create Partner API FastAPI application
    
    Separate app instance for:
    - B2B partner integrations
    - White-label deployments
    - API marketplace
    """
    app = FastAPI(
        title="Regula Intelligence Partner API",
        description="B2B API for revenue integrity and compliance checking",
        version="1.0.0",
        docs_url="/partner/docs",
        redoc_url="/partner/redoc",
        openapi_url="/partner/openapi.json"
    )
    
    # CORS - restrictive for partner API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, whitelist partner domains
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    # Include partner endpoints
    app.include_router(partner_router, prefix="/api/v1/partner", tags=["partner"])
    
    @app.get("/partner/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "partner-api"}
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("partner_api_started")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("partner_api_shutdown")
    
    return app


# Create app instance
partner_app = create_partner_app()
