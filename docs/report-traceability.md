# 技术报告对齐追踪表

这份表把技术报告中的阶段性能力声明映射到当前 `main` 分支的代码路径、测试覆盖和已知限制。它用于说明“已经落地到仓库的能力”，不把仍待生产化的内容包装成已完成。

| 阶段 | 已实现能力 | 主要代码路径 | 测试覆盖 | 已知限制 |
| --- | --- | --- | --- | --- |
| Phase 1 | 无底图文本初图入口，带确定性 fallback 候选。 | `backend/common/init_logic.py`、`backend/gateway/main.py`、`frontend/src/App.jsx`、`/api/init-plan`、`/api/init-generate` | `backend/tests/test_init_logic.py` | fallback 不是真实 FLUX 生成，会渲染位图预览文字。 |
| Phase 2 | 异步生成骨架，支持 job id 轮询，同时保留同步生成。 | `backend/gateway/jobs.py`、`backend/gateway/main.py`、`frontend/src/App.jsx`、`/api/jobs`、`/api/generate` | `backend/tests/test_jobs.py` | 仍是进程内协作式执行，不是 Redis/Celery。 |
| Phase 3 | 可序列化画布状态，包含 base、mask、素材和文字层元数据。 | `backend/common/canvas_state.py`、`backend/common/schemas.py`、`frontend/src/canvasState.js` | `backend/tests/test_canvas_state.py`、`frontend/tests/canvasState.test.mjs` | 完整 Fabric scene JSON 还不是后端唯一状态源。 |
| Phase 4 | 每次生成返回质量报告，包含 mask、局部化、保真和 prompt trace 指标。 | `backend/common/quality.py`、`backend/common/utils/masks.py`、`backend/gateway/main.py` | `backend/tests/test_quality.py` | 指标是轻量启发式评估，不是人工偏好评分。 |
| Phase 5 | 轻量 CI 基线，覆盖后端测试/导入、前端 helper/build 和 diff 空白检查。 | `.github/workflows/ci.yml`、`backend/tests/test_ci_workflow.py` | `backend/tests/test_ci_workflow.py` | CI 不跑 GPU 推理、Docker 构建、浏览器 E2E 或部署 smoke test。 |
| Phase 6 | 文件项目持久化和父版本链。 | `backend/gateway/projects.py`、`frontend/src/projectState.js`、`/api/projects` | `backend/tests/test_projects.py`、`frontend/tests/projectState.test.mjs` | 没有多用户数据库、鉴权和迁移层。 |
| Phase 7 | file-backed 异步 job 快照、取消和重启恢复标记。 | `backend/gateway/jobs.py`、`backend/gateway/main.py`、`frontend/src/App.jsx` | `backend/tests/test_jobs.py` | 没有独立 worker、分布式锁或模型调用内部硬取消。 |
| Phase 8 | 首个 Fabric.js 图层编辑切片，支持图层可见性、锁定、排序和 transform 回写。 | `frontend/src/components/EditorStage.jsx`、`frontend/src/layerState.js`、`frontend/src/App.jsx` | `frontend/tests/layerState.test.mjs`、`frontend/tests/canvasState.test.mjs` | 分组、吸附、完整 scene 持久化和 PPT 导出仍是后续工作。 |
| Phase 9 | SAM 正/负点提示，兼容原有 mask fallback 和 provenance。 | `backend/common/segment_logic.py`、`backend/segmenter/runtime.py`、`frontend/src/regionPrompts.js` | `backend/tests/test_segment_logic.py`、`frontend/tests/regionPrompts.test.mjs` | 没有自动文本 grounding、实例候选列表或多 mask 选择器。 |
| Phase 10 | OCR-ready 文本一致性校验和 vector text SVG 导出。 | `backend/common/export_logic.py`、`backend/gateway/main.py`、`frontend/src/exportState.js`、`/api/canvas/validate-text`、`/api/canvas/export-svg` | `backend/tests/test_export_logic.py`、`frontend/tests/exportState.test.mjs` | 没有内置 OCR 引擎和 PPTX 导出。 |
| Phase 11 | FLUX-compatible 初图 provider、本地 FLUX.2-klein-4B 服务部署和候选评分。 | `backend/flux_service/`、`backend/gateway/init_provider.py`、`backend/common/init_logic.py`、`frontend/src/initCandidates.js`、`docker-compose.yml`、`scripts/run_flux.sh` | `backend/tests/test_flux_service.py`、`backend/tests/test_local_flux_deployment.py`、`backend/tests/test_init_provider.py`、`backend/tests/test_init_logic.py`、`frontend/tests/initCandidates.test.mjs` | 不随仓库捆绑 FLUX 权重，也没有高清异步二阶段生成或持久化候选 artifact；默认 FLUX.2-klein-4B 权重部署时下载/缓存，通常需要约 13GB VRAM。 |
| Phase 12 | 文件化实验台账和实验看板。 | `backend/gateway/benchmarks.py`、`frontend/src/benchmarkState.js`、`frontend/src/components/ResultPanel.jsx`、`/api/benchmarks/summary` | `backend/tests/test_benchmarks.py`、`frontend/tests/benchmarkState.test.mjs` | benchmark 需要用户显式记录，不是自动数据集 runner 输出。 |
| Phase 13 | 可选网关 token、部署 readiness 检查和本追踪表。 | `backend/gateway/security.py`、`backend/gateway/deployment.py`、`frontend/src/apiClient.js`、`/api/deployment/readiness`、`GATEWAY_API_TOKEN` | `backend/tests/test_security.py`、`backend/tests/test_traceability.py`、`frontend/tests/apiClient.test.mjs` | 没有多用户登录、角色权限、token 轮换、外部 uptime 监控或完整 observability。 |

## 已知限制

- 安全方案是由 `GATEWAY_API_TOKEN` 控制的单共享 token，适合受控部署边界，不是多租户权限系统。
- readiness 检查只检查本地配置、文件系统和服务 URL，不会真实调用 planner、segmenter、PowerPaint、本地 FLUX、Qwen-Image、OCR 或浏览器 E2E。
- 报告对齐仍是工程化分阶段落地。若能力存在边界或生产化缺口，会在 [已知问题与后续缺口](known-issues.md) 中明确记录，而不是把报告级愿景写成已完成能力。
