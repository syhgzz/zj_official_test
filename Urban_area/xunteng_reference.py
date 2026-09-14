# -*- coding: utf-8 -*-
"""
xunteng_reference.py —— 迅腾 `equiSurfaceImg` 参考 Java 代码的 1:1 Python 实现。

对照关系（行号 / 步骤编号来自用户提供的参考代码）
=================================================
段 A  work(jsonArray, name, field, isclip, colorStr, outDir, imageOnly)
      步骤 1  解析散点、求包围盒        -> work() 内联
      步骤 2  范围外扩 0.07°            -> work() 内联（BigDecimalUtil 语义用 round 兜）
      步骤 3  按约 1km 格距算 cols/rows -> grid_size_from_km()
      步骤 4  createGridXY_Num + IDW    -> create_grid_xy_num() / interpolation_idw_neighbor()

段 B  finishFromGrid(matrix, xAxis, yAxis, t, field, isclip, colorStr, outDir, imageOnly, rows, cols, pointCount)
      步骤 5  解析色阶 colorStr          -> parse_legend_color_map()
      步骤 6  由坐标轴求 bbox            -> frame_bbox()
      步骤 7  等值面追踪                  -> equi_surface_from_grid()
                Contour.tracingBorders / tracingContourLines / smoothLines / tracingPolygons
      步骤 8  区间填色样式 addShapeLayer  -> add_shape_layer() / color_for_value()
      步骤 9  渲染 256x256 PNG            -> get_map_content()
      步骤 10 返回                        -> WorkResult

与 Java 的差异（刻意保留的语义等价，而不是"改进"）
--------------------------------------------------
* GeoTools StreamingRenderer + ReferencedEnvelope(WGS84) 在本例中就是**经纬度线性映射**
  （图层 CRS 与显示 CRS 都是 WGS84，无投影变换），因此步骤 9 用 matplotlib 做同样的线性映射。
* Java 的 `ECQL.toFilter("value >= k AND value < k2")` 逐条 Rule 依次匹配、**第一条命中即用**；
  Python 里 color_for_value() 用同样的顺序与边界（`>=` / `<`），命中不了就不填充（透明）。
* **色带不是直接拿 LowValue 去比区间**：wContour 输出的多边形 LowValue 恒等于 HighValue，
  区分"在等值线之上还是之下"的是 `IsHighCenter`（详见 color_for_polygon 的说明与实测数据）。
  默认 BAND_MODE='auto' 按 IsHighCenter 选色带，这才是能出对图的那一种。
  如果你的 getFeatureCollection 确实只是 `featureBuilder.add(polygon.LowValue)`，
  用 BAND_MODE='low' / `--band-mode low` 复现（但那样降水图的背景会被误填成第二档）。
"""

import json
import math
import os
import re

# 参考代码里写死的缺测值
UNDEF_DATA = -9999.0
# feature 上供 ECQL 过滤的取值来源：'low' -> polygon.LowValue
FEATURE_VALUE_FIELD = 'low'
# 色带选取模式：'auto' 按 IsHighCenter 判上下（出图正确，默认）；'low'/'high' 直接用该字段
# 走 ECQL 区间规则（仅当你的 getFeatureCollection 确实只写了 LowValue/HighValue 时才用）
BAND_MODE = 'auto'


class WorkResult(object):
    """对应 Java 的 WorkResult(imgFile, htmlFile, geojsonFile, metaFile, bbox)。"""

    __slots__ = ('img', 'html', 'geojson', 'meta', 'bbox',
                 'info', 'n_polygons', 'n_drawn')

    def __init__(self, img=None, html=None, geojson=None, meta=None, bbox=None):
        self.img = img
        self.html = html
        self.geojson = geojson
        self.meta = meta
        self.bbox = bbox
        self.info = None
        self.n_polygons = 0
        self.n_drawn = 0

    def __repr__(self):
        return 'WorkResult(img=%r, bbox=%r)' % (self.img, self.bbox)


# ---------------------------------------------------------------------------
# 公共小工具（对应参考代码里的 FileUtil / BigDecimalUtil / normalizeRelativePath）
# ---------------------------------------------------------------------------

