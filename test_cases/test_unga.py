# -*- coding: utf-8 -*-
"""
燃气页
"""
import sys
import os

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
startTime_file = int(datetime(2019,1,1,0,0,0).timestamp()) * 1000    
endTime_file = int(datetime(2019,12,31,23,59,59).timestamp()) * 1000
# startTime_file = int(datetime(2026,5,5,0,0,0).timestamp()) * 1000    
# endTime_file = int(datetime(2026,6,5,23,59,59).timestamp()) * 1000
minLng_file = minLng_global
maxLng_file = maxLng_global
minLat_file = minLat_global
maxLat_file = maxLat_global

task_set = []


def test_get_overview(client: APIClient):
    """
    燃气页: 测试获取模块概览
    GET /api/v1/unga/overview
    """
    number = '3.5.1'
    title = '燃气页: 模块概览'
    path = '/api/v1/unga/overview'
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
        save_response_to_file('unga_overview', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response


def test_get_tasks(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    燃气页: 测试获取检测任务列表
    GET /api/v1/unga/tasks
    """
    number = '3.5.2'
    title = '燃气页: 检测任务列表'
    path = '/api/v1/unga/tasks'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
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
        save_response_to_file('unga_tasks', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    global task_set
    if response :

        tasks = response.get("data", {}).get("tasks", [])
        task_set = [t["taskId"] for t in tasks if "taskId" in t]

    return response


def test_get_task_trajectory(client: APIClient, task_id: int = 1):
    """
    燃气页: 测试获取任务轨迹数据
    GET /api/v1/unga/tasks/{id}/trajectory
    """
    number = '3.5.3'
    title = '燃气页: 走航轨迹查询'
    path = f'/api/v1/unga/tasks/{task_id}/trajectory'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'startTime': startTime,
        # 'endTime': endTime,
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
        save_response_to_file('unga_task_trajectory', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response


def test_get_leaks(client: APIClient, page_num: int = 1, page_size: int = 20):
    """
    燃气页: 测试获取泄露点列表
    GET /api/v1/unga/leaks
    """
    number = '3.5.4'
    title = '燃气页: 泄露点管理'
    path = '/api/v1/unga/leaks'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        'pageNum': page_num,
        'pageSize': page_size,
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
        save_response_to_file('unga_leaks', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response


def test_get_statistics(client: APIClient):
    """
    燃气页: 测试获取走航统计数据
    GET /api/v1/unga/statistics
    """
    number = '3.5.5'
    title = '燃气页: 统计分析'
    path = '/api/v1/unga/statistics'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'packId': '430000003510_20250630_1437',
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
        save_response_to_file('unga_statistics', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response

def test_get_tasks_trajectory(client: APIClient, task_id: int = 1):
    """
    燃气页: 测试获取地理区域内轨迹数据
    GET /api/v1/unga/tasks/trajectory
    """
    number = '3.5.6'
    title = '燃气页: 走航轨迹查询'
    path = '/api/v1/unga/tasks/trajectory'
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
        save_response_to_file('unga_tasks_trajectory', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response

def test_get_statistics_ext(client: APIClient):
    """
    燃气页: 测试获取区域内走航统计数据
    GET /api/v1/unga/statistics/ext
    """
    number = '3.5.7'
    title = '燃气页: 统计分析'
    path = '/api/v1/unga/statistics/ext'
    startTime = startTime_file
    endTime = endTime_file
    minLng = minLng_file
    maxLng = maxLng_file
    minLat = minLat_file
    maxLat = maxLat_file
    params = {
        # 'packId': '430000003510_20250630_1437',
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
        save_response_to_file('unga_statistics_ext', response, path, params, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response


def test_update_sampling_point_status(client: APIClient, status: str):
    """
    燃气页: 测试设置采样点处置状态
    PUT /api/v1/unga/leaks/{samplingPointId}/status

    status取值:
        unchecked: 疑似
        checking: 已处置
        confirmed: 已确认
    """
    number = '3.5.8'
    title = '燃气页: 设置采样点处置状态'
    samplingPointId = '180500001587_20190903_2254:leak_0'  # 原状态: unchecked
    path = f'/api/v1/unga/leaks/{samplingPointId}/status'
    data = {
        'status': status,
    }
    start_dt = datetime.now()
    response = client.request('PUT', path, data=data)
    end_dt = datetime.now()
    elapsed = (end_dt - start_dt).total_seconds()

    print_response(
        title,
        'PUT',
        path,
        response,
        config.verbose,
        number=number,
        title=title,
        elapsed_seconds=elapsed,
    )

    if config.save_response and response:
        save_response_to_file('unga_sampling_point_status', response, path, data, config.response_dir, number=number, title=title, start_time=start_dt, end_time=end_dt)

    return response


def run_all_tests():
    """运行燃气页模块的所有测试 1 2 3 4 5 6"""
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 燃气页: 模块概览 /api/v1/unga/overview
    test_get_overview(client) # 3.5.1

    # 燃气页: 检测任务列表 /api/v1/unga/tasks
    test_get_tasks(client, page_num=1, page_size=2000) # 3.5.2

    # 燃气页: 走航轨迹查询 /api/v1/unga/tasks/{id}/trajectory
    for task_id in task_set:
        test_get_task_trajectory(client, task_id=task_id) # 3.5.3

    # 燃气页: 泄露点管理 /api/v1/unga/leaks
    test_get_leaks(client, page_num=1, page_size=2000) # 3.5.4

    # 燃气页: 统计分析 /api/v1/unga/statistics
    # test_get_statistics(client) # 3.5.5
    
    # 燃气页: 走航轨迹查询 /api/v1/unga/tasks/trajectory
    test_get_tasks_trajectory(client) # 3.5.6

    # 燃气页: 统计分析 /api/v1/unga/statistics/ext
    test_get_statistics_ext(client) # 3.5.7

    # 燃气页: 设置采样点处置状态 /api/v1/unga/leaks/{samplingPointId}/status
    test_update_sampling_point_status(client, status='checking') # 3.5.8
    test_update_sampling_point_status(client, status='confirmed') # 3.5.8

    # 燃气页: 设置采样点处置状态 /api/v1/unga/leaks/{samplingPointId}/status
    # 测试unchecked状态，同时恢复原状态
    test_update_sampling_point_status(client, status='unchecked') # 3.5.8

if __name__ == '__main__':
    run_all_tests()
