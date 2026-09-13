from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from app.config import CLOUDFLARED, PUBLIC_URL, ROOT, TUNNEL, TUNNEL_TOKEN

_URL_RE = re.compile(r"https://([a-z0-9-]+)\.trycloudflare\.com")
_NAMED_OK = re.compile(r"Registered tunnel connection|connIndex=")
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
        self._named_ready = False

    def start(self) -> str | None:
        if TUNNEL in ("off", "0", "false"):
            print("公网隧道已关闭（--no-tunnel / XIANGQI_TUNNEL=off）", flush=True)
            if PUBLIC_URL:
                print(f"使用固定公网地址：{PUBLIC_URL}", flush=True)
            return PUBLIC_URL or None
        if TUNNEL_TOKEN:
            bin_path = find_cloudflared()
            if not bin_path:
                print("未找到 cloudflared，无法开 Named Tunnel（可放到 engines/cloudflared）", flush=True)
                return PUBLIC_URL or None
            print(f"正在开启 Cloudflare Named Tunnel（{bin_path}）…", flush=True)
            time.sleep(0.4)
            return self._start_named(bin_path)
        if PUBLIC_URL:
            print(
                f"已设置 XIANGQI_PUBLIC_URL={PUBLIC_URL}，不再开 trycloudflare 临时域名。",
                flush=True,
            )
            return PUBLIC_URL
        bin_path = find_cloudflared()
        if not bin_path:
            print("未找到 cloudflared，无法开公网隧道（可放到 engines/cloudflared）", flush=True)
            return None
        print(f"正在开启公网隧道（{bin_path}）…", flush=True)
        time.sleep(0.4)
        cmd = [bin_path, "tunnel", "--url", f"http://127.0.0.1:{self.port}", "--no-autoupdate"]
        if shutil.which("stdbuf"):
            cmd = ["stdbuf", "-oL", "-eL"] + cmd
        url = self._launch(cmd, wait_url=True)
        if url:
            return url
        print("公网隧道第一次未就绪，重试一次…", flush=True)
        self.stop()
        time.sleep(1)
        url = self._launch(cmd, wait_url=True)
        if url:
            return url
        tail = "\n".join(self._lines[-8:]) if self._lines else "(无日志)"
        print("公网隧道未能建立，外网暂不可达。日志：\n" + tail, flush=True)
        return None

    def _start_named(self, bin_path: str) -> str | None:
        """Cloudflare Named Tunnel：域名固定，比 trycloudflare 临时链接稳。"""
        cmd = [bin_path, "tunnel", "--no-autoupdate", "run", "--token", TUNNEL_TOKEN]
        ok = self._launch(cmd, wait_url=False, alive_sec=20)
        if not ok:
            print("Named Tunnel 第一次未就绪，重试一次…", flush=True)
            self.stop()
            time.sleep(1)
            ok = self._launch(cmd, wait_url=False, alive_sec=20)
        if not ok:
            tail = "\n".join(self._lines[-8:]) if self._lines else "(无日志)"
            print("Named Tunnel 启动失败。日志：\n" + tail, flush=True)
            return PUBLIC_URL or None
        if PUBLIC_URL:
            print(f"Named Tunnel 已连接，固定公网：{PUBLIC_URL}", flush=True)
            return PUBLIC_URL
        print(
            "Named Tunnel 已启动，请设置 XIANGQI_PUBLIC_URL=https://你的域名 以便大厅显示固定地址。",
            flush=True,
        )
        return None

    def _launch(self, cmd: list[str], *, wait_url: bool = True, alive_sec: float = 35) -> str | None:
        self.public_url = None
        self._named_ready = False
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            print(f"启动 cloudflared 失败：{exc}", flush=True)
            return None
        threading.Thread(target=self._pump, daemon=True).start()
        deadline = time.time() + alive_sec
        while time.time() < deadline:
            if wait_url and self.public_url:
                return self.public_url
            if not wait_url and self._named_ready:
                return "ok"
            if self._proc.poll() is not None:
                return None
            time.sleep(0.2)
        if wait_url:
            return self.public_url
        return "ok" if (self._proc and self._proc.poll() is None) else None

    def _pump(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._lines.append(line.rstrip())
            m = _URL_RE.search(line)
            if m and m.group(1) not in _SKIP_HOSTS:
                self.public_url = m.group(0)
            if _NAMED_OK.search(line):
                self._named_ready = True

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
        self._proc = None
