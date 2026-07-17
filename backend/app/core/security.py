"""
AuthN/AuthZ. See docs/security.md.

Key rule: tenant_id is ALWAYS read from the validated JWT claim, never from a request
body/query param -- a client cannot assert a different tenant to read another tenant's
data. In production, tokens are issued after OAuth2/OIDC login against a real IdP; this
module includes a dev-only `mint_dev_token` helper so the API is exercisable locally
without standing up a full IdP.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.config import settings
from app.models.schemas import Role


class AuthContext:
    def __init__(self, user_id: str, tenant_id: str, role: Role):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


def mint_dev_token(user_id: str, tenant_id: str, role: Role = Role.contributor) -> str:
    """Dev/demo-only helper. Production tokens are issued by the IdP after OAuth2/OIDC
    login, not minted here."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role.value,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


async def get_auth_context(authorization: str = Header(default="")) -> AuthContext:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decode(token)
    return AuthContext(user_id=payload["sub"], tenant_id=payload["tenant_id"], role=Role(payload["role"]))


ROLE_HIERARCHY = {
    Role.viewer: 0,
    Role.contributor: 1,
    Role.tenant_admin: 2,
    Role.platform_admin: 3,
}


def require_role(min_role: Role):
    def _check(ctx: AuthContext) -> AuthContext:
        if ROLE_HIERARCHY[ctx.role] < ROLE_HIERARCHY[min_role]:
            raise HTTPException(status_code=403, detail=f"requires role >= {min_role.value}")
        return ctx
    return _check
