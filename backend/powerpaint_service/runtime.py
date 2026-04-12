from __future__ import annotations

import importlib.util
import os
import threading
from pathlib import Path

import torch
from huggingface_hub import snapshot_download

from common.schemas import PowerPaintGenerateRequest
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url


class PowerPaintRuntime:
    def __init__(self) -> None:
        self.repo_path = Path(os.getenv("POWERPAINT_REPO_PATH", "/opt/PowerPaint"))
        self.model_repo = os.getenv("POWERPAINT_MODEL_REPO", "JunhaoZhuang/PowerPaint-v1")
        self.checkpoint_dir = Path(os.getenv("POWERPAINT_CHECKPOINT_DIR", "/models/powerpaint/ppt-v1"))
        self.version = os.getenv("POWERPAINT_VERSION", "ppt-v1")
        self.weight_dtype_name = os.getenv("POWERPAINT_WEIGHT_DTYPE", "float16")
        self.local_files_only = os.getenv("POWERPAINT_LOCAL_FILES_ONLY", "false").lower() == "true"
        self._controller = None
        self._lock = threading.Lock()

    @property
    def weight_dtype(self) -> torch.dtype:
        return torch.float16 if self.weight_dtype_name == "float16" else torch.float32

    def _load_module(self):
        app_path = self.repo_path / "app.py"
        spec = importlib.util.spec_from_file_location("powerpaint_app", app_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load PowerPaint entrypoint from {app_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.weight_dtype = self.weight_dtype
        return module

    def startup(self) -> None:
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        if not any(self.checkpoint_dir.iterdir()):
            snapshot_download(
                repo_id=self.model_repo,
                local_dir=str(self.checkpoint_dir),
                local_dir_use_symlinks=False,
            )

        module = self._load_module()
        self._controller = module.PowerPaintController(
            weight_dtype=self.weight_dtype,
            checkpoint_dir=str(self.checkpoint_dir),
            local_files_only=self.local_files_only,
            version=self.version,
        )

    def generate(self, payload: PowerPaintGenerateRequest) -> str:
        if self._controller is None:
            raise RuntimeError("PowerPaint runtime has not been initialized.")

        image = decode_data_url_to_image(payload.image, mode="RGB")
        mask = decode_data_url_to_image(payload.mask_image, mode="L").convert("RGB")

        with self._lock:
            results, _ = self._controller.infer(
                input_image={"image": image, "mask": mask},
                text_guided_prompt=payload.prompt if payload.task == "text-guided" else "",
                text_guided_negative_prompt=payload.negative_prompt if payload.task == "text-guided" else "",
                shape_guided_prompt=payload.prompt if payload.task == "shape-guided" else "",
                shape_guided_negative_prompt=payload.negative_prompt if payload.task == "shape-guided" else "",
                fitting_degree=payload.fitting_degree,
                ddim_steps=payload.steps,
                scale=payload.guidance_scale,
                seed=payload.seed,
                task=payload.task,
                vertical_expansion_ratio=payload.vertical_expansion_ratio,
                horizontal_expansion_ratio=payload.horizontal_expansion_ratio,
                outpaint_prompt=payload.prompt if payload.task == "image-outpainting" else "",
                outpaint_negative_prompt=payload.negative_prompt if payload.task == "image-outpainting" else "",
                removal_prompt=payload.prompt if payload.task == "object-removal" else "",
                removal_negative_prompt=payload.negative_prompt if payload.task == "object-removal" else "",
            )

        return encode_image_to_data_url(results[0])
