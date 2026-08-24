'''
甲方需要8.30展示的部分，进行接口测试. 各个模块页面的测试时间段和城市如下表所示，测试时请注意：

    |    页面|    城市|    时间段    

    |    形变|    重庆|    26.5.1-26.8.20
    |    燃气|    重庆|    19.9.1-19.9.30
    |    燃气|    北京|    26.5.1-26.5.30
    |    燃气|    株洲|    任意有数据时间段
    |    沉降|    重庆|    18.1.1-25.12.31
    |    沉降|    株洲|    22.1.1-25.12.31
    |    降水|    重庆|    26.5.1-26.8.20
    |    降水|    北京|    26.5.1-26.8.20

'''
# 测试范围: 各模块测试文件 __main__ 中启用的接口(注释掉的不测; 3.4.9 暂时不测; 3.5.8 写接口不测)
# 输出目录: responses_0830/<模块>_<城市>_<时间段>/, 问题接口汇总写入 responses_0830/report.md
# 除 print_response 的成功/失败判定外, 额外检查返回 data 是否为空或为0, 空则控制台提示
#
# 函数职责:
#   check_data   只检查响应, 返回失败原因
#   run_case     只编排一次调用(调用->检查->拼装记录), 保持外层调用简洁
#   write_report 只把记录写入 report.md
#
# run_case 的 tag 使用各模块测试函数内部的 title 字符串(如 '形变页: 告警汇总'),
# 同时用于控制台空数据提示和 report.md 记录。
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import config
from lib.api_client import APIClient

try:
    from test_cases.common import loc_list
    from test_cases import test_udmds, test_unga, test_upss, test_upns_a, test_upns_w
    from test_cases import test_api_v1_upss_samples as upss_samples
except ImportError:
    from common import loc_list
    import test_udmds, test_unga, test_upss, test_upns_a, test_upns_w
    import test_api_v1_upss_samples as upss_samples

# 本次测试响应输出根目录
RESPONSE_ROOT = 'responses_0830'


def set_response_dir(sub_dir):
    """切换响应保存目录到 responses_0830/<sub_dir>, 并强制开启保存开关

    各模块测试函数内部通过 config.response_dir 读取保存目录;
    response_dir 是 property, 需改底层 ConfigParser 生效。
    按 模块_城市_时间段 分目录, 避免多城市同名文件互相覆盖。
    """
    if not config.config.has_section('test'):
        config.config.add_section('test')
    config.config.set('test', 'save_response', 'true')
    config.config.set('test', 'response_dir', os.path.join(RESPONSE_ROOT, sub_dir))


def _is_empty_data(value):
    """递归判断数据是否无有效内容:
    None、空串、空列表/字典、数值0 均视为空;
    字典中含有列表/字典类型字段时, 只按这些集合字段判定
    (字符串/数值等标量视为元数据, 如 layer/unit/layerName, 不算有效数据)"""
    if value is None or value == '':
        return True
    if isinstance(value, bool):
        return False  # 布尔值视为有效数据
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, (list, tuple)):
        return len(value) == 0 or all(_is_empty_data(v) for v in value)
    if isinstance(value, dict):
        if not value:
            return True
        collections = [v for v in value.values() if isinstance(v, (list, tuple, dict))]
        if collections:
            return all(_is_empty_data(v) for v in collections)
        return all(_is_empty_data(v) for v in value.values())
    return False


def check_data(tag, response):
    """检查一次接口调用的响应, 返回失败原因('' 表示正常)

    调用成功但 data 为空/为0 时在控制台给出提示;
    调用失败的 FAILED 行已由 print_response 输出, 这里不重复打印。
    """
    if isinstance(response, tuple):  # 兼容 test_get_points/test_get_stations 返回 (response, list)
        response = response[0]

    if response is None:
        return '调用失败(无响应: 连接失败或HTTP状态码非200)'
    if not isinstance(response, dict):
        return f'响应格式异常: {type(response).__name__}'
    if response.get('timeout'):
        return f'请求超时(超过{config.timeout}s)'

    code = response.get('code')
    if isinstance(code, str) and code.isdigit():
        code = int(code)
    if code != 200:
        msg = response.get('msg') or response.get('message') or ''
        return f"业务失败(code={response.get('code')}, msg={msg})"

    if _is_empty_data(response.get('data')):
        print(f'[空数据提示] {tag}: 接口调用成功, 但返回数据为空或为0, 请确认该城市/时间段是否有数据')
        return '返回数据为空或为0'

    return ''


