# -*- coding: utf-8 -*-
"""
run_compare.py —— 讯腾降水图算法复现 + 与平台参考截图对照

流程
====
1. 拉取（或读缓存） /api/v1/upns/precipitation/layers 北京 2026-08-28 00:00~12:00
2. 取目标时刻（默认 12:00）帧，按讯腾算法(等值面填色+WGS84线性映射)渲染 256x256 PNG
3. 与 references/ 目录下的讯腾平台参考截图自动并排对比（按文件名关键字匹配图层）
4. 可选 --diff：用站点散点(104站历史值)复算 IDW 格网，与平台格网逐格对比(RMSE/相关系数)

用法
====
    uv run python -m precipitation_xunteng.run_compare                 # 默认两层+12:00
    uv run python -m precipitation_xunteng.run_compare --diff --idw-power 2
    uv run python -m precipitation_xunteng.run_compare --no-fetch      # 只用缓存
    uv run python -m precipitation_xunteng.run_compare --refs references --hour 12
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np

from config.config import config
from lib.api_client import APIClient

from Urban_area import eqs_algorithm as eqs
from Urban_area.fetch_layers import fetch_layer, ms
from Urban_area.layer_config import DEFAULT_LAYERS, LAYERS, layer_clip

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PACKAGE_DIR, 'data')
REF_DIR = os.path.join(PACKAGE_DIR, 'references')
OUT_DIR = os.path.join(PACKAGE_DIR, 'output')

IMG_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')


def load_cache(layer, date_str, hour_start, hour_end):
    path = os.path.join(DATA_DIR, 'raw', f'{layer}_{date_str}_{hour_start:02d}-{hour_end:02d}.json')
    if not os.path.exists(path):
        return None, path
    with open(path, encoding='utf-8') as f:
        resp = json.load(f)
    return resp['data'], path


def find_reference(ref_dir, layer):
    """按 ref_keywords 在参考截图目录中匹配图层对应截图。"""
    meta = LAYERS.get(layer, {})
    words = [w.lower() for w in meta.get('ref_keywords', [])]
    if not os.path.isdir(ref_dir):
        return None
    for fn in sorted(os.listdir(ref_dir)):
        if not fn.lower().endswith(IMG_EXTS):
            continue
        low = fn.lower()
        if any(w in low for w in words):
            return os.path.join(ref_dir, fn)
    return None


def station_series(client, code, metric, target_ms, cache_dir):
    """
    取单站历史时间序列（带本地缓存），返回 {'timestamps': [...], 'values': [...]} 或 None。
    缓存文件按 站点+指标 命名；若缓存未覆盖 target_ms 则重新拉取更宽的窗口。
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, f'hist_{code}_{metric}.json')
    cached = None
    if os.path.exists(cache):
        with open(cache, encoding='utf-8') as f:
            cached = json.load(f)
        stamps = cached.get('timestamps') or []
        if stamps and stamps[-1] >= target_ms - 60_000:
            return cached

    start = ms(datetime.fromtimestamp(target_ms / 1000, tz=None).replace(
        hour=0, minute=0, second=0, microsecond=0))
    resp = client.request(
        'GET', f'/api/v1/upns/stations/{code}/history',
        params={'metrics': metric, 'interval': '1h',
                'startTime': start, 'endTime': target_ms + 60_000})
    if not resp or resp.get('code') != 200:
        return cached
    data = resp.get('data') or {}
    series = data.get('timeSeries') or {}
    ts = {'timestamps': series.get('timestamps') or [],
          'values': series.get(metric) or []}
    if not ts['timestamps']:
        return cached
    with open(cache, 'w', encoding='utf-8') as f:
        json.dump(ts, f)
    return ts


def fetch_station_history(client, code, metric, target_ms, cache_dir):
    """拉取单站历史并返回 target_ms 最近时刻的指标值（带本地缓存）。"""
    ts = station_series(client, code, metric, target_ms, cache_dir)
    if not ts or not ts['timestamps']:
        return None
    idx = min(range(len(ts['timestamps'])),
              key=lambda i: abs(ts['timestamps'][i] - target_ms))
    values = ts['values']
    return values[idx] if idx < len(values) else None


