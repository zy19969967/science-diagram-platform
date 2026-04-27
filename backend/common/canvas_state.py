from __future__ import annotations

from common.schemas import CanvasLayer, CanvasState


def _merge_data(
    layer: CanvasLayer,
    update: dict[str, object],
    *,
    drop_keys: set[str] | None = None,
) -> CanvasLayer:
    data = dict(layer.data)
    for key in drop_keys or set():
        data.pop(key, None)
    data.update(update)
    return layer.model_copy(update={"data": data})


def _ensure_base_layer(layers: list[CanvasLayer], result_url: str) -> list[CanvasLayer]:
    updated: list[CanvasLayer] = []
    found = False
    for layer in layers:
        if layer.type == "base-image" and not found:
            updated.append(
                _merge_data(
                    layer,
                    {
                        "image_url": result_url,
                        "source": "generated",
                        "embedded_source_image": False,
                    },
                    drop_keys={"source_image", "embedded_base_image"},
                )
            )
            found = True
        else:
            updated.append(layer)
    if not found:
        updated.insert(
            0,
            CanvasLayer(
                id="base-generated",
                type="base-image",
                name="Generated result",
                data={
                    "image_url": result_url,
                    "source": "generated",
                    "embedded_source_image": False,
                },
            ),
        )
    return updated


def _update_mask_layers(layers: list[CanvasLayer], mask_url: str | None) -> list[CanvasLayer]:
    if not mask_url:
        return layers
    return [
        (
            _merge_data(
                layer,
                {"mask_url": mask_url, "embedded_mask_image": False},
                drop_keys={"mask_image"},
            )
            if layer.type == "mask"
            else layer
        )
        for layer in layers
    ]


def build_canvas_state_after_generate(
    state: CanvasState | None,
    *,
    run_id: str,
    artifacts: dict[str, str],
) -> CanvasState | None:
    if state is None:
        return None

    result_url = artifacts.get("result", "")
    mask_url = artifacts.get("mask")
    layers = _ensure_base_layer(list(state.layers), result_url)
    layers = _update_mask_layers(layers, mask_url)
    history = [*state.history, run_id]
    metadata = {
        **state.metadata,
        "latest_run_id": run_id,
        "latest_result_url": result_url,
        "latest_mask_url": mask_url,
    }
    return state.model_copy(
        deep=True,
        update={
            "source": "generated",
            "layers": layers,
            "history": history,
            "metadata": metadata,
        },
    )
