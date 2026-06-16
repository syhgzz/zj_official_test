# chenjiang_test — 沉降数据可视化项目

基于高德地图的沉降数据热力图可视化全栈项目，包含前端 SPA、HTTP 数据服务、WebSocket + Protobuf 数据服务。

## 项目结构

```
chenjiang_test/
├── start.sh                  # 一键启动全部服务
├── README.md
├── heatmap-app/              # 前端：Vue3 + Vite + 高德地图
│   ├── README.md
│   ├── src/
│   │   ├── App.vue           # 主组件（散点图、热力图、插值图）
│   │   ├── main.js           # 入口
│   │   ├── lib/
│   │   │   ├── interplot_figure.js   # 插值图层工厂
│   │   │   ├── interp-worker.js      # Web Worker 渲染
│   │   │   └── webgl-splat.js        # WebGL2 GPU 加速
│   │   └── data/                     # JSON 数据文件
│   └── ...
└── server_app/               # 后端：HTTP + WebSocket 数据服务
    ├── README.md
    ├── http_server.js         # HTTP 二进制数据接口
    ├── ws_server.js           # WebSocket + Protobuf 接口
    ├── points.proto           # Protobuf 消息定义
    └── package.json
```

## 快速启动

```bash
cd chenjiang_test
./start.sh
```

一键启动 3 个服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 Vite | `:5173` | Vue3 开发服务器 |
| HTTP 接口 | `:3456` | 二进制点数据服务 |
| WebSocket | `:3457` | Protobuf 编码点数据服务 |

访问 `http://localhost:5173` 即可使用。

按 `Ctrl+C` 停止全部服务。

## 架构

```
┌─────────────────────────────────────────┐
│                前端 (port 5173)          │
│  Vue3 + Vite + 高德地图 JS API           │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │  散点图   │ │  热力图   │ │ 插值图   │  │
│  │CPUCanvas │ │AMap SDK  │ │Worker   │  │
│  └──────────┘ └──────────┘ │+GPU     │  │
│                            └─────────┘  │
└──────────────┬──────────────────────────┘
               │ fetch / WebSocket
       ┌───────┴───────┐
       │               │
┌──────▼──────┐ ┌──────▼──────┐
│ HTTP :3456  │ │  WS :3457   │
│ binary      │ │  Protobuf   │
│ Float32[]   │ │  encoded    │
└──────┬──────┘ └──────┬──────┘
       │               │
       └───────┬───────┘
               │
    ┌──────────▼──────────┐
    │  数据源              │
    │  • JSON 文件 (本地)  │
    │  • 随机生成 (视口内)  │
    └─────────────────────┘
```

## 数据流

1. **本地模式**：前端直接加载 `src/data/*.json`，无需后端
2. **HTTP 模式**：前端 → `GET :3456?source=random&count=N` → 接收二进制 `Float32Array`
3. **WebSocket 模式**：前端 → 发送 JSON 请求 → 接收 Protobuf 编码响应

## 技术栈

| 层 | 技术 |
|------|------|
| 前端框架 | Vue 3 (Composition API) |
| 构建工具 | Vite |
| 地图 SDK | 高德 JS API 2.0 |
| 插值算法 | Gaussian / IDW / RBF / Kriging |
| GPU 加速 | WebGL2 (IDW/Gaussian splatting) |
| 后端 HTTP | Node.js `http` 模块 |
| 后端 WebSocket | `ws` 库 |
| 序列化 | Protobuf (protobufjs) |
