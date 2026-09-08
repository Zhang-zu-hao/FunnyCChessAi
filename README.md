# FunnyCChessAi

一个集**中国象棋**多种衍生玩法于一体、且内置多种 AI 引擎及模型的在线对战平台。

开发者 **ZZH** · 开源 **GPL-3.0** · 仓库 [Zhang-zu-hao/FunnyCChessAi](https://github.com/Zhang-zu-hao/FunnyCChessAi)

默认玩法为 **揭棋**。支持人机与可分享链接的在线联机。

## 玩法

大厅顺序：揭棋（默认）→ 中国象棋 → 暗棋 → 侦查象棋 → 满洲Dog棋 → 霸王棋 → 五虎棋。点选即弹出规则与图示。

## 启动

```bash
source /data/zhangzuhao/lab/env.sh   # 仅本实验室机器需要
bash scripts/install.sh             # 首次：创建 conda 环境 xiangqi-arena 并链接皮卡鱼
bash scripts/run.sh                 # 默认端口 8877
```

或：

```bash
conda activate xiangqi-arena
python run.py --port 8877
```

`--no-tunnel` 只开本机与局域网。

本地 conda 环境名仍为 `xiangqi-arena`，与仓库名 FunnyCChessAi 相互独立。

## AI 难度 1–10 与 ZZH

对局侧栏会显示当前引擎名称与关键参数。

| 档位 | 揭棋 | 中国象棋 | 其他变体 |
|---|---|---|---|
| 1–3 | 浅层 MINIMAX + 随机权重 | 皮卡鱼浅层 | 浅层规则树 |
| 4–6 | 皮卡鱼轻量提示 + 揭棋搜索 | 皮卡鱼轻量 NNUE | 标准搜索 |
| 7–9 | 皮卡鱼提示 + 揭棋全量搜索 | 皮卡鱼标准深度 | 深度搜索 |
| 10 | 最长思考 | 皮卡鱼极限 | 最长思考 |
| **ZZH** | `engines/zzh/<mode>.pt` 或 `XIANGQI_ZZH_URL`，未接入则回退 10 级 | 同左 | 同左 |

皮卡鱼二进制请自行放入 `engines/pikafish` 与 `engines/pikafish.nnue`（可用符号链接）。权重文件体积大，不进 Git，训练见 [`train/README.md`](train/README.md)。

## 可插拔接口

- `XIANGQI_CUSTOM_AI_URL`：HTTP 模型，`POST` JSON `{"mode","fen","legal_moves","side","level"}` → `{"move","comment"}`
- `XIANGQI_LLM_*`：OpenAI 兼容解说
- `XIANGQI_ZZH_URL` / `engines/zzh/<mode>.pt`：ZZH 级

## 自检

```bash
conda activate xiangqi-arena
python -m unittest tests.test_game tests.test_ai tests.test_variants -v
```
