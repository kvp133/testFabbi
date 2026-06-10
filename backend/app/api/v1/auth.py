import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_redis, security_scheme
from app.core.redis import RedisClient
from app.core.security import (
    create_access_token,
    create_refresh_token,
    revoked_token_key,
    verify_token,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services.auth_service import create_user, get_user_by_email

router = APIRouter()


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await create_user(db, user_data)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    user = await get_user_by_email(db, user_data.email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )

    from app.core.security import verify_password

    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
):
    """Refresh access token using refresh token."""
    payload = verify_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    jti = payload.get("jti")
    if jti and await redis.exists(revoked_token_key(jti)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    user_id = payload.get("sub")
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/logout")
async def logout(
    request: RefreshTokenRequest | None = None,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    current_user: User = Depends(get_current_user),
    redis: RedisClient = Depends(get_redis),
):
    """Logout user by revoking the access token (and refresh token if provided).

    Adds each token's JTI to a Redis blocklist with a TTL equal to the
    token's remaining lifetime. get_current_user consults the blocklist
    on every authenticated request.
    """
    await _revoke_token(redis, credentials.credentials)
    if request is not None and request.refresh_token:
        await _revoke_token(redis, request.refresh_token)
    return {"message": "Successfully logged out"}


async def _revoke_token(redis: RedisClient, token: str) -> None:
    payload = verify_token(token)
    if payload is None:
        return
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return
    remaining = int(exp - time.time())
    if remaining > 0:
        await redis.set(revoked_token_key(jti), "1", ex=remaining)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return current_user
