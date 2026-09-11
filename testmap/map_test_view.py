# -*- coding: utf-8 -*-
"""
map_test_view.py —— 用迅腾参考算法出图，并生成一个**带底图的地图测试页**。

它用的就是你给的那套算法（段 B），逐步骤对齐：

    步骤 5  解析色阶 colorStr -> dataInterval          xunteng_reference.parse_legend_color_map
    步骤 6  由坐标轴求 bbox                            xunteng_reference.frame_bbox
    步骤 7  等值面追踪（isclip 可选）                   xunteng_reference.equi_surface_from_grid
              Contour.tracingBorders / tracingContourLines / smoothLines / tracingPolygons
              —— 这四支是 wcontour/ 里对 wContour 1.6.1 的逐行移植，
                 已用原始 Java 编译运行导出的多边形做过 5 阶段按位对拍
    步骤 8  按区间填色（>= / <，末档 >=）               xunteng_reference.color_for_polygon
    步骤 9  渲染 PNG                                   xunteng_reference.get_map_content
    步骤 10 返回 WorkResult

地图侧：把渲染出来的 PNG 按 bbox 地理配准，叠到**高德底图**上（ImageLayer），
底图加载失败时自动退到离线视图（经纬网 + 行政区轮廓 + 栅格），页面不会白屏。

用法：
    python map_test_view.py
    python map_test_view.py --input <接口返回.json> --size 1024 --outdir map_view

产物（全部在本文件夹内）：
    map_view/index.html          地图测试页
    map_view/data.js             帧清单 + 色阶 + 行政区轮廓
    map_view/wmts_map_config.js  高德/天地图凭证（从项目里拷）
    map_view/layers/*.png        各帧出图

看完直接打开：http://localhost:<port>/index.html  （必须用 localhost，见下方说明）
"""

import argparse
import datetime
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = r'E:\work\zj_official_test'
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
os.environ.setdefault('MPLCONFIGDIR', os.path.join(HERE, '.mplcache'))

from precipitation_xunteng import eqs_algorithm as eqs            # noqa: E402
from precipitation_xunteng import xunteng_reference as xr          # noqa: E402
from precipitation_xunteng.layer_config import LAYERS              # noqa: E402

WMTS_CONFIG = os.path.join(PROJECT, 'wmts_demo', 'wmts_map_config.js')
LAYER = 'XTSKJSXS'
REFERENCE_SIZE = 256          # 参考代码 getMapContent 里写死的尺寸
UNDEF = xr.UNDEF_DATA


# ---------------------------------------------------------------------------

def find_input(explicit):
    if explicit:
        return explicit
    for f in sorted(os.listdir(HERE)):
        if f.lower().endswith('.json') and 'precipitation_layers' in f:
            return os.path.join(HERE, f)
    raise SystemExit('没找到接口返回 JSON（*precipitation_layers*.json），用 --input 指定')


def load_data(path):
    with open(path, encoding='utf-8') as f:
        j = json.load(f)
    resp = j['response'] if isinstance(j.get('response'), dict) else j
    return resp['data']


def boundary_rings(area_wkt):
    """groups[].area（MULTIPOLYGON WKT）-> 环坐标数组，供底图加载失败时画轮廓。"""
    if not area_wkt:
        return []
    try:
        import shapely
    except ImportError:
        return []
    geom = shapely.from_wkt(area_wkt)
    parts = list(geom.geoms) if geom.geom_type.startswith('Multi') else [geom]
    rings = [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in parts]
    rings.sort(key=len, reverse=True)
    return rings


