<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'

import { normalizeStations } from './data/normalizeStations.js'
import { createStationLayer } from './map/createStationLayer.js'
import { escapeHtml, formatTimestamp } from './ui/formatStation.js'

const DEFAULT_AMAP_KEY = '244262d7f08882349099fad8cd2ae0cc'
const CHONGQING_CENTER = [106.58, 29.563]

const mapContainer = ref(null)
const loading = ref(true)
const reloading = ref(false)
const errorMessage = ref('')
const mode = ref('raw')
const layerVisible = ref(true)
const currentPointCount = ref(0)
const currentZoom = ref(10)
const stats = ref({
  reportedTotal: 0,
  rawCount: 0,
  validCount: 0,
  uniqueCount: 0,
  duplicateCount: 0,
  invalidCoordinateCount: 0,
  onlineCount: 0,
  offlineCount: 0,
  unknownCount: 0,
})
const modeStatusCounts = ref({ online: 0, offline: 0, unknown: 0 })
const metadata = ref({})
const timings = ref({ fetch: 0, normalize: 0, layer: 0 })

let AMap = null
let map = null
let infoWindow = null
let layerController = null
let normalized = { raw: [], unique: [] }

const isRawMode = computed(() => mode.value === 'raw')
const modeLabel = computed(() => isRawMode.value ? '原始记录' : '唯一站点')

function milliseconds(value) {
  return `${Number(value || 0).toFixed(1)} ms`
}

function countStatuses(stations) {
  return stations.reduce((counts, station) => {
    counts[station.status] += 1
    return counts
  }, { online: 0, offline: 0, unknown: 0 })
}

function numberText(value, digits = 2) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '--'
}

function statusText(status) {
  return { online: '在线', offline: '离线', unknown: '未知' }[status] || '未知'
}

function stationInfoMarkup(station) {
  const signalRatio = station.signalQuality?.avgNoiseRatio
  const beidouCount = station.satelliteCount?.bdCount
  const rows = [
    ['站点编码', station.stationCode || '--'],
    ['运行状态', statusText(station.status)],
    ['原始经度', numberText(station.sourceLongitude, 6)],
    ['原始纬度', numberText(station.sourceLatitude, 6)],
    ['高程', `${numberText(station.alt, 2)} m`],
    ['延迟', `${numberText(station.delay, 1)} ms`],
    ['北斗卫星', Number.isFinite(Number(beidouCount)) ? `${Number(beidouCount)} 颗` : '--'],
    ['平均信噪比', numberText(signalRatio, 1)],
    ['更新时间', formatTimestamp(station.lastUpdateTime)],
  ]
  const content = rows.map(([label, value]) => (
    `<div class="station-popup__row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`
  )).join('')

  return `<div class="station-popup station-popup--${station.status}"><div class="station-popup__header"><span class="station-popup__pulse"></span><div><small>GNSS STATION</small><h3>${escapeHtml(station.stationName)}</h3></div><button class="station-popup__close" type="button" onclick="window.__closeGnssStationInfo?.()" aria-label="关闭">×</button></div><div class="station-popup__body">${content}</div></div>`
}

function openStationInfo(station) {
  if (!map || !infoWindow) return
  infoWindow.setContent(stationInfoMarkup(station))
  infoWindow.open(map, [station.longitude, station.latitude])
}

function closeStationInfo() {
  infoWindow?.close()
}

function rebuildLayer() {
  if (!AMap || !map) return
  closeStationInfo()
  layerController?.destroy()
  const activeStations = isRawMode.value ? normalized.raw : normalized.unique
  const startedAt = performance.now()
  layerController = createStationLayer({
    AMap,
    map,
    stations: activeStations,
    onStationClick: openStationInfo,
  })
  timings.value.layer = performance.now() - startedAt
  currentPointCount.value = layerController.markerCount
  modeStatusCounts.value = countStatuses(activeStations)
  layerController.setVisible(layerVisible.value)
}

