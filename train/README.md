# 训练

每个玩法：**内置搜索当教师自对弈** → 策略/价值网络。检测到 CUDA 时用 GPU 训练网络（采集阶段主要吃 CPU/搜索）。

旧版随机合法着几分钟就能跑完，棋力很差。请用时间预算重训，例如约 3.5 小时：

```bash
bash train/queue.sh          # 默认 TRAIN_HOURS=3.5
# 或
python -m train.loop --mode all --hours 3.5 --teacher-level 2 --epochs 8
```

环境需要 CUDA 版 PyTorch（2.1+）以及对战依赖（`cchess` 等）。

```bash
pip install -r requirements.txt
pip install -r train/requirements-train.txt
```

权重写入 `engines/zzh/<mode>.pt`。网络是 from/to 分解的轻量卷积，便于放进 Git。大厅选 **自训练** 或 AI 对战里选「自训练模型」时加载；缺失则回退该玩法 10 级搜索。

也可设 `XIANGQI_ZZH_URL`，约定与 `XIANGQI_CUSTOM_AI_URL` 相同。

把你自己的 `.pt` 放到 `engines/local/` 或在大厅上传，即可与皮卡鱼 / 启发式 / 自训练模型互相对战。
