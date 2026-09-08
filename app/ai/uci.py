from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

_BESTMOVE_RE = re.compile(r"^\s*bestmove\s+(\S+)")
_SCORE_RE = re.compile(r"score\s+(?:cp\s+)?(mate\s+)?(-?\d+)")
_DEPTH_RE = re.compile(r"\binfo\s+depth\s+(\d+)")


class UCIEngine:
    """通用 UCI 引擎进程（皮卡鱼等）。cwd 必须能找到 NNUE。"""

    def __init__(
        self,
        path: str | Path,
        eval_file: str | Path | None = None,
        threads: int = 2,
        hash_mb: int = 64,
        name: str | None = None,
    ):
        self.path = str(Path(path).resolve())
        self.eval_file = str(Path(eval_file).resolve()) if eval_file else None
        self.threads = threads
        self.hash_mb = hash_mb
        self.name = name or Path(self.path).name
        self._lines: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._start()

    def _start(self) -> None:
        cwd = str(Path(self.path).parent)
        env = dict(os.environ)
        self._proc = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            cwd=cwd,
            env=env,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        self._send("uci")
        self._expect(("uciok",), 15)
        self._send(f"setoption name Threads value {self.threads}")
        self._send(f"setoption name Hash value {self.hash_mb}")
        if self.eval_file:
            self._send(f"setoption name EvalFile value {self.eval_file}")
        self._send("ucinewgame")
        self._send("isready")
        self._expect(("readyok",), 30)

    def _reader(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._lines.put(line.rstrip("\n"))

    def _send(self, line: str) -> None:
        if not self.alive:
            raise RuntimeError(f"引擎已退出: {self.name}")
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(line + "\n")
        self._proc.stdin.flush()

    def _readline(self, timeout: float) -> str:
        try:
            return self._lines.get(timeout=max(0.05, timeout))
        except queue.Empty:
            return ""

    def _expect(self, keywords: tuple[str, ...], timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self._readline(deadline - time.time())
            if any(k in line for k in keywords):
                return
        raise RuntimeError(f"{self.name} 未在 {timeout}s 内返回 {keywords}")

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def restart(self) -> None:
        self.quit()
        while not self._lines.empty():
            try:
                self._lines.get_nowait()
            except queue.Empty:
                break
        self._start()

    def quit(self) -> None:
        try:
            if self.alive:
                self._send("quit")
                self._proc.wait(timeout=2)
        except Exception:
            pass
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.kill()
        except Exception:
            pass
        try:
            if self._proc:
                if self._proc.stdin:
                    self._proc.stdin.close()
                if self._proc.stdout:
                    self._proc.stdout.close()
        except Exception:
            pass
        self._proc = None

    def best_move(
        self,
        fen: str,
        movetime_ms: int | None = None,
        depth: int | None = None,
        searchmoves: list[str] | None = None,
        timeout_sec: float | None = None,
    ) -> tuple[str, float | None]:
        with self._lock:
            try:
                return self._best_move(fen, movetime_ms, depth, searchmoves, timeout_sec)
            except (RuntimeError, BrokenPipeError, OSError):
                try:
                    self.restart()
                    return self._best_move(fen, movetime_ms, depth, searchmoves, timeout_sec)
                except Exception:
                    return "", None

    def _best_move(
        self,
        fen: str,
        movetime_ms: int | None,
        depth: int | None,
        searchmoves: list[str] | None,
        timeout_sec: float | None = None,
    ) -> tuple[str, float | None]:
        while not self._lines.empty():
            try:
                self._lines.get_nowait()
            except queue.Empty:
                break
        cmd = f"position fen {fen}"
        self._send(cmd)
        go = "go"
        if depth is not None:
            go += f" depth {depth}"
        elif movetime_ms is not None:
            go += f" movetime {movetime_ms}"
        else:
            go += " depth 8"
        if searchmoves:
            go += " searchmoves " + " ".join(searchmoves)
        self._send(go)
        wait = 8.0
        if depth is not None:
            wait = max(4.0, float(depth) * 0.9 + 2.0)
        if movetime_ms:
            wait = max(wait, movetime_ms / 1000 + 5)
        if timeout_sec is not None:
            wait = timeout_sec
        deadline = time.time() + wait
        scores: dict[int, float] = {}
        best = ""
        while time.time() < deadline:
            line = self._readline(min(0.5, deadline - time.time()))
            if not line:
                continue
            dm = _DEPTH_RE.search(line)
            sm = _SCORE_RE.search(line)
            if sm:
                d = int(dm.group(1)) if dm else 0
                mate = bool(sm.group(1))
                val = int(sm.group(2))
                scores[d] = (1e5 if val > 0 else -1e5) * max(1, abs(val)) if mate else float(val)
            m = _BESTMOVE_RE.match(line)
            if m:
                best = m.group(1)
                if best in ("(none)", "0000", "none"):
                    best = ""
                break
        if not best:
            try:
                self._send("stop")
            except Exception:
                pass
        score = scores[max(scores)] if scores else None
        return best, score
