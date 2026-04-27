# 架构说明

本文档描述当前分支的实际架构，而不是技术报告中的理想终态。项目已经完成 Phase 1-13 的报告对齐基础能力，但仍然采用单节点、文件持久化、受控部署边界的工程实现。

## 服务链路

1. 前端上传底图、绘制 mask、放置素材、添加文字层，或从文本初图入口创建初始画布。
2. 前端通过 Gateway 调用规划、分割、生成、项目、实验台账和导出 API。
3. Gateway 负责统一合同校验、文件落盘、任务状态、项目版本、质量报告和可选 token 鉴权。
4. Gateway 按请求继续调用：
   - `planner /plan`：Qwen3.5 优先，规则规划 fallback。
   - `segmenter /segment`：SAM2.1 优先，几何 mask fallback。
   - `powerpaint /generate`：PowerPaint 局部生成服务。
   - `FLUX_INIT_URL`：可选远程初图 provider；未配置时使用确定性 fallback。
5. Gateway 将生成产物写入 `RUNS_DIR`，并把项目、异步任务和 benchmark 记录分别写入对应目录。
6. 前端把结果图、mask、质量报告、项目版本、图层状态和实验指标回流到工作区，支持下一轮编辑。

## 服务职责

### Frontend

- React + Vite 前端。
- Fabric.js 图层编辑切片负责素材/文字层选择、移动、缩放、显示、锁定和排序。
- 原有 mask canvas 仍负责 brush/erase 的局部编辑遮罩。
- `apiFetch` 统一 API 请求，可在构建时通过 `VITE_API_TOKEN` 附带 `Authorization: Bearer <token>`。
- 非 API 的 `/artifacts` 图像读取保持普通 fetch，不附带 token。

### Gateway

- FastAPI 网关，是浏览器唯一需要直接访问的后端 API。
- 核心模块：
  - `main.py`：API 路由与服务编排。
  - `jobs.py`：异步生成 job snapshot、取消和重启恢复标记。
  - `projects.py`：文件项目和版本快照。
  - `benchmarks.py`：实验 run ledger 和聚合指标。
  - `init_provider.py`：FLUX-compatible 远程 provider 和 fallback 选择。
  - `security.py`：可选单 token `/api/*` 保护。
  - `deployment.py`：readiness 配置检查。
- `/api/health`、`/assets`、`/artifacts`、OpenAPI docs 和 CORS preflight 保持豁免；其他 `/api/*` 在 `GATEWAY_API_TOKEN` 非空时需要 token。

### Planner

- 优先使用 `Qwen/Qwen3.5-4B` 生成结构化编辑计划。
- 输出不合法、模型不可用或依赖缺失时，回退到 `backend/common` 中的规则规划逻辑。
- 规划层负责结构化意图，不负责直接生成最终图像。

### Segmenter

- 优先使用 `facebook/sam2.1-hiera-base-plus`。
- 支持用户 mask、box、素材 placement 以及正/负点 prompt。
- 如果没有可用模型或模型调用失败，回退到几何 mask。
- 当前没有自动文本 grounding、实例列表或多 mask 候选 UI。

### PowerPaint Service

- 调用官方 PowerPaint 代码和 `PowerPaint 2.1` 权重。
- 接收原图、mask 和 prompt，返回局部生成结果。
- 权重不随 GitHub 仓库一起下载，需要通过 Hugging Face Git LFS 拉取或提前复制到服务器。

## 数据目录

Docker Compose 默认把这些目录挂到项目 `data/` 下：

```text
data/runs/         生成图、mask、质量报告和中间产物
data/projects/     项目 JSON 快照与版本链
data/jobs/         异步任务 JSON 快照
data/benchmarks/   benchmark run ledger
models/            Hugging Face 与 PowerPaint 权重缓存
```

无 Docker 部署通过 `.env.nodocker` 设置 `RUNS_DIR`、`BENCHMARKS_DIR`、`MODELS_DIR` 和 `HF_HOME`。`PROJECTS_DIR` 与 `JOBS_DIR` 如果不显式设置，会默认落在 `RUNS_DIR` 的同级目录。

## 主要 API 合同

- 初图：`POST /api/init-plan`、`POST /api/init-generate`
- 编辑规划：`POST /api/plan`
- 分割：`POST /api/segment`
- 同步生成：`POST /api/generate`
- 异步任务：`POST /api/jobs`、`GET /api/jobs/{job_id}`、`POST /api/jobs/{job_id}/cancel`
- 项目版本：`GET/POST /api/projects`、`GET /api/projects/{project_id}`、`POST /api/projects/{project_id}/versions`
- 文本与导出：`POST /api/canvas/validate-text`、`POST /api/canvas/export-svg`
- 实验台账：`GET/POST /api/benchmarks/runs`、`GET /api/benchmarks/summary`
- 部署检查：`GET /api/deployment/readiness`

## 为什么这样拆

- 让前端只依赖 Gateway，降低浏览器跨服务访问复杂度。
- 让 Qwen3.5、SAM2.1 和 PowerPaint 可以分开部署、分配 GPU 和独立回退。
- 让同步生成、异步任务、项目版本和 benchmark 共享同一套 schema 与 artifact 路径。
- 贴合技术报告中的“输入层 -> 规划层 -> 分割层 -> 执行层 -> 反馈层”，但用可测试、可部署的轻量实现逐步落地。

## 当前边界

- 认证是单共享 token，不是多用户登录、RBAC、token 轮换或审计系统。
- 异步任务是 Gateway 进程内执行加文件 snapshot，不是 Redis/Celery 或独立 worker 集群。
- 项目、job 和 benchmark 都是 JSON 文件持久化，不是数据库。
- Readiness 只检查本地目录、配置、服务 URL 格式和 traceability 文件，不调用真实模型或浏览器 E2E。
- 技术报告中的生产级能力和未完成项统一记录在 `docs/known-issues.md` 与 `docs/report-traceability.md`。
