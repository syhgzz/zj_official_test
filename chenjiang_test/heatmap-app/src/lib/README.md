# interplot_subsidence_figure

散点插值图层库，支持 4 种算法叠加在高德地图上。

## 通用参数

| 参数 | 类型 | 推荐值 | 说明 |
|---|---|---|---|
| `map` | AMap.Map | 必填 | 高德地图实例 |
| `data` | Array | 必填 | `[{lng, lat, value}]` |
| `colorFn` | Function | 必填 | `(value) => [r, g, b]` |
| `algorithm` | string | `idw` | `gaussian` \| `idw` \| `rbf` \| `kriging` |
| `sigmaMultiplier` | number | 3 | 搜索半径 = σ × 此值，影响插值平滑度 |
| `maxRadius` | number | 20000 | 搜索半径上限 px，设大防高倍缩放时覆盖缩水 |
| `opacity` | number | 0.7 | 图层透明度 0~1 |
| `gridStep` | number | 4 | 采样步长 px，1~8，越小越精细越慢 |
| `baseZoom` | number | 11 | 基准缩放级别，σ 等比缩放中心 |
| `debounceMs` | number | 200 | 平移/缩放后延迟渲染毫秒 |
| `initDelayMs` | number | 600 | 首次加载延迟毫秒 |
| `radiusJitter` | boolean | true | 蒙特卡洛半径采样开关 |
| `mcSamples` | number | 2 | 蒙特卡洛样本数，0~16（0=关闭） |

**返回** `{ show(), hide(), destroy() }`

---

## 1. IDW 反距离加权

### 算法原理

$$\hat{v}(x) = \frac{\sum w_i v_i}{\sum w_i}, \quad w_i = \frac{1}{(d_i^2 + \varepsilon)^{p/2}}$$

$d_i$ 为像素距离，$p$ 控制衰减速度，$\varepsilon$ 防除零。

### 用法

```js
const overlay = createInterpolationOverlay({
  map, data, colorFn,
  algorithm: 'idw',
  idwPower: 3.5,
  idwEpsilon: 0.1,
  sigmaMultiplier: 10,
  maxRadius: 20000,
})
```

### 专属参数

| 参数 | 类型 | 推荐值 | 说明 |
|---|---|---|---|
| `idwPower` | number | 3.5 | 幂 p，越大远点影响越小 |
| `idwEpsilon` | number | 0.1 | 平滑项，防除零 |

---

## 2. Gaussian 高斯核

### 算法原理

$$\hat{v}(x) = \frac{\sum w_i v_i}{\sum w_i}, \quad w_i = \exp\!\left(-\frac{d_i^2}{2\sigma^2}\right)$$

截断半径 $R = k \cdot \sigma$，$\sigma = \sigma_0 \cdot 2^{zoom - zoom_0}$。

### 用法

```js
const overlay = createInterpolationOverlay({
  map, data, colorFn,
  algorithm: 'gaussian',
  baseSigma: 25,
  sigmaMultiplier: 3,
  maxRadius: 20000,
})
```

### 专属参数

| 参数 | 类型 | 推荐值 | 说明 |
|---|---|---|---|
| `baseSigma` | number | 25 | 基础 σ，越大越平滑 |

---

## 3. RBF 径向基函数

### 算法原理

解局部线性系统 $A\alpha = v$，$A_{ij} = \phi(\|x_i-x_j\|) + \lambda\delta_{ij}$，插值：

$$\hat{v}(x) = \sum_{k=1}^N \alpha_k \cdot \phi(\|x - x_k\|)$$

| 核 `rbfType` | $\phi(r)$ |
|---|---|
| `thinPlate` | $r^2\ln r$ |
| `multiquadric` | $\sqrt{r^2 + 1}$ |
| `gaussian` | $e^{-r^2}$ |

### 用法

```js
const overlay = createInterpolationOverlay({
  map, data, colorFn,
  algorithm: 'rbf',
  rbfType: 'thinPlate',
  rbfSmooth: 0,
  sigmaMultiplier: 10,
  maxRadius: 20000,
})
```

### 专属参数

| 参数 | 类型 | 推荐值 | 说明 |
|---|---|---|---|
| `rbfType` | string | `thinPlate` | 核函数类型 |
| `rbfSmooth` | number | 0 | 正则化 λ，增大防过拟合 |

---

## 4. Kriging 克里金

### 算法原理

解 Ordinary Kriging 系统：

$$\begin{bmatrix}\Gamma & 1 \\ 1^T & 0\end{bmatrix} \begin{bmatrix}w \\ \mu\end{bmatrix} = \begin{bmatrix}\gamma_0 \\ 1\end{bmatrix}$$

变异函数 $\gamma(h)$：

| 模型 `krigingModel` | $\gamma(h)$ |
|---|---|
| `exponential` | $c_0 + c_s(1 - e^{-3h/a})$ |
| `spherical` | $c_0 + c_s(1.5r - 0.5r^3),\; r = \min(h/a,1)$ |
| `gaussian` | $c_0 + c_s(1 - e^{-3h^2/a^2})$ |

### 用法

```js
const overlay = createInterpolationOverlay({
  map, data, colorFn,
  algorithm: 'kriging',
  krigingModel: 'exponential',
  krigingNugget: 0,
  krigingRange: 200,
  krigingSill: 1,
  sigmaMultiplier: 10,
  maxRadius: 20000,
})
```

### 专属参数

| 参数 | 类型 | 推荐值 | 说明 |
|---|---|---|---|
| `krigingModel` | string | `exponential` | 变异函数模型 |
| `krigingNugget` | number | 0 | 块金值 $c_0$ |
| `krigingRange` | number | 200 | 变程 $a$（像素） |
| `krigingSill` | number | 1 | 基台 $c_0 + c_s$ |
