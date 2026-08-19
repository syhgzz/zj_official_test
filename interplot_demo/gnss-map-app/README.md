# GNSS 卫星站点分布测试页

这是一个完全独立的浏览器测试工程，用来验证数千个 GNSS 卫星站点在高德地图上的分布、状态和交互性能。

工程只读取 `zj_official_test/responses` 中已经保存的合并响应，不会调用真实 GNSS 接口，也不会修改或依赖 `zj_frontend`。

## 页面能力

- 默认保持重庆附近视角，不会自动缩放成全国一屏。
- 使用一个 `AMap.LabelsLayer` 批量绘制数千个 `LabelMarker`，不为每个点创建 DOM 标记或信息窗。
- 支持“原始记录”和“唯一站点”两种模式。
- 在线、离线和未知状态分别使用绿色、红色和灰蓝色。
- 点击站点可以查看编码、状态、经纬度、高程、延迟、卫星数、信噪比和更新时间。
- 显示数据读取、坐标转换/去重、图层创建耗时。

## 数据说明

运行开发服务器或构建前，`scripts/prepare-data.mjs` 会自动扫描：

```text
F:\work\zj_official_test\responses\*.json
```

它选择修改时间最新、接口路径为 `/api/v1/gnss-device/stations`、页码范围为 `1-36` 的合并响应，并生成：

```text
public\data\gnss-stations.json
```

生成文件已被 Git 忽略，不需要手工维护，也不包含请求签名信息。

当前响应包含 3586 条原始记录。由于上游服务的分页顺序不稳定，当前文件动态计算得到 2709 个唯一站点编码和 877 条重复行；重新抓取后这些数字可能变化，页面会按实际文件重新计算。

- **原始记录**：保留全部有效坐标行，用于测试 3586 点的渲染压力。
- **唯一站点**：按 `stationCode` 去重；优先保留在线记录，状态相同时保留更新时间较新的记录。

响应中的经纬度按 WGS-84 读取，绘制前会转换为高德地图使用的 GCJ-02 坐标。

## 启动

```powershell
cd F:\work\zj_official_test\interplot_demo\gnss-map-app
npm install
npm run dev
```

`npm run dev` 会先准备数据，再启动并打开浏览器页面。不需要启动 `interplot_demo/server_app`。

## 测试与构建

```powershell
npm test
npm run build
npm run preview
```

- `npm test`：验证响应选择、紧凑数据生成、坐标转换、去重统计、状态图标图层生命周期和弹窗安全格式化。
- `npm run build`：重新准备数据并生成 `dist` 生产构建。
- `npm run preview`：预览最近一次生产构建。

## 高德地图 Key

默认使用现有热力图测试工程中的浏览器 Key，便于直接启动。需要替换时，在 PowerShell 中设置：

```powershell
$env:VITE_AMAP_KEY = '你的高德浏览器端Key'
npm run dev
```

这里只能使用高德浏览器端 Key，不要放入 GNSS 接口的 `app_key`、`app_secret` 或其他服务端凭据。

## 常见问题

### 页面提示没有找到 GNSS 合并响应

先运行站点分页测试，确保 `responses` 中存在 `request_params.pageNum` 为 `1-36` 的合并 JSON，然后重新执行 `npm run dev`。

### 地图点位都是红色

颜色来自响应中的真实 `status`。当前保存的 3586 条记录全部为 `offline`，因此都会显示为红色；页面不会为了视觉效果伪造在线状态。

### 数字不是 3586 个唯一站点

3586 是当前 JSON 的原始行数，不是唯一编码数。上游分页结果存在跨页重复，右侧面板会同时显示原始行数、唯一站点数和重复行数。
