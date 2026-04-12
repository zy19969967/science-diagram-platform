# 4 卡部署说明

当前服务器共有 8 张 RTX 3090 24GB，但这个项目先按 4 张卡规划更稳妥，也更符合你当前的使用习惯。

## 推荐 GPU 集合

建议预留：

```text
2,3,6,7
```

推荐原因：

- GPU 2 和 GPU 7 相对更空闲。
- GPU 3 当前占用较轻，适合后续接入额外推理服务。
- GPU 6 有少量占用，但通常仍可作为第二阶段服务使用。
- GPU 1 当前显存占用较高，不建议优先使用。

## 当前版本怎么用这 4 张卡

当前仓库中：

- `powerpaint_service` 是唯一真正使用 GPU 的服务。
- `planner` 和 `segmenter` 还是轻量占位实现，默认不吃 GPU。

因此现阶段推荐：

- GPU 2：给 `powerpaint_service`
- GPU 3：给未来真实 `planner`
- GPU 6：给未来真实 `segmenter`
- GPU 7：保留给调试、实验或备用推理服务

## `.env.server.example` 建议值

```bash
PROJECT_GPU_POOL=2,3,6,7
POWERPAINT_CUDA_VISIBLE_DEVICES=2
PLANNER_CUDA_VISIBLE_DEVICES=3
SEGMENTER_CUDA_VISIBLE_DEVICES=6
AUX_CUDA_VISIBLE_DEVICES=7
```

## 当前 Compose 的实际行为

当前 `docker-compose.yml` 中：

- `powerpaint` 容器开启 GPU 能力
- 容器内通过 `CUDA_VISIBLE_DEVICES` 和 `NVIDIA_VISIBLE_DEVICES` 约束可见 GPU
- 其他服务先跑在 CPU 上

这意味着：

- 现在可以先稳定部署当前版本
- 后面再把 `planner` 和 `segmenter` 分别替换成真实 GPU 模型服务
- 不需要重做整套部署结构

## 后续升级建议

### 升级 `planner`

如果你后面接入真实 Qwen3.5 模型服务，建议单独绑定：

```bash
PLANNER_CUDA_VISIBLE_DEVICES=3
```

### 升级 `segmenter`

如果你后面接入真实 SAM-2 服务，建议单独绑定：

```bash
SEGMENTER_CUDA_VISIBLE_DEVICES=6
```

### 保留备用卡

保留 GPU 7 的好处：

- 可以在不影响主流程的情况下单独调试新模型
- 可以临时拿来跑批处理或导出任务
- 可以作为答辩前的应急切换卡
