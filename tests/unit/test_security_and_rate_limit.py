import pytest

from app.core.rate_limiter import TokenBucket
from app.core.security import ROLE_HIERARCHY, AuthContext, require_role
from app.models.schemas import Role


def test_token_bucket_denies_after_capacity_exhausted():
    bucket = TokenBucket(capacity=3, refill_per_minute=0)  # no refill during the test
    assert bucket.try_consume()
    assert bucket.try_consume()
    assert bucket.try_consume()
    assert not bucket.try_consume()


def test_role_hierarchy_allows_higher_roles():
    ctx = AuthContext(user_id="u1", tenant_id="acme", role=Role.tenant_admin)
    checked = require_role(Role.contributor)(ctx)
    assert checked is ctx


def test_role_hierarchy_denies_lower_roles():
    from fastapi import HTTPException
    ctx = AuthContext(user_id="u1", tenant_id="acme", role=Role.viewer)
    with pytest.raises(HTTPException):
        require_role(Role.tenant_admin)(ctx)


def test_role_hierarchy_ordering():
    assert ROLE_HIERARCHY[Role.platform_admin] > ROLE_HIERARCHY[Role.tenant_admin]
    assert ROLE_HIERARCHY[Role.tenant_admin] > ROLE_HIERARCHY[Role.contributor]
    assert ROLE_HIERARCHY[Role.contributor] > ROLE_HIERARCHY[Role.viewer]
