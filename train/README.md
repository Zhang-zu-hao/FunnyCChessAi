# 训练

默认走 **GPU 满载**：并行策略自对弈（棋盘编码后整批送进 4090）+ AMP 残差网络（16×256）。训练阶段 batch=4096，反复抽样 replay，让 GPU 持续算而不是在 CPU 搜索上空转。

```bash
bash train/queue.sh
# 或
TRAIN_HOURS=3.0 bash train/queue.sh
python -m train.loop --mode all --hours 3.0 --batch-size 4096 --play-batch 256
```

需要 CUDA 版 PyTorch（2.1+）以及 `pip install -r requirements.txt`。

权重写入 `engines/zzh/<mode>.pt`（fp16，通常远小于 100MB）。大厅选 **自训练** 或 AI 对战里选「自训练模型」时加载。

揭棋 / 暗棋编码里，未翻开的子一律写成 `X`，网络看不到预定真身；教师搜索同样只用子力池期望。暗子在棋盘上的格子是公开信息（扣着的棋谁都能看见），隐藏的是身份不是坐标。

也可设 `XIANGQI_ZZH_URL`，约定与 `XIANGQI_CUSTOM_AI_URL` 相同。自己的 `.pt` 放到 `engines/local/` 或在大厅上传即可互战。
