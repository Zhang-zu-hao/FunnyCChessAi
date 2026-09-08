#!/usr/bin/env bash
# shellcheck disable=SC1091
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f /data/zhangzuhao/lab/scripts/_common.sh ]]; then
  source /data/zhangzuhao/lab/scripts/_common.sh
else
  echo "需要 conda：请自行创建环境并 pip install -r $ROOT/requirements.txt" >&2
  exit 1
fi
log "install FunnyCChessAi"

ENV_NAME=xiangqi-arena
if [[ ! -x "$(env_py "$ENV_NAME")" ]]; then
  "$CONDA_ROOT/bin/conda" create -y -n "$ENV_NAME" python=3.12
fi
PIP="$(env_pip "$ENV_NAME")"
pip_setup "$PIP"
pip_tuna "$PIP" -r "$ROOT/requirements.txt"

ENGINE_SRC=/data/zhangzuhao/xiangqi-grpo/engines
ENGINE_DST="$ROOT/engines"
mkdir -p "$ENGINE_DST"
if [[ -x "$ENGINE_SRC/pikafish" ]]; then
  ln -sfn "$ENGINE_SRC/pikafish" "$ENGINE_DST/pikafish"
  ln -sfn "$ENGINE_SRC/pikafish.nnue" "$ENGINE_DST/pikafish.nnue"
  log "linked pikafish from xiangqi-grpo"
else
  log "WARNING: $ENGINE_SRC/pikafish 不存在，人机将回退启发式"
fi

# 可选公网隧道
if [[ ! -x "$ENGINE_DST/cloudflared" ]] && ! command -v cloudflared >/dev/null 2>&1; then
  log "try download cloudflared via ghfast"
  url="https://ghfast.top/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
  if curl -fL --retry 2 --max-time 60 -o "$ENGINE_DST/cloudflared" "$url"; then
    chmod +x "$ENGINE_DST/cloudflared"
  else
    log "cloudflared 下载失败，将仅使用局域网分享"
    rm -f "$ENGINE_DST/cloudflared"
  fi
fi

"$(env_py "$ENV_NAME")" -m unittest discover -s "$ROOT/tests" -v
log "FunnyCChessAi ready"
