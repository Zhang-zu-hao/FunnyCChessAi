"""训练/推理设备：优先 CUDA。"""
from __future__ import annotations


def torch_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def describe() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return f"cuda:{torch.cuda.get_device_name(0)}"
        return "cpu"
    except Exception:
        return "no-torch"