async function fetchAndNormalize() {
  const fetchStartedAt = performance.now()
  const response = await fetch(`/data/gnss-stations.json?time=${Date.now()}`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`站点数据请求失败（HTTP ${response.status}）`)
  const payload = await response.json()
  timings.value.fetch = performance.now() - fetchStartedAt
  if (!Array.isArray(payload?.stations)) throw new Error('站点数据格式不正确：缺少 stations 数组')

  const normalizeStartedAt = performance.now()
  normalized = normalizeStations(payload.stations, payload.meta?.reportedTotal)
  timings.value.normalize = performance.now() - normalizeStartedAt
  stats.value = normalized.stats
  metadata.value = payload.meta || {}
}

async function initialize() {
  loading.value = true
  errorMessage.value = ''
  try {
    const dataPromise = fetchAndNormalize()
    const amapPromise = AMapLoader.load({
      key: import.meta.env.VITE_AMAP_KEY || DEFAULT_AMAP_KEY,
      version: '2.0',
    })
    const [, loadedAmap] = await Promise.all([dataPromise, amapPromise])
    AMap = loadedAmap

    map = new AMap.Map(mapContainer.value, {
      center: CHONGQING_CENTER,
      zoom: 10,
      resizeEnable: true,
      layers: [
        new AMap.TileLayer.Satellite(),
        new AMap.TileLayer.RoadNet(),
      ],
    })
    currentZoom.value = map.getZoom()
    map.on('zoomchange', updateZoom)
    infoWindow = new AMap.InfoWindow({
      isCustom: true,
      offset: new AMap.Pixel(0, -12),
      closeWhenClickMap: true,
    })
    window.__closeGnssStationInfo = closeStationInfo
    rebuildLayer()
  } catch (error) {
    errorMessage.value = error?.message || '地图初始化失败'
  } finally {
    loading.value = false
  }
}

async function reloadData() {
  if (reloading.value) return
  reloading.value = true
  errorMessage.value = ''
  try {
    await fetchAndNormalize()
    rebuildLayer()
  } catch (error) {
    errorMessage.value = error?.message || '重新加载失败'
  } finally {
    reloading.value = false
  }
}

function setMode(nextMode) {
  if (mode.value === nextMode) return
  mode.value = nextMode
  rebuildLayer()
}

function toggleLayer() {
  layerVisible.value = !layerVisible.value
  layerController?.setVisible(layerVisible.value)
  if (!layerVisible.value) closeStationInfo()
}

function updateZoom() {
  if (map) currentZoom.value = map.getZoom()
}

onMounted(initialize)

onBeforeUnmount(() => {
  delete window.__closeGnssStationInfo
  layerController?.destroy()
  layerController = null
  infoWindow?.close()
  infoWindow = null
  if (map) {
    map.off('zoomchange', updateZoom)
    map.destroy()
    map = null
  }
  AMap = null
})
</script>