def render(data, target_ms, color_str, size, out_dir, suffix=''):
    """跑参考算法的段 B 并出图，返回这一帧的元信息。

    suffix 会拼进文件名 —— 同一帧会出多个版本（地图用的 1024、参考原尺寸 256、
    最低档不透明的白色版），不带后缀会互相覆盖。
    """
    Z, xs, ys, _ = eqs.extract_frame(data, target_ms)
    matrix = Z.tolist()
    n_nan = 0
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v != v:                       # 接口的 null -> 参考算法的缺测值
                matrix[i][j] = UNDEF
                n_nan += 1
    x_axis = [float(v) for v in xs]
    y_axis = [float(v) for v in ys]

    breaks, colors = xr.parse_legend_color_map(color_str)         # 步骤 5
    bbox = xr.frame_bbox(x_axis, y_axis)                          # 步骤 6
    # 步骤 7：wContour 会就地给 S0 加 dShift，传拷贝
    polys, _info = xr.equi_surface_from_grid([r[:] for r in matrix],
                                             x_axis, y_axis, breaks, False)
    dt = datetime.datetime.fromtimestamp(target_ms / 1000)
    name = f'{LAYER}_{dt:%Y%m%d_%H%M}{suffix}.png'
    n_drawn = xr.get_map_content(polys, {'bbox': bbox, 'width': size, 'height': size},  # 步骤 9
                                 os.path.join(out_dir, 'layers', name), breaks, colors, 1.0)

    valid = [v for row in matrix for v in row if v != UNDEF]
    return {
        'time': dt.strftime('%Y-%m-%d %H:%M'), 'label': dt.strftime('%H:%M'),
        'dtms': target_ms, 'png': 'layers/' + name, 'bbox': bbox,
        'cols': len(x_axis), 'rows': len(y_axis),
        'vmin': min(valid) if valid else None, 'vmax': max(valid) if valid else None,
        'vmean': (sum(valid) / len(valid)) if valid else None,
        'nPolygons': len(polys), 'nDrawn': n_drawn, 'nNan': n_nan,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='用参考算法出图并生成地图测试页')
    ap.add_argument('--input', default=None, help='接口返回 JSON（默认取本文件夹里的）')
    ap.add_argument('--layer', default=LAYER)
    ap.add_argument('--date', default=None, help='只出这一天（默认全部帧）')
    ap.add_argument('--size', type=int, default=1024, help='地图叠加图尺寸（参考代码是 256）')
    ap.add_argument('--also-256', action='store_true', default=True,
                    help='同时输出一张参考代码原尺寸 256×256 的图（默认开）')
    ap.add_argument('--clip', action='store_true', help='按行政边界裁剪等值面')
    ap.add_argument('--band-mode', choices=['auto', 'low', 'high'], default='auto')
    ap.add_argument('--outdir', default=os.path.join(HERE, 'map_view'))
    args = ap.parse_args(argv)

    xr.BAND_MODE = args.band_mode
    out_dir = args.outdir
    os.makedirs(os.path.join(out_dir, 'layers'), exist_ok=True)

    src = find_input(args.input)
    data = load_data(src)
    layer = data.get('layer') or args.layer
    meta = LAYERS.get(layer)
    if not meta:
        raise SystemExit(f'图层 {layer} 没在 layer_config.LAYERS 里配置色阶')
    print(f'输入: {os.path.basename(src)}')
    print(f'图层: {layer} {meta["name"]}（{data.get("unit")}）')

    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])
    labels = meta.get('legendLabels') or [str(b) for b in breaks]
    order = meta.get('legendOrder', 'desc')

    # 最低档透明时另出一张"显示版"
    alt_str, shown = None, meta.get('showFirstBand')
    if shown:
        obj = json.loads(meta['colorStr'])
        lowest = min(obj, key=lambda s: float(s))
        if obj[lowest].upper().endswith('00'):
            obj[lowest] = shown
            alt_str = json.dumps({k: obj[k] for k in sorted(obj, key=float)}, ensure_ascii=False)

    frames_ms = sorted({r['dataTime'] for r in data['rowsList']})
    if args.date:
        frames_ms = [t for t in frames_ms
                     if datetime.datetime.fromtimestamp(t / 1000).strftime('%Y-%m-%d') == args.date]
    print(f'帧: {len(frames_ms)} 个，尺寸 {args.size}px'
          + (f'（另出 {REFERENCE_SIZE}px）' if args.also_256 else ''))

    frames = []
    for t in frames_ms:
        fr = render(data, t, meta['colorStr'], args.size, out_dir)
        if alt_str:
            fr['pngWhite'] = render(data, t, alt_str, args.size, out_dir, suffix='_white')['png']
        if args.also_256:
            render(data, t, meta['colorStr'], REFERENCE_SIZE, out_dir, suffix='_256')
        frames.append(fr)
        print(f"  {fr['time']}  {fr['cols']}x{fr['rows']} 格网  "
              f"值 {fr['vmin']:.2f}~{fr['vmax']:.2f}  "
              f"多边形 {fr['nPolygons']}  填色 {fr['nDrawn']}")

    rings = boundary_rings((data.get('groups') or [{}])[0].get('area'))
    print(f'行政边界: {len(rings)} 个环，主环 {len(rings[0]) if rings else 0} 点（底图不可用时用）')

    view = list(frames[0]['bbox'])
    for f in frames:
        b = f['bbox']
        view = [min(view[0], b[0]), min(view[1], b[1]), max(view[2], b[2]), max(view[3], b[3])]
    for r in rings:
        for x, y in r:
            view[0] = min(view[0], x); view[1] = min(view[1], y)
            view[2] = max(view[2], x); view[3] = max(view[3], y)

    payload = {
        'layer': layer, 'title': meta['name'],
        'unit': data.get('unit') or meta.get('unit') or '',
        'engine': 'wContour 1.6.1 逐行移植（与原始 Java 5 阶段按位一致）',
        'note': '等值面追踪 → 区间填色 → 渲染（段 B）',
        'source': os.path.basename(src),
        'legend': {'breaks': [float(b) for b in breaks], 'colors': list(colors),
                   'labels': list(labels), 'order': order},
        'frames': frames, 'boundary': rings, 'view': view,
        'size': args.size, 'referenceSize': REFERENCE_SIZE,
    }
    with open(os.path.join(out_dir, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.XT = ')
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')

    shutil.copyfile(os.path.join(HERE, 'map_view_template.html'),
                    os.path.join(out_dir, 'index.html'))
    if os.path.exists(WMTS_CONFIG):
        shutil.copyfile(WMTS_CONFIG, os.path.join(out_dir, 'wmts_map_config.js'))
    else:
        print(f'!! 没找到 {WMTS_CONFIG}，页面底图不可用（会退到离线视图）')

    print(f'\n页面   : {os.path.join(out_dir, "index.html")}')
    print('打开   : 起个静态服务，然后浏览器访问 http://localhost:<端口>/index.html')
    print('         例: python -m http.server 8788 --bind 127.0.0.1 --directory '
          f'"{out_dir}"')
    print('         必须用 localhost 不能用 127.0.0.1 —— 高德 Key 白名单按域名生效，'
          'IP 不在白名单里底图会加载失败。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
