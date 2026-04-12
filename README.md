# 科学示意图交互式生成平台

基于技术报告与 [PowerPaint](https://github.com/open-mmlab/PowerPaint) 搭建的交互式科学示意图生成系统，采用前后端分离和 Docker Compose 编排，目标是支持“上传底图 -> 解析编辑意图 -> 生成 mask -> 调用 PowerPaint -> 回流下一轮编辑”的完整流程。

当前仓库已经按“本机开发、服务器运行”的方式整理完成，推荐直接推送到 GitHub 后，在服务器上通过 `git clone` 部署。

## 项目特点

- 前端使用 React + Vite，支持上传图片、手绘 mask、素材拖拽、任务输入与结果预览。
- 后端使用 FastAPI 拆分为 `gateway`、`planner`、`segmenter`、`powerpaint_service` 四个服务。
- 推理服务通过 Docker Compose 管理，适合在多 GPU Linux 服务器上部署。
- PowerPaint 权重通过 Hugging Face 在容器启动时拉取，便于后续替换为真实模型。
- 结果会按运行轮次保存到 `data/runs/<run_id>/`，便于调试、答辩演示和过程记录。

## 目录结构

```text
backend/
  assets/               科学素材目录
  common/               共享数据结构与通用逻辑
  gateway/              API 网关
  planner/              规划服务占位实现
  powerpaint_service/   PowerPaint 封装服务
  segmenter/            分割服务占位实现
frontend/               React 前端
data/runs/              生成结果与中间产物
docs/                   部署与架构文档
docker-compose.yml      服务编排文件
```

## 推荐部署方式

推荐在服务器中把项目克隆到下面这个目录：

```text
/home/common/yzhu_2025/science-diagram-platform
```

原因：

- 服务器系统盘 `/` 可用空间通常偏紧，不适合存放 Docker 镜像和模型缓存。
- `/home/common` 空间更大，更适合保存镜像层、模型、运行产物和日志。

## GitHub 克隆地址

HTTPS：

```bash
git clone https://github.com/zy19969967/science-diagram-platform.git
```

SSH：

```bash
git clone git@github.com:zy19969967/science-diagram-platform.git
```

## 4 卡部署建议

你当前服务器是 8 x RTX 3090 24GB，但本项目先按 4 张卡规划即可。结合你给出的占用情况，建议预留以下卡：

```text
2,3,6,7
```

建议分配方式：

- GPU 2：当前 `powerpaint_service` 默认使用这张卡。
- GPU 3：为后续接入真实 `planner` 模型预留。
- GPU 6：为后续接入真实 `segmenter` 模型预留。
- GPU 7：留作备用卡，用于扩展推理或调试。

注意：当前仓库里真正使用 GPU 的服务只有 `powerpaint_service`，所以默认只会先占用 1 张卡；其余 3 张卡是为了后续把 `planner` 和 `segmenter` 换成真实模型时直接沿用这套部署策略。

## 服务器部署步骤

### 1. 进入目标目录

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
```

### 2. 克隆仓库

```bash
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

### 3. 复制服务器环境变量

```bash
cp .env.server.example .env
```

### 4. 按需修改 `.env`

最低限度建议确认这几个值：

```bash
FRONTEND_PUBLIC_PORT=8080
GATEWAY_BIND_HOST=127.0.0.1
GATEWAY_PUBLIC_PORT=8000
POWERPAINT_CUDA_VISIBLE_DEVICES=2
```

如果你后面接入真实 `planner` 和 `segmenter`，也可以继续沿用同一份 GPU 规划：

```bash
PROJECT_GPU_POOL=2,3,6,7
PLANNER_CUDA_VISIBLE_DEVICES=3
SEGMENTER_CUDA_VISIBLE_DEVICES=6
AUX_CUDA_VISIBLE_DEVICES=7
```

### 5. 构建并启动

如果当前用户没有 Docker socket 权限，请直接使用 `sudo`：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

### 6. 查看状态与日志

```bash
sudo docker compose ps
sudo docker compose logs -f powerpaint
sudo docker compose logs -f gateway
sudo docker compose logs -f frontend
```

### 7. 浏览器访问

假设服务器公网 IP 是 `211.87.232.112`，并且你在 `.env` 里保留了：

```bash
FRONTEND_PUBLIC_PORT=8080
```

那么前端访问地址是：

```text
http://211.87.232.112:8080
```

## 部署前建议检查

### 1. Docker 数据目录

系统盘空间紧张时，建议先确认 Docker 根目录位置：

```bash
sudo docker info | grep 'Docker Root Dir'
```

如果 Docker Root Dir 仍在系统盘，而系统盘只剩很少空间，建议先迁移 Docker 数据目录后再构建镜像。

### 2. GPU 使用情况

部署前建议先看一下哪些卡是空闲的：

```bash
nvidia-smi
```

如果 GPU 2 被别人占满，可以把 `.env` 中的 `POWERPAINT_CUDA_VISIBLE_DEVICES` 改成 `7` 或其他空闲卡。

### 3. PowerPaint 首次启动时间

首次启动 `powerpaint_service` 会：

- 克隆 PowerPaint 仓库
- 安装依赖
- 拉取 Hugging Face 权重

因此第一次 `up -d` 比较慢是正常现象，建议持续观察：

```bash
sudo docker compose logs -f powerpaint
```

## 后续可扩展方向

1. 将 `planner` 接入真实 Qwen3.5 多模态或文本规划模型。
2. 将 `segmenter` 接入真实 SAM-2 分割流程。
3. 为前端增加更多科学器材素材和实验流程模板。
4. 为网关增加任务队列、历史记录检索和结果导出功能。
5. 在前端 Nginx 前面再加 Caddy 或 Nginx，统一做 HTTPS 和反向代理。

## 相关文档

- [服务器部署说明](docs/server-deploy.md)
- [4 卡部署说明](docs/server-4gpu-notes.md)
- [系统架构说明](docs/architecture.md)
