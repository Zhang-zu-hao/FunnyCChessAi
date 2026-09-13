from __future__ import annotations

import os
from pathlib import Path

from app.catalog import (
    JIEQI_MAX_DEPTH,
    JIEQI_TIME_SEC,
    VARIANT_DEPTH,
    VARIANT_TIME_SEC,
    XIANGQI_DEPTH,
    XIANGQI_MOVETIME_MS,
)

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = Path(os.environ.get("XIANGQI_ENGINE_DIR", ROOT / "engines"))
WEB_DIR = ROOT / "web"

HOST = os.environ.get("XIANGQI_HOST", "0.0.0.0")
PORT = int(os.environ.get("XIANGQI_PORT", "8877"))

PIKAFISH_BIN = Path(os.environ.get("PIKAFISH_BIN", ENGINE_DIR / "pikafish"))
PIKAFISH_NNUE = Path(os.environ.get("PIKAFISH_NNUE", ENGINE_DIR / "pikafish.nnue"))

CUSTOM_AI_URL = os.environ.get("XIANGQI_CUSTOM_AI_URL", "").strip()
CUSTOM_AI_KEY = os.environ.get("XIANGQI_CUSTOM_AI_KEY", "").strip()

LLM_BASE_URL = os.environ.get("XIANGQI_LLM_BASE_URL", "").strip()
LLM_API_KEY = os.environ.get("XIANGQI_LLM_API_KEY", "").strip()
LLM_MODEL = os.environ.get("XIANGQI_LLM_MODEL", "qwen2.5")

ENGINE_THREADS = int(os.environ.get("XIANGQI_ENGINE_THREADS", "4"))
ENGINE_HASH_MB = int(os.environ.get("XIANGQI_ENGINE_HASH", "64"))

# auto：默认开临时公网隧道；named：CLOUDFLARE_TUNNEL_TOKEN；off 关掉
TUNNEL = os.environ.get("XIANGQI_TUNNEL", "auto")
CLOUDFLARED = os.environ.get("CLOUDFLARED_BIN", "cloudflared")
TUNNEL_TOKEN = (
    os.environ.get("CLOUDFLARE_TUNNEL_TOKEN") or os.environ.get("XIANGQI_TUNNEL_TOKEN") or ""
).strip()
PUBLIC_URL = os.environ.get("XIANGQI_PUBLIC_URL", "").strip().rstrip("/")

LEVEL_DEPTH = XIANGQI_DEPTH
LEVEL_MOVETIME_MS = XIANGQI_MOVETIME_MS
