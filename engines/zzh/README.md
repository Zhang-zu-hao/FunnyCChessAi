# 自训练权重

`python -m train.loop` 或 `bash train/queue.sh` 会把各玩法权重写到本目录：`<mode>.pt`。

大厅难度选 **自训练**，或 AI 对战里选「自训练模型」，即加载对应文件。架构为轻量 from/to 卷积，单文件通常远小于 100MB，可随仓库发布。
