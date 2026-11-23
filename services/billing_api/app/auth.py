"""JWT (HS256) authentication. The subscriber identity always comes from the token `sub`."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.errors import ApiError

ROLE_SUBSCRIBER = "SUBSCRIBER"
ROLE_ADMIN = "ADMIN"

ISSUER = "billing-api"
AUDIENCE = "billing-clients"

_bearer = HTTPBearer(auto_error=False, description="JWT from POST /api/v1/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(subscriber_no: str, role: str) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": subscriber_no,
        "role": role,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), expires_in


@dataclass(frozen=True)
class Principal:
    subscriber_no: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


def _unauthorized(message: str) -> ApiError:
    return ApiError(401, "UNAUTHORIZED", message)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["sub", "role", "exp"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid token")
    if claims["role"] not in (ROLE_SUBSCRIBER, ROLE_ADMIN):
        raise _unauthorized("Invalid token role")
    return Principal(subscriber_no=claims["sub"], role=claims["role"])


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if not principal.is_admin:
        raise ApiError(403, "FORBIDDEN", "Administrator role required")
    return principal
