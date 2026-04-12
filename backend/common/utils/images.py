from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image


def decode_data_url_to_image(data_url: str, mode: str | None = None) -> Image.Image:
    if "," not in data_url:
        raise ValueError("Expected a valid data URL.")
    _, encoded = data_url.split(",", 1)
    binary = base64.b64decode(encoded)
    image = Image.open(BytesIO(binary))
    if mode:
        image = image.convert(mode)
    return image


def encode_image_to_data_url(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/{fmt.lower()};base64,{encoded}"
