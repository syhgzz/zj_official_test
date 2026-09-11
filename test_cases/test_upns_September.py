# -*- coding: utf-8 -*-
"""
降水页（September 专项测试用例）

查询时间窗口: 2026-09-01 00:00:00 ~ 2026-09-02 23:59:59
遍历 common.loc_list 中所有城市（排除 "全国"），
复用 test_upns_a / test_upns_w 的降水页接口测试函数，
对每个城市按该时间窗口查询接口数据。
"""

import os
import sys
from datetime import datetime

# 支持直接执行：python test_cases/test_upns_September.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import config
from lib.api_client import APIClient

try:
    from test_cases.common import loc_list
    from test_cases import test_upns_a, test_upns_w
except ImportError:
    from common import loc_list
    import test_upns_a, test_upns_w


# 本次测试的响应保存根目录；按城市拆分，避免多城市同名文件互相覆盖
RESPONSE_ROOT = 'responses_Upns_September'

# 查询时间窗口: 2026-09-01 00:00:00 ~ 2026-09-02 23:59:59
START_TIME = int(datetime(2026, 9, 1, 0, 0, 0).timestamp()) * 1000
END_TIME = int(datetime(2026, 9, 2, 23, 59, 59).timestamp()) * 1000

# 预测图层使用的基准时刻（取时间窗口末端的晚间，用于预报偏移分钟数）
FORECAST_START_TIME = int(datetime(2026, 9, 2, 20, 0, 0).timestamp()) * 1000

# 需要跳过的观测图层（如"降水图(分钟)"），按测试要求不再请求
SKIP_OBSERVATION_LAYERS = {'XTSKJSFZ'}


def set_response_dir(sub_dir):
    """切换响应保存目录到 responses_Upns_September/<sub_dir>，并强制开启保存开关。

    各接口函数内部通过 config.response_dir 读取保存目录；
    response_dir 是 property，需改底层 ConfigParser 生效。
    """
    if not config.config.has_section('test'):
        config.config.add_section('test')
    config.config.set('test', 'save_response', 'true')
    config.config.set('test', 'response_dir', os.path.join(RESPONSE_ROOT, sub_dir))


def run_city(client: APIClient, city: str):
    """对单个城市运行降水页全部接口（test_upns_a + test_upns_w）。"""
    minLng, maxLng, minLat, maxLat = loc_list[city]
    print(f'\n========== 降水页 - {city} ==========')
    set_response_dir(city)

    # ---- 降水页: test_upns_a 的接口 ----
    # 监测站点列表 /api/v1/upns/stations；站点编码服务于单站实时/历史接口
    _, station_codes = test_upns_a.test_get_stations(client, minLng, maxLng, minLat, maxLat)

    # 预警信息列表 /api/v1/upns/warnings
    test_upns_a.test_get_warnings(client, START_TIME, END_TIME, minLng, maxLng, minLat, maxLat)

    # 过去1小时内降水量最大前五地区 /api/v1/upns/last1hour_rain_top5
    test_upns_a.test_get_last1hour_rain_top5(client, minLng, maxLng, minLat, maxLat)

    # 当前大气可降水量最大前五地区 /api/v1/upns/last1hour_pwv_top5
    test_upns_a.test_get_last1hour_pwv_top5(client, minLng, maxLng, minLat, maxLat)

    # 单站实时数据 /api/v1/upns/stations/{code}/realtime、单站历史趋势 /api/v1/upns/stations/{code}/history
    if station_codes:
        print(f'\n共获取到 {len(station_codes)} 个降水监测站，开始测试单站接口。\n')
        for code in station_codes:
            print(f'正在测试降水监测站：{code}')
            test_upns_a.test_get_station_realtime(client, code)
            test_upns_a.test_get_station_history(client, START_TIME, END_TIME, code)
    else:
        print('\n站点列表未返回 stationCode，跳过单站实时/历史接口。\n')

    # ---- 降水页: test_upns_w 的降雨图层 ----
    # 实时观测图层，使用区间模式（时间窗口）
    for layer, layer_name in test_upns_w.OBSERVATION_LAYERS:
        if layer in SKIP_OBSERVATION_LAYERS:
            print(f'\n跳过观测图层：{layer_name}（{layer}）')
            continue
        print(f'\n正在测试观测图层：{layer_name}（{layer}）')
        test_upns_w.test_get_precipitation_layers(
            client,
            START_TIME,
            END_TIME,
            minLng,
            maxLng,
            minLat,
            maxLat,
            layer=layer,
            group_name=test_upns_w.groupName_file,
        )

    # 预测图层，使用基准时刻 + 预报偏移分钟数（60分钟与120分钟各一条目）
    for layer, layer_name, forecast_offset_minutes in test_upns_w.FORECAST_LAYER_CASES:
        print(f'\n正在测试预测图层：{layer_name}（{layer}），{forecast_offset_minutes}分钟后')
        test_upns_w.test_get_precipitation_layers(
            client,
            startTime=FORECAST_START_TIME,
            minLng=minLng,
            maxLng=maxLng,
            minLat=minLat,
            maxLat=maxLat,
            layer=layer,
            forecast_offset_minutes=forecast_offset_minutes,
            group_name=test_upns_w.groupName_file,
        )


if __name__ == '__main__':
    """按城市遍历降水页全部接口测试（排除 "全国"）。"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    cities = [city for city in loc_list if city != '全国']
    print(f'本次测试城市：{cities}')
    print(f'测试时间窗口：{datetime.fromtimestamp(START_TIME / 1000)} ~ {datetime.fromtimestamp(END_TIME / 1000)}')

    for city in cities:
        run_city(client, city)

    print(f'\n测试完成，响应已保存到 {RESPONSE_ROOT}/')
