# 4 卡部署说明

当前服务器共有 8 张 RTX 3090 24GB，但本项目按 4 张卡部署更稳妥，也更适合毕业设计阶段的答辩演示。

## 推荐 GPU 集合

```text
4,5,6,7
```

## 推荐分配

- GPU 4：`powerpaint_service`
- GPU 5：`planner`
- GPU 6：`segmenter`
- GPU 7：备用卡

## 这样分配的原因

- `powerpaint_service` 推理负载最大，单独占卡最稳
- `planner` 和 `segmenter` 都支持惰性加载，单独分卡后问题定位更容易
- 保留 1 张备用卡，便于后续临时调试、导出模型或替换更大的规划模型

## 当前模板对应关系

- Docker 模式：看 `.env.server.example`
- 无 Docker 模式：看 `.env.nodocker.example`

这两个模板现在都按 `4,5,6,7` 这组卡来示例。

## 当前仍未做的事

当前项目还没有实现“多任务异步队列”或“自动调度到备用卡”的能力，所以 GPU 7 目前是手工预留，不会自动接管任务。
