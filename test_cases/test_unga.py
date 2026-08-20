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


task_set = []


def test_get_overview(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    燃气页: 测试获取模块概览
    GET /api/v1/unga/overview
    """
    number = '3.5.1'
    title = '燃气页: 模块概览'
    path = '/api/v1/unga/overview'
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


def test_get_tasks(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num: int = 1, page_size: int = 20):
    """
    燃气页: 测试获取检测任务列表
    GET /api/v1/unga/tasks
    """
    number = '3.5.2'
    title = '燃气页: 检测任务列表'
    path = '/api/v1/unga/tasks'
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


def test_get_task_trajectory(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, task_id: int = 1):
    """
    燃气页: 测试获取任务轨迹数据
    GET /api/v1/unga/tasks/{id}/trajectory
    """
    number = '3.5.3'
    title = '燃气页: 走航轨迹查询'
    path = f'/api/v1/unga/tasks/{task_id}/trajectory'
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


def test_get_leaks(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num: int = 1, page_size: int = 20):
    """
    燃气页: 测试获取泄露点列表
    GET /api/v1/unga/leaks
    """
    number = '3.5.4'
    title = '燃气页: 泄露点管理'
    path = '/api/v1/unga/leaks'
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


def test_get_statistics(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    燃气页: 测试获取走航统计数据
    GET /api/v1/unga/statistics
    """
    number = '3.5.5'
    title = '燃气页: 统计分析'
    path = '/api/v1/unga/statistics'
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

def test_get_tasks_trajectory(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat, task_id: int = 1):
    """
    燃气页: 测试获取地理区域内轨迹数据
    GET /api/v1/unga/tasks/trajectory
    """
    number = '3.5.6'
    title = '燃气页: 走航轨迹查询'
    path = '/api/v1/unga/tasks/trajectory'
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

def test_get_statistics_ext(client: APIClient, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    燃气页: 测试获取区域内走航统计数据
    GET /api/v1/unga/statistics/ext
    """
    number = '3.5.7'
    title = '燃气页: 统计分析'
    path = '/api/v1/unga/statistics/ext'
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


def test_update_sampling_point_status(client: APIClient, samplingPointId: str, status: str):
    """
    燃气页: 测试设置采样点处置状态(仅写入)
    PUT /api/v1/unga/leaks/{samplingPointId}/status

    查询原始状态与恢复原始状态由调用方负责。

    status取值:
        unchecked: 疑似
        checking: 已处置
        confirmed: 已确认
    """
    number = '3.5.8'
    title = '燃气页: 设置采样点处置状态'
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


def test_get_sampling_point_status(client: APIClient, samplingPointId: str, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    燃气页: 查询采样点当前处置状态
    GET /api/v1/unga/leaks

    在泄露点列表中按 leakId/samplingPointId 匹配，返回该采样点当前 status；
    未找到时返回 None。
    """
    params = {
        'pageNum': 1,
        'pageSize': 2000,
        'startTime': startTime,
        'endTime': endTime,
        'minLng': minLng,
        'maxLng': maxLng,
        'minLat': minLat,
        'maxLat': maxLat,
    }
    resp = client.request('GET', '/api/v1/unga/leaks', params=params)
    if resp and resp.get('code') == 200:
        for leak in resp.get('data', {}).get('leaks', []):
            if leak.get('leakId') == samplingPointId or leak.get('samplingPointId') == samplingPointId:
                return leak.get('status')
    return None


def test_update_sampling_point_status_with_verify(client: APIClient, samplingPointId: str, statuses, startTime, endTime, minLng, maxLng, minLat, maxLat):
    """
    燃气页: 测试设置采样点处置状态并验证(查询原始状态 + 写入测试 + 恢复原始状态)

    流程:
        1. 通过泄露点列表查询该采样点当前处置状态
        2. 依次写入各目标状态，每次写入后读取一次状态检查是否写入成功
        3. 恢复为该采样点写入前的原始状态(写入后读取验证)

    statuses: 待测试的状态列表, 如 ['checking', 'confirmed']
    """
    # 1. 查询该采样点当前处置状态
    current_status = test_get_sampling_point_status(client, samplingPointId, startTime, endTime, minLng, maxLng, minLat, maxLat)
    print(f"采样点 {samplingPointId} 当前状态: {current_status}")

    # 2. 写入测试：每写入一次状态，读取一次状态检查是否写入成功
    for status in statuses:
        test_update_sampling_point_status(client, samplingPointId, status)  # 3.5.8
        verify_status = test_get_sampling_point_status(client, samplingPointId, startTime, endTime, minLng, maxLng, minLat, maxLat)
        if verify_status == status:
            print(f"✓ 写入成功: {samplingPointId} -> {status} (读取确认: {verify_status})")
        else:
            print(f"✗ 写入未生效: 期望 {status}, 读取到 {verify_status}")

    # 3. 恢复原始状态(同样写入后读取验证)
    if current_status is not None:
        test_update_sampling_point_status(client, samplingPointId, current_status)
        verify_status = test_get_sampling_point_status(client, samplingPointId, startTime, endTime, minLng, maxLng, minLat, maxLat)
        if verify_status == current_status:
            print(f"✓ 已恢复采样点 {samplingPointId} 原始状态: {current_status} (读取确认)")
        else:
            print(f"✗ 恢复失败: 期望 {current_status}, 读取到 {verify_status}")
    else:
        print(f"未获取到采样点 {samplingPointId} 原始状态, 跳过恢复")
        print(f"注意: 若需要手动恢复, 请将该点状态设为 unchecked")


if __name__ == '__main__':
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    # 测试时间范围与地理范围（仅从 common.py 的 loc_list 获取经纬度）
    startTime = int(datetime(2019, 1, 1, 0, 0, 0).timestamp()) * 1000
    endTime = int(datetime(2019, 12, 31, 23, 59, 59).timestamp()) * 1000
    minLng, maxLng, minLat, maxLat = loc_list['重庆']

    # 燃气页: 模块概览 /api/v1/unga/overview
    test_get_overview(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.5.1

    # 燃气页: 检测任务列表 /api/v1/unga/tasks
    test_get_tasks(client, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num=1, page_size=2000) # 3.5.2

    # 燃气页: 走航轨迹查询 /api/v1/unga/tasks/{id}/trajectory
    for task_id in task_set:
        test_get_task_trajectory(client, startTime, endTime, minLng, maxLng, minLat, maxLat, task_id=task_id) # 3.5.3

    # 燃气页: 泄露点管理 /api/v1/unga/leaks
    test_get_leaks(client, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num=1, page_size=2000) # 3.5.4

    # 燃气页: 统计分析 /api/v1/unga/statistics
    # test_get_statistics(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.5.5
    
    # 燃气页: 走航轨迹查询 /api/v1/unga/tasks/trajectory
    test_get_tasks_trajectory(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.5.6

    # 燃气页: 统计分析 /api/v1/unga/statistics/ext
    test_get_statistics_ext(client, startTime, endTime, minLng, maxLng, minLat, maxLat) # 3.5.7

    # 燃气页: 设置采样点处置状态 /api/v1/unga/leaks/{samplingPointId}/status
    # 查询原始状态 -> 写入测试(每次写入后读取验证) -> 恢复原始状态 由函数统一完成
    sampling_point_id = '180500001587_20190903_2254:leak_0'  # 原状态: unchecked
    test_update_sampling_point_status_with_verify(client, sampling_point_id, ['checking', 'confirmed'], startTime, endTime, minLng, maxLng, minLat, maxLat)  # 3.5.8
