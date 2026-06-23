# 沉降热力图

基于高德地图 JS API + Vue3 的沉降数据热力图可视化。

## 启动

```bash
npm install
npm run dev
```

## 功能

- **散点图** — CPU Canvas 2D 渲染（`renderScatter` 函数），沉降值按颜色映射逐点画圆，转 PNG 后通过 `AMap.ImageLayer` 叠加
- **AMap 热力图** — 高德原生热力图图层，radius 随缩放等比变化
- **插值图** — 4 种插值算法（Gaussian / IDW / RBF / Kriging），Web Worker 非阻塞渲染；IDW 和 Gaussian 支持 WebGL2 GPU 加速（`splatInit`/`splatDraw`）
- **搜索半径** — 最大搜索核半径倍率默认 ∞，可关闭限制搜索所有数据点
- **颜色系统** — 发散色阶 12 断点，支持 RGBA（COLOR_STOPS 每断点可选第 4 值为 alpha 0-255）
- **数据来源** — 支持 3 种模式：本地 JSON 文件、HTTP 二进制接口、WebSocket + ProtoBuf
- **调试模式** — 当前视口内随机生成指定数量点（1-200），快速验证算法参数

## 数据来源

| 模式 | 说明 |
|------|------|
| 本地 JSON | 加载 `src/data/` 下所有 JSON 文件，前端解析渲染 |
| HTTP 接口 | 请求 `localhost:3456`，返回 Float32Array 二进制数据 |
| WebSocket + ProtoBuf | 连接 `ws://localhost:3457`，Protobuf 编码传输 |

## 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 算法 | IDW | 反距离加权 |
| σ (baseSigma) | 25 | 基础高斯核标准差 |
| 搜索半径倍率 | ∞ | sigmaMultiplier，∞ = 搜索全图 |
| 搜索半径上限 | 20000 px | maxRadius |
| 采样步长 (gridStep) | 2 px | 越小越精细，越慢 |
| 透明度 | 0.6 | 插值图层透明度 |
| GPU 加速 | 开启 | IDW/Gaussian 走 WebGL2，其他走 CPU |
| 高斯模糊 | 关闭 | GPU 后处理模糊 |
| 半径蒙特卡洛 | 关闭 | 开启后 GPU 不生效，降级 CPU |
| IDW 幂 | 3.5 | 距离衰减指数 |
| IDW 平滑项 | 0.1 | 防止除零 |

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

## 渲染架构

```
App.vue
├─ renderScatter()           CPU Canvas 2D 散点图 → AMap.ImageLayer
├─ AMap.HeatMap              高德原生热力图
└─ createInterpolationOverlay()
   ├─ 主线程: lngLatToContainer → buildColorLUT → postMessage
   └─ Worker (interp-worker.js)
      ├─ GPU 路径 (webgl-splat.js): IDW/Gaussian
      │   splatInit() → splatDraw() (Pass1: 累加, Pass2: 合成)
      └─ CPU 路径: RBF/Kriging/jitter
          分箱查询 → 逐像素插值 → fillRect → toBlob
```

| 图层 | 渲染方式 | 核心函数 |
|------|---------|---------|
| 散点图 | CPU Canvas 2D | `renderScatter` (App.vue) |
| 热力图 | 高德 SDK | `AMap.HeatMap` |
| 插值图 (IDW/Gaussian) | GPU WebGL2 | `splatInit` / `splatDraw` (webgl-splat.js) |
| 插值图 (RBF/Kriging) | CPU Worker | `computeCellValue` 等 (interp-worker.js) |

## 插值图参数

详见 `src/lib/README.md`。快速调用：

```js
import { createInterpolationOverlay } from './lib/interplot_figure.js'

const overlay = createInterpolationOverlay({
  map, data, colorFn,
  binaryRawData: { lng: Float32Array, lat: Float32Array, val: Float32Array },  // 可选，远程数据路径
  algorithm: 'idw',           // gaussian | idw | rbf | kriging
  sigmaMultiplier: Infinity,  // 搜索所有数据点
  gridStep: 2,                // 采样步长
  gpuEnabled: true,           // GPU 加速（仅 IDW/Gaussian）
  onRender: (timings) => {    // 渲染耗时回调，timings 包含各阶段耗时
    console.log('total:', timings.total, 'ms')
  },
})
```

