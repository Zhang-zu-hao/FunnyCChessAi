# engines/

本目录存放对局引擎与模型权重，**大型二进制不入库**。

| 文件 | 用途 | 获取 |
|---|---|---|
| `pikafish` + `pikafish.nnue` | 中国象棋 UCI 引擎 | [Pikafish](https://github.com/official-pikafish/Pikafish) 发布包，或本地编译后符号链接 |
| `cloudflared` | 可选，公网分享链接 | [cloudflared](https://github.com/cloudflare/cloudflared/releases) |
| `zzh/<mode>.pt` | ZZH 档策略网络 | `python -m train.loop` 或 `bash train/queue.sh`，见 [`../train/README.md`](../train/README.md) |

环境变量：`PIKAFISH_BIN`、`PIKAFISH_NNUE`、`XIANGQI_ENGINE_DIR`、`XIANGQI_ZZH_DIR`。
