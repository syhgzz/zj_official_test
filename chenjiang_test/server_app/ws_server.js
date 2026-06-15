const { WebSocketServer } = require('ws')
const protobuf = require('protobufjs')
const fs = require('fs')
const path = require('path')
const PORT = 3457

const DATA_DIR = path.join(__dirname, '..', 'heatmap-app', 'src', 'data')
let cachedJsonPoints = null
function loadJsonData() {
  if (cachedJsonPoints) return cachedJsonPoints
  const files = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.json'))
  const points = []
  for (const f of files) {
    const raw = JSON.parse(fs.readFileSync(path.join(DATA_DIR, f), 'utf-8'))
    for (const p of raw?.response?.data?.points || [])
      points.push({ lng: p.longitude, lat: p.latitude, value: p.subsidence })
  }
  cachedJsonPoints = points
  console.log('Loaded', points.length, 'JSON points')
  return points
}

function genRandom(n, bounds) {
  const swLng = bounds ? bounds.swLng : 120
  const swLat = bounds ? bounds.swLat : 30
  const neLng = bounds ? bounds.neLng : 122
  const neLat = bounds ? bounds.neLat : 32
  const lng = new Float32Array(n), lat = new Float32Array(n), val = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    lng[i] = swLng + Math.random() * (neLng - swLng)
    lat[i] = swLat + Math.random() * (neLat - swLat)
    val[i] = (Math.random() - 0.5) * 60
  }
  return { lng, lat, val }
}

function toArrays(points) {
  const n = points.length, lng = new Float32Array(n), lat = new Float32Array(n), val = new Float32Array(n)
  for (let i = 0; i < n; i++) { lng[i]=points[i].lng; lat[i]=points[i].lat; val[i]=points[i].value }
  return { lng, lat, val }
}

let PointsResponse
async function init() {
  loadJsonData()
  const root = await protobuf.load(__dirname + '/points.proto')
  PointsResponse = root.lookupType('PointsResponse')
  new WebSocketServer({ port: PORT }).on('connection', ws => {
    ws.on('message', raw => {
      let source = 'random', count = 10000, bounds = null
      try {
        const p = JSON.parse(raw.toString())
        source = p.source || 'random'
        count = p.count || 10000
        bounds = p.bounds || null
      } catch(e) {}
      const arr = source === 'json'
        ? toArrays(loadJsonData())
        : genRandom(count, bounds)
      ws.send(PointsResponse.encode(PointsResponse.create(arr)).finish())
      console.log('WS', source, arr.lng.length, 'pts')
    })
  })
  console.log('WS on :'+PORT)
}
init().catch(console.error)
