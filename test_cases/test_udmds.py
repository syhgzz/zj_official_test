# -*- coding: utf-8 -*-
"""
形变安全监测模块API测试
"""
import sys
import os
from datetime import datetime

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
    number = '3.2.1'
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
    response = client.request('GET', '/api/v1/udmds/overview', params=params)
    print_response(
        '获取形变安全模块概览',
        'GET',
        '/api/v1/udmds/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_overview', response, '/api/v1/udmds/overview', params, config.response_dir, number=number, title=title)
    return response


def test_get_projects(client: APIClient):
    """测试获取监测工程列表"""
    number = '3.2.2'
    title = '工程列表'
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
    response = client.request('GET', '/api/v1/udmds/projects', params=params)
    print_response(
        '获取监测工程列表',
        'GET',
        '/api/v1/udmds/projects',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_projects', response, '/api/v1/udmds/projects', params, config.response_dir, number=number, title=title)
    return response


def test_get_points(client: APIClient):
    """测试获取监测点列表"""
    number = '3.2.3'
    title = '监测点列表'
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
    response = client.request('GET', '/api/v1/udmds/points', params=params)
    print_response(
        '获取监测点列表',
        'GET',
        '/api/v1/udmds/points',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_points', response, '/api/v1/udmds/points', params, config.response_dir, number=number, title=title)
    return response


def test_get_point_realtime(client: APIClient, code: str = "PD001"):
    """测试获取监测点实时数据"""
    number = '3.2.4'
    title = '单点实时数据'
    code = 'JCD03'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {

    }
    response = client.request('GET', f'/api/v1/udmds/points/{code}/realtime', params=params)
    print_response(
        '获取监测点实时数据',
        'GET',
        f'/api/v1/udmds/points/{code}/realtime',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_point_realtime', response, f'/api/v1/udmds/points/{code}/realtime', params, config.response_dir, number=number, title=title)
    return response

# displacement: 位移计
# accelerometer: 加速度计
# inclinometer: 倾角计
# fissures: 裂缝计
def test_get_point_history(client: APIClient, code: str = "PD001"):
    """测试获取监测点历史数据"""
    number = '3.2.5'
    title = '单点历史趋势'
    code = 'JCD03'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
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
    response = client.request('GET', f'/api/v1/udmds/points/{code}/history', params=params)
    print_response(
        '获取监测点历史数据',
        'GET',
        f'/api/v1/udmds/points/{code}/history',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_point_history', response, f'/api/v1/udmds/points/{code}/history', params, config.response_dir, number=number, title=title)
    return response


def test_get_project_statistics(client: APIClient):
    """测试获取工程统计"""
    number = '3.2.6'
    title = '工程统计'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'interval': '1d',
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    response = client.request('GET', '/api/v1/udmds/statistics/project', params=params)
    print_response(
        '获取工程统计',
        'GET',
        '/api/v1/udmds/statistics/project',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_project_statistics', response, '/api/v1/udmds/statistics/project', params, config.response_dir, number=number, title=title)
    return response


def test_get_alerts_summary(client: APIClient):
    """测试获取形变告警汇总"""
    number = '3.2.7'
    title = '告警汇总'
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

    response = client.request('GET', '/api/v1/udmds/alerts/summary', params=params)
    print_response(
        '获取形变告警汇总',
        'GET',
        '/api/v1/udmds/alerts/summary',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('udmds_alerts_summary', response, '/api/v1/udmds/alerts/summary', params, config.response_dir, number=number, title=title)
    return response


def test_get_risk(client: APIClient):
    """测试获取风险评估"""
    number = '3.2.8'
    title = '风险评估'
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
    response = client.request('GET', '/api/v1/udmds/risk', params=params)
    print_response('获取风险评估', 'GET', '/api/v1/udmds/risk', response, config.verbose, number=number, title=title)
    if config.save_response and response:
        save_response_to_file('udmds_risk', response, '/api/v1/udmds/risk', params, config.response_dir, number=number, title=title)
    return response


def run_all_tests():
    """运行形变安全监测模块的所有测试, 用到的接口 1 2 3 4 5 7"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    test_get_overview(client) # 3.2.1
    test_get_projects(client) # 3.2.2
    test_get_points(client) # 3.2.3
    test_get_point_realtime(client) # 3.2.4
    test_get_point_history(client) # 3.2.5
    # test_get_project_statistics(client)
    test_get_alerts_summary(client) # 3.2.7
    # test_get_risk(client)


if __name__ == '__main__':
    run_all_tests()