def run_case(tag, path, params, report_records, func, *args, **kwargs):
    """调用模块测试函数 func, 并用 check_data 检查响应

    有问题时把 接口名称(tag)/路径/请求参数/失败原因 拼装追加到 report_records;
    返回 func 的原始返回值(供取站点编码等)。本套件接口全为 GET。
    """
    response = func(*args, **kwargs)
    reason = check_data(tag, response)
    if reason:
        report_records.append({'method': 'GET', 'tag': tag, 'path': path, 'params': params, 'reason': reason})
    return response


def _humanize_params(params):
    """请求参数转人类可读形式, 用于报告展示:
    startTime/endTime 毫秒时间戳转可读时间; minLng/maxLng/minLat/maxLat 精确匹配 loc_list 转为城市名。
    """
    if not params:
        return '无'
    bbox_keys = ('minLng', 'maxLng', 'minLat', 'maxLat')
    result = {}
    for k, v in params.items():
        if k in ('startTime', 'endTime') and isinstance(v, (int, float)):
            result[k] = ts_str(v)  # 时间戳转可读时间
        else:
            result[k] = v
    # 4 个经纬度值与 loc_list 精确一致时, 替换为城市名
    if all(k in params for k in bbox_keys):
        bbox = [params[k] for k in bbox_keys]
        for city, city_bbox in loc_list.items():
            if bbox == list(city_bbox):
                result = {k: v for k, v in result.items() if k not in bbox_keys}
                result['城市'] = city
                break
    return json.dumps(result, ensure_ascii=False)


