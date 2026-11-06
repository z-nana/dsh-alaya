---
title: "Gradient-Descent"
type: tutorial
created: 2026-06-02
tags: [deep-learning, backpropagation, optimization]
seed_type: REFINED
created_by: system
strength: 0.5
last_activated: 2026-06-02
activation_count: 0
description: "梯度下降是最基础的优化算法，通过沿梯度反方向迭代更新参数以最小化损失函数。"
---

# 梯度下降

> 梯度下降（Gradient Descent）是最基础也是应用最广泛的优化算法，通过沿损失函数梯度的负方向迭代更新参数，逐步逼近最优解。几乎所有深度学习模型的训练都建立在梯度下降或其变体之上。

## 基本原理

对于可微损失函数 $\mathcal{L}(\theta)$，梯度下降的更新规则为：

$$ \theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}(\theta_t) $$

其中：
- $\theta_t$：第 $t$ 步的参数
- $\eta$：学习率（step size），决定每次更新的步长
- $\nabla_\theta \mathcal{L}(\theta_t)$：损失函数在 $\theta_t$ 处的梯度（一阶偏导向量）

**几何直观**：梯度指向函数增长最快的方向，负梯度即下降最快的方向。每次迭代沿最陡坡向下迈一步。

## 核心变体

### BGD（Batch Gradient Descent）

使用**整个训练集**计算一次梯度后更新参数：

$$ \theta_{t+1} = \theta_t - \eta \cdot \frac{1}{N} \sum_{i=1}^{N} \nabla_\theta \mathcal{L}_i(\theta_t) $$

- ✅ 梯度方向准确稳定，收敛平滑
- ❌ 每步需遍历全部样本，大数据集极慢
- ❌ 无法在线学习（无法增量更新）

### SGD（Stochastic Gradient Descent）

每次随机选取**一个样本**计算梯度并更新：

$$ \theta_{t+1} = \theta_t - \eta \nabla_\theta \mathcal{L}_i(\theta_t) $$

- ✅ 计算极快，可在线学习
- ✅ 梯度噪声有助于逃离鞍点
- ❌ 梯度方差大，收敛路径震荡
- ❌ 无法利用 GPU 并行批量计算

### Mini-Batch GD（默认选择）

每次使用**一个小批量**（batch size = $m$）的样本计算梯度：

$$ \theta_{t+1} = \theta_t - \eta \cdot \frac{1}{m} \sum_{i=1}^{m} \nabla_\theta \mathcal{L}_i(\theta_t) $$

- ✅ 折中 BGD 的稳定和 SGD 的速度
- ✅ 可利用 GPU 矩阵运算高效并行
- ✅ 小批量噪声有助于泛化
- ⚠️ batch size 是重要超参数（常见 32/64/128/256）

## 动量优化（Momentum）

引入**速度**概念，累积历史梯度方向，抑制震荡、加速收敛：

$$ v_{t+1} = \beta v_t + \eta \nabla_\theta \mathcal{L}(\theta_t) $$
$$ \theta_{t+1} = \theta_t - v_{t+1} $$

其中 $\beta \in [0,1)$ 为动量系数（常见 0.9）。

**直观理解**：小球沿损失面滚动，当前动量来自历史累积，即使在梯度很小的平坦区域也能保持速度前行。

### Nesterov Accelerated Gradient（NAG）

Momentum 的改进版，先"往前看一步"再计算梯度：

$$ v_{t+1} = \beta v_t + \eta \nabla_\theta \mathcal{L}(\theta_t - \beta v_t) $$
$$ \theta_{t+1} = \theta_t - v_{t+1} $$

NAG 比标准 Momentum 具有更好的收敛保证和更小的震荡。

## Adam（Adaptive Moment Estimation）

结合 Momentum 和 RMSProp 的自适应学习率优化器，是目前最常用的深度学习优化器：

$$ m_t = \beta_1 m_{t-1} + (1 - \beta_1) \nabla_\theta \mathcal{L}(\theta_t) $$
$$ v_t = \beta_2 v_{t-1} + (1 - \beta_2) [\nabla_\theta \mathcal{L}(\theta_t)]^2 $$
$$ \hat{m}_t = \frac{m_t}{1 - \beta_1^t}, \quad \hat{v}_t = \frac{v_t}{1 - \beta_2^t} $$
$$ \theta_{t+1} = \theta_t - \eta \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon} $$

- $m_t$：一阶矩估计（梯度均值），对应 Momentum
- $v_t$：二阶矩估计（梯度未中心化方差），对应自适应学习率
- $\beta_1 = 0.9, \beta_2 = 0.999, \epsilon = 10^{-8}$（默认值）
- 偏差校正 $\hat{m}_t, \hat{v}_t$：解决初始时刻估计值偏向 0 的问题

| 优化器 | 特点 | 适用场景 |
|:--|:--|:--|
| BGD | 稳定平滑 | 小数据集 |
| SGD | 简单快速 | 大型数据集（需精细调学习率） |
| Momentum | 加速收敛，抑制震荡 | 标准替代 SGD |
| NAG | 相比 Momentum 更早修正方向 | 需要更稳定收敛时 |
| Adam | 自适应学习率，对超参数鲁棒 | **默认首选** |
| AdamW | Adam + 权重解耦（decoupled weight decay） | 含正则化的大型模型 |

## 学习率调度（Learning Rate Scheduling）

学习率 $\eta$ 是梯度下降最重要的超参数。动态调整策略可显著提升收敛质量。

### 常用策略

**Step Decay**：每 $T$ 步将学习率乘以衰减因子 $\gamma$：
$$ \eta_t = \eta_0 \cdot \gamma^{\lfloor t/T \rfloor} $$

**Cosine Annealing**：按余弦周期从 $\eta_{\max}$ 衰减到 $\eta_{\min}$：
$$ \eta_t = \eta_{\min} + \frac{1}{2}(\eta_{\max} - \eta_{\min})(1 + \cos(\pi t / T)) $$

**Warmup**：训练初期从 0 线性增加到目标学习率，防止早期梯度震荡：
$$ \eta_t = \eta_{\max} \cdot \min\left(1, \frac{t}{T_{\text{warmup}}}\right) $$

**Cosine Annealing with Warm Restarts**：周期性余弦衰减 + 重启，每次重启后重置学习率，帮助逃离局部极小。

## References

- Robbins, H., & Monro, S. (1951). *A Stochastic Approximation Method*. Annals of Mathematical Statistics.
- Rumelhart, D. E., et al. (1986). *Learning representations by back-propagating errors*. Nature.
- Kingma, D. P., & Ba, J. (2015). *Adam: A Method for Stochastic Optimization*. ICLR. [https://arxiv.org/abs/1412.6980](https://arxiv.org/abs/1412.6980)
- Loshchilov, I., & Hutter, F. (2019). *Decoupled Weight Decay Regularization*. ICLR. [https://arxiv.org/abs/1711.05101](https://arxiv.org/abs/1711.05101)
- Loshchilov, I., & Hutter, F. (2017). *SGDR: Stochastic Gradient Descent with Warm Restarts*. ICLR. [https://arxiv.org/abs/1608.03983](https://arxiv.org/abs/1608.03983)
