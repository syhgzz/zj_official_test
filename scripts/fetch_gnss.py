# -*- coding: utf-8 -*-
"""
北斗基准站(GNSS-Device)数据导出
输出: 北斗基准站数据.xlsx
Sheet: 基准站信息(stations + realtime摘要合并) / 卫星信号(realtime.signals)
"""
import sys
import os
import time
from datetime import datetime
from openpyxl import Workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.api_client import APIClient
from config.config import config

OUTPUT = os.path.join(os.path.dirname(__file__), '..', '北斗基准站数据.xlsx')
PAGE_SIZE = 2000
DELAY = 0.15


def ts_to_str(ms):
    try:
        return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


def write_sheet(ws, rows, fieldnames):
    ws.append(list(fieldnames))
    for r in rows:
        ws.append([r.get(k, '') for k in fieldnames])


def main():
    client = APIClient(config.host, config.app_key, config.app_secret, config.timeout)

    station_rows = []
    signal_rows = []

    print("=" * 60)
    print("北斗基准站数据导出 (GNSS-Device)")
    print("=" * 60)

    # 1. 分页获取站点列表
    print("获取站点列表...")
    stations = []
    page = 1
    while True:
        params = {'pageNum': page, 'pageSize': PAGE_SIZE}
        res = client.request('GET', '/api/v1/gnss-device/stations', params=params)
        if not res or res.get('code') != 200:
            break
        data = res.get('data', {})
        batch = data.get('stations', [])
        stations.extend(batch)
        total = data.get('total', 0)
        if page * PAGE_SIZE >= (total or 1):
            break
        page += 1
        time.sleep(DELAY)
    print(f"  共 {len(stations)} 个站点")

    # 2. 对每个站点获取实时数据
    for idx, st in enumerate(stations, 1):
        code = st.get('stationCode', '')
        if not code:
            continue

        print(f"[{idx}/{len(stations)}] {code} ", end='', flush=True)

        # 从站点列表提取基础信息
        base = {
            'stationCode': code,
            'stationName': st.get('stationName', ''),
            '经度': st.get('longitude'),
            '纬度': st.get('latitude'),
            '高程(m)': st.get('alt'),
            '站点状态': st.get('status'),
            '更新时间': ts_to_str(st.get('lastUpdateTime')),
            '延迟(ms)': st.get('delay'),
        }
        sc = st.get('satelliteCount', {})
        if isinstance(sc, dict):
            base['北斗卫星数'] = sc.get('bdCount')
        sq = st.get('signalQuality', {})
        if isinstance(sq, dict):
            base['信号合格'] = sq.get('qualified')
            base['平均信噪比'] = sq.get('avgNoiseRatio')

        # 获取实时数据
        path = f'/api/v1/gnss-device/stations/{code}/realtime'
        res = client.request('GET', path, params={})
        time.sleep(DELAY)

        if not res or res.get('code') != 200:
            print("(失败)")
            station_rows.append(base)
            continue

        rdata = res.get('data', {})

        # 合并实时数据中的摘要信息
        base['数据时间'] = ts_to_str(rdata.get('dataTime'))
        rsc = rdata.get('satelliteCount', {})
        if isinstance(rsc, dict):
            base['北斗卫星数'] = rsc.get('bdCount')
        rsq = rdata.get('signalQuality', {})
        if isinstance(rsq, dict):
            base['信号合格'] = rsq.get('qualified')
            base['平均信噪比(dB)'] = rsq.get('avgNoiseRatio')
            base['最小信噪比(dB)'] = rsq.get('minNoiseRatio')

        station_rows.append(base)

        # 卫星信号数据
        signals = rdata.get('signals', [])
        print(f"{len(signals)} 颗卫星")
        for sig in signals:
            if not isinstance(sig, dict):
                continue
            signal_rows.append({
                'stationCode': code,
                '卫星编号': sig.get('satelliteNumber'),
                '方位角': sig.get('azimuth'),
                '高度角': sig.get('heightAngle'),
                'L1信噪比': sig.get('l1NoiseRatio'),
                'L2信噪比': sig.get('l2NoiseRatio'),
                'L3信噪比': sig.get('l3NoiseRatio'),
                'L4信噪比': sig.get('l4NoiseRatio'),
                'L5信噪比': sig.get('l5NoiseRatio'),
            })

    # 写入 XLSX
    wb = Workbook()

    ws_station = wb.active
    ws_station.title = '基准站信息'
    station_fields = ['stationCode', 'stationName', '经度', '纬度', '高程(m)',
                      '北斗卫星数', '站点状态', '更新时间', '延迟(ms)',
                      '信号合格', '平均信噪比(dB)', '最小信噪比(dB)', '数据时间']
    write_sheet(ws_station, station_rows, station_fields)

    ws_signal = wb.create_sheet('卫星信号')
    signal_fields = ['stationCode', '卫星编号', '方位角', '高度角',
                     'L1信噪比', 'L2信噪比', 'L3信噪比', 'L4信噪比', 'L5信噪比']
    write_sheet(ws_signal, signal_rows, signal_fields)

    wb.save(OUTPUT)
    print(f"\n完成! Sheet1 {len(station_rows)} 行, Sheet2 {len(signal_rows)} 行")
    print(f"保存至: {OUTPUT}")


if __name__ == '__main__':
    main()
