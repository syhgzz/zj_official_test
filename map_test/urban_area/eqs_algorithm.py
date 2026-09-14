# -*- coding: utf-8 -*-
"""
eqs_algorithm.py —— 讯腾 equiSurfaceImg 绘制算法复现（对照 txt 流程 1:1）

txt 流程映射
============
步骤 1  解析散点/统计极值          -> parse_scatter_stations()（--diff 模式使用）
步骤 2  范围外扩 0.07°             -> expand_bbox()
步骤 3  按约 1km 格距算 cols/rows  -> grid_size_from_km()
步骤 4  createGridXY + IDW(3,-9999) -> create_grid_xy() + idw_neighbor()
步骤 5  解析色阶 colorStr           -> parse_color_str()
步骤 6  由坐标轴求 bbox             -> frame_bbox()
步骤 7  等值面追踪(边界/等值线/闭合) -> 等价实现：matplotlib contourf
                                        （断点区间规则与 ECQL 完全一致）
步骤 8  按区间填色规则               -> contourf(colors=区间色, extend='max')
步骤 9  WGS84 线性映射渲染 256x256 PNG -> render_equi_surface()

说明
----
- 平台接口 /api/v1/upns/precipitation/layers 返回的是**已插值格网** + 行政边界
  （groups[].area, 即 isclip 裁剪多边形），因此主流程走"格网 -> 等值面 -> 渲染"；
  IDW 段保留为可选（--diff），用站点散点复算格网并与平台格网逐格对比。
- -9999 / null 与裁剪多边形外的格点按缺测处理（相当于 txt 的 _undefData=-9999
  与 tracingBorders 缺测边界处理）。
"""

import json
import math

import numpy as np

# -----------------------------------------------------------------------------
# 基础工具
# -----------------------------------------------------------------------------

EARTH_RADIUS_KM = 6378.137  # 与 txt 中 GeoJSONUtil.getDistance 保持一致


def haversine_km(lon1, lat1, lon2, lat2):
    """
    Haversine 球面距离，单位 km（地球半径 6378.137 km）。
    使用 numpy 函数，标量与数组（向量化）均可用。
    """
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(np.asarray(lat2, dtype=float) - np.asarray(lat1, dtype=float))
    dlon = np.radians(np.asarray(lon2, dtype=float) - np.asarray(lon1, dtype=float))
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def expand_bbox(minx, miny, maxx, maxy, pad=0.07):
    """txt 步骤 2：范围外扩 0.07°。"""
    return minx - pad, miny - pad, maxx + pad, maxy + pad


def grid_size_from_km(west, south, east, north, cell_side_km=1.0):
    """txt 步骤 3：按约 1km 格距计算 cols/rows（不足 2 兜底为 2）。"""
    x_fraction = cell_side_km / haversine_km(west, south, east, south)
    cell_width = x_fraction * (east - west)
    y_fraction = cell_side_km / haversine_km(west, south, west, north)
    cell_height = y_fraction * (north - south)

    cols = int(math.floor((east - west) / cell_width))
    rows = int(math.floor((north - south) / cell_height))
    return max(cols, 2), max(rows, 2)


def create_grid_xy(minx, miny, maxx, maxy, cols, rows):
    """txt 步骤 4：createGridXY_Num——在外扩矩形内均匀生成坐标轴。"""
    xs = np.linspace(minx, maxx, cols)
    ys = np.linspace(miny, maxy, rows)
    return xs, ys


# -----------------------------------------------------------------------------
# 步骤 1：散点解析（--diff 模式）
# -----------------------------------------------------------------------------


def parse_scatter_stations(stations, metric, target_dt_ms=None, history_lookup=None):
    """
    把站点列表转成 txt 的 jsonArray 语义：[[l, b, v], ...]

    stations: /api/v1/upns/stations 返回的站点 dict 列表
              {stationCode, location:{longitude,latitude}, ...}
    metric:   指标字段名（'pwv' / 'rain' / 'temperature' ...）
    history_lookup: 可选，callable(code, metric) -> 12:00 值；
                    为 None 时用站点实时值字段（仅当前值，非历史）。
    """
    train = []
    for s in stations:
        loc = s.get('location') or {}
        l, b = loc.get('longitude'), loc.get('latitude')
        if l is None or b is None:
            continue
        if history_lookup is not None:
            v = history_lookup(s.get('stationCode'), metric)
        else:
            v = s.get(metric)
        if v is None:
            continue
        train.append([float(l), float(b), float(v)])
    if not train:
        raise ValueError('有效插值点为空')
    return np.asarray(train, dtype=float)


# -----------------------------------------------------------------------------
# IDW 插值（txt 步骤 4：interpolation_IDW_Neighbor）
# -----------------------------------------------------------------------------


