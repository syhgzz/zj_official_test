# -*- coding: utf-8 -*-
"""
形变安全监测(UDMDS)数据导出
输出: 形变数据.xlsx
Sheet: 监测点信息 / 位移监测数据
"""
import sys
import os
import time
from datetime import datetime
from calendar import monthrange
from openpyxl import Workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from config.config import config

OUTPUT = os.path.join(os.path.dirname(__file__), '..', '形变数据.xlsx')
PAGE_SIZE = 2000
DELAY = 0.15


def monthly_ranges(start_year, end_year):
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            s = datetime(year, month, 1, 0, 0, 0)
            e = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
            yield int(s.timestamp()) * 1000, int(e.timestamp()) * 1000


def ts_to_str(ms):
    try:
        return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


def paginate(client, path, params, list_key):
    items = []
    page = 1
    while True:
        p = {**params, 'pageNum': page, 'pageSize': PAGE_SIZE}
        res = client.request('GET', path, params=p)
        if not res or res.get('code') != 200:
            break
        data = res.get('data', {})
        batch = data.get(list_key, [])
        if isinstance(batch, list):
            items.extend(batch)
        total = data.get('total', 0)
        if page * PAGE_SIZE >= (total or 1):
            break
        page += 1
        time.sleep(DELAY)
    return items


def write_sheet(ws, rows, fieldnames):
    ws.append(list(fieldnames))
    for r in rows:
        ws.append([r.get(k, '') for k in fieldnames])


def main():
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)
    wb = Workbook()

    # Sheet 1: 监测点信息
    ws_points = wb.active
    ws_points.title = '监测点信息'

    # Sheet 2: 位移监测数据
    ws_history = wb.create_sheet('位移监测数据')

    codes_seen = {}
    history_rows = []

    print("=" * 60)
    print("形变数据导出 (UDMDS)")
    print("=" * 60)

    for sm, em in monthly_ranges(2018, 2026):
        label = datetime.fromtimestamp(sm / 1000).strftime('%Y-%m')
        print(f"[{label}] 获取监测点... ", end='', flush=True)
        points = paginate(client, '/api/v1/udmds/points',
                          {'startTime': sm, 'endTime': em}, 'points')
        new_count = 0
        for pt in points:
            code = pt.get('pointCode')
            if code and code not in codes_seen:
                loc = pt.get('location', {})
                codes_seen[code] = {
                    'pointCode': code,
                    'projectCode': pt.get('projectCode', ''),
                    'projectName': pt.get('projectName', ''),
                    'deviceType': pt.get('deviceType', ''),
                    '经度': loc.get('longitude', ''),
                    '纬度': loc.get('latitude', ''),
                    '高程': loc.get('altitude', ''),
                    '状态': pt.get('status', ''),
                    'regionCode': pt.get('regionCode', ''),
                    'regionName': pt.get('regionName', ''),
                    'lastUpdateTime': ts_to_str(pt.get('lastUpdateTime')),
                }
                new_count += 1
        print(f"{len(points)} 个, 新 {new_count} 个")

    point_codes = sorted(codes_seen.keys())
    print(f"\n累计 {len(point_codes)} 个监测点, 获取历史数据...")

    for idx, code in enumerate(point_codes, 1):
        print(f"[{idx}/{len(point_codes)}] {code}")
        for sm, em in monthly_ranges(2018, 2026):
            path = f'/api/v1/udmds/points/{code}/history'
            res = client.request('GET', path, params={
                'interval': '1d',
                'startTime': sm,
                'endTime': em,
            })
            time.sleep(DELAY)
            if not res or res.get('code') != 200:
                continue
            data = res.get('data', {})
            records = (data.get('history') or data.get('records')
                       or data.get('data') or [])
            if isinstance(records, dict):
                records = [records]
            if not isinstance(records, list):
                continue
            for rec in records:
                if not isinstance(rec, dict):
                    continue
                row = {'pointCode': code}
                for k, v in rec.items():
                    if k in ('time', 'timestamp', 'dataTime', 'data_date',
                             'detectionTime', 'startTime', 'endTime'):
                        row['数据时间'] = ts_to_str(v) if isinstance(v, (int, float)) else v
                    elif isinstance(v, (int, float)):
                        row[k] = v
                    elif isinstance(v, str):
                        row[k] = v
                history_rows.append(row)
        time.sleep(DELAY)

    # 写入监测点信息 sheet
    pt_fields = ['pointCode', 'projectCode', 'projectName', 'deviceType',
                  '经度', '纬度', '高程', '状态', 'regionCode', 'regionName',
                  'lastUpdateTime']
    write_sheet(ws_points, list(codes_seen.values()), pt_fields)

    # 写入位移监测数据 sheet
    hist_fields = []
    hist_seen = set()
    for r in history_rows:
        for k in r:
            if k not in hist_seen:
                hist_seen.add(k)
                hist_fields.append(k)
    write_sheet(ws_history, history_rows, hist_fields)

    wb.save(OUTPUT)
    print(f"\n完成! Sheet1 {len(codes_seen)} 行, Sheet2 {len(history_rows)} 行")
    print(f"保存至: {OUTPUT}")


if __name__ == '__main__':
    main()
