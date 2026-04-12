# 架构说明

## 服务链路

1. 前端上传图片、绘制 mask 或放置素材。
2. 前端调用 `gateway /api/plan` 获取结构化任务建议。
3. 前端调用 `gateway /api/generate`。
4. 网关内部继续调用：
   - `planner /plan`
   - `segmenter /segment`
   - `powerpaint /generate`
5. 网关输出结果图，并将中间件产物写入 `data/runs/<run_id>/`。

## 为什么这样拆

- 方便后续把规则规划器替换成 Qwen3.5。
- 方便把轻量 mask 归一化替换成 SAM-2。
- 方便单独测 PowerPaint 推理开销与显存占用。
- 更贴合技术报告中的“输入层—规划层—分割层—执行层—反馈层”描述。
