# server_app — 数据服务

沉降可视化项目的后端数据服务，提供 HTTP 二进制接口和 WebSocket + Protobuf 接口，两种数据源（JSON 文件 / 随机生成）。

## 启动

```bash
cd server_app
npm install

# 分别启动
npm run http    # HTTP 服务 :3456
npm run ws      # WebSocket 服务 :3457

# 或通过父目录一键启动
cd .. && ./start.sh
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `http_server.js` | HTTP 二进制数据服务（端口 3456） |
| `ws_server.js` | WebSocket + Protobuf 数据服务（端口 3457） |
| `points.proto` | Protobuf 消息定义 |
| `package.json` | 依赖管理 |

## 数据源

两个服务共享相同的数据源逻辑：

### JSON 文件模式（`source=json`）
从 `../heatmap-app/src/data/*.json` 加载全部沉降点位数据，首次加载后缓存。

### 随机生成模式（`source=random`）
在指定经纬度范围内随机生成点数据，默认范围：
- 经度：120° ~ 122°
- 纬度：30° ~ 32°
- 沉降值：-30 ~ +30 mm（均匀分布）

---

## HTTP 接口 (`http_server.js`)

**端口**：`3456`

**请求**：
```
GET http://localhost:3456/?source=<json|random>&count=<N>&swLng=<W>&swLat=<S>&neLng=<E>&neLat=<N>
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `source` | `random` | `json` 或 `random` |
| `count` | `10000` | 点数（仅 random 模式生效） |
| `swLng` | `120` | 西南角经度 |
| `swLat` | `30` | 西南角纬度 |
| `neLng` | `122` | 东北角经度 |
| `neLat` | `32` | 东北角纬度 |

**响应**：
- Content-Type: `application/octet-stream`
- CORS: 允许所有来源
- 二进制格式：

```
[ 4B uint32 count ]
[ count × 4B float32 lng[] ]
[ count × 4B float32 lat[] ]
[ count × 4B float32 val[] ]
```

总大小 = `4 + count × 12` 字节。

**示例**：
```bash
# 生成 5000 个随机点
curl http://localhost:3456/?source=random&count=5000 > data.bin

# 返回 JSON 文件中的全部点
curl http://localhost:3456/?source=json > data.bin
```

---

## WebSocket 接口 (`ws_server.js`)

**端口**：`3457`

**协议**：WebSocket，客户端发送 JSON 请求，服务端返回 Protobuf 二进制响应。

### 请求格式（客户端 → 服务端）

```json
{
  "source": "random",
  "count": 10000,
  "bounds": {
    "swLng": 120,
    "swLat": 30,
    "neLng": 122,
    "neLat": 32
  }
}
```

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `source` | `"random"` | `"json"` 或 `"random"` |
| `count` | `10000` | 点数（仅 random 模式） |
| `bounds` | `null` | 视口范围，null 时使用默认范围 |

### 响应格式（服务端 → 客户端）

Protobuf 编码的 `PointsResponse` 消息：

```protobuf
syntax = "proto3";
message PointsResponse {
  repeated float lng = 1 [packed=true];
  repeated float lat = 2 [packed=true];
  repeated float val = 3 [packed=true];
}
```

### 前端解析示例

```js
const ws = new WebSocket('ws://localhost:3457')
ws.binaryType = 'arraybuffer'
ws.onopen = () => ws.send(JSON.stringify({ source: 'random', count: 5000 }))
ws.onmessage = async (e) => {
  const root = await protobuf.load('/points.proto')
  const PointsResponse = root.lookupType('PointsResponse')
  const data = PointsResponse.decode(new Uint8Array(e.data))
  // data.lng, data.lat, data.val 为 Float32Array
  ws.close()
}
```

---

## 依赖

| 包 | 版本 | 用途 |
|------|------|------|
| `ws` | ^8.0.0 | WebSocket 服务端 |
| `protobufjs` | ^7.0.0 | Protobuf 编码/解码 |

---

## 与前端的数据流对比

| 特性 | HTTP | WebSocket |
|------|------|-----------|
| 协议 | HTTP GET | WebSocket |
| 序列化 | 自定义二进制 (uint32 + float32[]) | Protobuf |
| 连接方式 | 短连接（每次 fetch） | 长连接（复用） |
| CORS | 需要配置 | 不受同源策略限制 |
| 前端解析 | `new Float32Array(buf)` 按偏移读取 | `PointsResponse.decode()` |
