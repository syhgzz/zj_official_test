# -*- coding: utf-8 -*-
"""
降水页
"""
import os
import sys
from datetime import datetime

# 支持直接执行：python test_cases/test_upns.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import config
from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file

try:
    from test_cases.common import *
except ImportError:
    from common import *


startTime_file = startTime_global
endTime_file = endTime_global
minLng_file = minLng_global
maxLng_file = maxLng_global
minLat_file = minLat_global
maxLat_file = maxLat_global

UPNS_BASE_PATH = '/api/v1/upns'


def _request_and_record(
    client: APIClient,
    path: str,
    params: dict,
    display_name: str,
    file_name: str,
    number: str,
    title: str,
):
    """统一执行 GET 请求，并沿用项目现有格式打印、计时和保存响应。"""
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    print_response(
        display_name,
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
            file_name,
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
# 降水页_模块概览
# 服务于大屏整体概况，包括站点在线情况、预警数量和当前平均气象条件。
# GET /api/v1/upns/overview
# -----------------------------------------------------------------------------
def test_get_overview(client: APIClient):
    """降水页_测试获取短临降水预警模块概览。"""
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/overview',
        {},
        '降水页_获取短临降水预警模块概览',
        'upns_overview',
        '',
        '降水页_模块概览',
    )


# -----------------------------------------------------------------------------
# 降水页_风险评估
# 服务于区域风险等级、评分、风险因素和处置建议展示。
# GET /api/v1/upns/risk
# -----------------------------------------------------------------------------
def test_get_risk(client: APIClient, region_code: str = None):
    """降水页_测试获取短临降水风险评估，可选按区域编码筛选。"""
    params = {}
    if region_code:
        params['regionCode'] = region_code
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/risk',
        params,
        '降水页_获取短临降水风险评估',
        'upns_risk',
        '',
        '降水页_风险评估',
    )


# -----------------------------------------------------------------------------
# 降水页_监测站点列表
# 服务于地图站点和站点下拉框；返回的 stationCode 继续服务单站实时数据、历史趋势接口。
# GET /api/v1/upns/stations
# -----------------------------------------------------------------------------
def test_get_stations(client: APIClient, page_num: int = 1, page_size: int = 20):
    """降水页_测试获取监测站点列表，并返回响应及站点编码列表。"""
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
    }
    response = _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/stations',
        params,
        '降水页_获取降水监测站点列表',
        'upns_stations',
        '',
        '降水页_监测站点列表',
    )

    stations = []
    if response and isinstance(response.get('data'), dict):
        stations = response['data'].get('stations', []) or []
    station_codes = [
        station['stationCode']
        for station in stations
        if isinstance(station, dict) and station.get('stationCode')
    ]
    return response, station_codes


# -----------------------------------------------------------------------------
# 降水页_预警信息列表
# 服务于大屏左上角“预警信息”，必须传入 BBOX 和起止时间。
# GET /api/v1/upns/warnings
# -----------------------------------------------------------------------------
def test_get_warnings(client: APIClient):
    """降水页_测试按地理范围和时间范围获取降水预警列表。"""
    params = {
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
        'startTime': startTime_file,
        'endTime': endTime_file,
    }
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/warnings',
        params,
        '降水页_获取降水预警信息列表',
        'upns_warnings',
        '',
        '降水页_预警信息列表',
    )


# -----------------------------------------------------------------------------
# 降水页_过去一小时降雨量统计
# 服务于大屏“过去1小时内降水量最大前五/前十”排名图表。
# GET /api/v1/upns/statistics/rain/now
# -----------------------------------------------------------------------------
def test_get_rain_statistics_now(client: APIClient):
    """降水页_测试获取过去一小时降雨量排名统计。"""
    params = {
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
    }
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/statistics/rain/now',
        params,
        '降水页_获取过去一小时降雨量统计',
        'upns_statistics_rain_now',
        '',
        '降水页_过去一小时降雨量统计',
    )


# -----------------------------------------------------------------------------
# 降水页_当前大气可降水量统计
# 服务于大屏“当前大气可降水量最大前五/前十”排名图表。
# GET /api/v1/upns/statistics/pwv/now
# -----------------------------------------------------------------------------
def test_get_pwv_statistics_now(client: APIClient):
    """降水页_测试获取当前大气可降水量排名统计。"""
    params = {
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
    }
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/statistics/pwv/now',
        params,
        '降水页_获取当前大气可降水量统计',
        'upns_statistics_pwv_now',
        '',
        '降水页_当前大气可降水量统计',
    )


