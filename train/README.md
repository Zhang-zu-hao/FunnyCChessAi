# 训练

每个玩法走同一套 **自对弈 → 策略/价值网络**。检测到 CUDA 时使用 GPU。

## 环境

对战服务本身**不需要** PyTorch。训练需要 CUDA 版 PyTorch（2.1+）。

```bash
cd FunnyCChessAi
pip install -r requirements.txt
pip install -r train/requirements-train.txt
# 按本机 CUDA 安装 torch，例如：
# pip install torch --index-url https://download.pytorch.org/whl/cu124
```

## 命令

```bash
python -m train.loop --mode jieqi --games 200 --epochs 5
python -m train.loop --mode all --games 80 --epochs 3
bash train/queue.sh
```

`--mode` 可选：`jieqi`、`xiangqi`、`anqi`、`zhencha`、`manchu`、`bawang`、`wuhu`、`all`。

权重写入 `engines/zzh/<mode>.pt`（约 180MB/个，已在 `.gitignore` 中排除）。大厅选 **ZZH** 时加载对应文件；缺失或推理失败则回退该玩法 10 级搜索。

也可设 `XIANGQI_ZZH_URL`，约定与 `XIANGQI_CUSTOM_AI_URL` 相同：

```json
POST {"mode","fen","legal_moves","side","level"}
→ {"move": "h2e2", "comment": "..."}
```

## 说明

当前自对弈采样为**随机合法着**，用于打通 GPU 与 checkpoint 格式，不是强棋力训练。若要提高棋力，请换成引擎对弈或 GRPO 等强化学习流程后再写入同一 `engines/zzh/<mode>.pt`。
