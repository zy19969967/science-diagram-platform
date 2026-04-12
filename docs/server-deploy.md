# 服务器部署说明

这份文档对应当前仓库的推荐部署方式：本机开发，服务器运行，使用 Docker Compose 拉起前端、网关和推理服务。

## 1. 环境要求

推荐环境：

- Ubuntu 22.04 或兼容 Linux 发行版
- Docker 24+
- Docker Compose v2
- NVIDIA 驱动
- NVIDIA Container Toolkit
- 至少 1 张可用 NVIDIA GPU

如果要继续把 `planner` 和 `segmenter` 换成真实模型，建议保留多张 GPU。

## 2. 推荐部署目录

建议把项目放在：

```text
/home/common/yzhu_2025/science-diagram-platform
```

不建议放到系统盘 `/` 下，因为 Docker 镜像层、模型缓存和构建中间产物会比较占空间。

## 3. 从 GitHub 获取项目

### HTTPS

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

### SSH

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone git@github.com:zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

## 4. 准备环境变量

复制服务器环境变量模板：

```bash
cp .env.server.example .env
```

当前推荐至少确认以下变量：

```bash
FRONTEND_PUBLIC_PORT=8080
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=8000
POWERPAINT_CUDA_VISIBLE_DEVICES=2
```

## 5. 构建和启动

如果当前账号没有 Docker daemon 权限，请直接使用 `sudo`：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

## 6. 查看运行状态

```bash
sudo docker compose ps
sudo docker compose logs -f frontend
sudo docker compose logs -f gateway
sudo docker compose logs -f powerpaint
```

## 7. 访问前端

以服务器 IP `211.87.232.112` 和默认端口 `8080` 为例：

```text
http://211.87.232.112:8080
```

## 8. 常见问题

### Docker 权限不足

如果看到 `permission denied while trying to connect to the Docker daemon socket`，说明当前账号不能直接访问 Docker，需要改用：

```bash
sudo docker compose ...
```

### 系统盘空间不足

建议先检查 Docker 根目录：

```bash
sudo docker info | grep 'Docker Root Dir'
```

如果 Docker 仍把数据写到系统盘，而系统盘空间不够，先迁移 Docker 数据目录再重新构建。

### PowerPaint 启动慢

首次构建与启动会下载依赖和模型，耗时较长是正常现象。建议持续看日志：

```bash
sudo docker compose logs -f powerpaint
```

### GPU 被占用

如果你预设的 GPU 正在被其他任务占用，可以在 `.env` 中修改：

```bash
POWERPAINT_CUDA_VISIBLE_DEVICES=7
```

然后重启：

```bash
sudo docker compose --env-file .env up -d --build
```
