# 接口文档

# 降水数据接口（UPNS 短临降水预警模块）

> 范围：`UpnsController` 对外业务面接口，前缀 `/api/v1/upns`，共 **14 个接口**。
> 全部为 GET、无请求体；需通过 HmacSHA256 签名验证。
> 最后核对更新：2026-08-20，与 `UpnsController` 当前代码一致；已剔除作废接口 `/statistics/regional`（调用将返回 410）。

## 通用约定

- **统一响应封装 `Result<T>`**：

  | 字段 | 类型 | 说明 |
  |---|---|---|
  | code | Integer | 状态码，`200`=成功；`400`=参数非法；`500`=系统错误 |
  | msg | String | 响应消息 |
  | data | T | 业务数据（各接口的 `T` 见下） |
  | timestamp | Long | 响应时间戳（毫秒） |

- **时间戳**：未特别说明均为 **Unix 毫秒时间戳（Long）**。
- **BBOX（地理范围）顺序在各接口不一致，务必分别对待**：
  - `/stations`、`/warnings`、`/statistics/rain/now`、`/statistics/pwv/now`：传「左上角(minLng, maxLat) + 右下角(maxLng, minLat)」四个参数。
  - `/precipitation/layers`：传 `minLng/maxLng/minLat/maxLat`（行级粗筛）。
  - `/layers/*`（气象要素插值图层）：传 `minLng/maxLng/minLat/maxLat`（站点过滤；四参数齐全时兼作插值范围）。

---

## 一、模块概览与风险评估

