const http = require('http')
const fs = require('fs')
const path = require('path')
const PORT = 3456

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

function encode(points) {
  const n = points.length
  const buf = Buffer.allocUnsafe(4 + n * 12)
  buf.writeUInt32LE(n, 0)
  for (let i = 0; i < n; i++) {
    buf.writeFloatLE(points[i].lng, 4 + i * 4)
    buf.writeFloatLE(points[i].lat, 4 + n * 4 + i * 4)
    buf.writeFloatLE(points[i].value, 4 + n * 8 + i * 4)
  }
  return buf
}

function genRandom(n, bounds) {
  const swLng = bounds ? bounds.swLng : 120
  const swLat = bounds ? bounds.swLat : 30
  const neLng = bounds ? bounds.neLng : 122
  const neLat = bounds ? bounds.neLat : 32
  const pts = []
  for (let i = 0; i < n; i++)
    pts.push({
      lng: swLng + Math.random() * (neLng - swLng),
      lat: swLat + Math.random() * (neLat - swLat),
      value: (Math.random() - 0.5) * 60
    })
  return pts
}

http.createServer((req, res) => {
  if (req.method === 'OPTIONS') { res.writeHead(204, {'Access-Control-Allow-Origin':'*'}); return res.end() }
  const u = new URL(req.url, 'http://localhost')
  const source = u.searchParams.get('source') || 'random'
  const count = parseInt(u.searchParams.get('count')) || 10000
  let points
  if (source === 'json') {
    points = loadJsonData()
  } else {
    const bounds = {
      swLng: parseFloat(u.searchParams.get('swLng')) || 120,
      swLat: parseFloat(u.searchParams.get('swLat')) || 30,
      neLng: parseFloat(u.searchParams.get('neLng')) || 122,
      neLat: parseFloat(u.searchParams.get('neLat')) || 32
    }
    points = genRandom(count, bounds)
  }
  const data = encode(points)
  res.writeHead(200, {'Content-Type':'application/octet-stream','Access-Control-Allow-Origin':'*'})
  res.end(data)
  console.log('HTTP', source, points.length, 'pts')
}).listen(PORT, () => { loadJsonData(); console.log('HTTP on :'+PORT) })
