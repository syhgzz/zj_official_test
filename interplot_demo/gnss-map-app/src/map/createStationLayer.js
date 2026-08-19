const STATUS_COLORS = {
  online: { core: '#00efaa', glow: '#00efaa' },
  offline: { core: '#ff5364', glow: '#ff3148' },
  unknown: { core: '#92a8bd', glow: '#6f879d' },
}

const ICONS = new Map()

function iconForStatus(status) {
  const normalizedStatus = STATUS_COLORS[status] ? status : 'unknown'
  if (ICONS.has(normalizedStatus)) return ICONS.get(normalizedStatus)

  const colors = STATUS_COLORS[normalizedStatus]
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18"><circle cx="9" cy="9" r="8" fill="${colors.glow}" fill-opacity=".18"/><circle cx="9" cy="9" r="5" fill="${colors.core}" fill-opacity=".32" stroke="${colors.core}" stroke-width="1.2"/><circle cx="9" cy="9" r="2.2" fill="#fff"/></svg>`
  const dataUrl = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
  ICONS.set(normalizedStatus, dataUrl)
  return dataUrl
}

export function extractStationFromLayerEvent(event) {
  const candidates = [
    event?.data?.data,
    event?.data?.target,
    event?.marker,
    event?.target,
    event?.data,
  ]

  for (const candidate of candidates) {
    if (!candidate) continue
    if (typeof candidate.getExtData === 'function') {
      const extData = candidate.getExtData()
      if (extData) return extData
    }
    if (candidate.extData) return candidate.extData
    if (Number.isFinite(candidate.longitude) && Number.isFinite(candidate.latitude)) return candidate
  }

  return null
}

export function createStationLayer({ AMap, map, stations, onStationClick }) {
  const layer = new AMap.LabelsLayer({ zIndex: 300, collision: false })
  const markers = stations.map(station => new AMap.LabelMarker({
    position: [station.longitude, station.latitude],
    zIndex: 300,
    icon: {
      type: 'image',
      image: iconForStatus(station.status),
      size: [18, 18],
      anchor: [9, 9],
    },
    extData: station,
  }))

  layer.add(markers)
  const handleClick = event => {
    const station = extractStationFromLayerEvent(event)
    if (station) onStationClick(station)
  }
  layer.on('click', handleClick)
  map.add(layer)

  let destroyed = false
  return {
    layer,
    markerCount: markers.length,
    setVisible(visible) {
      if (destroyed) return
      if (visible) layer.show()
      else layer.hide()
    },
    destroy() {
      if (destroyed) return
      destroyed = true
      layer.off('click', handleClick)
      map.remove(layer)
    },
  }
}
