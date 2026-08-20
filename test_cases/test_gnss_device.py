# -*- coding: utf-8 -*-
"""
卫星模块
"""
import sys
import os
from contextlib import contextmanager

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config
try:
    from test_cases.common import *
except ImportError:
    from common import *

# 模块私有配置，运行卫星模块测试时可临时覆盖，调用结束后恢复
startTime_file = startTime_global
endTime_file = endTime_global
minLng_file = minLng_global
maxLng_file = maxLng_global
minLat_file = minLat_global
maxLat_file = maxLat_global

_NATIONWIDE_BBOX = loc_list['全国']
_NATIONWIDE_START_TIME = int(datetime(2026, 5, 5, 0, 0, 0).timestamp()) * 1000
_NATIONWIDE_END_TIME = int(datetime(2026, 8, 19, 23, 59, 59).timestamp()) * 1000


@contextmanager
def _nationwide_config():
    """临时使用全国范围与时间，退出后恢复原来的私有配置。"""
    global startTime_file, endTime_file, minLng_file, maxLng_file, minLat_file, maxLat_file
    original = (
        startTime_file,
        endTime_file,
        minLng_file,
        maxLng_file,
        minLat_file,
        maxLat_file,
    )
    startTime_file = _NATIONWIDE_START_TIME
    endTime_file = _NATIONWIDE_END_TIME
    minLng_file, maxLng_file, minLat_file, maxLat_file = _NATIONWIDE_BBOX
    try:
        yield
    finally:
        (
            startTime_file,
            endTime_file,
            minLng_file,
            maxLng_file,
            minLat_file,
            maxLat_file,
        ) = original


