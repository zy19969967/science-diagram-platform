# 服务器部署 README

如果你的服务器不能使用 Docker、但可以使用 Conda，请改看：

- [无 Docker / Conda 服务器部署 README](server-conda-deploy.md)

这份文档面向“本机开发、服务器运行”的部署方式，默认目标环境是 Ubuntu 22.04 + Docker Compose + NVIDIA GPU 服务器。当前仓库已经接入真实模型优先的运行链路：

- `planner`：优先调用 `Qwen/Qwen3.5-4B`
- `segmenter`：优先调用 `facebook/sam2.1-hiera-base-plus`
- `powerpaint_service`：调用官方 `PowerPaint`
- `flux`：本地 diffusers FLUX-compatible 初图服务，默认 `black-forest-labs/FLUX.2-klein-4B`
- 当真实模型不可用时，会自动回退到仓库内规则逻辑，保证平台还能用于调试和演示
- Gateway 还包含异步任务、项目版本、benchmark ledger、readiness 检查和可选单 token 保护

## 0. 当前能不能部署

可以部署，但请按下面边界理解：

- 当前推荐部署版本是 PR 分支 `codex/report-alignment-phase1`；如果 PR 已经合并到 `main`，再改为部署 `main`。
- 推荐优先使用 Docker Compose，因为它会同时编排 `frontend`、`gateway`、`planner`、`segmenter`、`powerpaint` 和本地 `flux` 服务。
- 服务器必须能访问或已经缓存 Qwen3.5、SAM2.1、PowerPaint 2.1 和 FLUX 权重；仓库不会把这些大模型权重提交进 Git。
- 这是单节点、单用户、文件持久化优先的部署，适合毕业设计演示、内网测试和受控服务器环境；不是公网多租户生产系统。
- 如果 Docker 不可用，可以改用 [无 Docker / Conda 服务器部署 README](server-conda-deploy.md)。

## 1. 部署前提

建议服务器满足以下条件：

- Ubuntu 22.04 或兼容 Linux 发行版
- Docker 24+
- Docker Compose v2
- NVIDIA 驱动
- NVIDIA Container Toolkit
- 建议至少 4 张可用 GPU；资源紧张时可以让服务共享 GPU，但需要自己评估显存占用
- 足够的磁盘空间保存 Docker 镜像和模型缓存

如果你使用的正是当前这台 8 x RTX 3090 服务器，当前模板示例按 4 卡方式部署：

- GPU 4：`powerpaint_service`
- GPU 5：`planner`
- GPU 6：`segmenter`
- GPU 7：`flux`

## 2. 推荐部署目录

```text
/home/common/yzhu_2025/science-diagram-platform
```

不要把项目部署到系统盘 `/` 下。这个项目首次构建会下载 CUDA 版 PyTorch、Qwen3.5、SAM-2 和 PowerPaint 权重，系统盘空间不足时最容易在这里失败。

## 3. 服务器信息自检

如果你想先做一次环境核对，可以直接运行仓库自带脚本：

```bash
bash scripts/server-preflight.sh
```

如果当前账号没有 Docker 权限，脚本会提示你改用 `sudo docker ...`。

## 4. 克隆项目

如果 PR 还没有合并到 `main`，现在应当显式拉取当前开发分支：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone -b codex/report-alignment-phase1 https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

如果 PR 已经合并到 `main`，则使用：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

两种方式二选一，不要在同一个目录重复 clone。

## 5. 准备环境变量

复制服务器模板：

```bash
cp .env.server.example .env
```

当前模板已经写好了真实模型配置，最少确认下面这些项：

```bash
FRONTEND_PUBLIC_PORT=19084
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=19080

# Optional: keep empty for an open internal demo, or set both to the same value.
GATEWAY_API_TOKEN=
VITE_API_TOKEN=

POWERPAINT_CUDA_VISIBLE_DEVICES=4
PLANNER_CUDA_VISIBLE_DEVICES=5
SEGMENTER_CUDA_VISIBLE_DEVICES=6
FLUX_CUDA_VISIBLE_DEVICES=7
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
TORCH_VERSION=2.5.1
TORCHVISION_VERSION=0.20.1

POWERPAINT_REPO_GIT_URL=https://github.com/zhuang2002/PowerPaint.git
PLANNER_MODEL_REPO=Qwen/Qwen3.5-4B
SEGMENTER_MODEL_REPO=facebook/sam2.1-hiera-base-plus
POWERPAINT_MODEL_REPO=JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_MODEL_GIT_URL=https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_DOWNLOAD_METHOD=git
POWERPAINT_VERSION=ppt-v2
POWERPAINT_MODEL_DIR_NAME=ppt-v2-1
BENCHMARKS_DIR=/app/data/benchmarks

# Gateway defaults to the Compose-local flux service if this stays empty.
FLUX_INIT_URL=
FLUX_MODEL_REPO=black-forest-labs/FLUX.2-klein-4B
FLUX_MODEL_DTYPE=bfloat16
FLUX_NUM_INFERENCE_STEPS=4
FLUX_GUIDANCE_SCALE=1.0
FLUX_MAX_SEQUENCE_LENGTH=512
FLUX_LOCAL_FILES_ONLY=false
```

