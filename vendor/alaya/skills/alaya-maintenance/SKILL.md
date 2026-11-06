---
name: alaya-maintenance
description: 检查和维护 Alaya 知识库，包括动态索引、类别描述提醒、链接审计、90天熏习衰减、安装校验与健康检查。用于用户要求检查、修复、重建索引、熏习或排查知识库异常。
---

# Alaya 维护

## 默认原则

- 先检查、后写入。健康检查和链接检查默认只读。
- 类别以 `wiki/` 下当前有效目录为准，数量可以动态增加；发布后校验“总索引类别集合 = 磁盘有效类别集合”。`16` 只是旧知识库兼容基线，不是硬编码上限。
- 类别减少可能是误删或扫描错误，默认阻止发布；用户确认确实删除后才加 `--confirm-removals`。
- `_generated` 标记只控制自动生成区域，用户手写说明不得被覆盖。

## 健康检查

```bash
python scripts/health_check.py --kb-root <目录>
python scripts/health_check.py --kb-root <目录> --json
```

检查配置兼容、角色、记忆、严格知识卡、动态类别集合、当前发布标记、原文引用和链接。旧字段别名只报告兼容状态，不自动改用户配置。

## 索引

```bash
python scripts/build_index.py --full --check-only --kb-root <目录>
python scripts/build_index.py --full --kb-root <目录>
python scripts/build_index.py --category <类别> --kb-root <目录>
```

单类别模式只重扫该类别，但重新发布的总索引仍必须是完整集合。同一天多次更新不能仅靠日期判断是否已发布，应比较当前内容清单与发布清单。

类别描述分两条线：

- 当前清单：每次索引立刻更新，机械生成，不调用大模型。
- 描述基线：智能体真正重写类别描述后，用 `--mark-description-updated <类别>` 标记。

内容变化后，在每次导入反馈中让用户选择立即更新描述或继续累计；最迟 3 天提醒。数量阈值按类别规模自适应，避免小类别太迟、大类别太频繁。

## 链接

```bash
python scripts/fix_links.py --kb-root <目录>
python scripts/fix_links.py --kb-root <目录> --apply
```

扫描所有 Markdown。识别相对路径、根路径、锚点和别名。默认只报告；`--apply` 只修复唯一可确定的大小写错误。同名目标产生歧义时不自动选择。

## 熏习

```bash
python scripts/perfume.py --level 3 --kb-root <目录>
python scripts/perfume.py --level 2 --kb-root <目录>
```

`level 3（到期检查）` 可稳定搭便车在每次回答提交、导入完成和群组汇总之后；同一维护周期自动去重。`level 2（立即维护）` 用于用户明确要求。

默认参数让普通知识卡从强度 `0.5` 约 90 天衰减到休眠阈值 `0.1`。算法只保留一个主周期参数，衰减率和半衰期由它推导。卡片只有显式设置非旧默认值的专用半衰期时才覆盖全局策略。首次升级只写当天基线，不补扣历史。

## 安装与单文件包

```bash
python scripts/verify_installation.py
python scripts/build_skill_full.py --check-only
python scripts/build_skill_full.py
```

正常安装验证多文件核心。`SKILL_FULL.md` 是可选兼容产物，仅 `verify_installation.py --single-file` 要求它存在。构建器只读取显式标记区块，不用宽泛正则猜内容。

## 返回码

- `0`：检查通过或动作完成。
- `1`：发现需要人工处理的健康/质量问题。
- `2`：参数、配置、路径或执行错误。

不要把大量警告等同于损坏。检查项应给出精确文件和原因；同一根因尽量合并报告。
