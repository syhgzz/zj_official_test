# -*- coding: utf-8 -*-
"""
形变安全监测模块API测试
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config


def test_get_overview(client: APIClient):
    """测试获取模块概览"""
    number = '3.2.1'
    title = '模块概览'
    response = client.request('GET', '/api/v1/udmds/overview')
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
        save_response_to_file('udmds_overview', response, config.response_dir)
    return response


def test_get_projects(client: APIClient):
    """测试获取监测工程列表"""
    number = '3.2.2'
    title = '工程列表'
    params = {'pageNum': 1, 'pageSize': 20}
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
        save_response_to_file('udmds_projects', response, config.response_dir)
    return response


def test_get_points(client: APIClient):
    """测试获取监测点列表"""
    number = '3.2.3'
    title = '监测点列表'
    response = client.request('GET', '/api/v1/udmds/points')
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
        save_response_to_file('udmds_points', response, config.response_dir)
    return response


def test_get_point_realtime(client: APIClient, code: str = "PD001"):
    """测试获取监测点实时数据"""
    number = '3.2.4'
    title = '单点实时数据'
    response = client.request('GET', f'/api/v1/udmds/points/{code}/realtime')
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
        save_response_to_file('udmds_point_realtime', response, config.response_dir)
    return response


def test_get_point_history(client: APIClient, code: str = "PD001"):
    """测试获取监测点历史数据"""
    number = '3.2.5'
    title = '单点历史趋势'
    params = {'deviceType': 'displacement', 'interval': '1h'}
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
        save_response_to_file('udmds_point_history', response, config.response_dir)
    return response


def test_get_project_statistics(client: APIClient):
    """测试获取工程统计"""
    number = '3.2.6'
    title = '工程统计'
    params = {'interval': '1d'}
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
        save_response_to_file('udmds_project_statistics', response, config.response_dir)
    return response


def test_get_alerts_summary(client: APIClient):
    """测试获取形变告警汇总"""
    number = '3.2.7'
    title = '告警汇总'
    response = client.request('GET', '/api/v1/udmds/alerts/summary')
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
        save_response_to_file('udmds_alerts_summary', response, config.response_dir)
    return response


def test_get_risk(client: APIClient):
    """测试获取风险评估"""
    response = client.request('GET', '/api/v1/udmds/risk')
    print_response('获取风险评估', 'GET', '/api/v1/udmds/risk', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('udmds_risk', response, config.response_dir)
    return response


def run_all_tests():
    """运行形变安全监测模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    test_get_overview(client)
    test_get_projects(client)
    test_get_points(client)
    test_get_point_realtime(client)
    test_get_point_history(client)
    test_get_project_statistics(client)
    test_get_alerts_summary(client)
    test_get_risk(client)


if __name__ == '__main__':
    run_all_tests()
