# 已完成能力与后续缺口

这份文档记录当前项目在完成技术报告 Phase 1-13 对齐之后，哪些能力已经可以演示，哪些仍然只是轻量实现或后续生产化缺口。更细的阶段映射见 `docs/report-traceability.md`。

## 已经修复或补齐的问题

- 增加了 `.gitattributes`，避免本地与 GitHub 因 `CRLF/LF` 导致重复分叉
- `POWERPAINT_LOCAL_FILES_ONLY=true` 时，如果本地权重不存在，会明确报错而不是静默尝试联网下载
- 移除了 `docker-compose.yml` 中未接入业务链路的 `redis` 服务，减少无效依赖
- 前端 Nginx 对 `/api` 的代理超时已经调大，降低冷启动时被反向代理提前断开的概率
- Phase 1-13 已补齐报告对齐基础能力：文本初图、异步任务、画布状态、质量报告、CI、项目版本、持久化 job、Fabric 图层、SAM 点提示、OCR-ready SVG、FLUX-compatible provider、实验台账、readiness 和单 token 网关保护

## 已实现模块的剩余缺口

### 0. FLUX 初图服务与候选重排

当前已经补入无图文本入口的 API 合同和确定性 fallback 初图候选，便于前端先进入“文本初图 -> 后续局部编辑”的闭环。Phase 11 新增了 `FLUX_INIT_URL` 可配置 FLUX-compatible provider、`auto`/`flux-local`/`flux-remote`/`deterministic-fallback` provider 选择、候选评分重排和前端 provider/score 展示。当前分支又补入了仓库内 `backend/flux_service`、Docker Compose `flux` 服务和 Conda/tmux 启动脚本，使默认部署路径改为本地 FLUX.2-klein-4B 服务。仍未完成的是在本仓库内捆绑 FLUX.2-klein-4B 权重、低清预览/高清异步二阶段生成和长期候选 artifact 存储；默认权重为 Apache 2.0 开源模型，通常需要约 13GB VRAM，首次运行或更新时仍可能需要从 Hugging Face 下载。fallback 画面中的文字仍是位图提示，第三阶段新增的文本层只覆盖前端轻量标签元数据。

### 0.1 Qwen-Image 本地编辑服务

当前已经接入本地 Qwen-Image masked edit provider：Docker 内部服务名为 `qwen-image`、端口 `8005`，服务在 `qwen-image` profile 下启动；Conda/tmux 默认 `QWEN_IMAGE_PORT=19086`，Gateway 通过 `QWEN_IMAGE_URL` 访问。模型第一版默认是 `Qwen/Qwen-Image-Edit`，默认 `bfloat16`、50 steps、`true_cfg_scale=4.0`、`strength=1.0`，第一版不默认使用 Qwen-Image-Edit-2511。剩余风险是真实 80GB GPU 烟测和效果评估仍需在服务器完成；默认部署目标为 2 张 H20-NVLink 96GB，GPU 0 给 Qwen-Image，GPU 1 给 PowerPaint、planner、segmenter 和 FLUX。

### 1. 认证与权限控制

当前平台默认面向内网或受控环境。Phase 13 新增了可选的 `GATEWAY_API_TOKEN` 单 token 网关保护；配置后，非豁免 `/api/*` 路由需要 `Authorization: Bearer <token>` 或 `X-API-Token`，前端也可以通过 `VITE_API_TOKEN` 透传同一 token。它仍不是完整账号系统：没有多用户登录、角色权限、token 轮换、审计日志或生产级 secret 管理。`VITE_API_TOKEN` 会进入静态前端 bundle，只适合受控演示或内网边界，不应当视为公网多租户安全方案。

### 2. 异步任务队列与进度跟踪

当前已经补入异步任务骨架并升级为 file-backed 状态持久化：前端可以通过 `POST /api/jobs` 创建生成任务，通过 `GET /api/jobs/{job_id}` 轮询状态、进度和结果，并通过 `POST /api/jobs/{job_id}/cancel` 发起取消；原有 `/api/generate` 同步接口仍然保留。Gateway 会把 job snapshot 写入 `JOBS_DIR`，重启后可继续读取已完成、失败或取消的任务状态；重启时仍处于执行中的任务会被标记为 `FAILED` 并记录 `failure_stage`。但这还不是 Redis/Celery 级别的外部队列：没有独立 worker、多 worker 调度、跨实例锁、真正的后台恢复执行，也不能硬中断已经进入模型调用内部的请求。

