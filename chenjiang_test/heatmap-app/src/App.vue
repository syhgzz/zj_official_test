<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { createInterpolationOverlay } from './lib/interplot_figure.js'
import protobuf from 'protobufjs'

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
const interpGridStep = ref(2)
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
const interpBlurRadius = ref(1.5)
const interpSigmaMultInf = ref(true)
const interpMaxRadiusInf = ref(false)
const gpuEnabled = ref(true)
const interpMaxNearby = ref(0)
const renderTime = ref(0)
const timingBreakdown = ref({})
const genDataTime = ref(0)
const maxDataPoints = ref(Infinity)
const currentZoom = ref(0)
const showDebug = ref(false)
const debugCount = ref(30)
const dataSource = ref('local') // 'local' | 'http' | 'websocket'
const dataConstruction = ref('json') // 'json' | 'random'
const randomCount = ref(10000)
// Network measurement
const netTime = ref(0)
const netBytes = ref(0)
const netMethod = ref('')
const viewportW = ref(0)
const viewportH = ref(0)
const renderW = ref(0)
const renderH = ref(0)

const histCanvas = ref(null)
const ctrlPanel = ref(null)

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

function genRandom(n, bounds) {
  const swLng = bounds ? bounds.swLng : 120
  const swLat = bounds ? bounds.swLat : 30
  const neLng = bounds ? bounds.neLng : 122
  const neLat = bounds ? bounds.neLat : 32
  const pts = new Array(n)
  for (let i = 0; i < n; i++)
    pts[i] = {
      longitude: swLng + Math.random() * (neLng - swLng),
      latitude: swLat + Math.random() * (neLat - swLat),
      subsidence: (Math.random() - 0.5) * 60
    }
  return pts
}

function getMapBounds() {
  if (!map) return null
  const b = map.getBounds()
  const sw = b.getSouthWest(), ne = b.getNorthEast()
  return { swLng: sw.lng, swLat: sw.lat, neLng: ne.lng, neLat: ne.lat }
}

function zoomRadius(zoom) {
  const r = Math.round(BASE_RADIUS * Math.pow(2, zoom - BASE_ZOOM))
  return Math.max(10, Math.min(600, r))
}

function lerpColor(c0, c1, t) {
  const r = Math.round(c0[0] + (c1[0] - c0[0]) * t)
  const g = Math.round(c0[1] + (c1[1] - c0[1]) * t)
  const b = Math.round(c0[2] + (c1[2] - c0[2]) * t)
  const aa = c0.length > 3 ? c0[3] : 255
  const ba = c1.length > 3 ? c1[3] : 255
  const aChan = Math.round(aa + (ba - aa) * t)
  return aChan < 255 ? [r, g, b, aChan] : [r, g, b]
}

const COLOR_STOPS = [
  [-30, [75, 0, 130, 255]],
  [-20, [0, 0, 180, 255]],
  [-10, [30, 80, 220, 255]],
  [-5,  [80, 160, 240, 255]],
  [-2,  [150, 210, 250, 255]],
  [0,   [0, 200, 0, 255]],
  [3,   [150, 220, 0, 255]],
  [6,   [255, 200, 0, 255]],
  [10,  [255, 140, 0, 255]],
  [15,  [255, 60, 0, 255]],
  [23,  [200, 0, 0, 255]]
]

function getSubsidenceArray(subsidence) {
  const v = Math.max(-30, Math.min(23, subsidence))
  for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
    const [v0, c0] = COLOR_STOPS[i]
    const [v1, c1] = COLOR_STOPS[i + 1]
    if (v <= v1) {
      const t = (v - v0) / (v1 - v0)
      return lerpColor(c0, c1, t)
    }
  }
  return [200, 0, 0, 255]
}

function getSubsidenceColor(subsidence) {
  const c = getSubsidenceArray(subsidence)
  const [r, g, b, a] = c.length === 4 ? c : [...c, 255]
  return a < 255 ? `rgba(${r},${g},${b},${(a / 255).toFixed(3)})` : `rgb(${r},${g},${b})`
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
    window.addEventListener('resize', updateViewportInfo)

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
    // Enable draggable control panel
    setTimeout(() => {
      const el = ctrlPanel.value
      if (!el) return
      const title = el.querySelector('.ctrl-title')
      let dragging = false, ox = 0, oy = 0
      title.style.cursor = 'move'
      title.addEventListener('mousedown', e => {
        dragging = true; ox = e.clientX - el.offsetLeft; oy = e.clientY - el.offsetTop
        e.preventDefault()
      })
      window.addEventListener('mousemove', e => {
        if (!dragging) return
        el.style.left = (e.clientX - ox) + 'px'
        el.style.top = (e.clientY - oy) + 'px'
      })
      window.addEventListener('mouseup', () => { dragging = false })
    }, 500)
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
  if (scatterLayer) {
    showScatter.value ? scatterLayer.setMap(map) : scatterLayer.setMap(null)
  } else {
    massMarks.forEach(m => showScatter.value ? m.show() : m.hide())
  }
}

