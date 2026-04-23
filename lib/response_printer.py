# -*- coding: utf-8 -*-
"""
响应数据打印与统计工具
"""
import json
import os
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


_CAPTURE_STATE: Dict[str, Any] = {
    'enabled': False,
    'response_dir': 'responses',
    'api_log_path': '',
    'planned_total': 0,
    'module_plan': [],
    'started_at': None,
    'global_index': 0,
    'current_module_key': '',
    'current_module_name': '',
    'current_module_total': 0,
    'current_module_index': 0,
    'records': [],
}


def _truncate_text(value: Any, max_len: int = 180) -> str:
    """将任意值转换为单行短文本，便于控制台与日志展示。"""
    text = str(value).replace('\n', ' ').replace('\r', ' ').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + '...'


def _extract_message(response: Dict[str, Any]) -> str:
    """优先提取常见消息字段。"""
    for key in ('msg', 'message', 'errMsg', 'errmsg', 'errorMsg'):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ''


def _contains_error_semantics(message: str) -> bool:
    """通过关键词判断消息语义是否为错误。"""
    if not message:
        return False

    lowered = message.lower()
    success_keywords = ('成功', 'ok', 'success')
    error_keywords = (
        '失败', '错误', '异常', '超时',
        'error', 'failed', 'forbidden',
        'unauthorized', 'invalid', 'denied', 'timeout'
    )

    if any(word in lowered for word in success_keywords):
        return False
    return any(word in lowered for word in error_keywords)


def _detect_error_payload(response: Dict[str, Any]) -> str:
    """检测响应中显式报错字段。"""
    for key in ('error', 'errors', 'err', 'errMsg', 'errmsg', 'errorMsg', 'exception', 'traceback'):
        if key not in response:
            continue
        value = response.get(key)
        if value not in (None, '', [], {}, 0, False):
            return f"{key}={_truncate_text(value)}"

    if response.get('success') is False:
        return 'success=false'

    status = response.get('status')
    if isinstance(status, str) and status.lower() in ('error', 'failed', 'fail', 'exception'):
        return f"status={status}"

    message = _extract_message(response)
    if _contains_error_semantics(message):
        return message

    return ''


def _evaluate_response(response: Any) -> Tuple[bool, str, Any]:
    """
    统一成功判定：请求成功 + code=200 + 响应中无报错信息。

    Returns:
        (是否成功, 失败原因, 业务code)
    """
    if response is None:
        return False, '请求失败或无响应', None

    if not isinstance(response, dict):
        return False, f"响应格式异常: {type(response).__name__}", None

    if 'code' not in response:
        return False, '响应缺少code字段', None

    code = response.get('code')
    normalized_code = code
    if isinstance(code, str) and code.isdigit():
        normalized_code = int(code)

    if normalized_code != 200:
        message = _extract_message(response)
        if message:
            return False, f"业务失败(code={code}, msg={message})", code
        return False, f"业务失败(code={code})", code

    error_payload = _detect_error_payload(response)
    if error_payload:
        return False, f"响应包含报错信息: {error_payload}", code

    return True, '', code


def _format_progress(module_key: str, global_index: int, planned_total: int, module_index: int, module_total: int) -> str:
    """格式化双层进度显示。"""
    total_part = f"{global_index}/{planned_total}" if planned_total else str(global_index)
    module_part = f"{module_index}/{module_total}" if module_total else str(module_index)
    return f"[总 {total_part}] [{module_key} {module_part}]"


def _append_api_log_line(line: str):
    """将单接口结果追加写入日志文件。"""
    log_path = _CAPTURE_STATE.get('api_log_path')
    if not log_path:
        return

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def _sanitize_sequence(value: Any) -> str:
    """将序号清洗为可用于文件名的文本。"""
    text = str(value or '').strip()
    if not text:
        return ''

    safe_chars = []
    for ch in text:
        if ch.isalnum() or ch in ('.', '_', '-'):
            safe_chars.append(ch)
        else:
            safe_chars.append('_')

    return ''.join(safe_chars).strip('_')


def _sanitize_path_for_filename(path_value: Any) -> str:
    """将接口路径转换为文件名安全片段。"""
    text = str(path_value or '').strip()
    if not text:
        return ''

    text = text.split('?', 1)[0].strip().strip('/')
    if not text:
        return 'root'

    safe = text
    for old, new in (('/', '_'), ('-', '_'), ('{', ''), ('}', ''), (' ', '_')):
        safe = safe.replace(old, new)

    while '__' in safe:
        safe = safe.replace('__', '_')

    return safe.strip('_')


