<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { createInterpolationOverlay } from './lib/interplot_subsidence_figure.js'

const mapContainer = ref(null)
const loading = ref(true)
const errorMsg = ref(null)
const pointCount = ref(0)
const showHeatmap = ref(false)
const showScatter = ref(true)
const showInterp = ref(true)
const interpSigma = ref(25)
const interpSigmaMult = ref(3)
const interpMaxRadius = ref(2000)
const interpOpacity = ref(0.6)
const interpGridStep = ref(4)
const currentZoom = ref(0)

const histCanvas = ref(null)

let map = null
let heatmap = null
let massMarks = null
let interpOverlay = null
let pointsData = []

const dataUrlMap = import.meta.glob('./data/*.json', { query: '?url', eager: true, import: 'default' })
const DATA_FILES = Object.values(dataUrlMap)
const AMAP_KEY = '244262d7f08882349099fad8cd2ae0cc'
const BASE_ZOOM = 11
const BASE_RADIUS = 30

function zoomRadius(zoom) {
  const r = Math.round(BASE_RADIUS * Math.pow(2, zoom - BASE_ZOOM))
  return Math.max(10, Math.min(600, r))
}

function getSubsidenceColor(subsidence) {
  if (subsidence <= -20) return 'rgb(75,0,130)'
  if (subsidence <= -15) return 'rgb(0,0,180)'
  if (subsidence <= -10) return 'rgb(30,80,220)'
  if (subsidence <= -5)  return 'rgb(80,160,240)'
  if (subsidence <= -2)  return 'rgb(150,210,250)'
  if (subsidence <= 0)   return 'rgb(0,180,0)'
  if (subsidence <= 3)   return 'rgb(150,220,0)'
  if (subsidence <= 6)   return 'rgb(255,200,0)'
  if (subsidence <= 10)  return 'rgb(255,140,0)'
  if (subsidence <= 15)  return 'rgb(255,60,0)'
  return 'rgb(200,0,0)'
}

