# -*- coding: utf-8 -*-
"""
algo_compare.py —— 算法对算法对比（完全不依赖截图）

对比双方（输入完全一致：同一时刻、同一区域的站点散点 + 同一色阶）
    我的实验算法  my ：站点散点 → 包围盒±0.07° → 1km 格网 → IDW(k近邻) → 等值面填色 → PNG
    讯腾实时算法  xt ：平台服务端实时降水场（/api/v1/upns/precipitation/layers 返回的格网）→ 同色阶出图

量化对比（都在程序里算，不用肉眼看图）
    1) 公共格网场差：把两套算法的场双线性采样到同一评估格网（两 bbox 交集，约 1km）
       → RMSE / MAE / 偏差 / 相关系数 / 色阶分类一致率
    2) 站点交叉验证：我的算法做留一法（LOO，用其余站点预测该站点）
       讯腾格网直接在站点位置取值 → 两者对站点实测值的 RMSE / MAE / 偏差
    3) 差值场：my - xt 的填色图（零值带透明），一眼看出两套算法差在哪、差多少

用法
    uv run python -m precipitation_xunteng.algo_compare --layer XTSKPWV --hour 12
    uv run python -m precipitation_xunteng.algo_compare --layer XTSKJSXS --hour 12 --k 6 --power 2
    uv run python -m precipitation_xunteng.algo_compare --layer XTSKPWV --hour 12 --no-fetch
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

from jingyao_test.Urban_area import eqs_algorithm as eqs
from jingyao_test.Urban_area.fetch_layers import fetch_layer, ms
from jingyao_test.Urban_area.layer_config import LAYERS
from jingyao_test.Urban_area.run_compare import (DATA_DIR, PACKAGE_DIR, load_cache,
                                               station_series)

# 差值场色阶：[-∞,-5) 蓝 → 0 附近透明 → [5,∞) 红
DIFF_COLOR_STR = json.dumps({
    '-999': '#313695', '-5': '#74add1', '-2': '#abd9e9',
    '-0.5': '#ffffff00', '0.5': '#fdae61', '2': '#f46d43', '5': '#a50026',
}, ensure_ascii=False)


# -----------------------------------------------------------------------------
# 输入：站点散点（任意时刻，从缓存序列里取）
# -----------------------------------------------------------------------------


def series_value_at(series, dt_ms, tol_ms=None):
    """从站点历史序列里取 dt_ms 最近时刻的值（可选容差）。"""
    if not series or not series.get('timestamps'):
        return None
    ts = series['timestamps']
    idx = min(range(len(ts)), key=lambda i: abs(ts[i] - dt_ms))
    if tol_ms is not None and abs(ts[idx] - dt_ms) > tol_ms:
        return None
    values = series.get('values') or []
    return values[idx] if idx < len(values) else None


def load_stations(client, bbox):
    """取区域内的降水监测站列表。"""
    resp = client.request('GET', '/api/v1/upns/stations',
                          params={'pageNum': 1, 'pageSize': 500,
                                  'minLng': bbox[0], 'maxLng': bbox[1],
                                  'minLat': bbox[2], 'maxLat': bbox[3]})
    stations = ((resp or {}).get('data') or {}).get('stations') or []
    return stations


def warm_station_series(client, stations, metric, max_dt_ms, cache_dir):
    """预热站点历史缓存，使其覆盖到 max_dt_ms（之后逐帧查询都命中缓存）。"""
    ok = 0
    for s in stations:
        code = s.get('stationCode')
        if not code:
            continue
        if station_series(client, code, metric, max_dt_ms, cache_dir):
            ok += 1
    print(f'  站点历史预热: {ok}/{len(stations)} 站（覆盖到 '
          f'{datetime.fromtimestamp(max_dt_ms / 1000):%H:%M}）')


def load_scatter(client, stations, metric, dt_ms, cache_dir, tol_ms=30 * 60 * 1000,
                 fallback_field=None):
    """
    拼 txt 语义的散点 trainData：[[l, b, v], ...]（站点位置 + 该时刻实测值）。

    站点历史接口缺少该要素时（实测 rain 全为 null），若给出 fallback_field
    =(Z, xs, ys)（平台场），则用平台场在站点位置取值作为兜底散点，
    返回的 source 标记为 'platform-sampled'（对比含义变为"IDW 重建平台场"）。
    返回 (scatter, skipped, source)。
    """
    train = []
    lons, lats = [], []
    skipped = 0
    for s in stations:
        code = s.get('stationCode')
        loc = s.get('location') or {}
        l, b = loc.get('longitude'), loc.get('latitude')
        if not code or l is None or b is None:
            skipped += 1
            continue
        lons.append(float(l))
        lats.append(float(b))
        series = station_series(client, code, metric, dt_ms, cache_dir)
        v = series_value_at(series, dt_ms, tol_ms=tol_ms)
        if v is None:
            skipped += 1
            continue
        train.append([float(l), float(b), float(v)])

    if not train and fallback_field is not None:
        Zf, xsf, ysf = fallback_field
        if lons:
            vals = sample_bilinear(Zf, xsf, ysf, np.asarray(lons), np.asarray(lats),
                                   pointwise=True)
            for l, b, v in zip(lons, lats, vals):
                if np.isfinite(v):
                    train.append([l, b, float(v)])
        if train:
            return np.asarray(train, dtype=float), skipped, 'platform-sampled'

    if not train:
        raise ValueError(f'有效插值点为空（站点历史无 {metric} 数据）')
    return np.asarray(train, dtype=float), skipped, 'station-history'


# -----------------------------------------------------------------------------
# 我的实验算法（可调参）
# -----------------------------------------------------------------------------


def my_algorithm_field(scatter, cell_km=1.0, k=3, power=2.0, pad=0.07):
    """txt 步骤 1~4 的等价实现：外扩 0.07° → 1km 格网 → IDW(k 近邻, power)。"""
    lons, lats, vals = scatter[:, 0], scatter[:, 1], scatter[:, 2]
    west, south, east, north = eqs.expand_bbox(
        float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max()), pad)
    cols, rows = eqs.grid_size_from_km(west, south, east, north, cell_km)
    xs, ys = eqs.create_grid_xy(west, south, east, north, cols, rows)
    Z = eqs.idw_neighbor(scatter, xs, ys, k=k, power=power)
    return Z, xs, ys


def xt_algorithm_field(data, dt_ms):
    """讯腾实时算法的场：平台服务端返回的格网。"""
    Z, xs, ys, notes = eqs.extract_frame(data, dt_ms)
    return Z, np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)


# -----------------------------------------------------------------------------
# 公共评估格网 + 指标
# -----------------------------------------------------------------------------


def build_eval_grid(bbox, cell_km=1.0):
    """在两 bbox 交集上建约 cell_km 的评估格网。"""
    cols, rows = eqs.grid_size_from_km(bbox[0], bbox[1], bbox[2], bbox[3], cell_km)
    xs = np.linspace(bbox[0], bbox[2], max(cols, 2))
    ys = np.linspace(bbox[1], bbox[3], max(rows, 2))
    return xs, ys


def sample_bilinear(Z, xs, ys, xq, yq, pointwise=False):
    """
    规则格网双线性采样（超出范围返回 nan）。
    pointwise=False：xq/ys 为坐标轴，返回 (len(yq), len(xq)) 格网；
    pointwise=True ：xq/yq 为逐点坐标，返回与 xq 同形状。
    """
    if pointwise:
        X, Y = np.asarray(xq, dtype=float), np.asarray(yq, dtype=float)
    else:
        X, Y = np.meshgrid(xq, yq)
    Z = np.asarray(Z, dtype=float)
    out = np.full(X.shape, np.nan, dtype=float)
    inside = (X >= xs[0]) & (X <= xs[-1]) & (Y >= ys[0]) & (Y <= ys[-1])
    if not inside.any():
        return out
    i = np.clip(np.searchsorted(xs, X[inside], side='right') - 1, 0, len(xs) - 2)
    j = np.clip(np.searchsorted(ys, Y[inside], side='right') - 1, 0, len(ys) - 2)
    x0, x1 = xs[i], xs[i + 1]
    y0, y1 = ys[j], ys[j + 1]
    wx = np.where(x1 > x0, (X[inside] - x0) / np.where(x1 > x0, x1 - x0, 1), 0.0)
    wy = np.where(y1 > y0, (Y[inside] - y0) / np.where(y1 > y0, y1 - y0, 1), 0.0)
    v00 = Z[j, i]
    v10 = Z[j, i + 1]
    v01 = Z[j + 1, i]
    v11 = Z[j + 1, i + 1]
    with np.errstate(invalid='ignore'):
        v = (v00 * (1 - wx) * (1 - wy) + v10 * wx * (1 - wy)
             + v01 * (1 - wx) * wy + v11 * wx * wy)
    v = np.where(np.isnan(v00) | np.isnan(v10) | np.isnan(v01) | np.isnan(v11), np.nan, v)
    out[inside] = v
    return out


def field_metrics(a, b, undef=-9999.0):
    """两场的误差指标（nan/缺测剔除）。"""
    A = np.asarray(a, dtype=float).ravel()
    B = np.asarray(b, dtype=float).ravel()
    ok = (~np.isnan(A)) & (~np.isnan(B)) & (A != undef) & (B != undef)
    A, B = A[ok], B[ok]
    if A.size < 2:
        return {'n': int(A.size), 'rmse': float('nan'), 'mae': float('nan'),
                'bias': float('nan'), 'corr': float('nan'), 'max_abs': float('nan')}
    d = A - B
    corr = float(np.corrcoef(A, B)[0, 1]) if A.std() > 0 and B.std() > 0 else float('nan')
    return {'n': int(A.size),
            'rmse': float(np.sqrt(np.mean(d ** 2))),
            'mae': float(np.mean(np.abs(d))),
            'bias': float(np.mean(d)),
            'corr': corr,
            'max_abs': float(np.max(np.abs(d)))}


def value_class(v, breaks):
    """按 txt 区间规则（value>=k_i 且 <k_{i+1}，最后一档 >=k_last）返回档位索引。"""
    idx = -1
    for i, b in enumerate(breaks):
        if v >= b:
            idx = i
    return idx


def class_agreement(a, b, breaks):
    """色阶分类一致率（两套算法落在同一色阶档位的格点比例）。"""
    A = np.asarray(a, dtype=float).ravel()
    B = np.asarray(b, dtype=float).ravel()
    ok = ~np.isnan(A) & ~np.isnan(B)
    A, B = A[ok], B[ok]
    if A.size == 0:
        return float('nan'), 0
    same = sum(1 for x, y in zip(A, B) if value_class(x, breaks) == value_class(y, breaks))
    return same / A.size, int(A.size)


def cross_validate_my(scatter, k=3, power=2.0):
    """我的算法留一法（LOO）：用其余站点预测该站点，评估其内插精度。"""
    errs = []
    n = len(scatter)
    if n < 3:
        return {'n': 0}
    for i in range(n):
        others = np.delete(scatter, i, axis=0)
        x, y, v = scatter[i]
        pred = eqs.idw_neighbor(others, np.array([x]), np.array([y]),
                                k=min(k, len(others)), power=power)[0, 0]
        errs.append(pred - v)
    errs = np.asarray(errs, dtype=float)
    return {'n': int(errs.size), 'rmse': float(np.sqrt(np.mean(errs ** 2))),
            'mae': float(np.mean(np.abs(errs))), 'bias': float(np.mean(errs)),
            'max_abs': float(np.max(np.abs(errs)))}


def validate_xt_at_stations(scatter, Zxt, xs_xt, ys_xt):
    """讯腾格网在站点位置的取值 vs 站点实测值。"""
    pred = sample_bilinear(Zxt, xs_xt, ys_xt, scatter[:, 0], scatter[:, 1], pointwise=True)
    obs = scatter[:, 2]
    ok = ~np.isnan(pred)
    if not ok.any():
        return {'n': 0}
    d = pred[ok] - obs[ok]
    return {'n': int(ok.sum()), 'rmse': float(np.sqrt(np.mean(d ** 2))),
            'mae': float(np.mean(np.abs(d))), 'bias': float(np.mean(d)),
            'max_abs': float(np.max(np.abs(d)))}


# -----------------------------------------------------------------------------
# 出图
# -----------------------------------------------------------------------------


def render_field(Z, xs, ys, breaks, colors, out_png, mask_wkt=None, size=1024):
    eqs.render_equi_surface(Z, xs, ys, breaks, colors, out_png,
                            width=size, height=size, mask_wkt=mask_wkt, undef=-9999.0)


def side_by_side(items, out_png, title):
    """items: [(png_path, label), ...]"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.image import imread

    eqs.setup_cjk_font()
    fig, axes = plt.subplots(1, len(items), figsize=(5.6 * len(items), 6))
    if len(items) == 1:
        axes = [axes]
    for ax, (path, label) in zip(axes, items):
        ax.imshow(imread(path))
        ax.set_title(label, fontsize=11)
        ax.axis('off')
    fig.suptitle(title, fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def write_html(rows, out_html, title):
    body = ''.join(rows)
    html = (f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
            f'<title>{title}</title>'
            f'<style>body{{font-family:Inter,"Microsoft YaHei",sans-serif;margin:24px;color:#172033}}'
            f'table{{border-collapse:collapse;font-size:13px}}td,th{{border:1px solid #e2e8f0;padding:6px 10px}}'
            f'img{{max-width:100%;border:1px solid #e2e8f0;border-radius:8px}}'
            f'h2{{margin-top:28px}}</style></head><body><h1>{title}</h1>{body}</body></html>')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html)


