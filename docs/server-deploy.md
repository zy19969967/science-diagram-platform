# 服务器部署 README

如果你的服务器不能使用 Docker、但可以使用 Conda，请改看：

- [无 Docker / Conda 服务器部署 README](server-conda-deploy.md)

这份文档面向“本机开发、服务器运行”的部署方式，默认目标环境是 Ubuntu 22.04 + Docker Compose + NVIDIA GPU 服务器。当前仓库已经接入真实模型优先的运行链路：

- `planner`：优先调用 `Qwen/Qwen3.5-4B`
- `segmenter`：优先调用 `facebook/sam2.1-hiera-base-plus`
- `powerpaint_service`：调用官方 `PowerPaint`
- 当真实模型不可用时，会自动回退到仓库内规则逻辑，保证平台还能用于调试和演示

## 1. 部署前提

建议服务器满足以下条件：

- Ubuntu 22.04 或兼容 Linux 发行版
- Docker 24+
- Docker Compose v2
- NVIDIA 驱动
- NVIDIA Container Toolkit
- 至少 3 张可用 GPU
- 足够的磁盘空间保存 Docker 镜像和模型缓存

如果你使用的正是当前这台 8 x RTX 3090 服务器，当前模板示例按 4 卡方式部署：

- GPU 4：`powerpaint_service`
- GPU 5：`planner`
- GPU 6：`segmenter`
- GPU 7：备用卡

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

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

## 5. 准备环境变量

复制服务器模板：

```bash
cp .env.server.example .env
```

当前模板已经写好了真实模型配置，最少桮认下面这些项：

```bash
FRONTEND_PUBLIC_PORT=19084
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=19080

POWERPAINT_CUDA_VISIBLE_DEVICES=4
PLANNER_CUDA_VISIBLE_DEVICES=5
SEGMENTER_CUDA_VISIBLE_DEVICES=6
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
```

几个关键说明：

- `GATEWAY_BIND_HOST=127.0.0.1` 表示网关只对本机开放，前端容器通过 Docker 网络反向代理访问它
- `FRONTEND_PUBLIC_PORT=19084` 表示浏览器最终访问的是前端容器
- `PowerPaint 2.1` 仍然复用 BrushNet 的 `ppt-v2` 推理分支，因此 `POWERPAINT_VERSION` 保持 `ppt-v2`
- `AUX_CUDA_VISIBLE_DEVICES` 目前只是预留备用卡，不会被 Compose 自动绑定到服务

如果你已经提前下载过模型，也可以开启纯本地模式：

```bash
PLANNER_LOCAL_FILES_ONLY=true
SEGMENTER_LOCAL_FILES_ONLY=true
POWERPAINT_LOCAL_FILES_ONLY=true
```

注意：开启本地模式后，如果缓存目录里没有对应权重，服务会直接报错，而不是联网下载。

## 6. 首次构建

如果你用户涨正是 Docker daemon 权限，请使用 `sudo`：

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

## 9. 首次请求较慢是正常现象

`planner` 和 `segmenter` 采用惰性加载。也就是说：

- 容器可以先启动成功
- 第一次真正调用 `/api/plan` 或 `/api/segment` 时才加载模型
- 首次请求明显比后续请求慢

为了避免前端经由 Nginx 反代时在冷启动阶段超时，前端容器已经把 `/api` 代理超时调大到 600 秒。

## 10. 模型缓存与磁盘建议

仓库默认把模型缓存挂到项目下的 `./models`：

```text
./models
```

这样做的好处是：

- `planner`、`segmenter`、`powerpaint` 共享 Hugging Face 缓存
- 重启容器不必重新下载所有模型
- 更容易把模型目录迁移到大盘路径

如果 Docker Root Dir 仍在系统盘，可以先检查：

```bash
sudo docker info | grep 'Docker Root Dir'
```

## 11. 更新项目

以后更新仓库时，推荐这样做：

```bash
cd /home/common/yzhu_2025/science-diagram-platform
git pull
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
- `powerpaint` 日志里是否正在初始化权重

这通常不是死机，而是冷启动。

### 12.6 Where PowerPaint 2.1 Weights Come From

`POWERPAINT_REPO_GIT_URL` only pulls the PowerPaint code repository. The `PowerPaint 2.1` weights are not stored in the GitHub code repository. They still need to come from the Hugging Face Git LFS repository referenced by `POWERPAINT_MODEL_GIT_URL`, or be copied into the model directory ahead of time.
