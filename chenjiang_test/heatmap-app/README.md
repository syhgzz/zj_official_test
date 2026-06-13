# 沉降热力图

基于高德地图 JS API + Vue3 的沉降数据热力图可视化。

## 启动

```bash
npm install
npm run dev
```

## 功能

- **散点图** — 沉降值按颜色映射渲染到 Canvas ImageLayer
- **AMap 热力图** — 高德原生热力图图层
- **插值图** — 4 种插值算法（Gaussian / IDW / RBF / Kriging），Worker + GPU 非阻塞渲染
- **搜索半径** — 最大搜索核半径倍率默认 ∞，可关闭限制搜索所有数据点
- **颜色系统** — 发散色阶 12 断点，支持 RGBA（COLOR_STOPS 每断点可选第 4 值为 alpha 0-255）
- **调试模式** — 可拖拽标记点，点数 1-200，散点图自动隐藏

## 默认参数

| 参数 | 默认值 |
|------|--------|
| 算法 | IDW（反距离加权） |
| σ | 25 |
| 搜索半径倍率 | ∞ |
| 搜索半径上限 | 20000 px |
| 采样步长 (gridStep) | 2 px |
| 透明度 | 0.6 |
| 高斯模糊 | 关闭 |
| 模糊半径 | 1.5 px |

## 热力图覆盖范围随缩放不变的原理

AMap HeatMap 的 `radius` 是固定像素值，放大后同样像素覆盖的地理范围变小，导致热力色块收缩。

**解决方法**：监听 `zoomchange` 事件，按 `radius = BASE_RADIUS × 2^(zoom - BASE_ZOOM)` 等比缩放 radius（下限 10px，上限 600px）。

## 配色

发散色阶，以 0 为中性点（绿色），负值偏蓝紫，正值偏红橙。COLOR_STOPS 中每个断点 `[value, [r, g, b, a]]`，a 可选（默认 255）。

| 沉降值 | 颜色 |
|---|---|
| ≤-30 | 紫 |
| -20 | 深蓝 |
| -10 | 中蓝 |
| -5 | 浅蓝 |
| -2 | 淡蓝 |
| 0 | 绿 |
| 3 | 黄绿 |
| 6 | 黄 |
| 10 | 橙 |
| 15 | 橙红 |
| ≥23 | 红 |

## 插值图参数

详见 `src/lib/README.md`。快速调用：

```js
import { createInterpolationOverlay } from './lib/interplot_figure.js'

const overlay = createInterpolationOverlay({
  map, data, colorFn,
  algorithm: 'idw',           // gaussian | idw | rbf | kriging
  sigmaMultiplier: Infinity,  // 搜索所有数据点
  gridStep: 2,                // 采样步长
})
```

