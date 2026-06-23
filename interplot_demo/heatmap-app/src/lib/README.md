# lib/ — 插值渲染库

散点插值图层，Worker + GPU 非阻塞渲染，4 种算法叠加高德地图。

## ⚠️ 外部调用须知

- `import { createInterpolationOverlay } from '...'` → 直接使用，**调用即非阻塞**
- 插值计算在 **Web Worker** 后台执行，主线程仅做像素坐标转换（需 AMap API），不卡 UI
- PNG 编码异步（`toBlob` / `convertToBlob`），不阻塞
- Worker 不可用时自动降级主线程；GPU 不可用自动降级 CPU Worker 路径
- 销毁：调用 `overlay.destroy()` 终止 Worker、移除图层
- 渲染耗时通过 `onRender: (timings) => {}` 回调获取，`timings` 对象包含各阶段耗时（详见下方）
- **数据格式**：支持两种传入方式
  - `data: [{lng, lat, value}]` — 对象数组（本地 JSON）
  - `binaryRawData: {lng: Float32Array, lat: Float32Array, val: Float32Array}` — 类型数组（远程 HTTP/WebSocket 路径）
- **性能**：
  - GPU 路径（IDW/Gaussian）：1 万点流畅，10 万点约 3-4 秒，百万点会卡死
  - CPU 路径（RBF/Kriging/jitter）：比 GPU 慢 5-10 倍，建议点数 < 5000
  - 数据点数很大时，缩小搜索半径倍率到 3-7 可大幅提速

## 快速开始

```js
import { createInterpolationOverlay } from './lib/interplot_figure.js'

const overlay = createInterpolationOverlay({
  map,                     // AMap.Map 实例
  data: [{ lng, lat, value }],  // 数据点（对象数组）
  binaryRawData: {              // 或使用类型数组（远程路径）
    lng: new Float32Array([...]),
    lat: new Float32Array([...]),
    val: new Float32Array([...]),
  },
  colorFn: (v) => [r, g, b],    // (v) => [r, g, b] 或 [r, g, b, a]（a: 0-255）
  algorithm: 'idw',             // gaussian | idw | rbf | kriging
  onRender: (timings) => {      // 渲染耗时回调，timings 为各阶段耗时对象
    console.log('total:', timings.total)
  },
})
```

## 全部参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `map` | AMap.Map | 必填 | |
| `data` | Array | `[]` | `[{lng, lat, value}]` 对象数组 |
| `binaryRawData` | Object | `null` | `{lng: Float32Array, lat: Float32Array, val: Float32Array}` 类型数组，优先级高于 `data` |
| `colorFn` | Function | 必填 | `(v) => [r, g, b]` 或 `[r, g, b, a]` (a: 0-255) |
| `algorithm` | string | `idw` | `gaussian` \| `idw` \| `rbf` \| `kriging` |
| `opacity` | number | 0.7 | 图层透明度 |
| `gridStep` | number | 2 | 采样步长 px，越小越精细 |
| `maxNearbyPoints` | number | 0 | 每像素最多处理数据点数，0=不限制，GPU 下不生效 |
| `baseSigma` | number | 25 | 基础 σ |
| `sigmaMultiplier` | number | ∞ | 搜索半径 = σ × 此值 |
| `maxRadius` | number | 20000 | 搜索半径上限 px |
| `baseZoom` | number | 11 | σ 等比缩放基准级别 |
| `debounceMs` | number | 200 | 防抖延迟 ms |
| `onRender` | Function | null | `(timings) => void`，timings 结构见下方 |

### IDW 专属

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `idwPower` | 3.5 | 距离衰减幂 |
| `idwEpsilon` | 0.1 | 平滑项 |