def normalize_relative_path(name):
    """参考代码 normalizeRelativePath(t)：相对路径规范化，去掉盘符/前导分隔符/.. 。"""
    if name is None:
        return 'out'
    s = str(name).replace('\\', '/').strip()
    s = re.sub(r'^[A-Za-z]:', '', s)
    parts = [p for p in s.split('/') if p not in ('', '.', '..')]
    if not parts:
        return 'out'
    return '/'.join(parts)


def mkdir(path):
    """参考代码 FileUtil.mkdir(File)：目录不存在就建（含父目录）。"""
    if path:
        os.makedirs(path, exist_ok=True)
    return path


def bd_subtract(a, b):
    """BigDecimalUtil.subtract：十进制精确相减，避免 0.07 的二进制误差。"""
    from decimal import Decimal
    return float(Decimal(str(a)) - Decimal(str(b)))


def bd_add(a, b):
    """BigDecimalUtil.add：十进制精确相加。"""
    from decimal import Decimal
    return float(Decimal(str(a)) + Decimal(str(b)))


# ---------------------------------------------------------------------------
# 步骤 5：色阶
# ---------------------------------------------------------------------------

def parse_legend_color_map(color_str):
    """
    步骤 5：把 colorStr（JSON：断点 -> 颜色）解析成按断点升序的 (breaks, colors)。

    对应 Java：
        JSONObject colorObj = JSONObject.parseObject(colorStr);
        TreeMap<Double, String> legendColorMap = new TreeMap<>();
        ... dataInterval = legendColorMap.keySet()...
    """
    obj = json.loads(color_str) if isinstance(color_str, str) else dict(color_str)
    items = sorted((float(k), str(v)) for k, v in obj.items())
    breaks = [k for k, _ in items]
    colors = [c for _, c in items]
    return breaks, colors


# ---------------------------------------------------------------------------
# 步骤 6：坐标轴 -> bbox
# ---------------------------------------------------------------------------

def frame_bbox(x_axis, y_axis):
    """步骤 6：minX=xAxis[0]，maxX=xAxis[末]，minY/maxY 同理（minY>maxY 时交换）。"""
    min_x = float(x_axis[0])
    max_x = float(x_axis[len(x_axis) - 1])
    min_y = float(y_axis[0])
    max_y = float(y_axis[len(y_axis) - 1])
    if min_y > max_y:
        tmp = min_y
        min_y = max_y
        max_y = tmp
    return [min_x, min_y, max_x, max_y]


# ---------------------------------------------------------------------------
# 步骤 7：等值面追踪
# ---------------------------------------------------------------------------

