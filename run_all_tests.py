# -*- coding: utf-8 -*-
"""
运行所有API测试的主程序
"""
import sys
import os
import argparse
import inspect
import traceback
from datetime import datetime

# 确保可以导入test_cases模块
sys.path.insert(0, os.path.dirname(__file__))

# 导入各模块测试
from test_cases.test_overview import run_all_tests as test_overview
from test_cases.test_unga import run_all_tests as test_unga
from test_cases.test_gnss_device import run_all_tests as test_gnss_device
from test_cases.test_upns import run_all_tests as test_upns
from test_cases.test_ugss import run_all_tests as test_ugss
from test_cases.test_udmds import run_all_tests as test_udmds
from test_cases.test_upss import run_all_tests as test_upss
from config.config import config
from lib.response_printer import (
    start_stats_capture,
    stop_stats_capture,
    set_module_context,
    save_summary_to_file,
)


# 模块映射
MODULES = {
    'overview': ('系统概览', test_overview),
    'unga': ('走航甲烷检测', test_unga),
    'gnss-device': ('北斗设备状态', test_gnss_device),
    'upns': ('短临降水预警', test_upns),
    'ugss': ('GNSS干扰监测', test_ugss),
    'udmds': ('形变安全监测', test_udmds),
    'upss': ('沉降态势感知', test_upss),
}


def _count_module_interfaces(test_func) -> int:
    """统计模块内 test_ 开头的接口测试函数数量。"""
    module = inspect.getmodule(test_func)
    if module is None:
        return 0

    test_functions = [
        func_name
        for func_name, func in inspect.getmembers(module, inspect.isfunction)
        if func.__module__ == module.__name__ and func_name.startswith('test_')
    ]
    return len(test_functions)


def _build_module_plan(test_modules):
    """构建模块执行计划，包含每模块计划接口数。"""
    module_plan = []
    for module_key, (module_name, test_func) in test_modules:
        module_total = _count_module_interfaces(test_func)
        module_plan.append({
            'module_key': module_key,
            'module_name': module_name,
            'module_total': module_total,
            'test_func': test_func,
        })
    return module_plan


def run_tests(modules=None):
    """
    运行测试

    Args:
        modules: 要测试的模块列表,None表示测试所有模块
    """
    start_time = datetime.now()

    # 确定要测试的模块
    if modules is None:
        test_modules = list(MODULES.items())
    else:
        test_modules = [(k, v) for k, v in MODULES.items() if k in modules]

        # 检查无效的模块名
        invalid_modules = set(modules) - set(MODULES.keys())
        if invalid_modules:
            print(f"警告: 以下模块不存在: {', '.join(invalid_modules)}")
            print(f"可用模块: {', '.join(MODULES.keys())}\n")

    module_plan = _build_module_plan(test_modules)
    planned_total = sum(item['module_total'] for item in module_plan)

    start_stats_capture(
        response_dir=config.response_dir,
        planned_total=planned_total,
        module_plan=[
            {
                'module_key': item['module_key'],
                'module_name': item['module_name'],
            }
            for item in module_plan
        ],
        started_at=start_time,
    )

    print("\n" + "=" * 70)
    print("中检数据治理平台 API 测试程序")
    print("=" * 70)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"计划模块数: {len(module_plan)}")
    print(f"计划接口总数: {planned_total}")
    print("=" * 70)

    # 运行测试
    for item in module_plan:
        module_key = item['module_key']
        module_name = item['module_name']
        module_total = item['module_total']
        test_func = item['test_func']

        set_module_context(module_key, module_name, module_total)
        print(f"\n[{module_name} ({module_key})] 开始测试，共{module_total}个接口")

        try:
            test_func()
        except Exception as e:
            print(f"[ERROR] 模块测试失败: {module_name} ({module_key}) - {e}")
            traceback.print_exc()

    # 测试结束
    end_time = datetime.now()
    summary_path, summary_text = save_summary_to_file(filename='summary.md', end_time=end_time)
    stop_stats_capture()

    print("\n" + "=" * 70)
    print("API测试统计汇总")
    print("=" * 70)
    print(summary_text.rstrip())
    print(f"\n统计文件已保存: {summary_path}")
    print("=" * 70 + "\n")


def list_modules():
    """列出所有可用模块"""
    print("\n可用的测试模块:")
    print("-" * 60)
    for key, (name, _) in MODULES.items():
        print(f"  {key:15} - {name}")
    print("-" * 60 + "\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='中检数据治理平台 API 测试程序',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试所有模块
  python run_all_tests.py

  # 测试指定模块
  python run_all_tests.py -m overview upss

  # 列出所有可用模块
  python run_all_tests.py --list
        """
    )

    parser.add_argument(
        '-m', '--modules',
        nargs='+',
        help='指定要测试的模块'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='列出所有可用模块'
    )

    args = parser.parse_args()

    if args.list:
        list_modules()
    else:
        run_tests(args.modules)


if __name__ == '__main__':
    main()
