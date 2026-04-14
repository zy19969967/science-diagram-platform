# 服务器执行清单

这份清单按你当前服务器环境整理：不使用 Docker，使用多 `venv` + 多端口 + 多 GPU 运行项目。

## 0. 推荐目录

```bash
/home/common/yzhu_2025/science-diagram-platform
```

## 1. 克隆项目

```bash
mkdir -p /home/common/yzhu_2025
cd /home/common/yzhu_2025
git clone https://github.com/zy19969967/science-diagram-platform.git
cd science-diagram-platform
cp .env.nodocker.example .env.nodocker
```

## 2. 修改 `.env.nodocker`

把下面几项确认好：

```bash
PROJECT_ROOT=/home/common/yzhu_2025/science-diagram-platform
POWERPAINT_REPO_PATH=/home/common/yzhu_2025/PowerPaint

POWERPAINT_CUDA_VISIBLE_DEVICES=4
PLANNER_CUDA_VISIBLE_DEVICES=5
SEGMENTER_CUDA_VISIBLE_DEVICES=6
AUX_CUDA_VISIBLE_DEVICES=7

PUBLIC_GATEWAY_BASE_URL=http://211.87.232.112:8000
FRONTEND_STATIC_PORT=8080
```

如果你不想公网直接访问网关，可以保留：

```bash
GATEWAY_HOST=127.0.0.1
```

这时前端需要由反向代理转发到 `8000`。如果你先追求最简单可用，也可以暂时改成：

```bash
GATEWAY_HOST=0.0.0.0
```

## 3. 安装环境

```bash
bash scripts/setup_venvs.sh
```

## 4. 构建前端

```bash
bash scripts/build_frontend.sh
```

## 5. 后台启动后端服务

如果服务器装了 `tmux`，推荐这样启动：

```bash
bash scripts/start_all_tmux.sh
```

如果你还想顺手把静态前端也一起挂起来：

```bash
bash scripts/start_all_tmux.sh --with-frontend
```

## 6. 查看运行状态

```bash
bash scripts/status_tmux.sh
bash scripts/check_services.sh
```

查看日志：

```bash
tail -f logs/planner.log
tail -f logs/segmenter.log
tail -f logs/powerpaint.log
tail -f logs/gateway.log
```

如果启用了前端静态服务：

```bash
tail -f logs/frontend.log
```

## 7. 停止服务

```bash
bash scripts/stop_all_tmux.sh
```

## 8. 前端访问地址

如果你用了：

```bash
bash scripts/start_all_tmux.sh --with-frontend
```

默认前端地址：

```text
http://211.87.232.112:8080
```

## 9. 最小手动启动顺序

如果你不想用 `tmux` 脚本，也可以手动分开启动：

```bash
bash scripts/run_planner.sh
bash scripts/run_segmenter.sh
bash scripts/run_powerpaint.sh
bash scripts/run_gateway.sh
bash scripts/serve_frontend.sh
```

## 10. 建议的首次检查

先看 GPU：

```bash
nvidia-smi
```

再看服务健康：

```bash
bash scripts/check_services.sh
```

如果 `planner`、`segmenter`、`powerpaint` 第一次慢，不一定是故障，通常是在下载或加载模型。
