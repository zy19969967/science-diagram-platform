from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import Request

from common.schemas import GatewayAuthStatus

AUTH_EXEMPT_PATHS = (
    "/api/health",
    "/assets",
    "/artifacts",
    "/docs",
    "/openapi.json",
    "/redoc",
)


@dataclass(frozen=True)
class GatewayAuthConfig:
    token: str = ""

    @property
    def enabled(self) -> bool:
        return bool(self.token.strip())

    def status(self) -> GatewayAuthStatus:
        return GatewayAuthStatus(
            enabled=self.enabled,
            exempt_paths=list(AUTH_EXEMPT_PATHS),
        )


def is_auth_exempt(path: str, method: str = "GET") -> bool:
    if method.upper() == "OPTIONS":
        return True
    for prefix in AUTH_EXEMPT_PATHS:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def bearer_token_from_header(value: str | None) -> str:
    if not value:
        return ""
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def request_is_authorized(request: Request, config: GatewayAuthConfig) -> bool:
    if not config.enabled or is_auth_exempt(request.url.path, request.method):
        return True

    expected = config.token.strip()
    presented = bearer_token_from_header(request.headers.get("authorization"))
    if not presented:
        presented = request.headers.get("x-api-token", "").strip()
    return bool(presented) and secrets.compare_digest(presented, expected)
