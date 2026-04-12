from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .schemas import AssetMeta

BASE_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BASE_DIR / "assets" / "catalog.json"


@lru_cache(maxsize=1)
def load_asset_catalog() -> list[AssetMeta]:
    raw_items = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [AssetMeta(**item) for item in raw_items]


def get_asset(asset_id: str | None) -> AssetMeta | None:
    if not asset_id:
        return None
    for asset in load_asset_catalog():
        if asset.id == asset_id:
            return asset
    return None


def asset_catalog_with_urls(base_url: str) -> list[AssetMeta]:
    normalized = base_url.rstrip("/")
    items: list[AssetMeta] = []
    for asset in load_asset_catalog():
        items.append(
            asset.model_copy(
                update={
                    "image_url": f"{normalized}/assets/science/{asset.file_name}",
                }
            )
        )
    return items