function toggleInterp() {
  showInterp.value = !showInterp.value
  if (interpOverlay) showInterp.value ? interpOverlay.show() : interpOverlay.hide()
}

// dataSrc: array of {longitude,latitude,subsidence} objects, or {lng:Float32Array,lat:Float32Array,val:Float32Array}
function renderScatter(dataSrc) {
  if (!map) return
  // Resolve data source
  let ptArr, isRaw = false
  if (dataSrc && dataSrc.lng && dataSrc.val) { isRaw = true; ptArr = dataSrc }
  else if (Array.isArray(dataSrc)) ptArr = dataSrc
  else ptArr = pointsData
  const n = isRaw ? ptArr.lng.length : ptArr.length
  if (n > 50000) {
    if (scatterLayer) scatterLayer.setMap(null)
    return
  }
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
  if (isRaw) {
    for (let i = 0; i < n; i++) {
      const pixel = map.lngLatToContainer([ptArr.lng[i], ptArr.lat[i]])
      if (pixel.x < 0 || pixel.x > w || pixel.y < 0 || pixel.y > h) continue
      scatterCtx.fillStyle = getSubsidenceColor(ptArr.val[i])
      scatterCtx.beginPath()
      scatterCtx.arc(pixel.x, pixel.y, 2, 0, Math.PI * 2)
      scatterCtx.fill()
    }
  } else {
    const limit = Math.min(n, maxDataPoints.value)
    for (let i = 0; i < limit; i++) {
      const p = ptArr[i]
      const pixel = map.lngLatToContainer([p.longitude, p.latitude])
      if (pixel.x < 0 || pixel.x > w || pixel.y < 0 || pixel.y > h) continue
      scatterCtx.fillStyle = getSubsidenceColor(p.subsidence)
      scatterCtx.beginPath()
      scatterCtx.arc(pixel.x, pixel.y, 2, 0, Math.PI * 2)
      scatterCtx.fill()
    }
  }
  const imgBounds = map.getBounds()
  scatterCanvas.toBlob(blob => {
    const url = URL.createObjectURL(blob)
    if (scatterLayer) { scatterLayer.setMap(null); URL.revokeObjectURL(scatterLayer._url) }
    scatterLayer = new AMap.ImageLayer({ url, bounds: imgBounds, opacity: 1, zooms: [2, 20] })
    scatterLayer._url = url
    if (showScatter.value) scatterLayer.setMap(map)
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
    if (scatterLayer) scatterLayer.setMap(null)
    generateDebugData()
  } else {
    pointsData = realPointsData
    realPointsData = []
    clearDebugMarkers()
    rebuildAll()
  }
}

function generateDebugData() {
  const t0 = performance.now()
  clearDebugMarkers()
  const bounds = map.getBounds()
  const sw = bounds.getSouthWest(), ne = bounds.getNorthEast()
  const count = debugCount.value
  pointsData = new Array(count)
  for (let i = 0; i < count; i++) {
    pointsData[i] = {
      longitude: sw.lng + Math.random() * (ne.lng - sw.lng),
      latitude: sw.lat + Math.random() * (ne.lat - sw.lat),
      subsidence: (Math.random() - 0.5) * 60
    }
  }
  genDataTime.value = performance.now() - t0
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

  // Reset network measurements
  netTime.value = 0; netBytes.value = 0; netMethod.value = ''

  // Determine data based on source + construction
  let activeData, mappedData
  const isRemote = dataSource.value === 'http' || dataSource.value === 'websocket'

  const mapBounds = getMapBounds()
  if (dataConstruction.value === 'random') {
    // Local random: generate in-browser within map viewport
    activeData = genRandom(randomCount.value, mapBounds)
    mappedData = activeData.map(p => ({ lng: p.longitude, lat: p.latitude, value: p.subsidence }))
    pointCount.value = activeData.length
    if (!showDebug.value) renderScatter(activeData)
  } else {
    // JSON: use locally loaded pointsData
    activeData = pointsData.slice(0, maxDataPoints.value)
    pointCount.value = activeData.length
    if (!showDebug.value) renderScatter(activeData)
    mappedData = activeData.map(p => ({ lng: p.longitude, lat: p.latitude, value: p.subsidence }))
  }

  const overlayOpts = {
    map,
    data: isRemote ? [] : mappedData,
    binaryRawData: null,
    colorFn: (v) => getSubsidenceArray(v),
    algorithm: interpAlgorithm.value, baseSigma: interpSigma.value,
    sigmaMultiplier: interpSigmaMultInf.value ? Infinity : interpSigmaMult.value,
    maxRadius: interpMaxRadiusInf.value ? Infinity : interpMaxRadius.value,
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
    maxNearbyPoints: interpMaxNearby.value,
    onRender: (timings) => {
      renderTime.value = timings.total || 0
      timingBreakdown.value = { ...timings }
      console.log('⏱ 渲染耗时 (ms):',
        'collectPoints:', (timings.main_collectPoints||0).toFixed(1),
        'buildLUT:', (timings.main_buildLUT||0).toFixed(1),
        'postMsg:', (timings.main_postMessage||0).toFixed(1),
        '| GPU_setup:', (timings.gpu_setup||0).toFixed(1),
        'upload:', (timings.gpu_upload||0).toFixed(1),
        'pass1:', (timings.gpu_pass1||0).toFixed(1),
        'pass2:', (timings.gpu_pass2||0).toFixed(1),
        'finish:', (timings.gpu_finish||0).toFixed(1),
        '| blur:', (timings.worker_blur||0).toFixed(1),
        'png:', (timings.worker_png||0).toFixed(1),
        '| imgLayer:', (timings.main_imageLayer||0).toFixed(1),
        '| TOTAL:', (timings.total||0).toFixed(1)
      )
    }
  }

  // ---- Path 1 & 2: LOCAL (json / random) ----
  if (dataSource.value === 'local') {
    const n = mappedData.length
    const rawLng = new Float32Array(n)
    const rawLat = new Float32Array(n)
    const rawVal = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      rawLng[i] = mappedData[i].lng; rawLat[i] = mappedData[i].lat; rawVal[i] = mappedData[i].value
    }
    overlayOpts.binaryRawData = { lng: rawLng, lat: rawLat, val: rawVal }
    interpOverlay = createInterpolationOverlay(overlayOpts)
    if (showInterp.value) interpOverlay.show()
    updateViewportInfo()
    return
  }

  // ---- Path 3 & 4: HTTP ----
  if (dataSource.value === 'http') {
    const source = dataConstruction.value
    const count = randomCount.value
    let url = source === 'json'
      ? 'http://localhost:3456/?source=json'
      : `http://localhost:3456/?source=random&count=${count}`
    // Send viewport bounds for random mode so server generates in-viewport points
    if (source === 'random' && mapBounds) {
      url += `&swLng=${mapBounds.swLng}&swLat=${mapBounds.swLat}&neLng=${mapBounds.neLng}&neLat=${mapBounds.neLat}`
    }
    const t0 = performance.now()
    fetch(url)
      .then(r => r.arrayBuffer()).then(buf => {
        const elapsed = performance.now() - t0
        netTime.value = elapsed
        netBytes.value = buf.byteLength
        netMethod.value = 'HTTP (binary)'
        console.log('🌐 HTTP ' + source + ':', elapsed.toFixed(1), 'ms', buf.byteLength, 'B')
        const c = new Uint32Array(buf, 0, 1)[0]
        pointCount.value = c
        const brd = {
          lng: new Float32Array(buf.slice(4, 4 + c * 4)),
          lat: new Float32Array(buf.slice(4 + c * 4, 4 + c * 8)),
          val: new Float32Array(buf.slice(4 + c * 8, 4 + c * 12))
        }
        overlayOpts.binaryRawData = brd
        interpOverlay = createInterpolationOverlay(overlayOpts)
        if (showInterp.value) interpOverlay.show()
        updateViewportInfo()
        // Render scatter from received raw data
        if (!showDebug.value && c <= 50000) renderScatter(brd)
      })
    return
  }

  // ---- Path 5 & 6: WebSocket + ProtoBuf ----
  if (dataSource.value === 'websocket') {
    const source = dataConstruction.value
    const count = randomCount.value
    const t0 = performance.now()
    const ws = new WebSocket('ws://localhost:3457')
    ws.binaryType = 'arraybuffer'
    const payload = { source, count }
    if (source === 'random' && mapBounds) payload.bounds = mapBounds
    ws.onopen = () => ws.send(JSON.stringify(payload))
    ws.onmessage = async e => {
      const elapsed = performance.now() - t0
      netTime.value = elapsed
      netBytes.value = e.data.byteLength
      netMethod.value = 'WebSocket + ProtoBuf'
      console.log('🔌 WS+ProtoBuf ' + source + ':', elapsed.toFixed(1), 'ms', e.data.byteLength, 'B')
      protobuf.load('/points.proto').then(root => {
        const d = root.lookupType('PointsResponse').decode(new Uint8Array(e.data))
        pointCount.value = d.lng.length
        const brd = {
          lng: new Float32Array(d.lng),
          lat: new Float32Array(d.lat),
          val: new Float32Array(d.val)
        }
        overlayOpts.binaryRawData = brd
        interpOverlay = createInterpolationOverlay(overlayOpts)
        if (showInterp.value) interpOverlay.show()
        updateViewportInfo()
        // Render scatter from received raw data
        if (!showDebug.value && d.lng.length <= 50000) renderScatter(brd)
        ws.close()
      })
    }
    return
  }
}

