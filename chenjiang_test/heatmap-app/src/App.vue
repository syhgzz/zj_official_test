<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { createInterpolationOverlay } from './lib/interplot_figure.js'

const mapContainer = ref(null)
const loading = ref(true)
const errorMsg = ref(null)
const pointCount = ref(0)
const showHeatmap = ref(false)
const showScatter = ref(true)
const showInterp = ref(true)
const interpSigma = ref(25)
const interpSigmaMult = ref(3)
const interpMaxRadius = ref(20000)
const interpOpacity = ref(0.6)
const interpGridStep = ref(4)
const interpAlgorithm = ref('idw')
const interpIdwPower = ref(3.5)
const interpIdwEps = ref(0.1)
const interpRbfType = ref('thinPlate')
const interpRbfSmooth = ref(0)
const interpKrModel = ref('exponential')
const interpKrNugget = ref(0)
const interpKrRange = ref(200)
const interpKrSill = ref(1)
const interpRadiusJitter = ref(false)
const interpMCSamples = ref(2)
const interpMCJitterFactor = ref(0.2)
const interpBlurEnabled = ref(false)
const interpBlurRadius = ref(3)
const gpuEnabled = ref(true)
const renderTime = ref(0)
const maxDataPoints = ref(10000)
const currentZoom = ref(0)
const showDebug = ref(false)
const debugCount = ref(30)

const histCanvas = ref(null)

let map = null
let heatmap = null
let massMarks = []
let interpOverlay = null
let pointsData = []
let realPointsData = []
let debugMarkers = []
let scatterCanvas = null, scatterCtx = null, scatterLayer = null, scatterTimer = null

const dataUrlMap = import.meta.glob('./data/*.json', { query: '?url', eager: true, import: 'default' })
const DATA_FILES = Object.values(dataUrlMap)
const AMAP_KEY = '244262d7f08882349099fad8cd2ae0cc'
const BASE_ZOOM = 11
const BASE_RADIUS = 30

function zoomRadius(zoom) {
  const r = Math.round(BASE_RADIUS * Math.pow(2, zoom - BASE_ZOOM))
  return Math.max(10, Math.min(600, r))
}

function lerpColor(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t)
  ]
}

const COLOR_STOPS = [
  [-30, [75, 0, 130]],
  [-20, [0, 0, 180]],
  [-10, [30, 80, 220]],
  [-5,  [80, 160, 240]],
  [-2,  [150, 210, 250]],
  [0,   [0, 200, 0]],
  [3,   [150, 220, 0]],
  [6,   [255, 200, 0]],
  [10,  [255, 140, 0]],
  [15,  [255, 60, 0]],
  [23,  [200, 0, 0]]
]

function getSubsidenceColor(subsidence) {
  const v = Math.max(-30, Math.min(23, subsidence))
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const [v0, c0] = COLOR_STOPS[i]
    const [v1, c1] = COLOR_STOPS[i + 1]
    if (v <= v1) {
      const t = (v - v0) / (v1 - v0)
      const [r, g, b] = lerpColor(c0, c1, t)
      return `rgb(${r},${g},${b})`
    }
  }
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
      scheduleScatterRender()
    })
    map.on('moveend', scheduleScatterRender)
    currentZoom.value = map.getZoom()

    // 9. 初始化数据并构建全部图层
    pointsData = points
    realPointsData = points
    rebuildAll()

    // 10. 绘制分布直方图
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
  if (massMarks) { massMarks.forEach(m => m.setMap(null)); massMarks = [] }
  clearDebugMarkers()
  if (interpOverlay) { interpOverlay.destroy(); interpOverlay = null }
  if (map) { map.destroy(); map = null }
})

function toggleHeatmap() {
  showHeatmap.value = !showHeatmap.value
  if (heatmap) showHeatmap.value ? heatmap.show() : heatmap.hide()
}

function toggleScatter() {
  showScatter.value = !showScatter.value
  if (showDebug.value) {
    debugMarkers.forEach(m => showScatter.value ? m.show() : m.hide())
  } else if (scatterLayer) {
    showScatter.value ? scatterLayer.setMap(map) : scatterLayer.setMap(null)
  } else {
    massMarks.forEach(m => showScatter.value ? m.show() : m.hide())
  }
}

