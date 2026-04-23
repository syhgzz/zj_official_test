# -*- coding: utf-8 -*-
"""
短临降水预警模块API测试
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config
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


def test_get_overview(client: APIClient):
    """测试获取模块概览"""
    number = '3.1.1'
    title = '模块概览'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/overview', params=params)
    print_response(
        '获取短临降水模块概览',
        'GET',
        '/api/v1/upns/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_overview', response, '/api/v1/upns/overview', params, config.response_dir)
    return response


def test_get_stations(client: APIClient):
    """测试获取监测站点列表"""
    number = '3.1.2'
    title = '站点列表及状态'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'pageNum': 1,
        'pageSize': 20,
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/stations', params=params)
    print_response(
        '获取监测站点列表',
        'GET',
        '/api/v1/upns/stations',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_stations', response, '/api/v1/upns/stations', params, config.response_dir)
    return response


def test_get_station_realtime(client: APIClient, code: str = "ST001"):
    """测试获取站点实时数据"""
    number = '3.1.3'
    title = '单站实时数据'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', f'/api/v1/upns/stations/{code}/realtime', params=params)
    print_response(
        '获取站点实时数据',
        'GET',
        f'/api/v1/upns/stations/{code}/realtime',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_station_realtime', response, f'/api/v1/upns/stations/{code}/realtime', params, config.response_dir)
    return response


def test_get_station_history(client: APIClient, code: str = "ST001"):
    """测试获取站点历史数据"""
    number = '3.1.4'
    title = '单站历史趋势'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'interval': '1h',
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', f'/api/v1/upns/stations/{code}/history', params=params)
    print_response(
        '获取站点历史数据',
        'GET',
        f'/api/v1/upns/stations/{code}/history',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_station_history', response, f'/api/v1/upns/stations/{code}/history', params, config.response_dir)
    return response


def test_get_regional_statistics(client: APIClient):
    """测试获取区域降水统计"""
    number = '3.1.5'
    title = '区域统计'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/statistics/regional', params=params)
    print_response(
        '获取区域降水统计',
        'GET',
        '/api/v1/upns/statistics/regional',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_regional_statistics', response, '/api/v1/upns/statistics/regional', params, config.response_dir)
    return response


def test_get_warnings_summary(client: APIClient):
    """测试获取降水预警汇总"""
    number = '3.1.6'
    title = '预警汇总'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/warnings/summary', params=params)
    print_response(
        '获取降水预警汇总',
        'GET',
        '/api/v1/upns/warnings/summary',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_warnings_summary', response, '/api/v1/upns/warnings/summary', params, config.response_dir)
    return response


def test_get_rain_statistics(client: APIClient):
    """测试获取降雨量统计"""
    number = '3.1.7'
    title = '降雨量实时统计'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/statistics/rain/now', params=params)
    print_response(
        '获取降雨量统计',
        'GET',
        '/api/v1/upns/statistics/rain/now',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_rain_statistics', response, '/api/v1/upns/statistics/rain/now', params, config.response_dir)
    return response


def test_get_pwv_statistics(client: APIClient):
    """测试获取大气可降水量统计"""
    number = '3.1.8'
    title = '大气可降水量实时统计'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/statistics/pwv/now', params=params)
    print_response(
        '获取大气可降水量统计',
        'GET',
        '/api/v1/upns/statistics/pwv/now',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upns_pwv_statistics', response, '/api/v1/upns/statistics/pwv/now', params, config.response_dir)
    return response


def test_get_risk(client: APIClient):
    """测试获取风险评估"""
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/upns/risk', params=params)
    print_response('获取风险评估', 'GET', '/api/v1/upns/risk', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_risk', response, '/api/v1/upns/risk', params, config.response_dir)
    return response


def run_all_tests():
    """运行短临降水预警模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    test_get_overview(client)
    test_get_stations(client)
    test_get_station_realtime(client)
    test_get_station_history(client)
    test_get_regional_statistics(client)
    test_get_warnings_summary(client)
    test_get_rain_statistics(client)
    test_get_pwv_statistics(client)
    test_get_risk(client)


if __name__ == '__main__':
    run_all_tests()
