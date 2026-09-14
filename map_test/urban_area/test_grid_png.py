# -*- coding: utf-8 -*-
"""
test_grid_png.py —— 迅腾参考算法（`equiSurfaceImg` 段 B）出图测试程序。

它做什么
========
读接口返回结果文件夹里的 JSON（`/api/v1/upns/precipitation/layers` 的原始响应），
取出 8.28 00:00~12:00 北京每个整点时刻的格网，按参考 Java 的 `finishFromGrid` 链路出图：

    格网 → 解析色阶断点 → 由坐标轴求 bbox
         → 等值面追踪(tracingBorders/tracingContourLines/smoothLines/tracingPolygons)
         → 按区间填色(ECQL 的 >= / < 规则)
         → WGS84 线性映射渲染 256x256 PNG

等值面追踪是 `wcontour/` 里对 wContour 1.6.1 的**逐行移植**，已用原始 Java 编译运行
导出的多边形做过全阶段按位对拍（见 `tools/README.md`）。

用法
====
    # 默认：自动扫描 responses/ 与 data/raw/ 下所有 JSON，出 XTSKJSXS 的 00:00~12:00
    uv run python -m precipitation_xunteng.test_grid_png

    # 指定接口返回文件
    uv run python -m precipitation_xunteng.test_grid_png ^
        --input "responses\\降水页_..._api_v1_upns_precipitation_layers.json"

    # 按行政边界裁剪 + 多图层 + 输出 4 倍预览图
    uv run python -m precipitation_xunteng.test_grid_png --clip --layer XTSKJSXS XTSKPWV --preview

产物
====
    <outdir>/<layer>_<日期>_<HHMM>.png          256x256，与参考代码同尺寸
    <outdir>/<layer>_<日期>_<HHMM>.meta.json    该帧的参数与统计
    <outdir>/<layer>_<日期>_<HHMM>_preview.png  可选，放大预览（便于肉眼看色带）
    <outdir>/report.md / index.html             本次运行的汇总
"""

import argparse
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jingyao_test.Urban_area import eqs_algorithm as eqs                    # noqa: E402
from jingyao_test.Urban_area import xunteng_reference as xr                  # noqa: E402
from jingyao_test.Urban_area.layer_config import LAYERS                      # noqa: E402

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
DEFAULT_INPUT_DIRS = [os.path.join(PROJECT_DIR, 'responses'),
                      os.path.join(PACKAGE_DIR, 'data', 'raw')]
DEFAULT_OUT_DIR = os.path.join(PACKAGE_DIR, 'output', 'xunteng_png')


# ---------------------------------------------------------------------------
# 输入发现与解析
# ---------------------------------------------------------------------------

def discover_inputs(explicit):
    """返回待处理的 json 文件列表。显式给了 --input 就只用它。"""
    if explicit:
        files = []
        for p in explicit:
            if os.path.isdir(p):
                files += [os.path.join(p, f) for f in sorted(os.listdir(p))
                          if f.lower().endswith('.json')]
            elif os.path.isfile(p):
                files.append(p)
            else:
                print(f'!! 输入不存在: {p}')
        return files
    files = []
    for d in DEFAULT_INPUT_DIRS:
        if os.path.isdir(d):
            files += [os.path.join(d, f) for f in sorted(os.listdir(d))
                      if f.lower().endswith('.json')]
    return files


def load_payload(path):
    """
    读一层接口返回，返回 data 字典或 None。

    兼容两种落盘格式：
      * 抓包/结果文件夹：{"title":..., "response": {"code":200, "data": {...}}}
      * fetch_layers 缓存：{"code":200, "data": {...}}
    """
    try:
        with open(path, encoding='utf-8') as f:
            j = json.load(f)
    except Exception as e:
        print(f'!! 读取失败 {os.path.basename(path)}: {e}')
        return None
    if isinstance(j.get('response'), dict):
        resp = j['response']
    elif 'data' in j:
        resp = j
    else:
        return None
    if resp.get('code') not in (200, '200', None):
        print(f'!! 接口返回 code={resp.get("code")} msg={resp.get("msg")} '
              f'({os.path.basename(path)})')
        return None
    data = resp.get('data')
    if not isinstance(data, dict) or 'rowsList' not in data:
        return None
    return data


