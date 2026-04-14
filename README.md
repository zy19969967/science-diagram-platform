# 科学示意图交互式生成平台

基于技术报告与 [PowerPaint](https://github.com/open-mmlab/PowerPaint) 搭建的交互式科学示意图生成系统，采用前后端分离和 Docker Compose 编排，支持“上传底图 -> 规划编辑意图 -> 生成/细化 mask -> 调用 PowerPaint -> 回流下一轮编辑”的完整流程。

当前版本已经把 `planner` 和 `segmenter` 从占位逻辑升级为“真实模型优先、规则回退兜底”的实现：

- `planner` 优先调用官方 Hugging Face `Qwen/Qwen3.5-4B` 多模态模型，结合图像和文字生成结构化编辑计划。
- `segmenter` 优先调用官方 Hugging Face `facebook/sam2.1-hiera-base-plus`，对用户粗选区做 SAM-2 细化。
- `powerpaint_service` 继续调用官方 [PowerPaint](https://github.com/open-mmlab/PowerPaint) 仓库执行局部编辑。
- 当模型下载失败、GPU 不可用或模型输出异常时，系统会自动回退到仓库内置的轻量规则逻辑，保证服务仍可启动和调试。

仓库地址：<https://github.com/zy19969967/science-diagram-platform>

## 目录结构

```text
backend/
  assets/               科学素材目录
  common/               共享数据结构与通用逻辑
  gateway/              API 网关
  planner/              Qwen3.5 规划服务
  powerpaint_service/   PowerPaint 执行服务
  segmenter/            SAM-2 分割服务
frontend/               React 前端
data/runs/              生成结果与中间产物
docs/                   部署与架构文档
docker-compose.yml      服务编排文件
```

## 服务器推荐目录

建议在服务器中把项目克隆到下面这个目录：

```text
/home/common/yzhu_2025/science-diagram-platform
```

原因：

- 系统盘 `/` 空间通常偏紧，不适合存放 Docker 镜像和模型缓存。
- `/home/common` 更适合保存镜像层、模型、运行产物和日志。

## 4 卡部署建议

你当前服务器是 8 x RTX 3090 24GB，但本项目先按 4 张卡规划即可，推荐预留：

```text
2,3,6,7
```

推荐分配：

- GPU 2：`powerpaint_service`
- GPU 3：`planner`
- GPU 6：`segmenter`
- GPU 7：备用卡

## 服务器部署步骤

### 1. 克隆仓库

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
```

### 2. 复制环境变量

```bash
cp .env.server.example .env
```

### 3. 核对关键配置

模板里已经写好了真实模型配置，最少确认下面这些值：

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

如果你希望只读取本地缓存模型，也可以改成：

```bash
PLANNER_LOCAL_FILES_ONLY=true
SEGMENTER_LOCAL_FILES_ONLY=true
POWERPAINT_LOCAL_FILES_ONLY=true
```

### 4. 构建并启动

如果当前用户没有 Docker socket 权限，请直接使用 `sudo`：

```bash
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

### 5. 查看状态与日志

```bash
sudo docker compose ps
sudo docker compose logs -f planner
sudo docker compose logs -f segmenter
sudo docker compose logs -f powerpaint
sudo docker compose logs -f gateway
```

### 6. 浏览器访问

假设服务器公网 IP 是 `211.87.232.112`，并且 `.env` 中保留：

```bash
FRONTEND_PUBLIC_PORT=8080
```

那么访问地址为：

```text
http://211.87.232.112:8080
```

## 当前实现的策略说明

- `/api/plan` 现在会把原图一起发给 `planner`，让 Qwen3.5 参考图像内容生成 PowerPaint 所需的结构化计划。
- `/api/segment` 和 `/api/generate` 会把原图一起发给 `segmenter`，让 SAM-2 用用户粗选区的外接框做精细分割。
- 如果用户只是拖了素材位置、并没有指向现有图中对象，`segmenter` 会自动回退到几何 mask，避免 SAM-2 错分背景。
- 这样既满足“真实模型接入”，也保留了毕业设计演示时最稳妥的回退路径。

## 部署前建议检查

```bash
sudo docker info | grep 'Docker Root Dir'
nvidia-smi
```

如果 GPU 2、3 或 6 已被占满，可以在 `.env` 中替换成其他空闲卡，再执行：

```bash
sudo docker compose --env-file .env up -d --build
```

## 相关文档

- [服务器部署说明](docs/server-deploy.md)
- [4 卡部署说明](docs/server-4gpu-notes.md)
- [系统架构说明](docs/architecture.md)
