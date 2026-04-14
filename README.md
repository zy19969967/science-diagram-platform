# 科学示意图交互式生成平台

基于技术报告与 [PowerPaint](https://github.com/open-mmlab/PowerPaint) 搭建的交互式科学示意图生成系统，采用前后端分离和 Docker Compose 编排，支持“上传底图 -> 规划编辑意图 -> 生成/细化 mask -> 调用 PowerPaint -> 回流下一轮编辑”的完整流程。

当前版本已经接入真实模型优先的运行链路：

- `planner`：优先调用官方 Hugging Face `Qwen/Qwen3.5-4B`
- `segmenter`：优先调用官方 Hugging Face `facebook/sam2.1-hiera-base-plus`
- `powerpaint_service`：继续调用官方 [PowerPaint](https://github.com/open-mmlab/PowerPaint)
- 当真实模型不可用、GPU 不可用或模型输出异常时，会自动回退到仓库内的规则逻辑

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
scripts/                服务器辅助脚本
docker-compose.yml      服务编排文件
```

## 快速部署

推荐服务器部署目录：

```text
/home/common/yzhu_2025/science-diagram-platform
```

当前模板示例的 4 卡分配：

- GPU 4：`powerpaint_service`
- GPU 5：`planner`
- GPU 6：`segmenter`
- GPU 7：备用

如果服务器可用 Docker，最短部署路径如下：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.server.example .env
sudo docker compose --env-file .env build
sudo docker compose --env-file .env up -d
```

如果服务器不能使用 Docker，请改看无 Docker 文档，并使用 `scripts/setup_venvs.sh`、`scripts/start_all_tmux.sh`、`scripts/run_*.sh` 这组脚本。

浏览器访问：

```text
http://<你的服务器IP>:8080
```

## 推荐先做的检查

可以直接运行：

```bash
bash scripts/server-preflight.sh
```

它会输出：

- 操作系统信息
- `nvidia-smi`
- Docker / Docker Compose 版本
- NVIDIA Container Toolkit
- 内存、磁盘、网络
- Docker Root Dir

## 当前实现说明

- `/api/plan` 会把原图一起发给 `planner`，让 Qwen3.5 参考图像内容生成结构化计划
- `/api/segment` 和 `/api/generate` 会把原图一起发给 `segmenter`，让 SAM-2 用粗选区外接框做精细分割
- 如果用户只是拖了素材位置、并没有明确选中图中对象，`segmenter` 会自动回退到几何 mask
- 前端反向代理已经调大 `/api` 超时，降低模型冷启动时的前端超时概率
- 对于无 Docker 场景，仓库已经补齐多 `venv` 安装脚本、启动脚本、tmux 管理脚本和部署文档

## 相关文档

- [服务器部署 README](docs/server-deploy.md)
- [无 Docker 服务器部署 README](docs/server-venv-deploy.md)
- [服务器执行清单](docs/server-execution-checklist.md)
- [4 卡部署说明](docs/server-4gpu-notes.md)
- [已知问题与后续缺口](docs/known-issues.md)
- [系统架构说明](docs/architecture.md)
