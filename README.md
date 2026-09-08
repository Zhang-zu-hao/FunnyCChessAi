<div align="center">

# FunnyCChessAi

**一个集中国象棋多种衍生玩法于一体、且内置多种 AI 引擎及模型的在线对战平台**

[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

开发者 **ZZH** · 默认玩法 **揭棋** · 人机对战 / 可分享房间

[功能](#功能) · [玩法](#玩法) · [快速开始](#快速开始) · [AI](#ai-难度) · [训练](#训练) · [许可证](#许可证)

</div>

---

## 简介

[揭棋](https://image.qqchess.qq.com/test_160324/activity/html/jieqiguize.html) 等变体是不完全信息棋：暗子不能直接丢给标准象棋引擎。FunnyCChessAi 把 **规则、搜索、Web 对局、可插拔模型** 放在同一套服务里：

- 浏览器打开即可人机或联机，大厅点选玩法会弹出规则与图示
- 中国象棋走 [Pikafish](https://github.com/official-pikafish/Pikafish)；揭棋走专用规则树（negamax / 迭代加深 / 静态搜索），高强度档可叠加皮卡鱼开局提示
- 难度 **1–10** 与 **ZZH**（本地 `engines/zzh/<mode>.pt` 或 HTTP 模型）；未接入权重时回退该玩法最强内置搜索

## 功能

- **七种玩法**：揭棋（默认）、中国象棋、暗棋、侦查象棋、满洲Dog棋、霸王棋、五虎棋
- **人机 / 在线房间**：创建房间后复制链接，同网段或（可选）公网隧道即可对弈
- **可插拔 AI**：皮卡鱼 UCI、变体规则搜索、HTTP 自定义模型、OpenAI 兼容解说、ZZH 权重
- **训练入口**：自对弈采集 + 策略/价值网络，CUDA 可用时自动走 GPU（见 [`train/README.md`](train/README.md)）

## 玩法

| 顺序 | 模式 | 说明 |
|:---:|:---|:---|
| 1 | **揭棋** | 将帅明放，其余扣放；暗子按开局占位子走，走完翻开 |
| 2 | 中国象棋 | 传统明棋，皮卡鱼引擎 |
| 3 | 暗棋 | 4×8 翻翻棋：翻子或走一格 |
| 4 | 侦查象棋 | 暗子可伪装走法，吃暗须猜真身 |
| 5 | 满洲Dog棋 | 红方一枚「满洲车」兼车/马/炮 |
| 6 | 霸王棋 | 红方帅+车，每回合两次行动 |
| 7 | 五虎棋 | 红方五兵仕相帅，兵可连动 |

规则全文与图示在大厅点选玩法时弹出，亦写在 `app/catalog.py`。

## 快速开始

需要 **Python 3.10+**。

```bash
git clone https://github.com/Zhang-zu-hao/FunnyCChessAi.git
cd FunnyCChessAi

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py --port 8877
```

浏览器打开终端里打印的地址（本机一般为 `http://127.0.0.1:8877`）。

| 参数 / 环境变量 | 默认 | 说明 |
|---|---|---|
| `--host` / `XIANGQI_HOST` | `0.0.0.0` | 监听地址 |
| `--port` / `XIANGQI_PORT` | `8877` | 端口 |
| `--no-tunnel` / `XIANGQI_TUNNEL=off` | `auto` | 关闭 cloudflared 公网隧道，仅本机与局域网 |

本实验室若已有 conda 环境 `xiangqi-arena`，也可：

```bash
conda activate xiangqi-arena
python run.py --port 8877
# 或：bash scripts/run.sh
```

## 皮卡鱼（中国象棋人机）

标准象棋强度依赖 [Pikafish](https://github.com/official-pikafish/Pikafish)。请自行将二进制与网络文件放到：

```
engines/pikafish
engines/pikafish.nnue
```

也可用环境变量 `PIKAFISH_BIN`、`PIKAFISH_NNUE`，或对已编译文件做符号链接。未放置时，象棋人机回退启发式，揭棋仍使用内置搜索。

## AI 难度

对局侧栏会显示当前引擎名称与关键参数。

| 档位 | 揭棋 | 中国象棋 | 其他变体 |
|---|---|---|---|
| 1–3 | 浅层 minimax + 随机权重 | 皮卡鱼浅层 | 浅层规则树 |
| 4–6 | 皮卡鱼开局提示 + 揭棋搜索 | 皮卡鱼轻量 NNUE | 标准搜索 |
| 7–9 | 皮卡鱼提示 + 揭棋全量搜索 | 皮卡鱼标准深度 | 深度搜索 |
| 10 | 最长思考 | 皮卡鱼极限 | 最长思考 |
| **ZZH** | 加载 `engines/zzh/<mode>.pt` 或 `XIANGQI_ZZH_URL`；失败则回退 10 级 | 同左 | 同左 |

ZZH 权重约 180MB/个，**不进入 Git**（GitHub 单文件限制 100MB）。训练方法见下方与 [`train/README.md`](train/README.md)。

当前仓库内训练管线用随机合法着做自对弈，用于打通 GPU 与存盘格式；棋力不等于皮卡鱼或正式 GRPO 引擎。

## 配置

| 变量 | 作用 |
|---|---|
| `XIANGQI_CUSTOM_AI_URL` | 自定义着法服务。`POST` JSON `{"mode","fen","legal_moves","side","level"}` → `{"move","comment"}` |
| `XIANGQI_CUSTOM_AI_KEY` | 可选，`Authorization: Bearer …` |
| `XIANGQI_ZZH_URL` | ZZH 档 HTTP 模型（约定同上） |
| `XIANGQI_ZZH_DIR` | 本地权重目录，默认 `engines/zzh` |
| `XIANGQI_LLM_BASE_URL` / `XIANGQI_LLM_API_KEY` / `XIANGQI_LLM_MODEL` | OpenAI 兼容解说 |
| `XIANGQI_ENGINE_THREADS` / `XIANGQI_ENGINE_HASH` | 皮卡鱼线程与 Hash（MB） |
| `XIANGQI_ENGINE_DIR` | 引擎根目录，默认 `engines/` |
| `CLOUDFLARED_BIN` | 公网隧道可执行文件 |

## 训练

需要已安装 **CUDA 版 PyTorch** 的环境（例如本机 conda `xiangqi-grpo`）。

```bash
pip install -r train/requirements-train.txt
# 按本机 CUDA 安装 torch，例如：
# pip install torch --index-url https://download.pytorch.org/whl/cu124

python -m train.loop --mode jieqi --games 200 --epochs 5
python -m train.loop --mode all --games 80 --epochs 3
bash train/queue.sh          # 七种玩法单卡顺序排队
```

权重写入 `engines/zzh/<mode>.pt`。大厅选择 **ZZH** 时加载对应文件。

## 仓库结构

```
FunnyCChessAi/
├── app/                 # FastAPI 服务与对局逻辑
│   ├── catalog.py       # 玩法、难度、对外元数据（项目名/协议/仓库地址）
│   ├── main.py          # HTTP / WebSocket 入口
│   ├── rooms.py         # 房间、人机调度
│   ├── game/            # 各玩法规则
│   └── ai/              # 皮卡鱼 / 揭棋搜索 / 变体搜索 / ZZH / HTTP
├── web/                 # 大厅与棋盘前端
├── train/               # 自对弈训练
├── engines/             # 皮卡鱼、ZZH 权重（二进制不入库）
├── tests/               # unittest
├── scripts/             # 安装与启动辅助脚本
├── run.py               # 启动入口
├── requirements.txt     # 对战服务依赖
└── LICENSE              # GPL-3.0
```

## HTTP / WebSocket

| 路径 | 说明 |
|---|---|
| `GET /` | 大厅页面 |
| `GET /health` | 健康检查、引擎是否可用 |
| `GET /api/info`、`GET /api/modes` | 项目元数据与玩法目录 |
| `WS /ws` | 对局：`create` / `join` / `move` / `seat` / `new_game` / `resign` / `level` |

## 测试

```bash
python -m unittest tests.test_game tests.test_ai tests.test_variants -v
```

皮卡鱼相关用例在 `engines/pikafish` 不存在时自动跳过。

## 致谢

- [Pikafish](https://github.com/official-pikafish/Pikafish)（GPL-3.0）
- [cchess](https://pypi.org/project/cchess/)（GPL）

## 许可证

[GPL-3.0](LICENSE)。与皮卡鱼、cchess 的传染性协议兼容。欢迎学习、对局与二次开发。

开发者 **ZZH** · [Zhang-zu-hao/FunnyCChessAi](https://github.com/Zhang-zu-hao/FunnyCChessAi)
