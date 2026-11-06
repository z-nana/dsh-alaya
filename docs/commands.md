# 命令映射

先调用 `alaya_guide` 读取对应主题。`alaya_run` 的 `args_json` 是字符串数组的 JSON 文本，不执行 shell。所有命令均由桥接器注入 `--kb-root`，参数中不能再次指定。可传 `["--help"]` 获取完整用法。

| command | 上游脚本 | 常用参数 |
|---|---|---|
| health | health_check.py | `--json`，默认只读 |
| index | build_index.py | `--check-only`、`--full`、`--category <类别>` |
| links | fix_links.py | 默认预览，`--apply` 修正确定的大小写链接 |
| personas | persona_manager.py | `list`、`clone 源 目标`、`delete 名称 --yes`、`restore 回收项` |
| memory | memory_manager.py | `show`、`set --payload-file -`、`forget 字段`、`invitation later/never/reset` |
| commit | perfume.py | `--level answer/group/1/2/3 --payload-file -` |
| observe | bi_observer.py | 默认只读，`--write` 更新观察，`--migrate` 显式迁移 |
| import | batch_import.py | `源 --category 类别 --copy-raw yes/no --dry-run` |
| paper | import_paper.py | `源 --mode info/full --category 类别 --copy-raw yes/no --dry-run` |
| card | post_process.py | `卡片路径 --category 类别 --copy-raw yes/no --dry-run` |
| quality | import_quality_review.py | `--category 类别`，生成上游质量报告，可能写入报告文件 |

上游 `quality` 不是纯只读操作；执行前按写操作处理。首次初始化不做旧版库迁移；需要迁移时先备份，并按上游指南在用户明确要求下操作。

稳定偏好写入示例：

```json
{
  "command": "memory",
  "args_json": "[\"set\",\"--payload-file\",\"-\"]",
  "stdin": "{\"fields\":{\"language\":{\"value\":\"简体中文\",\"source\":\"user_confirmed\"}}}",
  "kb_root": "D:/Alaya知识库"
}
```

执行结果包含 `ok`、`exitCode`、`stdout`、`stderr`；`exitCode != 0` 表示脚本失败，不能据此宣称写入成功。路径、读取与搜索等传输错误会作为 DSH 工具错误抛出。