# -----------------------------------------------------------------------------
# 降水页_过去1小时降水量最大前五
# 服务于大屏“过去1小时内降水量最大前五”排名展示。
# GET /api/v1/upns/last1hour_rain_top5
# -----------------------------------------------------------------------------
def test_get_last1hour_rain_top5(client: APIClient):
    """降水页_测试获取过去1小时内降水量最大前五。"""
    params = {
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
    }
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/last1hour_rain_top5',
        params,
        '降水页_获取过去1小时内降水量最大前五',
        'upns_last1hour_rain_top5',
        '',
        '降水页_过去1小时降水量最大前五',
    )


# -----------------------------------------------------------------------------
# 降水页_当前大气可降水量最大前五
# 服务于大屏“当前大气可降水量最大前五”排名展示。
# GET /api/v1/upns/last1hour_pwv_top5
# -----------------------------------------------------------------------------
def test_get_last1hour_pwv_top5(client: APIClient):
    """降水页_测试获取当前大气可降水量最大前五。"""
    params = {
        'minLng': minLng_file,
        'maxLat': maxLat_file,
        'maxLng': maxLng_file,
        'minLat': minLat_file,
    }
    return _request_and_record(
        client,
        f'{UPNS_BASE_PATH}/last1hour_pwv_top5',
        params,
        '降水页_获取当前大气可降水量最大前五',
        'upns_last1hour_pwv_top5',
        '',
        '降水页_当前大气可降水量最大前五',
    )


# -----------------------------------------------------------------------------
# 降水页_指定站点实时数据
# 服务于单站最新温度、湿度、降雨、气压、PWV 和预警状态展示。
# 依赖监测站点列表返回的 stationCode。
# GET /api/v1/upns/stations/{code}/realtime
# -----------------------------------------------------------------------------
def test_get_station_realtime(client: APIClient, code: str):
    """降水页_测试获取指定降水监测站点的最新实时数据。"""
    path = f'{UPNS_BASE_PATH}/stations/{code}/realtime'
    return _request_and_record(
        client,
        path,
        {},
        f'降水页_获取站点 {code} 实时数据',
        f'upns_station_{code}_realtime',
        '',
        '降水页_单站实时数据',
    )


# -----------------------------------------------------------------------------
# 降水页_指定站点历史趋势
# 服务于右侧站点降水/PWV/温湿度等历史曲线和汇总统计。
# 依赖监测站点列表返回的 stationCode。
# GET /api/v1/upns/stations/{code}/history
# -----------------------------------------------------------------------------
def test_get_station_history(client: APIClient, code: str):
    """降水页_测试获取指定站点在公共时间范围内的多指标历史趋势。"""
    path = f'{UPNS_BASE_PATH}/stations/{code}/history'
    params = {
        'metrics': 'temperature,humidity,rain,windSpeed,windDirection,pressure,pwv',
        'interval': '1h',
        'startTime': startTime_file,
        'endTime': endTime_file,
    }
    return _request_and_record(
        client,
        path,
        params,
        f'降水页_获取站点 {code} 历史趋势',
        f'upns_station_{code}_history',
        '',
        '降水页_单站历史趋势',
    )


# -----------------------------------------------------------------------------
# 降水页_区域降水统计
# 服务于行政区域维度的降雨量、PWV、预警时序及汇总展示。
# GET /api/v1/upns/statistics/regional
# -----------------------------------------------------------------------------

def run_all_tests():
    """按依赖顺序运行降水页的全部接口测试。"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 降水页_模块概览 /api/v1/upns/overview
    test_get_overview(client)

    # 降水页_风险评估 /api/v1/upns/risk
    test_get_risk(client)

    # 降水页_监测站点列表 /api/v1/upns/stations；站点编码服务于单站实时数据、历史趋势测试。
    _, station_codes = test_get_stations(client)

    # 降水页_预警信息列表 /api/v1/upns/warnings
    test_get_warnings(client)

    # 降水页_过去一小时降雨量统计 /api/v1/upns/statistics/rain/now
    test_get_rain_statistics_now(client)

    # 降水页_当前大气可降水量统计 /api/v1/upns/statistics/pwv/now
    test_get_pwv_statistics_now(client)

    # 降水页_过去1小时降水量最大前五 /api/v1/upns/last1hour_rain_top5
    test_get_last1hour_rain_top5(client)

    # 降水页_当前大气可降水量最大前五 /api/v1/upns/last1hour_pwv_top5
    test_get_last1hour_pwv_top5(client)

    # 降水页_单站实时数据 /api/v1/upns/stations/{code}/realtime、
    # 降水页_单站历史趋势 /api/v1/upns/stations/{code}/history
    if station_codes:
        print(f'\n共获取到 {len(station_codes)} 个降水监测站，开始测试单站接口。\n')
        for code in station_codes:
            print(f'正在测试降水监测站：{code}')
            test_get_station_realtime(client, code)
            test_get_station_history(client, code)
    else:
        print('\n站点列表未返回 stationCode，跳过依赖站点编码的单站接口。\n')


if __name__ == '__main__':
    run_all_tests()