### 1. 获取模块概览
- **请求方法**：`GET /api/v1/upns/overview`
- **功能说明**：获取短临降水预警模块整体概览数据（站点在线情况、预警计数、当前平均气象条件）。
- **请求参数**：无。
- **响应数据结构**：`Result<UpnsOverviewVO>`，字段见 [VO·1](#vo1-upnsoverviewvo)。

### 2. 获取风险评估
- **请求方法**：`GET /api/v1/upns/risk`
- **功能说明**：短临降水模块的独立风险评估（风险等级、评分、各风险因子）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| regionCode | String | 否 | 区域编码 |

- **响应数据结构**：`Result<RiskAssessmentVO>`，字段见 [VO·9](#vo9-riskassessmentvo)。

---

## 二、降水站点与降雨查询

> 本组接口均面向"按地理范围（BBOX）或区域编码查询站点 / 降雨 / 预警"，供地图或榜单展示，参数语义一致。

### 3. 获取监测站点列表
- **请求方法**：`GET /api/v1/upns/stations`
- **功能说明**：获取降水监测站点列表及当前状态，支持分页、区域筛选或 BBOX 地理边界查询。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| pageNum | Integer | 否 | 1 | 页码 |
| pageSize | Integer | 否 | 20 | 每页数量 |
| regionCode | String | 否 | — | 区域编码（与 BBOX 互斥） |
| status | String | 否 | — | 状态筛选（online/offline） |
| minLng | Double | 否 | — | 左上角经度（bbox 最小经度） |
| maxLat | Double | 否 | — | 左上角纬度（bbox 最大纬度） |
| maxLng | Double | 否 | — | 右下角经度（bbox 最大经度） |
| minLat | Double | 否 | — | 右下角纬度（bbox 最小纬度） |

- **响应数据结构**：`Result<UpnsStationPageVO>`，字段见 [VO·2](#vo2-upnsstationpagevo) / [VO·3](#vo3-upnsstationvo)。

### 4. 获取降水预警汇总
- **请求方法**：`GET /api/v1/upns/warnings/summary`
- **功能说明**：按时间范围与预警级别统计降水预警汇总（总数、等级分布、时间分布、预警详情）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| startTime | Long | 否 | 开始时间戳（毫秒） |
| endTime | Long | 否 | 结束时间戳（毫秒） |
| level | Integer | 否 | 预警级别（1-4） |

- **响应数据结构**：`Result<WarningSummaryVO>`，字段见 [VO·6](#vo6-warningsummaryvo)。

### 5. 获取预警信息列表（预警小窗口）
- **请求方法**：`GET /api/v1/upns/warnings`
- **功能说明**：按地理范围（BBOX）与时间范围查询降水预警列表，返回时间、站点名、经纬度、级别，供前端小窗口表格展示。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| minLng | Double | 是 | 左上角经度（bbox 最小经度） |
| maxLat | Double | 是 | 左上角纬度（bbox 最大纬度） |
| maxLng | Double | 是 | 右下角经度（bbox 最大经度） |
| minLat | Double | 是 | 右下角纬度（bbox 最小纬度） |
| startTime | Long | 是 | 起始时间戳（毫秒） |
| endTime | Long | 是 | 终止时间戳（毫秒） |

- **响应数据结构**：`Result<List<UpnsWarningItemVO>>`，`data` 为数组，元素见 [VO·7](#vo7-upnswarningitemvo)。

### 6. 获取降雨量统计（前一小时前十站点）
- **请求方法**：`GET /api/v1/upns/statistics/rain/now`
- **功能说明**：前一小时降雨量前十的站点统计，支持区域编码或 BBOX。数据源为降雨量统计同步数据；前一小时无数据时回退取最近 1000 条（`period` 字段区分 `last_hour`/`latest_1000`）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| regionCode | String | 否 | 区域编码（与 BBOX 互斥） |
| minLng | Double | 否 | 左上角经度 |
| maxLat | Double | 否 | 左上角纬度 |
| maxLng | Double | 否 | 右下角经度 |
| minLat | Double | 否 | 右下角纬度 |

- **响应数据结构**：`Result<RainfallStatisticsVO>`，字段见 [VO·8](#vo8-rainfallstatisticsvo)。

### 7. 获取大气可降水量（PWV）统计
- **请求方法**：`GET /api/v1/upns/statistics/pwv/now`
- **功能说明**：当前大气可降水量（PWV）前十的站点统计，支持区域编码或 BBOX。数据源为 PWV 统计同步数据；前一小时无数据时回退取最近 1000 条（`period` 字段区分 `last_hour`/`latest_1000`）。
- **请求参数**：同 [接口 6](#6-获取降雨量统计前一小时前十站点)（regionCode + BBOX）。
- **响应数据结构**：`Result<PwvStatisticsVO>`，字段见 [VO·10](#vo10-pwvstatisticsvo)。

---

## 三、站点实时与历史数据

### 8. 获取站点实时数据
- **请求方法**：`GET /api/v1/upns/stations/{code}/realtime`
- **功能说明**：根据站点编码获取该站点最新一条实时监测数据及预警状态。

| 参数 | 类型 | 必填 | 位置 | 说明 |
|---|---|---|---|---|
| code | String | 是 | Path | 站点编码（如 `UPNS001`） |

- **响应数据结构**：`Result<UpnsRealtimeVO>`，字段见 [VO·4](#vo4-upnsrealtimevo)。

### 9. 获取站点历史趋势数据
- **请求方法**：`GET /api/v1/upns/stations/{code}/history`
- **功能说明**：获取指定站点历史多指标时序数据及统计汇总，支持指标筛选、时间间隔、时间范围。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| code | String | 是 | — | Path，站点编码 |
| metrics | String | 否 | — | 指标列表（逗号分隔，如 `temperature,humidity,rain`），不传返回全部 |
| dataType | String | 否 | — | **已废弃**，向后兼容（实际取 `metrics != null ? metrics : dataType`） |
| interval | String | 否 | `1h` | 聚合时间间隔 |
| startTime | Long | 否 | — | 开始时间戳（毫秒），不传默认过去 24 小时 |
| endTime | Long | 否 | — | 结束时间戳（毫秒），不传默认当前时间 |

- **响应数据结构**：`Result<UpnsHistoryVO>`，字段见 [VO·5](#vo5-upnshistoryvo)。

---

## 四、降水图层格网数据（等值线渲染 / 预测降水图）

### 10. 获取降雨图层格网数据
- **请求方法**：`GET /api/v1/upns/precipitation/layers`
- **功能说明**：返回降雨图层多时刻规则二维矩阵 `values[row][col]`，供前端等值线成图。通过 `forecastOffsetMinutes` 切换两种模式：
  - **预测模式**（`forecastOffsetMinutes` ≠ null，对应"获取预测降水图"）：锚定该预测图层最新发布批次，在其多个未来 `dataTime` 中选 lead time 最接近所求偏移的单个时刻，返回**单时刻**矩阵，忽略 `startTime/endTime`。
  - **区间模式**（`forecastOffsetMinutes` = null，对应"获取降水图"）：按 `startTime/endTime` 查询（两端都为空时取最新一个 `dataTime`），返回**多时刻**矩阵。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| layer | String | 是 | — | 图层编码（"种类"），取值见下表 |
| forecastOffsetMinutes | Long | 否 | — | 预测时间点偏移（分钟），仅预测图层有效：`60`=1 小时后、`120`=2 小时后；非预测图层传入返回 400 |
| startTime | Long | 否 | — | 起始数据时间（毫秒），区间模式闭区间下界 |
| endTime | Long | 否 | — | 截止数据时间（毫秒），区间模式闭区间上界 |
| minLng | Double | 否 | — | bbox 最小经度（行级粗筛） |
| maxLng | Double | 否 | — | bbox 最大经度 |
| minLat | Double | 否 | — | bbox 最小纬度 |
| maxLat | Double | 否 | — | bbox 最大纬度 |
| groupName | String | 否 | — | 裁剪区域组名，不传返回所有组 |

**`layer`（种类）取值：**

| 编码 | 中文名 | 类别 | 单位 |
|---|---|---|---|
| XTSKPWV | 大气可降水量（10分钟） | 实时观测 | mm |
| XTSKJSXS | 小时降水量 | 实时观测 | mm |
| XTSKJSXS10Min | 10分钟降水量 | 实时观测 | mm |
| XTSKJSFZ | 分钟降水量 | 实时观测 | mm |
| LSTMXSJS | 时序预测模型 | 预测 | mm |
| CONVLSTMXSJS | 卷积预测模型 | 预测 | mm |

- **响应数据结构**：`Result<PrecipitationLayerDataVO>`，字段见 [VO·11](#vo11-precipitationlayerdatavo)。

---

## 五、气象要素插值图层（站点观测 IDW 插值）

> 数据来源为站点实时观测（Socket `UPNSRealtime`），按自然小时聚合后由服务端做 IDW（反距离加权，p=2）插值为规则二维矩阵。**响应结构与 `/precipitation/layers` 完全一致**（`Result<PrecipitationLayerDataVO>`，字段见 [VO·11](#vo11-precipitationlayerdatavo)），前端可复用同一等值线渲染管线；区别在于 `createTime` 恒为 `null`（非外部发布批次），`dataTime` 为自然小时整点（桶起始）。

| 接口 | layer 编码 | 图层 | 单位 | 小时聚合口径 |
|---|---|---|---|---|
| `GET /api/v1/upns/layers/pwv-hourly` | PWVHOURLY | 大气可降水量（每小时） | mm | 站点小时内 PWV **平均值** |
| `GET /api/v1/upns/layers/temperature` | TEMPERATURE | 气温图 | ℃ | 站点小时内 **最新一条** 观测 |
| `GET /api/v1/upns/layers/humidity` | HUMIDITY | 湿度图 | %RH | 站点小时内 **最新一条** 观测 |
| `GET /api/v1/upns/layers/pressure` | PRESSURE | 气压图 | hPa | 站点小时内 **最新一条** 观测 |

### 11-14. 获取气象要素插值图层（四个接口共用以下参数与语义）

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| startTime | Long | 否 | — | 起始时间（毫秒），闭区间下界 |
| endTime | Long | 否 | — | 截止时间（毫秒），闭区间上界 |
| minLng | Double | 否 | — | bbox 最小经度（站点过滤） |
| maxLng | Double | 否 | — | bbox 最大经度 |
| minLat | Double | 否 | — | bbox 最小纬度 |
| maxLat | Double | 否 | — | bbox 最大纬度 |
| groupName | String | 否 | — | 裁剪区域组名，不传返回所有组 |

**时间语义**：`startTime/endTime` 均不传 → 只返回最新一个自然小时桶快照；只传 `endTime` → 起始收敛为其前 24 小时；`snapshots` 按 `dataTime` 升序。

**格网语义**：
- 插值范围：bbox 四参数齐全时为 bbox；否则为命中站点外接矩形四边外扩 0.05°
- 格距默认 0.01°（bbox 过大时自动放大格距，单边格点数上限 500），格点覆盖范围两端（含边界）
- `values[row][col]` 第 0 行为最北（maxLat），向南递增，经纬度反算公式与 VO·11 一致
- IDW p=2，全部命中站点参与；站点恰在格点上时直接取站点值

**已知限制**：格网值为站点观测的插值推算而非实测格点，距站点较远区域为外推值，建议配合 `groups[].area` 裁剪后成图。

---

## 附录：响应数据结构（VO 字段定义）

> 除特别说明，数值/集合字段均有默认值（数值 0、字符串 `""`、集合为空）。

### VO·1 UpnsOverviewVO
| 字段 | 类型 | 说明 |
|---|---|---|
| snapshotTime | Long | 快照时间（毫秒） |
| stations | Stations | 站点统计（见下） |
| warnings | Warnings | 预警统计（见下） |
| currentConditions | CurrentConditions | 当前气象条件（见下） |

- **Stations**：`total`(Integer 站点总数)、`online`(Integer 在线)、`offline`(Integer 离线)、`onlineRate`(Double 在线率)
- **Warnings**：`activeCount`(Integer 活跃预警数)、`todayCount`(Integer 今日预警数)、`levelOneCount`/`levelTwoCount`/`levelThreeCount`(Integer 各等级数)
- **CurrentConditions**：`avgTemperature`/`avgHumidity`/`avgRain`/`maxRain`/`maxRainStation`/`avgWindSpeed`/`avgPressure`/`avgPWV`/`maxPWV`/`maxPWVStation`

### VO·2 UpnsStationPageVO
| 字段 | 类型 | 说明 |
|---|---|---|
| total | Long | 总记录数 |
| pageNum | Integer | 当前页码 |
| pageSize | Integer | 每页数量 |
| stations | List&lt;UpnsStationVO&gt; | 站点列表 |

### VO·3 UpnsStationVO
| 字段 | 类型 | 说明 |
|---|---|---|
| stationCode | String | 站点编码 |
| stationName | String | 站点名称 |
| location | LocationVO | 位置（`longitude`/`latitude`/`altitude`，Double） |
| altitude | Double | 海拔 |
| regionCode | String | 区域编码 |
| regionName | String | 区域名称 |
| status | String | 状态（online/offline） |
| lastUpdateTime | Long | 最后更新时间（毫秒） |
| temperature | Double | 当前温度 |
| humidity | Double | 当前湿度 |
| rain | Double | 当前降雨量 |
| windSpeed | Double | 当前风速 |
| windDirection | Double | 当前风向 |
| pressure | Double | 当前气压 |
| pwv | Double | 当前 PWV |
| hasWarning | Boolean | 是否有预警 |
| warningLevel | Integer | 预警等级 |

### VO·4 UpnsRealtimeVO
| 字段 | 类型 | 说明 |
|---|---|---|
| stationCode | String | 站点编码 |
| stationName | String | 站点名称 |
| longitude | Double | 经度 |
| latitude | Double | 纬度 |
| altitude | Double | 海拔 |
| data | MonitoringData | 监测数据（见下） |
| dataTime | Long | 数据时间（毫秒） |
| warningStatus | WarningStatus | 预警状态（见下） |

- **MonitoringData**：`temperature`/`humidity`/`rain`/`windSpeed`/`windDirection`/`pressure`/`pwv`（均 Double）
- **WarningStatus**：`hasWarning`(Boolean)、`level`(Integer 等级)、`threshold`(Double 阈值)、`exceedValue`(Double 超出值)

### VO·5 UpnsHistoryVO
| 字段 | 类型 | 说明 |
|---|---|---|
| stationCode | String | 站点编码 |
| stationName | String | 站点名称 |
| interval | String | 聚合间隔 |
| startTime | Long | 开始时间 |
| endTime | Long | 结束时间 |
| timeSeries | TimeSeriesData | 多指标并行时序数据（见下） |
| statistics | Map&lt;String, FieldStatistics&gt; | 按指标名分组的统计（key 如 `rain`/`pwv`/`temperature`） |
| timestamp | Long | 更新时间 |

- **TimeSeriesData**：`timestamps`(List&lt;Long&gt;) + 各指标 List&lt;Double&gt;：`temperature`(℃)/`humidity`(%RH)/`rain`(mm)/`windSpeed`(m/s)/`windDirection`(°)/`pressure`(hPa)/`pwv`(mm)
- **FieldStatistics**：`avg`/`max`/`min`/`sum`(Double；`sum` 用于降雨等累加字段)

### VO·6 WarningSummaryVO
| 字段 | 类型 | 说明 |
|---|---|---|
| startTime | Long | 统计开始时间 |
| endTime | Long | 统计结束时间 |
| summary | Summary | 预警汇总（见下） |
| levelDistribution | List&lt;LevelDistribution&gt; | 等级分布 |
| timeDistribution | List&lt;TimeDistribution&gt; | 时间分布（按小时） |
| warnings | List&lt;Warning&gt; | 预警详情 |
| timestamp | Long | 更新时间 |

- **Summary**：`totalCount`/`levelOneCount`/`levelTwoCount`/`levelThreeCount`(Integer 总数与各等级数)、`affectedStationCount`/`affectedRegionCount`(Integer 受影响站点/区域数)
- **LevelDistribution**：`level`(Integer)/`count`(Integer)/`percentage`(Double)
- **TimeDistribution**：`hour`(String)/`count`(Integer)
- **Warning**：`warningId`/`code`(String)、`time`(Long)、`level`(Integer)、`threshold`(Double)、`stationCount`(Integer)、`affectedArea`(String)、`maxPWV`(Double)、`maxPWVStation`(String)

### VO·7 UpnsWarningItemVO
| 字段 | 类型 | 说明 |
|---|---|---|
| code | String | 预警编码 |
| stationName | String | 站点名称（对应"区域"列） |
| time | Long | 预警时间（Unix 毫秒） |
| level | Integer | 预警级别（1-4，上游透传值） |
| longitude | Double | 经度 |
| latitude | Double | 纬度 |
| regionCode | String | 区域编码 |
| regionName | String | 区域名称 |

### VO·8 RainfallStatisticsVO
| 字段 | 类型 | 说明 |
|---|---|---|
| period | String | 统计周期（`last_hour`=前一小时；`latest_1000`=回退最近 1000 条） |
| startTime | Long | 开始时间 |
| endTime | Long | 结束时间 |
| topStations | List&lt;TopStation&gt; | 前十站点 |
| statistics | Statistics | 统计信息 |
| regionCode | String | 区域编码（查询参数回显） |
| regionName | String | 区域名称 |
| timestamp | Long | 更新时间 |

- **TopStation**：`rank`/`stationCode`/`stationName`/`longitude`/`latitude`/`rain`(Double)/`regionName`
- **Statistics**：`totalStations`/`measuredStations`(Integer)/`avgRain`/`maxRain`/`minRain`(Double)

### VO·9 RiskAssessmentVO
| 字段 | 类型 | 说明 |
|---|---|---|
| module | String | 模块代码 |
| moduleName | String | 模块名称 |
| assessmentTime | Long | 评估时间 |
| regionCode | String | 区域编码 |
| regionName | String | 区域名称 |
| riskLevel | String | 风险等级（low/medium/high） |
| riskScore | Double | 风险评分 |
| riskFactors | List&lt;RiskFactor&gt; | 风险因子列表 |
| recommendation | String | 建议 |
| timestamp | Long | 更新时间 |

- **RiskFactor**：`factor`/`factorName`/`value`(**Object**，动态类型)/`weight`(Double)/`score`(Double)/`level`(String low/medium/high)

### VO·10 PwvStatisticsVO
结构与 [RainfallStatisticsVO](#vo8-rainfallstatisticsvo) 高度相似，围绕 `pwv`：TopStation 额外含 `temperature`/`humidity`，无 `rain`；Statistics 为 `avgPWV`/`maxPWV`/`minPWV`。`period` 语义同（`last_hour`/`latest_1000`）。
- **TopStation**：`rank`/`stationCode`/`stationName`/`longitude`/`latitude`/`pwv`/`temperature`/`humidity`/`regionName`
- **Statistics**：`totalStations`/`measuredStations`/`avgPWV`/`maxPWV`/`minPWV`

### VO·11 PrecipitationLayerDataVO
| 字段 | 类型 | 说明 |
|---|---|---|
| layer | String | 图层编码 |
| layerName | String | 图层中文名 |
| unit | String | 数值单位（mm） |
| groupName | String | 实际查询组名（传了则回显，否则 null） |
| groups | List&lt;GroupAreaVO&gt; | 命中的裁剪区域（`groupName`+`area` GeoJSON） |
| snapshots | List&lt;LayerSnapshotVO&gt; | 各时刻矩阵，按 dataTime 升序；预测模式固定 1 个 |

- **LayerSnapshotVO**：`dataTime`(Long 数据时间)/`createTime`(Long 发布时间，可空)/`cols`(Integer)/`rows`(Integer)/`bbox`(BboxVO)/`values`(double[][]，第 0 行为最北 maxLat，向南递增)
  - 经纬度反算（等间距）：`dLng=(maxLng-minLng)/(cols-1)`，`dLat=(maxLat-minLat)/(rows-1)`，`点(row,col)=[minLng+col*dLng, maxLat-row*dLat]`
- **BboxVO**：`minLng`/`maxLng`/`minLat`/`maxLat`(Double)
- **GroupAreaVO**：`groupName`(String)/`area`(String GeoJSON)

---

## 附：接口—响应类型对照

| # | 接口 | 响应 data 类型 |
|---|---|---|
| 1 | GET /api/v1/upns/overview | UpnsOverviewVO |
| 2 | GET /api/v1/upns/risk | RiskAssessmentVO |
| 3 | GET /api/v1/upns/stations | UpnsStationPageVO |
| 4 | GET /api/v1/upns/warnings/summary | WarningSummaryVO |
| 5 | GET /api/v1/upns/warnings | List&lt;UpnsWarningItemVO&gt; |
| 6 | GET /api/v1/upns/statistics/rain/now | RainfallStatisticsVO |
| 7 | GET /api/v1/upns/statistics/pwv/now | PwvStatisticsVO |
| 8 | GET /api/v1/upns/stations/{code}/realtime | UpnsRealtimeVO |
| 9 | GET /api/v1/upns/stations/{code}/history | UpnsHistoryVO |
| 10 | GET /api/v1/upns/precipitation/layers | PrecipitationLayerDataVO |
| 11 | GET /api/v1/upns/layers/pwv-hourly | PrecipitationLayerDataVO |
| 12 | GET /api/v1/upns/layers/temperature | PrecipitationLayerDataVO |
| 13 | GET /api/v1/upns/layers/humidity | PrecipitationLayerDataVO |
| 14 | GET /api/v1/upns/layers/pressure | PrecipitationLayerDataVO |


# 0824补充
## 过去1小时内降水量最大前五
### 路由: /api/v1/upns/last1hour_rain_top5

- 请求参数:
maxLng, minLng, maxLat, minLat

- 响应数据:
{
  "code": 200,
  "msg": "操作成功"
  "data": [
    { "area": "XX1区", value: 90 },
    { "area": "XX2区", value: 80 },
    { "area": "XX3区", value: 70 },
    { "area": "XX4区", value: 60 },
    { "area": "XX5区", value: 50 }
  ]
}

---

## 当前大气可降水量最大前五
### 路由: /api/v1/upns/last1hour_pwv_top5


- 请求参数:
maxLng, minLng, maxLat, minLat

- 响应数据:
{
  "code": 200,
  "msg": "操作成功"
  "data": [
    { "area": "XX1区", value: 90 },
    { "area": "XX2区", value: 80 },
    { "area": "XX3区", value: 70 },
    { "area": "XX4区", value: 60 },
    { "area": "XX5区", value: 50 }
  ]
}

---

## 沉降图层(获取目前已生成了WMTS数据的期次列表与图层地址数据)
### 路由: /api/v1/upss/issue_layer

- 请求参数:
无

- 响应数据
{
  "code": 200,
  "msg": "操作成功",
  "data": [
    { "issue": "20250524", "wmts_url": "http://114.255.16.109:7010/sj_raster/v6/wmts/service/system/10001801/1?ak=sf3ebb7eb413fb01aab003391e3e0a27fa"}, 
    { "issue": "20250612", "wmts_url": "http://114.255.16.109:7010/sj_raster/v6/wmts/service/system/10001802/1?ak=sf3ebb7eb413fb01aab003391e3e0a27fa"}, 
  ]
}

### 沉降图显示微信群中提到的8个期次
1. 新增加接口 /api/v1/upss/issue-list 用于固定显示微信群中提到的8个期次.(未来可调整为显示所有期次) （已解决）
  请求结果样例:
{
  "code": 200,
  "msg": "",
  "data": [
    "20250203",
    "20240130",
    "20230204",
    "20220209",
    "20210207",
    "20200222",
    "20190219",
    "20180204"
  ],
  "timestamp": 0
}