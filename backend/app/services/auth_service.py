"""
Regula Health - Authentication Service
User registration, login, and JWT token management
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import structlog
import uuid

from app.models import User, Organization
from app.schemas import UserRegister, UserLogin, Token
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)

logger = structlog.get_logger()


class AuthService:
    """Handle user authentication operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def register_user(self, user_data: UserRegister) -> Tuple[User, Token]:
        """
        Register a new user and create their organization
        
        Args:
            user_data: User registration data
            
        Returns:
            Tuple of (User, Token)
            
        Raises:
            HTTPException: If email already exists
        """
        # Check if user already exists
        stmt = select(User).where(User.email == user_data.email)
        result = await self.db.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create organization
        organization = Organization(
            id=uuid.uuid4(),
            name=user_data.organization_name,
            ein=user_data.ein,
            is_active=True,
            subscription_tier="solo"  # Default tier
        )
        self.db.add(organization)
        await self.db.flush()  # Get organization ID
        
        # Create user
        user = User(
            id=uuid.uuid4(),
            organization_id=organization.id,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            is_active=True,
            is_superuser=False,
            role="admin"  # First user in org is admin
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        # Generate tokens
        tokens = self._create_tokens(user)
        
        logger.info(
            "user_registered",
            user_id=str(user.id),
            email=user.email,
            organization_id=str(organization.id)
        )
        
        return user, tokens
    
    async def login(self, credentials: UserLogin) -> Token:
        """
        Authenticate user and return JWT tokens
        
        Args:
            credentials: User login credentials
            
        Returns:
            JWT tokens
            
        Raises:
            HTTPException: If credentials are invalid
        """
        # Find user by email
        stmt = select(User).where(User.email == credentials.email)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(credentials.password, user.hashed_password):
            logger.warning("failed_login_attempt", email=credentials.email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Check MFA if enabled
        if user.mfa_enabled:
            if not credentials.mfa_code:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MFA code required"
                )
            # MFA verification not yet implemented - block for security
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="MFA verification not yet implemented. Please disable MFA in database or implement pyotp verification."
            )
        
        # Generate tokens
        tokens = self._create_tokens(user)
        
        logger.info("user_logged_in", user_id=str(user.id), email=user.email)
        
        return tokens
    
    async def refresh_access_token(self, refresh_token: str) -> Token:
        """
        Issue new access token from valid refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token pair
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        payload = decode_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new tokens
        tokens = self._create_tokens(user)
        
        logger.info("token_refreshed", user_id=str(user.id))
        
        return tokens
    
    async def get_current_user(self, token: str) -> User:
        """
        Get current user from JWT token
        
        Args:
            token: JWT access token
            
        Returns:
            User object
            
        Raises:
            HTTPException: If token is invalid
        """
        payload = decode_token(token)
        
        if not payload or payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        
        # Get user from database
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        return user
    
    def _create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for user"""
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "org_id": str(user.organization_id),
            "role": user.role
        }
        
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )


async def get_auth_service(db: AsyncSession) -> AuthService:
    """Dependency injection for auth service"""
    return AuthService(db)