function updateViewportInfo() {
  const c = mapContainer.value
  if (c) {
    viewportW.value = c.clientWidth
    viewportH.value = c.clientHeight
    renderW.value = Math.ceil(c.clientWidth / interpGridStep.value)
    renderH.value = Math.ceil(c.clientHeight / interpGridStep.value)
  }
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
        <span>点数: </span>
        <input v-model.number="debugCount" min="1" max="99999999" style="width:100px;text-align:center;border:1px solid #ccc;border-radius:4px;padding:2px 4px">
        <button @click="generateDebugData" style="font-size:11px;padding:2px 8px;border:1px solid #1677ff;border-radius:4px;background:#1677ff;color:#fff;cursor:pointer">确定</button>
      </div>
      <div style="border-top:1px solid #ddd;margin:2px 0"></div>
      <div style="font-size:10px;color:#999;margin-bottom:2px">数据来源</div>
      <label class="mode-item" @click="dataSource = 'local'; rebuildAll()">
        <span class="check-box">{{ dataSource === 'local' ? '☑' : '☐' }}</span>
        本地
      </label>
      <label class="mode-item" @click="dataSource = 'http'; rebuildAll()">
        <span class="check-box">{{ dataSource === 'http' ? '☑' : '☐' }}</span>
        HTTP接口
      </label>
      <label class="mode-item" @click="dataSource = 'websocket'; rebuildAll()">
        <span class="check-box">{{ dataSource === 'websocket' ? '☑' : '☐' }}</span>
        WebSocket+ProtoBuf
      </label>
      <div style="border-top:1px solid #ddd;margin:2px 0"></div>
      <div style="font-size:10px;color:#999;margin-bottom:2px">数据构造</div>
      <label class="mode-item" @click="dataConstruction = 'json'; rebuildAll()">
        <span class="check-box">{{ dataConstruction === 'json' ? '☑' : '☐' }}</span>
        读取JSON文件
      </label>
      <label class="mode-item" @click="dataConstruction = 'random'; rebuildAll()">
        <span class="check-box">{{ dataConstruction === 'random' ? '☑' : '☐' }}</span>
        随机生成
      </label>
      <div v-if="dataConstruction === 'random'" class="debug-row">
        <span>点数: </span>
        <input v-model.number="randomCount" min="100" max="99999999" style="width:100px;text-align:center;border:1px solid #ccc;border-radius:4px;padding:2px 4px">
        <button @click="rebuildAll" style="font-size:11px;padding:2px 8px;border:1px solid #1677ff;border-radius:4px;background:#1677ff;color:#fff;cursor:pointer">确定</button>
      </div>
    </div>

    <!-- 插值参数控制 -->
    <div v-if="!loading && !errorMsg" ref="ctrlPanel" class="control-panel">
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
        <label>最大搜索核半径倍率: <span>{{ interpSigmaMultInf ? '∞' : interpSigmaMult }}</span></label>
        <div style="display:flex;align-items:center;gap:4px">
          <input type="range" v-model.number="interpSigmaMult" min="1" max="100" step="1" :disabled="interpSigmaMultInf" @change="rebuildInterp" style="flex:1">
          <label style="white-space:nowrap;font-size:10px;cursor:pointer;user-select:none"><input type="checkbox" v-model="interpSigmaMultInf" @change="rebuildInterp" style="accent-color:#1677ff;vertical-align:middle"> ∞</label>
        </div>
      </div>
      <div class="ctrl-row">
        <label>最大搜索半径上限: <span>{{ interpMaxRadiusInf ? '∞' : interpMaxRadius }}</span></label>
        <div style="display:flex;align-items:center;gap:4px">
          <input type="range" v-model.number="interpMaxRadius" min="100" max="50000" step="500" :disabled="interpMaxRadiusInf" @change="rebuildInterp" style="flex:1">
          <label style="white-space:nowrap;font-size:10px;cursor:pointer;user-select:none"><input type="checkbox" v-model="interpMaxRadiusInf" @change="rebuildInterp" style="accent-color:#1677ff;vertical-align:middle"> ∞</label>
        </div>
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
          GPU加速 (IDW/Gaussian)
        </label>
      </div>
      <div v-if="interpBlurEnabled" class="ctrl-row">
        <label>模糊半径: <span>{{ interpBlurRadius }}</span>px</label>
        <input type="range" v-model.number="interpBlurRadius" min="0.5" max="20" step="0.5" @change="rebuildAll">
      </div>
      <div class="ctrl-row">
        <label>每像素最多点数: <span>{{ interpMaxNearby || '无限制' }}</span></label>
        <input type="range" v-model.number="interpMaxNearby" min="0" max="5000" step="50" @change="rebuildInterp">
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
      <p>底图：高德交通图</p>
      <p>放大倍率：{{ currentZoom.toFixed(1) }}x</p>
      <p>视口：{{ viewportW }} × {{ viewportH }}</p>
      <p>渲染分辨率：{{ renderW }} × {{ renderH }} (gridStep={{ interpGridStep }})</p>
      <p>渲染耗时：{{ renderTime.toFixed(0) }} ms</p>
      <p v-if="genDataTime">生成数据：{{ genDataTime.toFixed(0) }} ms</p>
      <p v-if="netTime > 0" style="color:#1677ff">网络传输：{{ netMethod }}，{{ netTime.toFixed(0) }} ms，{{ (netBytes/1024).toFixed(1) }} KB</p>
      <div v-if="timingBreakdown.total" style="font-size:10px;line-height:1.4;margin-top:4px;max-height:200px;overflow-y:auto;background:#f5f5f5;padding:4px 6px;border-radius:4px">
        <div>main_collectPoints: {{ (timingBreakdown.main_collectPoints||0).toFixed(1) }}ms</div>
        <div>main_buildLUT: {{ (timingBreakdown.main_buildLUT||0).toFixed(1) }}ms</div>
        <div>main_postMessage: {{ (timingBreakdown.main_postMessage||0).toFixed(1) }}ms</div>
        <div style="color:#1677ff">GPU_setup: {{ (timingBreakdown.gpu_setup||0).toFixed(1) }}ms</div>
        <div style="color:#1677ff">GPU_upload: {{ (timingBreakdown.gpu_upload||0).toFixed(1) }}ms</div>
        <div style="color:#1677ff">GPU_pass1: {{ (timingBreakdown.gpu_pass1||0).toFixed(1) }}ms</div>
        <div style="color:#1677ff">GPU_pass2: {{ (timingBreakdown.gpu_pass2||0).toFixed(1) }}ms</div>
        <div style="color:#1677ff">GPU_finish: {{ (timingBreakdown.gpu_finish||0).toFixed(1) }}ms</div>
        <div>worker_blur: {{ (timingBreakdown.worker_blur||0).toFixed(1) }}ms</div>
        <div style="color:#cf1322">worker_png: {{ (timingBreakdown.worker_png||0).toFixed(1) }}ms</div>
        <div>main_imageLayer: {{ (timingBreakdown.main_imageLayer||0).toFixed(1) }}ms</div>
      </div>
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
  position: absolute; top: 420px; left: 20px;
  background: rgba(255,255,255,0.95); backdrop-filter: blur(6px);
  padding: 8px 12px; border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.15); z-index: 500;
  font-size: 11px; display: flex; flex-direction: column; gap: 5px;
  user-select: none; min-width: 170px;
}
.ctrl-title { font-weight: 600; font-size: 12px; color: #333; margin-bottom: 2px; cursor: move; }
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
