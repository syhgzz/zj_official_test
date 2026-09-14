# -*- coding: utf-8 -*-
"""
export_web.py —— 导出网页版：讯腾实时算法出图 + 与参考截图对比

对每个时刻用讯腾算法（等值面填色 + 色阶 + 行政边界裁剪）渲染平台实时场，
并收集 references/ 里匹配到的讯腾平台截图与静态并排对比图，供页面左右对比。

产物目录 precipitation_xunteng/output/web/：
    precip_compare.html   对比页（左：地图 + 讯腾实时场出图；右：参考截图）
    precip_layers.js      图层清单（图层/帧/bbox/色阶/参考截图）
    wmts_map_config.js    从 wmts_demo/ 复制（高德 Key、天地图 Token）
    layers/*.png          各时刻讯腾实时场出图（透明背景，按 bbox 地理配准）
    refs/*.png            匹配到的参考截图副本
    compare/*.png         静态并排对比图副本（run_compare 生成）

用法：
    uv run python -m precipitation_xunteng.export_web --no-fetch
    uv run python -m precipitation_xunteng.export_web --layers XTSKPWV XTSKJSXS --size 1024
"""

import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import numpy as np

from config.config import config
from lib.api_client import APIClient

from jingyao_test.Urban_area import eqs_algorithm as eqs
from jingyao_test.Urban_area.algo_compare import (load_scatter, load_stations,
                                               warm_station_series)
from jingyao_test.Urban_area.fetch_layers import fetch_layer
from jingyao_test.Urban_area.layer_config import DEFAULT_LAYERS, LAYERS, layer_clip
from jingyao_test.Urban_area.run_compare import (DATA_DIR, OUT_DIR, PACKAGE_DIR,
                                               find_reference, load_cache)

WEB_TEMPLATE_DIR = os.path.join(PACKAGE_DIR, 'web')
WEB_OUT_DIR = os.path.join(PACKAGE_DIR, 'output', 'web')
WMTS_CONFIG_SRC = os.path.join(os.path.dirname(PACKAGE_DIR), 'wmts_demo', 'wmts_map_config.js')


def load_layer_data(client, layer, args):
    if args.no_fetch:
        data, cache_path = load_cache(layer, args.date, args.hour_range[0], args.hour_range[1])
        if data is None:
            print(f'!! 无缓存 {cache_path}（去掉 --no-fetch 联网拉取），跳过 {layer}')
            return None
        return data
    data, cache_path = fetch_layer(client, layer, args.date,
                                   args.hour_range[0], args.hour_range[1], args.bbox)
    print(f'[{layer}] 已拉取: {cache_path}')
    return data


def alt_color_str(layer):
    """若该层第一档被设为透明隐藏，返回"显示版"colorStr（第一档还原为不透明），否则 None。"""
    meta = LAYERS.get(layer) or {}
    shown = meta.get('showFirstBand')
    if not shown:
        return None
    obj = json.loads(meta['colorStr'])
    if not obj:
        return None
    lowest = min(obj, key=lambda s: float(s))
    if obj[lowest].upper().endswith('00'):        # 当前是透明的
        obj[lowest] = shown
        return json.dumps(obj, ensure_ascii=False)
    return None