def start_stats_capture(
    response_dir: str = 'responses',
    planned_total: int = 0,
    module_plan: Optional[List[Dict[str, Any]]] = None,
    started_at: Optional[datetime] = None,
    api_log_filename: str = 'api_results.md'
):
    """
    开始采集测试结果。

    Args:
        response_dir: 结果输出目录
        planned_total: 计划接口总数
        module_plan: 模块计划信息列表
        started_at: 测试开始时间
        api_log_filename: 单接口结果日志文件名
    """
    started_at = started_at or datetime.now()
    os.makedirs(response_dir, exist_ok=True)

    api_log_path = os.path.join(response_dir, api_log_filename)

    _CAPTURE_STATE.update({
        'enabled': True,
        'response_dir': response_dir,
        'api_log_path': api_log_path,
        'planned_total': int(planned_total or 0),
        'module_plan': deepcopy(module_plan) if module_plan else [],
        'started_at': started_at,
        'global_index': 0,
        'current_module_key': '',
        'current_module_name': '',
        'current_module_total': 0,
        'current_module_index': 0,
        'records': [],
    })

    with open(api_log_path, 'w', encoding='utf-8') as f:
        f.write('# API单接口测试结果\n\n')
        f.write(f"- 开始时间: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        if planned_total:
            f.write(f"- 计划接口总数: {planned_total}\n")
        f.write('\n')


def stop_stats_capture():
    """停止采集。"""
    _CAPTURE_STATE['enabled'] = False


def set_module_context(module_key: str, module_name: str, module_total: int = 0):
    """设置当前模块上下文，用于分组展示和模块内进度。"""
    _CAPTURE_STATE['current_module_key'] = module_key
    _CAPTURE_STATE['current_module_name'] = module_name
    _CAPTURE_STATE['current_module_total'] = int(module_total or 0)
    _CAPTURE_STATE['current_module_index'] = 0


def get_stats_records() -> List[Dict[str, Any]]:
    """获取采集到的单接口记录副本。"""
    return deepcopy(_CAPTURE_STATE.get('records', []))


def build_summary_markdown(end_time: Optional[datetime] = None) -> str:
    """构建统计汇总Markdown文本。"""
    end_time = end_time or datetime.now()
    started_at = _CAPTURE_STATE.get('started_at') or end_time

    records: List[Dict[str, Any]] = _CAPTURE_STATE.get('records', [])
    planned_total = int(_CAPTURE_STATE.get('planned_total') or 0)
    module_plan = _CAPTURE_STATE.get('module_plan') or []

    total_count = len(records)
    success_count = sum(1 for item in records if item.get('success'))
    failed_count = total_count - success_count
    success_rate = (success_count / total_count * 100.0) if total_count else 0.0

    module_stats: Dict[str, Dict[str, Any]] = {}
    module_order: List[str] = []
    for item in records:
        module_key = item.get('module_key') or 'unknown'
        module_name = item.get('module_name') or module_key

        if module_key not in module_stats:
            module_stats[module_key] = {
                'module_name': module_name,
                'total': 0,
                'success': 0,
                'failed': 0,
            }
            module_order.append(module_key)

        module_stats[module_key]['total'] += 1
        if item.get('success'):
            module_stats[module_key]['success'] += 1
        else:
            module_stats[module_key]['failed'] += 1

    for item in module_plan:
        module_key = item.get('module_key')
        module_name = item.get('module_name') or module_key
        if not module_key:
            continue
        if module_key not in module_stats:
            module_stats[module_key] = {
                'module_name': module_name,
                'total': 0,
                'success': 0,
                'failed': 0,
            }
        if module_key not in module_order:
            module_order.append(module_key)

    duration = (end_time - started_at).total_seconds()

    lines = [
        '# API测试统计汇总',
        '',
        f"- 开始时间: {started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总耗时: {duration:.2f}秒",
        '',
        '## 总体统计',
    ]

    if planned_total:
        lines.append(f"- 计划接口总数: {planned_total}")

    lines.extend([
        f"- 共统计接口: {total_count}",
        f"- 成功: {success_count}",
        f"- 报错: {failed_count}",
        f"- 成功率: {success_rate:.2f}%",
        '',
        '## 模块统计',
        '| 模块 | 接口数 | 成功 | 报错 |',
        '| --- | ---: | ---: | ---: |',
    ])

    if module_order:
        for module_key in module_order:
            stat = module_stats[module_key]
            display_name = f"{stat['module_name']} ({module_key})"
            lines.append(
                f"| {display_name} | {stat['total']} | {stat['success']} | {stat['failed']} |"
            )
    else:
        lines.append('| - | 0 | 0 | 0 |')

    lines.extend(['', '## 错误接口列表'])

    failed_items = [item for item in records if not item.get('success')]
    if failed_items:
        for index, item in enumerate(failed_items, 1):
            module_key = item.get('module_key') or 'unknown'
            api_name = item.get('api_name') or '-'
            method = item.get('method') or '-'
            path = item.get('path') or '-'
            reason = item.get('reason') or '未知错误'
            lines.append(
                f"{index}. [{module_key}] {api_name} ({method} {path}) - {_truncate_text(reason)}"
            )
    else:
        lines.append('- 无')

    api_log_path = _CAPTURE_STATE.get('api_log_path')
    if api_log_path:
        lines.extend(['', '## 接口明细文件', f"- {os.path.basename(api_log_path)}"])

    return '\n'.join(lines) + '\n'


def save_summary_to_file(
    filename: str = 'summary.md',
    end_time: Optional[datetime] = None
) -> Tuple[str, str]:
    """
    保存统计汇总Markdown。

    Returns:
        (汇总文件路径, 汇总文本)
    """
    response_dir = _CAPTURE_STATE.get('response_dir') or 'responses'
    os.makedirs(response_dir, exist_ok=True)

    summary_text = build_summary_markdown(end_time=end_time)
    summary_path = os.path.join(response_dir, filename)

    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)

    return summary_path, summary_text


