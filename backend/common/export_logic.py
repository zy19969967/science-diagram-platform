from __future__ import annotations

from html import escape

from common.schemas import (
    CanvasLayer,
    SvgExportRequest,
    SvgExportResponse,
    TextObservation,
    TextValidationReport,
    TextValidationRequest,
)


def _clean_label(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _label_key(value: object) -> str:
    return _clean_label(value).casefold()


def _visible_layers(layers: list[CanvasLayer], *, include_hidden: bool) -> list[CanvasLayer]:
    return [layer for layer in layers if include_hidden or layer.visible]


def _vector_text_labels(request: TextValidationRequest) -> list[str]:
    labels: list[str] = []
    for layer in _visible_layers(request.canvas_state.layers, include_hidden=request.include_hidden_layers):
        if layer.type != "text":
            continue
        text = _clean_label(layer.data.get("text", ""))
        if text:
            labels.append(text)
    return labels


def _ocr_labels(observations: list[TextObservation]) -> list[str]:
    return [label for label in (_clean_label(item.text) for item in observations) if label]


def _unique_labels(labels: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for label in labels:
        key = _label_key(label)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def build_text_validation_report(request: TextValidationRequest) -> TextValidationReport:
    vector_labels = _unique_labels(_vector_text_labels(request))
    ocr_labels = _unique_labels(_ocr_labels(request.ocr_observations))
    expected_labels = _unique_labels([_clean_label(label) for label in request.expected_labels])
    if not expected_labels:
        expected_labels = vector_labels

    recognized_labels = ocr_labels if request.ocr_observations else vector_labels
    recognized_keys = {_label_key(label) for label in recognized_labels}
    expected_keys = {_label_key(label) for label in expected_labels}

    matched_labels = [label for label in expected_labels if _label_key(label) in recognized_keys]
    missing_labels = [label for label in expected_labels if _label_key(label) not in recognized_keys]
    extra_vector_labels = [label for label in vector_labels if _label_key(label) not in expected_keys]

    warnings: list[str] = []
    source = "provided-ocr" if request.ocr_observations else "vector-text-fallback"
    if not request.ocr_observations:
        warnings.append("No OCR observations supplied; using vector text layers for reconciliation.")
    else:
        unconfirmed = [label for label in vector_labels if _label_key(label) not in recognized_keys]
        if unconfirmed:
            warnings.append(f"OCR observations did not confirm vector labels: {', '.join(unconfirmed)}.")

    status = "fail" if missing_labels else "pass"
    if warnings and status == "pass":
        status = "warn"

    return TextValidationReport(
        status=status,
        source=source,
        expected_labels=expected_labels,
        vector_labels=vector_labels,
        ocr_labels=ocr_labels,
        matched_labels=matched_labels,
        missing_labels=missing_labels,
        extra_vector_labels=extra_vector_labels,
        warnings=warnings,
    )


def _attr(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: object, default: float = 0.0) -> float:
    return value if isinstance(value, (int, float)) else default


def _svg_image(layer: CanvasLayer, width: int, height: int, warnings: list[str]) -> str:
    data = layer.data
    href = data.get("image_url")
    if not href:
        if data.get("embedded_source_image") or data.get("embedded_base_image"):
            warnings.append(
                f"Layer {layer.id} references embedded bitmap data that is not stored in canvas_state; SVG export uses a placeholder."
            )
        return (
            f'<rect data-layer-id="{_attr(layer.id)}" x="0" y="0" width="{width}" height="{height}" '
            'fill="#f8fafc" stroke="#cbd5e1" stroke-dasharray="8 8" />'
        )

    if layer.type == "asset":
        x = _number(data.get("x"), 0.5) * width
        y = _number(data.get("y"), 0.5) * height
        draw_width = _number(data.get("width"), 0.2) * width
        draw_height = _number(data.get("height"), 0.2) * height
        left = x - draw_width / 2
        top = y - draw_height / 2
        rotation = _number(data.get("rotation"), 0.0)
        transform = f' transform="rotate({rotation} {x} {y})"' if rotation else ""
        return (
            f'<image data-layer-id="{_attr(layer.id)}" href="{_attr(href)}" '
            f'x="{left:.2f}" y="{top:.2f}" width="{draw_width:.2f}" height="{draw_height:.2f}" '
            f'opacity="{layer.opacity:.3f}" preserveAspectRatio="xMidYMid meet"{transform} />'
        )

    return (
        f'<image data-layer-id="{_attr(layer.id)}" href="{_attr(href)}" '
        f'x="0" y="0" width="{width}" height="{height}" opacity="{layer.opacity:.3f}" '
        'preserveAspectRatio="xMidYMid meet" />'
    )


def _svg_text(layer: CanvasLayer, width: int, height: int) -> str:
    data = layer.data
    text = _clean_label(data.get("text", ""))
    if not text:
        return ""
    x = _number(data.get("x"), 0.5) * width
    y = _number(data.get("y"), 0.5) * height
    font_size = _number(data.get("font_size"), 22)
    color = data.get("color") or "#18324c"
    align = data.get("align") or "center"
    anchor = {"left": "start", "right": "end", "center": "middle"}.get(str(align), "middle")
    return (
        f'<text data-layer-id="{_attr(layer.id)}" x="{x:.2f}" y="{y:.2f}" '
        f'font-size="{font_size:.2f}" fill="{_attr(color)}" text-anchor="{anchor}" '
        f'opacity="{layer.opacity:.3f}" font-family="Arial, Helvetica, sans-serif">{escape(text)}</text>'
    )


def build_svg_export(request: SvgExportRequest) -> SvgExportResponse:
    state = request.canvas_state
    warnings: list[str] = []
    body: list[str] = []
    for layer in _visible_layers(state.layers, include_hidden=request.include_hidden_layers):
        if layer.type in {"base-image", "asset"}:
            body.append(_svg_image(layer, state.width, state.height, warnings))
        elif layer.type == "text":
            text_node = _svg_text(layer, state.width, state.height)
            if text_node:
                body.append(text_node)
        elif layer.type == "mask":
            warnings.append(f"Layer {layer.id} is a raster mask and is not exported as editable SVG geometry.")
        elif layer.type == "region-prompt":
            warnings.append(f"Layer {layer.id} stores SAM prompt provenance and is not exported as visible SVG content.")

    text_report = build_text_validation_report(
        TextValidationRequest(
            canvas_state=state,
            expected_labels=request.expected_labels,
            ocr_observations=request.ocr_observations,
            include_hidden_layers=request.include_hidden_layers,
        )
    )
    warnings.extend(text_report.warnings)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{state.width}" height="{state.height}" '
        f'viewBox="0 0 {state.width} {state.height}" role="img" aria-label="{_attr(state.canvas_id)}">\n'
        f'  <title>{escape(state.canvas_id)}</title>\n'
        + "\n".join(f"  {item}" for item in body)
        + "\n</svg>\n"
    )
    return SvgExportResponse(
        svg=svg,
        filename=request.filename or "science-diagram.svg",
        text_report=text_report,
        warnings=_unique_labels(warnings),
    )
