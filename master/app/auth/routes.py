"""
Authentication API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app.db.session import get_db
from app.users.models import User
from app.users.schemas import UserResponse
from app.audit import audit_log, AuditStatus
from app.playgrounds.service import PlaygroundService
from .service import AuthService

logger = logging.getLogger(__name__)
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    RefreshRequest,
    PasswordChangeRequest,
    ForgotPasswordRequest,
    ValidateResetTokenRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from .password_reset_service import PasswordResetService
from .dependencies import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Returns access and refresh tokens on success.
    """
    auth_service = AuthService(db)

    try:
        user, tokens = await auth_service.register(
            email=request.email,
            password=request.password,
            name=request.name,
            invite_code=request.invite_code,
        )

        # Audit log: successful registration
        await audit_log(
            db=db,
            request=req,
            action="auth.register",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            metadata={"email": request.email},
            status=AuditStatus.SUCCESS,
        )

    except ValueError as e:
        # Audit log: failed registration
        await audit_log(
            db=db,
            request=req,
            action="auth.register",
            metadata={"email": request.email, "reason": str(e)},
            status=AuditStatus.FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.

    Returns access and refresh tokens on success.
    """
    auth_service = AuthService(db)

    # Get client info
    user_agent = req.headers.get("user-agent")
    ip_address = req.client.host if req.client else None

    try:
        user, tokens = await auth_service.login(
            email=request.email,
            password=request.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # Audit log: successful login
        await audit_log(
            db=db,
            request=req,
            action="auth.login",
            user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            metadata={"method": "email", "email": request.email},
            status=AuditStatus.SUCCESS,
        )

    except ValueError as e:
        # Audit log: failed login
        await audit_log(
            db=db,
            request=req,
            action="auth.login",
            metadata={"method": "email", "email": request.email, "reason": str(e)},
            status=AuditStatus.FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Returns new access and refresh tokens.
    """
    auth_service = AuthService(db)

    try:
        tokens = await auth_service.refresh_tokens(request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        # Log the error and return a generic auth error
        import logging
        logging.getLogger(__name__).error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: RefreshRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Logout by revoking refresh token.
    """
    auth_service = AuthService(db)
    await auth_service.logout(request.refresh_token)

    # Stop running playground on logout
    try:
        playground_service = PlaygroundService(db)
        playground = await playground_service.get_by_user_id(current_user.id)
        if playground and playground.status.value == "running":
            await playground_service.stop(playground)
            logger.info(f"Stopped playground for user {current_user.id} on logout")
    except Exception as e:
        logger.warning(f"Failed to stop playground on logout: {e}")

    # Audit log: logout
    await audit_log(
        db=db,
        request=req,
        action="auth.logout",
        user_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        status=AuditStatus.SUCCESS,
    )

    return MessageResponse(message="Logged out successfully")




@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get current authenticated user info.
    """
    return current_user


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset email. Always returns 200 to prevent user enumeration.
    """
    service = PasswordResetService(db)
    await service.request_reset(email=request.email, base_url=request.base_url)
    await db.commit()
    return MessageResponse(message="If that email is registered, we've sent a password reset link.")


@router.post("/validate-reset-token")
async def validate_reset_token(
    request: ValidateResetTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Check whether a password reset token is still valid.
    """
    service = PasswordResetService(db)
    try:
        user = await service.validate_token(request.token)
        # Mask email: show first char + *** + @domain
        email = user.email
        at_idx = email.index("@")
        masked = email[0] + "***" + email[at_idx:]
        return {"valid": True, "email": masked}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using a valid token. The new_password is SHA-256 hashed by the client.
    """
    service = PasswordResetService(db)
    try:
        await service.reset_password(raw_token=request.token, new_password_hash=request.new_password)
        await db.commit()
        return MessageResponse(message="Password reset successfully")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


