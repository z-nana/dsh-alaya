---
title: "Transformer-Architecture"
type: survey
created: 2026-06-02
tags: [deep-learning, transformer, attention, neural-networks]
seed_type: REFINED
created_by: system
strength: 0.7
last_activated: 2026-06-02
activation_count: 0
description: "Transformer 是 Vaswani et al. (2017) 提出的序列建模架构，完全基于注意力机制，摒弃了循环和卷积结构，成为现代深度学习的基础范式。"
---

# Transformer 架构

> Transformer 是 Vaswani et al. (2017) 在《Attention Is All You Need》中提出的序列建模架构，完全基于注意力机制，摒弃了循环和卷积结构，成为现代深度学习的基础范式。

## 核心组件

### 1. 自注意力机制（Self-Attention）

自注意力通过计算序列中每个位置与其他所有位置的注意力权重，捕获全局依赖关系：

$$ \text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V $$

- **Q（Query）**：查询向量，表示当前 token 希望关注什么
- **K（Key）**：键向量，表示每个 token 被关注的依据
- **V（Value）**：值向量，表示每个 token 的实际信息
- **缩放因子 $1/\sqrt{d_k}$**：防止点积过大导致 softmax 梯度消失

**计算流程**：输入序列经线性变换得到 Q、K、V → Q 与 K 点积计算相似度 → 缩放后经 softmax 归一化为权重 → 加权聚合 V。

### 2. 多头注意力（Multi-Head Attention）

将自注意力拆分为 $h$ 个独立的头，每个头在不同表示子空间上学习注意力分布：

$$ \text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h)W^O $$

其中 $\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$。

多头机制允许模型同时关注不同位置的、不同语义层面的信息（如语法关系、语义相似性、指代关系等）。标准 Transformer 使用 $h=8$ 个头。

### 3. 位置编码（Positional Encoding）

由于自注意力本身不具备序列顺序感知能力，Transformer 通过位置编码注入位置信息：

$$ PE_{(pos, 2i)} = \sin(pos / 10000^{2i/d_{\text{model}}}) $$
$$ PE_{(pos, 2i+1)} = \cos(pos / 10000^{2i/d_{\text{model}}}) $$

- 使用正弦/余弦函数确保不同位置之间的相对关系可被模型学习
- 可处理比训练时更长的序列（外推能力）
- 后续工作发展出可学习位置编码、旋转位置编码（RoPE）、AliBi 等变体

### 4. 前馈网络（Feed-Forward Network, FFN）

每个 Transformer 层中包含一个两层的全连接前馈网络：

$$ \text{FFN}(x) = \max(0, xW_1 + b_1)W_2 + b_2 $$

- 中间隐藏层维度通常为 $4 \times d_{\text{model}}$（如 $d_{\text{model}}=512$, $d_{ff}=2048$）
- 使用 ReLU 激活函数（后续改进包括 GELU、SwiGLU 等）
- 每个位置独立应用相同的 FFN，参数共享

## 架构总览

Encoder-Decoder 结构：

```
输入序列
    ↓
[位置编码]
    ↓
┌─────────────────────┐      ┌─────────────────────┐
│   Encoder Layer ×N  │      │   Decoder Layer ×N  │
│                     │      │                     │
│  自注意力 (多头)      │      │  掩码自注意力 (多头)   │
│      ↓              │      │      ↓              │
│  残差 + 层归一化      │      │  残差 + 层归一化      │
│      ↓              │      │      ↓              │
│  前馈网络 (FFN)      │      │  交叉注意力 (多头)    │
│      ↓              │      │      ↓              │
│  残差 + 层归一化      │      │  残差 + 层归一化      │
│      ↓              │      │      ↓              │
│      →→→→→→→→→→→→→→→│←────│  前馈网络 (FFN)      │
└─────────────────────┘      │      ↓              │
                             │  残差 + 层归一化      │
                             └─────────────────────┘
                                    ↓
                              输出 (Softmax)
```

每个子层（自注意力、FFN）之后都采用**残差连接**和**层归一化**：

$$ \text{output} = \text{LayerNorm}(x + \text{Sublayer}(x)) $$

## 关键应用领域

| 领域 | 代表性工作 | 说明 |
|:--|:--|:--|
| **机器翻译** | Transformer (2017), mBART, M2M-100 | Transformer 最初的目标任务，WMT 基准长期霸榜 |
| **文本摘要** | PEGASUS, BART, T5 | 生成式与抽取式摘要均受益于长程依赖捕获能力 |
| **代码生成** | Codex, AlphaCode, CodeGemma | 利用自注意力建模代码中跨行的 token 依赖 |
| **蛋白质结构预测** | AlphaFold2 (Evoformer), ESM-2 | 将氨基酸远程相互作用建模为注意力权重 |
| **多模态** | ViT, CLIP, DALL·E | 将图像分割为 patch 序列，应用标准 Transformer |
| **时序预测** | Informer, Autoformer, PatchTST | 将时间序列转化为 token 序列进行建模 |

## 影响与意义

Transformer 的提出标志着深度学习从 RNN/CNN 主导进入 **Attention 范式**。其核心贡献在于：

1. **并行计算**：摆脱 RNN 的顺序依赖，可充分利用 GPU 并行能力
2. **长程依赖**：自注意力的全局感受野解决了 RNN 的梯度消失问题
3. **规模扩展**：Transformer 架构在更大数据和更大模型下持续提升（Scaling Law）
4. **跨模态统一**：以序列为媒介，可统一处理文本、图像、语音、代码、分子结构等

## 跨分类链接

- [[../philosophy/Consciousness-and-Attention]] — 注意力的哲学根基：作意心所、八识理论与"你注意什么，你就成为什么"

## References

- Vaswani, A., et al. (2017). *Attention Is All You Need*. NeurIPS. [https://arxiv.org/abs/1706.03762](https://arxiv.org/abs/1706.03762)
- Devlin, J., et al. (2019). *BERT: Pre-training of Deep Bidirectional Transformers*. NAACL. [https://arxiv.org/abs/1810.04805](https://arxiv.org/abs/1810.04805)
- Brown, T. B., et al. (2020). *Language Models are Few-Shot Learners*. NeurIPS. [https://arxiv.org/abs/2005.14165](https://arxiv.org/abs/2005.14165)
- Jumper, J., et al. (2021). *Highly accurate protein structure prediction with AlphaFold*. Nature. [https://doi.org/10.1038/s41586-021-03819-2](https://doi.org/10.1038/s41586-021-03819-2)