# -----------------------------------------------------------------------------
# 单帧对比（供 export_web 复用）
# -----------------------------------------------------------------------------


def compare_frame(client, layer, data, dt_ms, stations, cache_dir, args, out_dir,
                  with_metrics=True):
    """
    对某一时刻做完整对比，返回：
      {'items': {'my': {...}, 'xt': {...}, 'diff': {...}}, 'metrics': {...}}
    items 里每项含 png 相对名与 bbox（相对 out_dir）。
    """
    meta = LAYERS[layer]
    breaks, colors = eqs.parse_color_str(meta['colorStr'])
    diff_breaks, diff_colors = eqs.parse_color_str(DIFF_COLOR_STR)
    area_wkt = (data.get('groups') or [{}])[0].get('area')

    Zxt, xs_xt, ys_xt = xt_algorithm_field(data, dt_ms)
    scatter = None
    skipped = 0
    scatter_error = None
    scatter_source = None
    fallback = (Zxt, xs_xt, ys_xt) if getattr(args, 'scatter_fallback', True) else None
    try:
        scatter, skipped, scatter_source = load_scatter(
            client, stations, meta['metric'], dt_ms, cache_dir,
            tol_ms=args.tol_minutes * 60 * 1000, fallback_field=fallback)
    except Exception as e:  # 站点历史无该要素且无兜底场
        scatter_error = str(e)

    stamp = datetime.fromtimestamp(dt_ms / 1000).strftime('%H%M')
    result = {'items': {}, 'metrics': {}}

    xt_png = f'{layer}_{stamp}_xt.png'
    render_field(Zxt, xs_xt, ys_xt, breaks, colors, os.path.join(out_dir, xt_png),
                 mask_wkt=area_wkt, size=args.size)
    result['items']['xt'] = {'png': xt_png, 'bbox': eqs.frame_bbox(xs_xt, ys_xt)}

    if scatter is None:
        result['metrics'] = {'error': f'我的算法无法运行：{scatter_error}'}
        return result

    Zmy, xs_my, ys_my = my_algorithm_field(scatter, cell_km=args.cell_km,
                                           k=args.k, power=args.power)
    my_png = f'{layer}_{stamp}_my.png'
    render_field(Zmy, xs_my, ys_my, breaks, colors, os.path.join(out_dir, my_png),
                 size=args.size)
    result['items']['my'] = {'png': my_png, 'bbox': eqs.frame_bbox(xs_my, ys_my)}

    if not with_metrics:
        return result

    # 公共评估格网（两 bbox 交集）
    ibox = (max(xs_my[0], xs_xt[0]), max(ys_my[0], ys_xt[0]),
            min(xs_my[-1], xs_xt[-1]), min(ys_my[-1], ys_xt[-1]))
    exs, eys = build_eval_grid(ibox, cell_km=args.cell_km)
    Am = sample_bilinear(Zmy, xs_my, ys_my, exs, eys)
    Bm = sample_bilinear(Zxt, xs_xt, ys_xt, exs, eys)
    field = field_metrics(Am, Bm)
    agree, n_agree = class_agreement(Am, Bm, breaks)
    loo = cross_validate_my(scatter, k=args.k, power=args.power)
    xt_at_st = validate_xt_at_stations(scatter, Zxt, xs_xt, ys_xt)

    diff_png = f'{layer}_{stamp}_diff.png'
    render_field(Am - Bm, exs, eys, diff_breaks, diff_colors,
                 os.path.join(out_dir, diff_png), size=args.size)
    result['items']['diff'] = {'png': diff_png, 'bbox': list(ibox)}

    result['metrics'] = {
        'points': int(len(scatter)), 'skipped': int(skipped),
        'scatter_source': scatter_source,
        'eval_grid': [len(exs), len(eys)], 'eval_bbox': [float(v) for v in ibox],
        'field': field, 'class_agreement': agree, 'class_n': n_agree,
        'loo_my': loo, 'xt_at_stations': xt_at_st,
    }
    return result


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description='我的实验算法 vs 讯腾实时算法（程序内对比，不用截图）')
    ap.add_argument('--layer', default='XTSKPWV')
    ap.add_argument('--date', default='2026-08-28')
    ap.add_argument('--hour', type=int, default=12)
    ap.add_argument('--minute', type=int, default=0, help='目标分钟（默认 0）')
    ap.add_argument('--hour-range', nargs=2, type=int, default=[0, 12], metavar=('H_START', 'H_END'))
    ap.add_argument('--bbox', nargs=4, type=float, default=[115.814, 116.816, 39.637, 40.423])
    ap.add_argument('--k', type=int, default=3, help='我的算法 IDW 近邻数（txt 参考为 3）')
    ap.add_argument('--power', type=float, default=2.0, help='我的算法 IDW 幂次')
    ap.add_argument('--cell-km', type=float, default=1.0, help='格网边长(km)')
    ap.add_argument('--tol-minutes', type=float, default=30.0, help='站点历史取值容差(分钟)')
    ap.add_argument('--no-platform-fallback', dest='scatter_fallback', action='store_false',
                    help='禁用兜底散点（站点历史缺该要素时改用平台场在站点位置取值）')
    ap.add_argument('--size', type=int, default=1024)
    ap.add_argument('--no-fetch', action='store_true')
    ap.add_argument('--outdir', default=os.path.join(PACKAGE_DIR, 'output', 'algo_compare'))
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    client = APIClient(config.host, config.app_key, config.app_secret, 120)
    layer = args.layer
    meta = LAYERS[layer]

    if args.no_fetch:
        data, _ = load_cache(layer, args.date, args.hour_range[0], args.hour_range[1])
        if data is None:
            raise SystemExit('无缓存数据，请去掉 --no-fetch 联网拉取')
    else:
        data, path = fetch_layer(client, layer, args.date,
                                 args.hour_range[0], args.hour_range[1], args.bbox)
        print(f'已拉取: {path}')

    target_dt = datetime(*map(int, args.date.split('-')), args.hour, args.minute, 0)
    target_ms = ms(target_dt)
    frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
    if target_ms not in frames:
        target_ms = min(frames, key=lambda t: abs(t - target_ms))
        target_dt = datetime.fromtimestamp(target_ms / 1000)
    time_str = target_dt.strftime('%Y-%m-%d %H:%M')

    print(f'\n=== 算法对比 {layer} {meta["name"]} @ {time_str} ===')
    print('取站点散点 ...')
    stations = load_stations(client, args.bbox)
    print(f'  站点数: {len(stations)}')
    cache_dir = os.path.join(DATA_DIR, 'cache')

    res = compare_frame(client, layer, data, target_ms, stations, cache_dir, args, args.outdir)
    m = res['metrics']
    if m.get('error'):
        print(f'  !! {m["error"]}')
        print(f'  讯腾图层已出图: {os.path.join(args.outdir, res["items"]["xt"]["png"])}')
        return
    field, loo, xt_st = m['field'], m['loo_my'], m['xt_at_stations']

    print(f'  有效散点 {m["points"]} 个（跳过 {m["skipped"]}）')
    print(f'  公共评估格网 {m["eval_grid"][0]}x{m["eval_grid"][1]}，bbox={[round(v,4) for v in m["eval_bbox"]]}')
    print(f'  [场差] 我的算法 vs 讯腾：RMSE={field["rmse"]:.4f} MAE={field["mae"]:.4f} '
          f'偏差={field["bias"]:.4f} 相关={field["corr"]:.4f} 最大差={field["max_abs"]:.4f}')
    print(f'  [色阶一致率] {m["class_agreement"]*100:.2f}%（{m["class_n"]} 格点）')
    print(f'  [站点LOO] 我的算法：RMSE={loo.get("rmse", float("nan")):.4f} '
          f'MAE={loo.get("mae", float("nan")):.4f} 偏差={loo.get("bias", float("nan")):.4f}（{loo.get("n",0)} 站）')
    print(f'  [站点拟合] 讯腾格网取值：RMSE={xt_st.get("rmse", float("nan")):.4f} '
          f'MAE={xt_st.get("mae", float("nan")):.4f} 偏差={xt_st.get("bias", float("nan")):.4f}（{xt_st.get("n",0)} 站）')

    stamp = target_dt.strftime('%Y%m%d_%H%M')
    side = os.path.join(args.outdir, f'{layer}_{stamp}_side.png')
    side_by_side([
        (os.path.join(args.outdir, res['items']['my']['png']),
         f'我的实验算法（IDW k={args.k}, p={args.power}）'),
        (os.path.join(args.outdir, res['items']['xt']['png']), '讯腾实时算法（平台格网）'),
        (os.path.join(args.outdir, res['items']['diff']['png']), '差值场（我的 − 讯腾）'),
    ], side, f'{meta["name"]} {time_str} · 算法对比')
    print(f'  并排图: {side}')

    rows = [f'<h2>{layer} {meta["name"]} @ {time_str}</h2>',
            '<table><tr><th>指标</th><th>值</th></tr>',
            f'<tr><td>有效站点散点</td><td>{m["points"]}（跳过 {m["skipped"]}）</td></tr>',
            f'<tr><td>公共评估格网</td><td>{m["eval_grid"][0]} × {m["eval_grid"][1]}</td></tr>',
            f'<tr><td>场差 RMSE / MAE / 偏差</td><td>{field["rmse"]:.4f} / {field["mae"]:.4f} / {field["bias"]:.4f}</td></tr>',
            f'<tr><td>场相关系数</td><td>{field["corr"]:.4f}</td></tr>',
            f'<tr><td>色阶分类一致率</td><td>{m["class_agreement"]*100:.2f}%</td></tr>',
            f'<tr><td>我的算法 站点LOO RMSE / MAE</td><td>{loo.get("rmse", float("nan")):.4f} / {loo.get("mae", float("nan")):.4f}</td></tr>',
            f'<tr><td>讯腾格网 站点拟合 RMSE / MAE</td><td>{xt_st.get("rmse", float("nan")):.4f} / {xt_st.get("mae", float("nan")):.4f}</td></tr>',
            '</table>',
            f'<p><img src="{os.path.basename(side)}"></p>']
    write_html(rows, os.path.join(args.outdir, f'{layer}_{stamp}_report.html'),
               '我的实验算法 vs 讯腾实时算法')
    print(f'  报告: {os.path.join(args.outdir, f"{layer}_{stamp}_report.html")}')


if __name__ == '__main__':
    main()