def metric_history_has_values(client, stations, metric, target_ms, cache_dir):
    """探测站点历史接口该指标是否有值（前 3 站有任一非 null 即认为可用）。"""
    for s in stations[:3]:
        code = s.get('stationCode')
        if not code:
            continue
        v = fetch_station_history(client, code, metric, target_ms, cache_dir)
        if v is not None:
            return True
    return False


def build_scatter_history(client, stations, metric, target_ms, cache_dir):
    """按 txt 步骤 1 拼散点 jsonArray 语义 [[l,b,v],...]（历史时刻值）。"""
    train = []
    skipped = 0
    for i, s in enumerate(stations, 1):
        loc = s.get('location') or {}
        l, b = loc.get('longitude'), loc.get('latitude')
        if l is None or b is None:
            skipped += 1
            continue
        v = fetch_station_history(client, s.get('stationCode'), metric, target_ms, cache_dir)
        if v is None:
            skipped += 1
            continue
        train.append([float(l), float(b), float(v)])
        if i % 20 == 0:
            print(f'  历史散点: {i}/{len(stations)} 站 ...')
    if not train:
        raise ValueError('有效插值点为空（站点历史无该指标数据）')
    print(f'  有效散点 {len(train)} 个（跳过 {skipped} 站）')
    return np.asarray(train, dtype=float)


