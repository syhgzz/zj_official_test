# -*- coding: utf-8 -*-
"""
export_web_reference.py —— 用**忠实移植版**出图，接进现有的 `precip_compare.html`。

跟 `export_web.py` 的区别
=========================
| | export_web.py | 本文件 |
|---|---|---|
| 数据来源 | 调接口（`lib/api_client`，需要签名联网） | **只读本地接口返回 JSON**（`responses/`、`data/raw/`），不联网 |
| 等值面 | matplotlib `contourf` 近似 | **wContour 1.6.1 逐行移植**（`xunteng_reference.equi_surface_from_grid`） |
| 色带 | 按数值区间（contourf levels） | 按 `IsHighCenter` 定位区间（见 `xunteng_reference.color_for_polygon`） |
| 产物 | `output/web/` | `output/web_ref/` |

产物结构与 `precip_layers.js` **完全同构**，所以现有的 `precip_compare.html`
（地图叠加 + 时刻滑块 + 色阶图例 + 参考截图）不用改一行就能用。

用法
====
    uv run python -m precipitation_xunteng.export_web_reference
    uv run python -m precipitation_xunteng.export_web_reference --layers XTSKJSXS XTSKPWV --size 1024
    uv run python -m precipitation_xunteng.serve_web --dir precipitation_xunteng/output/web_ref
    # 然后浏览器打开 http://localhost:8765/precip_compare.html

为什么必须用 HTTP 打开：高德 `ImageLayer` 叠加本地 PNG 在 `file://` 下不渲染，
且高德 Key 白名单按域名生效（`localhost` 可、`127.0.0.1` 可能不在白名单）。
"""

import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jingyao_test.Urban_area import eqs_algorithm as eqs                  # noqa: E402
from jingyao_test.Urban_area import xunteng_reference as xr                # noqa: E402
from jingyao_test.Urban_area.layer_config import LAYERS, layer_clip        # noqa: E402
from jingyao_test.Urban_area.run_compare import find_reference             # noqa: E402

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
WEB_TEMPLATE_DIR = os.path.join(PACKAGE_DIR, 'web')
WEB_OUT_DIR = os.path.join(PACKAGE_DIR, 'output', 'web_ref')
WMTS_CONFIG_SRC = os.path.join(PROJECT_DIR, 'wmts_demo', 'wmts_map_config.js')
REFERENCE_SIZE = 256          # 参考代码 getMapContent 里写死的尺寸


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------

def discover_inputs(explicit):
    """接口返回 JSON：显式指定优先，否则扫 responses/ 与 data/raw/。"""
    if explicit:
        files = []
        for p in explicit:
            if os.path.isdir(p):
                files += [os.path.join(p, f) for f in sorted(os.listdir(p))
                          if f.lower().endswith('.json')]
            elif os.path.isfile(p):
                files.append(p)
        return files
    dirs = [os.path.join(PROJECT_DIR, 'responses'),
            os.path.join(PACKAGE_DIR, 'data', 'raw')]
    files = []
    for d in dirs:
        if os.path.isdir(d):
            files += [os.path.join(d, f) for f in sorted(os.listdir(d))
                      if f.lower().endswith('.json')]
    return files


def load_payload(path):
    """兼容两种落盘格式：结果文件夹 {"response":{"data":...}} / 缓存 {"data":...}。"""
    try:
        with open(path, encoding='utf-8') as f:
            j = json.load(f)
    except Exception as e:
        print(f'  !! 读取失败 {os.path.basename(path)}: {e}')
        return None
    resp = j['response'] if isinstance(j.get('response'), dict) else j
    data = resp.get('data')
    if not isinstance(data, dict) or 'rowsList' not in data:
        return None
    return data


# ---------------------------------------------------------------------------
# 色阶 / 图例（一律以 layer_config.py 为准）
# ---------------------------------------------------------------------------

def layer_legend(layer):
    """返回网页图例需要的字段（breaks / colors / legendLabels / legendOrder）。"""
    meta = LAYERS[layer]
    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])
    return {
        'breaks': [float(b) for b in breaks],
        'colors': list(colors),
        'legendLabels': meta.get('legendLabels'),
        'legendOrder': meta.get('legendOrder', 'desc'),
    }


def alt_color_str(layer):
    """最低档是透明（#RRGGBBAA 的 AA=00）且配置了 showFirstBand 时，返回"显示版" colorStr。"""
    meta = LAYERS.get(layer) or {}
    shown = meta.get('showFirstBand')
    if not shown:
        return None
    obj = json.loads(meta['colorStr'])
    if not obj:
        return None
    lowest = min(obj, key=lambda s: float(s))
    if obj[lowest].upper().endswith('00'):
        obj[lowest] = shown
        order = sorted(obj, key=float)
        return json.dumps({k: obj[k] for k in order}, ensure_ascii=False)
    return None