### 3. 画布状态、图层系统与项目级持久化

当前生成请求已经可以携带可序列化 `canvas_state`，并在生成后返回更新后的 base image、mask、asset 和 text layer 元数据；前端已经接入首个 Fabric.js 图层编辑器，支持图层模式下选择素材/文字对象、拖动或缩放回写状态，并提供 base、mask、asset、text layer 的可见性、锁定和非 base 图层重排 UI。当前还新增了基于 vector text layer 的文本一致性校验合同和 SVG 导出路径，SVG 中可见文本层会保留为 `<text>`。仍未完成的是完整 Fabric scene JSON 持久化、复杂组合/对齐、PPT 导出、真实 OCR 引擎校验或多用户长期会话能力。

### 4. 更细粒度的 SAM-2 交互

当前 `segmenter` 已支持用户 mask/box/asset placement 以及正负点 SAM prompt。前端也新增了正点/负点模式，用户可以在画布上多次点击添加 point prompts，并把这些点作为 `point_prompts` 传入生成链路。仍未完成的是多 mask 候选选择、实例级分割列表、自动文本 grounding、点击历史分支和高级 refinement scoring UI。

### 5. 自动化测试与 CI

仓库当前已经补入面向初图、异步任务、画布状态和质量报告的后端单元测试，并增加了 GitHub Actions 轻量 CI 来运行后端单测、Python 编译检查、前端 helper 测试、前端构建和 diff 空白检查。但 CI 还没有覆盖 Docker 镜像构建、真实模型推理、GPU 环境、接口集成测试、前端端到端测试或部署 smoke test。

### 6. 评估与实验管理

当前生成结果会返回并落盘每轮 `quality_report`，包含 mask 覆盖、mask 内变化、局部化得分、保真得分和 prompt/provenance 元数据。Phase 10 已提供 OCR-ready 文本校验接口：如果调用方提供 OCR observations，后端可以和预期标签/vector text layer 做一致性比较；未提供 OCR 时会明确标记为 vector-text fallback。Phase 12 又新增了文件化实验台账、`/api/benchmarks/runs`、`/api/benchmarks/summary` 和前端实验看板，可以显式记录当前 run 并查看总体均值、provider 对比、文本通过率和最近记录。剩余缺口是内置真实 OCR 模型、人工偏好评分、自动数据集 runner、模型版本调度、CSV/PDF 报告导出和多用户实验管理。

## 当前主要风险

### 1. 首次请求延迟较高

`planner` 和 `segmenter` 都是惰性加载，第一次真实请求会加载模型，耗时明显高于热启动后的请求。

### 2. 规划模型仍可能回退到规则逻辑

Qwen3.5 输出结构化 JSON 时如果结果不合法，服务会自动回退到仓库内的 `build_plan` 规则逻辑。这保证了可用性，但也意味着模型规划结果不是每次都能稳定命中。

### 3. 部署对磁盘空间比较敏感

如果 Docker 数据目录仍在系统盘，而系统盘空间不足，首次构建和首次下载模型时仍然可能失败。

## 当前结论

目前代码已经具备：

- 服务器部署能力
- 真实 Qwen3.5 / SAM-2 / PowerPaint 接入能力
- 前后端基本联通能力
- 规则回退兜底能力
- 可选单 token 网关保护、readiness 配置检查和报告对齐追踪表

但这些能力仍然以单节点、单用户、文件持久化和受控部署边界为前提。如果要进一步做成“更稳定的长期服务”，下一阶段最值得补的是：

1. 接口集成测试与端到端测试
2. 多用户鉴权、角色权限、secret 管理和审计日志
3. Redis/Celery 或独立 worker 级持久化异步任务队列
4. 完整 Fabric scene 持久化、PPT 导出和高级编辑工具
5. 扩展 CI、端到端测试、OCR 校验和自动数据集评估报表
## Phase 6 项目持久化说明

