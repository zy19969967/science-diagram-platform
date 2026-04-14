# 服务器部署说明

这份文档对应当前仓库的推荐部署方式：本机开发，服务器运行，使用 Docker Compose 拉起前端、网关、Qwen3.5 规划服务、SAM-2 分割服务和 PowerPaint 执行服务。

## 环境要求

- Ubuntu 22.04 或兼容 Linux 发行版
- Docker 24+
- Docker Compose v2
- NVIDIA 驱动
- NVIDIA Container Toolkit
- 至少 3 张可用 NVIDIA GPU

## 推荐部署目录

```text
/home/common/yzhu_2025/science-diagram-platform
```

## 获取项目

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

## 准备环境变量

```bash
cp .env.server.example .env
```

建议至少确认：

```bash
FRONTEND_PUBLIC_PORT=8080
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=8000
POWERPAINT_CUDA_VISIBLE_DEVICES=2
PLANNER_CUDA_VISIBLE_DEVICES=3
SEGMENTER_CUDA_VISIBLE_DEVICES=6
PLANNER_MODEL_REPO=Qwen/Qwen3.5-4B
SEGMENTER_MODEL_REPO=facebook/sam2.1-hiera-base-plus
```

## 构建和启动

如果当前账号没有 Docker daemon 权限，请直接使用 `sudo`：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

## 查看运行状态

```bash
sudo docker compose ps
sudo docker compose logs -f frontend
sudo docker compose logs -f gateway
sudo docker compose logs -f planner
sudo docker compose logs -f segmenter
sudo docker compose logs -f powerpaint
```

## 首次启动说明

首次构建与启动会下载：

- CUDA 版 PyTorch 轮子
- Qwen3.5 模型权重
- SAM-2 模型权重
- PowerPaint 仓库依赖与权重

因此第一次启动较慢是正常现象。

## 常见问题

### Docker 权限不足

```bash
sudo docker compose ...
```

### 系统盘空间不足

```bash
sudo docker info | grep 'Docker Root Dir'
```

### GPU 被占用

修改 `.env` 后重启：

```bash
sudo docker compose --env-file .env up -d --build
```

### 想离线启动

```bash
PLANNER_LOCAL_FILES_ONLY=true
SEGMENTER_LOCAL_FILES_ONLY=true
POWERPAINT_LOCAL_FILES_ONLY=true
```
