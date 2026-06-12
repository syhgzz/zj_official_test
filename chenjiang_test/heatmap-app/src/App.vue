<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'

const mapContainer = ref(null)
const loading = ref(true)
const errorMsg = ref(null)
const pointCount = ref(0)

let map = null
let heatmap = null

const DATA_URL = '/data/3.4.5_沉降地图（热力图）_api_v1_upss_statistics_regional_20250110.json'
const AMAP_KEY = '244262d7f08882349099fad8cd2ae0cc'
const BASE_ZOOM = 11
const BASE_RADIUS = 30

function zoomRadius(zoom) {
  const r = Math.round(BASE_RADIUS * Math.pow(2, zoom - BASE_ZOOM))
  return Math.max(10, Math.min(600, r))
}

onMounted(async () => {
  try {
    // 1. Load JSON data
    const response = await fetch(DATA_URL)
    if (!response.ok) throw new Error(`数据加载失败 (HTTP ${response.status})`)
    const json = await response.json()
    const points = json?.response?.data?.points || []
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

    // 6. Prepare heatmap data：sqrt 变换拉伸低值区层次
    const heatmapData = points.map(p => ({
      lng: p.longitude,
      lat: p.latitude,
      count: Math.sqrt(Math.max(0, p.subsidence))
    }))

    // 7. Create heatmap layer（2D）
    heatmap = new AMap.HeatMap(map, {
      radius: BASE_RADIUS,
      opacity: [0, 0.8],
      gradient: {
        0: 'blue',
        0.2: 'green',
        0.5: 'yellow',
        1: 'red'
      },
      zooms: [3, 18]
    })

    // 8. Set heatmap data with max=sqrt(25)=5（≤0→蓝, ~1→绿, ~6→黄, ≥25→红）
    heatmap.setDataSet({
      data: heatmapData,
      max: 5
    })

    // 动态调整热力图半径，保持地理覆盖范围不随缩放变化（zoomchange 实现平滑过渡）
    map.on('zoomchange', () => {
      if (heatmap) {
        heatmap.setOptions({ radius: zoomRadius(map.getZoom()) })
      }
    })

    loading.value = false
  } catch (err) {
    errorMsg.value = err.message || '未知错误'
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (heatmap) {
    heatmap.setMap(null)
    heatmap = null
  }
  if (map) {
    map.destroy()
    map = null
  }
})
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

    <!-- 图例面板 -->
    <div v-if="!loading && !errorMsg" class="legend">
      <div class="legend-title">沉降强度 (mm)</div>
      <div class="legend-gradient"></div>
      <div class="legend-labels">
        <span>≤0</span>
        <span>1</span>
        <span>6</span>
        <span>≥25</span>
      </div>
    </div>

    <!-- 信息面板 -->
    <div v-if="!loading && !errorMsg" class="info-panel">
      <h3>沉降热力图</h3>
      <p>数据点：{{ pointCount.toLocaleString() }} 个</p>
      <p>底图：高德交通图</p>
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
  background: linear-gradient(to right, blue, green, yellow, red);
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: #888;
}

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
</style>
