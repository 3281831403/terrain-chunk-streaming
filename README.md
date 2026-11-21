# terrain-chunk-streaming

## 题面

开放世界跑图开始卡顿，走两步就掉帧、远处地形还缺一块：驻留按矩形而不是环，角落超载；LOD 距离数组无序，选错层级；预算只按块数，忽略块大小；优先队列用 `heapq` 但元组含 dict，比较抛错；卸载不检查引用计数，正在用的块被释放；重复块不去重，同一块加载两次；LOD 跳跃不检测，出现空洞；加载帧数向下取整，永远差一帧；批量共用驻留集合，帧之间串；`radius=0` 不校验，返回空集导致除零。stream/terrains.py 是核心，tests/test_terrains.py 15个红。要修的是：环形驻留、无序距离阈值选层、字节预算、稳定优先队列、引用计数保护、重复块去重、LOD 跳跃检测、帧数向上取整、帧间隔离与整体回滚、radius 校验，让 15 个测试全部通过。

## 运行方式

在仓库根目录执行：

```bash
python -m pytest tests -q
```

初始状态必须恰好输出 `15 failed`，不能有 collection、import 或 syntax error。除 Python 标准库（`math`、`heapq`）和 pytest 外无外部依赖；全程离线、不使用随机数。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 图形渲染 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 约束

- `stream/terrains.py` 中的 8 个函数目前全部 `raise NotImplementedError`，契约写在各自 docstring 中。
- 块字典固定使用 `{"cx", "cz", "lod", "size", "loaded"}` 五个字段；坐标单位为块，LOD 从 0 开始，预算单位为字节。
- `tests/test_terrains.py` 不可修改。修复实现，不要改动、删除或跳过测试。