# ---------------------------------------------------------------------------
# 单帧：追踪一次，渲染两种尺寸
# ---------------------------------------------------------------------------

def render_frame(layer, data, target_ms, out_dir, args):
    """忠实移植链路出图。返回 (items, bbox, info)。"""
    meta = LAYERS[layer]
    color_str = meta['colorStr']
    breaks, colors = xr.parse_legend_color_map(color_str)

    Z, xs, ys, _ = eqs.extract_frame(data, target_ms)
    matrix = Z.tolist()
    n_nan = 0
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v != v:                                  # NaN -> 参考算法的缺测值
                matrix[i][j] = xr.UNDEF_DATA
                n_nan += 1
    x_axis = [float(v) for v in xs]
    y_axis = [float(v) for v in ys]
    bbox = xr.frame_bbox(x_axis, y_axis)

    clip = args.clip if args.clip is not None else layer_clip(layer)
    area_wkt = None
    if clip:
        groups = data.get('groups') or []
        area_wkt = groups[0].get('area') if groups else None
        if not area_wkt:
            clip = False

    # 与 finishFromGrid 完全相同的调用链（追踪一次，两种尺寸复用同一批多边形）
    # 注意 wContour 会就地给 S0 加 dShift，所以要传拷贝
    polys, info = xr.equi_surface_from_grid([r[:] for r in matrix], x_axis, y_axis,
                                            breaks, clip, clip_wkt=area_wkt)
    if not polys:
        raise RuntimeError('等值面结果为空，无法出图')

    dt = datetime.fromtimestamp(target_ms / 1000)
    base = f'{layer}_{dt:%H%M}_ref'
    layers_dir = os.path.join(out_dir, 'layers')

    items = {}
    # 页面用的叠加图（默认 1024，按 bbox 地理配准）
    web_png = os.path.join(layers_dir, base + '.png')
    n_drawn = xr.get_map_content(polys, {'bbox': bbox, 'width': args.size,
                                         'height': args.size},
                                 web_png, breaks, colors, 1.0)
    items['grid'] = {'png': f'layers/{base}.png', 'bbox': bbox}
    # 与参考代码同尺寸的 256×256 留档
    ref_png = os.path.join(layers_dir, base + '256.png')
    xr.get_map_content(polys, {'bbox': bbox, 'width': REFERENCE_SIZE,
                               'height': REFERENCE_SIZE},
                       ref_png, breaks, colors, 1.0)

    # 最低档透明的图层：另出一张"显示版"（页面上的「显示 0~0.1 白色档」用它）
    alt = alt_color_str(layer)
    if alt:
        ab, ac = xr.parse_legend_color_map(alt)
        alt_png = os.path.join(layers_dir, base + '_white.png')
        xr.get_map_content(polys, {'bbox': bbox, 'width': args.size,
                                   'height': args.size},
                           alt_png, ab, ac, 1.0)
        items['gridWhite'] = {'png': f'layers/{base}_white.png', 'bbox': bbox}

    info = (f'接口格网 {len(x_axis)}x{len(y_axis)}'
            f' → 等值面 {len(polys)} 个（填色 {n_drawn}）'
            f'{"，按行政边界裁剪" if clip else ""}'
            + (f'，{n_nan} 个缺测格点' if n_nan else ''))
    stats = dict(cols=len(x_axis), rows=len(y_axis),
                 nPolygons=len(polys), nDrawn=n_drawn, nNan=n_nan)
    valid = [v for row in matrix for v in row if v != xr.UNDEF_DATA]
    if valid:
        stats['vmin'] = min(valid)
        stats['vmax'] = max(valid)
    return items, bbox, info, stats


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def render_scatter_frame(layer, scatter_json, t, dt, out_dir, args):
    """
    「复刻迅腾算法」：txt 段A + 段B（逐行移植引擎）
      段A：散点 → 包围盒（minX==0 的 Java 写法）→ BigDecimal 外扩 0.07° → 1km 格网 → IDW(3 近邻)
      段B：wContour 等值面追踪 → 按 IsHighCenter 选色带填色 → PNG
    """
    meta = LAYERS[layer]
    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])

    # ---- 步骤 1：遍历 jsonArray（Java 的 minX == 0 判断逐字保留）----
    min_x = max_x = min_y = max_y = 0.0
    rows = len(scatter_json)
    train_data = [[0.0, 0.0, 0.0] for _ in range(rows)]
    valid = 0
    for i in range(rows):
        item = scatter_json[i]
        l, b, v = item.get('l'), item.get('b'), item.get('v')
        if l is None or b is None or v is None:
            continue
        l, b, v = float(l), float(b), float(v)
        if min_x == 0 or l < min_x:
            min_x = l
        if max_x == 0 or l > max_x:
            max_x = l
        if min_y == 0 or b < min_y:
            min_y = b
        if max_y == 0 or b > max_y:
            max_y = b
        train_data[i][0], train_data[i][1], train_data[i][2] = l, b, v
        valid += 1
    if valid == 0:
        raise ValueError('有效插值点为空')

    # ---- 步骤 2/3/4 ----
    min_x, max_x = xr.bd_subtract(min_x, 0.07), xr.bd_add(max_x, 0.07)
    min_y, max_y = xr.bd_subtract(min_y, 0.07), xr.bd_add(max_y, 0.07)
    cols, n_rows = xr.grid_size_from_km(min_x, min_y, max_x, max_y, 1.0)
    x_axis, y_axis = xr.create_grid_xy_num(min_x, min_y, max_x, max_y, cols, n_rows)
    matrix = xr.interpolation_idw_neighbor(train_data, x_axis, y_axis, 3, xr.UNDEF_DATA)

    # ---- 段 B ----
    bbox = xr.frame_bbox(x_axis, y_axis)
    clip = args.clip if args.clip is not None else layer_clip(layer)
    area_wkt = None
    if clip:
        groups = (args.current_data or {}).get('groups') or []
        area_wkt = groups[0].get('area') if groups else None
        if not area_wkt:
            clip = False
    polys, info = xr.equi_surface_from_grid([r[:] for r in matrix], x_axis, y_axis,
                                            breaks, clip, clip_wkt=area_wkt)
    if not polys:
        raise RuntimeError('等值面结果为空，无法出图')

    base = f'{layer}_{dt:%H%M}_xtref'
    layers_dir = os.path.join(out_dir, 'layers')
    png = os.path.join(layers_dir, base + '.png')
    n_drawn = xr.get_map_content(polys, {'bbox': bbox, 'width': args.size,
                                         'height': args.size},
                                 png, breaks, colors, 1.0)
    ref_png = os.path.join(layers_dir, base + '256.png')
    xr.get_map_content(polys, {'bbox': bbox, 'width': REFERENCE_SIZE,
                               'height': REFERENCE_SIZE},
                       ref_png, breaks, colors, 1.0)
    items = {'xt': {'png': f'layers/{base}.png', 'bbox': bbox}}

    alt = alt_color_str(layer)
    if alt:
        ab, ac = xr.parse_legend_color_map(alt)
        alt_png = os.path.join(layers_dir, base + '_white.png')
        xr.get_map_content(polys, {'bbox': bbox, 'width': args.size,
                                   'height': args.size},
                           alt_png, ab, ac, 1.0)
        items['xtWhite'] = {'png': f'layers/{base}_white.png', 'bbox': bbox}

    info = (f'散点 {valid} 个 → {cols}x{n_rows} 格网'
            f' → 等值面 {len(polys)} 个（填色 {n_drawn}）'
            f'{"，按行政边界裁剪" if clip else ""}')
    stats = dict(points=valid, cols=cols, rows=n_rows,
                 nPolygons=len(polys), nDrawn=n_drawn)
    return items, bbox, info, stats