onMounted(async () => {
  try {
    // 1. 并行加载全部 11 个文件
    const responses = await Promise.all(DATA_FILES.map(url => fetch(url)))
    const jsons = await Promise.all(responses.map(r => r.json()))
    const points = jsons.flatMap(j => j?.response?.data?.points || [])
    pointCount.value = points.length

    if (points.length === 0) {
      errorMsg.value = '未找到点位数据'
      loading.value = false
      return
    }

    // 2. Compute map center
    const sumLng = points.reduce((s, p) => s + p.longitude, 0)
    const sumLat = points.reduce((s, p) => s + p.latitude, 0)
    const center = [sumLng / points.length, sumLat / points.length]

    // 3. Load AMap JS API
    const AMap = await AMapLoader.load({
      key: AMAP_KEY,
      version: '2.0',
      plugins: ['AMap.HeatMap']
    })

    // 4. Create map instance
    map = new AMap.Map(mapContainer.value, {
      zoom: BASE_ZOOM,
      center: center,
      resizeEnable: true
    })

    // 5. Add traffic layer（交通图）
    const trafficLayer = new AMap.TileLayer.Traffic({
      zIndex: 10
    })
    map.add(trafficLayer)

    // 6. 热力图数据：平移 +30 纳入负值
    const heatmapData = points.map(p => ({
      lng: p.longitude,
      lat: p.latitude,
      count: p.subsidence + 30
    }))

    // 7. 发散色梯度（绿=0 中心）
    heatmap = new AMap.HeatMap(map, {
      radius: BASE_RADIUS,
      opacity: [0, 0.8],
      gradient: {
        0: 'rgb(75,0,130)',
        0.28: 'rgb(0,0,220)',
        0.57: 'rgb(0,200,0)',
        0.72: 'rgb(255,200,0)',
        0.85: 'rgb(255,60,0)',
        1: 'rgb(200,0,0)'
      },
      zooms: [3, 18]
    })

    heatmap.setDataSet({ data: heatmapData, max: 53 })
    heatmap.hide()

    // 动态调整热力图半径，保持地理覆盖范围不随缩放变化（zoomchange 实现平滑过渡）
    map.on('zoomchange', () => {
      if (heatmap) heatmap.setOptions({ radius: zoomRadius(map.getZoom()) })
      currentZoom.value = map.getZoom()
    })
    currentZoom.value = map.getZoom()

    // 9. 创建散点图层（CircleMarker，每个点独立颜色）
    massMarks = points.map(p => {
      const marker = new AMap.CircleMarker({
        center: [p.longitude, p.latitude],
        radius: 2,
        fillColor: getSubsidenceColor(p.subsidence),
        fillOpacity: 0.8,
        strokeColor: 'rgba(255,255,255,0.3)',
        strokeWeight: 1,
        zIndex: 20
      })
      marker.setMap(map)
      marker.show()
      return marker
    })

    // 10. 创建高斯核插值图层
    pointsData = points
    interpOverlay = createInterpolationOverlay({
      map,
      data: points.map(p => ({ lng: p.longitude, lat: p.latitude, value: p.subsidence })),
      colorFn: (v) => { const m = getSubsidenceColor(v).match(/\d+/g); return m ? m.map(Number) : [0,0,255] },
      baseSigma: interpSigma.value,
      sigmaMultiplier: interpSigmaMult.value,
      maxRadius: interpMaxRadius.value,
      opacity: interpOpacity.value,
      gridStep: interpGridStep.value
    })
    interpOverlay.show()

    // 11. 绘制分布直方图
    setTimeout(() => {
      const c = histCanvas.value
      if (!c) return
      const bins = [-30, -20, -15, -10, -5, -2, 0, 2, 5, 10, 15, 24]
      const hist = new Array(bins.length - 1).fill(0)
      for (const p of points) {
        for (let i = 0; i < bins.length - 1; i++) {
          if (p.subsidence >= bins[i] && p.subsidence < bins[i + 1]) { hist[i]++; break }
        }
      }
      const cx = c.getContext('2d')
      const maxH = Math.max(...hist)
      const w = 220, h = 130, pad = 2
      const barW = (w - pad * (hist.length + 1)) / hist.length
      for (let i = 0; i < hist.length; i++) {
        const bh = maxH ? (hist[i] / maxH) * (h - 25) : 0
        const x = pad + i * (barW + pad)
        const mid = (bins[i] + bins[i + 1]) / 2
        cx.fillStyle = getSubsidenceColor(mid)
        cx.fillRect(x, h - bh - 18, barW, bh)
        cx.fillStyle = '#666'
        cx.font = '8px sans-serif'
        cx.textAlign = 'center'
        const label = bins[i] <= -30 ? '≤-30' : bins[i] >= 20 ? '≥20' : bins[i].toString()
        cx.fillText(label, x + barW / 2, h - 4)
      }
    }, 300)

    loading.value = false
  } catch (err) {
    errorMsg.value = err.message || '未知错误'
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (heatmap) { heatmap.setMap(null); heatmap = null }
  if (massMarks) { massMarks.forEach(m => m.setMap(null)); massMarks = null }
  if (interpOverlay) { interpOverlay.destroy(); interpOverlay = null }
  if (map) { map.destroy(); map = null }
})

function toggleHeatmap() {
  showHeatmap.value = !showHeatmap.value
  if (heatmap) showHeatmap.value ? heatmap.show() : heatmap.hide()
}

function toggleScatter() {
  showScatter.value = !showScatter.value
  if (massMarks) {
    massMarks.forEach(m => showScatter.value ? m.show() : m.hide())
  }
}

function toggleInterp() {
  showInterp.value = !showInterp.value
  if (interpOverlay) showInterp.value ? interpOverlay.show() : interpOverlay.hide()
}

function rebuildInterp() {
  if (interpOverlay) { interpOverlay.destroy(); interpOverlay = null }
  interpOverlay = createInterpolationOverlay({
    map,
    data: pointsData.map(p => ({ lng: p.longitude, lat: p.latitude, value: p.subsidence })),
    colorFn: (v) => { const m = getSubsidenceColor(v).match(/\d+/g); return m ? m.map(Number) : [0,0,255] },
    baseSigma: interpSigma.value,
    sigmaMultiplier: interpSigmaMult.value,
    maxRadius: interpMaxRadius.value,
    opacity: interpOpacity.value,
    gridStep: interpGridStep.value
  })
  if (showInterp.value) interpOverlay.show()
}
</script>

<template>
  <div class="app-root">
    <!-- 地图容器 -->
    <div ref="mapContainer" class="map-container"></div>

    <!-- 加载遮罩 -->
    <div v-if="loading" class="overlay loading-overlay">
      <div class="spinner"></div>
      <span>地图加载中...</span>
    </div>

    <!-- 错误遮罩 -->
    <div v-if="errorMsg" class="overlay error-overlay">
      <div class="error-box">
        <span class="error-icon">⚠️</span>
        <p>{{ errorMsg }}</p>
      </div>
    </div>

    <!-- 模式切换 -->
    <div v-if="!loading && !errorMsg" class="mode-panel">
      <label class="mode-item" @click="toggleHeatmap">
        <span class="check-box">{{ showHeatmap ? '☑' : '☐' }}</span>
        热力图
      </label>
      <label class="mode-item" @click="toggleScatter">
        <span class="check-box">{{ showScatter ? '☑' : '☐' }}</span>
        散点图
      </label>
      <label class="mode-item" @click="toggleInterp">
        <span class="check-box">{{ showInterp ? '☑' : '☐' }}</span>
        插值图
      </label>
    </div>

    <!-- 插值参数控制 -->
    <div v-if="!loading && !errorMsg" class="control-panel">
      <div class="ctrl-title">插值参数</div>
      <div class="ctrl-row">
        <label>σ: <span>{{ interpSigma }}</span></label>
        <input type="range" v-model.number="interpSigma" min="5" max="80" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>最大搜索核半径倍率: <span>{{ interpSigmaMult }}</span></label>
        <input type="range" v-model.number="interpSigmaMult" min="1" max="6" step="0.5" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>最大搜索半径上限: <span>{{ interpMaxRadius }}</span></label>
        <input type="range" v-model.number="interpMaxRadius" min="100" max="5000" step="100" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>透明度: <span>{{ interpOpacity }}</span></label>
        <input type="range" v-model.number="interpOpacity" min="0.1" max="1" step="0.1" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>采样步长: <span>{{ interpGridStep }}</span>px</label>
        <input type="range" v-model.number="interpGridStep" min="2" max="8" step="1" @change="rebuildInterp">
      </div>
    </div>

    <!-- 图例面板 -->
    <div v-if="!loading && !errorMsg" class="legend">
      <div class="legend-title">沉降强度 (mm)</div>
      <div class="legend-gradient"></div>
      <div class="legend-labels">
        <span>≤-20</span>
        <span>-10</span>
        <span>0</span>
        <span>5</span>
        <span>≥12</span>
      </div>
    </div>

    <!-- 信息面板 -->
    <div v-if="!loading && !errorMsg" class="info-panel">
      <h3>沉降热力图</h3>
      <p>数据点：{{ pointCount.toLocaleString() }} 个</p>
      <p>底图：高德交通图</p>
      <p>放大倍率：{{ currentZoom.toFixed(1) }}x</p>
    </div>

    <!-- 分布直方图 -->
    <div v-if="!loading && !errorMsg" class="histogram-panel">
      <canvas ref="histCanvas" width="220" height="130"></canvas>
    </div>
  </div>
</template>

<style scoped>
.app-root {
  width: 100%;
  height: 100%;
  position: relative;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* ---- 遮罩层 ---- */
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.loading-overlay {
  background: rgba(255, 255, 255, 0.85);
  flex-direction: column;
  gap: 16px;
  font-size: 16px;
  color: #555;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #e0e0e0;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-overlay {
  background: rgba(255, 240, 240, 0.92);
}

.error-box {
  text-align: center;
  color: #c0392b;
  font-size: 16px;
}

.error-icon {
  font-size: 36px;
  display: block;
  margin-bottom: 8px;
}

/* ---- 图例 ---- */
.legend {
  position: absolute;
  bottom: 30px;
  left: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(6px);
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 500;
  user-select: none;
}

.legend-title {
  font-weight: 600;
  font-size: 13px;
  color: #333;
  margin-bottom: 8px;
}

.legend-gradient {
  width: 210px;
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(to right, rgb(75,0,130), rgb(0,0,220), rgb(0,200,0), rgb(255,200,0), rgb(200,0,0));
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}

/* ---- 模式切换 ---- */
.mode-panel {
  position: absolute;
  top: 20px;
  left: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(6px);
  padding: 10px 14px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 500;
  display: flex;
  flex-direction: column;
  gap: 6px;
  user-select: none;
}
.mode-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #444;
  cursor: pointer;
  padding: 2px 0;
}
.mode-item:hover { color: #1677ff; }
.check-box {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

/* ---- 插值参数控制 ---- */
.control-panel {
  position: absolute; top: 120px; left: 20px;
  background: rgba(255,255,255,0.95); backdrop-filter: blur(6px);
  padding: 8px 12px; border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15); z-index: 500;
  font-size: 11px; display: flex; flex-direction: column; gap: 5px;
  user-select: none; min-width: 170px;
}
.ctrl-title { font-weight: 600; font-size: 12px; color: #333; margin-bottom: 2px; }
.ctrl-row { display: flex; flex-direction: column; gap: 1px; }
.ctrl-row label { color: #555; display: flex; justify-content: space-between; }
.ctrl-row input[type=range] { width: 100%; cursor: pointer; accent-color: #1677ff; }

/* ---- 信息面板 ---- */
.info-panel {
  position: absolute;
  top: 20px;
  right: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(6px);
  padding: 12px 18px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 500;
  user-select: none;
}

.info-panel h3 {
  margin: 0 0 6px 0;
  font-size: 16px;
  color: #333;
  font-weight: 600;
}

.info-panel p {
  margin: 3px 0;
  font-size: 13px;
  color: #666;
}

/* ---- 直方图 ---- */
.histogram-panel {
  position: absolute;
  bottom: 30px;
  right: 20px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(6px);
  padding: 6px 8px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 500;
}
</style>