function toggleInterp() {
  showInterp.value = !showInterp.value
  if (interpOverlay) showInterp.value ? interpOverlay.show() : interpOverlay.hide()
}

function renderScatter() {
  if (!map || showDebug.value) return
  const container = mapContainer.value
  if (!container) return
  const w = container.clientWidth, h = container.clientHeight
  if (!w || !h) return
  if (!scatterCanvas) {
    scatterCanvas = document.createElement('canvas')
    scatterCtx = scatterCanvas.getContext('2d')
  }
  scatterCanvas.width = w; scatterCanvas.height = h
  scatterCtx.clearRect(0, 0, w, h)
  const activeData = pointsData.slice(0, maxDataPoints.value)
  for (const p of activeData) {
    const pixel = map.lngLatToContainer([p.longitude, p.latitude])
    if (pixel.x < 0 || pixel.x > w || pixel.y < 0 || pixel.y > h) continue
    scatterCtx.fillStyle = getSubsidenceColor(p.subsidence)
    scatterCtx.beginPath()
    scatterCtx.arc(pixel.x, pixel.y, 2, 0, Math.PI * 2)
    scatterCtx.fill()
  }
  const bounds = map.getBounds()
  scatterCanvas.toBlob(blob => {
    const url = URL.createObjectURL(blob)
    if (scatterLayer) { scatterLayer.setMap(null); URL.revokeObjectURL(scatterLayer._url) }
    scatterLayer = new AMap.ImageLayer({ url, bounds, opacity: 1, zooms: [2, 20] })
    scatterLayer._url = url
    if (showScatter.value && !showDebug.value) scatterLayer.setMap(map)
  }, 'image/png')
}

function scheduleScatterRender() {
  clearTimeout(scatterTimer)
  scatterTimer = setTimeout(renderScatter, 200)
}

function rebuildInterp() {
  rebuildAll()
}

function toggleDebug() {
  showDebug.value = !showDebug.value
  if (showDebug.value) {
    realPointsData = pointsData
    generateDebugData()
  } else {
    pointsData = realPointsData
    realPointsData = []
    clearDebugMarkers()
    rebuildAll()
  }
}

function generateDebugData() {
  clearDebugMarkers()
  const bounds = map.getBounds()
  const sw = bounds.getSouthWest(), ne = bounds.getNorthEast()
  pointsData = []
  for (let i = 0; i < debugCount.value; i++) {
    const lng = sw.lng + Math.random() * (ne.lng - sw.lng)
    const lat = sw.lat + Math.random() * (ne.lat - sw.lat)
    const subsidence = (Math.random() - 0.5) * 60
    pointsData.push({ longitude: lng, latitude: lat, subsidence })
  }
  rebuildAll()
}

function clearDebugMarkers() {
  debugMarkers.forEach(m => m.setMap(null))
  debugMarkers = []
}

