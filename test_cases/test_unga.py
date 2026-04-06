# -*- coding: utf-8 -*-
"""
走航甲烷检测模块API测试
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config


def test_get_overview(client: APIClient):
    """
    测试获取模块概览
    GET /api/v1/unga/overview
    """
    number = '3.5.1'
    title = '模块概览'
    response = client.request('GET', '/api/v1/unga/overview')
    print_response(
        '获取走航甲烷模块概览',
        'GET',
        '/api/v1/unga/overview',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('unga_overview', response, config.response_dir)

    return response


def test_get_tasks(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    测试获取检测任务列表
    GET /api/v1/unga/tasks
    """
    number = '3.5.2'
    title = '检测任务列表'
    params = {'pageNum': page_num, 'pageSize': page_size}
    response = client.request('GET', '/api/v1/unga/tasks', params=params)
    print_response(
        '获取检测任务列表',
        'GET',
        '/api/v1/unga/tasks',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('unga_tasks', response, config.response_dir)

    return response


def test_get_task_trajectory(client: APIClient, task_id: int = 1):
    """
    测试获取任务轨迹数据
    GET /api/v1/unga/tasks/{id}/trajectory
    """
    number = '3.5.3'
    title = '走航轨迹查询'
    response = client.request('GET', f'/api/v1/unga/tasks/{task_id}/trajectory')
    print_response(
        '获取任务轨迹数据',
        'GET',
        f'/api/v1/unga/tasks/{task_id}/trajectory',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('unga_task_trajectory', response, config.response_dir)

    return response


def test_get_leaks(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    测试获取泄露点列表
    GET /api/v1/unga/leaks
    """
    number = '3.5.4'
    title = '泄露点管理'
    params = {'pageNum': page_num, 'pageSize': page_size}
    response = client.request('GET', '/api/v1/unga/leaks', params=params)
    print_response(
        '获取泄露点列表',
        'GET',
        '/api/v1/unga/leaks',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('unga_leaks', response, config.response_dir)

    return response


def test_get_statistics(client: APIClient):
    """
    测试获取走航统计数据
    GET /api/v1/unga/statistics
    """
    number = '3.5.5'
    title = '统计分析'
    response = client.request('GET', '/api/v1/unga/statistics')
    print_response(
        '获取走航统计数据',
        'GET',
        '/api/v1/unga/statistics',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('unga_statistics', response, config.response_dir)

    return response


def run_all_tests():
    """运行走航甲烷检测模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试1: 获取模块概览
    test_get_overview(client)

    # 测试2: 获取检测任务列表
    test_get_tasks(client)

    # 测试3: 获取任务轨迹数据
    test_get_task_trajectory(client)

    # 测试4: 获取泄露点列表
    test_get_leaks(client)

    # 测试5: 获取走航统计数据
    test_get_statistics(client)


if __name__ == '__main__':
    run_all_tests()