几个关键说明：

- `GATEWAY_BIND_HOST=127.0.0.1` 表示网关只对本机开放，前端容器通过 Docker 网络反向代理访问它
- `FRONTEND_PUBLIC_PORT=19084` 表示浏览器最终访问的是前端容器
- `GATEWAY_API_TOKEN` 为空时保持旧的开放内网行为；非空时，除 `/api/health`、静态素材和文档路由外，`/api/*` 需要 token
- 如果设置了 `GATEWAY_API_TOKEN`，前端构建也要设置相同的 `VITE_API_TOKEN`，Docker Compose 会把它传给 Vite build
- `VITE_API_TOKEN` 会进入静态前端 bundle，只适合内网或受控演示边界，不是公网多租户认证方案
- `PowerPaint 2.1` 仍然复用 BrushNet 的 `ppt-v2` 推理分支，因此 `POWERPAINT_VERSION` 保持 `ppt-v2`
- `flux` 是本地初图服务，Compose 内部默认把 `FLUX_INIT_URL` 设置为 `http://flux:8004`
- 默认 FLUX 模型是 Apache 2.0 开源的 `black-forest-labs/FLUX.2-klein-4B`，通常需要约 13GB VRAM
- 初图生成阶段不会调用外部 FLUX API；只有首次下载或更新模型权重时可能访问 Hugging Face
- `FLUX_MODEL_REPO` 可以是 Hugging Face repo，也可以是服务器上的本地模型目录；如果已提前准备权重，可以设置 `FLUX_LOCAL_FILES_ONLY=true`
- Compose 会把 `RUNS_DIR`、`PROJECTS_DIR`、`JOBS_DIR` 和 `BENCHMARKS_DIR` 挂到项目 `data/` 目录下，便于重启后读取生成产物、项目版本、异步任务和实验记录

如果你已经提前下载过模型，也可以开启纯本地模式：

```bash
PLANNER_LOCAL_FILES_ONLY=true
SEGMENTER_LOCAL_FILES_ONLY=true
POWERPAINT_LOCAL_FILES_ONLY=true
```

注意：开启本地模式后，如果缓存目录里没有对应权重，服务会直接报错，而不是联网下载。

## 6. 首次构建

如果当前用户没有 Docker daemon 权限，请使用 `sudo`：

```bash
sudo docker compose --env-file .env build
```

首次构建通常最慢，因为会下载：

- CUDA 版 PyTorch 依赖
- Qwen3.5 权重
- SAM-2 权重
- PowerPaint 依赖和权重

## 7. 启动服务

```bash
sudo docker compose --env-file .env up -d
```

检查容器状态：

```bash
sudo docker compose ps
```

查看核心日志：

```bash
sudo docker compose logs -f frontend
sudo docker compose logs -f gateway
sudo docker compose logs -f planner
sudo docker compose logs -f segmenter
sudo docker compose logs -f powerpaint
sudo docker compose logs -f flux
```

## 8. 健康检查与访问地址

如果服务器公网 IP 是 `211.87.232.112`，并且保留：

```bash
FRONTEND_PUBLIC_PORT=19084
```

那么浏览器访问地址就是：

```text
http://211.87.232.112:19084
```

也可以在服务器里直接检查网关健康状态：

```bash
curl http://127.0.0.1:19080/api/health
```

检查部署 readiness：

```bash
curl http://127.0.0.1:19080/api/deployment/readiness
```

