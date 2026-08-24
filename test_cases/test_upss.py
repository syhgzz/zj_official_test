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


point_set = set()
issue_list = []

def test_get_overview(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取模块概览"""
    number = '3.4.1'
    title = '沉降页: 模块概览'
    path = '/api/v1/upss/overview'
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


def test_get_periods(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取沉降期次列表"""
    number = '3.4.2'
    title = '沉降页: 沉降期列表'
    path = '/api/v1/upss/periods'
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


def test_get_period_summary(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, issue: str = "20221220"):
    """沉降页: 测试获取期次汇总统计"""
    number = '3.4.3'
    title = '沉降页: 期次汇总'
    issue = "20220424"
    path = f'/api/v1/upss/periods/{issue}/summary'
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


def test_get_point_history(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, pointcode: str):
    """沉降页: 测试获取单点沉降历史"""
    number = '3.4.4'
    title = '沉降页: 单点沉降历史'
    code = pointcode
    path = f'/api/v1/upss/points/{code}/history'
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


def test_get_regional_statistics(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, issue: str = None, pageNum: int = 1):
    """沉降页: 测试获取区域沉降统计"""
    number = '3.4.5'
    title = '沉降页: 沉降地图（热力图）'
    path = '/api/v1/upss/statistics/regional'
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


def test_get_grid_rate(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, issue: str = None):
    """沉降页: 测试获取网格沉降速率"""
    number = '3.4.6'
    title = '沉降页: 沉降速率'
    path = '/api/v1/upss/statistics/gridRate'
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


def test_get_grid_gradient(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, issue: str = None):
    """沉降页: 测试获取网格沉降梯度"""
    number = '3.4.7'
    title = '沉降页: 沉降速率梯度'
    path = '/api/v1/upss/statistics/gridGradient'
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


def test_get_warning_issue(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取沉降预警信息"""
    number = '3.4.8'
    title = '沉降页: 预警信息'
    path = '/api/v1/upss/visualization/warning/issue'
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


def test_get_statistics_issue(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取沉降态势统计"""
    number = '3.4.9'
    title = '沉降页: 沉降态势统计'
    path = '/api/v1/upss/visualization/statistics/issue'
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


def test_get_max_subsidence_timeseries(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取最大沉降点时序"""
    number = '3.4.10'
    title = '沉降页: 最大沉降点时序统计'
    path = '/api/v1/upss/visualization/max-subsidence/timeseries'
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


def test_get_top_gradient(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取Top5沉降梯度"""
    number = '3.4.11'
    title = '沉降页: 前五沉降梯度值位置统计'
    path = '/api/v1/upss/visualization/top-gradient'
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


def test_get_risk(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """沉降页: 测试获取风险评估"""
    number = '3.4.12'
    title = '沉降页: 风险评估'
    path = '/api/v1/upss/risk'
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


def test_get_issue_layer(client: APIClient):
    """沉降页: 测试获取沉降图层(已生成WMTS数据的期次列表与图层地址)"""
    number = ''
    title = '沉降页: 沉降图层'
    path = '/api/v1/upss/issue_layer'
    params = {}
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    print_response(title, 'GET', path, response, config.verbose, number=number, title=title, elapsed_seconds=elapsed)
    if config.save_response and response:
        save_response_to_file('upss_issue_layer', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


def test_get_issue_list(client: APIClient):
    """沉降页: 测试获取沉降图固定显示的8个期次"""
    number = ''
    title = '沉降页: 沉降图期次列表'
    path = '/api/v1/upss/issue-list'
    params = {}
    start_dt = datetime.now()
    response = client.request('GET', path, params=params)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    print_response(title, 'GET', path, response, config.verbose, number=number, title=title, elapsed_seconds=elapsed)
    if config.save_response and response:
        save_response_to_file('upss_issue_list', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)
    return response


if __name__ == '__main__':
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2025, 1, 1, 0, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2025, 2, 28, 23, 59, 59).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 沉降页: 模块概览 /api/v1/upss/overview
    # test_get_overview(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.1
    # 沉降页: 沉降期列表 /api/v1/upss/periods
    test_get_periods(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.2
    # 沉降页: 期次汇总 /api/v1/upss/periods/{issue}/summary
    # test_get_period_summary(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.3
    # 沉降页: 沉降地图（热力图） /api/v1/upss/statistics/regional
    # for issue in issue_list:
    #     for pg in range(1, 100):
    #         test_get_regional_statistics(client, startTime, endTime, minLng, maxLng, minLat, maxLat, issue=issue, pageNum=pg) # 3.4.5
    # 沉降页: 沉降速率 /api/v1/upss/statistics/gridRate
    #     test_get_grid_rate(client, startTime, endTime, minLng, maxLng, minLat, maxLat, issue=issue) # 3.4.6
    # 沉降页: 沉降速率梯度 /api/v1/upss/statistics/gridGradient
    #     test_get_grid_gradient(client, startTime, endTime, minLng, maxLng, minLat, maxLat, issue=issue) # 3.4.7
    # 沉降页: 预警信息 /api/v1/upss/visualization/warning/issue
    test_get_warning_issue(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.8
    # 沉降页: 最大沉降点时序统计 /api/v1/upss/visualization/max-subsidence/timeseries
    test_get_max_subsidence_timeseries(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.10
    # 沉降页: 前五沉降梯度值位置统计 /api/v1/upss/visualization/top-gradient
    test_get_top_gradient(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.11
    # 沉降页: 风险评估 /api/v1/upss/risk
    # test_get_risk(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.12

    # 成都接口更改，不通过pointcode获取单点历史数据
    # 沉降页: 单点沉降历史 /api/v1/upss/points/{code}/history
    # point_set.add('1305')  # 添加一个默认点位，确保有数据可测
    # for pc in point_set:
    #     test_get_point_history(client, startTime, endTime, minLng, maxLng, minLat, maxLat, pointcode=pc) # 3.4.4

    # 沉降页: 沉降态势统计 /api/v1/upss/visualization/statistics/issue
    # test_get_statistics_issue(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.4.9 暂时不测

    # 沉降页: 沉降图期次列表 /api/v1/upss/issue-list
    test_get_issue_list(client) 
    # 沉降页: 沉降图层 /api/v1/upss/issue_layer
    test_get_issue_layer(client) 

    
