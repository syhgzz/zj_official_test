# -*- coding: utf-8 -*-
"""
GNSS干扰监测模块API测试
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
    number = '3.3.1'
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
    response = client.request('GET', '/api/v1/ugss/overview', params=params)
    print_response(
        '获取GNSS干扰模块概览',
        'GET',
        '/api/v1/ugss/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_overview', response, config.response_dir)
    return response


def test_get_stations(client: APIClient):
    """测试获取基准站列表"""
    number = '3.3.2'
    title = '基站列表'
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
    response = client.request('GET', '/api/v1/ugss/stations', params=params)
    print_response(
        '获取基准站列表',
        'GET',
        '/api/v1/ugss/stations',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_stations', response, config.response_dir)
    return response


def test_get_station_realtime(client: APIClient, code: str = "GS001"):
    """测试获取基站实时数据"""
    number = '3.3.3'
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
    response = client.request('GET', f'/api/v1/ugss/stations/{code}/realtime', params=params)
    print_response(
        '获取基站实时数据',
        'GET',
        f'/api/v1/ugss/stations/{code}/realtime',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_station_realtime', response, config.response_dir)
    return response


def test_get_events(client: APIClient):
    """测试获取干扰事件列表"""
    number = '3.3.4'
    title = '干扰事件列表'
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
    response = client.request('GET', '/api/v1/ugss/events', params=params)
    print_response(
        '获取干扰事件列表',
        'GET',
        '/api/v1/ugss/events',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_events', response, config.response_dir)
    return response


def test_get_frequency_statistics(client: APIClient):
    """测试获取频率干扰统计"""
    number = '3.3.5'
    title = '频率统计'
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
    response = client.request('GET', '/api/v1/ugss/statistics/frequency', params=params)
    print_response(
        '获取频率干扰统计',
        'GET',
        '/api/v1/ugss/statistics/frequency',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_frequency_statistics', response, config.response_dir)
    return response


def test_get_warnings_summary(client: APIClient):
    """测试获取预警汇总统计"""
    number = '3.3.6'
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
    response = client.request('GET', '/api/v1/ugss/warnings/summary', params=params)
    print_response(
        '获取预警汇总统计',
        'GET',
        '/api/v1/ugss/warnings/summary',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('ugss_warnings_summary', response, config.response_dir)
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
    response = client.request('GET', '/api/v1/ugss/risk', params=params)
    print_response('获取风险评估', 'GET', '/api/v1/ugss/risk', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('ugss_risk', response, config.response_dir)
    return response


def run_all_tests():
    """运行GNSS干扰监测模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    test_get_overview(client)
    test_get_stations(client)
    test_get_station_realtime(client)
    test_get_events(client)
    test_get_frequency_statistics(client)
    test_get_warnings_summary(client)
    test_get_risk(client)


if __name__ == '__main__':
    run_all_tests()
