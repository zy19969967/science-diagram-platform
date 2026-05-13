# 服务器部署说明

本文档是公开仓库唯一保留的部署说明，合并了原来的 Docker、Conda 和检查清单内容。当前完整功能已经落在 `main`，服务器直接部署默认分支即可。

## 1. 部署边界

- 推荐目标环境是 Ubuntu 22.04、NVIDIA GPU、2 张 H20-NVLink 96GB。
- 默认 GPU 分配为 GPU 0 跑 `qwen-image`，GPU 1 跑 `powerpaint_service`、`planner`、`segmenter` 和 `flux`。
- 仓库不会提交 Qwen3.5、SAM2.1、PowerPaint 2.1、FLUX 或 Qwen-Image 权重；首次启动或更新模型时可能需要访问 Hugging Face。
- 当前方案是单节点、单用户、文件持久化实现，适合毕业设计演示、内网测试和受控服务器环境，不是公网多租户生产系统。
- 如果可以使用 Docker，优先走 Docker Compose；如果服务器不能使用 Docker，再走 Conda/tmux。

推荐部署目录：

```text
/home/common/yzhu_2025/science-diagram-platform
```

## 2. Docker Compose 部署

先确认服务器基础环境：

```bash
nvidia-smi
docker --version
docker compose version
df -h
```

克隆仓库并准备环境变量：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.server.example .env
```

至少确认 `.env` 中这些配置：

```bash
FRONTEND_PUBLIC_PORT=19084
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=19080

PROJECT_GPU_POOL=0,1
QWEN_IMAGE_CUDA_VISIBLE_DEVICES=0
POWERPAINT_CUDA_VISIBLE_DEVICES=1
PLANNER_CUDA_VISIBLE_DEVICES=1
SEGMENTER_CUDA_VISIBLE_DEVICES=1
FLUX_CUDA_VISIBLE_DEVICES=1

PLANNER_MODEL_REPO=Qwen/Qwen3.5-4B
SEGMENTER_MODEL_REPO=facebook/sam2.1-hiera-base-plus
POWERPAINT_MODEL_REPO=JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_MODEL_GIT_URL=https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_VERSION=ppt-v2
POWERPAINT_MODEL_DIR_NAME=ppt-v2-1

FLUX_INIT_URL=
FLUX_MODEL_REPO=black-forest-labs/FLUX.2-klein-4B
FLUX_MODEL_DTYPE=bfloat16
FLUX_LOCAL_FILES_ONLY=false

QWEN_IMAGE_URL=
QWEN_IMAGE_MODEL_REPO=Qwen/Qwen-Image-Edit
QWEN_IMAGE_MODEL_DTYPE=bfloat16
QWEN_IMAGE_NUM_INFERENCE_STEPS=50
QWEN_IMAGE_TRUE_CFG_SCALE=4.0
QWEN_IMAGE_STRENGTH=1.0
QWEN_IMAGE_LOCAL_FILES_ONLY=false

GATEWAY_API_TOKEN=
VITE_API_TOKEN=
```

说明：

- `FLUX_INIT_URL` 留空时，Gateway 在 Compose 内默认调用 `http://flux:8004`。
- `QWEN_IMAGE_URL` 留空时，Gateway 在 Compose 内默认调用 `http://qwen-image:8005`。
- Qwen-Image 第一版默认使用 `Qwen/Qwen-Image-Edit`，第一版不默认使用 Qwen-Image-Edit-2511；切换 2511 前需要单独验证依赖、显存和效果。
- Qwen-Image 按独占 80GB GPU 设计。默认的 2 张 H20-NVLink 96GB 布局中，GPU 0 留给 Qwen-Image，GPU 1 承载 PowerPaint、planner、segmenter 和 FLUX。
- 如果配置 `GATEWAY_API_TOKEN`，需要同时把 `VITE_API_TOKEN` 设置成同一个值并重新构建前端。
- `VITE_API_TOKEN` 会进入静态前端 bundle，只适合内网或受控演示边界。

构建并启动完整链路：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env --profile qwen-image up -d
```

如果只想先启动 PowerPaint legacy 链路，不启动 Qwen-Image，可以去掉 profile：

```bash
sudo docker compose --env-file .env up -d
```

查看状态和日志：

```bash
sudo docker compose ps
sudo docker compose logs -f frontend
sudo docker compose logs -f gateway
sudo docker compose logs -f planner
sudo docker compose logs -f segmenter
sudo docker compose logs -f powerpaint
sudo docker compose logs -f flux
sudo docker compose logs -f qwen-image
```

## 3. Conda/tmux 部署

Conda 路径适用于无法使用 Docker、但可以创建 Conda 环境的服务器。项目会拆成多个本地服务，通过 `127.0.0.1:端口` 通信。

准备仓库：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.nodocker.example .env.nodocker
```

至少确认 `.env.nodocker` 中这些配置：

