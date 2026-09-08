from __future__ import annotations

from app.catalog import clamp_level

from .base import AIEngine, MoveRequest, MoveResponse
from .custom import HttpModelEngine
from .heuristic import HeuristicEngine
from .llm import LLMNarrator
from .pikafish import PikafishEngine
from .variant_search import VariantSearchEngine
from .zzh import ZzhEngine

_pikafish: PikafishEngine | None = None
_heuristic = HeuristicEngine()
_http: HttpModelEngine | None = None
_narrator = LLMNarrator()
_variant = VariantSearchEngine()
_zzh: ZzhEngine | None = None


def pikafish() -> PikafishEngine:
    global _pikafish
    if _pikafish is None:
        _pikafish = PikafishEngine()
    return _pikafish


def http_engine() -> HttpModelEngine:
    global _http
    if _http is None:
        _http = HttpModelEngine()
    return _http


def zzh() -> ZzhEngine:
    global _zzh
    if _zzh is None:
        _zzh = ZzhEngine()
    return _zzh


def list_engines() -> list[dict]:
    pk = pikafish()
    http = http_engine()
    z = zzh()
    return [
        {"id": pk.id, "name": pk.name, "available": pk.available(), "modes": ["xiangqi", "jieqi"]},
        {"id": _variant.id, "name": _variant.name, "available": True, "modes": sorted(_variant.modes)},
        {"id": _heuristic.id, "name": _heuristic.name, "available": True, "modes": ["xiangqi", "jieqi"]},
        {"id": http.id, "name": http.name, "available": http.available(), "modes": ["xiangqi", "jieqi"]},
        {"id": z.id, "name": z.name, "available": z.available(), "modes": sorted(z.modes)},
        {"id": "llm-narrator", "name": _narrator.name, "available": _narrator.available(), "modes": []},
    ]


def resolve(engine_id: str | None, mode: str = "jieqi") -> AIEngine:
    eid = (engine_id or "auto").lower()
    if eid in ("zzh",):
        return zzh()
    if eid in ("custom", "custom-http", "http") and http_engine().available():
        return http_engine()
    if eid in ("heuristic", "random"):
        return _heuristic
    if eid in ("variant-search", "variant") or mode in _variant.modes:
        if mode in _variant.modes and eid in ("auto", "pikafish", ""):
            return _variant
        if eid in ("variant-search", "variant"):
            return _variant
    pk = pikafish()
    if pk.available() and mode in ("xiangqi", "jieqi"):
        return pk
    if mode in _variant.modes:
        return _variant
    return _heuristic


def choose_move(req: MoveRequest, engine_id: str | None = None) -> MoveResponse:
    req.level = clamp_level(req.level)
    if req.level == 99 or (engine_id or "").lower() == "zzh":
        zresp = zzh().choose_move(req)
        if zresp.move and zresp.move in set(req.legal_moves):
            return zresp
        req.level = 10
        engine_id = "auto"
    engine = resolve(engine_id, req.mode)
    try:
        resp = engine.choose_move(req)
    except Exception as exc:
        if req.mode in _variant.modes:
            resp = _variant.choose_move(req)
        else:
            resp = _heuristic.choose_move(req)
        resp.fallback = True
        resp.comment = f"{getattr(engine, 'id', 'ai')} 失败（{exc}），兜底"
    legal = set(req.legal_moves)
    if (not resp.move) or (resp.move not in legal):
        if req.mode in _variant.modes:
            fb = _variant.choose_move(req)
        else:
            fb = _heuristic.choose_move(req)
        fb.fallback = True
        fb.comment = resp.comment or "着法非法，兜底"
        return fb
    return resp


def narrator() -> LLMNarrator:
    return _narrator


def shutdown() -> None:
    if _pikafish:
        _pikafish.close()
    if _http:
        _http.close()