如果配置了 `GATEWAY_API_TOKEN`：

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:19080/api/deployment/readiness
```

`/api/deployment/readiness` 只检查本地目录、auth 配置、服务 URL 格式、assets 目录和 traceability 文档是否存在；它不会调用 Qwen3.5、SAM2.1、PowerPaint 或本地 FLUX 模型。

## 9. 首次请求较慢是正常现象

`planner`、`segmenter` 和 `flux` 采用惰性加载。也就是说：

- 容器可以先启动成功
- 第一次真正调用 `/api/plan` 或 `/api/segment` 时才加载模型
- 第一次真正调用 `/api/init-generate` 且命中本地 FLUX 时才加载 FLUX 模型
- 首次请求明显比后续请求慢

为了避免前端经由 Nginx 反代时在冷启动阶段超时，前端容器已经把 `/api` 代理超时调大到 600 秒。本地 FLUX 首次加载也可能超过普通 HTTP 请求预期，建议先在服务器上用小尺寸初图请求预热。

## 10. 模型缓存与磁盘建议

仓库默认把模型缓存挂到项目下的 `./models`：

```text
./models
```

这样做的好处是：

- `planner`、`segmenter`、`powerpaint` 共享 Hugging Face 缓存
- `flux` 也复用同一个 Hugging Face 缓存
- 重启容器不必重新下载所有模型
- 更容易把模型目录迁移到大盘路径

如果 Docker Root Dir 仍在系统盘，可以先检查：

```bash
sudo docker info | grep 'Docker Root Dir'
```

运行数据默认落在：

```text
./data/runs
./data/projects
./data/jobs
./data/benchmarks
```

这些目录是当前项目的文件持久化基础；如果迁移服务器，需要一起备份。

## 11. 更新项目

以后更新仓库时，推荐这样做：

```bash
cd /home/common/yzhu_2025/science-diagram-platform
git pull origin codex/report-alignment-phase1
sudo docker compose --env-file .env up -d --build
```

如果你已经把 PR 合并到 `main` 并切回主分支，则使用：

```bash
git pull origin main
sudo docker compose --env-file .env up -d --build
```

## 12. 常见问题

### 12.1 Docker 权限不足

现象：

- `permission denied while trying to connect to the Docker daemon socket`

处理方式：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

### 12.2 系统盘空间不足

现象：

- 构建镜像时失败
- 下载模型时失败
- `No space left on device`

处理方式：

- 优先把仓库放到 `/home/common/...`
- 检查 `Docker Root Dir`
- 必要时迁移 Docker 数据目录

### 12.3 GPU 被其他任务占用

处理方式：

- 先运行 `nvidia-smi`
- 把 `.env` 中的 GPU 编号改成空闲卡
- 重新执行：

```bash
sudo docker compose --env-file .env up -d --build
```

### 12.4 本地模式启动失败

如果你把 `*_LOCAL_FILES_ONLY=true`，但缓存目录里没有模型，服务会直接失败。需要先关闭本地模式，或提前把模型缓存准备好。

### 12.5 首次请求超时

如果是第一次请求，先检查：

- `planner` 日志里是否正在加载 Qwen3.5
- `segmenter` 日志里是否正在加载 SAM-2
- `flux` 日志里是否正在加载 FLUX 模型
- `powerpaint` 日志里是否正在初始化权重

这通常不是死机，而是冷启动。

### 12.6 Token 配置后前端请求 401

优先确认：

- `.env` 中 `GATEWAY_API_TOKEN` 和 `VITE_API_TOKEN` 是否一致
- 修改 token 后是否重新执行了 `sudo docker compose --env-file .env up -d --build`
- 请求是否访问的是 `/api/*`；`/assets` 与 `/artifacts` 是静态资源路由，当前仍然 intentionally exempt

### 12.7 本地 FLUX 初图失败

优先确认：

- `sudo docker compose logs -f flux`
- `FLUX_MODEL_REPO` 是否是可访问的 Hugging Face repo 或服务器本地模型目录
- 如果设置了 `FLUX_LOCAL_FILES_ONLY=true`，`models/huggingface` 或本地模型目录里是否已经有完整权重
- GPU 7 是否空闲，或者把 `FLUX_CUDA_VISIBLE_DEVICES` 改成空闲卡
- 如果只是 FLUX 服务不可用，Gateway 的 `auto` 初图生成会回退到确定性 fallback；显式 `flux-local` 请求会返回错误

### 12.8 Where PowerPaint 2.1 Weights Come From

`POWERPAINT_REPO_GIT_URL` only pulls the PowerPaint code repository. The `PowerPaint 2.1` weights are not stored in the GitHub code repository. They still need to come from the Hugging Face Git LFS repository referenced by `POWERPAINT_MODEL_GIT_URL`, or be copied into the model directory ahead of time.
