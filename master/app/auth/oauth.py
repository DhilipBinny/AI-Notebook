"""
Google OAuth authentication routes.

Provides endpoints for:
- /auth/google - Redirect to Google OAuth
- /auth/google/callback - Handle Google OAuth callback
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.config import Config
import logging

from app.db.session import get_db
from app.core.config import settings
from app.users.models import OAuthProvider
from app.users.service import UserService
from app.users.schemas import UserCreateOAuth
from app.audit import audit_log, AuditStatus
from .jwt import create_token_pair
from .service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["OAuth"])

# Initialize OAuth client
oauth = OAuth()

# Register Google OAuth provider
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name='google',
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
    logger.info("Google OAuth configured")
else:
    logger.warning("Google OAuth not configured - missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")


@router.get("/google")
async def google_login(request: Request):
    """
    Initiate Google OAuth login flow.

    Redirects the user to Google's OAuth consent screen.
    After authentication, Google will redirect back to /auth/google/callback.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    # Build callback URL
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/auth/google/callback"

    logger.info(f"Google OAuth: Redirecting to Google (callback: {redirect_uri})")

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback.

    Google redirects here after user authenticates.
    This endpoint:
    1. Exchanges the authorization code for tokens
    2. Fetches user info from Google
    3. Creates or finds existing user
    4. Returns JWT tokens via redirect to frontend
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured"
        )

    try:
        # Exchange code for tokens and get user info
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            # If userinfo not in token, fetch it
            user_info = await oauth.google.userinfo(token=token)

        logger.info(f"Google OAuth: Received user info for {user_info.get('email')}")

    except OAuthError as e:
        logger.error(f"Google OAuth error: {e}")

        # Audit log: OAuth error
        await audit_log(
            db=db,
            request=request,
            action="auth.login_oauth",
            metadata={"provider": "google", "error": str(e)},
            status=AuditStatus.FAILED,
        )
        await db.commit()

        # Redirect to frontend with error
        frontend_url = settings.oauth_redirect_base_url
        return RedirectResponse(
            url=f"{frontend_url}/auth/login?error=oauth_failed&message={str(e)}"
        )

    # Extract user data from Google response
    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')
    picture = user_info.get('picture')

    if not email or not google_id:
        logger.error("Google OAuth: Missing email or sub in user info")
        frontend_url = settings.oauth_redirect_base_url
        return RedirectResponse(
            url=f"{frontend_url}/auth/login?error=oauth_failed&message=Missing+email+from+Google"
        )

    user_service = UserService(db)
    auth_service = AuthService(db)

    # Check if user exists by OAuth ID
    user = await user_service.get_by_oauth(OAuthProvider.GOOGLE, google_id)

    if user:
        # Existing OAuth user - update info if needed
        logger.info(f"Google OAuth: Found existing user {user.email}")
        if user.avatar_url != picture or user.name != name:
            user.avatar_url = picture
            user.name = name
            await db.flush()
    else:
        # Check if user exists by email (might have registered with password)
        existing_user = await user_service.get_by_email(email)

        if existing_user:
            # Link Google account to existing user
            if existing_user.oauth_provider == OAuthProvider.LOCAL:
                logger.info(f"Google OAuth: Linking Google to existing user {email}")
                existing_user.oauth_provider = OAuthProvider.GOOGLE
                existing_user.oauth_id = google_id
                existing_user.avatar_url = picture or existing_user.avatar_url
                existing_user.is_verified = True
                await db.flush()
                user = existing_user
            else:
                # User has different OAuth provider
                logger.warning(f"Google OAuth: User {email} already linked to {existing_user.oauth_provider}")
                frontend_url = settings.oauth_redirect_base_url
                return RedirectResponse(
                    url=f"{frontend_url}/auth/login?error=oauth_failed&message=Email+already+linked+to+another+provider"
                )
        else:
            # Create new user
            logger.info(f"Google OAuth: Creating new user {email}")
            user_data = UserCreateOAuth(
                email=email,
                name=name,
                oauth_provider=OAuthProvider.GOOGLE,
                oauth_id=google_id,
                avatar_url=picture,
            )
            user = await user_service.create_oauth(user_data)

    # Update last login
    await user_service.update_last_login(user)

    # Create JWT tokens
    tokens = create_token_pair(user.id)

    # Store refresh token session
    await auth_service._create_session(user.id, tokens.refresh_token)

    # Audit log: successful OAuth login
    await audit_log(
        db=db,
        request=request,
        action="auth.login_oauth",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        metadata={"provider": "google", "email": email},
        status=AuditStatus.SUCCESS,
    )

    # Commit the transaction (user, session, and audit log)
    await db.commit()

    # Redirect to frontend with tokens
    # Use oauth_redirect_base_url which is the main entry point (nginx)
    frontend_url = settings.oauth_redirect_base_url

    logger.info(f"Google OAuth: Successfully authenticated {email}, redirecting to frontend")

    return RedirectResponse(
        url=f"{frontend_url}/auth/callback?access_token={tokens.access_token}&refresh_token={tokens.refresh_token}"
    )


@router.get("/providers")
async def get_available_providers():
    """
    Get list of available OAuth providers.

    Returns which OAuth providers are configured and available for use.
    """
    providers = []

    if settings.google_client_id and settings.google_client_secret:
        providers.append({
            "name": "google",
            "display_name": "Google",
            "enabled": True
        })

    return {
        "providers": providers
    }
