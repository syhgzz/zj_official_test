# 中检项目接口测试集合包
包括 **API 测试程序**、**interplot_figure.js 插值渲染库示例** 与 **Protobuf 接口调试工具** 。

## 项目结构

```
zj_official_test/
│
├── config/                        # API 测试配置
│   ├── api_config.ini            # 服务器地址与认证信息
│   └── config.py                 # 配置加载模块
│
├── lib/                           # API 测试共享库
│   ├── signature.py              # HmacSHA256 签名算法
│   ├── api_client.py             # 统一 API 请求客户端
│   └── response_printer.py       # 响应格式化输出与统计采集
│
├── test_cases/                    # 模块测试用例
│   ├── test_overview.py          # 系统概览
│   ├── test_upss.py              # 沉降态势感知
│   ├── test_udmds.py             # 形变安全监测
│   ├── test_ugss.py              # GNSS 干扰监测
│   ├── test_unga.py              # 走航甲烷检测
│   └── test_gnss_device.py       # 北斗设备状态
│
├── test-samples/                  # 单接口 Protobuf 调试工具
│   ├── request_samples.py        # HTTP + Protobuf 客户端 CLI（接口: /api/v1/upss/samples）
│   ├── subsidence.proto          # SubsidencePointStream Protobuf 定义
│   └── subsidence_pb2.py         # protoc 编译后的 Python 代码
│
├── scripts/                       # 工具脚本
│   ├── fetch_upss.py             # 沉降数据抓取
│   ├── fetch_unga.py             # 甲烷检测数据抓取
│   ├── fetch_udmds.py            # 形变监测数据抓取
│   ├── fetch_gnss.py             # GNSS 数据抓取
│   ├── extract_interfaces.py     # 接口文档提取
│   └── json2csv.py               # JSON → CSV 转换
│
├── chenjiang_test/                # interplot_figure.js 用法示例程序
│   ├── heatmap-app/              # Vue3 + Vite + 高德地图 Demo
│   ├── server_app/               # 后端数据服务 (HTTP + WebSocket)
│   └── start.sh                  # 一键启动脚本
│
├── pyproject.toml                 # Python 项目配置 (依赖: requests, protobuf)
├── trajectory_map.html            # Leaflet 走航轨迹地图展示（独立 HTML）
└── README.md                      # 本文件
```

---

## 一、API 测试程序 (Python)

基于 Python 的中检项目 API 测试程序，覆盖 **7 大模块、44+ 接口**，支持统一的 HmacSHA256 签名认证、配置管理与结果采集。

### 环境要求

