# 无 Docker / Conda 服务器部署 README

这份文档适用于服务器无法使用 Docker、但可以使用 Conda 环境的场景。当前项目已经把无 Docker 流程切换为多服务、多 Conda 环境的部署方式。

当前可以部署，但如果 PR 还没有合并到 `main`，请部署 `codex/report-alignment-phase1` 分支；如果 PR 已经合并，则部署 `main` 即可。

当前项目本身就是多服务架构，因此最稳的替代方案是：

- `gateway` 一个 Conda 环境
- `planner` 一个 Conda 环境
- `segmenter` 一个 Conda 环境
- `powerpaint_service` 一个 Conda 环境
- `flux` 一个 Conda 环境
- 前端单独构建为静态文件

这些服务之间通过 `127.0.0.1:端口` 的 HTTP API 通信，不依赖 Docker 才能互相连接。

## 1. 前提条件

建议服务器满足：

- Miniconda or Anaconda available; all service Conda environments default to Python 3.10, including `powerpaint`
- 已安装 Miniconda 或 Anaconda，并且 `conda` 命令可直接使用
- `git`
- 可以访问 Hugging Face 和 GitHub
- 推荐安装 `git-lfs`，用于按 Git 方式拉取 `PowerPaint 2.1` 权重
- NVIDIA 驱动与 CUDA 可用
- Node.js 18+ 与 `npm`，如果你准备在服务器上构建前端
- 推荐安装 `tmux`，便于后台常驻运行多个服务

如果服务器没有 Node.js，也可以只在服务器上运行后端，在本机构建前端后再上传 `frontend/dist`。

## 2. 推荐目录

```text
/home/common/yzhu_2025/science-diagram-platform
```

另外还需要单独准备官方 PowerPaint 仓库：

```text
/home/common/yzhu_2025/PowerPaint
```

## 3. 克隆仓库

如果 PR 还没有合并到 `main`，现在用：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone -b codex/report-alignment-phase1 https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.nodocker.example .env.nodocker
```

如果 PR 已经合并到 `main`，则使用：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.nodocker.example .env.nodocker
```

`bash scripts/setup_conda_envs.sh` 会在 PowerPaint 仓库不存在时自动克隆它。

## 4. 编辑 `.env.nodocker`

至少确认这几项：

```bash
PROJECT_ROOT=/home/common/yzhu_2025/science-diagram-platform
POWERPAINT_REPO_PATH=/home/common/yzhu_2025/PowerPaint
POWERPAINT_REPO_GIT_URL=https://github.com/zhuang2002/PowerPaint.git

CONDA_PYTHON_VERSION=3.10
CONDA_PYTHON_VERSION_POWERPAINT=3.10
CONDA_BIN=conda
CONDA_ENV_GATEWAY=sci-gateway
CONDA_ENV_PLANNER=sci-planner
CONDA_ENV_SEGMENTER=sci-segmenter
CONDA_ENV_POWERPAINT=sci-powerpaint
CONDA_ENV_FLUX=sci-flux
HF_ENDPOINT=https://hf-mirror.com
TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
TORCH_VERSION=2.5.1
TORCHVISION_VERSION=0.20.1

POWERPAINT_CUDA_VISIBLE_DEVICES=4
PLANNER_CUDA_VISIBLE_DEVICES=5
SEGMENTER_CUDA_VISIBLE_DEVICES=6
FLUX_CUDA_VISIBLE_DEVICES=7

POWERPAINT_MODEL_REPO=JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_MODEL_GIT_URL=https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1
POWERPAINT_DOWNLOAD_METHOD=git
POWERPAINT_VERSION=ppt-v2
POWERPAINT_MODEL_DIR_NAME=ppt-v2-1
POWERPAINT_LOCAL_FILES_ONLY=false

FLUX_HOST=127.0.0.1
FLUX_PORT=19085
FLUX_INIT_URL=http://127.0.0.1:19085
FLUX_MODEL_REPO=black-forest-labs/FLUX.1-schnell
FLUX_MODEL_DTYPE=bfloat16
FLUX_NUM_INFERENCE_STEPS=4
FLUX_GUIDANCE_SCALE=0.0
FLUX_LOCAL_FILES_ONLY=false

GATEWAY_PORT=19080
PLANNER_PORT=19081
POWERPAINT_PORT=19082
SEGMENTER_PORT=19083
PUBLIC_GATEWAY_BASE_URL=http://211.87.232.112:19080
FRONTEND_STATIC_PORT=19084

# Optional: keep empty for an open internal demo, or set both to the same value.
GATEWAY_API_TOKEN=
VITE_API_TOKEN=

RUNS_DIR=/home/common/yzhu_2025/science-diagram-platform/data/runs
BENCHMARKS_DIR=/home/common/yzhu_2025/science-diagram-platform/data/benchmarks
```

