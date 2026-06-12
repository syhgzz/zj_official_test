# 沉降热力图

基于高德地图 JS API + Vue3 的沉降数据热力图可视化。

## 启动

```bash
npm install
npm run dev
```

## 热力图覆盖范围随缩放不变的原理

AMap HeatMap 的 `radius` 是固定像素值，放大后同样像素覆盖的地理范围变小，导致热力色块收缩。

**解决方法**：监听 `zoomchange` 事件，按 `radius = BASE_RADIUS × 2^(zoom - BASE_ZOOM)` 等比缩放 radius（下限 10px，上限 600px）：

```js
const BASE_ZOOM = 11
const BASE_RADIUS = 30

function zoomRadius(zoom) {
  const r = Math.round(BASE_RADIUS * Math.pow(2, zoom - BASE_ZOOM))
  return Math.max(10, Math.min(600, r))
}

map.on('zoomchange', () => {
  heatmap.setOptions({ radius: zoomRadius(map.getZoom()) })
})
```

> 使用 `zoomchange` 而非 `zoomend`，每帧更新 radius，实现平滑过渡。

## 配色

数据经 `log1p` 对数变换后映射到蓝→绿→黄→红四色梯度：

| 沉降值 | 颜色 |
|---|---|
| ≤0 | 蓝 |
| 1 | 绿 |
| 4 | 黄 |
| ≥10 | 红 |