def load_scatter_json(client, layer, bbox, dt_ms, cache_dir, tol_minutes=30.0):
    """取该时刻站点散点，转成 txt 的 jsonArray 形状 [{'l','b','v'}, ...]。"""
    from jingyao_test.Urban_area.algo_compare import load_scatter, load_stations

    stations = load_stations(client, bbox)
    arr, _skipped, src = load_scatter(client, stations, LAYERS[layer]['metric'],
                                      dt_ms, cache_dir,
                                      tol_ms=tol_minutes * 60 * 1000)
    return [{'l': float(a), 'b': float(b), 'v': float(c)} for a, b, c in arr], src


def export_layer(layer, payloads, out_dir, args, manifest):
    meta = LAYERS.get(layer)
    if not meta:
        print(f'!! 未配置图层 {layer}，跳过')
        return

    legend = layer_legend(layer)
    frames = []
    seen = set()
    for path, data in payloads:
        if data.get('layer') != layer:
            continue
        for r in (data.get('rowsList') or []):
            t = r.get('dataTime')
            if t is None or t in seen:
                continue
            dt = datetime.fromtimestamp(t / 1000)
            if args.date and dt.strftime('%Y-%m-%d') != args.date:
                continue
            if not (args.hour_start <= dt.hour <= args.hour_end):
                continue
            seen.add(t)
            frames.append((t, dt, path, data))
    frames.sort(key=lambda x: x[0])
    if not frames:
        print(f'!! {layer} 在 {args.date} {args.hour_start:02d}:00~{args.hour_end:02d}:00 无数据帧，跳过')
        return

    entry = {
        'name': meta['name'],
        'unit': meta.get('unit', ''),
        'metric': meta.get('metric', ''),
        'breaks': legend['breaks'],
        'colors': legend['colors'],
        'legendLabels': legend['legendLabels'],
        'legendOrder': legend['legendOrder'],
        # 页面在 inputMode=='grid' 时不会用 algoParams 拼文案，这里放引擎信息备查
        'algoParams': {'engine': 'wcontour-1.6.1-port',
                       'bandMode': xr.BAND_MODE,
                       'clip': bool(args.clip if args.clip is not None else layer_clip(layer))},
        'frames': [],
    }

    print(f'[{layer}] {meta["name"]}：{len(frames)} 帧，'
          f'色阶断点 {legend["breaks"]}，'
          f'引擎=wContour 逐行移植，尺寸 {args.size}px（另存 {REFERENCE_SIZE}px）')

    client = None
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'cache')
    if not args.no_scatter:
        try:
            from config.config import config
            from lib.api_client import APIClient
            client = APIClient(config.host, config.app_key, config.app_secret, 120)
        except Exception as e:
            print(f'  -- 站点散点不可用（{e}），复刻迅腾算法将跳过')

    for t, dt, path, data in frames:
        args.current_data = data
        try:
            items, bbox, info, stats = render_frame(layer, data, t, out_dir, args)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'  !! {dt:%Y-%m-%d %H:%M} 接口格网出图失败: {e}')
            continue

        # 「复刻迅腾算法」= txt 段A(散点→IDW) + 段B(wContour 等值面)
        xt_info = '无站点散点，复刻算法不可用'
        input_mode = 'none'
        if client is not None:
            try:
                scatter_json, src = load_scatter_json(client, layer, args.bbox, t,
                                                      cache_dir, args.tol_minutes)
                xt_items, _b, xt_info, _s = render_scatter_frame(
                    layer, scatter_json, t, dt, out_dir, args)
                items.update(xt_items)
                input_mode = 'scatter'
                xt_info = f'{xt_info}（散点来源 {src}）'
            except Exception as e:
                print(f'  {dt:%Y-%m-%d %H:%M} 复刻迅腾算法跳过：{e}')

        entry['frames'].append({
            'dtms': t,
            'time': dt.strftime('%Y-%m-%d %H:%M'),
            'items': items,
            'inputMode': input_mode,
            'scatterSource': None,
            'info': xt_info,
            'gridInfo': info,
            'stats': stats,
            'src': os.path.basename(path),
        })
        print(f'  {dt:%Y-%m-%d %H:%M}  接口格网: {info}')
        print(f'  {" " * 16}  复刻迅腾算法: {xt_info}')

    manifest['layers'][layer] = entry

    ref = find_reference(args.refs, layer)
    if ref:
        ref_name = f'{layer}_{os.path.basename(ref)}'
        shutil.copyfile(ref, os.path.join(out_dir, 'refs', ref_name))
        manifest['refs'].append({'layer': layer, 'file': f'refs/{ref_name}',
                                 'name': os.path.basename(ref)})
        print(f'  参考截图: {os.path.basename(ref)}')
    else:
        print(f'  -- 未匹配到参考截图（关键词 {meta["ref_keywords"]}）；'
              f'把截图放进 {args.refs} 后重跑，或直接在页面上「本地选择…」')


