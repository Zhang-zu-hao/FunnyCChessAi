from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.config import CLOUDFLARED, ROOT, TUNNEL

_URL_RE = re.compile(r"https://([a-z0-9-]+)\.trycloudflare\.com")
_SKIP_HOSTS = {"api", "www"}


def lan_urls(port: int) -> list[str]:
    urls = [f"http://127.0.0.1:{port}"]
    try:
        out = subprocess.check_output(["hostname", "-I"], text=True, timeout=2)
        for ip in out.split():
            if ip.startswith("127.") or ":" in ip:
                continue
            urls.append(f"http://{ip}:{port}")
    except Exception:
        pass
    return urls


def find_cloudflared() -> str | None:
    env = os.environ.get("CLOUDFLARED_BIN") or CLOUDFLARED
    if env and Path(env).is_file() and os.access(env, os.X_OK):
        return env
    which = shutil.which("cloudflared")
    if which:
        return which
    local = ROOT / "engines" / "cloudflared"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return None


class Tunnel:
    def __init__(self, port: int):
        self.port = port
        self.public_url: str | None = None
        self._proc: subprocess.Popen | None = None
        self._lines: list[str] = []

    def start(self) -> str | None:
        if TUNNEL in ("off", "0", "false"):
            return None
        bin_path = find_cloudflared()
        if not bin_path:
            return None
        try:
            self._proc = subprocess.Popen(
                [bin_path, "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception:
            return None
        threading.Thread(target=self._pump, daemon=True).start()
        deadline = time.time() + 18
        while time.time() < deadline:
            if self.public_url:
                return self.public_url
            if self._proc.poll() is not None:
                return None
            time.sleep(0.2)
        return self.public_url

    def _pump(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._lines.append(line.rstrip())
            m = _URL_RE.search(line)
            if m and m.group(1) not in _SKIP_HOSTS:
                self.public_url = m.group(0)

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
