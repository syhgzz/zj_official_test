const EARTH_AXIS = 6378245.0
const ECCENTRICITY_SQUARED = 0.00669342162296594323
const STATUS_RANK = { unknown: 0, offline: 1, online: 2 }

function outsideChina(longitude, latitude) {
  return longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271
}

function transformLatitude(longitude, latitude) {
  let result = -100 + 2 * longitude + 3 * latitude + 0.2 * latitude * latitude
  result += 0.1 * longitude * latitude + 0.2 * Math.sqrt(Math.abs(longitude))
  result += (20 * Math.sin(6 * longitude * Math.PI) + 20 * Math.sin(2 * longitude * Math.PI)) * 2 / 3
  result += (20 * Math.sin(latitude * Math.PI) + 40 * Math.sin(latitude / 3 * Math.PI)) * 2 / 3
  result += (160 * Math.sin(latitude / 12 * Math.PI) + 320 * Math.sin(latitude * Math.PI / 30)) * 2 / 3
  return result
}

function transformLongitude(longitude, latitude) {
  let result = 300 + longitude + 2 * latitude + 0.1 * longitude * longitude
  result += 0.1 * longitude * latitude + 0.1 * Math.sqrt(Math.abs(longitude))
  result += (20 * Math.sin(6 * longitude * Math.PI) + 20 * Math.sin(2 * longitude * Math.PI)) * 2 / 3
  result += (20 * Math.sin(longitude * Math.PI) + 40 * Math.sin(longitude / 3 * Math.PI)) * 2 / 3
  result += (150 * Math.sin(longitude / 12 * Math.PI) + 300 * Math.sin(longitude / 30 * Math.PI)) * 2 / 3
  return result
}

export function wgs84ToGcj02(longitude, latitude) {
  if (outsideChina(longitude, latitude)) return [longitude, latitude]

  let latitudeDelta = transformLatitude(longitude - 105, latitude - 35)
  let longitudeDelta = transformLongitude(longitude - 105, latitude - 35)
  const latitudeRadians = latitude / 180 * Math.PI
  let magic = Math.sin(latitudeRadians)
  magic = 1 - ECCENTRICITY_SQUARED * magic * magic
  const squareRootMagic = Math.sqrt(magic)
  latitudeDelta = latitudeDelta * 180 / ((EARTH_AXIS * (1 - ECCENTRICITY_SQUARED)) / (magic * squareRootMagic) * Math.PI)
  longitudeDelta = longitudeDelta * 180 / (EARTH_AXIS / squareRootMagic * Math.cos(latitudeRadians) * Math.PI)

  return [longitude + longitudeDelta, latitude + latitudeDelta]
}

function finiteNumber(value, fallback = null) {
  if (value === '' || value === null || value === undefined) return fallback
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function normalizedStatus(value) {
  const status = String(value ?? '').trim().toLowerCase()
  return status === 'online' || status === 'offline' ? status : 'unknown'
}

export function normalizeStation(raw, rowIndex) {
  const sourceLongitude = finiteNumber(raw?.longitude)
  const sourceLatitude = finiteNumber(raw?.latitude)
  if (
    sourceLongitude === null
    || sourceLatitude === null
    || sourceLongitude < -180
    || sourceLongitude > 180
    || sourceLatitude < -90
    || sourceLatitude > 90
  ) {
    return null
  }

  const stationCode = String(raw?.stationCode ?? '').trim()
  const stationName = String(raw?.stationName ?? '').trim() || stationCode || `未命名站点 ${rowIndex + 1}`
  const [longitude, latitude] = wgs84ToGcj02(sourceLongitude, sourceLatitude)

  return {
    id: stationCode ? `${stationCode}-${rowIndex}` : `row-${rowIndex}`,
    stationCode,
    stationName,
    longitude,
    latitude,
    sourceLongitude,
    sourceLatitude,
    alt: finiteNumber(raw?.alt, 0),
    status: normalizedStatus(raw?.status),
    delay: finiteNumber(raw?.delay, 0),
    signalQuality: raw?.signalQuality && typeof raw.signalQuality === 'object'
      ? raw.signalQuality
      : { qualified: false, avgNoiseRatio: 0 },
    satelliteCount: raw?.satelliteCount && typeof raw.satelliteCount === 'object'
      ? raw.satelliteCount
      : { bdCount: 0 },
    lastUpdateTime: finiteNumber(raw?.lastUpdateTime, 0),
  }
}

function shouldReplace(current, candidate) {
  const currentRank = STATUS_RANK[current.status]
  const candidateRank = STATUS_RANK[candidate.status]
  if (candidateRank !== currentRank) return candidateRank > currentRank
  return candidate.lastUpdateTime > current.lastUpdateTime
}

export function normalizeStations(rawStations, reportedTotal) {
  const source = Array.isArray(rawStations) ? rawStations : []
  const raw = []
  const uniqueByCode = new Map()
  const statusCounts = { online: 0, offline: 0, unknown: 0 }

  source.forEach((station, rowIndex) => {
    const normalized = normalizeStation(station, rowIndex)
    if (!normalized) return
    raw.push(normalized)
    statusCounts[normalized.status] += 1

    const uniqueKey = normalized.stationCode || normalized.id
    const current = uniqueByCode.get(uniqueKey)
    if (!current || shouldReplace(current, normalized)) {
      uniqueByCode.set(uniqueKey, normalized)
    }
  })

  const unique = [...uniqueByCode.values()]
  const numericReportedTotal = finiteNumber(reportedTotal, source.length)

  return {
    raw,
    unique,
    stats: {
      reportedTotal: numericReportedTotal,
      rawCount: source.length,
      validCount: raw.length,
      uniqueCount: unique.length,
      duplicateCount: raw.length - unique.length,
      invalidCoordinateCount: source.length - raw.length,
      onlineCount: statusCounts.online,
      offlineCount: statusCounts.offline,
      unknownCount: statusCounts.unknown,
    },
  }
}