说明：

- `PUBLIC_GATEWAY_BASE_URL` 是给前端构建用的，浏览器会直接访问这个地址
- `gateway` 默认绑定在 `127.0.0.1:19080`
- 如果你希望公网直接访问网关，可以把 `GATEWAY_HOST` 改成 `0.0.0.0`
- `FLUX_INIT_URL` 默认指向本机 `flux` 服务；Gateway 的 `auto` 初图生成会优先调用它
- 初图生成不会调用外部 FLUX API；Gateway 只访问本机 `flux` 服务，只有下载或更新权重时可能访问 Hugging Face
- `FLUX_MODEL_REPO` 可以是 Hugging Face repo，也可以是服务器上的本地模型目录；提前准备好权重时可设置 `FLUX_LOCAL_FILES_ONLY=true`
- `GATEWAY_API_TOKEN` 为空时保持开放内网行为；非空时，除 `/api/health` 等豁免路由外，`/api/*` 需要 token
- 如果设置了 `GATEWAY_API_TOKEN`，前端构建时也要设置相同的 `VITE_API_TOKEN`
- `VITE_API_TOKEN` 会进入前端静态 bundle，只适合受控演示或内网边界
- 如果脚本里找不到 `conda`，可以额外设置 `CONDA_BIN=/你的/miniconda3/bin/conda`
- `TORCH_INDEX_URL` 必须指向 CUDA wheel 源；如果 PyTorch 装成 CPU 版，模型会显示 `device: cpu`
- `POWERPAINT_DOWNLOAD_METHOD=git` 会按 Git / Git LFS 方式拉取 `PowerPaint 2.1` 权重
- `PowerPaint 2.1` 仍然走 BrushNet 的 `ppt-v2` 推理分支，所以 `POWERPAINT_VERSION` 保持 `ppt-v2`
- 如果你已经提前把模型拉到本地，建议把 `POWERPAINT_LOCAL_FILES_ONLY=true`
- 如果你已经有统一的 Conda 环境命名规范，可以直接改上面的 `CONDA_ENV_*`
- `PROJECTS_DIR` 和 `JOBS_DIR` 如果不显式设置，会默认落在 `RUNS_DIR` 的同级目录下，即 `data/projects` 和 `data/jobs`

## 5. 一次性安装环境

```bash
bash scripts/setup_conda_envs.sh
```

这个脚本会做几件事：

- 创建 `sci-gateway` 等 Conda 环境，名称可由 `.env.nodocker` 覆盖
- 安装各自依赖
- 安装前端依赖
- 自动克隆 PowerPaint 仓库
- 安装本地 `flux` 服务依赖；FLUX 权重仍通过 Hugging Face 缓存或本地模型目录提供

如果服务器访问 Hugging Face API 不稳定，再执行：

```bash
bash scripts/fetch_powerpaint_model.sh
```

下载完成后，建议把 `.env.nodocker` 里的 `POWERPAINT_LOCAL_FILES_ONLY` 改成 `true`，这样 `powerpaint` 启动时会直接使用本地 `PowerPaint 2.1` 权重。

## 6. 启动后端服务

如果服务器安装了 `tmux`，推荐直接后台启动：

```bash
bash scripts/start_all_tmux.sh
```

如果还想同时挂起前端静态服务：

```bash
bash scripts/start_all_tmux.sh --with-frontend
```

查看会话状态：

```bash
bash scripts/status_tmux.sh
```

停止所有会话：

```bash
bash scripts/stop_all_tmux.sh
```

如果你不想用 `tmux`，也可以手动分开启动：

```bash
bash scripts/run_planner.sh
bash scripts/run_segmenter.sh
bash scripts/run_powerpaint.sh
bash scripts/run_flux.sh
bash scripts/run_gateway.sh
```

默认端口：

- `planner`: `127.0.0.1:19081`
- `segmenter`: `127.0.0.1:19083`
- `powerpaint`: `127.0.0.1:19082`
- `flux`: `127.0.0.1:19085`
- `gateway`: `127.0.0.1:19080`

## 7. 构建并提供前端

先构建：

```bash
bash scripts/build_frontend.sh
```

再直接用 Python 提供静态文件：

