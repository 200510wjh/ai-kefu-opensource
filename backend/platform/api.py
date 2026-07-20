from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


logger = logging.getLogger("merchant_ops.api")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    ok: bool
    data: Any = None
    error: ApiError | None = None
    request_id: str
    elapsed_ms: int | None = None


def request_id_for(request: Request | None) -> str:
    if request is not None and hasattr(request.state, "request_id"):
        return str(request.state.request_id)
    return str(uuid.uuid4())


def success_response(data: Any, request: Request | None = None, status_code: int = 200) -> JSONResponse:
    payload = ApiResponse(ok=True, data=jsonable_encoder(data), request_id=request_id_for(request))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def error_response(
    code: str,
    message: str,
    request: Request | None = None,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ApiResponse(
        ok=False,
        error=ApiError(code=code, message=message, details=details or {}),
        request_id=request_id_for(request),
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


async def request_context_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Unhandled request error", extra={"request_id": request.state.request_id, "path": request.url.path, "elapsed_ms": elapsed_ms})
        raise
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    logger.info(
        "request completed",
        extra={
            "request_id": request.state.request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        },
    )
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if request.url.path.startswith("/api/v1"):
        return error_response("HTTP_ERROR", str(exc.detail), request=request, status_code=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception", extra={"request_id": request_id_for(request), "path": request.url.path})
    if request.url.path.startswith("/api/v1"):
        return error_response("INTERNAL_ERROR", "服务暂时不可用，请稍后重试。", request=request, status_code=500)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
