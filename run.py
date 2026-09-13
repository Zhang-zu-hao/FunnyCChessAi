#!/usr/bin/env python3
"""单次启动：Web 服务 + 可分享链接。"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from app.catalog import LICENSE_NAME, PROJECT_TITLE

    parser = argparse.ArgumentParser(description=PROJECT_TITLE)
    parser.add_argument("--host", default=os.environ.get("XIANGQI_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("XIANGQI_PORT", "8877")))
    parser.add_argument("--no-tunnel", action="store_true", help="关闭公网隧道，仅本机与局域网")
    parser.add_argument(
        "--public-url",
        default=os.environ.get("XIANGQI_PUBLIC_URL", ""),
        help="固定公网地址，例如 https://chess.example.com",
    )
    parser.add_argument(
        "--tunnel-token",
        default=os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", "") or os.environ.get("XIANGQI_TUNNEL_TOKEN", ""),
        help="Cloudflare Named Tunnel token（固定域名，比 trycloudflare 稳）",
    )
    args = parser.parse_args()
    os.environ["XIANGQI_HOST"] = args.host
    os.environ["XIANGQI_PORT"] = str(args.port)
    if args.no_tunnel:
        os.environ["XIANGQI_TUNNEL"] = "off"
    if args.public_url:
        os.environ["XIANGQI_PUBLIC_URL"] = args.public_url.strip().rstrip("/")
    if args.tunnel_token:
        os.environ["CLOUDFLARE_TUNNEL_TOKEN"] = args.tunnel_token.strip()

    from app.main import app
    import uvicorn

    print("=" * 56)
    print(f"  {PROJECT_TITLE}  ·  {LICENSE_NAME}")
    print("  揭棋 / 中国象棋 / 暗棋 / 侦查 / 满洲Dog / 霸王 / 五虎")
    print(f"  监听 {args.host}:{args.port} （启动后见终端里的访问链接）")
    print("=" * 56)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