```bash
bash scripts/serve_frontend.sh
```

默认前端访问地址：

```text
http://211.87.232.112:19084
```

## 8. 检查服务状态

先确认每个 Conda 环境能看到 CUDA：

```bash
bash scripts/check_gpu_envs.sh
```

如果任何环境输出 `torch.version.cuda: None` 或 `torch.cuda.is_available: False`，说明该环境没有可用的 CUDA PyTorch，先重跑：

```bash
bash scripts/setup_conda_envs.sh
```

然后再检查服务 HTTP 状态：

```bash
bash scripts/check_services.sh
```

如果 5 个接口都返回 JSON，说明链路已经连通。

还可以检查 Gateway 部署 readiness：

```bash
curl http://127.0.0.1:19080/api/deployment/readiness
```

如果配置了 `GATEWAY_API_TOKEN`：

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:19080/api/deployment/readiness
```

这个 readiness 只检查本地目录、auth 配置、服务 URL 格式、assets 目录和 traceability 文档，不会主动调用 Qwen3.5、SAM2.1、PowerPaint 或本地 FLUX 模型。

## 9. 首次运行为什么会慢

首次启动或首次请求时，服务会下载或加载：

- Qwen3.5 权重
- SAM-2 权重
- PowerPaint 2.1 权重
- FLUX 初图模型权重

因此第一次调用 `/api/plan`、`/api/segment`、`/api/generate` 明显偏慢是正常的。
第一次调用 `/api/init-generate` 且命中本地 FLUX 时也会加载 FLUX 模型，建议先用小尺寸请求预热。

## 10. 常见问题

### 10.1 Conda 环境能不能互相通信

可以。它们不是直接共享 Python 包，而是通过 HTTP 端口通信。

### 10.2 GPU 冲突

如果某张卡已经被占用，直接改 `.env.nodocker` 里的 GPU 编号，然后重启对应脚本。

### 10.3 前端打开后请求失败

优先检查：

- `PUBLIC_GATEWAY_BASE_URL` 是否写成了真实服务器 IP
- `gateway` 是否真的在对应地址监听
- 防火墙是否放行前端端口
- 如果启用了 token，`GATEWAY_API_TOKEN` 和构建前端时的 `VITE_API_TOKEN` 是否一致
- 修改 `VITE_API_TOKEN` 后是否重新运行了 `bash scripts/build_frontend.sh`

### 10.4 PowerPaint 没启动

优先检查：

- `POWERPAINT_REPO_PATH` 是否正确
- 官方 PowerPaint 仓库是否已经克隆
- `bash scripts/fetch_powerpaint_model.sh` 是否已经把 `PowerPaint 2.1` 权重拉到本地
- 相关 Python 依赖是否安装完整

### 10.5 本地 FLUX 初图失败

优先检查：

- `bash scripts/run_flux.sh` 是否已经启动
- `curl http://127.0.0.1:19085/health` 是否返回 JSON
- `FLUX_MODEL_REPO` 是否是可访问的 Hugging Face repo 或服务器本地模型目录
- 如果设置了 `FLUX_LOCAL_FILES_ONLY=true`，模型权重是否已经在本地缓存或模型目录中
- `FLUX_CUDA_VISIBLE_DEVICES` 指向的 GPU 是否空闲

Gateway 的默认 `auto` 初图请求在本地 FLUX 不可用时会回退到确定性 fallback；显式 `flux-local` 请求会返回错误。

### 10.6 运行数据在哪里

默认运行数据目录：

```text
data/runs         生成图、mask、质量报告和中间产物
data/projects     项目 JSON 快照与版本链
data/jobs         异步任务 JSON 快照
data/benchmarks   benchmark run ledger
models            Hugging Face 与 PowerPaint 权重缓存
```

迁移服务器或备份毕业设计演示数据时，至少备份 `data/` 和必要的 `models/`。

### 10.7 PowerPaint Code And Weight Sources

- `POWERPAINT_REPO_GIT_URL` points to the PowerPaint code repository, by default `https://github.com/zhuang2002/PowerPaint.git`
- `POWERPAINT_MODEL_GIT_URL` points to the `PowerPaint 2.1` weight repository, by default `https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1`
- Cloning the GitHub code repository does not include the `PowerPaint 2.1` checkpoints
- If the server cannot reach `huggingface.co:443`, download `ppt-v2-1` on another machine first, then copy it to `/home/common/yzhu_2025/science-diagram-platform/models/powerpaint/ppt-v2-1`
