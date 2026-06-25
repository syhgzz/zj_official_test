# -*- coding: utf-8 -*-
"""
模拟请求 GET /api/v1/upss/samples 并解析 protobuf 响应。

接口说明:
    - 路径: GET /api/v1/upss/samples
    - 参数: issue(期次 yyyyMMdd)、minLng/maxLng/minLat/maxLat(bbox)、
            dataType(subsidence 沉降量 | gradient 沉降梯度 | velocity 沉降速率)
    - 响应: application/octet-stream，响应体为 SubsidencePointStream protobuf
            (lng/lat/val 三个等长 packed double 数组，按索引一一对应；val 无值填 0)
    - 错误: 参数非法时以 text/plain + HTTP 400 返回(按状态码区分错误与正常二进制流)

依赖: pip install requests
      (protobuf 运行时由本目录 subsidence_pb2.py 携带)
"""

import argparse
import base64
import hashlib
import hmac
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("缺少依赖 requests，请先执行: pip install requests")

# 让脚本能 import 同目录的 subsidence_pb2
sys.path.insert(0, str(Path(__file__).resolve().parent))
import subsidence_pb2  # type: ignore  # noqa: E402  (protoc 生成，类型由 descriptor 动态构造)


# ---------- 配置(默认值，可用命令行参数覆盖) ----------
DEFAULT_HOST = "http://175.155.229.220:19000"
DEFAULT_APP_KEY = "test-app-key"            # 见 application.yml: app.auth.credentials
DEFAULT_APP_SECRET = "test-app-secret-123456"

# 任务指定的默认请求参数
DEFAULT_PARAMS = {
    "minLng": 105.782,
    "maxLng": 108.345,
    "minLat": 28.999,
    "maxLat": 30.147,
    # "issue": "20200222",
    "issue": "20250203",
    "dataType": "subsidence",
}

# dataType -> val 的物理含义(用于输出标注)
VAL_LABEL = {
    "subsidence": "沉降量(mm)",
    "gradient": "沉降梯度(mm)",
    "velocity": "沉降速率(mm/年)",
}


