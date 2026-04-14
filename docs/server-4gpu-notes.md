# 4 卡部署说明

当前服务器共有 8 张 RTX 3090 24GB，但这个项目按 4 张卡规划会更稳妥，也更适合毕业设计阶段的部署和答辩演示。

## 推荐 GPU 集合

```text
2,3,6,7
```

推荐分配：

- GPU 2：`powerpaint_service`
- GPU 3：`planner`
- GPU 6：`segmenter`
- GPU 7：备用

## 当前版本如何使用这 4 张卡

- `powerpaint_service` 使用真实 PowerPaint 推理。
- `planner` 使用真实 Qwen3.5 多模态模型做编辑规划。
- `segmenter` 使用真实 SAM-2 做 mask 细化。
- 所有服务仍保留规则回退逻辑，避免模型异常时整个平台不可用。

## `.env.server.example` 建议值

```bash
PROJECT_GPU_POOL=2,3,6,7
POWERPAINT_CUDA_VISIBLE_DEVICES=2
PLANNER_CUDA_VISIBLE_DEVICES=3
SEGMENTER_CUDA_VISIBLE_DEVICES=6
AUX_CUDA_VISIBLE_DEVICES=7
```

## Compose 的实际行为

- `planner`、`segmenter`、`powerpaint` 三个容器都启用了 GPU 能力。
- 容器内部通过 `CUDA_VISIBLE_DEVICES` 和 `NVIDIA_VISIBLE_DEVICES` 约束可见 GPU。
- 模型缓存共享到 `./models`，避免每个容器重复下载 Hugging Face 权重。
- `planner` 和 `segmenter` 默认采用惰性加载，容器先启动，首次请求时再拉起真实模型。

## 使用建议

如果后面想切更大的模型，优先保持单服务单卡，不要和 PowerPaint 混卡。这样答辩前排查问题会简单很多。
