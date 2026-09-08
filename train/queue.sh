#!/usr/bin/env bash
# 4090 上按玩法排队训练（单卡顺序跑，避免多进程抢 GPU）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# 优先用已带 CUDA 的 xiangqi-grpo；否则用 xiangqi-arena
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
echo "Python: $PY" | tee "$LOG"
echo "GPU queue log: $LOG" | tee -a "$LOG"
"$PY" -c 'import torch; print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu")' | tee -a "$LOG"

run_one() {
  local mode="$1" games="$2" epochs="$3"
  echo "======== $mode  games=$games epochs=$epochs $(date -Iseconds) ========" | tee -a "$LOG"
  "$PY" -m train.loop --mode "$mode" --games "$games" --epochs "$epochs" --out-dir "$ROOT/engines/zzh" 2>&1 | tee -a "$LOG"
}

# 核心玩法多采一点，变体随后排队
run_one jieqi 200 5
run_one xiangqi 200 5
run_one anqi 120 5
run_one zhencha 120 5
run_one manchu 120 5
run_one bawang 120 5
run_one wuhu 120 5

echo "======== ALL DONE $(date -Iseconds) ========" | tee -a "$LOG"
ls -l "$ROOT/engines/zzh" | tee -a "$LOG"
