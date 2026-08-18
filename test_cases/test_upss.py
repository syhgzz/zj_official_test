# -*- coding: utf-8 -*-
"""
沉降页
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


# startTime_file = startTime_global
# endTime_file = endTime_global
startTime_file = int(datetime(2025,1,1,0,0,0).timestamp()) * 1000    
endTime_file = int(datetime(2025,2,28,23,59,59).timestamp()) * 1000
minLng_file = minLng_global
maxLng_file = maxLng_global
minLat_file = minLat_global
maxLat_file = maxLat_global
point_set = set()
issue_list = []

def run_all_tests():
    """运行沉降页模块的所有测试"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 沉降页: 模块概览 /api/v1/upss/overview
    # test_get_overview(client) # 3.4.1
    # 沉降页: 沉降期列表 /api/v1/upss/periods
    test_get_periods(client) # 3.4.2
    # 沉降页: 期次汇总 /api/v1/upss/periods/{issue}/summary
    # test_get_period_summary(client) # 3.4.3
    # 沉降页: 沉降地图（热力图） /api/v1/upss/statistics/regional
    # for issue in issue_list:
    #     for pg in range(1, 100):
    #         test_get_regional_statistics(client, issue=issue, pageNum=pg) # 3.4.5
    # 沉降页: 沉降速率 /api/v1/upss/statistics/gridRate
    #     test_get_grid_rate(client, issue=issue) # 3.4.6
    # 沉降页: 沉降速率梯度 /api/v1/upss/statistics/gridGradient
    #     test_get_grid_gradient(client, issue=issue) # 3.4.7
    # 沉降页: 预警信息 /api/v1/upss/visualization/warning/issue
    test_get_warning_issue(client) # 3.4.8
    # 沉降页: 最大沉降点时序统计 /api/v1/upss/visualization/max-subsidence/timeseries
    test_get_max_subsidence_timeseries(client) # 3.4.10
    # 沉降页: 前五沉降梯度值位置统计 /api/v1/upss/visualization/top-gradient
    test_get_top_gradient(client) # 3.4.11
    # 沉降页: 风险评估 /api/v1/upss/risk
    # test_get_risk(client) # 3.4.12
    
    # 成都接口更改，不通过pointcode获取单点历史数据
    # 沉降页: 单点沉降历史 /api/v1/upss/points/{code}/history
    # point_set.add('1305')  # 添加一个默认点位，确保有数据可测
    # for pc in point_set:
    #     test_get_point_history(client, pointcode=pc) # 3.4.4

    # 沉降页: 沉降态势统计 /api/v1/upss/visualization/statistics/issue
    test_get_statistics_issue(client) # 3.4.9 暂时不测

