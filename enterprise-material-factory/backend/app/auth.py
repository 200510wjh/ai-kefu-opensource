from __future__ import annotations

import base64
import hashlib
import hmac
import json
from fastapi import Depends, Header, HTTPException

from .config import get_settings
from .models import AuthSession, LoginRequest
from .store import store


def _sign(payload: bytes) -> str:
    secret = get_settings().secret_key.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def issue_token(user_id: str, tenant_id: str) -> str:
    payload = json.dumps({"user_id": user_id, "tenant_id": tenant_id}, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{encoded}.{_sign(encoded.encode('ascii'))}"


def parse_token(token: str) -> tuple[str, str]:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if not hmac.compare_digest(_sign(encoded.encode("ascii")), signature):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    padded = encoded + "=" * (-len(encoded) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    return str(payload["user_id"]), str(payload["tenant_id"])


def login(payload: LoginRequest) -> AuthSession:
    tenant = store.get_tenant_by_slug(payload.tenant_slug)
    if not tenant:
        raise HTTPException(status_code=401, detail="Unknown tenant")
    user = store.get_user_by_email(tenant.id, payload.email)
    if not user or payload.password != "demo123":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return AuthSession(token=issue_token(user.id, tenant.id), user=user, tenant=tenant)


def current_session(authorization: str | None = Header(default=None)) -> AuthSession:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user_id, tenant_id = parse_token(authorization.split(" ", 1)[1])
    user = store.users.get(user_id)
    tenant = store.tenants.get(tenant_id)
    if not user or not tenant:
        raise HTTPException(status_code=401, detail="Session not found")
    return AuthSession(token=authorization.split(" ", 1)[1], user=user, tenant=tenant)


SessionDep = Depends(current_session)
