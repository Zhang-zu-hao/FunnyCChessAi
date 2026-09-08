# 引擎目录

此目录**不入库**大型二进制：

- `pikafish` / `pikafish.nnue`：标准象棋 UCI 引擎（可从 [Pikafish](https://github.com/official-pikafish/Pikafish) 获取，或对本机已编译文件做符号链接）
- `cloudflared`：可选，用于生成公网分享链接
- `zzh/*.pt`：ZZH 级策略网络权重，用 `python -m train.loop` 或 `bash train/queue.sh` 生成
