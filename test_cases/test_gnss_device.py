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


startTime_file = startTime_global
endTime_file = endTime_global
minLng_file = minLng_global
maxLng_file = maxLng_global
minLat_file = minLat_global
maxLat_file = maxLat_global


def test_get_overview(client: APIClient):
    """
    卫星模块: 测试获取模块概览
    GET /api/v1/gnss-device/overview
    """
    number = '3.6.1'
    title = '卫星模块: 模块概览'
    path = '/api/v1/gnss-device/overview'
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

def test_get_stations(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    卫星模块: 测试获取站点列表
    GET /api/v1/gnss-device/stations
    """
    number = '3.6.2'
    title = '卫星模块: 站点列表及状态'
    path = '/api/v1/gnss-device/stations'
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

def test_get_nation_stations(client, page_size=100):
    """
    卫星模块: 测试获取站点列表
    GET /api/v1/gnss-device/stations
    """
    title = '卫星模块: 站点列表及状态'
    path = '/api/v1/gnss-device/stations'
    minLng, maxLng, minLat, maxLat = loc_list['全国']
    params = {
        'pageNum': 1,
        'pageSize': page_size,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    all_stations = []
    total_pages = 1
    successful_elapsed = 0.0
    page = 1
    while page <= total_pages:
        params['pageNum'] = page
        start_dt = datetime.now()
        response = client.request('GET', path, params=params)
        end_dt = datetime.now()
        elapsed = (end_dt - start_dt).total_seconds()
        if response and response.get('code') == 200:
            successful_elapsed += elapsed
            data = response.get('data') or {}
            if page == 1:
                total = int(data['total'])
                total_pages = max(1, (total + page_size - 1) // page_size)
            all_stations.extend(data.get('stations') or [])

        title_page = title + f'_第{page}页' + f"_pageSize={page_size}"
        print_response(
            title_page,
            'GET',
            path,
            response,
            config.verbose,
            number='',
            title=title_page,
            elapsed_seconds=elapsed,
        )
        if config.save_response and response and response.get('code') == 200:
            save_response_to_file(
                title_page,
                response,
                path,
                params,
                config.response_dir,
                number='',
                title=title_page,
                start_time=start_dt,
                end_time=end_dt,
            )


        page += 1



    print(f'抓取全国所有站点总时长: {successful_elapsed:.3f} 秒')

    return 

def test_get_station_realtime(client: APIClient, code: str = "BJ001"):
    """
    卫星模块: 测试获取站点实时数据
    GET /api/v1/gnss-device/stations/{code}/realtime
    """
    number = '3.6.3'
    title = '卫星模块: 单站实时数据'
    path = f'/api/v1/gnss-device/stations/{code}/realtime'
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


def run_all_tests():
    """运行卫星模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 卫星模块: 模块概览 /api/v1/gnss-device/overview
    test_get_overview(client)

    # 卫星模块: 站点列表及状态 /api/v1/gnss-device/stations
    # test_get_stations(client)

    # 卫星模块: 获取全国站点列表及状态 /api/v1/gnss-device/stations
    # test_get_nation_stations(client)

    # 卫星模块: 获取全国站点列表及状态 /api/v1/gnss-device/stations
    test_get_nation_stations(client, page_size=3500)

    # 卫星模块: 单站实时数据 /api/v1/gnss-device/stations/{code}/realtime
    # test_get_station_realtime(client)


if __name__ == '__main__':
    run_all_tests()
