# -*- coding: utf-8 -*-
"""
响应数据打印工具
格式化打印API响应数据
"""
import json
import os
from typing import Any, Dict
from datetime import datetime


def print_response(
    api_name: str,
    method: str,
    path: str,
    response: Any,
    verbose: bool = True
):
    """
    格式化打印API响应

    Args:
        api_name: API名称
        method: HTTP方法
        path: API路径
        response: 响应数据
        verbose: 是否打印详细信息
    """
    print("\n" + "=" * 60)
    print(f"API测试: {api_name}")
    print("=" * 60)
    print(f"请求方法: {method}")
    print(f"请求路径: {path}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    if response is None:
        print("响应: 请求失败")
    elif isinstance(response, dict):
        # 检查业务响应码
        if 'code' in response:
            code = response['code']
            message = response.get('message', '')
            data = response.get('data', None)

            if code == 200:
                print(f"响应状态: 成功 (code={code})")
                if message:
                    print(f"响应消息: {message}")
                if verbose and data is not None:
                    print(f"响应数据:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"响应状态: 失败 (code={code})")
                print(f"错误消息: {message}")
        else:
            # 直接打印响应
            if verbose:
                print("响应数据:")
                print(json.dumps(response, indent=2, ensure_ascii=False))
    else:
        print(f"响应数据: {response}")

    print("=" * 60 + "\n")


def save_response_to_file(
    api_name: str,
    response: Any,
    response_dir: str = 'responses'
):
    """
    保存响应到文件

    Args:
        api_name: API名称
        response: 响应数据
        response_dir: 保存目录
    """
    # 创建保存目录
    os.makedirs(response_dir, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = api_name.replace('/', '_').replace(' ', '_')
    filename = f"{timestamp}_{safe_name}.json"
    filepath = os.path.join(response_dir, filename)

    # 保存响应
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(response, f, indent=2, ensure_ascii=False)

    print(f"响应已保存到: {filepath}")