```bash
PROJECT_ROOT=/home/common/yzhu_2025/science-diagram-platform
POWERPAINT_REPO_PATH=/home/common/yzhu_2025/PowerPaint
CONDA_BIN=conda

CONDA_ENV_GATEWAY=sci-gateway
CONDA_ENV_PLANNER=sci-planner
CONDA_ENV_SEGMENTER=sci-segmenter
CONDA_ENV_POWERPAINT=sci-powerpaint
CONDA_ENV_FLUX=sci-flux
CONDA_ENV_QWEN_IMAGE=sci-qwen-image

PROJECT_GPU_POOL=0,1
QWEN_IMAGE_CUDA_VISIBLE_DEVICES=0
POWERPAINT_CUDA_VISIBLE_DEVICES=1
PLANNER_CUDA_VISIBLE_DEVICES=1
SEGMENTER_CUDA_VISIBLE_DEVICES=1
FLUX_CUDA_VISIBLE_DEVICES=1

FLUX_PORT=19085
FLUX_INIT_URL=http://127.0.0.1:19085
QWEN_IMAGE_PORT=19086
QWEN_IMAGE_URL=http://127.0.0.1:19086

GATEWAY_PORT=19080
PLANNER_PORT=19081
POWERPAINT_PORT=19082
SEGMENTER_PORT=19083
FRONTEND_STATIC_PORT=19084
PUBLIC_GATEWAY_BASE_URL=http://211.87.232.112:19080

RUNS_DIR=/home/common/yzhu_2025/science-diagram-platform/data/runs
BENCHMARKS_DIR=/home/common/yzhu_2025/science-diagram-platform/data/benchmarks
```

安装环境：

```bash
bash scripts/setup_conda_envs.sh
```

推荐用 tmux 启动全部服务：

```bash
bash scripts/start_all_tmux.sh --with-frontend
```

也可以手动分开启动：

```bash
bash scripts/run_planner.sh
bash scripts/run_segmenter.sh
bash scripts/run_powerpaint.sh
bash scripts/run_flux.sh
bash scripts/run_qwen_image.sh
bash scripts/run_gateway.sh
bash scripts/build_frontend.sh
bash scripts/serve_frontend.sh
```

检查服务：

```bash
bash scripts/status_tmux.sh
bash scripts/check_gpu_envs.sh
bash scripts/check_services.sh
```

停止服务：

```bash
bash scripts/stop_all_tmux.sh
```

## 4. 访问与健康检查

如果服务器 IP 是 `211.87.232.112`，并且保留 `FRONTEND_PUBLIC_PORT=19084` 或 `FRONTEND_STATIC_PORT=19084`，浏览器访问：

```text
http://211.87.232.112:19084
```

在服务器上检查 Gateway：

```bash
curl http://127.0.0.1:19080/api/health
curl http://127.0.0.1:19080/api/deployment/readiness
```

如果启用了 token：

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:19080/api/deployment/readiness
```

`/api/deployment/readiness` 只检查目录、配置、服务 URL 和 traceability 文件；它不会加载 Qwen3.5、SAM2.1、PowerPaint、Qwen-Image 或 FLUX 模型。

## 5. 首次功能验证

建议按这个顺序验证：

1. 打开前端页面。
2. 在无图生成输入框输入：`画一个酶促反应示意图，包含底物、酶、产物和箭头`。
3. 点击初图生成，确认能出现候选图；如果 FLUX 未就绪，应出现 fallback 候选。
4. 选择候选图进入编辑。
5. 绘制 mask 或添加 SAM 正/负点提示。
6. 输入局部编辑指令并执行生成。
7. 检查结果图、质量报告、项目保存和 benchmark 记录。

首次请求慢是正常现象，因为 Qwen3.5、SAM2.1、PowerPaint、Qwen-Image 和 FLUX 都可能惰性加载。

演示前可以顺序预热模型：

```bash
bash scripts/prewarm_models.sh
```

不要并发预热；如果出现 CUDA OOM，先检查 `.env` 或 `.env.nodocker` 中的 GPU 分配，尤其确认 Qwen-Image 是否独占 80GB GPU。

## 6. 更新与故障处理

更新服务器代码：

```bash
git pull origin main
```

Docker 路径重新构建并启动：

```bash
sudo docker compose --env-file .env --profile qwen-image up -d --build
```

Conda 路径更新依赖并重启：

```bash
bash scripts/setup_conda_envs.sh
bash scripts/stop_all_tmux.sh
bash scripts/start_all_tmux.sh --with-frontend
```

常见问题：

- 前端打不开：检查 `frontend` 容器或 `serve_frontend.sh`，再检查服务器防火墙是否放行 `19084`。
- Gateway 健康检查失败：检查 `gateway` 日志、`.env` 或 `.env.nodocker` 中的端口和 token。
- 真实模型不工作但 fallback 可用：优先检查模型缓存、`HF_ENDPOINT`、`*_LOCAL_FILES_ONLY` 和 GPU 显存。
- PyTorch 显示 CPU：检查 `TORCH_INDEX_URL` 是否指向 CUDA wheel 源，并重新安装对应 Conda 环境。
- PowerPaint 权重缺失：确认 `POWERPAINT_MODEL_REPO`、`POWERPAINT_MODEL_GIT_URL`、`POWERPAINT_MODEL_DIR_NAME` 和本地权重目录。