def main(argv=None):
    ap = argparse.ArgumentParser(description='用忠实移植版出图，生成对照网页')
    ap.add_argument('--layers', nargs='+', default=['XTSKJSXS', 'XTSKPWV'])
    ap.add_argument('--input', nargs='+', default=None,
                    help='接口返回 JSON 文件/目录（默认扫 responses/ 与 data/raw/）')
    ap.add_argument('--date', default='2026-08-28')
    ap.add_argument('--hour-start', type=int, default=0)
    ap.add_argument('--hour-end', type=int, default=12)
    ap.add_argument('--size', type=int, default=1024, help='页面叠加图尺寸（参考代码是 256）')
    ap.add_argument('--clip', dest='clip', action='store_true', default=None,
                    help='强制按行政边界裁剪（默认沿用 layer_config 的 clip）')
    ap.add_argument('--no-clip', dest='clip', action='store_false',
                    help='强制不裁剪')
    ap.add_argument('--band-mode', choices=['auto', 'low', 'high'], default='auto',
                    help='色带选取：auto=按 IsHighCenter（默认）；low/high=直接用 LowValue/HighValue')
    ap.add_argument('--refs', default=os.path.join(PACKAGE_DIR, 'references'))
    ap.add_argument('--bbox', nargs=4, type=float, default=[115.814, 116.816, 39.637, 40.423],
                    help='站点查询范围 minLng maxLng minLat maxLat（默认北京）')
    ap.add_argument('--tol-minutes', type=float, default=30.0,
                    help='站点历史取值容差(分钟)')
    ap.add_argument('--no-scatter', action='store_true',
                    help='不出「复刻迅腾算法」（散点→IDW）那一层，只出接口格网')
    ap.add_argument('--outdir', default=WEB_OUT_DIR)
    args = ap.parse_args(argv)

    xr.BAND_MODE = args.band_mode

    files = discover_inputs(args.input)
    if not files:
        print('!! 没有找到接口返回 JSON，请用 --input 指定')
        return 2
    print(f'输入 {len(files)} 个文件: ' + ', '.join(os.path.basename(p) for p in files))

    payloads = []
    for p in files:
        d = load_payload(p)
        if d is not None:
            payloads.append((p, d))
    if not payloads:
        print('!! 没有任何可用的图层数据')
        return 2

    for sub in ('layers', 'refs', 'compare'):
        os.makedirs(os.path.join(args.outdir, sub), exist_ok=True)
    # 页面模板：把清单引用加上时间戳，避免浏览器缓存旧版清单（旧文件名会导致叠加图 404）
    page = open(os.path.join(WEB_TEMPLATE_DIR, 'precip_compare.html'), encoding='utf-8').read()
    stamp = datetime.now().strftime('%Y%m%d%H%M%S')
    page = page.replace('./precip_layers.js', f'./precip_layers.js?v={stamp}')
    with open(os.path.join(args.outdir, 'precip_compare.html'), 'w', encoding='utf-8') as f:
        f.write(page)
    if os.path.exists(WMTS_CONFIG_SRC):
        shutil.copyfile(WMTS_CONFIG_SRC, os.path.join(args.outdir, 'wmts_map_config.js'))
    else:
        print(f'!! 未找到 {WMTS_CONFIG_SRC}（高德/天地图凭证），页面底图不可用')

    manifest = {
        'generatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'date': args.date,
        'hourRange': [args.hour_start, args.hour_end],
        'requestBbox': None,
        'engine': {'name': 'wcontour-1.6.1-port', 'bandMode': args.band_mode,
                   'referenceSize': REFERENCE_SIZE},
        'layers': {},
        'refs': [],
        'compareImages': [],
    }

    for layer in args.layers:
        print(f'\n===== {layer} {LAYERS.get(layer, {}).get("name", "")} =====')
        export_layer(layer, payloads, args.outdir, args, manifest)

    # 若已存在静态并排对比图，一并带上（没有就留空）
    for png in sorted(glob.glob(os.path.join(PACKAGE_DIR, 'output', '*_compare.png'))):
        shutil.copyfile(png, os.path.join(args.outdir, 'compare', os.path.basename(png)))
        manifest['compareImages'].append(f'compare/{os.path.basename(png)}')

    # 第一帧的 bbox 作为地图初始视野兜底（优先接口格网层，没有散点层时也能取到）
    for lyr in manifest['layers'].values():
        if lyr['frames']:
            items = lyr['frames'][0]['items']
            ref_item = items.get('grid') or items.get('xt')
            if ref_item:
                manifest['requestBbox'] = ref_item['bbox']
                break

    manifest_path = os.path.join(args.outdir, 'precip_layers.js')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('window.PRECIP_DATA = ')
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write(';\n')

    n_frames = sum(len(v['frames']) for v in manifest['layers'].values())
    print(f'\n网页  : {os.path.join(args.outdir, "precip_compare.html")}')
    print(f'清单  : {manifest_path}（{len(manifest["layers"])} 图层 / {n_frames} 帧）')
    print(f'打开  : uv run python -m precipitation_xunteng.serve_web '
          f'--dir "{args.outdir}"  →  http://localhost:8765/precip_compare.html')
    return 0


if __name__ == '__main__':
    sys.exit(main())
