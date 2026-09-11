# -*- coding: utf-8 -*-
"""
build_xunteng_html.py —— 把接口返回格网渲染成图，并生成一个**完全独立**的离线 HTML 页面。

和项目里那套 `export_web_reference.py` / `precip_compare.html` 没有任何关系：
  * 页面不依赖高德/天地图/WMTS，不引用任何 CDN，`file://` 双击就能看；
  * 行政区轮廓用接口返回的 `groups[].area`（WKT）自己画成 SVG，离线也有地理参照；
  * 出图仍走 precipitation_xunteng 里那套 wContour 1.6.1 逐行移植
    （只读该包，不往它目录写任何东西）。

产物（全部在 testmap 内）：
    xunteng_html/index.html      页面
    xunteng_html/data.js         帧清单 + 色阶 + 边界（本脚本生成）
    xunteng_html/layers/*.png    各帧出图

用法：
    python build_xunteng_html.py
"""

import json
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'xunteng_html')
LAYERS_DIR = os.path.join(OUT, 'layers')

# 只读引用项目里的移植实现
PROJECT = r'E:\work\zj_official_test'
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# matplotlib 的缓存目录默认在用户目录（当前沙箱只允许写 testmap），指到本地
os.environ.setdefault('MPLCONFIGDIR', os.path.join(HERE, '.mplcache'))

from precipitation_xunteng import eqs_algorithm as eqs            # noqa: E402
from precipitation_xunteng import xunteng_reference as xr          # noqa: E402
from precipitation_xunteng.layer_config import LAYERS              # noqa: E402

LAYER = 'XTSKJSXS'
SIZE = 1024                    # 页面里用的位图尺寸（参考代码本身是 256）
UNDEF = xr.UNDEF_DATA


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------

def find_input():
    """testmap 里那个接口返回 JSON。"""
    for f in sorted(os.listdir(HERE)):
        if f.lower().endswith('.json') and 'precipitation_layers' in f:
            return os.path.join(HERE, f)
    raise SystemExit('没找到接口返回 JSON（*precipitation_layers*.json）')


def load_data(path):
    with open(path, encoding='utf-8') as f:
        j = json.load(f)
    resp = j['response'] if isinstance(j.get('response'), dict) else j
    return resp['data']


# ---------------------------------------------------------------------------
# 行政区轮廓（WKT -> 环坐标数组）
# ---------------------------------------------------------------------------

def boundary_rings(area_wkt, tol=0.0):
    """把 groups[].area 的 MULTIPOLYGON 转成环坐标数组，供 SVG 画轮廓。

    这里 tol=0（不简化）：实测这个边界主环一共 293 点，全带上也就几 KB，
    简化反而会让轮廓变得认不出来（tol=0.003 只剩 22 点）。
    """
    if not area_wkt:
        return []
    try:
        import shapely
    except ImportError:
        return []
    geom = shapely.from_wkt(area_wkt)
    if tol:
        geom = geom.simplify(tol, preserve_topology=True)
    parts = list(geom.geoms) if geom.geom_type.startswith('Multi') else [geom]
    rings = []
    for p in parts:
        rings.append([[round(x, 5), round(y, 5)] for x, y in p.exterior.coords])
    rings.sort(key=len, reverse=True)
    return rings


# ---------------------------------------------------------------------------
# 出图
# ---------------------------------------------------------------------------

