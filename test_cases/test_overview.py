# -*- coding: utf-8 -*-
"""
系统概览模块API测试
"""
import sys
import os

# 添加父目录到Python路径
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


def test_get_realtime(client: APIClient):
    """
    测试获取系统实时概览
    GET /api/v1/overview/realtime
    """
    number = '2.1.1'
    title = '获取系统实时概览'
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
    response = client.request('GET', '/api/v1/overview/realtime', params=params)
    print_response(
        '获取系统实时概览',
        'GET',
        '/api/v1/overview/realtime',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('overview_realtime', response, '/api/v1/overview/realtime', params, config.response_dir)

    return response


def test_get_summary(client: APIClient):
    """
    测试获取系统综合统计
    GET /api/v1/overview/summary
    """
    number = '2.2.1'
    title = '获取系统综合统计'
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
    response = client.request('GET', '/api/v1/overview/summary', params=params)
    print_response(
        '获取系统综合统计',
        'GET',
        '/api/v1/overview/summary',
        response,
        config.verbose,
        number=number,
        title=title,
    )

    if config.save_response and response:
        save_response_to_file('overview_summary', response, '/api/v1/overview/summary', params, config.response_dir)

    return response


def run_all_tests():
    """运行系统概览模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试1: 获取系统实时概览
    test_get_realtime(client)

    # 测试2: 获取系统综合统计
    test_get_summary(client)


if __name__ == '__main__':
    run_all_tests()