def render_compare_pair(layer, algo_png, ref_png, out_png, title):
    """左：参考截图；右：算法出图。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.image import imread

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    for ax, path, label in ((axes[0], ref_png, '讯腾平台截图(参考)'),
                            (axes[1], algo_png, '讯腾算法复现(本程序)')):
        img = imread(path)
        ax.imshow(img)
        ax.set_title(label, fontsize=12)
        ax.axis('off')
    fig.suptitle(title, fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def write_html(entries, html_path):
    rows = []
    for e in entries:
        ref_rel = (os.path.relpath(e['ref_png'], os.path.dirname(html_path))
                   if e.get('ref_png') and os.path.exists(e['ref_png']) else None)
        algo_rel = os.path.relpath(e['algo_png'], os.path.dirname(html_path))
        blocks = [f'<div style="font-weight:bold">算法复现</div>'
                  f'<img src="{algo_rel}" style="max-width:49%">']
        if ref_rel:
            blocks.insert(0, '<div style="font-weight:bold">讯腾平台截图</div>'
                            f'<img src="{ref_rel}" style="max-width:49%">')
        rows.append(
            f'<h2>{e["layer"]} - {e["name"]}（{e["time_str"]}，单位 {e["unit"]}）</h2>'
            f'<p>{e["summary"]}</p>'
            f'<div style="display:flex;gap:12px">{"".join(blocks)}</div><hr>'
        )
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>降水量图对照报告</title>'
            '</head><body><h1>讯腾降水量图算法复现对照</h1>' + ''.join(rows) + '</body></html>')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description='讯腾降水图算法复现与对照')
    ap.add_argument('--layers', nargs='+', default=DEFAULT_LAYERS)
    ap.add_argument('--date', default='2026-08-28')
    ap.add_argument('--hour', type=int, default=12)
    ap.add_argument('--hour-range', nargs=2, type=int, default=[0, 12], metavar=('H_START', 'H_END'))
    ap.add_argument('--bbox', nargs=4, type=float, default=[115.814, 116.816, 39.637, 40.423],
                    help='minLng maxLng minLat maxLat（默认北京 loc_list）')
    ap.add_argument('--no-fetch', action='store_true', help='仅使用 data/raw 缓存，不联网')
    ap.add_argument('--refs', default=REF_DIR, help='参考截图目录')
    ap.add_argument('--outdir', default=OUT_DIR)
    ap.add_argument('--diff', action='store_true', help='IDW 散点复算格网并与平台格网对比')
    ap.add_argument('--idw-k', type=int, default=3)
    ap.add_argument('--idw-power', type=float, default=2.0)
    ap.add_argument('--flip-ys', action='store_true',
                    help='渲染时上下翻转格网（第 1 行画在顶部，复现"平台行首在上"的显示约定；'
                         '默认按 gridLocations 真实经纬度绘制）')
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    client = APIClient(config.host, config.app_key, config.app_secret, 120)

    target_dt = datetime(*map(int, args.date.split('-')), args.hour, 0, 0)
    target_ms = ms(target_dt)
    time_str = target_dt.strftime('%Y-%m-%d %H:%M')

    report_lines = [f'# 讯腾降水量图算法复现对照报告', '',
                    f'- 时间范围: {args.date} {args.hour_range[0]:02d}:00 ~ {args.hour_range[1]:02d}:59',
                    f'- 对比时刻: {time_str}', f'- 区域 bbox: {args.bbox}', '']
    entries = []

    for layer in args.layers:
        meta = LAYERS.get(layer)
        if not meta:
            print(f'!! 未配置的图层: {layer}，跳过')
            continue
        print(f'\n===== {layer} {meta["name"]} =====')

        # 1) 取数据（缓存优先）
        data = None
        cache_path = None
        if not args.no_fetch:
            data, cache_path = fetch_layer(client, layer, args.date,
                                           args.hour_range[0], args.hour_range[1], args.bbox)
            print(f'已拉取: {cache_path}')
        else:
            data, cache_path = load_cache(layer, args.date, args.hour_range[0], args.hour_range[1])
            if data is None:
                print(f'!! 缓存不存在: {cache_path}（去掉 --no-fetch 联网拉取）')
                report_lines.append(f'## {layer}：无缓存数据，跳过')
                continue
        frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
        print(f'数据帧: {len(frames)} 个，时刻: '
              f'{datetime.fromtimestamp(frames[0] / 1000):%H:%M} ~ '
              f'{datetime.fromtimestamp(frames[-1] / 1000):%H:%M}')

        # 2) 目标帧（无精确时刻则取最近）
        if target_ms not in frames:
            if not frames:
                print('!! 无数据帧，跳过')
                report_lines.append(f'## {layer}：无数据帧，跳过')
                continue
            nearest = min(frames, key=lambda t: abs(t - target_ms))
            print(f'!! 目标时刻 {time_str} 无帧，使用最近帧 '
                  f'{datetime.fromtimestamp(nearest / 1000):%H:%M}')
            target_ms = nearest

        Z, xs, ys, notes = eqs.extract_frame(data, target_ms)
        bbox = eqs.frame_bbox(xs, ys)
        if args.flip_ys:
            Z = Z[::-1, :]
            ys = ys[::-1]
            print('已按 --flip-ys 上下翻转（第 1 行绘制在顶部）')
        breaks, colors = eqs.parse_color_str(meta['colorStr'])
        clip = layer_clip(layer)
        area_wkt = (data.get('groups') or [{}])[0].get('area') if clip else None
        print(f'行政边界裁剪: {"开（groups[].area）" if clip else "关（色块铺满数据范围）"}')

        # 3) 渲染（256x256 与 4x 预览）
        base = f'{layer}_{args.date}_{target_dt.strftime("%H%M")}'
        algo_png = os.path.join(args.outdir, f'{base}_algo256.png')
        preview = os.path.join(args.outdir, f'{base}_preview4x.png')
        eqs.render_equi_surface(Z, xs, ys, breaks, colors, algo_png,
                                mask_wkt=area_wkt, undef=-9999.0)
        eqs.render_equi_surface(Z, xs, ys, breaks, colors, preview,
                                width=1024, height=1024, mask_wkt=area_wkt, undef=-9999.0)
        valid = Z[(~np.isnan(Z)) & (Z != -9999.0)]
        vstats = ('' if len(valid) == 0 else
                  f'值范围 {np.nanmin(valid):.2f} ~ {np.nanmax(valid):.2f} '
                  f'(均值 {np.nanmean(valid):.2f}, 非缺测格点 {len(valid)}/{Z.size})')
        print(f'已出图: {algo_png}（{bbox}，{len(ys)}x{len(xs)} 格网，{vstats}）')

        # 4) 参考截图配对 + 并排对比
        ref_png = find_reference(args.refs, layer)
        title = f'{meta["name"]} {time_str} | 左: 讯腾平台截图 | 右: 算法复现(256x256, {bbox[0]:.3f}~{bbox[2]:.3f}E)'
        summary = (f'数据帧 {len(frames)} 个；色阶断点 {[float(b) for b in breaks]}；'
                   f'bbox [{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}]；'
                   f'cols/rows = {len(xs)}/{len(ys)}；{vstats}')
        if ref_png:
            cmp_png = os.path.join(args.outdir, f'{base}_compare.png')
            render_compare_pair(layer, algo_png, ref_png, cmp_png, title)
            print(f'已生成对照图: {cmp_png}')
            summary += f'；参考截图: {os.path.basename(ref_png)}'
        else:
            cmp_png = None
            print(f'!! references/ 中未找到匹配参考图（关键词: {meta["ref_keywords"]}），'
                  f'请把讯腾截图放入 {args.refs}')

        # 5) 可选 IDW 复现对比
        diff_info = ''
        if args.diff:
            print('--diff: 拉取站点散点历史并复算 IDW 格网 ...')
            try:
                resp = client.request('GET', '/api/v1/upns/stations',
                                      params={'pageNum': 1, 'pageSize': 500,
                                              'minLng': args.bbox[0], 'maxLng': args.bbox[1],
                                              'minLat': args.bbox[2], 'maxLat': args.bbox[3]})
                stations = (resp or {}).get('data', {}).get('stations', [])
                print(f'  站点数: {len(stations)}')
                cache_dir = os.path.join(DATA_DIR, 'cache')
                if not metric_history_has_values(client, stations, meta['metric'],
                                                 target_ms, cache_dir):
                    raise RuntimeError(
                        f'站点历史接口无 {meta["metric"]} 值（实测全为 null），'
                        f'该图层无法用站点散点复算')
                train = build_scatter_history(client, stations, meta['metric'],
                                              target_ms, cache_dir)
                grid_idw = eqs.idw_neighbor(train, xs, ys, k=args.idw_k, power=args.idw_power)
                stats = eqs.compare_grids(grid_idw, Z)
                diff_info = (f'IDW 复算(k={args.idw_k}, p={args.idw_power}) vs 平台格网: '
                             f'RMSE={stats["rmse"]:.4f}, MAE={stats["mae"]:.4f}, '
                             f'相关系数={stats["corr"]:.4f}, 有效格点={stats["n_valid"]}')
                print(f'  {diff_info}')
            except Exception as e:
                diff_info = f'--diff 失败（图层 {layer}）: {e}'
                print(f'  !! {diff_info}')

        report_lines += [f'## {layer} {meta["name"]}', '', f'- {summary}']
        if ref_png:
            report_lines.append(f'- 参考截图: {ref_png}')
            report_lines.append(f'- 对照图: {cmp_png}')
        report_lines.append(f'- 算法出图: {algo_png}（256x256）; 预览: {preview}')
        if diff_info:
            report_lines.append(f'- {diff_info}')
        report_lines.append('')
        entries.append({'layer': layer, 'name': meta['name'], 'unit': data.get('unit', ''),
                        'time_str': time_str, 'summary': summary,
                        'algo_png': algo_png, 'cmp_png': cmp_png, 'ref_png': ref_png})

    report_path = os.path.join(args.outdir, 'report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    html_path = os.path.join(args.outdir, 'compare_index.html')
    write_html(entries, html_path)
    print(f'\n报告: {report_path}\n对照页: {html_path}')


if __name__ == '__main__':
    main()