<template>
  <main class="dashboard-shell">
    <div ref="mapContainer" class="map-canvas" aria-label="GNSS 卫星站点分布地图"></div>
    <div class="map-shade"></div>

    <header class="dashboard-title">
      <span class="dashboard-title__wing"></span>
      <div>
        <p>GNSS DEVICE MONITOR</p>
        <h1>卫星站点分布测试</h1>
      </div>
      <span class="dashboard-title__wing dashboard-title__wing--right"></span>
    </header>

    <section v-if="!loading" class="glass-panel control-panel" aria-label="地图控制">
      <div class="panel-heading">
        <div>
          <small>MAP CONTROLS</small>
          <h2>卫星图层</h2>
        </div>
        <span class="live-dot" :class="{ 'live-dot--off': !layerVisible }"></span>
      </div>

      <div class="segmented-control" aria-label="数据模式">
        <button :class="{ active: mode === 'raw' }" type="button" @click="setMode('raw')">原始记录</button>
        <button :class="{ active: mode === 'unique' }" type="button" @click="setMode('unique')">唯一站点</button>
      </div>

      <button class="action-button" type="button" @click="toggleLayer">
        <span>{{ layerVisible ? '●' : '○' }}</span>{{ layerVisible ? '隐藏卫星状态' : '显示卫星状态' }}
      </button>
      <button class="action-button action-button--secondary" type="button" :disabled="reloading" @click="reloadData">
        <span :class="{ rotating: reloading }">↻</span>{{ reloading ? '正在重新加载' : '重新加载数据' }}
      </button>

      <div class="source-note" :title="metadata.sourceFile">
        <span>数据源</span>
        <strong>{{ metadata.sourceFile || '--' }}</strong>
      </div>
    </section>

    <section v-if="!loading" class="glass-panel status-panel" aria-label="卫星分布状态">
      <div class="panel-heading">
        <div>
          <small>DEVICE STATUS</small>
          <h2>卫星分布状态</h2>
        </div>
        <span class="mode-badge">{{ modeLabel }}</span>
      </div>

      <div class="status-grid">
        <article class="status-card status-card--online">
          <span class="status-card__icon">●</span>
          <strong>{{ modeStatusCounts.online.toLocaleString() }}</strong>
          <small>在线</small>
        </article>
        <article class="status-card status-card--offline">
          <span class="status-card__icon">●</span>
          <strong>{{ modeStatusCounts.offline.toLocaleString() }}</strong>
          <small>离线</small>
        </article>
        <article class="status-card status-card--unknown">
          <span class="status-card__icon">●</span>
          <strong>{{ modeStatusCounts.unknown.toLocaleString() }}</strong>
          <small>未知</small>
        </article>
      </div>

      <dl class="statistics-list">
        <div><dt>接口报告总数</dt><dd>{{ stats.reportedTotal.toLocaleString() }}</dd></div>
        <div><dt>JSON 原始行数</dt><dd>{{ stats.rawCount.toLocaleString() }}</dd></div>
        <div><dt>唯一站点编码</dt><dd>{{ stats.uniqueCount.toLocaleString() }}</dd></div>
        <div><dt>跨页重复行</dt><dd class="warning-text">{{ stats.duplicateCount.toLocaleString() }}</dd></div>
        <div><dt>无效坐标</dt><dd>{{ stats.invalidCoordinateCount.toLocaleString() }}</dd></div>
        <div class="statistics-list__primary"><dt>当前图层点数</dt><dd>{{ currentPointCount.toLocaleString() }}</dd></div>
      </dl>
    </section>

    <aside class="legend-panel" aria-label="图例">
      <span><i class="legend-dot legend-dot--online"></i>在线</span>
      <span><i class="legend-dot legend-dot--offline"></i>离线</span>
      <span><i class="legend-dot legend-dot--unknown"></i>未知</span>
    </aside>

    <footer v-if="!loading" class="performance-strip">
      <span>ZOOM <strong>{{ currentZoom.toFixed(1) }}</strong></span>
      <span>数据读取 <strong>{{ milliseconds(timings.fetch) }}</strong></span>
      <span>坐标与去重 <strong>{{ milliseconds(timings.normalize) }}</strong></span>
      <span>图层创建 <strong>{{ milliseconds(timings.layer) }}</strong></span>
      <span class="performance-strip__rows">已加载 <strong>{{ currentPointCount.toLocaleString() }}</strong> 点</span>
    </footer>

    <div v-if="loading" class="screen-overlay loading-overlay">
      <div class="radar-loader"><span></span></div>
      <strong>正在装载卫星站点</strong>
      <small>读取站点数据并创建批量图层</small>
    </div>

    <div v-if="errorMessage" class="error-toast" role="alert">
      <div><strong>加载异常</strong><p>{{ errorMessage }}</p></div>
      <button type="button" @click="map ? reloadData() : initialize()">重试</button>
    </div>
  </main>
</template>
