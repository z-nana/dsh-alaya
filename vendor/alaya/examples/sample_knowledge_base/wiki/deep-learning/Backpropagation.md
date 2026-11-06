---
title: "Backpropagation"
type: tutorial
created: 2026-06-02
tags: [deep-learning, neural-networks, backpropagation, optimization]
seed_type: REFINED
created_by: system
strength: 0.55
last_activated: 2026-06-02
activation_count: 0
description: "反向传播是训练神经网络的核心算法，通过链式法则计算梯度并逐层更新参数。"
---

# 反向传播

> 反向传播（Backpropagation）是训练神经网络的核心算法，通过链式法则从输出层向输入层逐层计算损失函数对各参数的梯度，是实现梯度下降的前提。它本质上是自动微分中反向模式（reverse-mode AD）在神经网络上的特例。

## 链式法则（Chain Rule）

反向传播的数学基础是多变量微积分的链式法则。对于复合函数 $f(g(x))$：

$$ \frac{df}{dx} = \frac{df}{dg} \cdot \frac{dg}{dx} $$

在神经网络中，损失 $\mathcal{L}$ 是各层参数的嵌套复合函数，梯度需从输出层开始逐层回传：

$$ \frac{\partial \mathcal{L}}{\partial w_{ij}^{(l)}} = \frac{\partial \mathcal{L}}{\partial a_j^{(l)}} \cdot \frac{\partial a_j^{(l)}}{\partial z_j^{(l)}} \cdot \frac{\partial z_j^{(l)}}{\partial w_{ij}^{(l)}} $$

其中 $z_j^{(l)} = \sum_i w_{ij}^{(l)} a_i^{(l-1)} + b_j^{(l)}$，$a_j^{(l)} = \phi(z_j^{(l)})$，$\phi$ 为激活函数。

## 计算图（Computational Graph）

计算图是有向无环图（DAG），节点表示变量或操作，边表示数据流。反向传播在计算图上执行两步：

### 前向 Pass（Forward Pass）

从输入到输出，按拓扑序计算每个节点的值并缓存中间结果：

```
输入 x → 线性变换 z = Wx + b → 激活 a = ReLU(z) → ... → 损失 ℓ
缓存:   x, W, b                   z, ReLU 的输入           ℓ
```

### 反向 Pass（Backward Pass）

从输出到输入，应用链式法则逐节点计算梯度：

```
dℓ/dℓ = 1
  → dℓ/dz = dℓ/da · da/dz = dℓ/da · ReLU'(z)
    → dℓ/dW = dℓ/dz · dz/dW = dℓ/dz · x^T
    → dℓ/db = dℓ/dz · dz/db = dℓ/dz
    → dℓ/dx = dℓ/dz · dz/dx = W^T · dℓ/dz
```

**关键**：前向 Pass 缓存的中间变量（如激活层输入 $z$）被反向 Pass 用来计算局部梯度。

## 梯度局部计算

### 常见操作的局部梯度

| 操作 | 前向 | 局部梯度（对输入） |
|:--|:--|:--|
| 线性变换 | $z = Wx + b$ | $\partial z / \partial x = W^T$，$\partial z / \partial W = x^T$ |
| ReLU | $a = \max(0, z)$ | $\partial a / \partial z = \mathbb{1}[z > 0]$ |
| Sigmoid | $\sigma = 1/(1+e^{-z})$ | $\partial \sigma / \partial z = \sigma(1-\sigma)$ |
| Tanh | $\tanh(z)$ | $\partial / \partial z = 1 - \tanh^2(z)$ |
| Softmax + CrossEntropy | $\hat{y}_i = e^{z_i}/\sum e^{z_j}$ | $\partial \mathcal{L} / \partial z_i = \hat{y}_i - y_i$ |

### 激活函数梯度详解

**ReLU 梯度**：
$$ \frac{\partial \text{ReLU}}{\partial z} = \begin{cases} 1 & z > 0 \\ 0 & z \leq 0 \end{cases} $$
- 正区间的梯度恒为 1，不会衰减，是解决梯度消失的关键
- 负区间梯度为 0，导致 Dying ReLU 问题

**Sigmoid 梯度**：
$$ \sigma'(z) = \sigma(z)(1 - \sigma(z)) $$
- 当 $|\sigma(z)|$ 接近 0 或 1 时，梯度趋近于 0
- 最大值在 $\sigma(0) = 0.5$ 处，仅为 0.25

**Tanh 梯度**：
$$ \tanh'(z) = 1 - \tanh^2(z) $$
- 在 $z=0$ 处最大为 1，饱和区趋近于 0
- 输出零中心，梯度更新方向更稳定

## 梯度消失与梯度爆炸

### 梯度消失（Vanishing Gradients）

深层网络中，链式法则的乘积效应使梯度指数衰减：

$$ \frac{\partial \mathcal{L}}{\partial w^{(1)}} = \prod_{l=1}^{L} \left( W^{(l)} \cdot \phi'(z^{(l)}) \right) \cdot \frac{\partial \mathcal{L}}{\partial a^{(L)}} $$

当 $\|W^{(l)} \cdot \phi'(z^{(l)})\| < 1$ 时，连乘趋于 0，浅层参数无法更新。

**解决方案**：ReLU 系列激活函数、Batch Normalization、残差连接（Skip Connection）。

### 梯度爆炸（Exploding Gradients）

当 $\|W^{(l)} \cdot \phi'(z^{(l)})\| > 1$ 时，连乘趋于无穷，参数更新震荡发散。

**解决方案**：梯度裁剪（Gradient Clipping）、权重初始化（Xavier / He Initialization）。

## 反向传播的伪代码

```
# 前向 pass
activations = [x]
for layer in network:
    z = layer.forward(activations[-1])
    activations.append(activation(z))

# 计算损失
loss = loss_fn(activations[-1], target)

# 反向 pass
grad = loss_gradient()
for i in reversed(range(len(network))):
    grad = backward_layer(network[i], activations[i+1], grad)
```

## References

- Rumelhart, D. E., Hinton, G. E., & Williams, R. J. (1986). *Learning representations by back-propagating errors*. Nature. [https://doi.org/10.1038/323533a0](https://doi.org/10.1038/323533a0)
- LeCun, Y., et al. (1989). *Backpropagation Applied to Handwritten Zip Code Recognition*. Neural Computation.
- Goodfellow, I., Bengio, Y., & Courville, A. (2016). *Deep Learning*. MIT Press.