def idw_neighbor(train, xs, ys, k=3, power=2.0, fill=-9999.0):
    """
    IDW 近邻插值：每个格点取最近的 k 个站点，权重 w = 1 / d^power。

    txt 只说明 "近邻数：3、缺测填充 -9999"，未给出幂次；
    默认 power=2（经典 IDW），可用 --idw-power 调整，
    --diff 模式会给出复算格网与平台格网的 RMSE/相关系数用于标定。
    """
    pts = train[:, :2]
    vals = train[:, 2]
    n_pts = len(pts)
    k = min(k, n_pts) if n_pts else 0

    X, Y = np.meshgrid(xs, ys)
    out = np.full(X.shape, fill, dtype=float)

    # 逐格点：对全部站点向量化算真实公里距离，取最近 k 个加权
    flat_x, flat_y = X.ravel(), Y.ravel()
    for idx in range(len(flat_x)):
        x, y = flat_x[idx], flat_y[idx]
        d_km2 = (haversine_km(x, y, pts[:, 0], pts[:, 1])) ** 2
        order = np.argsort(d_km2)[:k]
        dd = d_km2[order]
        vv = vals[order]
        if len(order) == 0:
            continue
        if np.any(dd == 0):
            out.ravel()[idx] = vv[np.argmin(dd)]
        else:
            w = 1.0 / np.power(dd, power / 2.0)
            out.ravel()[idx] = np.sum(w * vv) / np.sum(w)

    return out


# -----------------------------------------------------------------------------
# 色阶（txt 步骤 5）
# -----------------------------------------------------------------------------


def parse_color_str(color_str):
    """
    colorStr: JSON 字符串，如 {"0":"#00FF00","5":"#FFFF00","10":"#FF0000"}
    返回 (breaks, colors)：
      breaks[k] <-> colors[k]，区间规则：
      [breaks[k], breaks[k+1]) -> colors[k]，最后一个 -> colors[-1] 为 >= breaks[-1]
    """
    if isinstance(color_str, str):
        obj = json.loads(color_str)
    else:
        obj = dict(color_str)
    items = sorted((float(k), str(v)) for k, v in obj.items())
    breaks = np.array([k for k, _ in items], dtype=float)
    colors = [c for _, c in items]
    return breaks, colors


def frame_bbox(xs, ys):
    """txt 步骤 6：由坐标轴求输出范围 bbox=[minX,minY,maxX,maxY]（排序兜底）。"""
    minx, maxx = float(xs[0]), float(xs[-1])
    miny, maxy = float(ys[0]), float(ys[-1])
    if miny > maxy:
        miny, maxy = maxy, miny
    return [minx, miny, maxx, maxy]


# -----------------------------------------------------------------------------
# 平台格网解析
# -----------------------------------------------------------------------------


def extract_frame(data, target_dt_ms):
    """
    从 /api/v1/upns/precipitation/layers 的 data 中抽取指定时刻的一帧。

    返回 (Z[rows,cols], xs[cols], ys[rows])，行列顺序与接口一致。
    """
    rows_list = data.get('rowsList') or []
    frame_rows = [r for r in rows_list if r.get('dataTime') == target_dt_ms]
    if not frame_rows:
        raise ValueError(f'目标时刻 {target_dt_ms} 无数据帧（该层时间点: '
                         f'{sorted({r.get("dataTime") for r in rows_list})}）')
    frame_rows.sort(key=lambda r: r.get('currentRow', 0))

    xs = [float(p.split(',')[0]) for p in frame_rows[0]['gridLocations']]
    ys = []
    Z = np.empty((len(frame_rows), len(xs)), dtype=float)
    for i, row in enumerate(frame_rows):
        ys.append(float(row['gridLocations'][0].split(',')[1]))
        Z[i] = [float(v) if v is not None else np.nan for v in row['gridValues']]
    ys = np.asarray(ys, dtype=float)

    # 交叉校验：与 data.bbox / cols / rows 一致性（不一致以 gridLocations 为准并记录）
    notes = []
    if data.get('cols') is not None and int(data['cols']) != len(xs):
        notes.append(f"cols={data['cols']} != gridLocations 数量 {len(xs)}")
    if data.get('rows') is not None and int(data['rows']) != len(ys):
        notes.append(f"rows={data['rows']} != 行数 {len(ys)}")
    return Z, xs, ys, notes


def mask_polygon_contains(area_wkt, xs, ys):
    """
    将 groups[].area（MULTIPOLYGON WKT）栅格化为布尔掩膜（True=格点在边界内）。
    对应 txt 中 isclip=true 时 GeoJSONUtil.loadArea 对等值面做行政边界裁剪。
    """
    import shapely
    geom = shapely.from_wkt(area_wkt)
    X, Y = np.meshgrid(xs, ys)
    try:
        return shapely.contains_xy(geom, X, Y)
    except AttributeError:  # shapely < 2.0 兼容
        from shapely.vectorized import contains
        return contains(geom, X, Y)


# -----------------------------------------------------------------------------
# 等值面填色渲染（txt 步骤 7/8/9）
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# txt 全链路驱动（段A + 段B）
# -----------------------------------------------------------------------------


