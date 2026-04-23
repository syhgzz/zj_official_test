# -*- coding: utf-8 -*-
"""
沉降态势感知模块API测试
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config


def test_get_overview(client: APIClient):
    """测试获取模块概览"""
    number = '3.4.1'
    title = '模块概览'
    response = client.request('GET', '/api/v1/upss/overview')
    print_response(
        '获取沉降态势模块概览',
        'GET',
        '/api/v1/upss/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_overview', response, config.response_dir)
    return response


def test_get_periods(client: APIClient):
    """测试获取沉降期次列表"""
    number = '3.4.2'
    title = '沉降期列表'
    params = {'pageNum': 1, 'pageSize': 20}
    response = client.request('GET', '/api/v1/upss/periods', params=params)
    print_response(
        '获取沉降期次列表',
        'GET',
        '/api/v1/upss/periods',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_periods', response, config.response_dir)
    return response


def test_get_period_summary(client: APIClient, issue: str = "20221220"):
    """测试获取期次汇总统计"""
    number = '3.4.3'
    title = '期次汇总'
    issue = "20220424"
    response = client.request('GET', f'/api/v1/upss/periods/{issue}/summary')
    print_response(
        '获取期次汇总统计',
        'GET',
        f'/api/v1/upss/periods/{issue}/summary',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_period_summary', response, config.response_dir)
    return response


def test_get_point_history(client: APIClient, code: str = "PS001"):
    """测试获取单点沉降历史"""
    number = '3.4.4'
    title = '单点沉降历史'
    code = '1305'
    params = {
        'startIssue': '20180120',
        'endIssue': '20240101'
    }
    response = client.request('GET', f'/api/v1/upss/points/{code}/history', params=params)
    print_response(
        '获取单点沉降历史',
        'GET',
        f'/api/v1/upss/points/{code}/history',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_point_history', response, config.response_dir)
    return response


def test_get_regional_statistics(client: APIClient):
    """测试获取区域沉降统计"""
    number = '3.4.5'
    title = '沉降地图（热力图）'
    params = {'issue': '20220424', 'dimension': 'admin', 'pageNum': 1, 'pageSize': 1000}
    response = client.request('GET', '/api/v1/upss/statistics/regional', params=params)
    print_response(
        '获取区域沉降统计',
        'GET',
        '/api/v1/upss/statistics/regional',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_regional_statistics', response, config.response_dir)
    return response


def test_get_grid_rate(client: APIClient):
    """测试获取网格沉降速率"""
    number = '3.4.6'
    title = '沉降速率'
    params = {'issue': '20220424'}
    response = client.request('GET', '/api/v1/upss/statistics/gridRate', params=params)
    print_response(
        '获取网格沉降速率',
        'GET',
        '/api/v1/upss/statistics/gridRate',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_grid_rate', response, config.response_dir)
    return response


def test_get_grid_gradient(client: APIClient):
    """测试获取网格沉降梯度"""
    number = '3.4.7'
    title = '沉降速率梯度'
    params = {'issue': '20220424'}
    response = client.request('GET', '/api/v1/upss/statistics/gridGradient', params=params)
    print_response(
        '获取网格沉降梯度',
        'GET',
        '/api/v1/upss/statistics/gridGradient',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_grid_gradient', response, config.response_dir)
    return response


def test_get_warning_issue(client: APIClient):
    """测试获取沉降预警信息"""
    number = '3.4.8'
    title = '预警信息'
    endTime = 1738857421000  
    # 2025-2-6 21:34  
    startTime = 1738157653000
    # 2025-1-29 21:34

    #测试节点时间戳是在1738512000000  2025-2-3 0:0:0，lng106.5,lat29.7
    
    # endTime = int(time.time() * 1000)
    # startTime = endTime - 1000 * 24 * 60 * 60 * 1000
    # params = {}
    params = {'minLng': 106.263, 
              'maxLng':107.444, 
              'minLat': 29.232, 
              'maxLat':30.030, 
              'startTime':startTime, 
              'endTime':endTime}
    response = client.request('GET', '/api/v1/upss/visualization/warning/issue', params=params)
    print_response(
        '获取沉降预警信息',
        'GET',
        '/api/v1/upss/visualization/warning/issue',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_warning_issue', response, config.response_dir)
    return response


def test_get_statistics_issue(client: APIClient):
    """测试获取沉降态势统计"""
    number = '3.4.9'
    title = '沉降态势统计'
    params = {'issue': '20250203'}
    response = client.request('GET', '/api/v1/upss/visualization/statistics/issue', params=params)
    print_response(
        '获取沉降态势统计',
        'GET',
        '/api/v1/upss/visualization/statistics/issue',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_statistics_issue', response, config.response_dir)
    return response


def test_get_max_subsidence_timeseries(client: APIClient):
    """测试获取最大沉降点时序"""
    number = '3.4.10'
    title = '最大沉降点时序统计'
    response = client.request('GET', '/api/v1/upss/visualization/max-subsidence/timeseries')
    print_response(
        '获取最大沉降点时序',
        'GET',
        '/api/v1/upss/visualization/max-subsidence/timeseries',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_max_subsidence_timeseries', response, config.response_dir)
    return response


def test_get_top_gradient(client: APIClient):
    """测试获取Top5沉降梯度"""
    number = '3.4.11'
    title = '前五沉降梯度值位置统计'
    params = {'startIssue': '20220424', 'endIssue': '20220526'}
    response = client.request('GET', '/api/v1/upss/visualization/top-gradient', params=params)
    print_response(
        '获取Top5沉降梯度',
        'GET',
        '/api/v1/upss/visualization/top-gradient',
        response,
        config.verbose,
        number=number,
        title=title,
    )
    if config.save_response and response:
        save_response_to_file('upss_top_gradient', response, config.response_dir)
    return response


def test_get_risk(client: APIClient):
    """测试获取风险评估"""
    response = client.request('GET', '/api/v1/upss/risk')
    print_response('获取风险评估', 'GET', '/api/v1/upss/risk', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upss_risk', response, config.response_dir)
    return response


def run_all_tests():
    """运行沉降态势感知模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    test_get_overview(client)
    test_get_periods(client)
    test_get_period_summary(client)
    test_get_point_history(client)
    test_get_regional_statistics(client)
    test_get_grid_rate(client)
    test_get_grid_gradient(client)
    test_get_warning_issue(client)
    test_get_statistics_issue(client)
    test_get_max_subsidence_timeseries(client)
    test_get_top_gradient(client)
    test_get_risk(client)


if __name__ == '__main__':
    run_all_tests()