# ---------- 签名(算法与 test/lib/signature.py、服务端一致) ----------
def sign_headers(app_key, app_secret):
    """生成 appKey/timestamp/sign 请求头。enabled=false 时服务端忽略，带上无副作用。"""
    timestamp = str(int(time.time() * 1000))
    sign_string = f"{timestamp}\n{app_secret}"
    digest = hmac.new(
        app_secret.encode("utf-8"),
        sign_string.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return {
        "appKey": app_key,
        "timestamp": timestamp,
        "sign": base64.b64encode(digest).decode("utf-8"),
    }


# ---------- 请求 ----------
def fetch_samples(host, params, app_key, app_secret, timeout=30):
    url = f"{host.rstrip('/')}/api/v1/upss/samples"
    headers = {"Accept": "application/octet-stream", **sign_headers(app_key, app_secret)}
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        # 参数错误等服务端以纯文本返回，按 HTTP 状态码区分错误与正常二进制流
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
    return resp.content


# ---------- 解析与输出 ----------
def parse(body):
    stream = subsidence_pb2.SubsidencePointStream()
    stream.ParseFromString(body)
    return stream


def summarize(stream, val_label):
    n = len(stream.lng)
    print(f"抽样点数: {n}")
    if n == 0:
        print("(响应为空：该期次/区域可能无数据)")
        return
    lngs, lats, vals = stream.lng, stream.lat, stream.val
    print(f"经度范围: [{min(lngs)}, {max(lngs)}]")
    print(f"纬度范围: [{min(lats)}, {max(lats)}]")
    print(f"{val_label} 全部: min={min(vals)}, max={max(vals)}")
    nonzero = [v for v in vals if v != 0.0]
    if nonzero:
        print(f"{val_label} 非零({len(nonzero)}/{n}): "
              f"min={min(nonzero)}, max={max(nonzero)}, mean={sum(nonzero) / len(nonzero):.4f}")
    else:
        print(f"{val_label} 全为 0：该期次/区域可能无有效数据(服务端空值也填 0)")


def preview(stream, limit=10):
    n = min(limit, len(stream.lng))
    print(f"\n前 {n} 个样本 (lng, lat, val):")
    for i in range(n):
        print(f"  [{i}] {stream.lng[i]}, {stream.lat[i]}, {stream.val[i]}")


def save_csv(stream, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("index,lng,lat,val\n")
        for i in range(len(stream.lng)):
            f.write(f"{i},{stream.lng[i]},{stream.lat[i]},{stream.val[i]}\n")
    print(f"已保存 CSV: {path} ({len(stream.lng)} 行)")


# ---------- main ----------
def build_arg_parser():
    ap = argparse.ArgumentParser(description="请求 /api/v1/upss/samples 并解析 protobuf 响应")
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"服务地址，默认 {DEFAULT_HOST}")
    ap.add_argument("--app-key", default=DEFAULT_APP_KEY)
    ap.add_argument("--app-secret", default=DEFAULT_APP_SECRET)
    ap.add_argument("--issue", default=DEFAULT_PARAMS["issue"], help="期次 yyyyMMdd")
    ap.add_argument("--min-lng", type=float, default=DEFAULT_PARAMS["minLng"])
    ap.add_argument("--max-lng", type=float, default=DEFAULT_PARAMS["maxLng"])
    ap.add_argument("--min-lat", type=float, default=DEFAULT_PARAMS["minLat"])
    ap.add_argument("--max-lat", type=float, default=DEFAULT_PARAMS["maxLat"])
    ap.add_argument("--data-type", default=DEFAULT_PARAMS["dataType"],
                    choices=["subsidence", "gradient", "velocity"])
    ap.add_argument("--limit", type=int, default=100, help="预览样本条数")
    ap.add_argument("--csv", type=str, default="./responses/stream.csv", help="将解析结果保存为 CSV 的路径")
    ap.add_argument("--raw", type=str, default="./responses/stream.bin", help="将原始 protobuf 二进制保存到该路径(便于调试)")
    ap.add_argument("--timeout", type=int, default=30, help="请求超时秒数，默认 30")
    return ap


def test_api_v1_upss_samples(
    host=DEFAULT_HOST,
    app_key=DEFAULT_APP_KEY,
    app_secret=DEFAULT_APP_SECRET,
    issue=DEFAULT_PARAMS["issue"],
    min_lng=DEFAULT_PARAMS["minLng"],
    max_lng=DEFAULT_PARAMS["maxLng"],
    min_lat=DEFAULT_PARAMS["minLat"],
    max_lat=DEFAULT_PARAMS["maxLat"],
    data_type=DEFAULT_PARAMS["dataType"],
    limit=100,
    csv="./responses/stream.csv",
    raw="./responses/stream.bin",
    timeout=30,
):
    """请求 /api/v1/upss/samples 并解析 protobuf 响应"""
    Path(csv).parent.mkdir(parents=True, exist_ok=True)
    Path(raw).parent.mkdir(parents=True, exist_ok=True)
    params = {
        "minLng": min_lng,
        "maxLng": max_lng,
        "minLat": min_lat,
        "maxLat": max_lat,
        "issue": issue,
        "dataType": data_type,
    }
    print(f"GET {host}/api/v1/upss/samples")
    print(f"参数: {params}")

    try:
        body = fetch_samples(host, params, app_key, app_secret, timeout=timeout)
    except requests.exceptions.ConnectionError:
        sys.exit(f"连接失败：请确认服务已启动 {host}")
    except requests.exceptions.Timeout:
        sys.exit(f"请求超时({timeout}s)")
    except RuntimeError as e:
        sys.exit(str(e))

    print(f"收到 {len(body)} 字节 protobuf")
    if raw:
        Path(raw).write_bytes(body)
        print(f"已保存原始二进制: {raw}")

    try:
        stream = parse(body)
    except Exception as e:
        sys.exit(f"protobuf 解析失败: {e}\n(响应可能非二进制流，前 200 字节: {body[:200]!r})")

    summarize(stream, VAL_LABEL.get(data_type, "val"))
    preview(stream, limit)
    if csv:
        save_csv(stream, csv)


if __name__ == "__main__":
    issues = ["20250203", "20250110"]
    data_types = ["subsidence", "gradient", "velocity"]

    for issue in issues:
        for data_type in data_types:
            suffix = f"{issue}_{data_type}"
            csv_path = f"./responses/samples_{suffix}.csv"
            raw_path = f"./responses/samples_{suffix}.bin"
            print(f"\n{'=' * 60}")
            print(f"测试: issue={issue}, dataType={data_type}")
            print(f"{'=' * 60}")
            test_api_v1_upss_samples(issue=issue, data_type=data_type, csv=csv_path, raw=raw_path)
