# -*- coding: utf-8 -*-
"""
短临降水预警模块API测试
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from lib.response_printer import print_response, save_response_to_file
from config.config import config


def test_get_overview(client: APIClient):
    """测试获取模块概览"""
    response = client.request('GET', '/api/v1/upns/overview')
    print_response('获取短临降水模块概览', 'GET', '/api/v1/upns/overview', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_overview', response, config.response_dir)
    return response


def test_get_stations(client: APIClient):
    """测试获取监测站点列表"""
    params = {'pageNum': 1, 'pageSize': 20}
    response = client.request('GET', '/api/v1/upns/stations', params=params)
    print_response('获取监测站点列表', 'GET', '/api/v1/upns/stations', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_stations', response, config.response_dir)
    return response


def test_get_station_realtime(client: APIClient, code: str = "ST001"):
    """测试获取站点实时数据"""
    response = client.request('GET', f'/api/v1/upns/stations/{code}/realtime')
    print_response('获取站点实时数据', 'GET', f'/api/v1/upns/stations/{code}/realtime', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_station_realtime', response, config.response_dir)
    return response


def test_get_station_history(client: APIClient, code: str = "ST001"):
    """测试获取站点历史数据"""
    params = {'interval': '1h'}
    response = client.request('GET', f'/api/v1/upns/stations/{code}/history', params=params)
    print_response('获取站点历史数据', 'GET', f'/api/v1/upns/stations/{code}/history', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_station_history', response, config.response_dir)
    return response


def test_get_regional_statistics(client: APIClient):
    """测试获取区域降水统计"""
    response = client.request('GET', '/api/v1/upns/statistics/regional')
    print_response('获取区域降水统计', 'GET', '/api/v1/upns/statistics/regional', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_regional_statistics', response, config.response_dir)
    return response


def test_get_warnings_summary(client: APIClient):
    """测试获取降水预警汇总"""
    response = client.request('GET', '/api/v1/upns/warnings/summary')
    print_response('获取降水预警汇总', 'GET', '/api/v1/upns/warnings/summary', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_warnings_summary', response, config.response_dir)
    return response


def test_get_rain_statistics(client: APIClient):
    """测试获取降雨量统计"""
    response = client.request('GET', '/api/v1/upns/statistics/rain/now')
    print_response('获取降雨量统计', 'GET', '/api/v1/upns/statistics/rain/now', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_rain_statistics', response, config.response_dir)
    return response


def test_get_pwv_statistics(client: APIClient):
    """测试获取大气可降水量统计"""
    response = client.request('GET', '/api/v1/upns/statistics/pwv/now')
    print_response('获取大气可降水量统计', 'GET', '/api/v1/upns/statistics/pwv/now', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_pwv_statistics', response, config.response_dir)
    return response


def test_get_risk(client: APIClient):
    """测试获取风险评估"""
    response = client.request('GET', '/api/v1/upns/risk')
    print_response('获取风险评估', 'GET', '/api/v1/upns/risk', response, config.verbose)
    if config.save_response and response:
        save_response_to_file('upns_risk', response, config.response_dir)
    return response


def run_all_tests():
    """运行短临降水预警模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    print("\n" + "#" * 60)
    print("#" + " " * 16 + "短临降水预警模块测试" + " " * 16 + "#")
    print("#" * 60 + "\n")

    test_get_overview(client)
    test_get_stations(client)
    test_get_station_realtime(client)
    test_get_station_history(client)
    test_get_regional_statistics(client)
    test_get_warnings_summary(client)
    test_get_rain_statistics(client)
    test_get_pwv_statistics(client)
    test_get_risk(client)

    print("\n短临降水预警模块测试完成!\n")


if __name__ == '__main__':
    run_all_tests()
