"""
Regula Health - Main FastAPI Application
Enterprise-grade healthcare compliance platform
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import structlog
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import init_db, close_db
from app.api.v1 import auth, claims, analytics

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management

    Handles startup and shutdown tasks
    """
    # Startup
    logger.info("application_starting", environment=settings.ENVIRONMENT)

    # Initialize database
    await init_db()
    logger.info("database_initialized")

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await close_db()


# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="NY Medicaid Rate Compliance Engine - Enterprise Healthcare Platform",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)


# ============================================================================
# Middleware Configuration
# ============================================================================

# CORS - Allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "X-Total-Count"],
)

# Trusted Host (security)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["regula.health", "*.regula.health"]
    )


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler

    Prevents stack trace leakage in production
    """
    logger.error(
        "unhandled_exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )

    if settings.is_production:
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
    else:
        return JSONResponse(status_code=500, content={"detail": str(exc)})


# ============================================================================
# API Routes
# ============================================================================

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(claims.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)


# Health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint

    Returns application status for monitoring
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint

    Returns API information
    """
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
        "status": "operational",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
    )
