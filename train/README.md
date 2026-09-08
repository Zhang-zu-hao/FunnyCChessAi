# AI 训练（GPU 优先）

每个玩法都走同一套 **自对弈 → 策略/价值网络** 流程，检测到 CUDA 就用 GPU。

```bash
source /data/zhangzuhao/lab/env.sh   # 仅本实验室机器需要
conda activate xiangqi-grpo          # 需已安装 CUDA 版 PyTorch
cd /path/to/FunnyCChessAi
# 按本机 CUDA 安装 PyTorch，例如：
# pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install -r train/requirements-train.txt

python -m train.loop --mode jieqi --games 200 --epochs 5
python -m train.loop --mode all --games 80 --epochs 3
```

或排队训练全部玩法（单卡顺序跑）：

```bash
bash train/queue.sh
```

权重写到 `engines/zzh/<mode>.pt`（约 180MB/个，**不要提交到 Git**）。大厅选 **ZZH** 级时会尝试加载对应权重；没有权重则回退该玩法最强内置搜索。

也可设 `XIANGQI_ZZH_URL` 指向自建 HTTP 模型（与 `XIANGQI_CUSTOM_AI_URL` 同一 JSON 约定）。

当前自对弈用随机合法着采集，便于打通 GPU 管线；正式训练请换成引擎对弈 / GRPO。
