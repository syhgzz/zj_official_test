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
# 接口 1：模块概览
# 服务于大屏整体概况，包括站点在线情况、预警数量和当前平均气象条件。
# GET /api/v1/upns/overview
# -----------------------------------------------------------------------------
def test_get_overview(client: APIClient):
    """降水页: 测试获取短临降水预警模块概览。"""
    path = '/api/v1/upns/overview'
    params = {}
    file_name = 'upns_overview'
    number = ''
    title = '降水页: 模块概览'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 2：风险评估
# 服务于区域风险等级、评分、风险因素和处置建议展示。
# GET /api/v1/upns/risk
# -----------------------------------------------------------------------------
def test_get_risk(client: APIClient, region_code: str = None):
    """降水页: 测试获取短临降水风险评估，可选按区域编码筛选。"""
    path = '/api/v1/upns/risk'
    params = {}
    if region_code:
        params['regionCode'] = region_code
    file_name = 'upns_risk'
    number = ''
    title = '降水页: 风险评估'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 3：监测站点列表
# 服务于地图站点和站点下拉框；返回的 stationCode 继续服务接口 7、8。
# GET /api/v1/upns/stations
# -----------------------------------------------------------------------------
def test_get_stations(client: APIClient, minLng, maxLng, minLat, maxLat, page_num: int = 1, page_size: int = 20):
    """降水页: 测试获取监测站点列表，并返回响应及站点编码列表。"""
    path = '/api/v1/upns/stations'
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
        'minLng': minLng,
        'maxLat': maxLat,
        'maxLng': maxLng,
        'minLat': minLat,
    }
    file_name = 'upns_stations'
    number = ''
    title = '降水页: 监测站点列表'
    response = _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)

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
# 接口 4：预警信息列表
# 服务于大屏左上角“预警信息”，必须传入 BBOX 和起止时间。
# GET /api/v1/upns/warnings
# -----------------------------------------------------------------------------
def test_get_warnings(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """降水页: 测试按地理范围和时间范围获取降水预警列表。"""
    path = '/api/v1/upns/warnings'
    params = {
        'minLng': minLng,
        'maxLat': maxLat,
        'maxLng': maxLng,
        'minLat': minLat,
        'startTime': startTime,
        'endTime': endTime,
    }
    file_name = 'upns_warnings'
    number = ''
    title = '降水页: 预警信息列表'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 5：过去一小时降雨量统计
# 服务于大屏“过去1小时内降水量最大前五/前十”排名图表。
# GET /api/v1/upns/statistics/rain/now
# -----------------------------------------------------------------------------
def test_get_rain_statistics_now(client: APIClient, minLng, maxLng, minLat, maxLat):
    """降水页: 测试获取过去一小时降雨量排名统计。"""
    path = '/api/v1/upns/statistics/rain/now'
    params = {
        'minLng': minLng,
        'maxLat': maxLat,
        'maxLng': maxLng,
        'minLat': minLat,
    }
    file_name = 'upns_statistics_rain_now'
    number = ''
    title = '降水页: 过去一小时降雨量统计'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 6：当前大气可降水量（PWV）统计
# 服务于大屏“当前大气可降水量最大前五/前十”排名图表。
# GET /api/v1/upns/statistics/pwv/now
# -----------------------------------------------------------------------------
def test_get_pwv_statistics_now(client: APIClient, minLng, maxLng, minLat, maxLat):
    """降水页: 测试获取当前大气可降水量排名统计。"""
    path = '/api/v1/upns/statistics/pwv/now'
    params = {
        'minLng': minLng,
        'maxLat': maxLat,
        'maxLng': maxLng,
        'minLat': minLat,
    }
    file_name = 'upns_statistics_pwv_now'
    number = ''
    title = '降水页: 当前大气可降水量统计'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 7：指定站点实时数据
# 服务于单站最新温度、湿度、降雨、气压、PWV 和预警状态展示。
# 依赖接口 3 返回的 stationCode。
# GET /api/v1/upns/stations/{code}/realtime
# -----------------------------------------------------------------------------
def test_get_station_realtime(client: APIClient, code: str):
    """降水页: 测试获取指定降水监测站点的最新实时数据。"""
    path = f'/api/v1/upns/stations/{code}/realtime'
    params = {}
    file_name = f'upns_station_{code}_realtime'
    number = ''
    title = '降水页: 单站实时数据'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 8：指定站点历史趋势
# 服务于右侧站点降水/PWV/温湿度等历史曲线和汇总统计。
# 依赖接口 3 返回的 stationCode。
# GET /api/v1/upns/stations/{code}/history
# -----------------------------------------------------------------------------
def test_get_station_history(client: APIClient, startTime, endTime, code: str):
    """降水页: 测试获取指定站点在公共时间范围内的多指标历史趋势。"""
    path = f'/api/v1/upns/stations/{code}/history'
    params = {
        'metrics': 'temperature,humidity,rain,windSpeed,windDirection,pressure,pwv',
        'interval': '1h',
        'startTime': startTime,
        'endTime': endTime,
    }
    file_name = f'upns_station_{code}_history'
    number = ''
    title = '降水页: 单站历史趋势'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 9：区域降水统计
# 服务于行政区域维度的降雨量、PWV、预警时序及汇总展示。
# GET /api/v1/upns/statistics/regional
# -----------------------------------------------------------------------------
def test_get_regional_statistics(client: APIClient, region_code: str = None):
    """降水页: 测试获取区域降水、PWV 和预警统计。"""
    path = '/api/v1/upns/statistics/regional'
    params = {}
    if region_code:
        params['regionCode'] = region_code
    file_name = 'upns_statistics_regional'
    number = ''
    title = '降水页: 区域降水统计'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 10：过去1小时内降水量最大前五
# 服务于大屏"过去1小时内降水量最大前五"排名展示。
# GET /api/v1/upns/last1hour_rain_top5
# -----------------------------------------------------------------------------
def test_get_last1hour_rain_top5(client: APIClient, minLng, maxLng, minLat, maxLat):
    """降水页: 测试获取过去1小时内降水量最大前五地区"""
    path = '/api/v1/upns/last1hour_rain_top5'
    params = {
        'minLng': minLng,
        'maxLat': maxLat,
        'maxLng': maxLng,
        'minLat': minLat,
    }
    file_name = 'upns_last1hour_rain_top5'
    number = ''
    title = '降水页: 过去1小时降水量前五地区'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


# -----------------------------------------------------------------------------
# 接口 11：当前大气可降水量最大前五
# 服务于大屏"当前大气可降水量最大前五"排名展示。
# GET /api/v1/upns/last1hour_pwv_top5
# -----------------------------------------------------------------------------
def test_get_last1hour_pwv_top5(client: APIClient, minLng, maxLng, minLat, maxLat):
    """降水页: 测试获取当前大气可降水量最大前五地区"""
    path = '/api/v1/upns/last1hour_pwv_top5'
    params = {
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    file_name = 'upns_last1hour_pwv_top5'
    number = ''
    title = '降水页: 当前大气可降水量前五地区'
    return _request_and_record(client, path=path, params=params, display_name=title, file_name=file_name, number=number, title=title)


if __name__ == '__main__':
    """按依赖顺序运行降水页的全部接口测试。"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2026, 5, 5, 0, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2026, 6, 5, 23, 59, 59).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 降水页: 模块概览 /api/v1/upns/overview
    test_get_overview(client)

    # 降水页: 风险评估 /api/v1/upns/risk
    test_get_risk(client)

    # 降水页: 监测站点列表 /api/v1/upns/stations；站点编码服务于单站实时/历史接口
    _, station_codes = test_get_stations(client, minLng, maxLng, minLat, maxLat)

    # 降水页: 预警信息列表 /api/v1/upns/warnings
    test_get_warnings(client, startTime, endTime, minLng, maxLng, minLat, maxLat)

    # 降水页: 过去一小时降雨量统计 /api/v1/upns/statistics/rain/now
    test_get_rain_statistics_now(client, minLng, maxLng, minLat, maxLat)

    # 降水页: 当前大气可降水量统计 /api/v1/upns/statistics/pwv/now
    test_get_pwv_statistics_now(client, minLng, maxLng, minLat, maxLat)

    # 降水页: 单站实时数据 /api/v1/upns/stations/{code}/realtime、
    # 降水页: 单站历史趋势 /api/v1/upns/stations/{code}/history
    if station_codes:
        print(f'\n共获取到 {len(station_codes)} 个降水监测站，开始测试单站接口。\n')
        for code in station_codes:
            print(f'正在测试降水监测站：{code}')
            test_get_station_realtime(client, code)
            test_get_station_history(client, startTime, endTime, code)
    else:
        print('\n站点列表未返回 stationCode，跳过单站实时/历史接口。\n')

    # 降水页: 区域降水统计 /api/v1/upns/statistics/regional
    test_get_regional_statistics(client)

    # 降水页: 过去1小时内降水量最大前五地区 /api/v1/upns/last1hour_rain_top5
    test_get_last1hour_rain_top5(client, minLng, maxLng, minLat, maxLat)

    # 降水页: 当前大气可降水量最大前五地区 /api/v1/upns/last1hour_pwv_top5
    test_get_last1hour_pwv_top5(client, minLng, maxLng, minLat, maxLat)