def equi_surface_from_grid(matrix, x_axis, y_axis, data_interval, isclip,
                           clip_wkt=None, clip_geojson=None):
    """
    对应 Java：equiSurfaceImg.equiSurfaceFromGrid(matrix, xAxis, yAxis, dataInterval, isclip)

        double _undefData = -9999.0;
        int nc = dataInterval.length;
        int[][] S1 = new int[gridData.length][gridData[0].length];
        List<Border> _borders = Contour.tracingBorders(gridData, xAxis, yAxis, S1, _undefData);
        List<PolyLine> cPolylineList = Contour.tracingContourLines(
                gridData, xAxis, yAxis, nc, dataInterval, _undefData, _borders, S1);
        cPolylineList = Contour.smoothLines(cPolylineList);
        List<Polygon> cPolygonList = Contour.tracingPolygons(gridData, cPolylineList, _borders, dataInterval);
        FeatureCollection polygonCollection = getFeatureCollection(cPolygonList);

    isclip=True 时按行政边界裁剪；裁剪失败**回退未裁剪结果**（与参考代码一致）。
    返回 (polygons, info)；polygons 是 wContour 的 Polygon 列表。
    """
    from .wcontour import borders as _borders_mod
    from .wcontour import contour_lines as _cl_mod
    from .wcontour import smoothing as _smooth_mod
    from .wcontour import polygons as _poly_mod

    if matrix is None or len(matrix) == 0 or x_axis is None or y_axis is None:
        raise ValueError('格网数据为空')
    if len(matrix) != len(y_axis) or len(matrix[0]) != len(x_axis):
        raise ValueError('矩阵尺寸与坐标轴不一致: matrix=%dx%d axes=%dx%d'
                         % (len(matrix), len(matrix[0]), len(y_axis), len(x_axis)))

    undef = UNDEF_DATA
    nc = len(data_interval)
    m, n = len(matrix), len(matrix[0])
    S1 = [[0] * n for _ in range(m)]

    borders = _borders_mod.tracingBorders(matrix, list(x_axis), list(y_axis), S1, undef)
    c_lines = _cl_mod.tracingContourLines(matrix, list(x_axis), list(y_axis),
                                          nc, list(data_interval), undef, borders, S1)
    c_lines = _smooth_mod.smoothLines(c_lines)
    polys = _poly_mod.tracingPolygons(matrix, c_lines, borders, list(data_interval))

    info = dict(nc=nc, undef=undef, nBorders=len(borders),
                nContourLines=len(c_lines), nPolygons=len(polys), clipped=False)

    if isclip:
        clip_poly = _load_clip_polygon(clip_wkt, clip_geojson)
        if clip_poly is not None:
            clipped = _clip_polygons(polys, clip_poly)
            if clipped is not None:
                polys = clipped
                info['clipped'] = True
            else:
                info['clipFallback'] = '裁剪失败，回退未裁剪结果'
        else:
            info['clipFallback'] = '未提供行政边界，回退未裁剪结果'
    return polys, info


def _load_clip_polygon(clip_wkt, clip_geojson):
    """对应 Java GeoJSONUtil.loadArea(...)：拿到行政边界几何。"""
    try:
        import shapely
    except ImportError:                                     # pragma: no cover
        return None
    if clip_wkt:
        return shapely.from_wkt(clip_wkt)
    if clip_geojson:
        if isinstance(clip_geojson, str):
            clip_geojson = json.loads(clip_geojson)
        return shapely.geometry.shape(clip_geojson)
    return None


def _clip_polygons(polys, clip_poly):
    """把 wContour 的 Polygon 列表按行政边界裁剪；失败返回 None（调用方回退）。"""
    try:
        import shapely
        from shapely.geometry import Polygon as ShpPolygon
        from .wcontour.global_types import Polygon, PolyLine, PointD
    except ImportError:                                     # pragma: no cover
        return None

    out = []
    try:
        for g in polys:
            ring = [(p.X, p.Y) for p in g.OutLine.PointList]
            if len(ring) < 4:
                continue
            shp = ShpPolygon(ring, [[(p.X, p.Y) for p in h.PointList] for h in g.HoleLines])
            if not shp.is_valid:
                shp = shp.buffer(0)
            inter = shp.intersection(clip_poly)
            if inter.is_empty:
                continue
            geoms = list(inter.geoms) if inter.geom_type.startswith('Multi') else [inter]
            for part in geoms:
                if part.is_empty or part.area == 0:
                    continue
                np_ = Polygon()
                np_.IsBorder = g.IsBorder
                np_.IsInnerBorder = g.IsInnerBorder
                np_.LowValue = g.LowValue
                np_.HighValue = g.HighValue
                np_.IsClockWise = g.IsClockWise
                np_.StartPointIdx = g.StartPointIdx
                np_.IsHighCenter = g.IsHighCenter
                np_.Area = part.area
                ext = part.bounds
                np_.Extent.xMin, np_.Extent.yMin, np_.Extent.xMax, np_.Extent.yMax = ext
                line = PolyLine()
                line.Value = g.OutLine.Value
                line.Type = g.OutLine.Type
                line.BorderIdx = g.OutLine.BorderIdx
                line.PointList = [PointD(x, y) for x, y in part.exterior.coords]
                np_.OutLine = line
                for r in part.interiors:
                    hl = PolyLine()
                    hl.Value = line.Value
                    hl.PointList = [PointD(x, y) for x, y in r.coords]
                    np_.HoleLines.append(hl)
                out.append(np_)
        return out
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 步骤 8：区间填色
# ---------------------------------------------------------------------------