function rebuildAll() {
  massMarks.forEach(m => m.setMap(null))
  massMarks = []
  if (interpOverlay) { interpOverlay.destroy(); interpOverlay = null }
  clearDebugMarkers()
  const activeData = pointsData.slice(0, maxDataPoints.value)
  pointCount.value = activeData.length

  if (showDebug.value) {
    const color = (v) => getSubsidenceColor(v)
    debugMarkers = activeData.map(p => {
      const el = document.createElement('div')
      el.style.cssText = `width:12px;height:12px;border-radius:50%;background:${color(p.subsidence)};border:2px solid #fff;cursor:grab`
      const m = new AMap.Marker({
        position: [p.longitude, p.latitude], content: el,
        draggable: true, zIndex: 25, offset: new AMap.Pixel(-6, -6)
      })
      m.on('dragend', (e) => {
        const pos = e.target.getPosition()
        p.longitude = pos.lng; p.latitude = pos.lat
        rebuildAll()
      })
      if (showScatter.value) m.setMap(map); else { m.setMap(map); m.hide() }
      return m
    })
  } else {
    renderScatter()
  }

  interpOverlay = createInterpolationOverlay({
    map,
    data: activeData.map(p => ({ lng: p.longitude, lat: p.latitude, value: p.subsidence })),
    colorFn: (v) => { const m = getSubsidenceColor(v).match(/\d+/g); return m ? m.map(Number) : [0,0,255] },
    algorithm: interpAlgorithm.value, baseSigma: interpSigma.value,
    sigmaMultiplier: interpSigmaMult.value, maxRadius: interpMaxRadius.value,
    opacity: interpOpacity.value, gridStep: interpGridStep.value,
    idwPower: interpIdwPower.value, idwEpsilon: interpIdwEps.value,
    rbfType: interpRbfType.value, rbfSmooth: interpRbfSmooth.value,
    krigingModel: interpKrModel.value, krigingNugget: interpKrNugget.value,
    krigingRange: interpKrRange.value, krigingSill: interpKrSill.value,
    radiusJitter: interpRadiusJitter.value,
    mcSamples: interpMCSamples.value,
    mcJitterFactor: interpMCJitterFactor.value,
    blurEnabled: interpBlurEnabled.value,
    blurRadius: interpBlurRadius.value,
    gpuEnabled: gpuEnabled.value,
    onRender: (ms) => { renderTime.value = ms }
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
      <div style="border-top:1px solid #ddd;margin:2px 0"></div>
      <label class="mode-item" @click="toggleDebug">
        <span class="check-box">{{ showDebug ? '☑' : '☐' }}</span>
        调试模式
      </label>
      <div v-if="showDebug" class="debug-row">
        <span>点数: {{ debugCount }}</span>
        <input type="range" v-model.number="debugCount" min="5" max="200" @change="generateDebugData" style="width:80px">
      </div>
    </div>

    <!-- 插值参数控制 -->
    <div v-if="!loading && !errorMsg" class="control-panel">
      <div class="ctrl-title">插值参数</div>
      <div class="ctrl-row">
        <label>算法:</label>
        <select v-model="interpAlgorithm" @change="rebuildInterp" style="width:100%">
          <option value="gaussian">Gaussian 高斯核</option>
          <option value="idw">IDW 反距离加权</option>
          <option value="rbf">RBF 径向基函数</option>
          <option value="kriging">Kriging 克里金</option>
        </select>
      </div>
      <div class="ctrl-row">
        <label>σ: <span>{{ interpSigma }}</span></label>
        <input type="range" v-model.number="interpSigma" min="5" max="80" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>最大搜索核半径倍率: <span>{{ interpSigmaMult }}</span></label>
        <input type="range" v-model.number="interpSigmaMult" min="1" max="100" step="1" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>最大搜索半径上限: <span>{{ interpMaxRadius }}</span></label>
        <input type="range" v-model.number="interpMaxRadius" min="100" max="50000" step="500" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>透明度: <span>{{ interpOpacity }}</span></label>
        <input type="range" v-model.number="interpOpacity" min="0.1" max="1" step="0.1" @change="rebuildInterp">
      </div>
      <div class="ctrl-row">
        <label>采样步长: <span>{{ interpGridStep }}</span>px</label>
        <input type="range" v-model.number="interpGridStep" min="1" max="8" step="1" @change="rebuildAll">
      </div>
      <div class="ctrl-row">
        <label>
          <input type="checkbox" v-model="interpRadiusJitter" @change="rebuildAll" style="accent-color:#1677ff">
          半径蒙特卡洛
        </label>
      </div>
      <div v-if="interpRadiusJitter" class="ctrl-row">
        <label>MC样本: <span>{{ interpMCSamples }}</span></label>
        <input type="range" v-model.number="interpMCSamples" min="0" max="16" step="1" @change="rebuildAll">
      </div>
      <div v-if="interpRadiusJitter" class="ctrl-row">
        <label>抖动幅度: <span>{{ interpMCJitterFactor }}</span></label>
        <input type="range" v-model.number="interpMCJitterFactor" min="0" max="1" step="0.05" @change="rebuildAll">
      </div>
      <div class="ctrl-row">
        <label>
          <input type="checkbox" v-model="interpBlurEnabled" @change="rebuildAll" style="accent-color:#1677ff">
          GPU高斯模糊
        </label>
      </div>
      <div class="ctrl-row">
        <label>
          <input type="checkbox" v-model="gpuEnabled" @change="rebuildAll" style="accent-color:#1677ff">
          GPU加速 (IDW)
        </label>
      </div>
      <div v-if="interpBlurEnabled" class="ctrl-row">
        <label>模糊半径: <span>{{ interpBlurRadius }}</span>px</label>
        <input type="range" v-model.number="interpBlurRadius" min="1" max="20" step="0.5" @change="rebuildAll">
      </div>
      <div v-if="interpAlgorithm === 'idw'" class="ctrl-row">
        <label>幂: <span>{{ interpIdwPower }}</span></label>
        <input type="range" v-model.number="interpIdwPower" min="1" max="6" step="0.5" @change="rebuildInterp">
      </div>
      <div v-if="interpAlgorithm === 'idw'" class="ctrl-row">
        <label>ε: <span>{{ interpIdwEps }}</span></label>
        <input type="range" v-model.number="interpIdwEps" min="0.01" max="2" step="0.01" @change="rebuildInterp">
      </div>
      <div v-if="interpAlgorithm === 'rbf'" class="ctrl-row">
        <label>核:</label>
        <select v-model="interpRbfType" @change="rebuildInterp" style="width:100%">
          <option value="thinPlate">Thin Plate Spline</option>
          <option value="multiquadric">Multiquadric</option>
          <option value="gaussian">Gaussian RBF</option>
        </select>
      </div>
      <div v-if="interpAlgorithm === 'rbf'" class="ctrl-row">
        <label>平滑: <span>{{ interpRbfSmooth }}</span></label>
        <input type="range" v-model.number="interpRbfSmooth" min="0" max="10" step="0.5" @change="rebuildInterp">
      </div>
      <div v-if="interpAlgorithm === 'kriging'" class="ctrl-row">
        <label>模型:</label>
        <select v-model="interpKrModel" @change="rebuildInterp" style="width:100%">
          <option value="exponential">Exponential 指数</option>
          <option value="spherical">Spherical 球状</option>
          <option value="gaussian">Gaussian 高斯</option>
        </select>
      </div>
      <div v-if="interpAlgorithm === 'kriging'" class="ctrl-row">
        <label>块金: <span>{{ interpKrNugget }}</span></label>
        <input type="range" v-model.number="interpKrNugget" min="0" max="5" step="0.1" @change="rebuildInterp">
      </div>
      <div v-if="interpAlgorithm === 'kriging'" class="ctrl-row">
        <label>变程: <span>{{ interpKrRange }}</span></label>
        <input type="range" v-model.number="interpKrRange" min="50" max="800" step="50" @change="rebuildInterp">
      </div>
      <div v-if="interpAlgorithm === 'kriging'" class="ctrl-row">
        <label>基台: <span>{{ interpKrSill }}</span></label>
        <input type="range" v-model.number="interpKrSill" min="1" max="50" step="1" @change="rebuildInterp">
      </div>
    </div>

    <!-- 信息面板 -->
    <div v-if="!loading && !errorMsg" class="info-panel">
      <h3>沉降热力图</h3>
      <p>数据点：{{ pointCount.toLocaleString() }} 个</p>
      <p>
        显示前
        <input type="range" v-model.number="maxDataPoints" min="1" max="10000" step="100" @change="rebuildAll"
          style="width:120px;vertical-align:middle;margin:0 4px">
        {{ maxDataPoints }} 个
      </p>
      <p>底图：高德交通图</p>
      <p>放大倍率：{{ currentZoom.toFixed(1) }}x</p>
      <p>渲染耗时：{{ renderTime.toFixed(0) }} ms</p>
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
.debug-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #555; padding-left: 26px;
}
.debug-row input {
  border: 1px solid #ccc; border-radius: 4px;
  padding: 1px 4px; text-align: center;
}
.check-box {
  font-size: 16px;
  width: 20px;
  text-align: center;
}

/* ---- 插值参数控制 ---- */
.control-panel {
  position: absolute; top: 190px; left: 20px;
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