def test_get_overview(client: APIClient):
    """
    测试获取模块概览
    GET /api/v1/gnss-device/overview
    """
    number = '卫星模块'
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
    start_dt = datetime.now()
    response = client.request('GET', '/api/v1/gnss-device/overview', params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    print_response(
        '获取北斗设备模块概览',
        'GET',
        '/api/v1/gnss-device/overview',
        response,
        config.verbose,
        number=number,
        title=title,
        elapsed_seconds=elapsed,
    )

    if config.save_response and response:
        save_response_to_file('gnss_device_overview', response, '/api/v1/gnss-device/overview', params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response

# 站点编码列表
station_codes = []

def test_get_stations(
    client: APIClient,
    page_num: int = 1,
    page_size: int = 100,
):
    """
    测试获取站点列表
    GET /api/v1/gnss-device/stations
    """
    number = '卫星模块'
    title = '站点列表及状态'
    path = '/api/v1/gnss-device/stations'
    if page_size <= 0:
        raise ValueError('page_size 必须大于 0')
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    all_stations = []
    first_response = None
    reported_total = None
    failed_pages = []
    first_start_dt = None
    last_end_dt = None
    all_records_start_dt = datetime.now()

    def print_all_records_elapsed():
        all_records_end_dt = datetime.now()
        elapsed_seconds = (all_records_end_dt - all_records_start_dt).total_seconds()
        print(f'获取所有记录站点列表总时间: {elapsed_seconds:.3f} 秒')

    def fetch_page(current_page):
        """请求一页站点列表，超时或空响应时自动重试一次。"""
        params = {
            'pageNum': current_page,
            'pageSize': page_size,
            'minLng': minLng,
            'maxLng': maxLng,
            'minLat': minLat,
            'maxLat': maxLat,
        }
        start_dt = datetime.now()
        response = client.request('GET', path, params=params)
        if not response or response.get('timeout'):
            print(f'第 {current_page} 页请求失败或超时，重试 1 次')
            response = client.request('GET', path, params=params)
        end_dt = datetime.now()
        elapsed = (end_dt - start_dt).total_seconds()
        page_title = f'{title}（第{current_page}页）'

        print_response(
            page_title,
            'GET',
            path,
            response,
            config.verbose,
            number=number,
            title=page_title,
            elapsed_seconds=elapsed,
        )

        if config.save_response and response:
            save_response_to_file(
                f'gnss_device_stations_page_{current_page}',
                response,
                path,
                params,
                config.response_dir,
                number=number,
                title=page_title,
                start_time=start_dt,
                end_time=end_dt,
            )

        return response, start_dt, end_dt

    # 先请求第一页，用接口返回的 total 计算总页数，再拉取剩余页面
    first_response, first_start_dt, first_end_dt = fetch_page(page_num)
    last_end_dt = first_end_dt

    if not first_response or first_response.get('code') != 200:
        failed_pages.append(page_num)
        print_all_records_elapsed()
        raise RuntimeError(f'站点列表请求失败页码: {failed_pages}')

    data = first_response.get('data') or {}
    try:
        reported_total = int(data.get('total'))
    except (TypeError, ValueError):
        print_all_records_elapsed()
        raise RuntimeError(f'接口返回的站点总数无效: {data.get("total")}')
    if reported_total < 0:
        print_all_records_elapsed()
        raise RuntimeError(f'接口返回的站点总数不能为负数: {reported_total}')

    total_page_count = max(1, (reported_total + page_size - 1) // page_size)
    last_page = max(page_num, total_page_count)
    all_stations.extend(data.get('stations') or [])

    for current_page in range(page_num + 1, last_page + 1):
        response, _, end_dt = fetch_page(current_page)
        last_end_dt = end_dt
        if not response or response.get('code') != 200:
            failed_pages.append(current_page)
            continue
        all_stations.extend((response.get('data') or {}).get('stations') or [])

    if failed_pages:
        print_all_records_elapsed()
        raise RuntimeError(f'站点列表请求失败页码: {failed_pages}')

    page_count = last_page - page_num + 1

    if reported_total is not None and len(all_stations) < reported_total:
        print_all_records_elapsed()
        raise RuntimeError(
            f'站点抓取不完整: 接口共 {reported_total} 个，实际获取 {len(all_stations)} 个'
        )

    all_station_codes = [
        station['stationCode']
        for station in all_stations
        if station.get('stationCode')
    ]
    unique_station_codes = list(dict.fromkeys(all_station_codes))
    duplicate_station_code_count = len(all_station_codes) - len(unique_station_codes)

    combined_data = {
        **((first_response or {}).get('data') or {}),
        'total': reported_total if reported_total is not None else len(all_stations),
        'pageNum': page_num,
        'pageSize': len(all_stations),
        'stations': all_stations,
        'fetchedPageCount': page_count,
        'uniqueStationCount': len(unique_station_codes),
        'duplicateStationCodeCount': duplicate_station_code_count,
    }
    combined_response = {
        **(first_response or {'code': 200, 'msg': 'success'}),
        'data': combined_data,
    }
    global station_codes
    station_codes = unique_station_codes

    if config.save_response:
        merged_params = {
            'pageNum': f'{page_num}-{page_num + page_count - 1}',
            'pageSize': page_size,
            'minLng': minLng,
            'maxLng': maxLng,
            'minLat': minLat,
            'maxLat': maxLat,
        }
        save_response_to_file(
            'gnss_device_stations_all',
            combined_response,
            path,
            merged_params,
            config.response_dir,
            number=number,
            title=f'{title}（全部）',
            start_time=first_start_dt,
            end_time=last_end_dt,
        )

    print(f'站点列表抓取完成: 共请求 {page_count} 页，获取 {len(all_stations)} 条站点记录')
    if duplicate_station_code_count:
        print(
            '警告: 服务端分页结果存在重叠，'
            f'唯一站点编码 {len(unique_station_codes)} 个，重复记录 {duplicate_station_code_count} 条'
        )
    print_all_records_elapsed()
    return combined_response


def test_get_station_realtime(client: APIClient, code: str = "BJ001"):
    """
    测试获取站点实时数据
    GET /api/v1/gnss-device/stations/{code}/realtime
    """
    number = '卫星模块'
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
        start_dt = datetime.now()
        response = client.request('GET', f'/api/v1/gnss-device/stations/{code}/realtime', params=params)
        end_dt = datetime.now()
        elapsed = (end_dt - start_dt).total_seconds()
        
        print_response(
            '获取站点实时数据',
            'GET',
            f'/api/v1/gnss-device/stations/{code}/realtime',
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
                f'/api/v1/gnss-device/stations/{code}/realtime',
                params,
                config.response_dir,
                number=number,
                title=title,
                start_time=start_dt,
                end_time=end_dt,
            )

    return response


def run_all_tests():
    """运行北斗设备状态模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    with _nationwide_config():
        # 测试1: 获取模块概览
        test_get_overview(client)

        # 测试2: 获取站点列表
        test_get_stations(client)

        # # 卫星模块: 单站实时数据 /api/v1/gnss-device/stations/{code}/realtime
        # test_get_station_realtime(client)


if __name__ == '__main__':
    run_all_tests()
