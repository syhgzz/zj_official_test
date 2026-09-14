# -*- coding: utf-8 -*-
"""
build_single_html.py —— 一次运行，把**所有东西**打包成一个自包含 HTML。

和 testmap 里另外两个脚本的关系：

    map_test_view.py        在线版：叠高德底图，但页面拆成 index.html + data.js
                            + layers/*.png —— 必须起静态服务才能看
    build_xunteng_html.py   离线版：不依赖任何外网，同样拆成三个文件
    本脚本                  两者合一：底图/兜底/色阶面板照搬在线版，
                            但 PNG 走 base64、帧数据和 Key 内联，
                            产物**只有一个 .html**，双击就能开

「所有的一起」指同一页里能同时看到三样东西：
    1024 叠加版（叠底图） / 1024 显示版（0~0.1 档画白） / 256 参考原尺寸版
后两者原来要么靠勾选框切换、要么根本没进页面，现在侧栏里可以直接对拍。

产物（全部在 testmap 内）：
    single_html/index.html   唯一个文件，双击可开

用法：
    python build_single_html.py
    python build_single_html.py --date 2026-08-28 --out E:\\somewhere\\precip.html
"""

import argparse
import base64
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = r'E:\work\zj_official_test'
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
os.environ.setdefault('MPLCONFIGDIR', os.path.join(HERE, '.mplcache'))

from precipitation_xunteng import eqs_algorithm as eqs            # noqa: E402
from precipitation_xunteng import xunteng_reference as xr          # noqa: E402
from precipitation_xunteng.layer_config import LAYERS              # noqa: E402

TEMPLATE = os.path.join(HERE, 'map_view_template.html')
WMTS_CONFIG = os.path.join(PROJECT, 'wmts_demo', 'wmts_map_config.js')
DEFAULT_OUT = os.path.join(HERE, 'single_html', 'index.html')

LAYER = 'XTSKJSXS'
SIZE = 1024                   # 页面主视图尺寸（参考代码本身是 256）
REFERENCE_SIZE = 256          # 原版 getMapContent 写死的尺寸，单列出来对拍
UNDEF = xr.UNDEF_DATA

# 模板里的注入点。故意做成 HTML 注释而不是占位符：万一模板被别的脚本
# 单独用了，注释留在产物里也无害，标记本身不会渲染出来。
MARK_DATA = '<!--{{SINGLE_HTML_DATA}}-->'
MARK_CFG = '<!--{{SINGLE_HTML_CONFIG}}-->'


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------

def find_input(explicit=None):
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
    """groups[].area（MULTIPOLYGON WKT）-> 环坐标数组，供离线轮廓视图。"""
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


# ---------------------------------------------------------------------------
# 出图
# ---------------------------------------------------------------------------

def render(data, target_ms, color_str, size, layers_dir, suffix=''):
    """跑参考算法的段 B 出图，返回这一帧的元信息；png 字段是内联用的 data URI。"""
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

    breaks, colors = xr.parse_legend_color_map(color_str)
    bbox = xr.frame_bbox(x_axis, y_axis)
    # wContour 会就地给 S0 加 dShift，传拷贝
    polys, _info = xr.equi_surface_from_grid([r[:] for r in matrix],
                                             x_axis, y_axis, breaks, False)

    dt = datetime.datetime.fromtimestamp(target_ms / 1000)
    name = f'{LAYER}_{dt:%Y%m%d_%H%M}_{size}{suffix}.png'
    path = os.path.join(layers_dir, name)
    n_drawn = xr.get_map_content(polys, {'bbox': bbox, 'width': size, 'height': size},
                                 path, breaks, colors, 1.0)

    valid = [v for row in matrix for v in row if v != UNDEF]
    return {
        'time': dt.strftime('%Y-%m-%d %H:%M'), 'label': dt.strftime('%H:%M'),
        'dtms': target_ms, 'png': png_data_uri(path), 'bbox': bbox,
        'cols': len(x_axis), 'rows': len(y_axis),
        'vmin': min(valid) if valid else None, 'vmax': max(valid) if valid else None,
        'vmean': (sum(valid) / len(valid)) if valid else None,
        'nPolygons': len(polys), 'nDrawn': n_drawn, 'nNan': n_nan,
        '_file': name,
    }


