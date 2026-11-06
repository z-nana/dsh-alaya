---
name: alaya-memory
description: 管理 Alaya 的角色私有记忆、跨角色共享记忆、用户偏好档案和 BI 观察记录。用于用户要求记住、忘记、查看偏好，或角色回答和群组讨论后提交记忆。
---

# Alaya 记忆

## 记忆分层

```text
alaya/memory/
├─ <persona>_memory.json       角色私有记忆：该角色自己的互动事实
├─ ambient.json                机械环境信号：近期标签、情绪和活跃角色
├─ shared/
│  ├─ profile.json             经用户确认的稳定偏好与固定特征
│  ├─ state.json               跨角色当前有效状态，有容量上限
│  ├─ history.json             重要变化历史，有时间和数量上限
│  └─ INDEX.md                 派生的人类可读摘要
├─ bi_state.json               BI 当前观察结论
└─ bi_notes.json               BI 有界变化事件
```

`ambient.json` 是角色共享的轻量环境，不是 BI（观察员角色）的长篇笔记。BI 负责观察交互模式；共享记忆负责给多个角色复用已经确认的信息。

## 固定保存时机

不要等待“会话快结束”这种难以稳定识别的时机：

- 每次角色回答完成后，固定提交一次。
- 每次群组讨论完成汇总后，固定提交一次。
- 用户明确说“记住”“保存这个”“以后都这样”时，把已确认内容加入本轮提交。
- 没有得到许可的敏感信息、不稳定猜测和整段原对话不保存。

持久开关是 `memory.semantic_memory_enabled`。关闭时或本轮负载含 `no_semantic_memory: true` 时，只执行知识引用、亲和度和即时环境等机械维护，不写角色私有语义记忆及共享语义记忆。

提交入口：

```bash
python scripts/perfume.py --level answer --kb-root <目录> --payload-file <payload.json>
python scripts/perfume.py --level group --kb-root <目录> --payload-file <payload.json>
```

单角色用唯一 `turn_id`，群组用唯一 `group_id`。重试同一标识不得重复写入。`history` 写对应角色私有记忆；`shared_state` 写当前跨角色状态；`shared_event` 写一次真正有意义的变化。先验证整个 JSON，再开始任何写入。

## 当前状态与历史

- 当前状态只保留仍然有效、会影响后续服务的事实，按主题覆盖更新并设置容量上限。
- 变化历史记录“什么从什么变成什么、何时、依据是什么”，达到数量、时长或文件体积上限后裁剪。
- 已失效的当前状态应删除或替换，而不是一直追加。
- `INDEX.md` 是派生摘要，可重建；JSON 才是数据源。

## 用户偏好档案

初始化后可询问一次：“为了以后更贴合你的习惯，是否现在记录称呼、语言、回答风格、兴趣和你愿意明确提供的基本信息？”给出“现在、以后、不要再问”。选择“以后”延迟 30 天，选择“不要再问”不再主动打扰，除非用户重置。

允许自动提取候选的内容仅限低风险偏好，例如用户明确反复表达的语言、长度、格式或兴趣；写入前仍应让用户确认。年龄、性别、教育、职业等身份字段只能来自用户明确陈述，不能推断。健康、宗教、政治、财务、精确地址等敏感项必须用户明确要求且单独确认。密钥、令牌、银行卡号等秘密永不保存。

```bash
python scripts/memory_manager.py --kb-root <目录> show
python scripts/memory_manager.py --kb-root <目录> set --payload-file <profile.json>
python scripts/memory_manager.py --kb-root <目录> forget <字段>
python scripts/memory_manager.py --kb-root <目录> invitation later
```

新值与已确认值冲突时先询问，只有用户确认替换后才在负载中使用 `replace_confirmed: true`。忘记字段时同时移除该字段的变化历史。

## BI 观察

BI 观察至少覆盖六方面：需求与目标、决策习惯、表达偏好、知识兴趣、角色协作模式、风险与未解决问题。

```bash
python scripts/bi_observer.py --kb-root <目录>
python scripts/bi_observer.py --kb-root <目录> --write
```

默认只读预览；`--write` 才更新。当前状态采用稳定标识和覆盖更新，不重复累计同一句；历史只在状态真正变化时追加，并按每域、总数、时间和文件大小裁剪。旧版列表需要迁移时显式使用 `--migrate`，先备份再转换。
