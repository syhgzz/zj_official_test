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


def test_get_realtime(client: APIClient):
    """
    测试获取系统实时概览
    GET /api/v1/overview/realtime
    """
    response = client.request('GET', '/api/v1/overview/realtime')
    print_response('获取系统实时概览', 'GET', '/api/v1/overview/realtime', response, config.verbose)

    if config.save_response and response:
        save_response_to_file('overview_realtime', response, config.response_dir)

    return response


def test_get_summary(client: APIClient):
    """
    测试获取系统综合统计
    GET /api/v1/overview/summary
    """
    params = {}
    response = client.request('GET', '/api/v1/overview/summary', params=params)
    print_response('获取系统综合统计', 'GET', '/api/v1/overview/summary', response, config.verbose)

    if config.save_response and response:
        save_response_to_file('overview_summary', response, config.response_dir)

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
