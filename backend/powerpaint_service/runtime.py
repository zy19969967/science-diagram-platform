from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import threading
from pathlib import Path

import torch
from huggingface_hub import snapshot_download

from common.schemas import PowerPaintGenerateRequest
from common.utils.images import decode_data_url_to_image, encode_image_to_data_url


class PowerPaintRuntime:
    def __init__(self) -> None:
        self.repo_path = Path(os.getenv("POWERPAINT_REPO_PATH", "/opt/PowerPaint"))
        self.model_repo = os.getenv("POWERPAINT_MODEL_REPO", "JunhaoZhuang/PowerPaint-v2-1")
        self.checkpoint_dir = Path(os.getenv("POWERPAINT_CHECKPOINT_DIR", "/models/powerpaint/ppt-v2-1"))
        self.version = os.getenv("POWERPAINT_VERSION", "ppt-v2")
        self.model_git_url = os.getenv("POWERPAINT_MODEL_GIT_URL", f"https://huggingface.co/{self.model_repo}")
        self.download_method = os.getenv("POWERPAINT_DOWNLOAD_METHOD", "git").lower()
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

    def _checkpoint_exists(self) -> bool:
        return self.checkpoint_dir.exists() and any(self.checkpoint_dir.iterdir())

    def _download_snapshot(self) -> None:
        snapshot_download(
            repo_id=self.model_repo,
            local_dir=str(self.checkpoint_dir),
            local_dir_use_symlinks=False,
        )

    def _download_git(self) -> None:
        if shutil.which("git") is None:
            raise RuntimeError("git is required for POWERPAINT_DOWNLOAD_METHOD=git")

        try:
            subprocess.run(["git", "lfs", "version"], check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise RuntimeError(
                "git-lfs is required for POWERPAINT_DOWNLOAD_METHOD=git. Install git-lfs first."
            ) from exc

        if self.checkpoint_dir.exists():
            if any(self.checkpoint_dir.iterdir()):
                if not (self.checkpoint_dir / ".git").exists():
                    raise RuntimeError(
                        f"Checkpoint directory {self.checkpoint_dir} already exists but is not a git repository. "
                        "Move it aside or clear it before downloading with git."
                    )
                subprocess.run(["git", "-C", str(self.checkpoint_dir), "lfs", "pull"], check=True)
                return
            self.checkpoint_dir.rmdir()

        subprocess.run(["git", "lfs", "install"], check=True)
        subprocess.run(["git", "clone", self.model_git_url, str(self.checkpoint_dir)], check=True)
        subprocess.run(["git", "-C", str(self.checkpoint_dir), "lfs", "pull"], check=True)

    def _download_weights(self) -> None:
        if self.download_method == "snapshot":
            self._download_snapshot()
            return

        if self.download_method in {"git", "git-lfs", "git_lfs"}:
            self._download_git()
            return

        raise RuntimeError(
            f"Unsupported POWERPAINT_DOWNLOAD_METHOD={self.download_method}. "
            "Use `snapshot` or `git`."
        )

    def startup(self) -> None:
        self.checkpoint_dir.parent.mkdir(parents=True, exist_ok=True)
        if not self._checkpoint_exists():
            if self.local_files_only:
                raise FileNotFoundError(
                    "PowerPaint weights are missing while POWERPAINT_LOCAL_FILES_ONLY=true. "
                    f"Expected cached weights under {self.checkpoint_dir}."
                )
            try:
                self._download_weights()
            except Exception as exc:
                raise RuntimeError(
                    "Failed to prepare PowerPaint weights. "
                    f"download_method={self.download_method}, model_repo={self.model_repo}, "
                    f"model_git_url={self.model_git_url}. "
                    "Cloning the PowerPaint GitHub repository only provides the application code, "
                    "not the PowerPaint 2.1 checkpoint weights. "
                    "If the server cannot reach the Hugging Face API, try `bash scripts/fetch_powerpaint_model.sh` "
                    "and then set POWERPAINT_LOCAL_FILES_ONLY=true."
                ) from exc

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
