# 已知问题与后续缺口

这份文档记录当前项目在“可部署、可演示”之外，仍然存在的缺口和风险，方便后续继续完善毕业设计。

## 本轮已经修复的问题

- 增加了 `.gitattributes`，避免本地与 GitHub 因 `CRLF/LF` 导致重复分叉
- `POWERPAINT_LOCAL_FILES_ONLY=true` 时，如果本地权重不存在，会明确报错而不是静默尝试联网下载
- 移除了 `docker-compose.yml` 中未接入业务链路的 `redis` 服务，减少无效依赖
- 前端 Nginx 对 `/api` 的代理超时已经调大，降低冷启动时被反向代理提前断开的概率

## 当前仍未实现的功能

### 0. FLUX 初图服务与候选重排

当前已经补入无图文本入口的 API 合同和确定性 fallback 初图候选，便于前端先进入“文本初图 -> 后续局部编辑”的闭环。Phase 11 又新增了 `FLUX_INIT_URL` 可配置远程初图服务适配器、`auto`/`flux-remote`/`deterministic-fallback` provider 选择、候选评分重排和前端 provider/score 展示。仍未完成的是在本仓库内捆绑 FLUX.2 [klein] 4B 权重、本地 GPU 初图模型服务、低清预览/高清异步二阶段生成和长期候选 artifact 存储；fallback 画面中的文字仍是位图提示，第三阶段新增的文本层只覆盖前端轻量标签元数据。

### 1. 认证与权限控制

当前平台默认面向内网或受控环境，没有登录、权限隔离或访问令牌机制。如果直接暴露到公网，需要再加网关鉴权。

### 2. 异步任务队列与进度跟踪

当前已经补入异步任务骨架并升级为 file-backed 状态持久化：前端可以通过 `POST /api/jobs` 创建生成任务，通过 `GET /api/jobs/{job_id}` 轮询状态、进度和结果，并通过 `POST /api/jobs/{job_id}/cancel` 发起取消；原有 `/api/generate` 同步接口仍然保留。Gateway 会把 job snapshot 写入 `JOBS_DIR`，重启后可继续读取已完成、失败或取消的任务状态；重启时仍处于执行中的任务会被标记为 `FAILED` 并记录 `failure_stage`。但这还不是 Redis/Celery 级别的外部队列：没有独立 worker、多 worker 调度、跨实例锁、真正的后台恢复执行，也不能硬中断已经进入模型调用内部的请求。

### 3. 画布状态、图层系统与项目级持久化

当前生成请求已经可以携带可序列化 `canvas_state`，并在生成后返回更新后的 base image、mask、asset 和 text layer 元数据；前端已经接入首个 Fabric.js 图层编辑器，支持图层模式下选择素材/文字对象、拖动或缩放回写状态，并提供 base、mask、asset、text layer 的可见性、锁定和非 base 图层重排 UI。当前还新增了基于 vector text layer 的文本一致性校验合同和 SVG 导出路径，SVG 中可见文本层会保留为 `<text>`。仍未完成的是完整 Fabric scene JSON 持久化、复杂组合/对齐、PPT 导出、真实 OCR 引擎校验或多用户长期会话能力。

### 4. 更细粒度的 SAM-2 交互

当前 `segmenter` 已支持用户 mask/box/asset placement 以及正负点 SAM prompt。前端也新增了正点/负点模式，用户可以在画布上多次点击添加 point prompts，并把这些点作为 `point_prompts` 传入生成链路。仍未完成的是多 mask 候选选择、实例级分割列表、自动文本 grounding、点击历史分支和高级 refinement scoring UI。

### 5. 自动化测试与 CI

仓库当前已经补入面向初图、异步任务、画布状态和质量报告的后端单元测试，并增加了 GitHub Actions 轻量 CI 来运行后端单测、Python 编译检查、前端 helper 测试、前端构建和 diff 空白检查。但 CI 还没有覆盖 Docker 镜像构建、真实模型推理、GPU 环境、接口集成测试、前端端到端测试或部署 smoke test。

### 6. 评估与实验管理

