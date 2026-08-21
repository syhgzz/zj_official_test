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
    ('XTSKPWV', '大气可降水量（10分钟）'),
    ('XTSKJSXS', '小时降水量'),
    ('XTSKJSXS10Min', '10分钟降水量'),
    ('XTSKJSFZ', '分钟降水量'),
)

FORECAST_OFFSETS_BY_LAYER = {
    'LSTMXSJS': (60,),
    'CONVLSTMXSJS': (60, 120),
}

FORECAST_LAYER_CASES = (
    ('LSTMXSJS', '时序预测模型', 60),
    ('CONVLSTMXSJS', '卷积预测模型', 60),
    ('CONVLSTMXSJS', '卷积预测模型', 120),
)

OBSERVATION_LAYER_CODES = {layer for layer, _ in OBSERVATION_LAYERS}
LAYER_NAMES = dict(OBSERVATION_LAYERS)
LAYER_NAMES.update({layer: layer_name for layer, layer_name, _ in FORECAST_LAYER_CASES})


def test_get_precipitation_layers(
    client: APIClient,
    startTime,
    endTime,
    minLng,
    maxLng,
    minLat,
    maxLat,
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
    title = '降水页: 降雨图层格网数据'

    if layer in OBSERVATION_LAYER_CODES:
        if forecast_offset_minutes is not None:
            raise ValueError(f'观测图层 {layer} 不能传 forecastOffsetMinutes')
    elif layer in FORECAST_OFFSETS_BY_LAYER:
        allowed_offsets = FORECAST_OFFSETS_BY_LAYER[layer]
        if forecast_offset_minutes not in allowed_offsets:
            raise ValueError(
                f'预测图层 {layer} 的 forecastOffsetMinutes '
                f'只能为 {allowed_offsets}'
            )
    else:
        raise ValueError(f'不支持的图层编码：{layer}')

    path = '/api/v1/upns/precipitation/layers'

    params = {
        'layer': layer,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }

    if forecast_offset_minutes is None:
        params['startTime'] = startTime
        params['endTime'] = endTime
        mode_name = '区间'
        file_suffix = 'interval'
    else:
        params['forecastOffsetMinutes'] = forecast_offset_minutes
        mode_name = f'预测{forecast_offset_minutes}分钟'
        file_suffix = f'forecast_{forecast_offset_minutes}min'

    if group_name:
        params['groupName'] = group_name

    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    title = title + f'_{layer.lower()}_{file_suffix}_' + f'{start_dt.strftime("%Y%m%d_%H%M%S")}'

    print_response(
        f'获取降雨图层格网数据（{layer}，{mode_name}）',
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


if __name__ == '__main__':
    """运行 7 个有效图层/预测时间组合，并统一保存响应。"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)
    path = '/api/v1/upns/precipitation/layers'
    response_records = []
    batch_start_dt = datetime.now()

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

    batch_end_dt = datetime.now()

