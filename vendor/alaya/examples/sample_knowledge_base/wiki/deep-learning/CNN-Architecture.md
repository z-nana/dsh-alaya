---
title: "CNN-Architecture"
type: survey
created: 2026-06-02
tags: [deep-learning, neural-networks, cnn]
seed_type: REFINED
created_by: system
strength: 0.6
last_activated: 2026-06-02
activation_count: 0
description: "卷积神经网络通过局部感受野和权重共享实现高效的特征提取，是计算机视觉领域的核心架构。"
---

# 卷积神经网络

> 卷积神经网络（Convolutional Neural Network, CNN）专为处理网格结构数据（如图像）而设计，通过局部连接、权值共享和池化操作，在空间层级上逐层提取特征。从 LeNet 到 ResNet，CNN 是计算机视觉领域的基石。

## 卷积核（Convolutional Kernel / Filter）

卷积核是 CNN 的核心操作单元，本质上是一个可学习的特征检测器。

### 数学定义

对输入 $I \in \mathbb{R}^{H \times W \times C_{in}}$ 和卷积核 $K \in \mathbb{R}^{k_h \times k_w \times C_{in} \times C_{out}}$，输出特征图 $S$ 在位置 $(i,j)$ 第 $c$ 个通道的值为：

$$ S(i,j,c) = \sum_{u=0}^{k_h-1} \sum_{v=0}^{k_w-1} \sum_{c'=0}^{C_{in}-1} I(i+u, j+v, c') \cdot K(u, v, c', c) $$

### 关键特性

**局部连接**：每个神经元只连接输入的一个局部区域（感受野），而非全连接，参数量从 $O(N_{in} \times N_{out})$ 降至 $O(k_h \times k_w \times C_{in} \times C_{out})$。

**权值共享**：同一个卷积核在输入的所有空间位置共享参数，使网络具有平移等变性——猫不管出现在图像的哪个位置，同一卷积核都能检测到。

**多核叠加**：$C_{out}$ 个不同的卷积核可检测 $C_{out}$ 种不同的特征模式（边缘、纹理、形状等）。

### 卷积参数

| 参数 | 含义 | 常见值 |
|:--|:--|:--|
| 卷积核大小 $k$ | 感受野尺寸 | $3 \times 3$（主流）、$5 \times 5$ |
| 步长 $s$ | 卷积核滑动的步幅 | 1（标准）、2（下采样） |
| 填充 $p$ | 输入周围补零的圈数 | `same`（保持尺寸）、`valid`（不填充） |
| 输出通道数 $C_{out}$ | 特征图数量 | 64、128、256（逐层增加） |

输出特征图尺寸：

$$ H_{out} = \left\lfloor \frac{H_{in} + 2p - k}{s} \right\rfloor + 1 $$

## 池化层（Pooling Layer）

池化层对特征图进行下采样，降低空间维度、减少参数量、提供平移不变性。

### 最大池化（Max Pooling）

在 $k \times k$ 窗口内取最大值：

$$ \text{MaxPool}(I)_{i,j} = \max_{u,v \in [0,k)} I_{i+u, j+v} $$

- ✅ 保留了最强激活的响应
- ✅ 对小范围的平移和旋转具有鲁棒性
- ❌ 丢弃了位置精确信息

### 平均池化（Average Pooling）

在 $k \times k$ 窗口内取平均值：

$$ \text{AvgPool}(I)_{i,j} = \frac{1}{k^2} \sum_{u=0}^{k-1} \sum_{v=0}^{k-1} I_{i+u, j+v} $$

- 常用于全局平均池化（GAP），替代全连接层作为分类头

| 池化类型 | 特性 | 典型用途 |
|:--|:--|:--|
| Max Pooling | 保留最强特征，具平移不变性 | 中间层下采样 |
| Average Pooling | 平滑特征，保留整体分布 | 全局池化替代 FC |
| Global Avg Pooling | 整个特征图取平均 | 分类头（ResNet 等） |

## 特征图与层级结构

CNN 通过逐层堆叠卷积 + 池化，构建从低级到高级的特征层次：

```
输入图像 (224×224×3)
      ↓
[Conv 3×3 → ReLU → Conv 3×3 → ReLU → MaxPool 2×2]   ← 低级特征（边缘、角点、颜色块）
      ↓
[Conv 3×3 → ReLU → Conv 3×3 → ReLU → MaxPool 2×2]   ← 中级特征（纹理、图案、局部形状）
      ↓
[Conv 3×3 → ReLU → Conv 3×3 → ReLU → MaxPool 2×2]   ← 高级特征（物体部件、语义概念）
      ↓
[FC → ReLU → FC → Softmax]                           ← 分类决策
```

**特征可视化**：浅层卷积核学习到的是 Gabor-like 边缘检测器；中层检测到纹理和图案（如车轮、眼睛）；深层则激活了对完整物体或语义场景的反应。

## 迁移学习（Transfer Learning）

迁移学习是 CNN 实践中极其重要的策略：将在大型数据集（如 ImageNet）上预训练的 CNN 模型应用于新任务。

### 常见策略

| 策略 | 操作 | 适用条件 |
|:--|:--|:--|
| **特征提取器** | 冻结所有卷积层，只训练新分类头 | 新数据集小且与预训练数据相似 |
| **微调（Fine-tuning）** | 解冻部分高层卷积层，与分类头一起训练 | 新数据集中等规模 |
| **全量微调** | 解冻所有层，用较小学习率训练 | 新数据集大且差异大 |
| **渐进解冻** | 从顶层开始逐层解冻，边解冻边训练 | 数据分布差异较大时 |

### 选择指南

- **数据量大 + 数据相似**：全量微调
- **数据量大 + 数据不相似**：全量微调（需要更多训练轮次）
- **数据量小 + 数据相似**：特征提取器
- **数据量小 + 数据不相似**：微调高层卷积层（从顶向下 1-2 层）

## References

- LeCun, Y., et al. (1998). *Gradient-based learning applied to document recognition*. Proceedings of the IEEE.
- Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2012). *ImageNet Classification with Deep Convolutional Neural Networks*. NeurIPS.
- Simonyan, K., & Zisserman, A. (2015). *Very Deep Convolutional Networks for Large-Scale Image Recognition*. ICLR. [https://arxiv.org/abs/1409.1556](https://arxiv.org/abs/1409.1556)
- He, K., et al. (2016). *Deep Residual Learning for Image Recognition*. CVPR. [https://arxiv.org/abs/1512.03385](https://arxiv.org/abs/1512.03385)
- Yosinski, J., et al. (2014). *How transferable are features in deep neural networks?* NeurIPS. [https://arxiv.org/abs/1411.1792](https://arxiv.org/abs/1411.1792)
