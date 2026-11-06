# Alaya 技术参考

## 路径解析

运行期用户数据只允许来自：

1. 命令行 `--kb-root`；
2. `ALAYA_PATH_FILE` 指定的路径指针；
3. 用户主目录 `.alaya_path`；
4. 当前目录本身就是含 `alaya/config.json` 的知识库。

不能回退到技能安装目录。标准子目录为 `alaya`、`wiki`、`raw`。

## 配置兼容

有效配置在内存中由默认配置与用户配置深度合并。旧字段：

- `memory.hot_limit` 映射到 `memory.hot_zone_size`；
- `memory.cold_limit` 映射到 `memory.cold_zone_size`。

读取兼容不等于静默改写。用户文件只有通过向导显式迁移才更新，并先备份。配置迁移使用 `--migrate-config/--apply-migration`；旧 `ambient.json` 的长期偏好与未解问题使用 `--migrate-shared-memory/--apply-shared-memory-migration`，迁入 `shared/profile.json`、`shared/state.json` 和 `shared/history.json`。

统一语言由顶层 `language` 和 `persona.language_mode=global` 控制。默认休眠周期由 `knowledge.cold_after_days_default=90` 控制，运行时反推每日衰减率：

$$d=\left(\frac{s_{sleep}}{s_{wake}}\right)^{1/T}$$

默认 $s_{wake}=0.5$、$s_{sleep}=0.1$、$T=90$ 天。

## 互动负载

单角色示例：

```json
{
  "turn_id": "2026-08-08T10:00:00Z-001",
  "persona": "feynman",
  "cards_cited": ["wiki/physics/card.md"],
  "tags": ["physics"],
  "mood": "focused",
  "history": {"summary": "用户在比较两个物理解释。"},
  "shared_state": {"current_goal": "理解该主题"},
  "shared_event": {"type": "goal_changed", "summary": "目标从浏览转为深入理解"}
}
```

群组示例：

```json
{
  "group_id": "group-20260808-001",
  "participants": [
    {"persona": "feynman", "history": {"summary": "强调直觉解释"}},
    {"persona": "bi", "history": {"summary": "观察决策分歧"}}
  ],
  "cards_cited": [],
  "tags": ["decision"],
  "shared_event": {"type": "decision", "summary": "采用方案 A"}
}
```

负载必须是 JSON 对象；单角色要求 `turn_id/persona`，群组要求 `group_id/participants`。`cards_cited`、`tags` 必须是字符串数组，`history` 必须是对象。完整负载先验证，再写任何文件。

```bash
python scripts/perfume.py --level answer --kb-root <目录> --payload-file payload.json
python scripts/perfume.py --level group --kb-root <目录> --payload-file payload.json
```

`--level save` 是 `answer` 的兼容别名；`--level 1` 只做机械记录，不写语义记忆；`--level 2` 立即熏习；`--level 3` 到期检查。

## 共享档案负载

```json
{
  "fields": {
    "response_style": {
      "value": "先结论，后原因",
      "source": "user_confirmed",
      "evidence": "用户明确要求",
      "share_scope": "all_personas"
    }
  }
}
```

身份字段必须 `source=user_stated` 或 `user_confirmed`。冲突替换需 `replace_confirmed: true`。敏感字段还需命令行 `--allow-sensitive`，且前提是用户主动要求。秘密模式会被拒绝。

## 导入事务

导入分为计划与提交：

1. 扫描并验证来源；
2. 并行读取/提取；
3. 计算卡片身份、内容哈希、原文目标和冲突后缀；
4. `--dry-run` 到此结束，知识库零写入；
5. 获取导入锁，串行复制原文并校验哈希；
6. 原子写卡片；
7. 重扫类别并发布完整总索引；
8. 提醒类别描述策略并运行到期熏习。

`source_file` 只指向 `raw/` 中已验证副本，`source_path` 只指向未复制的外部原路径。

## 索引状态

- 当前内容清单：类别、相对路径、内容摘要；随索引发布更新。
- 描述基线：最后一次智能体精化描述时的清单。
- 描述到期：当前清单与描述基线不同，且达到自适应数量阈值或 3 天等待上限。

发布不硬编码类别数。总索引集合必须与磁盘有效类别集合相等；减少默认阻止，需 `--confirm-removals`。

## 角色回收

`persona_manager.py delete` 显示并移动三类私有文件：角色 JSON、角色档案、角色私有历史。删除默认角色必须指定存在的替代角色。共享记忆中的引用只报告。`restore` 可恢复；`purge` 需要回收项内角色键二次确认。

## BI 有界状态

`bi_state.json` 保存六领域当前观察，每个稳定标识覆盖更新；`bi_notes.json` 只在观察发生变化时追加。限制为每域 20 条、总事件 200 条、180 天和 512KB，达到任一上限即裁剪最旧事件。

## 返回码约定

| 返回码 | 含义 |
|---|---|
| `0` | 成功或检查通过 |
| `1` | 检查完成但发现需要人工处理的问题 |
| `2` | 参数、配置、路径或执行错误 |

## 脚本索引

| 脚本 | 作用 | 默认写入 |
|---|---|---|
| `setup_wizard.py` | 初始化/迁移知识库 | 是，显式目录 |
| `batch_import.py` | 批量导入与预览 | 预览否，确认后是 |
| `import_paper.py` | 单篇信息/完整导入 | `info` 否，`full` 是 |
| `post_process.py` | 语义卡后处理 | 预览否，确认后是 |
| `build_index.py` | 动态完整索引 | `--check-only` 否 |
| `fix_links.py` | 链接审计与唯一修复 | 默认否 |
| `health_check.py` | 综合健康检查 | 否 |
| `persona_manager.py` | 角色复制/回收/恢复 | 视子命令 |
| `memory_manager.py` | 用户档案查看/设置/忘记 | `show` 否 |
| `bi_observer.py` | BI 状态预览/提交 | 默认否 |
| `perfume.py` | 互动提交与熏习 | 是 |
| `import_quality_review.py` | 类别质量检查 | 默认否 |
| `verify_installation.py` | 安装结构检查 | 否 |
| `build_skill_full.py` | 可选单文件兼容包 | 检查否，构建是 |