当前生成结果会返回并落盘每轮 `quality_report`，包含 mask 覆盖、mask 内变化、局部化得分、保真得分和 prompt/provenance 元数据。Phase 10 已提供 OCR-ready 文本校验接口：如果调用方提供 OCR observations，后端可以和预期标签/vector text layer 做一致性比较；未提供 OCR 时会明确标记为 vector-text fallback。这仍然不是完整评估平台：还没有内置真实 OCR 模型、人工偏好评分、数据集级 benchmark 聚合、长期实验看板或模型版本对比报表。

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

但如果要进一步做成“更稳定的长期服务”，下一阶段最值得补的是：

1. 接口集成测试与端到端测试
2. 鉴权与访问控制
3. 持久化异步任务队列
4. Fabric.js 图层编辑与会话级项目持久化
5. 扩展 CI、端到端测试、OCR 校验和数据集级评估报表
## Phase 6 Persistence Note

The current branch now includes a lightweight single-user project persistence layer. It stores JSON project snapshots, parent-linked versions, selected initial-candidate metadata, run ids, canvas states, artifact URLs, and optional quality reports. This supersedes the earlier project-persistence part of the canvas-state gap; the remaining gap is full database-backed, multi-user, editor-level persistence.

Remaining persistence limitations: this is not a multi-user database, it has no auth or migration system, it does not replace the future Fabric.js editor, and initial-candidate data URL images are still treated as session data unless a later generated artifact URL exists.

## Phase 7 Durable Job Note

The current branch now includes durable file-backed async job snapshots under `JOBS_DIR`. Completed, failed, cancelled, and restart-interrupted jobs are readable after gateway restart, and the front end exposes a cancel action for the active async job.

Remaining async limitations: this is still not Redis/Celery, there is no separate worker service, no multi-worker scheduling or cross-instance coordination, and cancellation remains cooperative at gateway progress checkpoints rather than a hard interruption of an in-flight model call.

## Phase 8 Fabric Layer Note

The current branch now includes a first Fabric.js-backed editor slice. It keeps the existing `canvas_state` contract, adds layer order and per-layer visibility/lock/opacity metadata, and lets users switch into layer mode to select and transform asset/text objects without losing the brush/erase mask workflow.

Remaining layer-editor limitations: Fabric scene JSON is not persisted as the source of truth yet, mask drawing still uses the native mask canvas, SVG export is limited to visible referenced image layers plus vector text layers, PPT export is not implemented, OCR reconciliation requires caller-supplied OCR observations for bitmap text, and advanced editor features such as grouping, snapping, alignment guides, and full vector export validation remain future phases.

## Phase 9 SAM Point Prompt Note

The current branch now includes normalized positive/negative point prompts across the gateway, segmenter, front end, and `canvas_state` provenance. SAM2.1 receives `input_points` and `input_labels` when available, while the existing mask, box, and asset-placement fallback path remains intact.

Remaining SAM interaction limitations: there is no multi-mask candidate picker, no automatic text-to-region grounding, no instance segmentation list, and no advanced click refinement scoring UI yet.

## Phase 10 OCR-Ready SVG Export Note

The current branch now includes `/api/canvas/validate-text` and `/api/canvas/export-svg`. These endpoints consume the existing `canvas_state`, reconcile visible vector text layers against expected labels and optional OCR observations, and return an SVG document where visible text layers remain editable SVG `<text>` nodes. The front end exposes text validation and SVG export actions from the current workspace state.

Remaining export limitations: there is no built-in OCR model yet, bitmap-only labels from fallback images or PowerPaint output cannot be verified without supplied OCR observations, SVG export warns instead of embedding unavailable data-url source images, and PPTX export remains future work.

## Phase 11 FLUX-Compatible Init Provider Note

The current branch now includes a configurable FLUX-compatible initial-canvas provider path. `/api/init-generate` keeps the same endpoint shape, but `InitGenerateRequest.provider` can request `auto`, `deterministic-fallback`, or `flux-remote`; when `FLUX_INIT_URL` is configured, `auto` calls the remote provider and reranks returned candidates, otherwise it falls back with explicit warnings. The front end shows provider, fallback, rank, score, label coverage, and source metadata for each initial candidate.

Remaining initial-canvas limitations: this repository still does not bundle FLUX weights or a GPU model server, remote provider response quality depends on the separately deployed service, high-resolution async regeneration is not implemented yet, and init candidates are still session data URLs rather than durable artifact files.
