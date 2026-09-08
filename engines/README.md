# engines/

| 文件 | 用途 | 获取 |
|---|---|---|
| `pikafish` + `pikafish.nnue` | 中国象棋 UCI 引擎 | [Pikafish](https://github.com/official-pikafish/Pikafish)，二进制不入库 |
| `cloudflared` | 可选公网分享 | 不入库 |
| `zzh/<mode>.pt` | **自训练**策略网络 | `bash train/queue.sh`，随仓库发布 |
| `local/*.pt` | 你自己的权重 | 大厅上传或拷贝到该目录，不入库 |
