# -*- coding: utf-8 -*-
"""
运行所有API测试的主程序
"""
import sys
import os
import argparse
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


def run_tests(modules=None):
    """
    运行测试

    Args:
        modules: 要测试的模块列表,None表示测试所有模块
    """
    start_time = datetime.now()

    print("\n" + "=" * 70)
    print(" " * 15 + "中检数据治理平台 API 测试程序")
    print("=" * 70)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    # 确定要测试的模块
    if modules is None:
        test_modules = MODULES.items()
    else:
        test_modules = [(k, v) for k, v in MODULES.items() if k in modules]

        # 检查无效的模块名
        invalid_modules = set(modules) - set(MODULES.keys())
        if invalid_modules:
            print(f"警告: 以下模块不存在: {', '.join(invalid_modules)}")
            print(f"可用模块: {', '.join(MODULES.keys())}\n")

    # 运行测试
    for module_key, (module_name, test_func) in test_modules:
        print(f"\n{'=' * 70}")
        print(f"正在测试模块: {module_name} ({module_key})")
        print('=' * 70)

        try:
            test_func()
        except Exception as e:
            print(f"模块测试失败: {e}")
            import traceback
            traceback.print_exc()

    # 测试结束
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 70)
    print(f"测试完成! 总耗时: {duration:.2f}秒")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
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