def parse_color(value, opacity=1.0):
    """对应 Java parseColor(...)：支持 #RRGGBB 与 #RRGGBBAA。返回 (r,g,b,a) 0~1。"""
    s = str(value).strip()
    if s.startswith('#'):
        s = s[1:]
    if len(s) == 6:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        a = 255
    elif len(s) == 8:
        r, g, b, a = (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    elif len(s) == 3:
        r, g, b = (int(c * 2, 16) for c in s)
        a = 255
    else:
        raise ValueError('无法解析颜色: %r' % value)
    return (r / 255.0, g / 255.0, b / 255.0, (a / 255.0) * float(opacity))


def color_for_value(value, breaks, colors, opacity=1.0):
    """
    步骤 8：把 ECQL 规则按顺序求值，返回命中的颜色；没有规则命中返回 None（=不填充）。

        for (Map.Entry<Double, String> entry : levelProps.entrySet()) {
            int idx = valueList.indexOf(key);
            if (idx == valueList.size() - 1)  filter = ECQL.toFilter("value >=" + key);
            else                              filter = ECQL.toFilter("value >=" + key + " AND value <" + valueList.get(idx + 1));
        }

    GeoTools 的 Rule 按加入顺序依次匹配，第一条命中即用。
    """
    for i, key in enumerate(breaks):
        if value < key:
            continue
        if i == len(breaks) - 1:
            return parse_color(colors[i], opacity)
        if value < breaks[i + 1]:
            return parse_color(colors[i], opacity)
        # value >= 下一档下界 -> 这条规则不匹配，继续看下一条
    return None


def feature_value(polygon):
    """feature 的 value 属性：默认取 LowValue（见模块头说明）。"""
    if FEATURE_VALUE_FIELD == 'high':
        return polygon.HighValue
    return polygon.LowValue


def _band_index(v, breaks, tol=1e-9):
    """把某个断点值定位到 breaks 的下标（wContour 的 LowValue/HighValue 直接取自断点）。"""
    for i, k in enumerate(breaks):
        if abs(v - k) <= tol * max(1.0, abs(k)):
            return i
    return None


def color_for_polygon(polygon, breaks, colors, opacity=1.0, mode=None):
    """
    给 wContour 的多边形挑色带。

    为什么不能只用 LowValue
    ----------------------
    wContour 输出的多边形里 **LowValue 恒等于 HighValue**（都取它相邻的那条等值线值），
    真正区分"在等值线之上还是之下"的是 `IsHighCenter`。实测 8.28 12:00 的
    小时降水量：覆盖全域的那个"背景多边形"是 `LowValue=HighValue=0.1,
    IsHighCenter=False`（12 个洞 = 12 块降水区），它代表的是 **<0.1 的区域**；
    而每一块降水区是 `LowValue=HighValue=0.1, IsHighCenter=True`。
    两条多边形 LowValue 完全相同，只有 IsHighCenter 不同。

    所以色带按下列规则选（对应 MeteoInfo/wContour 的取值语义）：

        IsHighCenter=True  -> 该多边形在 LowValue **之上**，色带 = [LowValue, 下一档)
        IsHighCenter=False -> 该多边形在 LowValue **之下**，色带 = [上一档, LowValue)
        下标越界（比最低档还低 / 比最高档还高）-> 不填充

    mode:
        None / 'auto'  -> 按上面的 IsHighCenter 规则（默认，出图正确）
        'low'          -> 直接用 LowValue 走 ECQL 区间规则（若你的 getFeatureCollection
                          写的就是 `featureBuilder.add(polygon.LowValue)`，效果同这个）
        'high'         -> 直接用 HighValue
    """
    m = mode or BAND_MODE
    if m == 'low':
        return color_for_value(polygon.LowValue, breaks, colors, opacity)
    if m == 'high':
        return color_for_value(polygon.HighValue, breaks, colors, opacity)

    idx = _band_index(polygon.LowValue, breaks)
    if idx is None:
        # LowValue 不在断点上（理论上不该发生）：退回按 ECQL 区间规则
        return color_for_value(polygon.LowValue, breaks, colors, opacity)
    if not polygon.IsHighCenter:
        idx -= 1
    if idx < 0 or idx >= len(colors):
        return None
    return parse_color(colors[idx], opacity)


# ---------------------------------------------------------------------------
# 步骤 9：渲染 256x256 PNG
# ---------------------------------------------------------------------------

def get_map_content(polygons, params, img_path, breaks, colors, opacity=1.0, band_mode=None):
    """
    对应 Java equiSurfaceImg.getMapContent(params, imgPath)：

        width/height 默认 256；crs = DefaultGeographicCRS.WGS84；
        mapArea = new ReferencedEnvelope(x1, x2, y1, y2, crs)；
        StreamingRenderer.paint(g, rect, mapArea)；抗锯齿开；ImageIO.write(png)。

    GeoTools 在本例中是经纬度线性映射，这里用 matplotlib 做同样的映射。
    透明的洞按 even-odd 规则挖掉：外环统一 CCW，洞统一 CW（nonzero 填充规则）。
    """
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.path import Path
    from matplotlib.patches import PathPatch
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    bbox = params['bbox']
    width = int(params['width'])
    height = int(params['height'])
    min_x, min_y, max_x, max_y = bbox[0], bbox[1], bbox[2], bbox[3]

    fig = Figure(figsize=(width / 100.0, height / 100.0), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.set_facecolor((0, 0, 0, 0))

    n_drawn = 0
    for g in polygons:
        col = color_for_polygon(g, breaks, colors, opacity, mode=band_mode)
        if col is None:
            continue
        verts, codes = _compound_path(g)
        if verts is None:
            continue
        patch = PathPatch(Path(verts, codes), facecolor=col, edgecolor='none',
                          antialiased=True, linewidth=0)
        ax.add_patch(patch)
        n_drawn += 1

    out_dir = os.path.dirname(os.path.abspath(img_path))
    mkdir(out_dir)
    fig.savefig(img_path, dpi=100, transparent=True)
    return n_drawn


def _ring_orientation(ring):
    """鞋带公式：>0 逆时针（数学坐标），<0 顺时针。"""
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s


def _compound_path(g):
    from matplotlib.path import Path

    outer = [(p.X, p.Y) for p in g.OutLine.PointList]
    if len(outer) < 3:
        return None, None
    if _ring_orientation(outer) < 0:          # 外环 -> CCW
        outer = outer[::-1]
    rings = [outer]
    for h in g.HoleLines:
        hr = [(p.X, p.Y) for p in h.PointList]
        if len(hr) < 3:
            continue
        if _ring_orientation(hr) > 0:         # 洞 -> CW
            hr = hr[::-1]
        rings.append(hr)

    verts, codes = [], []
    for r in rings:
        verts.extend(r)
        verts.append(r[0])
        codes.append(Path.MOVETO)
        codes.extend([Path.LINETO] * (len(r) - 1))
        codes.append(Path.CLOSEPOLY)
    return verts, codes


# ---------------------------------------------------------------------------
# 步骤 3/4：段 A 的格网与 IDW（参考代码里 finishFromGrid 的入参来源）
# ---------------------------------------------------------------------------

def grid_size_from_km(west, south, east, north, cell_side_km=1.0):
    """步骤 3：按约 1km 格距算 cols/rows（不足 2 兜底为 2）。"""
    def hav(lon1, lat1, lon2, lat2):
        r = 6378.137
        rl1, rl2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(rl1) * math.cos(rl2) * math.sin(dlon / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    x_fraction = cell_side_km / hav(west, south, east, south)
    cell_width = x_fraction * (east - west)
    y_fraction = cell_side_km / hav(west, south, west, north)
    cell_height = y_fraction * (north - south)
    cols = int(math.floor((east - west) / cell_width))
    rows = int(math.floor((north - south) / cell_height))
    return max(cols, 2), max(rows, 2)


def create_grid_xy_num(min_x, min_y, max_x, max_y, cols, rows):
    """步骤 4：Interpolate.createGridXY_Num —— 闭区间上均匀取点（与 Java 同）。"""
    def lin(a, b, k):
        if k == 1:
            return [a]
        step = (b - a) / (k - 1)
        return [a + step * i for i in range(k)]
    return lin(min_x, max_x, cols), lin(min_y, max_y, rows)


# ---------------------------------------------------------------------------
# 段 B：finishFromGrid
# ---------------------------------------------------------------------------

def finish_from_grid(matrix, x_axis, y_axis, t, field, isclip, color_str, out_dir,
                     image_only, rows, cols, point_count, clip_wkt=None, clip_geojson=None):
    """
    参考代码 finishFromGrid(...) 的 1:1 实现（步骤 5 ~ 步骤 10）。
    """
    if matrix is None or len(matrix) == 0 or x_axis is None or y_axis is None:
        raise ValueError('格网数据为空')
    if len(matrix) != len(y_axis) or len(matrix[0]) != len(x_axis):
        raise ValueError('矩阵尺寸与坐标轴不一致: matrix=%dx%d axes=%dx%d'
                         % (len(matrix), len(matrix[0]), len(y_axis), len(x_axis)))

    # 步骤 5
    breaks, colors = parse_legend_color_map(color_str)
    data_interval = list(breaks)

    # 步骤 6
    bbox = frame_bbox(x_axis, y_axis)
    size = [cols if cols and cols > 0 else len(x_axis),
            rows if rows and rows > 0 else len(y_axis)]

    # 步骤 7
    polygons, info = equi_surface_from_grid(matrix, x_axis, y_axis, data_interval, isclip,
                                            clip_wkt=clip_wkt, clip_geojson=clip_geojson)
    if polygons is None:
        raise RuntimeError('等值面结果为空，无法出图')

    # 步骤 8 + 9
    mkdir(out_dir)
    relative = normalize_relative_path(t)
    img_file = os.path.join(out_dir, relative + '.png')
    mkdir(os.path.dirname(os.path.abspath(img_file)))
    params = {'bbox': bbox, 'width': 256, 'height': 256}
    n_drawn = get_map_content(polygons, params, img_file, breaks, colors, 1.0)

    result = WorkResult(img_file, None, None, None, bbox)
    result.info = info
    result.n_polygons = len(polygons)
    result.n_drawn = n_drawn

    if image_only:
        return result

    # 以下只在 imageOnly=false 时输出（workPngOnly 不会走到）
    base_dir = os.path.dirname(os.path.abspath(img_file))
    base_name = os.path.basename(img_file)[:-4]

    geo_file = os.path.join(base_dir, base_name + '.geojson')
    with open(geo_file, 'w', encoding='utf-8') as f:
        json.dump(feature_to_geojson(polygons), f, ensure_ascii=False)

    meta = {
        'name': relative, 'field': field, 'clip': bool(isclip),
        'width': 256, 'height': 256, 'bbox': bbox, 'size': size,
        'pointCount': point_count, 'colorStr': color_str,
        'img': os.path.basename(img_file), 'geojson': os.path.basename(geo_file),
        'polygons': len(polygons), 'drawn': n_drawn,
    }
    meta_file = os.path.join(base_dir, base_name + '.meta.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    return WorkResult(img_file, None, geo_file, meta_file, bbox)


def feature_to_geojson(polygons):
    """对应参考代码 equiSurfaceImg.featureToGeoJSON(featureCollection)。"""
    feats = []
    for g in polygons:
        rings = [[[p.X, p.Y] for p in g.OutLine.PointList]]
        for h in g.HoleLines:
            rings.append([[p.X, p.Y] for p in h.PointList])
        feats.append({
            'type': 'Feature',
            'properties': {'value': feature_value(g),
                           'low': g.LowValue, 'high': g.HighValue,
                           'isBorder': bool(g.IsBorder),
                           'isHighCenter': bool(g.IsHighCenter)},
            'geometry': {'type': 'Polygon', 'coordinates': rings},
        })
    return {'type': 'FeatureCollection', 'features': feats}


# ---------------------------------------------------------------------------
# 段 A：work / workPngOnly
# ---------------------------------------------------------------------------

def work(json_array, t, field, isclip, color_str, out_dir, image_only):
    """
    参考代码 work(jsonArray, t, field, isclip, colorStr, outDir, imageOnly)。

    步骤 1 遍历 jsonArray 取 l/b/v（任一为 null 跳过），统计 minX/maxX/minY/maxY；
           注意 Java 用 "minX == 0 || l < minX" 判断，**初始值为 0**，这里逐字保留。
    步骤 2 用 BigDecimal 加减外扩 0.07°。
    步骤 3 按 1km 格距算 cols/rows。
    步骤 4 createGridXY_Num + IDW(3 近邻, -9999 填充)。
    """
    min_x = 0.0
    max_x = 0.0
    min_y = 0.0
    max_y = 0.0
    rows = len(json_array)
    train_data = [[0.0, 0.0, 0.0] for _ in range(rows)]
    vales = []
    valid_count = 0
    for i in range(rows):
        item = json_array[i]
        l = item.get('l')
        b = item.get('b')
        pwv = item.get('v')
        if b is None or l is None or pwv is None:
            continue
        l = float(l)
        b = float(b)
        pwv = float(pwv)
        if min_x == 0 or l < min_x:
            min_x = l
        if max_x == 0 or l > max_x:
            max_x = l
        if min_y == 0 or b < min_y:
            min_y = b
        if max_y == 0 or b > max_y:
            max_y = b
        train_data[i][0] = l
        train_data[i][1] = b
        train_data[i][2] = pwv
        vales.append(str(pwv))
        valid_count += 1

    if valid_count == 0:
        raise ValueError('有效插值点为空')

    min_x = bd_subtract(min_x, 0.07)
    max_x = bd_add(max_x, 0.07)
    min_y = bd_subtract(min_y, 0.07)
    max_y = bd_add(max_y, 0.07)

    west, south, east, north = min_x, min_y, max_x, max_y
    cols, rows_n = grid_size_from_km(west, south, east, north, 1.0)

    x_axis, y_axis = create_grid_xy_num(min_x, min_y, max_x, max_y, cols, rows_n)
    grid = interpolation_idw_neighbor(train_data, x_axis, y_axis, 3, UNDEF_DATA)

    return finish_from_grid(grid, x_axis, y_axis, t, field, isclip, color_str, out_dir,
                            image_only, rows_n, cols, valid_count)


def work_png_only(json_array, name, field, isclip, color_str, out_dir):
    """参考代码 workPngOnly(...)：只出 PNG，返回图片文件路径。"""
    return work(json_array, name, field, isclip, color_str, out_dir, True).img


def interpolation_idw_neighbor(train_data, x_axis, y_axis, neighbor_number, undef_data):
    """
    步骤 4：Interpolate.interpolation_IDW_Neighbor 的等价实现
    （反距离权重，取最近 neighbor_number 个点；无有效点填 undef_data）。

    注意：这里只保证"近邻数 3 + 缺测 -9999"这两个参考代码明确给出的语义；
    wContour 原版用的是 KDTree + 幂次参数，若段 A 参与对拍需要单独标定幂次。
    """
    pts = [p for p in train_data if p[2] != undef_data]
    out = [[undef_data] * len(x_axis) for _ in range(len(y_axis))]
    if not pts:
        return out
    k = min(int(neighbor_number), len(pts))
    for iy, y in enumerate(y_axis):
        for ix, x in enumerate(x_axis):
            d2 = []
            for p in pts:
                dx = x - p[0]
                dy = y - p[1]
                d2.append((dx * dx + dy * dy, p[2]))
            d2.sort(key=lambda z: z[0])
            near = d2[:k]
            if near[0][0] == 0.0:
                out[iy][ix] = near[0][1]
                continue
            sw = 0.0
            sv = 0.0
            for dd, vv in near:
                w = 1.0 / dd          # 距离平方的倒数 = 1/d^2（经典 IDW，power=2）
                sw += w
                sv += w * vv
            out[iy][ix] = sv / sw if sw != 0.0 else undef_data
    return out
