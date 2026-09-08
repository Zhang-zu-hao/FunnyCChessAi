#!/usr/bin/env bash
# 单卡：GPU 大批次自对弈 + AMP 残差网络
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if /data/zhangzuhao/miniconda3/envs/xiangqi-grpo/bin/python -c 'import torch,cchess' 2>/dev/null; then
  PY=/data/zhangzuhao/miniconda3/envs/xiangqi-grpo/bin/python
elif /data/zhangzuhao/miniconda3/envs/xiangqi-arena/bin/python -c 'import torch' 2>/dev/null; then
  PY=/data/zhangzuhao/miniconda3/envs/xiangqi-arena/bin/python
else
  echo "请先安装 GPU 版 PyTorch" >&2
  exit 1
fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
mkdir -p "$ROOT/train/logs" "$ROOT/engines/zzh"
LOG="$ROOT/train/logs/queue_$(date +%Y%m%d_%H%M%S).log"
HOURS="${TRAIN_HOURS:-3.0}"
echo "Python: $PY" | tee "$LOG"
echo "GPU-heavy queue log: $LOG  hours=$HOURS" | tee -a "$LOG"
"$PY" -c 'import torch; print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")' | tee -a "$LOG"
echo "======== train.loop GPU --hours $HOURS $(date -Iseconds) ========" | tee -a "$LOG"
"$PY" -m train.loop --mode all --hours "$HOURS" --batch-size 4096 --play-batch 256 --play-games 2048 --out-dir "$ROOT/engines/zzh" 2>&1 | tee -a "$LOG"
echo "======== ALL DONE $(date -Iseconds) ========" | tee -a "$LOG"
ls -lh "$ROOT/engines/zzh" | tee -a "$LOG"
