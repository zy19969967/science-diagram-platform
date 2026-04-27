from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx

from common.init_logic import (
    FLUX_LOCAL_PROVIDER,
    FLUX_PROVIDERS,
    FLUX_REMOTE_PROVIDER,
    PROVIDER,
    build_init_candidates,
    score_and_rank_init_candidates,
)
from common.schemas import InitGenerateRequest, InitGenerateResponse

PostJsonFunc = Callable[[str, dict], Awaitable[dict]]


class InitProviderError(RuntimeError):
    pass


async def _post_json(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def _flux_generate_url(flux_init_url: str) -> str:
    normalized = flux_init_url.rstrip("/")
    if normalized.endswith("/generate") or normalized.endswith("/api/init-generate"):
        return normalized
    return f"{normalized}/generate"


def _requires_flux_service(provider: str) -> bool:
    return provider in FLUX_PROVIDERS


def _fallback_response(payload: InitGenerateRequest, warnings: list[str]) -> InitGenerateResponse:
    response = build_init_candidates(payload.model_copy(update={"provider": "deterministic-fallback"}))
    return response.model_copy(
        update={
            "requested_provider": payload.provider,
            "used_provider": PROVIDER,
            "fallback_used": True,
            "warnings": [*response.warnings, *warnings],
        }
    )


async def _generate_with_flux_service(
    payload: InitGenerateRequest,
    *,
    flux_init_url: str,
    post_json_func: PostJsonFunc,
) -> InitGenerateResponse:
    data = await post_json_func(_flux_generate_url(flux_init_url), payload.model_dump())
    response = InitGenerateResponse.model_validate(data)
    provider = response.provider if response.provider in FLUX_PROVIDERS else FLUX_REMOTE_PROVIDER
    if payload.provider == FLUX_LOCAL_PROVIDER:
        provider = FLUX_LOCAL_PROVIDER
    if payload.provider == FLUX_REMOTE_PROVIDER:
        provider = FLUX_REMOTE_PROVIDER
    response = response.model_copy(
        update={
            "provider": provider,
            "requested_provider": payload.provider,
            "used_provider": provider,
            "fallback_used": False,
            "warnings": response.warnings,
        }
    )
    return score_and_rank_init_candidates(response)


async def generate_initial_candidates(
    payload: InitGenerateRequest,
    *,
    flux_init_url: str | None,
    post_json_func: PostJsonFunc = _post_json,
) -> InitGenerateResponse:
    provider = payload.provider
    configured_url = (flux_init_url or "").strip()

    if provider == "deterministic-fallback":
        response = build_init_candidates(payload)
        return response.model_copy(update={"requested_provider": provider, "used_provider": PROVIDER, "fallback_used": False})

    if not configured_url:
        if _requires_flux_service(provider):
            raise InitProviderError(f"FLUX_INIT_URL is required when provider is {provider}.")
        return _fallback_response(payload, ["FLUX_INIT_URL is not configured; using deterministic fallback candidates."])

    try:
        return await _generate_with_flux_service(payload, flux_init_url=configured_url, post_json_func=post_json_func)
    except Exception as exc:
        if _requires_flux_service(provider):
            raise InitProviderError(f"FLUX initial-canvas service is unavailable: {exc}") from exc
        return _fallback_response(payload, [f"FLUX provider failed; using deterministic fallback candidates: {exc}"])
