"""
Regula Health - Authentication API Endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import AuthService, get_auth_service
from app.schemas import Token, UserRegister, UserLogin, UserResponse
from app.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user"""
    auth_service = await get_auth_service(db)
    return await auth_service.get_current_user(token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user and organization
    
    Creates a new user account and their organization. The user becomes
    the admin of their organization.
    """
    auth_service = await get_auth_service(db)
    user, tokens = await auth_service.register_user(user_data)
    
    # Return user info (tokens available via /login)
    return user


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible token login
    
    Returns JWT access and refresh tokens for authenticated users.
    """
    auth_service = await get_auth_service(db)
    credentials = UserLogin(email=form_data.username, password=form_data.password)
    return await auth_service.login(credentials)


@router.post("/login", response_model=Token)
async def login_json(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    JSON login endpoint
    
    Alternative to OAuth2 token endpoint with JSON body.
    """
    auth_service = await get_auth_service(db)
    return await auth_service.login(credentials)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token
    
    Exchange a valid refresh token for a new access token.
    """
    auth_service = await get_auth_service(db)
    return await auth_service.refresh_access_token(refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    
    Returns the authenticated user's profile.
    """
    return current_user