def frame_ms_list(data):
    return sorted({r['dataTime'] for r in (data.get('rowsList') or [])})


# ---------------------------------------------------------------------------
# 单帧出图
# ---------------------------------------------------------------------------

def render_frame(layer, data, target_ms, out_dir, clip, size, preview_size,
                 show_first_band, tag=''):
    """跑一帧，返回统计字典。"""
    meta = LAYERS.get(layer) or {}
    color_str = meta.get('colorStr')
    if not color_str:
        return dict(ok=False, error=f'图层 {layer} 未在 layer_config.LAYERS 里配置 colorStr')
    if show_first_band and meta.get('showFirstBand') and '00' in color_str:
        color_str = color_str.replace(str(meta['showFirstBand']) + '00',
                                      str(meta['showFirstBand']))

    Z, xs, ys, notes = eqs.extract_frame(data, target_ms)
    matrix = Z.tolist()
    # 接口里的 null 会被 extract_frame 变成 NaN；参考算法的缺测值是 -9999.0
    n_nan = 0
    for i, row in enumerate(matrix):
        for j, v in enumerate(row):
            if v != v:                       # NaN
                matrix[i][j] = xr.UNDEF_DATA
                n_nan += 1
    x_axis = [float(v) for v in xs]
    y_axis = [float(v) for v in ys]

    dt = datetime.datetime.fromtimestamp(target_ms / 1000)
    name = f'{layer}_{dt:%Y-%m-%d_%H%M}{tag}'
    bbox = xr.frame_bbox(x_axis, y_axis)

    area_wkt = None
    if clip:
        groups = data.get('groups') or []
        if groups and groups[0].get('area'):
            area_wkt = groups[0]['area']
        else:
            clip = False

    t0 = time.time()
    # 注意：wContour 的 createContourLines_UndefData 会给 S0 **就地**加一个 dShift
    # （contour[0]*1e-5，contour[0]==0 时取 1e-5），Java 原版也是改调用方数组。
    # 所以统计与预览都用拷贝，避免统计被 +1e-5 污染、预览被重复加两次。
    res = xr.finish_from_grid([row[:] for row in matrix], x_axis, y_axis, name, layer,
                              clip, color_str, out_dir, True, len(y_axis), len(x_axis),
                              len(matrix) * len(matrix[0]),
                              clip_wkt=area_wkt)
    elapsed = time.time() - t0

    valid = [v for row in matrix for v in row if v != xr.UNDEF_DATA]
    stats = dict(
        ok=True, layer=layer, layerName=meta.get('name', layer),
        unit=data.get('unit', ''), time=dt.strftime('%Y-%m-%d %H:%M'),
        target_ms=target_ms, cols=len(x_axis), rows=len(y_axis),
        bbox=bbox, clip=bool(clip), n_nan_filled=n_nan,
        n_valid=len(valid),
        vmin=(min(valid) if valid else None), vmax=(max(valid) if valid else None),
        vmean=(sum(valid) / len(valid) if valid else None),
        n_polygons=res.n_polygons, n_drawn=res.n_drawn,
        img=res.img, elapsed=round(elapsed, 3),
        breaks=[float(b) for b in xr.parse_legend_color_map(color_str)[0]],
        notes=notes,
    )

    # 预览图（参考代码只出 256，这里额外出一张大图方便肉眼看色带）
    if preview_size and preview_size > 0:
        polys, _ = xr.equi_surface_from_grid([row[:] for row in matrix], x_axis, y_axis,
                                             stats['breaks'], clip, clip_wkt=area_wkt)
        breaks, colors = xr.parse_legend_color_map(color_str)
        prev = os.path.join(out_dir, name + f'_preview{preview_size}.png')
        xr.get_map_content(polys, {'bbox': bbox, 'width': preview_size,
                                   'height': preview_size}, prev, breaks, colors, 1.0)
        stats['preview'] = prev

    with open(os.path.join(out_dir, name + '.meta.json'), 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    return stats


# ---------------------------------------------------------------------------
# 汇总输出
# ---------------------------------------------------------------------------

def write_report(entries, out_dir, args, inputs):
    lines = ['# 迅腾参考算法出图测试报告（段 B：接口格网 → 等值面填色 → 256×256 PNG）', '',
             f'- 运行时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}',
             f'- 输入文件: ' + ', '.join(os.path.basename(p) for p in inputs),
             f'- 图层: {", ".join(args.layer)}',
             f'- 时刻范围: {args.hour_start:02d}:00 ~ {args.hour_end:02d}:00',
             f'- 行政边界裁剪: {"开" if args.clip else "关"}',
             f'- 输出目录: {out_dir}', '']
    ok = [e for e in entries if e.get('ok')]
    bad = [e for e in entries if not e.get('ok')]
    lines += [f'共 {len(entries)} 帧：成功 {len(ok)}，失败 {len(bad)}', '']

    if ok:
        lines += ['| 图层 | 时刻 | 格网 | 值范围 | 多边形 | 已填色 | bbox | 图 |',
                  '|---|---|---|---|---|---|---|---|']
        for e in ok:
            rng = ('-' if e['vmin'] is None else
                   f"{e['vmin']:.2f} ~ {e['vmax']:.2f}")
            lines.append(
                f"| {e['layer']} | {e['time']} | {e['cols']}×{e['rows']} | {rng} | "
                f"{e['n_polygons']} | {e['n_drawn']} | "
                f"[{e['bbox'][0]:.4f},{e['bbox'][1]:.4f},{e['bbox'][2]:.4f},{e['bbox'][3]:.4f}] | "
                f"[{os.path.basename(e['img'])}]({os.path.basename(e['img'])}) |")
        lines.append('')
    for e in bad:
        lines.append(f"- 失败：{e.get('layer')} {e.get('time', '')} — {e.get('error')}")

    with open(os.path.join(out_dir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    cards = []
    for e in ok:
        img = os.path.basename(e['img'])
        big = os.path.basename(e['preview']) if e.get('preview') else img
        cards.append(
            f'<div class="card"><div class="hd">{e["layer"]} · {e["time"]}</div>'
            f'<img src="{img}" data-big="{big}">'
            f'<div class="ft">{e["cols"]}×{e["rows"]} 格网 · {e["n_polygons"]} 多边形 · '
            f'已填色 {e["n_drawn"]} · {e["elapsed"]}s</div></div>')
    html = ('<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">'
            '<title>迅腾参考算法出图测试</title><style>'
            'body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#0f1115;color:#e6e6e6;margin:0;padding:24px}'
            'h1{font-size:18px;font-weight:600;margin:0 0 4px}p.sub{color:#8b93a1;margin:0 0 20px;font-size:13px}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(236px,1fr));gap:14px}'
            '.card{background:#171a21;border:1px solid #242a35;border-radius:10px;overflow:hidden}'
            '.hd{padding:8px 10px;font-size:13px;font-weight:600;border-bottom:1px solid #242a35}'
            '.card img{width:100%;display:block;background:repeating-conic-gradient(#20242c 0 25%,#262b34 0 50%) 0 0/16px 16px;cursor:zoom-in}'
            '.ft{padding:6px 10px;font-size:11px;color:#8b93a1}'
            '</style></head><body><h1>迅腾参考算法出图测试（段 B）</h1>'
            f'<p class="sub">等值面追踪为 wContour 1.6.1 逐行移植，已与原始 Java 输出按位对拍 · '
            f'{len(ok)} 帧 · 点击图片看放大版</p>'
            '<div class="grid">' + ''.join(cards) + '</div>'
            '<script>document.querySelectorAll(".card img").forEach(function(im){'
            'im.onclick=function(){window.open(im.dataset.big||im.src)}});</script>'
            '</body></html>')
    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(html)
    return os.path.join(out_dir, 'report.md'), os.path.join(out_dir, 'index.html')


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description='迅腾参考算法出图测试（段 B）')
    ap.add_argument('--input', nargs='+', default=None,
                    help='接口返回 JSON 文件或目录（默认自动扫 responses/ 与 data/raw/）')
    ap.add_argument('--outdir', default=DEFAULT_OUT_DIR)
    ap.add_argument('--layer', nargs='+', default=['XTSKJSXS'],
                    help='图层编码（默认 XTSKJSXS 小时降水量）')
    ap.add_argument('--date', default='2026-08-28', help='只出这一天的帧')
    ap.add_argument('--hour-start', type=int, default=0)
    ap.add_argument('--hour-end', type=int, default=12)
    ap.add_argument('--clip', action='store_true',
                    help='按接口返回的行政边界（groups[].area）裁剪等值面')
    ap.add_argument('--size', type=int, default=256, help='PNG 尺寸（参考代码写死 256）')
    ap.add_argument('--preview', nargs='?', type=int, const=1024, default=0,
                    help='额外输出放大预览图，默认 1024（不带该参数则不出）')
    ap.add_argument('--show-first-band', action='store_true',
                    help='把第一档（如 0~0.1 的透明色）显示成不透明色')
    ap.add_argument('--band-mode', choices=['auto', 'low', 'high'], default='auto',
                    help='色带选取：auto=按 IsHighCenter 判在等值线之上/之下（默认，出图正确）；'
                         'low/high=直接用 LowValue/HighValue 走 ECQL 区间规则')
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 帧（调试用）')
    args = ap.parse_args(argv)

    xr.BAND_MODE = args.band_mode

    os.makedirs(args.outdir, exist_ok=True)
    inputs = discover_inputs(args.input)
    if not inputs:
        print('!! 没有找到输入 JSON，请用 --input 指定接口返回文件')
        return 2
    print(f'输入 {len(inputs)} 个文件: ' + ', '.join(os.path.basename(p) for p in inputs))

    wanted = set(args.layer)
    entries = []
    seen = set()
    n_frames = 0
    for path in inputs:
        data = load_payload(path)
        if data is None:
            continue
        layer = data.get('layer')
        if layer not in wanted:
            continue
        for t in frame_ms_list(data):
            dt = datetime.datetime.fromtimestamp(t / 1000)
            if dt.strftime('%Y-%m-%d') != args.date:
                continue
            if not (args.hour_start <= dt.hour <= args.hour_end):
                continue
            key = (layer, t)
            if key in seen:
                continue
            seen.add(key)
            n_frames += 1
            if args.limit and n_frames > args.limit:
                break
            try:
                st = render_frame(layer, data, t, args.outdir, args.clip, args.size,
                                  args.preview, args.show_first_band)
            except Exception as e:
                import traceback
                traceback.print_exc()
                st = dict(ok=False, layer=layer, time=dt.strftime('%Y-%m-%d %H:%M'),
                          error=f'{type(e).__name__}: {e}')
            entries.append(st)
            if st.get('ok'):
                print(f"  [OK] {st['layer']} {st['time']}  "
                      f"{st['cols']}x{st['rows']} 格网  值 {st['vmin']:.2f}~{st['vmax']:.2f}  "
                      f"多边形 {st['n_polygons']}  已填色 {st['n_drawn']}  "
                      f"{st['elapsed']}s  -> {os.path.basename(st['img'])}")
            else:
                print(f"  [FAIL] {st.get('layer')} {st.get('time','')} {st.get('error')}")

    if not entries:
        print('!! 没有匹配到任何数据帧（检查 --layer / --date / --hour-range）')
        return 1

    rep, idx = write_report(entries, args.outdir, args, inputs)
    ok = sum(1 for e in entries if e.get('ok'))
    print(f'\n完成 {ok}/{len(entries)} 帧')
    print(f'报告: {rep}\n索引: {idx}')
    return 0 if ok == len(entries) else 1


if __name__ == '__main__':
    sys.exit(main())
