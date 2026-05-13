# 服务器部署检查清单

这份清单面向“现在要把项目部署到服务器上跑起来”的场景。更细的分支文档见：

- Docker Compose 路径：`docs/server-deploy.md`
- 无 Docker / Conda 路径：`docs/server-conda-deploy.md`

## 0. 现在可以部署吗

可以部署，但要注意 5 个边界：

1. 当前完整功能已经落在 `main`，服务器直接部署默认分支即可。
2. 推荐优先使用 Docker Compose。它会同时启动 `frontend`、`gateway`、`planner`、`segmenter`、`powerpaint` 和本地 `flux` 服务。
3. 项目不会把 Qwen3.5、SAM2.1、PowerPaint 2.1、FLUX 权重提交进 Git。首次启动或首次请求时需要下载，或者你提前把模型放到服务器缓存目录。
4. 当前部署是单节点、单用户、文件持久化方案，适合毕业设计演示、内网测试和受控服务器环境；不是公网多租户生产系统。
5. 如果服务器不能用 Docker，再走 Conda/tmux 路径。

FLUX 的生成链路默认在服务器本地 `flux` 服务里运行，不调用外部 FLUX API。只有下载或更新模型权重时，才可能访问 Hugging Face；如果服务器不能联网，可以提前把模型权重复制到本地缓存或本地模型目录。

## 1. 推荐服务器条件

建议服务器满足：

- Ubuntu 22.04 或兼容 Linux 发行版
- NVIDIA GPU 可用，推荐 2 张 H20-NVLink 96GB 用于默认配置
- NVIDIA 驱动和 `nvidia-smi` 可用
- Docker 24+ 和 Docker Compose v2 可用
- NVIDIA Container Toolkit 可用
- 磁盘空间充足，建议把项目、模型和 Docker 数据放在大盘，不要放在系统盘根目录
- 能访问 GitHub、Hugging Face，或者已经提前准备好模型缓存

示例 GPU 分配：

```text
GPU 0 -> qwen-image
GPU 1 -> powerpaint_service, planner, segmenter, flux
```

如果你的服务器 GPU 编号不同，只要在 `.env` 中改对应变量即可。

## 2. 先在服务器上做环境检查

登录服务器后运行：

```bash
nvidia-smi
docker --version
docker compose version
df -h
```

如果 `docker` 需要 sudo，后续命令都用 `sudo docker ...`。

如果项目已经 clone，可以运行仓库脚本：

```bash
bash scripts/server-preflight.sh
```

## 3. 克隆正确分支

推荐目录：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
```

当前完整功能已经落在 `main`，直接克隆默认分支：

```bash
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

确认分支：

```bash
git status --short --branch
git log --oneline -3
```

## 4. 准备 Docker 环境变量

复制模板：

```bash
cp .env.server.example .env
```

编辑 `.env`：

```bash
nano .env
```

至少确认这些项：

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
HF_ENDPOINT=https://hf-mirror.com

FLUX_INIT_URL=
FLUX_MODEL_REPO=black-forest-labs/FLUX.2-klein-4B
FLUX_MODEL_DTYPE=bfloat16
FLUX_NUM_INFERENCE_STEPS=4
FLUX_GUIDANCE_SCALE=1.0
FLUX_MAX_SEQUENCE_LENGTH=512

GATEWAY_API_TOKEN=
VITE_API_TOKEN=
```

说明：

- `FLUX_INIT_URL` 留空时，Docker Compose 会默认让 Gateway 调用本地 `http://flux:8004`。
- 初图生成不会调用外部 FLUX API；Gateway 只访问 Compose 内部的本地 `flux` 服务。
- `HF_ENDPOINT=https://hf-mirror.com` 会让 Hugging Face 权重下载优先走镜像站；如果镜像站不可用，可以改回 `https://huggingface.co` 或清空该变量。
- 默认 FLUX 模型是 Apache 2.0 开源的 `black-forest-labs/FLUX.2-klein-4B`，通常需要约 13GB VRAM；首次启动或模型更新时可能需要从 Hugging Face 下载权重。
- 如果你已经有服务器本地 FLUX 模型目录，可以把 `FLUX_MODEL_REPO` 改成那个目录。
- 如果设置 `GATEWAY_API_TOKEN`，必须把 `VITE_API_TOKEN` 设置成同一个值，并重新 build 前端。
- 如果只是内网演示，可以先保持 token 为空，确认链路跑通后再加 token。

## 5. 构建 Docker 镜像

首次构建：

```bash
sudo docker compose --env-file .env build
```

首次构建会下载 CUDA PyTorch、后端依赖、前端依赖和模型相关依赖，耗时较长。失败时先看错误属于：

- 网络访问失败
- 磁盘空间不足
- Docker 权限不足
- CUDA/PyTorch wheel 源不可用

## 6. 启动服务

```bash
sudo docker compose --env-file .env --profile qwen-image up -d
```

查看容器：

```bash
sudo docker compose ps
```

查看日志：

```bash
sudo docker compose logs -f frontend
sudo docker compose logs -f gateway
sudo docker compose logs -f planner
sudo docker compose logs -f segmenter
sudo docker compose logs -f powerpaint
sudo docker compose logs -f flux
```

## 7. 健康检查

