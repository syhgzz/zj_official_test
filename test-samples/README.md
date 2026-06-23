# test-samples — /api/v1/upss/samples 模拟请求与 protobuf 解析

模拟请求 `GET /api/v1/upss/samples`(区域抽样查询，二进制流响应)，
解析其 protobuf 响应体 `SubsidencePointStream` 并输出抽样结果。

## 接口与响应格式

| 项 | 值 |
|----|----|
| 方法/路径 | `GET /api/v1/upss/samples` |
| 参数 | `issue`(期次 yyyyMMdd)、`minLng`/`maxLng`/`minLat`/`maxLat`(bbox)、`dataType` |
| dataType | `subsidence` 沉降量(mm，默认) / `gradient` 沉降梯度(mm) / `velocity` 沉降速率(mm/年) |
| 响应 | `application/octet-stream`，体为 `SubsidencePointStream` protobuf |
| 错误 | 参数非法时 `text/plain` + HTTP 400(按状态码区分错误与正常二进制流) |

`SubsidencePointStream` 含三个**等长** packed double 数组，按索引一一对应；
`val` 无值的位置填 `0`：

```protobuf
message SubsidencePointStream {
  repeated double lng = 1 [packed = true];  // 经度
  repeated double lat = 2 [packed = true];  // 纬度
  repeated double val = 3 [packed = true];  // 值(沉降量mm / 速率mm·年⁻¹ / 梯度mm)
}
```

## 文件

| 文件 | 说明 |
|------|------|
| `subsidence.proto` | 精简自 `src/main/proto/MessageInfo.proto`，仅含 `SubsidencePointStream`，字段定义与服务端一致 |
| `subsidence_pb2.py` | protoc 生成的 Python 解析类(**已生成**，无需再跑) |
| `request_samples.py` | 模拟请求 + 解析 + 输出主脚本 |
| `README.md` | 本文件 |

## 依赖

```bash
pip install requests
# protobuf 运行时(本机已随项目环境安装；若缺失再装):
pip install protobuf
```

## 重新生成 subsidence_pb2.py(仅当 proto 变更时)

```bash
protoc -I test-samples --python_out=test-samples test-samples/subsidence.proto
```

## 用法

默认参数(任务指定):

```bash
python test-samples/request_samples.py
# 等价参数: minLng=105.782 maxLng=108.345 minLat=28.999 maxLat=30.147 issue=20200222 dataType=subsidence
```

覆盖参数 / 切换数据类型 / 指定服务地址:

```bash
python test-samples/request_samples.py --issue 20221220 --data-type velocity --limit 5
python test-samples/request_samples.py --host http://192.168.1.10:8099
```

保存结果:

```bash
python test-samples/request_samples.py --csv out.csv --raw out.bin
```

## 输出示例

```
GET http://localhost:8099/api/v1/upss/samples
参数: {'minLng': 105.782, 'maxLng': 108.345, 'minLat': 28.999, 'maxLat': 30.147, 'issue': '20200222', 'dataType': 'subsidence'}
收到 296340 字节 protobuf
抽样点数: 12345
经度范围: [105.802, 108.341]
纬度范围: [29.001, 30.146]
沉降量(mm) 全部: min=-42.1, max=35.7
沉降量(mm) 非零(9876/12345): min=-42.1, max=35.7, mean=3.2145

前 10 个样本 (lng, lat, val):
  [0] 105.82, 29.01, 12.34
  ...
```

## 备注

- 验签默认关闭(`app.auth.enabled: false`)，脚本仍按 `application.yml` 中的 `test-app-key` / `test-app-secret-123456` 生成签名头；服务端开启验签后无需改动脚本。
- `val=0` 既可能是真实值，也可能是空值填充；输出同时给出"全部"与"非零"统计便于判断。
- 若服务端无该期次/区域数据，响应点数为 0 或 `val` 全 0。
