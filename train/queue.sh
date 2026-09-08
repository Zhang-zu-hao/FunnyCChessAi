#!/usr/bin/env bash
# 单卡排队：搜索教师自对弈，默认约 3.5 小时
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
HOURS="${TRAIN_HOURS:-3.5}"
echo "Python: $PY" | tee "$LOG"
echo "GPU queue log: $LOG  hours=$HOURS" | tee -a "$LOG"
"$PY" -c 'import torch; print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")' | tee -a "$LOG"
echo "======== train.loop --mode all --hours $HOURS $(date -Iseconds) ========" | tee -a "$LOG"
"$PY" -m train.loop --mode all --hours "$HOURS" --teacher-level 2 --epochs 8 --out-dir "$ROOT/engines/zzh" 2>&1 | tee -a "$LOG"
echo "======== ALL DONE $(date -Iseconds) ========" | tee -a "$LOG"
ls -l "$ROOT/engines/zzh" | tee -a "$LOG"