在服务器上检查 Gateway：

```bash
curl http://127.0.0.1:19080/api/health
```

检查部署 readiness：

```bash
curl http://127.0.0.1:19080/api/deployment/readiness
```

如果启用了 token：

```bash
curl -H "Authorization: Bearer <你的token>" http://127.0.0.1:19080/api/deployment/readiness
```

readiness 只检查目录、配置、服务 URL 和 traceability 文件；它不会真正加载 Qwen3.5、SAM2.1、PowerPaint 或 FLUX 模型。

## 8. 浏览器访问

如果服务器 IP 是 `211.87.232.112`，并且 `FRONTEND_PUBLIC_PORT=19084`，浏览器打开：

```text
http://211.87.232.112:19084
```

如果打不开，按顺序检查：

```bash
sudo docker compose ps
sudo docker compose logs -f frontend
curl http://127.0.0.1:19084
```

然后检查服务器防火墙或学校/实验室网络是否放行 `19084`。

## 9. 第一次功能验证

建议按这个顺序手动验证：

1. 打开前端页面。
2. 在无图生成输入框里输入一个简单需求，例如：`画一个酶促反应示意图，包含底物、酶、产物和箭头`。
3. 点击初图生成，观察是否出现候选图。
4. 如果本地 FLUX 模型还没下载或加载失败，前端应显示 fallback 候选，这说明 Gateway 仍然可用。
5. 选择一张候选图进入编辑。
6. 画 mask 或添加 SAM 点提示。
7. 输入局部编辑指令，执行同步或异步生成。
8. 查看结果、质量报告、项目保存、benchmark 记录是否能使用。

首次请求慢是正常现象，因为模型采用惰性加载：

- `/api/plan` 首次调用会加载 Qwen3.5
- `/api/segment` 首次调用会加载 SAM2.1
- `/api/init-generate` 命中本地 FLUX 时会加载 FLUX
- `/api/generate` 会调用 PowerPaint

## 10. 模型提前准备建议

如果服务器网络访问 Hugging Face 不稳定，建议提前准备：

```text
models/huggingface/       Qwen3.5、SAM2.1、FLUX 缓存
models/powerpaint/        PowerPaint 2.1 权重
```

然后在 `.env` 中打开本地模式：

```bash
PLANNER_LOCAL_FILES_ONLY=true
SEGMENTER_LOCAL_FILES_ONLY=true
POWERPAINT_LOCAL_FILES_ONLY=true
FLUX_LOCAL_FILES_ONLY=true
```

注意：本地模式打开后，如果缓存不完整，服务会直接报错。

## 11. 更新服务器代码

当前部署 `main` 时：

```bash
cd /home/common/yzhu_2025/science-diagram-platform
git pull origin main
sudo docker compose --env-file .env --profile qwen-image up -d --build
```

## 12. 无 Docker 时怎么部署

如果服务器不能使用 Docker：

```bash
cp .env.nodocker.example .env.nodocker
bash scripts/setup_conda_envs.sh
bash scripts/start_all_tmux.sh --with-frontend
bash scripts/check_gpu_envs.sh
bash scripts/check_services.sh
bash scripts/prewarm_models.sh
```

无 Docker 路径会启动这些服务：

```text
planner    127.0.0.1:19081
segmenter  127.0.0.1:19083
powerpaint 127.0.0.1:19082
flux       127.0.0.1:19085
gateway    127.0.0.1:19080
frontend   0.0.0.0:19084
```

详细步骤见 `docs/server-conda-deploy.md`。

## 13. 常见故障判断

### 前端打不开

- `sudo docker compose ps`
- `sudo docker compose logs -f frontend`
- 检查 `FRONTEND_PUBLIC_PORT`
- 检查服务器防火墙

### Gateway 401

- 是否设置了 `GATEWAY_API_TOKEN`
- `VITE_API_TOKEN` 是否和它一致
- 改 token 后是否重新 build 前端

### 初图只出现 fallback

- `sudo docker compose logs -f flux`
- `FLUX_MODEL_REPO` 是否正确
- `FLUX_LOCAL_FILES_ONLY=true` 时缓存是否完整
- `FLUX_CUDA_VISIBLE_DEVICES` 对应 GPU 1 是否空闲，或是否已经按实际 H20 编号调整

### PowerPaint 失败

- `sudo docker compose logs -f powerpaint`
- `POWERPAINT_MODEL_DIR_NAME` 是否对应实际权重目录
- PowerPaint 2.1 权重是否已经下载到 `models/powerpaint/ppt-v2-1`

### 首次请求很慢

这是正常情况。先看日志确认模型正在下载或加载，不要急着重启容器。Conda/tmux 部署可以在演示前运行 `bash scripts/prewarm_models.sh` 顺序预热 `planner`、`segmenter`、`powerpaint` 和 `flux`。

### 磁盘不足

- `df -h`
- `sudo docker system df`
- 检查 Docker Root Dir 是否在系统盘
- 必要时把 `models/`、`data/`、Docker 数据目录迁移到大盘

## 14. 部署后要备份什么

至少备份：

```text
data/runs/
data/projects/
data/jobs/
data/benchmarks/
.env
```

如果不想重新下载模型，也备份：

```text
models/
```