### RBF 专属

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rbfType` | `thinPlate` | `thinPlate` \| `multiquadric` \| `gaussian` |
| `rbfSmooth` | 0 | 正则化系数 |

### Kriging 专属

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `krigingModel` | `exponential` | `exponential` \| `spherical` \| `gaussian` |
| `krigingNugget` | 0 | 块金值 |
| `krigingRange` | 200 | 变程 |
| `krigingSill` | 1 | 基台 |

### GPU 加速

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `gpuEnabled` | true | GPU IDW / Gaussian 加速（jitter 开启时 GPU 不生效） |
| `radiusJitter` | false | MC 抖动（开启后 GPU 不生效） |
| `mcSamples` | 2 | MC 采样数 |
| `mcJitterFactor` | 0.2 | MC 抖动幅度 |
| `blurEnabled` | false | GPU 高斯模糊 |
| `blurRadius` | 1.5 | 模糊半径 px |

**返回** `{ show(), hide(), destroy() }`

### `onRender` 回调 timings 对象结构

```js
onRender: (timings) => {
  // timings 包含以下字段（单位 ms）：
  timings.total                    // 总耗时
  timings.main_collectPoints       // 主线程：lngLatToContainer 像素转换
  timings.main_buildLUT            // 主线程：颜色 LUT 构建
  timings.main_postMessage         // 主线程：发消息到 Worker
  // GPU 路径专属：
  timings.gpu_setup                // GPU：纹理/状态初始化
  timings.gpu_upload               // GPU：数据上传
  timings.gpu_pass1                // GPU：Pass 1 累加
  timings.gpu_pass2                // GPU：Pass 2 合成
  timings.gpu_finish               // GPU：读取像素
  // 通用：
  timings.worker_blur              // Worker：高斯模糊（若启用）
  timings.worker_png               // Worker：PNG 编码
  timings.main_imageLayer          // 主线程：创建 ImageLayer
}
```

## 架构

```
createInterpolationOverlay()
  ├─ 主线程: lngLatToContainer → buildColorLUT → postMessage
  └─ Worker (interp-worker.js)
     ├─ GPU 路径 (webgl-splat.js): IDW / Gaussian（jitter 关闭时）
     │   splatInit() → splatDraw()
     │   Pass 1: instanced quad splatting → float 纹理累加 (w*val, w)
     │   Pass 2: fullscreen quad → wv/w 归一化 → LUT 查色 → canvas
     │   (可选) blur → convertToBlob → postMessage
     └─ CPU 路径: RBF / Kriging / jitter 模式
         分箱 (buildBins) → 逐像素查询 (queryBins)
         → computeCellValue → fillRect → (可选) blur → convertToBlob
```

- 主线程不阻塞，渲染在 Worker 中完成
- GPU 支持 IDW 和 Gaussian，jitter 关闭时生效，不满足自动降级 CPU
- `data` 和 `binaryRawData` 两种输入格式，`binaryRawData` 用于远程数据路径（HTTP/WebSocket），避免重复序列化

## 算法公式

对每个像素点 $(x,y)$，在其搜索半径 $R$ 内的 $n$ 个数据点 $\{P_i\}$ 进行加权插值。

### Gaussian 高斯核

$$w_i = \exp\left(-\frac{d_i^2}{2\sigma^2}\right), \quad v(x,y) = \frac{\sum w_i \cdot v_i}{\sum w_i}$$

- $d_i$：像素到数据点 $P_i$ 的欧氏距离（像素）
- $\sigma = \text{baseSigma} \times 2^{\,zoom - baseZoom}$，随缩放等比变化
- 权重平滑衰减，无硬截止；$\sigma$ 控制影响范围，越小越局部
- GPU 加速：`w = exp(d2 * (-0.5 / sigma²))`

### IDW 反距离加权

$$w_i = \frac{1}{(d_i^2 + \varepsilon)^{p/2}}, \quad v(x,y) = \frac{\sum w_i \cdot v_i}{\sum w_i}$$

- $p$：幂指数（idwPower），越大近点权重越集中，默认 3.5
- $\varepsilon$：平滑项（idwEpsilon），防止除零，默认 0.1
- GPU 加速：`w = 1.0 / pow(d2 + eps, power * 0.5)`

### RBF 径向基函数

$$\begin{bmatrix} \phi(d_{ij}) + \lambda\delta_{ij} & \mathbf{1} \\ \mathbf{1}^T & 0 \end{bmatrix} \begin{bmatrix} \mathbf{w} \\ \mu \end{bmatrix} = \begin{bmatrix} \mathbf{v} \\ 0 \end{bmatrix}$$

$$v(x,y) = \sum_{i=1}^{n} w_i \cdot \phi(d_i)$$

- 求解 $n \times n$ 线性方程组得到权重 $w_i$
- $\phi(r)$ 核函数：`thinPlate` $(r^2 \log r)$、`multiquadric` $(\sqrt{r^2+1})$、`gaussian` $(e^{-r^2})$
- $\lambda$（rbfSmooth）：正则化系数，默认 0

### Kriging 克里金

$$w_i = \text{solve}\left( \gamma(d_{ij}) \right), \quad v(x,y) = \sum w_i \cdot v_i + \mu$$

- $\gamma(h)$ 变异函数模型：`exponential`、`spherical`、`gaussian`
- 参数：块金值（nugget）、变程（range）、基台（sill）

### 搜索半径

$$R = \min(\text{sigmaMultiplier} \times \sigma,\; \text{maxRadius})$$

- sigmaMultiplier = ∞ 时搜索所有数据点（半径由 maxRadius 限制）
- maxRadius = ∞ 时无上限

## 文件说明

| 文件 | 作用 |
|------|------|
| `interplot_figure.js` | 主入口，`createInterpolationOverlay()`。管理 Worker 创建/通信、像素坐标转换（`lngLatToContainer`）、颜色 LUT 预计算、`AMap.ImageLayer` 创建与更新 |
| `interp-worker.js` | Web Worker。接收像素坐标或 `binaryRawData` → 分派到 GPU 或 CPU 路径 → OffscreenCanvas 绘制 → `convertToBlob` 返回主线程。支持所有 4 种算法 + MC 抖动 + 高斯模糊 |
| `webgl-splat.js` | GPU IDW / Gaussian 加速。`splatInit()` 上传数据到 GPU（一次性），`splatDraw()` 每帧渲染（仅更新 uniform）。WebGL2 instanced quad + 双 float 纹理（w*val, w）+ composite pass |

## 非阻塞原理

```
主线程                              Worker 线程
  │                                    │
  ├─ map.lngLatToContainer(points)     │
  ├─ buildColorLUT()                   │
  ├─ postMessage({pixelPoints,          │
  │    rawLng, rawLat, rawVal,         │  (binaryRawData 直传，零拷贝)
  │    bounds, ...}) ─────────────────→│
  │                                    ├─ GPU: splatInit (首次) / splatDraw
  │                                    │   Pass 1: splatting 累加
  │                                    │   Pass 2: 归一化 + LUT 查色
  │                                    ├─ CPU: buildBins → queryBins
  │                                    │   → computeCellValue → fillRect
  │                                    ├─ (可选) blur
  │                                    ├─ convertToBlob()
  │                                    └─ postMessage({blob, timings}) ─→
  │  URL.createObjectURL(blob) ←───────│
  │  new AMap.ImageLayer({url})        │
  │  onRender(timings)                 │
