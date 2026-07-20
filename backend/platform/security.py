from __future__ import annotations

from typing import Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from backend.customer_service_saas import MerchantProfile, current_merchant


Permission = Literal[
    "enterprise:read",
    "enterprise:write",
    "crm:read",
    "crm:write",
    "knowledge:write",
    "automation:run",
    "settings:write",
    "team:write",
    "audit:read",
    "billing:read",
    "billing:write",
    "reports:read",
    "reports:write",
    "delivery:read",
    "delivery:write",
    "acceptance:read",
    "acceptance:run",
]


class AuthContext(BaseModel):
    merchant: MerchantProfile
    role: str = "owner"
    permissions: set[Permission] = {
        "enterprise:read",
        "enterprise:write",
        "crm:read",
        "crm:write",
        "knowledge:write",
        "automation:run",
        "settings:write",
        "team:write",
        "audit:read",
        "billing:read",
        "billing:write",
        "reports:read",
        "reports:write",
        "delivery:read",
        "delivery:write",
        "acceptance:read",
        "acceptance:run",
    }


def require_auth(merchant: MerchantProfile = Depends(current_merchant)) -> AuthContext:
    return AuthContext(merchant=merchant)


def require_permission(permission: Permission):
    def dependency(context: AuthContext = Depends(require_auth)) -> AuthContext:
        if permission not in context.permissions:
            raise HTTPException(status_code=403, detail="Permission denied")
        return context

    return dependency


def optional_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        return ""
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return authorization.split(" ", 1)[1].strip()
