---
title: "Neural-Networks"
type: tutorial
created: 2026-06-02
tags: [deep-learning, neural-networks, backpropagation, optimization]
seed_type: REFINED
created_by: system
strength: 0.6
last_activated: 2026-06-02
activation_count: 0
description: "神经网络是深度学习的基础模型，通过多层非线性变换学习数据的层次化表示。"
---

# 神经网络基础

> 人工神经网络（Artificial Neural Network, ANN）受生物神经元启发，通过多层可微函数的组合逼近任意复杂映射。它是深度学习大厦的基石。

## 1. 感知机（Perceptron）

感知机是神经网络的基本计算单元，由 Rosenblatt (1958) 提出：

$$ y = \phi\left(\sum_{i=1}^{n} w_i x_i + b\right) $$

其中 $\phi$ 为阶跃激活函数：

$$ \phi(z) = \begin{cases} 1 & \text{if } z \geq 0 \\ 0 & \text{if } z < 0 \end{cases} $$

**关键局限**：单层感知机只能解决线性可分问题（如 AND、OR），无法处理 XOR 等非线性问题 — 这一发现直接导致了 1970 年代的第一次 AI 寒冬。

## 2. 激活函数（Activation Functions）

激活函数引入非线性，使神经网络能够逼近任意复杂函数。

### Sigmoid

$$ \sigma(x) = \frac{1}{1 + e^{-x}} $$

- 输出范围：(0, 1)，适合作为二分类概率输出
- **缺点**：饱和区梯度趋近于零，导致梯度消失；输出非零中心，梯度更新呈锯齿状

### Tanh（双曲正切）

$$ \tanh(x) = \frac{e^x - e^{-x}}{e^x + e^{-x}} = 2\sigma(2x) - 1 $$

- 输出范围：(-1, 1)，零中心对称
- 缓解了非零中心问题，但饱和区仍存在梯度消失

### ReLU（Rectified Linear Unit）

$$ \text{ReLU}(x) = \max(0, x) $$

- 正区间梯度恒为 1，有效缓解梯度消失
- 计算简单，仅需一次比较
- **Dying ReLU 问题**：负区间梯度为 0，部分神经元可能永久失活
- 变体：Leaky ReLU（$\max(\alpha x, x)$）、ELU、GELU 等

| 函数 | 输出范围 | 梯度特性 | 常见用途 |
|:--|:--|:--|:--|
| Sigmoid | (0, 1) | 易饱和 | 二分类输出层 |
| Tanh | (-1, 1) | 零中心，仍饱和 | RNN、GAN 生成器 |
| ReLU | [0, ∞) | 正区间常数梯度 | 隐层默认选择 |

## 3. 反向传播（Backpropagation）

反向传播是训练神经网络的核心算法，通过链式法则从输出层向输入层逐层计算梯度：

**算法流程**：

1. **前向传播**：输入 $x$ 经过各层计算得到输出 $\hat{y}$
2. **计算损失**：$\mathcal{L}(\hat{y}, y)$ — 度量预测与真实值的差异
3. **反向求导**：从输出层开始，沿计算图反向应用链式法则：

$$ \frac{\partial \mathcal{L}}{\partial w_{ij}^{(l)}} = \frac{\partial \mathcal{L}}{\partial a_j^{(l)}} \cdot \frac{\partial a_j^{(l)}}{\partial z_j^{(l)}} \cdot \frac{\partial z_j^{(l)}}{\partial w_{ij}^{(l)}} $$

其中 $z_j^{(l)} = \sum_i w_{ij}^{(l)} a_i^{(l-1)} + b_j^{(l)}$，$a_j^{(l)} = \phi(z_j^{(l)})$

4. **参数更新**：使用梯度下降更新权重

## 4. 梯度下降（Gradient Descent）

通过沿损失函数梯度的负方向更新参数，最小化损失：

$$ \theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t) $$

其中 $\eta$ 为学习率。

### 主要变体

| 算法 | 更新策略 | 特点 |
|:--|:--|:--|
| **Batch GD** | 使用全部数据计算梯度 | 稳定但计算慢，无法在线学习 |
| **SGD** | 每次使用一个样本 | 计算快、可在线学习，但梯度噪声大 |
| **Mini-batch GD** | 每次使用一个小批量 | 折中方案，实践中默认选择 |
| **Momentum** | 累计历史梯度方向 | 加速收敛，抑制振荡 |
| **Adam** | 自适应学习率 + Momentum | 最常用的优化器，对超参数鲁棒 |

### 关键挑战与应对

- **学习率选择**：过大会发散，过小收敛慢 → 学习率调度（Cosine Annealing、Warmup）
- **局部极小值**：高维损失面中鞍点比局部极小更常见 → 动量和自适应方法有效
- **梯度消失/爆炸**：深层网络中梯度随层数指数衰减或增长 → Batch Normalization、残差连接

## References

- Rosenblatt, F. (1958). *The Perceptron: A Probabilistic Model for Information Storage and Organization in the Brain*. Psychological Review.
- Rumelhart, D. E., Hinton, G. E., & Williams, R. J. (1986). *Learning representations by back-propagating errors*. Nature. [https://doi.org/10.1038/323533a0](https://doi.org/10.1038/323533a0)
- Nair, V., & Hinton, G. E. (2010). *Rectified Linear Units Improve Restricted Boltzmann Machines*. ICML.
- Kingma, D. P., & Ba, J. (2015). *Adam: A Method for Stochastic Optimization*. ICLR. [https://arxiv.org/abs/1412.6980](https://arxiv.org/abs/1412.6980)