当前分支已经包含轻量的单用户项目持久化层，可以保存 JSON 项目快照、父版本关系、初图候选元数据、run id、画布状态、artifact URL 和可选质量报告。它补齐了早期“画布状态无法长期追踪”的主要缺口。

剩余限制：这不是多用户数据库，没有鉴权、迁移系统或编辑器级完整持久化；初图候选中的 data URL 图片在没有后续 artifact URL 前仍更接近会话数据。

## Phase 7 持久化异步任务说明

当前分支已经在 `JOBS_DIR` 下保存 file-backed 异步 job 快照。已完成、失败、取消和重启中断的任务都可以在 Gateway 重启后读取，前端也暴露了对当前异步任务的取消操作。

剩余限制：这仍不是 Redis/Celery，没有独立 worker、多 worker 调度或跨实例协调；取消是 Gateway 进度检查点上的协作式取消，不能硬中断已经进入模型内部的调用。

## Phase 8 Fabric 图层说明

当前分支已经包含第一个 Fabric.js 图层编辑切片。它保留既有 `canvas_state` 合同，增加图层顺序、可见性、锁定和透明度元数据，并允许用户在图层模式下选择、移动和缩放素材/文字对象。

剩余限制：Fabric scene JSON 还不是后端唯一状态源；mask 绘制仍使用原生 mask canvas；SVG 导出主要覆盖可见图片层和 vector text layer；PPT 导出、OCR 内置校验、组合、吸附、对齐辅助线和完整矢量导出验证仍是后续工作。

## Phase 9 SAM 点提示说明

当前分支已经在 Gateway、segmenter、前端和 `canvas_state` provenance 中统一了正/负点提示。SAM2.1 可在存在点提示时接收 `input_points` 和 `input_labels`，原有 mask、box 和素材 placement fallback 路径仍保留。

剩余限制：没有多 mask 候选选择器、自动文本到区域 grounding、实例分割列表或高级点击 refinement scoring UI。

## Phase 10 OCR-ready SVG 导出说明

当前分支已经包含 `/api/canvas/validate-text` 和 `/api/canvas/export-svg`。这些接口读取既有 `canvas_state`，将可见 vector text layer 与预期标签和可选 OCR observations 对齐，并返回保留可编辑 `<text>` 节点的 SVG。

剩余限制：没有内置 OCR 模型；fallback 图像或 PowerPaint 输出里的位图文字必须依赖调用方提供 OCR observations；SVG 导出不会嵌入不可用的 data-url 源图；PPTX 导出仍未实现。

## Phase 11 FLUX-compatible 初图 provider 说明

当前分支已经包含可配置的 FLUX-compatible 初图 provider。`/api/init-generate` 保持原有接口形状，但 `InitGenerateRequest.provider` 可以选择 `auto`、`deterministic-fallback`、`flux-local` 或 `flux-remote`；默认 Docker/Conda 部署会把 `FLUX_INIT_URL` 指向本地 `flux` 服务，并对候选结果重排。

剩余限制：仓库不捆绑 FLUX 权重；模型质量依赖实际配置的本地模型或缓存；高清异步再生成还未实现；初图候选仍是会话 data URL，而不是长期 artifact 文件。

## Phase 12 实验台账说明

当前分支已经在 `BENCHMARKS_DIR` 下包含轻量文件化实验台账。Gateway 可以记录带 `quality_report`、可选文本校验报告、provider/model 元数据、项目/版本 id、标签和紧凑 metadata 的实验记录，也能返回聚合指标和 provider 对比。

剩余限制：benchmark 记录需要用户显式触发，不是自动数据集 runner；没有内置 OCR、人类偏好标注、模型版本调度，也没有 CSV/PDF 报告导出。

## Phase 13 部署加固说明

当前分支已经包含可选单 token 网关保护、只读 `/api/deployment/readiness`、前端 `VITE_API_TOKEN` 透传，以及把报告声明映射到代码路径、测试和限制的 `docs/report-traceability.md`。

剩余限制：这不是多用户鉴权、RBAC、token 轮换、生产级 secret 管理、外部 uptime 监控、Docker/GPU smoke test 或完整 observability。静态 `/assets` 和 `/artifacts` 路由仍有意豁免，因此生成 artifact URL 仍应视为部署边界内可访问资源。