```

- `lngLatToContainer` 是唯一需 AMap API 的步骤 → 在主线程执行
- 其余全部（插值计算、Canvas 填充、PNG 编码）在 Worker 内完成
- **不阻塞**：主线程发起后立即返回，Worker 完成后通过 `postMessage` 回传 Blob
- 异步 PNG 编码使用 `OffscreenCanvas.convertToBlob`
- `binaryRawData` 为 `Float32Array`，通过 `postMessage` 传递时可被 Transferable 零拷贝传输

## 示例：发散色阶 colorFn

当前 `App.vue` 中使用的 colorFn 方案，支持 RGBA：

```js
// 4 通道线性插值，自动处理 alpha
function lerpColor(c0, c1, t) {
  const r = Math.round(c0[0] + (c1[0] - c0[0]) * t)
  const g = Math.round(c0[1] + (c1[1] - c0[1]) * t)
  const b = Math.round(c0[2] + (c1[2] - c0[2]) * t)
  const aa = c0.length > 3 ? c0[3] : 255
  const ba = c1.length > 3 ? c1[3] : 255
  const a = Math.round(aa + (ba - aa) * t)
  return a < 255 ? [r, g, b, a] : [r, g, b]
}

// 发散色阶：负值蓝紫、0 绿（中心）、正值红橙
const COLOR_STOPS = [
  [-30, [75, 0, 130, 255]],   // 紫
  [-20, [0, 0, 180, 255]],    // 深蓝
  [-10, [30, 80, 220, 255]],  // 中蓝
  [-5,  [80, 160, 240, 255]], // 浅蓝
  [-2,  [150, 210, 250, 255]],// 淡蓝
  [0,   [0, 200, 0, 255]],    // 绿（中性点）
  [3,   [150, 220, 0, 255]],
  [6,   [255, 200, 0, 255]],  // 黄
  [10,  [255, 140, 0, 255]],  // 橙
  [15,  [255, 60, 0, 255]],   // 橙红
  [23,  [200, 0, 0, 255]],    // 红
]

function colorFn(v) {
  const clamped = Math.max(-30, Math.min(23, v))
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const [v0, c0] = COLOR_STOPS[i]
    const [v1, c1] = COLOR_STOPS[i + 1]
    if (clamped <= v1) {
      return lerpColor(c0, c1, (clamped - v0) / (v1 - v0))
    }
  }
  return [200, 0, 0, 255]
}

// 直接使用
const overlay = createInterpolationOverlay({ map, data, colorFn, algorithm: 'idw' })

// 或简写为行内函数
const overlay = createInterpolationOverlay({
  map, data,
  colorFn: (v) => getSubsidenceArray(v),  // 返回 [r,g,b] 或 [r,g,b,a]
  algorithm: 'idw',
})
```
