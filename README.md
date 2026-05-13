# 科学示意图交互式生成平台

基于技术报告与 [PowerPaint](https://github.com/open-mmlab/PowerPaint) 搭建的交互式科学示意图生成系统。当前 `main` 分支已经完成技术报告对齐的 13 个阶段：从文本初图、局部编辑、异步任务、画布状态、项目持久化、Fabric 图层编辑、SAM 点提示、OCR-ready SVG 导出、本地 FLUX-compatible 初图服务、实验台账，到部署 readiness 和单 token 网关保护。

仓库地址：<https://github.com/zy19969967/science-diagram-platform>

## 当前能力

- 文本初图入口：`/api/init-plan` 和 `/api/init-generate` 支持无底图的初始画布候选；Gateway 默认调用本地 `flux` 服务，没有可用 FLUX 权重或服务异常时会回退到确定性候选。
- 交互式编辑链路：上传底图、绘制 mask、放置素材、添加文字层、使用 SAM 正/负点提示，再调用 PowerPaint 生成局部结果。
- 同步与异步生成：保留旧的 `/api/generate` 同步接口，同时新增 `/api/jobs`、`/api/jobs/{job_id}` 和取消接口。
- 可序列化画布状态：base、mask、asset、text layer、point prompts、quality report 和 provenance 可以随请求与项目版本保存。
- 项目与版本持久化：Gateway 以 JSON 文件保存项目快照和父版本关系，适合单用户演示与毕业设计迭代。
- 图层编辑器：前端接入首个 Fabric.js 图层编辑切片，支持素材/文字层选择、移动、缩放、显示、锁定和排序。
- 文本校验与导出：`/api/canvas/validate-text` 支持 OCR-ready 文本一致性合同，`/api/canvas/export-svg` 可导出包含可编辑 `<text>` 的 SVG。
- 实验台账：`/api/benchmarks/runs` 和 `/api/benchmarks/summary` 记录质量指标、provider、文本校验和项目版本信息。
- 部署加固：可选 `GATEWAY_API_TOKEN` 单 token 保护、前端 `VITE_API_TOKEN` 透传、`/api/deployment/readiness` 本地配置检查和对齐追踪表。

这些能力仍然是单节点、单用户、文件持久化优先的实现，不等同于生产级多租户系统。完整限制见 [已知问题与后续缺口](docs/known-issues.md) 和 [技术报告对齐追踪表](docs/report-traceability.md)。

## 服务组成

```text
backend/
  assets/               科学素材目录
  common/               共享 schema、画布状态、质量评估、导出逻辑
  gateway/              API 网关、任务、项目、实验台账、部署 readiness
  flux_service/         本地 FLUX-compatible 初图服务
  qwen_image_service/   Qwen-Image 本地图像编辑服务
  planner/              Qwen3.5 规划服务
  powerpaint_service/   PowerPaint 执行服务
  segmenter/            SAM-2 分割服务
frontend/               React + Vite + Fabric.js 前端
data/
  runs/                 生成结果与中间产物
  projects/             项目快照
  jobs/                 异步任务快照
  benchmarks/           实验台账
docs/                   部署、架构、对齐追踪与已知限制
scripts/                服务器辅助脚本
docker-compose.yml      Docker Compose 编排
```

真实模型优先链路：

- `planner`：优先调用 Hugging Face `Qwen/Qwen3.5-4B`
- `segmenter`：优先调用 Hugging Face `facebook/sam2.1-hiera-base-plus`
- `powerpaint_service`：调用官方 [PowerPaint](https://github.com/open-mmlab/PowerPaint)
- `flux_service`：本地 diffusers FLUX-compatible 初图服务，默认模型为 `black-forest-labs/FLUX.2-klein-4B`，通过 `Flux2KleinPipeline` 加载；模型为 Apache 2.0 开源权重，约需 13GB VRAM，权重不提交进仓库，首次运行或更新时可能需要从 Hugging Face 下载
- `qwen_image_service`：本地 Qwen-Image 编辑服务，Docker 内部服务名为 `qwen-image:8005`，Conda/tmux 默认端口为 `QWEN_IMAGE_PORT=19086`；第一版默认使用 `Qwen/Qwen-Image-Edit`，第一版不默认使用 Qwen-Image-Edit-2511
- `init provider`：Gateway 默认通过 `FLUX_INIT_URL=http://flux:8004` 调用本地 `flux_service`；服务不可用时 `auto` 模式回退到确定性 fallback
- 当真实模型不可用、GPU 不可用或模型输出异常时，会回退到仓库内规则逻辑

## 快速部署

推荐服务器部署目录：

```text
/home/common/yzhu_2025/science-diagram-platform
```

当前模板默认按 2 张 H20-NVLink 96GB 分配：

- GPU 0：`qwen-image`
- GPU 1：`powerpaint_service`、`planner`、`segmenter`、`flux`

Qwen-Image 按独占 80GB GPU 设计。H20-NVLink 96GB 的 GPU 0 留给 Qwen-Image，GPU 1 承载 PowerPaint、planner、segmenter 和 FLUX；如果实际机器编号不同，只改 `.env` 里的 `*_CUDA_VISIBLE_DEVICES` 即可。

Docker 部署：

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.server.example .env
sudo docker compose --env-file .env build
sudo docker compose --env-file .env --profile qwen-image up -d
```

如果只想先启动 PowerPaint legacy 链路，不启动 Qwen-Image，可以去掉 profile：

```bash
sudo docker compose --env-file .env up -d
```

当前完整功能已经落在 `main`，服务器直接部署默认分支即可。

如果服务器不能使用 Docker、但可以使用 Conda，请看 [服务器部署说明](docs/deployment.md)，并使用 `scripts/setup_conda_envs.sh`、`scripts/start_all_tmux.sh`、`scripts/run_*.sh` 这组脚本。

Conda 部署启动后，如果需要演示前提前把 Qwen3.5、SAM2、PowerPaint、FLUX 和 Qwen-Image 加载进显存，可以顺序运行：

```bash
bash scripts/prewarm_models.sh
```

脚本会生成一张小尺寸烧杯测试图并逐个触发 `planner`、`segmenter`、`powerpaint`、`flux` 和 `qwen-image`。不要并发预热；如果出现 CUDA OOM，请先调整 `.env.nodocker` 里的各服务 GPU 编号，尤其确认 Qwen-Image 是否有独占 80GB GPU。

浏览器访问：

```text
http://211.87.232.112:19084
```

## 部署检查

服务器环境自检：

```bash
bash scripts/server-preflight.sh
```

网关基础健康检查：

```bash
curl http://127.0.0.1:19080/api/health
```

部署 readiness 检查：

```bash
curl http://127.0.0.1:19080/api/deployment/readiness
```

如果配置了 `GATEWAY_API_TOKEN`，除 `/api/health` 等豁免路由外，`/api/*` 请求需要带 token：

```bash
curl -H "Authorization: Bearer <token>" http://127.0.0.1:19080/api/deployment/readiness
```

前端如果需要访问受保护的网关，在构建时设置同一个 `VITE_API_TOKEN`。

## 主要 API

- `GET /api/health`：基础健康检查。
- `GET /api/deployment/readiness`：本地部署配置、目录、服务 URL、traceability 和 auth 状态检查。
- `GET /api/assets`：读取内置科学素材。
- `POST /api/plan`：基于底图和用户意图生成结构化编辑计划。
- `POST /api/init-plan`：文本初图规划。
- `POST /api/init-generate`：文本初图候选生成，默认使用服务器本地 FLUX-compatible provider，失败时可 fallback。
- `POST /api/segment`：mask/box/素材位置/正负点提示分割。
- `POST /api/generate`：同步局部生成。
- `POST /api/jobs`、`GET /api/jobs/{job_id}`、`POST /api/jobs/{job_id}/cancel`：异步生成任务。
- `GET/POST /api/projects`、`GET /api/projects/{project_id}`、`POST /api/projects/{project_id}/versions`：项目和版本持久化。
- `POST /api/canvas/validate-text`、`POST /api/canvas/export-svg`：文本校验和 SVG 导出。
- `GET/POST /api/benchmarks/runs`、`GET /api/benchmarks/summary`：实验台账和聚合指标。

## 文档

公开仓库只保留面向部署、架构和项目验收的正式说明：

- [架构说明](docs/architecture.md)：当前服务链路、数据目录、API 合同和对齐边界。
- [服务器部署说明](docs/deployment.md)：Docker Compose 与 Conda/tmux 两种部署路径。
- [技术报告对齐追踪表](docs/report-traceability.md)：Phase 1-13 对技术报告声明、代码路径、测试和限制的映射。
- [已知问题与后续缺口](docs/known-issues.md)：已完成能力之外的剩余缺口和生产化风险。

## PowerPaint 代码与权重

- 代码仓库：`https://github.com/zhuang2002/PowerPaint.git`
- `PowerPaint 2.1` 权重：`https://huggingface.co/JunhaoZhuang/PowerPaint-v2-1`

克隆 GitHub 仓库只会下载 PowerPaint 代码，不包含 `PowerPaint 2.1` checkpoint。权重仍需要通过 Hugging Face Git LFS 拉取，或从其他机器复制到服务器。默认服务器权重目录为 `models/powerpaint/ppt-v2-1`。
