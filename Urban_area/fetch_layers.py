# -*- coding: utf-8 -*-
"""
fetch_layers.py —— 拉取 /api/v1/upns/precipitation/layers 并缓存原始 json

用法：
    uv run python -m precipitation_xunteng.fetch_layers --layers XTSKPWV XTSKJSXS \
        --date 2026-08-28 --hour-start 0 --hour-end 12
原始响应保存到 data/raw/，文件名：<layer>_<date>_<HH>-<HH>.json
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config import config
from lib.api_client import APIClient

from Urban_area.layer_config import LAYERS

RAW_DIR = os.path.join(os.path.dirname(__file__), 'data', 'raw')

ENDPOINT = '/api/v1/upns/precipitation/layers'
# 注意：/api/v1/precipitation/layers（无 upns 前缀）在本服务器返回 500


def ms(dt):
    return int(dt.timestamp()) * 1000


def fetch_layer(client, layer, date_str, hour_start, hour_end, bbox):
    """
    拉取单个图层并缓存，返回 (data_dict, raw_path)。

    时间窗 = hour_start:00:00 ~ hour_end:00:00（含 hour_end 整点帧）；
    默认 00~12 即 8-28 00:00~12:00，不会多取 12:00 之后的帧。
    """
    start = ms(datetime(*map(int, date_str.split('-')), hour_start, 0, 0))
    end = ms(datetime(*map(int, date_str.split('-')), hour_end, 0, 0))
    params = {
        'layer': layer,
        'startTime': start,
        'endTime': end,
        'minLng': bbox[0],
        'maxLng': bbox[1],
        'minLat': bbox[2],
        'maxLat': bbox[3],
    }
    resp = client.request('GET', ENDPOINT, params=params)
    if not resp or resp.get('code') != 200:
        raise RuntimeError(f'图层 {layer} 请求失败: 响应={resp}')
    os.makedirs(RAW_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, f'{layer}_{date_str}_{hour_start:02d}-{hour_end:02d}.json')
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(resp, f, ensure_ascii=False)
    return resp['data'], raw_path


def summarize(data, layer):
    """打印图层概览。"""
    meta = LAYERS.get(layer, {})
    frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
    print(f"[{layer}] {meta.get('name', '')} 单位={data.get('unit')} "
          f"cols/rows={data.get('cols')}/{data.get('rows')} 帧数={len(frames)}")
    print(f"  bbox={data.get('bbox')} groupName={data.get('groupName')} "
          f"groups={[g.get('groupName') for g in data.get('groups', [])]}")
    if frames:
        print(f"  时刻范围: {datetime.fromtimestamp(frames[0]/1000):%Y-%m-%d %H:%M}"
              f" ~ {datetime.fromtimestamp(frames[-1]/1000):%Y-%m-%d %H:%M}")
    return frames


def main():
    ap = argparse.ArgumentParser(description='拉取降水图层格网数据并缓存')
    ap.add_argument('--layers', nargs='+', default=list(LAYERS.keys()))
    ap.add_argument('--date', default='2026-08-28')
    ap.add_argument('--hour-start', type=int, default=0)
    ap.add_argument('--hour-end', type=int, default=12)
    ap.add_argument('--bbox', nargs=4, type=float, default=[115.814, 116.816, 39.637, 40.423],
                    help='minLng maxLng minLat maxLat（默认北京 loc_list）')
    args = ap.parse_args()

    client = APIClient(config.host, config.app_key, config.app_secret, 120)
    for layer in args.layers:
        data, path = fetch_layer(client, layer, args.date, args.hour_start, args.hour_end, args.bbox)
        print(f'已缓存: {path}')
        summarize(data, layer)


if __name__ == '__main__':
    main()