def export_layer(layer, args, manifest, out_dir):
    meta = LAYERS.get(layer)
    if not meta:
        print(f'!! 未配置图层 {layer}，跳过')
        return
    data = load_layer_data(client, layer, args)
    if data is None:
        return

    breaks, colors = eqs.parse_color_str(meta['colorStr'])
    frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
    if not frames:
        print(f'!! {layer} 无数据帧，跳过')
        return
    clip = layer_clip(layer)
    area_wkt = (data.get('groups') or [{}])[0].get('area') if clip else None
    alt_str = alt_color_str(layer)
    print(f'[{layer}] {meta["name"]}：{len(frames)} 帧，'
          f'色阶断点 {[float(b) for b in breaks]}，'
          f'行政边界裁剪 {"开" if clip else "关（色块铺满数据范围）"}'
          + ('，最低档默认隐藏（另出显示版）' if alt_str else ''))

    entry = {
        'name': meta['name'],
        'unit': data.get('unit') or meta.get('unit') or '',
        'metric': meta['metric'],
        'breaks': [float(b) for b in breaks],
        'colors': colors,
        'legendLabels': meta.get('legendLabels'),
        'legendOrder': meta.get('legendOrder', 'desc'),
        'algoParams': {'k': args.k, 'power': args.power, 'cellKm': args.cell_km, 'pad': args.pad},
        'frames': [],
    }

    cache_dir = os.path.join(DATA_DIR, 'cache')
    stations = load_stations(client, args.bbox)
    print(f'[{layer}] 站点数: {len(stations)}')
    warm_station_series(client, stations, meta['metric'], frames[-1], cache_dir)

    for dt in frames:
        hhmm = datetime.fromtimestamp(dt / 1000).strftime('%H%M')
        label = datetime.fromtimestamp(dt / 1000).strftime('%Y-%m-%d %H:%M')
        items = {}

        # 接口返回的格网（同一时刻）
        Zg, xsg, ysg, _ = eqs.extract_frame(data, dt)
        xsg = np.asarray(xsg, dtype=float)
        ysg = np.asarray(ysg, dtype=float)

        # ① 接口格网 → 等值面填色（txt 段B：finishFromGrid 那一半）
        grid_png = f'{layer}_{hhmm}_grid.png'
        eqs.render_equi_surface(Zg, xsg, ysg, breaks, colors,
                                os.path.join(out_dir, 'layers', grid_png),
                                width=args.size, height=args.size,
                                mask_wkt=area_wkt, undef=-9999.0)
        grid_bbox = [float(v) for v in eqs.frame_bbox(xsg, ysg)]
        items['grid'] = {'png': f'layers/{grid_png}', 'bbox': grid_bbox}
        if alt_str:
            alt_breaks, alt_colors = eqs.parse_color_str(alt_str)
            eqs.render_equi_surface(Zg, xsg, ysg, alt_breaks, alt_colors,
                                    os.path.join(out_dir, 'layers', f'{layer}_{hhmm}_grid_white.png'),
                                    width=args.size, height=args.size,
                                    mask_wkt=area_wkt, undef=-9999.0)
            items['gridWhite'] = {'png': f'layers/{layer}_{hhmm}_grid_white.png', 'bbox': grid_bbox}

        # ② 复刻迅腾算法（txt 段A+段B）：站点散点 → 外扩 0.07° → 1km 格网 → IDW(3近邻) → 等值面
        scatter = None
        source = None
        try:
            scatter, _skipped, source = load_scatter(
                client, stations, meta['metric'], dt, cache_dir,
                tol_ms=args.tol_minutes * 60 * 1000,
                fallback_field=(Zg, xsg, ysg) if args.platform_fallback else None)
        except Exception as e:
            print(f'  {label}: 无站点散点（{e}）')

        if scatter is not None:
            xt_png = f'{layer}_{hhmm}_xt.png'
            res = eqs.run_full_algorithm(
                scatter, meta['colorStr'], os.path.join(out_dir, 'layers', xt_png),
                k=args.k, power=args.power, cell_km=args.cell_km, pad=args.pad,
                clip=clip, mask_wkt=area_wkt, size=args.size)
            xt_bbox = [float(v) for v in res['bbox']]
            items['xt'] = {'png': f'layers/{xt_png}', 'bbox': xt_bbox}
            if alt_str:
                eqs.run_full_algorithm(
                    scatter, alt_str, os.path.join(out_dir, 'layers', f'{layer}_{hhmm}_xt_white.png'),
                    k=args.k, power=args.power, cell_km=args.cell_km, pad=args.pad,
                    clip=clip, mask_wkt=area_wkt, size=args.size)
                items['xtWhite'] = {'png': f'layers/{layer}_{hhmm}_xt_white.png', 'bbox': xt_bbox}
            xt_info = f'散点 {res["points"]} 个（{source}）→ {res["cols"]}x{res["rows"]} 格网'
            input_mode = 'scatter'
        else:
            xt_info = '无站点散点，复刻算法不可用'
            input_mode = 'none'

        entry['frames'].append({
            'dtms': dt, 'time': label, 'items': items,
            'inputMode': input_mode, 'scatterSource': source, 'info': xt_info,
        })
        print(f'  {label} 接口格网 -> {grid_png}｜复刻迅腾算法: {xt_info}')

    manifest['layers'][layer] = entry

    ref = find_reference(args.refs, layer)
    if ref:
        ref_name = f'{layer}_{os.path.basename(ref)}'
        shutil.copyfile(ref, os.path.join(out_dir, 'refs', ref_name))
        manifest['refs'].append({'layer': layer, 'file': f'refs/{ref_name}',
                                 'name': os.path.basename(ref)})
        print(f'  参考截图: {os.path.basename(ref)}')
    else:
        print(f'  !! 未匹配到参考截图（关键词 {meta["ref_keywords"]}），'
              f'可把截图放入 {args.refs} 后重跑，或在页面上用「本地选择…」')


