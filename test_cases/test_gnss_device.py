# -*- coding: utf-8 -*-
"""
北斗设备状态模块API测试
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
    """
    测试获取模块概览
    GET /api/v1/gnss-device/overview
    """
    number = '3.6.1'
    title = '模块概览'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/gnss-device/overview', params=params)
    print_response(
        '获取北斗设备模块概览',
        'GET',
        '/api/v1/gnss-device/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('gnss_device_overview', response, '/api/v1/gnss-device/overview', params, config.response_dir, number=number, title=title)

    return response

# 站点编码列表
station_codes = []

def test_get_stations(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    测试获取站点列表
    GET /api/v1/gnss-device/stations
    """
    number = '3.6.2'
    title = '站点列表及状态'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/gnss-device/stations', params=params)
    print_response(
        '获取站点列表',
        'GET',
        '/api/v1/gnss-device/stations',
        response,
        config.verbose,
        number=number,
        title=title,
    )



    if config.save_response and response:
        save_response_to_file('gnss_device_stations', response, '/api/v1/gnss-device/stations', params, config.response_dir, number=number, title=title)

    # station_codes = []  # 定义一个空列表来存储站点编码
    global station_codes  # 声明使用全局变量
    # 提取站点编码列表 从response的json格式中, data.stations是一个列表, 当中的stationCode字段就是站点编码
    if response and 'data' in response and 'stations' in response['data']:
        stations = response['data']['stations']
        station_codes = [station['stationCode'] for station in stations if 'stationCode']
    
    return response


def test_get_station_realtime(client: APIClient, code: str = "BJ001"):
    """
    测试获取站点实时数据
    GET /api/v1/gnss-device/stations/{code}/realtime
    """
    number = '3.6.3'
    title = '单站实时数据'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }

    for code in station_codes:
    # code = 'CQQX0038'
        response = client.request('GET', f'/api/v1/gnss-device/stations/{code}/realtime', params=params)
        print_response(
            '获取站点实时数据',
            'GET',
            f'/api/v1/gnss-device/stations/{code}/realtime',
            response,
            config.verbose,
            number=number,
            title=title,
        )
        if config.save_response and response:
            save_response_to_file(
                f'gnss_device_stations_{code}_realtime',
                response,
                f'/api/v1/gnss-device/stations/{code}/realtime',
                params,
                config.response_dir,
                number=number,
                title=title,
            )

    return response


def run_all_tests():
    """运行北斗设备状态模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试1: 获取模块概览
    test_get_overview(client)

    # 测试2: 获取站点列表
    test_get_stations(client)

    # 测试3: 获取站点实时数据
    test_get_station_realtime(client)


if __name__ == '__main__':
    run_all_tests()
