"""大语言模型解说接口（可选，首次交付不强制启用）。

约定：OpenAI 兼容 POST /chat/completions。
配置 XIANGQI_LLM_BASE_URL / XIANGQI_LLM_API_KEY / XIANGQI_LLM_MODEL 后，
可在走子后请求一句趣味解说。本地 Qwen 也可走同一协议。
"""
from __future__ import annotations

import json
from urllib import request

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class LLMNarrator:
    id = "llm-narrator"
    name = "LLM 棋局解说"

    def available(self) -> bool:
        return bool(LLM_BASE_URL)

    def comment(self, mode: str, move: str, fen: str, event: dict | None = None) -> str:
        if not LLM_BASE_URL:
            return ""
        sys_prompt = (
            "你是中国象棋讲解员。用一两句中文有趣地解说刚走的棋，不要给出下一步建议。"
            f"当前玩法：{'揭棋' if mode == 'jieqi' else '象棋'}。"
        )
        user = f"走法 {move}。局面 FEN：{fen}。事件：{event or {}}"
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user},
            ],
            "max_tokens": 80,
            "temperature": 0.8,
        }
        headers = {"Content-Type": "application/json"}
        if LLM_API_KEY:
            headers["Authorization"] = f"Bearer {LLM_API_KEY}"
        url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
        req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=6) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""