- Python 3.13+
- 依赖：[requests](https://pypi.org/project/requests/)、[protobuf](https://pypi.org/project/protobuf/)

### 安装

```bash
uv sync  # 或 pip install -e .
```

### 配置文件

编辑 `config/api_config.ini`，配置服务器地址与认证信息：

```ini
[server]
host = http://your-server:port
timeout = 120

[auth]
app_key = your-app-key
app_secret = your-app-secret

[test]
verbose = true
save_response = true
response_dir = responses
```

### 签名认证

使用 **HmacSHA256 + Base64** 签名算法，自动注入 `appKey`、`timestamp`、`sign` 请求头：

```
sign = Base64(HmacSHA256(timestamp + "\n" + appSecret))
```

参见 `lib/signature.py`。

### 运行测试

```bash
# 运行单个模块
python -m test_cases.test_overview
python -m test_cases.test_upss

# 运行全部模块（pytest）
python -m pytest test_cases/
```

### 数据抓取

```bash
# 抓取沉降数据并保存为 JSON
python scripts/fetch_upss.py

# 抓取形变监测数据
python scripts/fetch_udmds.py
```

### 测试模块一览

| 模块代码 | 模块名称 | 接口数 | 覆盖接口 |
|---------|---------|--------|---------|
| overview | 系统概览 | 2 | 实时概览、综合统计 |
| upss | 沉降态势感知 | 11 | 概览、期次列表、期次汇总、单点历史、沉降地图(热力图)、沉降速率、沉降速率梯度、预警信息、态势统计、最大沉降时序、前五梯度 |
| udmds | 形变安全监测 | 7 | 概览、工程列表、监测点列表、单点实时、单点历史、工程统计、告警汇总 |
| ugss | GNSS 干扰监测 | 7 | 概览、基站列表、单站实时、干扰事件、频率统计、预警汇总 |
| unga | 走航甲烷检测 | 5 | 概览、检测任务、走航轨迹、泄露点管理、统计分析 |
| upns | 短临降水预警 | 9 | 概览、站点列表、单站实时、单站历史、区域统计、预警汇总、降雨量实时、PWV 实时统计 |
| gnss-device | 北斗设备状态 | 3 | 设备概览、设备列表、设备详情 |

---

## 二、单接口 Protobuf 调试工具 (test-samples)

`test-samples/` 是针对 **单个新增接口** `GET /api/v1/upss/samples` 的独立调试 CLI 工具。该接口以 `application/octet-stream` 返回 Protobuf 编码的二进制数据。

### 接口说明

| 项目 | 内容 |
|------|------|
| 路径 | `GET /api/v1/upss/samples` |
| 参数 | `issue`(期次 yyyyMMdd)、`minLng/maxLng/minLat/maxLat`(空间范围)、`dataType`(subsidence \| gradient \| velocity) |
| 响应 | `application/octet-stream`，body 为 `SubsidencePointStream` Protobuf 消息 |
| 错误处理 | 参数非法时 `text/plain` + `HTTP 400` |

### Protobuf 消息定义

`test-samples/subsidence.proto` 定义了 `SubsidencePointStream` 消息——三个等长 `packed double` 数组，按索引一一对应；val 无值的位置填 0：

```protobuf
message SubsidencePointStream {
  repeated double lng = 1 [packed = true];  // 经度
  repeated double lat = 2 [packed = true];  // 纬度
  repeated double val = 3 [packed = true];  // 值(沉降量mm / 速率mm·年⁻¹ / 梯度mm)
}
```

### 使用方法

```bash
# 默认参数（重庆市周边，2020-02-22 期次，沉降量）
python test-samples/request_samples.py

# 指定参数
python test-samples/request_samples.py \
  --issue 20200222 \
  --min-lng 105.7 --max-lng 108.4 \
  --min-lat 28.9 --max-lat 30.2 \
  --data-type gradient

# 输出控制
python test-samples/request_samples.py --limit 20           # 预览前 20 条
python test-samples/request_samples.py --csv output.csv      # 保存为 CSV
python test-samples/request_samples.py --raw response.bin    # 保存原始二进制
```

---

## 三、interplot_figure.js 用法示例程序 (chenjiang_test)

`chenjiang_test/` 是一个 **展示 `createInterpolationOverlay`（interplot_figure.js）用法的 Demo 程序**，演示如何在 Vue 3 + 高德地图环境中使用插值渲染库。

### interplot_figure.js 是什么

`chenjiang_test/heatmap-app/src/lib/interplot_figure.js` 是一个通用的**散点插值图层库**，提供 `createInterpolationOverlay` 函数，支持：

| 特性 | 说明 |
|------|------|
| 四种算法 | Gaussian / IDW / RBF / Kriging |
| 渲染方式 | Web Worker（非阻塞） + 可选 WebGL2 GPU 加速（IDW/Gaussian） |
| 图层输出 | AMap.ImageLayer（PNG） |
| 数据输入 | 对象数组 `[{lng, lat, value}]` 或类型数组 `{lng: Float32Array, lat: Float32Array, val: Float32Array}` |
| 性能回调 | `onRender` 返回各阶段耗时（采样、Worker 计算、图层挂载等） |

详细 API 文档见 `chenjiang_test/heatmap-app/src/lib/README.md`。

### 快速体验

```bash
cd chenjiang_test
./start.sh
```

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 Vite | `:5173` | Demo 页面 |
| HTTP 数据接口 | `:3456` | 自定义二进制点数据服务（供数据源切换测试） |
| WebSocket | `:3457` | Protobuf 编码点数据服务（供数据源切换测试） |

访问 `http://localhost:5173` 即可使用。

### Demo 功能

| 功能 | 说明 |
|------|------|
| 三种数据来源 | 本地 JSON 文件 / HTTP 二进制接口 / WebSocket Protobuf |
| 算法切换 | Gaussian / IDW / RBF / Kriging |
| 参数实时调节 | sigma、搜索半径、采样步长、透明度、GPU 开关、模糊开关等 |
| 图层开关 | 散点图 / 热力图 / 插值图 独立显示 |
| 渲染耗时面板 | 实时显示各阶段耗时 breakdown |
| 调试模式 | 视口内随机生成指定数量数据点，快速验证参数效果 |

### 技术栈

| 层 | 技术 |
|------|------|
| 前端框架 | Vue 3 (Composition API) |
| 构建工具 | Vite |
| 地图 SDK | 高德 JS API 2.0 |
| 插值渲染库 | `interplot_figure.js`（Web Worker + WebGL2） |
| 后端 HTTP | Node.js http 模块 |
| 后端 WebSocket | ws 库 + protobufjs |

> 详细文档参见 `chenjiang_test/README.md`。

---

## 四、走航轨迹地图

`trajectory_map.html` 是一个独立的 **Leaflet 轨迹地图**，展示甲烷走航检测任务的车辆轨迹与采样点数据，直接用浏览器打开即可使用。

---

## 开发指南

### 添加新测试模块

1. 在 `config/api_config.ini` 中添加模块配置（如有需要）
2. 在 `test_cases/` 下创建 `test_<module>.py`，继承现有的测试模式
3. 使用 `lib/api_client.py` 发起签名请求
4. 使用 `lib/response_printer.py` 格式化输出与统计
