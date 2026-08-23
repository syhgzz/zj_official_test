# -*- coding: utf-8 -*-
"""
降水页
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config

try:
    from test_cases.common import *
except ImportError:
    from common import *


# 可选的裁剪区域组名；None 表示不限定组。
groupName_file = None

OBSERVATION_LAYERS = (
    ('XTSKPWV', '可降水量(10分钟)'),
    ('XTSKJSXS', '降水量(小时)'),
    ('XTSKJSXS10Min', '降水量(10分钟)'),
    ('XTSKJSFZ', '降水量(分钟)'),
)

FORECAST_LAYERS = {
    'LSTMXSJS': '时序预测模型',
    'CONVLSTMXSJS': '卷积预测模型',
}

FORECAST_LAYER_CASES = (
    ('LSTMXSJS', '时序预测模型', 60),
    ('CONVLSTMXSJS', '卷积预测模型', 60),
    ('CONVLSTMXSJS', '卷积预测模型', 120),
)

OBSERVATION_LAYER_CODES = {layer for layer, _ in OBSERVATION_LAYERS}
LAYER_NAMES = dict(OBSERVATION_LAYERS)
LAYER_NAMES.update(FORECAST_LAYERS)

def _optional_layer_params(
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """仅把已传入的公共图层查询参数放入请求。"""
    params = {}
    optional_params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
        'groupName': group_name,
    }
    for name, value in optional_params.items():
        if value is not None and (name != 'groupName' or value):
            params[name] = value
    return params


def _request_meteorological_layer(
    client: APIClient,
    endpoint: str,
    layer: str,
    layer_name: str,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """执行气象要素插值图层请求，并按项目统一格式打印和保存响应。"""
    number = ''
    title = f'降水页: {layer_name}_{layer}'
    path = f'/api/v1/upns/layers/{endpoint}'
    params = _optional_layer_params(
        startTime,
        endTime,
        minLng,
        maxLng,
        minLat,
        maxLat,
        group_name,
    )

    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    print_response(
        f'获取气象要素插值图层（{layer_name}，{layer}）',
        'GET',
        path,
        response,
        config.verbose,
        number=number,
        title=title,
        elapsed_seconds=elapsed,
    )

    if config.save_response and response:
        save_response_to_file(
            f'upns_layer_{endpoint.replace("-", "_")}',
            response,
            path,
            params,
            config.response_dir,
            number=number,
            title=title,
            start_time=start_dt,
            end_time=end_dt,
        )

    return response


# -----------------------------------------------------------------------------
# 接口 10：降雨图层格网数据
# 返回降雨图层多时刻规则二维矩阵；通过 forecastOffsetMinutes 切换区间/预测模式。
# GET /api/v1/upns/precipitation/layers
# -----------------------------------------------------------------------------
def test_get_precipitation_layers(
    client: APIClient,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    layer: str = 'XTSKJSXS',
    forecast_offset_minutes: int = None,
    group_name: str = None,
    response_records: list = None,
):
    """
    降水页: 测试获取降雨图层格网数据。

    forecast_offset_minutes 为 None 时按时间区间查询；
    传入预测偏移分钟数时查询单个预测时刻。
    GET /api/v1/upns/precipitation/layers
    """
    number = ''
    layer_name = LAYER_NAMES[layer]
    title = f'降水页: 降雨图层格网数据_{layer_name}_{layer}'

    if layer in OBSERVATION_LAYER_CODES:
        if forecast_offset_minutes is not None:
            raise ValueError(f'观测图层 {layer} 不能传 forecastOffsetMinutes')
    elif layer in FORECAST_LAYERS:
        if forecast_offset_minutes is not None and forecast_offset_minutes < 0:
            raise ValueError('forecastOffsetMinutes 不能为负数')
    else:
        raise ValueError(f'不支持的图层编码：{layer}')

    path = '/api/v1/upns/precipitation/layers'

    params = _optional_layer_params(
        minLng=minLng,
        maxLng=maxLng,
        minLat=minLat,
        maxLat=maxLat,
        group_name=group_name,
    )
    params['layer'] = layer

    if forecast_offset_minutes is None:
        if startTime is not None:
            params['startTime'] = startTime
        if endTime is not None:
            params['endTime'] = endTime
        if startTime is None and endTime is None:
            raise ValueError('必须传入 startTime 或 endTime')
    else:
        params['forecastOffsetMinutes'] = forecast_offset_minutes

    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    title = title + f'_{start_dt.strftime("%Y%m%d_%H%M%S")}'

    print_response(
        title,
        'GET',
        path,
        response,
        config.verbose,
        number=number,
        title=title,
        elapsed_seconds=elapsed,
    )

    if response_records is not None:
        response_records.append({
            'layer': layer,
            'layer_name': LAYER_NAMES.get(layer, layer),
            'mode': 'interval' if forecast_offset_minutes is None else 'forecast',
            'request_params': params,
            'start_time': start_dt.isoformat(),
            'end_time': end_dt.isoformat(),
            'elapsed_seconds': round(elapsed, 3),
            'response': response,
        })

    if config.save_response and response:
        # 每个图层/模式单独保存一份，文件名带 layer、模式与时间戳后缀，避免互相覆盖
        save_response_to_file(
            title,
            response,
            path,
            params,
            config.response_dir,
            number=number,
            title=title,
            start_time=start_dt,
            end_time=end_dt,
        )

    return response


# -----------------------------------------------------------------------------
# 接口 11：大气可降水量（每小时）插值图层
# 将站点自然小时内的 PWV 平均值通过 IDW 插值为规则二维矩阵。
# GET /api/v1/upns/layers/pwv-hourly
# -----------------------------------------------------------------------------
def test_get_pwv_hourly_layer(
    client: APIClient,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """
    降水页: 测试获取大气可降水量（每小时）插值图层。
    GET /api/v1/upns/layers/pwv-hourly
    """
    return _request_meteorological_layer(
        client, 'pwv-hourly', 'PWVHOURLY', '大气可降水量（每小时）',
        startTime, endTime, minLng, maxLng, minLat, maxLat, group_name,
    )


# -----------------------------------------------------------------------------
# 接口 12：气温插值图层
# 将站点自然小时内最新一条气温观测通过 IDW 插值为规则二维矩阵。
# GET /api/v1/upns/layers/temperature
# -----------------------------------------------------------------------------
def test_get_temperature_layer(
    client: APIClient,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """
    降水页: 测试获取气温插值图层。
    GET /api/v1/upns/layers/temperature
    """
    return _request_meteorological_layer(
        client, 'temperature', 'TEMPERATURE', '气温图',
        startTime, endTime, minLng, maxLng, minLat, maxLat, group_name,
    )


# -----------------------------------------------------------------------------
# 接口 13：湿度插值图层
# 将站点自然小时内最新一条湿度观测通过 IDW 插值为规则二维矩阵。
# GET /api/v1/upns/layers/humidity
# -----------------------------------------------------------------------------
def test_get_humidity_layer(
    client: APIClient,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """
    降水页: 测试获取湿度插值图层。
    GET /api/v1/upns/layers/humidity
    """
    return _request_meteorological_layer(
        client, 'humidity', 'HUMIDITY', '湿度图',
        startTime, endTime, minLng, maxLng, minLat, maxLat, group_name,
    )


# -----------------------------------------------------------------------------
# 接口 14：气压插值图层
# 将站点自然小时内最新一条气压观测通过 IDW 插值为规则二维矩阵。
# GET /api/v1/upns/layers/pressure
# -----------------------------------------------------------------------------
def test_get_pressure_layer(
    client: APIClient,
    startTime=None,
    endTime=None,
    minLng=None,
    maxLng=None,
    minLat=None,
    maxLat=None,
    group_name: str = None,
):
    """
    降水页: 测试获取气压插值图层。
    GET /api/v1/upns/layers/pressure
    """
    return _request_meteorological_layer(
        client, 'pressure', 'PRESSURE', '气压图',
        startTime, endTime, minLng, maxLng, minLat, maxLat, group_name,
    )


if __name__ == '__main__':
    """运行降雨图层与气象要素插值图层接口测试。"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)
    response_records = []

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2026, 8, 13, 3, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2026, 8, 13, 3, 40, 0).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 降水页: 降雨图层格网数据 /api/v1/upns/precipitation/layers
    # 4 个实时观测图层使用区间模式。
    for layer, layer_name in OBSERVATION_LAYERS:
        print(f'\n正在测试观测图层：{layer_name}（{layer}）')
        test_get_precipitation_layers(
            client,
            startTime,
            endTime,
            minLng,
            maxLng,
            minLat,
            maxLat,
            layer=layer,
            group_name=groupName_file,
            response_records=response_records,
        )

    # 降水页: 降雨图层格网数据 /api/v1/upns/precipitation/layers
    # LSTM 测试 1 小时；CONVLSTM 分别测试 1 小时和 2 小时。
    for layer, layer_name, forecast_offset_minutes in FORECAST_LAYER_CASES:
        print(
            f'\n正在测试预测图层：{layer_name}（{layer}），'
            f'{forecast_offset_minutes}分钟后'
        )
        test_get_precipitation_layers(
            client,
            startTime,
            endTime,
            minLng,
            maxLng,
            minLat,
            maxLat,
            layer=layer,
            forecast_offset_minutes=forecast_offset_minutes,
            group_name=groupName_file,
            response_records=response_records,
        )

    # 降水页: 大气可降水量（每小时）插值图层 /api/v1/upns/layers/pwv-hourly
    test_get_pwv_hourly_layer(
        client, startTime, endTime, minLng, maxLng, minLat, maxLat, groupName_file,
    )

    # 降水页: 气温插值图层 /api/v1/upns/layers/temperature
    test_get_temperature_layer(
        client, startTime, endTime, minLng, maxLng, minLat, maxLat, groupName_file,
    )

    # 降水页: 湿度插值图层 /api/v1/upns/layers/humidity
    test_get_humidity_layer(
        client, startTime, endTime, minLng, maxLng, minLat, maxLat, groupName_file,
    )

    # 降水页: 气压插值图层 /api/v1/upns/layers/pressure
    test_get_pressure_layer(
        client, startTime, endTime, minLng, maxLng, minLat, maxLat, groupName_file,
    )

