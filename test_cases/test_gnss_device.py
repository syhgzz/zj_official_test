# -*- coding: utf-8 -*-
"""
卫星模块
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


def test_get_overview(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    卫星模块: 测试获取模块概览
    GET /api/v1/gnss-device/overview
    """
    number = '3.6.1'
    title = '卫星模块: 模块概览'
    path = '/api/v1/gnss-device/overview'
    params = {
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
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

    if config.save_response and response:
        save_response_to_file('gnss_device_overview', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response

# 站点编码列表
station_codes = []

def test_get_stations(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num: int = 1, page_size: int = 20):
    """
    卫星模块: 测试获取站点列表
    GET /api/v1/gnss-device/stations
    """
    number = '3.6.2'
    title = '卫星模块: 站点列表及状态'
    path = '/api/v1/gnss-device/stations'
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
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



    if config.save_response and response:
        save_response_to_file('gnss_device_stations', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    # station_codes = []  # 定义一个空列表来存储站点编码
    global station_codes  # 声明使用全局变量
    # 提取站点编码列表 从response的json格式中, data.stations是一个列表, 当中的stationCode字段就是站点编码
    if response and 'data' in response and 'stations' in response['data']:
        stations = response['data']['stations']
        station_codes = [station['stationCode'] for station in stations if 'stationCode']
    
    return response


def test_get_station_realtime(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, code: str = "BJ001"):
    """
    卫星模块: 测试获取站点实时数据
    GET /api/v1/gnss-device/stations/{code}/realtime
    """
    number = '3.6.3'
    title = '卫星模块: 单站实时数据'
    path = f'/api/v1/gnss-device/stations/{code}/realtime'
    params = {
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }

    for code in station_codes:
    # code = 'CQQX0038'
        start_dt = datetime.now()
        response = client.request('GET', path, params=params)
        end_dt = datetime.now()
        elapsed = (end_dt - start_dt).total_seconds()
        
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
        if config.save_response and response:
            save_response_to_file(
                f'gnss_device_stations_{code}_realtime',
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
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2026, 5, 5, 0, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2026, 6, 5, 23, 59, 59).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 卫星模块: 模块概览 /api/v1/gnss-device/overview
    test_get_overview(client, startTime, endTime, minLng, maxLng, minLat, maxLat)

    # 卫星模块: 站点列表及状态 /api/v1/gnss-device/stations
    test_get_stations(client, startTime, endTime, minLng, maxLng, minLat, maxLat)

    # 卫星模块: 单站实时数据 /api/v1/gnss-device/stations/{code}/realtime
    test_get_station_realtime(client, startTime, endTime, minLng, maxLng, minLat, maxLat)