def test_get_overview(client: APIClient):
    """沉降页: 测试获取模块概览"""
    number = '3.4.1'
    title = '沉降页: 模块概览'
    path = '/api/v1/upss/overview'
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
        save_response_to_file('upss_overview', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_periods(client: APIClient):
    """沉降页: 测试获取沉降期次列表"""
    number = '3.4.2'
    title = '沉降页: 沉降期列表'
    path = '/api/v1/upss/periods'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'pageNum': 1,
        # 'pageSize': 20,
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
        save_response_to_file('upss_periods', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    if response and response.get('code') == 200:
        data = response.get('data', [])
        for item in data:
            if 'issue' in item:
                issue_list.append(item['issue'])
    return response


def test_get_period_summary(client: APIClient, issue: str = "20221220"):
    """沉降页: 测试获取期次汇总统计"""
    number = '3.4.3'
    title = '沉降页: 期次汇总'
    issue = "20220424"
    path = f'/api/v1/upss/periods/{issue}/summary'
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
        save_response_to_file('upss_period_summary', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_point_history(client: APIClient, pointcode: str):
    """沉降页: 测试获取单点沉降历史"""
    number = '3.4.4'
    title = '沉降页: 单点沉降历史'
    code = pointcode
    path = f'/api/v1/upss/points/{code}/history'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'startIssue': '20180120',
        # 'endIssue': '20240101',
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
        save_response_to_file('upss_point_history', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_regional_statistics(client: APIClient, issue: str = None, pageNum: int = 1):
    """沉降页: 测试获取区域沉降统计"""
    number = '3.4.5'
    title = '沉降页: 沉降地图（热力图）'
    path = '/api/v1/upss/statistics/regional'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'issue': issue if issue else '20250203',
        'dimension': 'admin',
        'pageNum': pageNum,
        'pageSize': 1000,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        for point in data.get('points', []):
            if 'pointCode' in point:
                point_set.add(point['pointCode'])
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
        save_response_to_file('upss_regional_statistics', response, path + f'_{issue}' + f'_page{pageNum}', params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_grid_rate(client: APIClient, issue: str = None):
    """沉降页: 测试获取网格沉降速率"""
    number = '3.4.6'
    title = '沉降页: 沉降速率'
    path = '/api/v1/upss/statistics/gridRate'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'issue': issue if issue else '20250203',
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        for point in data.get('points', []):
            if 'pointCode' in point:
                point_set.add(point['pointCode'])
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
        save_response_to_file('upss_grid_rate', response, path + f'_{issue}', params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_grid_gradient(client: APIClient, issue: str = None):
    """沉降页: 测试获取网格沉降梯度"""
    number = '3.4.7'
    title = '沉降页: 沉降速率梯度'
    path = '/api/v1/upss/statistics/gridGradient'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'issue': issue if issue else '20250203',
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        for point in data.get('points', []):
            if 'pointCode' in point:
                point_set.add(point['pointCode'])
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
        save_response_to_file('upss_grid_gradient', response, path + f'_{issue}', params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_warning_issue(client: APIClient):
    """沉降页: 测试获取沉降预警信息"""
    number = '3.4.8'
    title = '沉降页: 预警信息'
    path = '/api/v1/upss/visualization/warning/issue'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'issue': '20220424',
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
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        for warning in data.get('warnings', []):
            if 'pointCode' in warning:
                point_set.add(warning['pointCode'])
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
        save_response_to_file('upss_warning_issue', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_statistics_issue(client: APIClient):
    """沉降页: 测试获取沉降态势统计"""
    number = '3.4.9'
    title = '沉降页: 沉降态势统计'
    path = '/api/v1/upss/visualization/statistics/issue'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'issue': '20250203',
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
        save_response_to_file('upss_statistics_issue', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_max_subsidence_timeseries(client: APIClient):
    """沉降页: 测试获取最大沉降点时序"""
    number = '3.4.10'
    title = '沉降页: 最大沉降点时序统计'
    path = '/api/v1/upss/visualization/max-subsidence/timeseries'
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
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        point_info = data.get('pointInfo', {})
        if 'pointCode' in point_info:
            point_set.add(point_info['pointCode'])
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
        save_response_to_file('upss_max_subsidence_timeseries', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_top_gradient(client: APIClient):
    """沉降页: 测试获取Top5沉降梯度"""
    number = '3.4.11'
    title = '沉降页: 前五沉降梯度值位置统计'
    path = '/api/v1/upss/visualization/top-gradient'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'startIssue': '20230723',
        # 'endIssue': '20250203',
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
    
    if response and response.get('code') == 200:
        data = response.get('data', {})
        for point in data.get('topPoints', []):
            if 'pointCode' in point:
                point_set.add(point['pointCode'])
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
        save_response_to_file('upss_top_gradient', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_risk(client: APIClient):
    """沉降页: 测试获取风险评估"""
    number = '3.4.12'
    title = '沉降页: 风险评估'
    path = '/api/v1/upss/risk'
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
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()
    
    print_response(title, 'GET', path, response, config.verbose, number=number, title=title, elapsed_seconds=elapsed)
    if config.save_response and response:
        save_response_to_file('upss_risk', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response






if __name__ == '__main__':
    run_all_tests()