def main():
    global client
    ap = argparse.ArgumentParser(description='导出网页版：讯腾实时算法出图 + 截图对比')
    ap.add_argument('--layers', nargs='+', default=DEFAULT_LAYERS)
    ap.add_argument('--date', default='2026-08-28')
    ap.add_argument('--hour-range', nargs=2, type=int, default=[0, 12], metavar=('H_START', 'H_END'))
    ap.add_argument('--bbox', nargs=4, type=float, default=[115.814, 116.816, 39.637, 40.423])
    ap.add_argument('--refs', default=os.path.join(PACKAGE_DIR, 'references'))
    ap.add_argument('--size', type=int, default=1024)
    # 讯腾算法（txt）参数
    ap.add_argument('--k', type=int, default=3, help='IDW 近邻数（txt 参考为 3）')
    ap.add_argument('--power', type=float, default=2.0, help='IDW 幂次')
    ap.add_argument('--cell-km', type=float, default=1.0, help='格网边长(km)，txt 参考为 1.0')
    ap.add_argument('--pad', type=float, default=0.07, help='包围盒外扩(度)，txt 参考为 0.07')
    ap.add_argument('--tol-minutes', type=float, default=30.0, help='站点历史取值容差(分钟)')
    ap.add_argument('--platform-fallback', action='store_true',
                    help='站点历史缺该要素时，用平台场在站点位置抽样作为散点')
    ap.add_argument('--no-fetch', action='store_true')
    ap.add_argument('--outdir', default=WEB_OUT_DIR)
    args = ap.parse_args()

    for sub in ('layers', 'refs', 'compare'):
        os.makedirs(os.path.join(args.outdir, sub), exist_ok=True)
    # 页面模板：清单引用带时间戳，避免浏览器缓存旧清单导致叠加图 404
    page = open(os.path.join(WEB_TEMPLATE_DIR, 'precip_compare.html'), encoding='utf-8').read()
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    page = page.replace('./precip_layers.js', f'./precip_layers.js?v={stamp}')
    with open(os.path.join(args.outdir, 'precip_compare.html'), 'w', encoding='utf-8') as f:
        f.write(page)
    if os.path.exists(WMTS_CONFIG_SRC):
        shutil.copyfile(WMTS_CONFIG_SRC, os.path.join(args.outdir, 'wmts_map_config.js'))
    else:
        print(f'!! 未找到 {WMTS_CONFIG_SRC}（高德/天地图凭证），页面将无法加载底图')

    manifest = {
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': args.date,
        'hourRange': args.hour_range,
        'requestBbox': args.bbox,
        'layers': {},
        'refs': [],
        'compareImages': [],
    }

    client = APIClient(config.host, config.app_key, config.app_secret, 120)
    for layer in args.layers:
        print(f'\n===== {layer} {LAYERS.get(layer, {}).get("name", "")} =====')
        export_layer(layer, args, manifest, args.outdir)

    # 静态并排对比图（run_compare 生成：左=参考截图，右=算法出图）
    for png in sorted(glob.glob(os.path.join(OUT_DIR, '*_compare.png'))):
        shutil.copyfile(png, os.path.join(args.outdir, 'compare', os.path.basename(png)))
        manifest['compareImages'].append(f'compare/{os.path.basename(png)}')

    manifest_path = os.path.join(args.outdir, 'precip_layers.js')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('window.PRECIP_DATA = ')
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write(';\n')

    print(f'\n对比页: {os.path.join(args.outdir, "precip_compare.html")}')
    print(f'清单  : {manifest_path}')
    print(f'参考图: {len(manifest["refs"])} 张；并排对比图: {len(manifest["compareImages"])} 张')


if __name__ == '__main__':
    main()
