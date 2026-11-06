---
title: "Attention-Mechanisms"
type: survey
created: 2026-06-02
tags: [deep-learning, attention, transformer]
seed_type: REFINED
created_by: system
strength: 0.65
last_activated: 2026-06-02
activation_count: 0
description: "注意力机制允许模型在生成输出时动态关注输入序列中最相关的部分，是现代深度学习中最重要的基础技术之一。"
---

# 注意力机制

> 注意力机制（Attention Mechanism）允许模型在生成输出时动态关注输入序列中最相关的部分，是现代深度学习中最重要的基础技术之一。其核心思想来源于人类视觉注意力——我们并非平等地处理所有信息，而是聚焦于关键区域。

## Q-K-V 框架

注意力机制的核心是查询-键-值（Query-Key-Value, QKV）框架，灵感来源于信息检索系统：

- **Q（Query）**：当前关注点的表示，询问"我需要什么信息"
- **K（Key）**：输入序列中各位置的标识，回答"我包含什么信息"
- **V（Value）**：输入序列中各位置的实际内容，回答"我携带什么信息"

给定查询 $Q \in \mathbb{R}^{d_k}$、键 $K \in \mathbb{R}^{n \times d_k}$、值 $V \in \mathbb{R}^{n \times d_v}$，注意力输出的计算流程为：

1. Q 与每个 K 计算相似度得分
2. 得分经 softmax 归一化为权重
3. 权重加权聚合对应的 V

## 缩放点积注意力（Scaled Dot-Product Attention）

$$ \text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V $$

### 计算步骤详解

1. **点积**：$S = QK^T$ — 计算查询与所有键的相似度，结果 $S_{ij}$ 表示位置 $i$ 的查询对位置 $j$ 的关注强度
2. **缩放**：$\frac{S}{\sqrt{d_k}}$ — 当 $d_k$ 较大时，点积的方差随之增大，导致 softmax 梯度趋近于零。缩放因子 $1/\sqrt{d_k}$ 使方差稳定在 1 附近：
   $$\text{Var}(Q \cdot K) = d_k \implies \text{Var}\left(\frac{Q \cdot K}{\sqrt{d_k}}\right) = 1$$
3. **Softmax 归一化**：$\alpha_{ij} = \frac{\exp(S_{ij} / \sqrt{d_k})}{\sum_k \exp(S_{ik} / \sqrt{d_k})}$ — 将得分转换为概率分布，使注意力权重和为 1
4. **加权求和**：$\text{output}_i = \sum_j \alpha_{ij} V_j$ — 根据权重聚合值向量

### Softmax 的温度效应

注意力中的 softmax 本质上有一个隐含的"温度"参数：当得分差异大时，softmax 趋向于 one-hot 选择（hard attention）；当得分差异小时，趋向于均匀分布（diffuse attention）。缩放因子正是通过调节得分的尺度来控制注意力的集中程度。

## 注意力 vs. RNN 对比

| 特性 | 注意力机制 | RNN（LSTM/GRU） |
|:--|:--|:--|
| **计算方式** | 并行计算所有位置 | 顺序计算，每个时间步依赖上一步 |
| **感受野** | 全局，一步到位 | 局部递推，远距离需多步传播 |
| **长程依赖** | 天然捕获 O(1) 跳转 | 需克服梯度消失/爆炸 |
| **时间复杂度** | $O(n^2)$ | $O(n)$ |
| **空间复杂度** | $O(n^2)$（需存储注意力矩阵） | $O(n)$ |
| **可解释性** | 注意力权重可直接可视化 | 隐状态较难解释 |
| **外推能力** | 需位置编码辅助 | 天然支持变长序列 |

## 注意力机制的变体

| 类型 | 公式 | 特点 |
|:--|:--|:--|
| **加性注意力** | $a(Q,K) = v^T \tanh(WQ + UK)$ | Bahdanau 风格，适合处理不等长序列 |
| **点积注意力** | $a(Q,K) = Q^T K$ | 计算高效，实践中更常用 |
| **缩放点积注意力** | $a(Q,K) = Q^T K / \sqrt{d_k}$ | 防止梯度消失，Transformer 标准选择 |
| **双线性注意力** | $a(Q,K) = Q^T W K$ | 通过可学习的 $W$ 增加表达能力 |
| **余弦注意力** | $a(Q,K) = \frac{Q^T K}{\|Q\|\|K\|}$ | 仅考虑方向相似性，忽略模长 |

## 跨分类链接

- [[../philosophy/Consciousness-and-Attention]] — 注意力的哲学根基：作意心所中"导向"功能对应 QKV 中的 Query，Softmax 权重对应选择性注意力强度

## References

- Bahdanau, D., Cho, K., & Bengio, Y. (2015). *Neural Machine Translation by Jointly Learning to Align and Translate*. ICLR. [https://arxiv.org/abs/1409.0473](https://arxiv.org/abs/1409.0473)
- Vaswani, A., et al. (2017). *Attention Is All You Need*. NeurIPS. [https://arxiv.org/abs/1706.03762](https://arxiv.org/abs/1706.03762)
- Luong, M.-T., Pham, H., & Manning, C. D. (2015). *Effective Approaches to Attention-based Neural Machine Translation*. EMNLP. [https://arxiv.org/abs/1508.04025](https://arxiv.org/abs/1508.04025)
