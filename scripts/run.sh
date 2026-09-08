#!/usr/bin/env bash
# shellcheck disable=SC1091
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f /data/zhangzuhao/lab/scripts/_common.sh ]]; then
  source /data/zhangzuhao/lab/scripts/_common.sh
  ENV_NAME=xiangqi-arena
  if [[ ! -x "$(env_py "$ENV_NAME")" ]]; then
    echo "请先: bash $ROOT/scripts/install.sh"
    exit 1
  fi
  cd "$ROOT"
  exec "$(env_py "$ENV_NAME")" run.py "$@"
fi
cd "$ROOT"
exec python run.py "$@"
