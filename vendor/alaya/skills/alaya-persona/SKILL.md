---
name: alaya-persona
description: 使用和管理 Alaya 多角色，包括选择、创建、复制、切换、统一语言、群组讨论以及可恢复地移除角色。用于用户明确指定角色、要求多角色讨论或管理角色时。
---

# Alaya 角色

## 角色数据位置

角色配置保存在知识库的 `alaya/manas/`，角色档案和私有历史保存在 `alaya/memory/`。技能内置角色只是安装时可选的种子；一旦复制进用户知识库，后续以用户版本为准，技能升级不能覆盖。

列出角色：

```bash
python scripts/persona_manager.py --kb-root <目录> list
```

角色名会转换为安全键，只允许落在 `manas/` 内；任何路径穿越形式必须拒绝。

## 统一语言

默认采用 `persona.language_mode=global（统一）`，所有角色读取 `alaya/config.json` 顶层 `language`。用户要求所有角色切换语言时只改全局字段，不改每个角色。只有明确要求角色分别使用不同语言时，才改为 `individual（分别设置）` 并读取角色自己的语言。

## 使用角色

1. 读取角色 JSON 和角色档案。
2. 按角色的思维方式和表达风格回答，但不得突破安全、事实和用户指令边界。
3. 只检索与问题和角色兴趣相关的知识卡。
4. 回答完成后，用唯一 `turn_id` 调用 `perfume.py --level answer` 固定提交一次。
5. 提交失败不撤回答；清楚告知记忆写入失败。

不要把“角色化”变成夸张表演。角色应影响视角、提问方式和解释重点，而不是伪造身份或事实。

## 群组讨论

群组讨论按四步进行：

1. 确认参与角色和问题。
2. 每个角色独立给出短观点，避免后一个只附和前一个。
3. 指出一致、分歧和各自依据。
4. 给出主持人汇总；汇总完成后用唯一 `group_id` 调用 `perfume.py --level group`。

群组提交中每个 `participant` 可有自己的 `history`；共享结论放 `shared_state`，真正的决策变化放 `shared_event`。同一 `group_id` 重试不得重复增加亲和度或历史。

## 复制与移除

```bash
python scripts/persona_manager.py --kb-root <目录> clone <原角色> <新角色>
python scripts/persona_manager.py --kb-root <目录> delete <角色> --yes
python scripts/persona_manager.py --kb-root <目录> restore <回收项>
```

- 复制前校验源存在、目标不存在；角色配置、档案和私有历史作为一个提交处理。
- 移除默认角色时必须先给 `--new-default <替代角色>`。
- 删除是可恢复移动：角色配置、档案和私有历史进入知识库内回收区；共享记忆只报告引用，不擅自删除跨角色数据。
- 永久清理必须显式执行 `purge`，并用 `--confirm <角色键>` 二次确认。不能把临时文件、锁或整个知识库目录作为删除目标。

## 亲和度

亲和度只反映角色在真实互动中的共同出现，回答或群组提交时由唯一事件标识幂等更新；每日熏习按实际经过天数衰减。同一事件重放、失败重试和同日重复维护不得重复计数。