def run_full_algorithm(
    scatter,
    color_str,
    out_png,
    k=3,
    power=2.0,
    cell_km=1.0,
    pad=0.07,
    clip=False,
    mask_wkt=None,
    size=1024,
    undef=-9999.0,
):
    """
    严格按 txt 的链路执行：站点散点 → 外扩 0.07° → 1km 格网 → IDW(3 近邻) → 等值面填色 → PNG。

    步骤 1 用真实经纬度极值（修正了 txt 中 minX 初始 0 在跨 0° 时的写法）；
    步骤 2 外扩 pad；步骤 3 按公里换算 cols/rows（下限 2）；
    步骤 4 createGridXY + IDW(k 近邻, 缺测 -9999)；
    步骤 5-8 色阶断点 + 等值面填色；步骤 9 WGS84 线性映射渲染 PNG。

    scatter: [[l, b, v], ...]（有效散点）
    返回 dict(bbox, xs, ys, Z, cols, rows, points)
    """
    train = np.asarray(scatter, dtype=float)
    if train.ndim != 2 or len(train) == 0:
        raise ValueError('有效插值点为空')

    lons, lats = train[:, 0], train[:, 1]
    west, south, east, north = expand_bbox(
        float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max()), pad)

    cols, rows = grid_size_from_km(west, south, east, north, cell_km)
    xs, ys = create_grid_xy(west, south, east, north, cols, rows)
    Z = idw_neighbor(train, xs, ys, k=k, power=power, fill=undef)

    breaks, colors = parse_color_str(color_str)
    render_equi_surface(Z, xs, ys, breaks, colors, out_png,
                        width=size, height=size,
                        mask_wkt=mask_wkt if clip else None, undef=undef)

    return {'bbox': frame_bbox(xs, ys), 'xs': xs, 'ys': ys, 'Z': Z,
            'cols': cols, 'rows': rows, 'points': int(len(train))}


def setup_cjk_font():
    """matplotlib 中文字体（避免标题变成方框）。"""
    import matplotlib
    matplotlib.rcParams['font.sans-serif'] = [
        'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
    matplotlib.rcParams['axes.unicode_minus'] = False


def render_equi_surface(
    Z,
    xs,
    ys,
    breaks,
    colors,
    out_png,
    width=256,
    height=256,
    dpi=100,
    mask_wkt=None,
    undef=-9999.0,
):
    """
    等值面填色 + WGS84 线性映射渲染 PNG（256x256，透明背景，无底图）。

    - Z: 格网值；等于 undef 或 nan 的格点不绘制（相当于 _undefData 缺测）
    - mask_wkt: 行政边界 WKT；给出时按边界裁剪（isclip=true 语义）
    - 区间规则（步骤 8）：
        [k0,k1)->c0 / [k1,k2)->c1 / ... / [k_last,∞)->c_last；value<k0 不填充
      matplotlib contourf(levels=breaks, colors=colors, extend='max') 语义一致。
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    setup_cjk_font()
    Zv = np.asarray(Z, dtype=float).copy()
    Zv[np.isnan(Zv)] = np.nan
    Zv[Zv == undef] = np.nan

    X, Y = np.meshgrid(xs, ys)
    masked = np.ma.masked_invalid(Zv)
    if mask_wkt is not None:
        inside = mask_polygon_contains(mask_wkt, xs, ys)
        masked = np.ma.array(Zv, mask=np.isnan(Zv) | (~inside))

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    ax.set_xlim(float(xs[0]), float(xs[-1]))
    ax.set_ylim(float(ys[0]), float(ys[-1]))

    # levels=breaks（m 个）+ extend='max' -> m 个色带：m-1 个区间 + 1 个 >= 末断点
    ax.contourf(X, Y, masked, levels=list(breaks), colors=colors, extend='max')
    fig.savefig(out_png, transparent=True, dpi=dpi)
    plt.close(fig)


# -----------------------------------------------------------------------------
# 格网定量对比（--diff）
# -----------------------------------------------------------------------------


def compare_grids(a, b, undef=-9999.0):
    """逐格对比两个格网（nan/缺测均剔除），返回指标字典。"""
    A = np.asarray(a, dtype=float)
    B = np.asarray(b, dtype=float)
    valid = (~np.isnan(A)) & (~np.isnan(B)) & (A != undef) & (B != undef)
    A, B = A[valid], B[valid]
    n = len(A)
    if n == 0:
        return {'n_valid': 0, 'rmse': float('nan'), 'mae': float('nan'),
                'corr': float('nan'), 'mean_diff': float('nan')}
    diff = A - B
    return {
        'n_valid': int(n),
        'rmse': float(np.sqrt(np.mean(diff ** 2))),
        'mae': float(np.mean(np.abs(diff))),
        'corr': float(np.corrcoef(A, B)[0, 1]),
        'mean_diff': float(np.mean(diff)),
    }