def write_report(start_dt, report_records):
    """把本次运行的问题接口(超时/调用失败/业务失败/空数据)写入 responses_0830/report.md

    每条记录含 接口名称/路径/请求参数/失败原因;
    文件开头写测试运行时间和超时判定秒数。
    """
    os.makedirs(RESPONSE_ROOT, exist_ok=True)
    lines = [
        '# 接口测试问题报告',
        '',
        f"- 测试运行时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}",
        f'- 超时判定限制: {config.timeout}s',
        f'- 问题接口数: {len(report_records)}',
        '',
    ]
    for i, rec in enumerate(report_records, 1):
        lines.append(f"## {i}. [{rec['tag']}] {rec['method']} {rec['path']}")
        lines.append(f"- 失败原因: {rec['reason']}")
        params = rec.get('params')
        lines.append(f"- 请求参数: {json.dumps(params, ensure_ascii=False) if params else '无'}")
        lines.append(f"- 请求参数(转化): {_humanize_params(params)}")
        lines.append('')
    report_path = os.path.join(RESPONSE_ROOT, 'report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'\n问题报告已保存到 {report_path} (共 {len(report_records)} 条)')


def ts(y, m, d, h=0, mi=0, s=0, end=False):
    """构造毫秒时间戳; end=True 时取当天 23:59:59"""
    if end:
        h, mi, s = 23, 59, 59
    return int(datetime(y, m, d, h, mi, s).timestamp()) * 1000


def range_str(startTime, endTime):
    """毫秒时间戳区间转目录后缀: 同一天取 YYYYMMDD_HHMM-HHMM, 跨天取 YYYYMMDD-YYYYMMDD"""
    s = datetime.fromtimestamp(startTime / 1000)
    e = datetime.fromtimestamp(endTime / 1000)
    if s.date() == e.date():
        return f"{s.strftime('%Y%m%d_%H%M')}-{e.strftime('%H%M')}"
    return f"{s.strftime('%Y%m%d')}-{e.strftime('%Y%m%d')}"


def ts_str(ms):
    """毫秒时间戳转人类可读时间字符串, 用于控制台显示"""
    return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')


def run_udmds(client, city, startTime, endTime, report_records):
    """形变页: 按 test_udmds.py __main__ 中启用的接口执行(3.2.6/3.2.8 已注释, 不测)"""
    print(f'\n========== 形变页 - {city} ({ts_str(startTime)} ~ {ts_str(endTime)}) ==========')
    set_response_dir(f'形变_{city}_{range_str(startTime, endTime)}')
    minLng, maxLng, minLat, maxLat = loc_list[city]
    bbox_params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat}
    time_params = {'startTime': startTime, 'endTime': endTime, **bbox_params}

    # 形变页: 告警汇总 /api/v1/udmds/alerts/summary
    run_case('形变页: 告警汇总', '/api/v1/udmds/alerts/summary', time_params, report_records,
             test_udmds.test_get_alerts_summary, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 形变页: 模块概览 /api/v1/udmds/overview
    run_case('形变页: 模块概览', '/api/v1/udmds/overview', bbox_params, report_records,
             test_udmds.test_get_overview, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 形变页: 工程列表 /api/v1/udmds/projects
    run_case('形变页: 工程列表', '/api/v1/udmds/projects', {'pageNum': 1, 'pageSize': 20, **time_params}, report_records,
             test_udmds.test_get_projects, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 形变页: 监测点列表 /api/v1/udmds/points
    resp, pointcode_list = run_case('形变页: 监测点列表', '/api/v1/udmds/points', time_params, report_records,
                                    test_udmds.test_get_points, client, startTime, endTime, minLng, maxLng, minLat, maxLat)

    # 循环每个监测点: 单点实时数据 + 单点历史趋势
    print(f'\n共获取到 {len(pointcode_list)} 个监测点, 开始循环测试实时数据和历史趋势...\n')
    for code in pointcode_list:
        # 形变页: 单点实时数据 /api/v1/udmds/points/{code}/realtime
        run_case('形变页: 单点实时数据', f'/api/v1/udmds/points/{code}/realtime', None, report_records,
                 test_udmds.test_get_point_realtime, client, startTime, endTime, minLng, maxLng, minLat, maxLat, code=code)
        # 形变页: 单点历史趋势 /api/v1/udmds/points/{code}/history
        run_case('形变页: 单点历史趋势', f'/api/v1/udmds/points/{code}/history', {'interval': '1h', **time_params}, report_records,
                 test_udmds.test_get_point_history, client, startTime, endTime, minLng, maxLng, minLat, maxLat, code=code)


def run_unga(client, city, startTime, endTime, report_records):
    """燃气页: 按 test_unga.py __main__ 中启用的接口执行(3.5.5 已注释不测; 3.5.8 写接口不测)"""
    print(f'\n========== 燃气页 - {city} ({ts_str(startTime)} ~ {ts_str(endTime)}) ==========')
    set_response_dir(f'燃气_{city}_{range_str(startTime, endTime)}')
    minLng, maxLng, minLat, maxLat = loc_list[city]
    bbox_params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat}
    time_params = {'startTime': startTime, 'endTime': endTime, **bbox_params}

    # 燃气页: 模块概览 /api/v1/unga/overview
    run_case('燃气页: 模块概览', '/api/v1/unga/overview', time_params, report_records,
             test_unga.test_get_overview, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 燃气页: 检测任务列表 /api/v1/unga/tasks (taskId 写入模块全局 task_set)
    run_case('燃气页: 检测任务列表', '/api/v1/unga/tasks', {'pageNum': 1, 'pageSize': 2000, **time_params}, report_records,
             test_unga.test_get_tasks, client, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num=1, page_size=2000)

    # 燃气页: 走航轨迹查询(单任务) /api/v1/unga/tasks/{id}/trajectory, 循环全部任务
    print(f'\n共获取到 {len(test_unga.task_set)} 个检测任务, 开始循环测试单任务轨迹...\n')
    for task_id in test_unga.task_set:
        run_case('燃气页: 走航轨迹查询', f'/api/v1/unga/tasks/{task_id}/trajectory', bbox_params, report_records,
                 test_unga.test_get_task_trajectory, client, startTime, endTime, minLng, maxLng, minLat, maxLat, task_id=task_id)

    # 燃气页: 泄露点管理 /api/v1/unga/leaks
    run_case('燃气页: 泄露点管理', '/api/v1/unga/leaks', {'pageNum': 1, 'pageSize': 2000, **time_params}, report_records,
             test_unga.test_get_leaks, client, startTime, endTime, minLng, maxLng, minLat, maxLat, page_num=1, page_size=2000)
    # 燃气页: 区域内走航轨迹查询 /api/v1/unga/tasks/trajectory
    run_case('燃气页: 走航轨迹查询', '/api/v1/unga/tasks/trajectory', time_params, report_records,
             test_unga.test_get_tasks_trajectory, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 燃气页: 统计分析 /api/v1/unga/statistics/ext
    run_case('燃气页: 统计分析', '/api/v1/unga/statistics/ext', time_params, report_records,
             test_unga.test_get_statistics_ext, client, startTime, endTime, minLng, maxLng, minLat, maxLat)


def run_upss(client, city, startTime, endTime, report_records):
    """沉降页: 按 test_upss.py __main__ 中启用的接口执行(3.4.9 暂时不测, 其余注释接口不测)"""
    print(f'\n========== 沉降页 - {city} ({ts_str(startTime)} ~ {ts_str(endTime)}) ==========')
    set_response_dir(f'沉降_{city}_{range_str(startTime, endTime)}')
    minLng, maxLng, minLat, maxLat = loc_list[city]
    bbox_params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat}
    time_params = {'startTime': startTime, 'endTime': endTime, **bbox_params}

    # 沉降页: 沉降期列表 /api/v1/upss/periods (issue 写入模块全局 issue_list, 供抽样点接口循环使用)
    test_upss.issue_list.clear()  # issue_list 是 append 模式, 先清空避免混入其他城市组
    run_case('沉降页: 沉降期列表', '/api/v1/upss/periods', time_params, report_records,
             test_upss.test_get_periods, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    issues = list(test_upss.issue_list)  # 本城市组的期次快照
    # 沉降页: 预警信息 /api/v1/upss/visualization/warning/issue
    run_case('沉降页: 预警信息', '/api/v1/upss/visualization/warning/issue', time_params, report_records,
             test_upss.test_get_warning_issue, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 沉降页: 最大沉降点时序统计 /api/v1/upss/visualization/max-subsidence/timeseries
    run_case('沉降页: 最大沉降点时序统计', '/api/v1/upss/visualization/max-subsidence/timeseries', time_params, report_records,
             test_upss.test_get_max_subsidence_timeseries, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 沉降页: 前五沉降梯度值位置统计 /api/v1/upss/visualization/top-gradient
    run_case('沉降页: 前五沉降梯度值位置统计', '/api/v1/upss/visualization/top-gradient', time_params, report_records,
             test_upss.test_get_top_gradient, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 沉降页: 沉降图层 /api/v1/upss/issue_layer
    run_case('沉降页: 沉降图层', '/api/v1/upss/issue_layer', None, report_records,
             test_upss.test_get_issue_layer, client)
    # 沉降页: 沉降图期次列表 /api/v1/upss/issue-list
    run_case('沉降页: 沉降图期次列表', '/api/v1/upss/issue-list', None, report_records,
             test_upss.test_get_issue_list, client)

    # 沉降页: 抽样点数据(protobuf) /api/v1/upss/samples, 循环 issue × dataType
    run_upss_samples(city, minLng, maxLng, minLat, maxLat, issues, report_records)


def run_upss_samples(city, minLng, maxLng, minLat, maxLat, issues, report_records):
    """沉降页: 抽样点数据 /api/v1/upss/samples (protobuf), 循环 issue × dataType

    响应为二进制 protobuf(SubsidencePointStream, lng/lat/val 等长数组), 解析后按抽样点数判空;
    val 全为 0 也视为无有效数据(服务端空值填 0)。原始 bin 和解析 csv 保存到当前响应目录。
    """
    tag = '沉降页: 抽样点数据'  # 该接口所在模块无内部 title 字符串
    path = '/api/v1/upss/samples'
    print(f'\n共获取到 {len(issues)} 个期次, 开始循环测试抽样点数据(issue × 3种dataType)...\n')
    for issue in issues:
        for data_type in ('subsidence', 'gradient', 'velocity'):
            params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat,
                      'issue': issue, 'dataType': data_type}

            # 1. 请求(该接口用 requests 直连, 错误抛异常, 这里分类捕获)
            try:
                body = upss_samples.fetch_samples(config.host, params, config.app_key, config.app_secret, timeout=config.timeout)
                reason = ''
            except requests.exceptions.Timeout:
                reason = f'请求超时(超过{config.timeout}s)'
            except requests.exceptions.ConnectionError:
                reason = '调用失败(无响应: 连接失败或HTTP状态码非200)'
            except RuntimeError as e:  # fetch_samples 对 HTTP 非200 抛 RuntimeError
                reason = f'调用失败({str(e)[:200]})'
            if reason:
                print(f'[FAILED] {tag} | GET {path} | issue={issue} dataType={data_type} | 原因: {reason}')
                report_records.append({'method': 'GET', 'tag': tag, 'path': path, 'params': params, 'reason': reason})
                continue

            # 2. 解析 protobuf
            try:
                stream = upss_samples.parse(body)
            except Exception as e:
                reason = f'protobuf 解析失败({str(e)[:200]})'
                print(f'[FAILED] {tag} | GET {path} | issue={issue} dataType={data_type} | 原因: {reason}')
                report_records.append({'method': 'GET', 'tag': tag, 'path': path, 'params': params, 'reason': reason})
                continue

            # 3. 空数据判定: 抽样点数为0, 或 val 全为0(服务端空值填0)
            n = len(stream.lng)
            print(f'[SUCCESS] {tag} | GET {path} | issue={issue} dataType={data_type} | 抽样点数: {n}')
            if n == 0 or all(v == 0.0 for v in stream.val):
                print(f'[空数据提示] {tag}: issue={issue} dataType={data_type} 返回数据为空或为0, 请确认该期次是否有数据')
                report_records.append({'method': 'GET', 'tag': tag, 'path': path, 'params': params, 'reason': '返回数据为空或为0'})

            # 4. 保存原始二进制和解析后的 csv 到当前响应目录(沉降_<城市>_<时间段>/)
            Path(os.path.join(config.response_dir, f'samples_{issue}_{data_type}.bin')).write_bytes(body)
            upss_samples.save_csv(stream, os.path.join(config.response_dir, f'samples_{issue}_{data_type}.csv'))


def run_upns_a(client, city, startTime, endTime, report_records):
    """降水页: 按 test_upns_a.py __main__ 执行 3.7.1~3.7.9 共 9 个接口"""
    print(f'\n========== 降水页 - {city} ({ts_str(startTime)} ~ {ts_str(endTime)}) ==========')
    set_response_dir(f'降水_{city}_{range_str(startTime, endTime)}')
    minLng, maxLng, minLat, maxLat = loc_list[city]
    bbox_params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat}
    time_params = {'startTime': startTime, 'endTime': endTime, **bbox_params}

    # 降水页: 模块概览 /api/v1/upns/overview
    run_case('降水页: 模块概览', '/api/v1/upns/overview', None, report_records,
             test_upns_a.test_get_overview, client)
    # 降水页: 风险评估 /api/v1/upns/risk
    run_case('降水页: 风险评估', '/api/v1/upns/risk', None, report_records,
             test_upns_a.test_get_risk, client)
    # 降水页: 监测站点列表 /api/v1/upns/stations, 站点编码服务于 3.7.7/3.7.8
    resp, station_codes = run_case('降水页: 监测站点列表', '/api/v1/upns/stations', {'pageNum': 1, 'pageSize': 20, **bbox_params}, report_records,
                                   test_upns_a.test_get_stations, client, minLng, maxLng, minLat, maxLat)
    # 降水页: 预警信息列表 /api/v1/upns/warnings
    run_case('降水页: 预警信息列表', '/api/v1/upns/warnings', time_params, report_records,
             test_upns_a.test_get_warnings, client, startTime, endTime, minLng, maxLng, minLat, maxLat)
    # 降水页: 过去一小时降雨量统计 /api/v1/upns/statistics/rain/now
    run_case('降水页: 过去一小时降雨量统计', '/api/v1/upns/statistics/rain/now', bbox_params, report_records,
             test_upns_a.test_get_rain_statistics_now, client, minLng, maxLng, minLat, maxLat)
    # 降水页: 当前大气可降水量统计 /api/v1/upns/statistics/pwv/now
    run_case('降水页: 当前大气可降水量统计', '/api/v1/upns/statistics/pwv/now', bbox_params, report_records,
             test_upns_a.test_get_pwv_statistics_now, client, minLng, maxLng, minLat, maxLat)
    # 降水页: 过去1小时降水量前五地区 /api/v1/upns/last1hour_rain_top5
    run_case('降水页: 过去1小时降水量前五地区', '/api/v1/upns/last1hour_rain_top5', bbox_params, report_records,
             test_upns_a.test_get_last1hour_rain_top5, client, minLng, maxLng, minLat, maxLat)
    # 降水页: 当前大气可降水量前五地区 /api/v1/upns/last1hour_pwv_top5
    run_case('降水页: 当前大气可降水量前五地区', '/api/v1/upns/last1hour_pwv_top5', bbox_params, report_records,
             test_upns_a.test_get_last1hour_pwv_top5, client, minLng, maxLng, minLat, maxLat)

    # 循环每个站点: 单站实时数据 + 单站历史趋势
    if station_codes:
        print(f'\n共获取到 {len(station_codes)} 个降水监测站, 开始测试单站接口。\n')
        # 单站历史趋势的请求参数(与 test_upns_a.test_get_station_history 内部一致)
        history_params = {
            'metrics': 'temperature,humidity,rain,windSpeed,windDirection,pressure,pwv',
            'interval': '1h',
            'startTime': startTime,
            'endTime': endTime,
        }
        for code in station_codes:
            # 降水页: 单站实时数据 /api/v1/upns/stations/{code}/realtime
            run_case('降水页: 单站实时数据', f'/api/v1/upns/stations/{code}/realtime', None, report_records,
                     test_upns_a.test_get_station_realtime, client, code)
            # 降水页: 单站历史趋势 /api/v1/upns/stations/{code}/history
            run_case('降水页: 单站历史趋势', f'/api/v1/upns/stations/{code}/history', history_params, report_records,
                     test_upns_a.test_get_station_history, client, startTime, endTime, code)
    else:
        print('\n站点列表未返回 stationCode, 跳过单站接口 3.7.7/3.7.8。\n')




def run_upns_w(client, city, startTime, endTime, report_records):
    """降水页: 降雨图层格网数据 /api/v1/upns/precipitation/layers

    数据量大, 区间模式(观测图层)用短时间窗口; 预测模式不消耗时间区间。
    """
    print(f'\n========== 降水页(降雨图层) - {city} ({ts_str(startTime)} ~ {ts_str(endTime)}) ==========')
    set_response_dir(f'降水图层_{city}_{range_str(startTime, endTime)}')
    minLng, maxLng, minLat, maxLat = loc_list[city]
    bbox_params = {'minLng': minLng, 'maxLng': maxLng, 'minLat': minLat, 'maxLat': maxLat}
    time_params = {'startTime': startTime, 'endTime': endTime, **bbox_params}

    # 4 个实时观测图层使用区间模式
    for layer, layer_name in test_upns_w.OBSERVATION_LAYERS:
        print(f'\n正在测试观测图层: {layer_name}({layer})')
        run_case('降水页: 降雨图层格网数据', '/api/v1/upns/precipitation/layers', {'layer': layer, **time_params}, report_records,
                 test_upns_w.test_get_precipitation_layers, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
                 layer=layer, group_name=test_upns_w.groupName_file)

    # LSTM 测试 1 小时; CONVLSTM 分别测试 1 小时和 2 小时
    for layer, layer_name, offset in test_upns_w.FORECAST_LAYER_CASES:
        print(f'\n正在测试预测图层: {layer_name}({layer}), {offset}分钟后')
        run_case('降水页: 降雨图层格网数据', '/api/v1/upns/precipitation/layers',
                 {'layer': layer, 'forecastOffsetMinutes': offset, **bbox_params}, report_records,
                 test_upns_w.test_get_precipitation_layers, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
                 layer=layer, forecast_offset_minutes=offset, group_name=test_upns_w.groupName_file)

    # 降水页: 大气可降水量(每小时)插值图层 /api/v1/upns/layers/pwv-hourly
    run_case('降水页: 大气可降水量（每小时）', '/api/v1/upns/layers/pwv-hourly', time_params, report_records,
             test_upns_w.test_get_pwv_hourly_layer, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
             group_name=test_upns_w.groupName_file)
    # 降水页: 气温插值图层 /api/v1/upns/layers/temperature
    run_case('降水页: 气温图', '/api/v1/upns/layers/temperature', time_params, report_records,
             test_upns_w.test_get_temperature_layer, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
             group_name=test_upns_w.groupName_file)
    # 降水页: 湿度插值图层 /api/v1/upns/layers/humidity
    run_case('降水页: 湿度图', '/api/v1/upns/layers/humidity', time_params, report_records,
             test_upns_w.test_get_humidity_layer, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
             group_name=test_upns_w.groupName_file)
    # 降水页: 气压插值图层 /api/v1/upns/layers/pressure
    run_case('降水页: 气压图', '/api/v1/upns/layers/pressure', time_params, report_records,
             test_upns_w.test_get_pressure_layer, client, startTime, endTime, minLng, maxLng, minLat, maxLat,
             group_name=test_upns_w.groupName_file)


if __name__ == '__main__':
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)
    start_dt = datetime.now()  # 测试运行时间, 写入报告开头
    report_records = []        # 问题接口记录, 最终写入 report.md

    # 收到 SIGTERM(外部停止任务)时退出, finally 仍会写出当前报告
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))

    try:
        # 形变页: 重庆 2026.5.1-2026.8.20
        run_udmds(client, '重庆', ts(2026, 7, 1), ts(2026, 8, 20, end=True), report_records)

        # 燃气页: 重庆 2019.9.1-2019.9.30 / 北京 2026.5.1-2026.5.30 / 株洲 2026.5.1-2026.5.30
        run_unga(client, '重庆', ts(2019, 9, 1), ts(2019, 9, 30, end=True), report_records)
        run_unga(client, '北京', ts(2026, 5, 1), ts(2026, 5, 30, end=True), report_records)
        for year in range(2026, 2017, -1):
            for month in range(12, 0, -1):
                run_unga(client, '株洲', ts(year, month, 1), ts(year, month, 28, end=True), report_records)

        # 沉降页: 重庆 2018.1.1-2025.12.31 / 株洲 2022.1.1-2025.12.31
        for year in range(2026, 2017, -1):
            for month in range(12, 0, -1):
                run_upss(client, '重庆', ts(year, month, 1), ts(year, month, 28, end=True), report_records)
        run_upss(client, '株洲', ts(2022, 1, 1), ts(2025, 12, 31, end=True), report_records)

        # # 降水页: 重庆/北京 2026.5.1-2026.8.20 (3.7.1~3.7.9)
        # # 降雨图层数据量大, 区间模式统一用短窗口 2026.8.13 03:00-03:40
        for city in ('重庆', '北京'):
            for year in range(2026, 2027, 1):
                for month in range(8, 9, 1):
                    for day in range(13, 14, 1):
                        run_upns_a(client, city, ts(year, month, day), ts(year, month, day, end=True), report_records)
            # run_upns_w(client, city, ts(2026, 8, 12, 0, 0), ts(2026, 8, 13, 0, 0), report_records)
    finally:
        # 中途停止也落一份当前已记录的问题报告
        write_report(start_dt, report_records)

    print(f'\n测试完成, 响应已保存到 {RESPONSE_ROOT}/')
