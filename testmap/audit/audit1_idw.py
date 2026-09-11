# -*- coding: utf-8 -*-
"""
_audit.py —— 对「现在的测试程序 vs 你给的参考算法规格」做带证据的一致性审计。

只读 precipitation_xunteng，只往 testmap 写。

四项实验：
  A. 忠实移植 Interpolate.interpolation_IDW_Neighbor(...,3,-9999)，与你程序里用的
     xunteng_reference.interpolation_idw_neighbor 逐步对比 -> 量化差异
  B. 复现 work() 步骤 1 的 trainData 写入方式（按下标写入 + 跳过 null）-> 看被跳过的行变成什么
  C. 真实帧的等值面多边形：LowValue / HighValue / IsHighCenter -> 证明色带不能只用 LowValue
  D. createGridXY_Num 与你实现的逐点对比
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'E:\work\zj_official_test')
sys.path.insert(0, HERE)
os.environ.setdefault('MPLCONFIGDIR', os.path.join(HERE, '.mplcache'))

from precipitation_xunteng import xunteng_reference as xr      # noqa: E402

UNDEF = -9999.0


# ---------------------------------------------------------------------------
# A. Interpolate.interpolation_IDW_Neighbor 的逐行移植（Interpolate.java L169-250）
# ---------------------------------------------------------------------------

def interpolation_idw_neighbor_JAVA(SCoords, X, Y, NumberOfNearestNeighbors, unDefData):
    rowNum = len(Y)
    colNum = len(X)
    pNum = len(SCoords)
    GCoords = [[0.0] * colNum for _ in range(rowNum)]
    points = NumberOfNearestNeighbors
    AllWeights = [0.0] * pNum
    NW = [[0.0] * points, [0.0] * points]
    NWIdx = 0

    for i in range(rowNum):
        for j in range(colNum):
            GCoords[i][j] = unDefData
            SV = 0.0
            SW = 0.0
            NWIdx = 0
            for p in range(pNum):
                if SCoords[p][2] == unDefData:
                    AllWeights[p] = -1
                    continue
                if X[j] == SCoords[p][0] and Y[i] == SCoords[p][1]:
                    GCoords[i][j] = SCoords[p][2]
                    break
                else:
                    w = 1 / (math.pow(X[j] - SCoords[p][0], 2) + math.pow(Y[i] - SCoords[p][1], 2))
                    AllWeights[p] = w
                    if NWIdx < points:
                        NW[0][NWIdx] = w
                        NW[1][NWIdx] = p
                    NWIdx += 1

            if GCoords[i][j] == unDefData:
                for p in range(pNum):
                    w = AllWeights[p]
                    if w == -1:
                        continue
                    aMin = NW[0][0]
                    aP = 0
                    for l in range(1, points):
                        if NW[0][l] < aMin:
                            aMin = NW[0][l]
                            aP = l
                    if w > aMin:
                        NW[0][aP] = w
                        NW[1][aP] = p
                for p in range(points):
                    SV += NW[0][p] * SCoords[int(NW[1][p])][2]
                    SW += NW[0][p]
                GCoords[i][j] = SV / SW

    # ---- Smooth with 5 points  (s = 0.5)
    s = 0.5
    for i in range(1, rowNum - 1):
        for j in range(1, colNum - 1):
            GCoords[i][j] = GCoords[i][j] + s / 4 * (GCoords[i + 1][j] + GCoords[i - 1][j]
                                                     + GCoords[i][j + 1] + GCoords[i][j - 1]
                                                     - 4 * GCoords[i][j])
    return GCoords


def exp_A():
    print('=' * 78)
    print('A. IDW：我的实现 vs Interpolate.java 原版（同一批散点/同一格网）')
    print('=' * 78)
    import random
    random.seed(20260828)
    # 20 个站点，经度 115.8~116.8、纬度 39.6~40.4，值 0~15
    pts = [[round(115.8 + random.random() * 1.0, 4),
            round(39.6 + random.random() * 0.8, 4),
            round(random.random() * 15, 3)] for _ in range(20)]
    grid_n = 40
    X = [115.8 + i * (1.0 / (grid_n - 1)) for i in range(grid_n)]
    Y = [39.6 + i * (0.8 / (grid_n - 1)) for i in range(grid_n)]

    a = interpolation_idw_neighbor_JAVA(pts, X, Y, 3, UNDEF)
    b = xr.interpolation_idw_neighbor(pts, X, Y, 3, UNDEF)

    # 平滑只作用于内部点（1..n-2），所以分开统计
    inner_a, inner_b, edge_a, edge_b = [], [], [], []
    for i in range(grid_n):
        for j in range(grid_n):
            is_inner = 0 < i < grid_n - 1 and 0 < j < grid_n - 1
            (inner_a if is_inner else edge_a).append(a[i][j])
            (inner_b if is_inner else edge_b).append(b[i][j])

    def stat(va, vb, tag):
        d = [abs(x - y) for x, y in zip(va, vb)]
        nz = sum(1 for x in d if x > 1e-9)
        rmse = math.sqrt(sum(x * x for x in d) / len(d))
        print(f'  {tag:<14} 点数 {len(d):>5}  不一致 {nz:>5}  最大差 {max(d):.4f}  RMSE {rmse:.4f}')

    stat(inner_a, inner_b, '内部点(受平滑)')
    stat(edge_a, edge_b, '边界点(不平滑)')
    print(f'  取值范围 JAVA: {min(min(r) for r in a):.2f} ~ {max(max(r) for r in a):.2f}')
    print(f'  取值范围 MINE: {min(min(r) for r in b):.2f} ~ {max(max(r) for r in b):.2f}')
    print('  -> 原版在 IDW 之后还有一遍 s=0.5 的 5 点平滑；我的实现没有这一步。')


# ---------------------------------------------------------------------------
# B. work() 步骤 1 的 trainData 写入方式
# ---------------------------------------------------------------------------

def exp_B():
    print()
    print('=' * 78)
    print('B. 步骤 1：trainData 按 jsonArray 下标写入 + 跳过 null 会留下什么')
    print('=' * 78)
    json_array = [
        {'station': '54401', 'l': 116.47, 'b': 39.80, 'v': 12.5},
        {'station': '54402', 'l': None,   'b': 39.75, 'v': 11.8},   # l 为 null -> 跳过
        {'station': '54403', 'l': 116.52, 'b': 39.75, 'v': 11.8},
        {'station': '54404', 'l': 116.30, 'b': 40.10, 'v': None},   # v 为 null -> 跳过
        {'station': '54405', 'l': 116.10, 'b': 39.90, 'v': 9.4},
    ]
    train = [[0.0, 0.0, 0.0] for _ in range(len(json_array))]   # 与 Java 完全一致
    vales, valid, minX, maxX, minY, maxY = [], 0, 0.0, 0.0, 0.0, 0.0
    for i, it in enumerate(json_array):
        l, b, v = it.get('l'), it.get('b'), it.get('v')
        if l is None or b is None or v is None:
            continue
        l, b, v = float(l), float(b), float(v)
        if minX == 0 or l < minX: minX = l
        if maxX == 0 or l > maxX: maxX = l
        if minY == 0 or b < minY: minY = b
        if maxY == 0 or b > maxY: maxY = b
        train[i][0], train[i][1], train[i][2] = l, b, v
        vales.append(str(v)); valid += 1

    print(f'  jsonArray {len(json_array)} 条，有效 {valid} 条')
    print('  trainData（Java 与我的实现都是这么写的）：')
    for k, r in enumerate(train):
        mark = '   <-- 被跳过，留下 (0,0,0)' if r == [0.0, 0.0, 0.0] else ''
        print(f'    [{k}] {r}{mark}')
    print(f'  这个数组会原样传给 interpolation_IDW_Neighbor(trainData, ...)，长度 = {len(train)}')
    print('  而 IDW 只跳掉 v == -9999 的点；(0,0,0) 的 v 是 0，**不会被跳掉**，')
    print('  于是它们会作为「位于几内亚湾、值=0」的站点参与插值。')

    out = xr.interpolation_idw_neighbor(train, [116.4], [39.8], 3, UNDEF)
    print(f'  实测：格点(116.4,39.8) 只用 3 个近邻时的插值结果 = {out[0][0]:.4f}')
    clean = [r for r in train if r[2] != 0.0 or r[0] != 0.0]
    out2 = xr.interpolation_idw_neighbor(clean, [116.4], [39.8], 3, UNDEF)
    print(f'  对照：把 (0,0,0) 行剔掉后 = {out2[0][0]:.4f}')


# ---------------------------------------------------------------------------
# C. 色带：LowValue 够不够
# ---------------------------------------------------------------------------

def exp_C():
    print()
    print('=' * 78)
    print('C. 真实帧的等值面多边形：LowValue / HighValue / IsHighCenter')
    print('=' * 78)
    from precipitation_xunteng import eqs_algorithm as eqs
    from precipitation_xunteng.layer_config import LAYERS

    src = [f for f in os.listdir(HERE) if f.lower().endswith('.json')
           and 'precipitation_layers' in f][0]
    data = json.load(open(os.path.join(HERE, src), encoding='utf-8'))['response']['data']
    Z, xs, ys, _ = eqs.extract_frame(data, data['dataTime'])
    meta = LAYERS['XTSKJSXS']
    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])
    polys, _ = xr.equi_surface_from_grid([r[:] for r in Z.tolist()],
                                         [float(v) for v in xs], [float(v) for v in ys],
                                         breaks, False)

    n_same = sum(1 for g in polys if g.LowValue == g.HighValue)
    print(f'  多边形 {len(polys)} 个，其中 LowValue == HighValue 的 {n_same} 个'
          f'（{n_same / len(polys) * 100:.0f}%）')
    back = max(polys, key=lambda g: g.Area)
    print(f'  面积最大的多边形（=背景）：area={back.Area:.4f}  '
          f'LowValue={back.LowValue}  HighValue={back.HighValue}  IsHighCenter={back.IsHighCenter}')
    hi = [g for g in polys if g.IsHighCenter and g.Area < back.Area]
    if hi:
        h = max(hi, key=lambda g: g.Area)
        print(f'  面积最大的降水区：      area={h.Area:.4f}  '
              f'LowValue={h.LowValue}  HighValue={h.HighValue}  IsHighCenter={h.IsHighCenter}')
    print()
    print('  按三种取值方式，各自有多少面积落到哪一档：')
    for mode, pick in (('low  (只用 LowValue)', lambda g: g.LowValue),
                       ('high (只用 HighValue)', lambda g: g.HighValue),
                       ('auto (按 IsHighCenter)', None)):
        area_by_band = {}
        for g in polys:
            c = xr.color_for_polygon(g, breaks, colors, 1.0, mode='auto' if pick is None else
                                     ('low' if 'low' in mode else 'high'))
            key = '不填色' if c is None else '#%02X%02X%02X' % tuple(int(v * 255) for v in c[:3])
            area_by_band[key] = area_by_band.get(key, 0.0) + g.Area
        tot = sum(area_by_band.values())
        desc = '  '.join(f'{k}:{v / tot * 100:.1f}%' for k, v in
                         sorted(area_by_band.items(), key=lambda kv: -kv[1]))
        print(f'    {mode:<22} {desc}')


# ---------------------------------------------------------------------------
# D. createGridXY_Num
# ---------------------------------------------------------------------------

def exp_D():
    print()
    print('=' * 78)
    print('D. createGridXY_Num：原版 vs 我的实现')
    print('=' * 78)
    Xlb, Ylb, Xrt, Yrt = 115.7, 39.5, 116.9, 40.5
    n = 7
    java = [Xlb + i * ((Xrt - Xlb) / (n - 1)) for i in range(n)]
    mine, _ = xr.create_grid_xy_num(Xlb, Ylb, Xrt, Yrt, n, n)
    same = all(a == b for a, b in zip(java, mine))
    print(f'  原版: {[round(v, 10) for v in java]}')
    print(f'  我的: {[round(v, 10) for v in mine]}')
    print(f'  逐点完全相同: {same}')


if __name__ == '__main__':
    exp_A()
    exp_B()
    exp_C()
    exp_D()