def render_frame(data, target_ms, color_str, suffix=''):
    Z, xs, ys, _ = eqs.extract_frame(data, target_ms)
    matrix = Z.tolist()
    n_nan = 0
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v != v:
                matrix[i][j] = UNDEF
                n_nan += 1
    x_axis = [float(v) for v in xs]
    y_axis = [float(v) for v in ys]
    bbox = xr.frame_bbox(x_axis, y_axis)

    breaks, colors = xr.parse_legend_color_map(color_str)
    # 注意 wContour 会就地给 S0 加 dShift，传拷贝
    polys, _info = xr.equi_surface_from_grid([r[:] for r in matrix],
                                             x_axis, y_axis, breaks, False)
    dt = datetime.datetime.fromtimestamp(target_ms / 1000)
    name = f'{LAYER}_{dt:%Y%m%d_%H%M}{suffix}.png'
    path = os.path.join(LAYERS_DIR, name)
    n_drawn = xr.get_map_content(polys, {'bbox': bbox, 'width': SIZE, 'height': SIZE},
                                 path, breaks, colors, 1.0)

    valid = [v for row in matrix for v in row if v != UNDEF]
    return {
        'time': dt.strftime('%Y-%m-%d %H:%M'),
        'label': dt.strftime('%H:%M'),
        'png': 'layers/' + name,
        'bbox': bbox,
        'cols': len(x_axis), 'rows': len(y_axis),
        'vmin': (min(valid) if valid else None),
        'vmax': (max(valid) if valid else None),
        'vmean': (sum(valid) / len(valid) if valid else None),
        'nPolygons': len(polys), 'nDrawn': n_drawn, 'nNan': n_nan,
    }


def main():
    os.makedirs(LAYERS_DIR, exist_ok=True)

    src = find_input()
    data = load_data(src)
    meta = LAYERS[LAYER]
    print(f'输入: {os.path.basename(src)}')
    print(f'图层: {LAYER} {meta["name"]}（{data.get("unit")}）')

    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])
    labels = meta.get('legendLabels') or [str(b) for b in breaks]
    order = meta.get('legendOrder', 'desc')

    frames_ms = sorted({r['dataTime'] for r in data['rowsList']})
    print(f'帧: {len(frames_ms)} 个')

    # 最低档透明时另出一张"显示版"
    alt_str = None
    shown = meta.get('showFirstBand')
    if shown:
        obj = json.loads(meta['colorStr'])
        lowest = min(obj, key=lambda s: float(s))
        if obj[lowest].upper().endswith('00'):
            obj[lowest] = shown
            alt_str = json.dumps({k: obj[k] for k in sorted(obj, key=float)},
                                 ensure_ascii=False)

    frames = []
    for t in frames_ms:
        fr = render_frame(data, t, meta['colorStr'])
        if alt_str:
            fr['pngWhite'] = render_frame(data, t, alt_str, suffix='_white')['png']
        frames.append(fr)
        print(f"  {fr['time']}  {fr['cols']}x{fr['rows']} 格网  "
              f"值 {fr['vmin']:.2f}~{fr['vmax']:.2f}  "
              f"多边形 {fr['nPolygons']}  填色 {fr['nDrawn']}  -> {fr['png']}")

    rings = boundary_rings((data.get('groups') or [{}])[0].get('area'))
    print(f'行政边界: {len(rings)} 个环，主环 {len(rings[0]) if rings else 0} 点')

    # 视野 = 出图范围与边界范围的并集（留一点边）
    xs_all = [f['bbox'] for f in frames]
    view = [min(b[0] for b in xs_all), min(b[1] for b in xs_all),
            max(b[2] for b in xs_all), max(b[3] for b in xs_all)]
    for r in rings:
        for x, y in r:
            view[0] = min(view[0], x); view[1] = min(view[1], y)
            view[2] = max(view[2], x); view[3] = max(view[3], y)

    payload = {
        'layer': LAYER,
        'title': meta['name'],
        'unit': data.get('unit') or meta.get('unit') or '',
        'engine': 'wcontour-1.6.1-port（与原始 Java 逐行等价）',
        'source': os.path.basename(src),
        'legend': {'breaks': [float(b) for b in breaks], 'colors': list(colors),
                   'labels': list(labels), 'order': order},
        'frames': frames,
        'boundary': rings,
        'view': view,
        'size': SIZE,
        'whiteLabel': '把 0~0.1 档显示为白色',
    }
    with open(os.path.join(OUT, 'data.js'), 'w', encoding='utf-8') as f:
        f.write('window.XT = ')
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
        f.write(';\n')
    print(f'\n页面数据: {os.path.join(OUT, "data.js")}')
    print(f'打开    : {os.path.join(OUT, "index.html")}')


if __name__ == '__main__':
    main()
