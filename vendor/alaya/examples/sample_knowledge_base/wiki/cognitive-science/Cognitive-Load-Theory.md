---
title: "Cognitive-Load-Theory"
type: survey
created: 2026-06-02
tags: [cognitive-science, attention, deep-learning]
seed_type: REFINED
created_by: system
strength: 0.6
last_activated: 2026-06-02
activation_count: 0
description: "认知负荷理论关注学习过程中工作记忆的负荷管理，为教学设计提供认知科学依据。"
---

# 认知负荷理论

> 认知负荷理论（Cognitive Load Theory, CLT）由 John Sweller（1988）提出，基于人类认知架构的有限工作记忆容量，为教学设计和学习材料组织提供了系统性的理论指导。其核心理念是：**教学设计应当尊重工作记忆的容量约束**。

## 理论基础：人类认知架构

CLT 建立在 Baddeley 工作记忆模型和 Atkinson-Shiffrin 记忆模型的基础之上：

| 认知结构 | 容量 | 持久性 | 在 CLT 中的角色 |
|:--|:--:|:--:|:--|
| **工作记忆** | 极有限（2–4 个信息块） | 数秒 | 所有 conscious 处理发生的场所 |
| **长时记忆** | 近乎无限 | 数年～终生 | 以图式（schema）形式存储知识 |
| **图式（Schema）** | — | — | 将零散信息组织为结构化知识单元 |

**图式理论**：学习本质上是构建和自动化图式的过程。一旦某个图式被充分自动化（如阅读、开车），它在工作记忆中只占极少的处理资源——这就是专家与新手在认知效率上的根本差异。

## 三种认知负荷

Sweller 将认知负荷分为三种类型，它们叠加在工作记忆的有限容量上：

```
总认知负荷 = 内在负荷 + 外在负荷 + 关联负荷
                        ≤ 工作记忆容量
```

### 1. 内在负荷（Intrinsic Cognitive Load）

由学习材料本身的复杂程度和学生的先前知识水平共同决定。

$$ \text{内在负荷} \propto \text{元素交互性（element interactivity）} $$

- **高元素交互性材料**：各元素必须同时在工作记忆中处理才能理解——如解数学方程、理解程序设计中的递归
- **低元素交互性材料**：元素可以逐个独立学习——如记忆外语单词、背诵事实性知识

**设计启示**：内在负荷不能直接减少（材料复杂度是固有的），但可以通过以下方式管理：
- 先学习子元素，再整合
- 使用"从简单到复杂"的渐进式序列
- 对初学者先行提供部分解决问题（worked example）

### 2. 外在负荷（Extraneous Cognitive Load）

由**教学设计本身**引入的不必要认知负荷——与学习目标无关，纯粹由材料的呈现方式造成。

| 负荷来源 | 说明 | 示例 |
|:--|:--|:--|
| **注意力分散效应** | 相关信息在空间或时间上分离 | 图解与文字说明分页展示 |
| **冗余效应** | 同一信息以多种形式重复呈现 | 幻灯片上读文字 + 演讲者同时念相同文字 |
| **分裂注意力效应** | 学生需在多个信息源之间切换视线 | 教科书上的图与文字描述分隔两页 |
| **格式效应** | 不恰当的媒体形式 | 用文本描述一个复杂的空间关系，而非用图示 |

**设计启示**：外在负荷**可以通过优化教学设计来降低**——这是 CLT 对教育实践最有价值的贡献。

### 3. 关联负荷（Germane Cognitive Load）

与学习目标**直接相关的有效认知负荷**——用于图式构建和自动化处理的认知资源投入。

- 关联负荷不是"第三种"独立的负荷，而是**被释放出的工作记忆资源**——原本被外在负荷占用的资源，如果能节省下来，就可以分配给关联负荷
- **关联负荷的增加意味着更深层的学习**：比较与对比、自我解释、精加工


| 负荷类型 | 来源 | 可控性 | 设计目标 |
|:--|:--|:--:|:--|
| **内在负荷** | 材料复杂度 × 学习者知识水平 | 间接管理 | 分解 + 渐进 |
| **外在负荷** | 教学设计质量 | ✅ 直接降低 | 最小化 |
| **关联负荷** | 学习者投入程度 | ✅ 直接提升 | 最大化 |

## 10 个 CLT 教学设计效应

Sweller 及其合作者通过大量实验验证了以下效应：

| # | 效应 | 核心原则 |
|:--|:--|:--|
| 1 | **Worked Example Effect** | 对初学者，研究已解决的示例比解决问题本身更有效 |
| 2 | **Completion Effect** | 提供部分解决方案，要求学习者补全剩余部分 |
| 3 | **Split-Attention Effect** | 将相互参照的信息源在物理上整合（图+文合一） |
| 4 | **Redundancy Effect** | 删除不必要的重复信息 |
| 5 | **Modality Effect** | 视觉信息用图形 + 听觉信息用语音（双通道原理） |
| 6 | **Expertise Reversal Effect** | 对专家有效的设计（如 worked example）对新手有效，随知识增长逐渐失效甚至有害 |
| 7 | **Guidance Fading Effect** | 随学习者知识增长逐步撤除教学支架 |
| 8 | **Transient Information Effect** | 避免仅通过短暂呈现的信息传达核心内容（如纯口头讲解复杂原理） |
| 9 | **Element Interactivity Effect** | 不同效应的有效性取决于元素交互性的高低 |
| 10 | **Isolated-Interacting Elements Effect** | 先将高交互性材料分解为孤立元素，再逐步整合 |

## CLT 与深度学习的关系

认知负荷理论对深度学习领域有直接的指导意义——尤其是针对 Transformer 和注意力机制的类比：

1. **工作记忆 ≈ Transformer 的上下文窗口** — 有限容量是硬约束，超出窗口的信息无法被处理
2. **内在负荷 ≈ 输入序列的语义复杂度** — 长序列/高信息密度输入对注意力机制的压力更大
3. **外在负荷 ≈ 冗余/不相关的输入内容** — 噪声 token 会占用注意力权重资源
4. **关联负荷 ≈ 对关键 token 的注意力分配** — 好的注意力机制（如稀疏注意力）本质上是在做认知负荷优化

## References

- Sweller, J. (1988). *Cognitive load during problem solving: Effects on learning*. Cognitive Science, 12(2), 257–285.
- Sweller, J., Van Merriënboer, J. J. G., & Paas, F. (2019). *Cognitive Architecture and Instructional Design: 20 Years Later*. Educational Psychology Review, 31(2), 261–292.
- Paas, F., Renkl, A., & Sweller, J. (2003). *Cognitive Load Theory and Instructional Design: Recent Developments*. Educational Psychologist, 38(1), 1–4.
- Kirschner, P. A., Sweller, J., & Clark, R. E. (2006). *Why Minimal Guidance During Instruction Does Not Work: An Analysis of the Failure of Constructivist, Discovery, Problem-Based, Experiential, and Inquiry-Based Teaching*. Educational Psychologist, 41(2), 75–86.
