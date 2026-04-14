# 4 卡部署说明

当前服务器共有 8 张 RTX 3090 24GB，但本项目按 4 张卡部署更稳妥，也更适合毕业设计阶段的答辩演示。

## 推荐 GPU 集合

```text
2,3,6,7
```

## 推荐分配

- GPU 2：`powerpaint_service`
- GPU 3：`planner`
- GPU 6：`segmenter`
- GPU 7：备用卡

## 这样分配的原因

- `powerpaint_service` 推理负载最大，单独占卡最稳
- `planner` 和 `segmenter` 都支持惰性加载，单独分卡后问题定位更容易
- 保留 1 张备用卡，便于后续临时调试、导出模型或替换更大的规划模型

## 当前 Compose 的实际行为

- `planner`、`segmenter`、`powerpaint` 都启用了 GPU 能力
- 容器内通过 `CUDA_VISIBLE_DEVICES` 与 `NVIDIA_VISIBLE_DEVICES` 限制可见 GPU
- 模型缓存统一挂载到 `./models`
- `AUX_CUDA_VISIBLE_DEVICES` 只是预留变量，当前没有容器自动消费它

## 对应的 `.env.server.example`

```bash
PROJECT_GPU_POOL=2,3,6,7
POWERPAINT_CUDA_VISIBLE_DEVICES=2
PLANNER_CUDA_VISIBLE_DEVICES=3
SEGMENTER_CUDA_VISIBLE_DEVICES=6
AUX_CUDA_VISIBLE_DEVICES=7
```

## 什么时候需要调整

如果 `nvidia-smi` 显示 GPU 2、3、6 已经被别的任务大量占用，可以把 `.env` 改成别的空闲卡组合。改完后重新执行：

```bash
sudo docker compose --env-file .env up -d --build
```

## 当前仍未做的事

当前项目还没有实现“多任务异步队列”或“自动调度到备用卡”的能力，所以 GPU 7 目前是手工预留，不会自动接管任务。
