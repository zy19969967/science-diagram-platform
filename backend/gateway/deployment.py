from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from common.schemas import (
    DeploymentReadinessCheck,
    DeploymentReadinessResponse,
    GatewayAuthStatus,
    ReadinessStatus,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def directory_check(name: str, path: Path) -> DeploymentReadinessCheck:
    if path.exists() and path.is_dir():
        return DeploymentReadinessCheck(name=name, status="pass", detail=str(path))
    return DeploymentReadinessCheck(name=name, status="fail", detail=f"Directory is missing: {path}")


def service_url_check(name: str, url: str) -> DeploymentReadinessCheck:
    if url.startswith("http://") or url.startswith("https://"):
        return DeploymentReadinessCheck(name=name, status="pass", detail=url)
    return DeploymentReadinessCheck(name=name, status="warn", detail=f"Service URL is not HTTP(S): {url or 'empty'}")


def traceability_check(path: Path) -> DeploymentReadinessCheck:
    if path.exists() and path.is_file():
        return DeploymentReadinessCheck(name="traceability_matrix", status="pass", detail=str(path))
    return DeploymentReadinessCheck(name="traceability_matrix", status="fail", detail=f"Missing traceability matrix: {path}")


def auth_check(auth: GatewayAuthStatus) -> DeploymentReadinessCheck:
    if auth.enabled:
        return DeploymentReadinessCheck(name="gateway_auth", status="pass", detail="Gateway API token is configured.")
    return DeploymentReadinessCheck(name="gateway_auth", status="warn", detail="GATEWAY_API_TOKEN is not configured.")


def combined_status(checks: list[DeploymentReadinessCheck]) -> ReadinessStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def build_deployment_readiness(
    *,
    auth: GatewayAuthStatus,
    storage_dirs: dict[str, Path],
    service_urls: dict[str, str],
    assets_dir: Path,
    traceability_path: Path,
) -> DeploymentReadinessResponse:
    checks = [auth_check(auth)]
    checks.extend(directory_check(name, path) for name, path in storage_dirs.items())
    checks.append(directory_check("assets_dir", assets_dir))
    checks.extend(service_url_check(name, url) for name, url in service_urls.items())
    checks.append(traceability_check(traceability_path))

    warnings = [check.detail for check in checks if check.status == "warn"]
    return DeploymentReadinessResponse(
        status=combined_status(checks),
        checked_at=utc_now(),
        auth=auth,
        checks=checks,
        warnings=warnings,
    )