def print_response(
    api_name: str,
    method: str,
    path: str,
    response: Any,
    verbose: bool = True,
    number: str = '',
    title: str = ''
):
    """
    输出单接口测试结果（标准流简洁行 + 文件日志）

    Args:
        api_name: API名称
        method: HTTP方法
        path: API路径
        response: 响应数据
        verbose: 保留参数,兼容旧调用
        number: 接口编号(如 3.1.1)
        title: 接口标题(如 模块概览)
    """
    _ = verbose
    success, reason, code = _evaluate_response(response)
    now = datetime.now()

    method = (method or '-').upper()
    path = path or '-'
    number = (number or '').strip()
    title = (title or '').strip()

    module_key = _CAPTURE_STATE.get('current_module_key') or 'unknown'
    module_name = _CAPTURE_STATE.get('current_module_name') or module_key
    global_index = 0
    module_index = 0
    global_total = 0
    module_total = 0

    if _CAPTURE_STATE.get('enabled'):
        _CAPTURE_STATE['global_index'] += 1
        _CAPTURE_STATE['current_module_index'] += 1

        global_index = _CAPTURE_STATE['global_index']
        module_index = _CAPTURE_STATE['current_module_index']
        global_total = _CAPTURE_STATE.get('planned_total') or 0
        module_total = _CAPTURE_STATE.get('current_module_total') or 0

    progress_prefix = ''
    if global_index:
        progress_prefix = _format_progress(module_key, global_index, global_total, module_index, module_total) + ' '

    status_text = 'SUCCESS' if success else 'FAILED'
    display_title = title or (api_name or '-').strip() or '-'
    number_prefix = f"[{number}] " if number else ''
    line = f"{progress_prefix}[{status_text}] {number_prefix}{display_title} | {method} {path}"
    if not success and reason:
        line += f" | 原因: {reason}"

    print(line)

    record = {
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S'),
        'module_key': module_key,
        'module_name': module_name,
        'api_name': api_name,
        'number': number,
        'title': display_title,
        'method': method,
        'path': path,
        'success': success,
        'reason': reason,
        'code': code,
        'global_index': global_index,
        'global_total': global_total,
        'module_index': module_index,
        'module_total': module_total,
    }

    if _CAPTURE_STATE.get('enabled'):
        _CAPTURE_STATE['records'].append(record)

        log_line = (
            f"- {record['timestamp']} "
            f"{_format_progress(module_key, global_index, global_total, module_index, module_total)} "
            f"[{status_text}] {number_prefix}{display_title} | {method} {path}"
        )
        if not success and reason:
            log_line += f" | 原因: {_truncate_text(reason)}"
        _append_api_log_line(log_line)


def save_response_to_file(
    api_name: str,
    response: Any,
    path: str,
    request_params: Optional[Dict[str, Any]],
    response_dir: str = 'responses',
    number: str = '',
    title: str = '',
):
    """
    保存响应到文件

    Args:
        api_name: API名称
        response: 响应数据
        path: 接口请求路径(由调用方传入)
        request_params: 请求参数(由调用方传入)
        response_dir: 保存目录
        number: 接口编号(由调用方传入)
        title: 接口标题(由调用方传入)
    """
    # 创建保存目录
    os.makedirs(response_dir, exist_ok=True)

    # 按“number_title_path”生成文件名，仅使用调用方显式参数。
    sequence = _sanitize_sequence(number)
    title_part = _sanitize_path_for_filename(title)
    path_part = _sanitize_path_for_filename(path)
    if not path_part:
        path_part = _sanitize_path_for_filename(api_name)

    filename_parts = [part for part in (sequence, title_part, path_part) if part]
    filename = f"{'_'.join(filename_parts)}.json" if filename_parts else 'response.json'

    filepath = os.path.join(response_dir, filename)

    # 按固定顺序写入: number -> title -> path -> request_params -> response
    payload = {
        'number': number,
        'title': title,
        'path': path,
        'request_params': request_params or {},
        'response': response,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
