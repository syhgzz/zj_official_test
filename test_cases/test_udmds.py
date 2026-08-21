# -*- coding: utf-8 -*-
"""
形变页
"""
import sys
import os
from datetime import datetime
from xmlrpc import client

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config
try:
    from test_cases.common import *
except ImportError:
    from common import *


def test_get_overview(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取模块概览"""
    number = '3.2.1'
    title = '形变页: 模块概览'
    path = '/api/v1/udmds/overview'
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
        save_response_to_file('udmds_overview', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_projects(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取监测工程列表"""
    number = '3.2.2'
    title = '形变页: 工程列表'
    path = '/api/v1/udmds/projects'
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
        save_response_to_file('udmds_projects', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_points(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取监测点列表"""
    number = '3.2.3'
    title = '形变页: 监测点列表'
    path = '/api/v1/udmds/points'
    params = {
        'startTime': startTime,
        'endTime': endTime,
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
        save_response_to_file('udmds_points', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    pointcode_list = []
    if response and response.get('data', {}).get('points'):
        pointcode_list = [p['pointCode'] for p in response['data']['points']]
    return response, pointcode_list


def test_get_point_realtime(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, code: str = "PD001"):
    """形变页: 测试获取监测点实时数据"""
    number = '3.2.4'
    title = '形变页: 单点实时数据'
    path = f'/api/v1/udmds/points/{code}/realtime'
    params = {

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
        save_response_to_file('udmds_point_realtime', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response

# displacement: 位移计
# accelerometer: 加速度计
# inclinometer: 倾角计
# fissures: 裂缝计
def test_get_point_history(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, code: str = "PD001"):
    """形变页: 测试获取监测点历史数据"""
    number = '3.2.5'
    title = '形变页: 单点历史趋势'
    path = f'/api/v1/udmds/points/{code}/history'
    params = {
        # 'deviceType': 'accelerometer',
        'interval': '1h',
        'startTime': startTime,
        'endTime': endTime,
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
        save_response_to_file('udmds_point_history', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_project_statistics(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取工程统计"""
    number = '3.2.6'
    title = '形变页: 工程统计'
    path = '/api/v1/udmds/statistics/project'
    params = {
        'interval': '1d',
        'startTime': startTime,
        'endTime': endTime,
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
        save_response_to_file('udmds_project_statistics', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_alerts_summary(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取形变告警汇总"""
    number = '3.2.7'
    title = '形变页: 告警汇总'
    path = '/api/v1/udmds/alerts/summary'
    params = {
        'startTime': startTime,
        'endTime': endTime,
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
        save_response_to_file('udmds_alerts_summary', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_risk(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """形变页: 测试获取风险评估"""
    number = '3.2.8'
    title = '形变页: 风险评估'
    path = '/api/v1/udmds/risk'
    params = {
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    print_response(title, 'GET', path, response, config.verbose, number=number, title=title, elapsed_seconds=elapsed)
    if config.save_response and response:
        save_response_to_file('udmds_risk', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


if __name__ == '__main__':
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2026, 5, 5, 0, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2026, 6, 5, 23, 59, 59).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 形变页: 告警汇总 /api/v1/udmds/alerts/summary
    test_get_alerts_summary(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.2.7
    # 形变页: 模块概览 /api/v1/udmds/overview
    test_get_overview(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.2.1
    # 形变页: 工程列表 /api/v1/udmds/projects
    test_get_projects(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.2.2
    # 形变页: 监测点列表 /api/v1/udmds/points
    _, pointcode_list = test_get_points(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.2.3

    print(f"\n共获取到 {len(pointcode_list)} 个监测点, 开始循环测试实时数据和历史趋势...\n")
    for code in pointcode_list:
        print(f"正在测试监测点: {code}")
        # 形变页: 单点实时数据 /api/v1/udmds/points/{code}/realtime
        test_get_point_realtime(client, startTime, endTime, minLng, maxLng, minLat, maxLat, code=code) # 3.2.4
        # 形变页: 单点历史趋势 /api/v1/udmds/points/{code}/history
        test_get_point_history(client, startTime, endTime, minLng, maxLng, minLat, maxLat, code=code) # 3.2.5
    # 形变页: 工程统计 /api/v1/udmds/statistics/project
    # test_get_project_statistics(client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    
    # 形变页: 风险评估 /api/v1/udmds/risk
    # test_get_risk(client, startTime, endTime, minLng, maxLng, minLat, maxLat)