def png_data_uri(path):
    """PNG -> data URI。页面里 ImageLayer 和 <img>.src 都只吃 URL 字符串，
    换成 data URI 后模板的渲染代码一行都不用改。"""
    with open(path, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')


def png_size(path):
    return os.path.getsize(path) if os.path.exists(path) else 0


# ---------------------------------------------------------------------------
# 打包
# ---------------------------------------------------------------------------

def js_safe(obj):
    """JSON 里内嵌进 <script> 时的安全化。

    只需要挡 `</script` 和 `<!--`：前者会提前结束脚本块，后者会开启
    HTML 注释态。其余字符在 <script> 里都是合法的（包括中文）。
    """
    s = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return s.replace('</', '<\\/').replace('<!--', '<\\!--')


def build_html(payload, cfg_text, template_path):
    """把数据/凭证注入模板。

    注入点不在了也能跑：那说明数据已经烘进文件本体（模板即成品），
    这时直接原样用它，不再重复注入。

    凭证的注入点在模板的 `if (window.WMTS_MAP_CONFIG) return;` 之后，所以
    这里注入的是"内层内容"：有凭证就直接赋值，没有就让它在同目录找外部文件
    （file:// 下会静默失败，但不影响页面）。
    """
    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    if MARK_DATA not in html:
        print('  （模板里没有数据注入点，按"数据已烘进文件"处理，原样输出）')
    else:
        html = html.replace(MARK_DATA, '<script>window.XT=' + js_safe(payload) + ';</script>')

    if MARK_CFG in html:
        if cfg_text:
            inner = '\n  ' + cfg_text.strip() + '\n'
        else:
            inner = ("\n  var s = document.createElement('script');\n"
                     "  s.src = './wmts_map_config.js';\n"
                     "  s.onerror = function () { window.WMTS_MAP_CONFIG = null; };\n"
                     "  document.head.appendChild(s);\n")
        html = html.replace(MARK_CFG, inner)
    return html


def main(argv=None):
    ap = argparse.ArgumentParser(description='把全部产物打包成一个自包含 HTML')
    ap.add_argument('--input', default=None, help='接口返回 JSON（默认取本文件夹里的）')
    ap.add_argument('--date', default=None, help='只出这一天（默认全部帧）')
    ap.add_argument('--out', default=DEFAULT_OUT, help='输出的 .html 路径')
    ap.add_argument('--inplace', action='store_true',
                    help='把数据直接烘进 map_view_template.html 本体（模板即成品）')
    ap.add_argument('--keep-layers', action='store_true',
                    help='保留过程中生成的 PNG（默认构建完删掉，省得留一堆中间文件）')
    args = ap.parse_args(argv)

    src = find_input(args.input)
    data = load_data(src)
    meta = LAYERS[LAYER]
    print(f'输入: {os.path.basename(src)}')
    print(f'图层: {LAYER} {meta["name"]}（{data.get("unit")}）')

    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])
    labels = meta.get('legendLabels') or [str(b) for b in breaks]

    # 最低档透明时另出一张"显示版"（0~0.1 档画成白色）
    alt_str, shown = None, meta.get('showFirstBand')
    if shown:
        obj = json.loads(meta['colorStr'])
        lowest = min(obj, key=lambda s: float(s))
        if obj[lowest].upper().endswith('00'):
            obj[lowest] = shown
            alt_str = json.dumps({k: obj[k] for k in sorted(obj, key=float)},
                                 ensure_ascii=False)

    frames_ms = sorted({r['dataTime'] for r in data['rowsList']})
    if args.date:
        frames_ms = [t for t in frames_ms
                     if datetime.datetime.fromtimestamp(t / 1000).strftime('%Y-%m-%d') == args.date]
    if not frames_ms:
        raise SystemExit('没有匹配的帧（检查 --date）')
    print(f'帧: {len(frames_ms)} 个，主视图 {SIZE}px + 参考 {REFERENCE_SIZE}px')

    out_path = os.path.abspath(args.out)
    layers_dir = os.path.join(os.path.dirname(out_path), '_layers_tmp')
    os.makedirs(layers_dir, exist_ok=True)

    frames = []
    raw_bytes = 0
    for t in frames_ms:
        fr = render(data, t, meta['colorStr'], SIZE, layers_dir)
        raw_bytes += png_size(os.path.join(layers_dir, fr['_file']))
        if alt_str:
            fr['pngWhite'] = render(data, t, alt_str, SIZE, layers_dir, suffix='_white')['png']
        r256 = render(data, t, meta['colorStr'], REFERENCE_SIZE, layers_dir)
        fr['png256'] = r256['png']
        raw_bytes += png_size(os.path.join(layers_dir, r256['_file']))
        if alt_str:
            w = render(data, t, alt_str, REFERENCE_SIZE, layers_dir, suffix='_white')
            fr['png256White'] = w['png']
        del fr['_file']
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
        'layer': LAYER, 'title': meta['name'],
        'unit': data.get('unit') or meta.get('unit') or '',
        'engine': 'wContour 1.6.1 逐行移植（与原始 Java 5 阶段按位一致）',
        'note': '等值面追踪 → 区间填色 → 渲染（段 B）',
        'source': os.path.basename(src),
        'legend': {'breaks': [float(b) for b in breaks], 'colors': list(colors),
                   'labels': list(labels), 'order': meta.get('legendOrder', 'desc')},
        'frames': frames, 'boundary': rings, 'view': view,
        'size': SIZE, 'referenceSize': REFERENCE_SIZE,
        'selfContained': True,
    }

    cfg_text = ''
    if os.path.exists(WMTS_CONFIG):
        with open(WMTS_CONFIG, encoding='utf-8') as f:
            cfg_text = f.read()
    else:
        print(f'!! 没找到 {WMTS_CONFIG}，页面底图不可用（会退到离线视图）')

    html = build_html(payload, cfg_text, TEMPLATE)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    if args.inplace:
        # 模板即成品：把同一份内容写回模板本体
        with open(TEMPLATE, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'\n已烘进模板: {TEMPLATE}（该文件现在双击即可打开）')

    if not args.keep_layers:
        for fn in os.listdir(layers_dir):
            os.remove(os.path.join(layers_dir, fn))
        os.rmdir(layers_dir)

    size_kb = os.path.getsize(out_path) / 1024
    print(f'\n单文件 : {out_path}')
    print(f'体积   : {size_kb:,.0f} KB'
          f'（源 PNG {raw_bytes/1024:,.0f} KB，base64 后约 {raw_bytes*4/3/1024:,.0f} KB）')
    print('打开   : 直接双击这个 .html 就行 —— 不需要静态服务')
    print('         联网时显示高德底图；没网或 Key 失效会自动退回「经纬网+轮廓」视图')
    return 0


if __name__ == '__main__':
    sys.exit(main())
