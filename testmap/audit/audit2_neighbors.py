# -*- coding: utf-8 -*-
"""
_audit2.py —— 追查 A 里"边界点也不一致"的根因。

怀疑：Interpolate.interpolation_IDW_Neighbor 的"维护 top-N 权重"那一段
（Interpolate.java L210-229）会把同一个站点写进多个邻居槽位，导致 SV/SW 重复计权。
本脚本逐格点记录 NW 里的站点下标，统计重复情况，并与"真正的 top-3"对比。
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'E:\work\zj_official_test')

UNDEF = -9999.0


def java_idw_with_trace(SCoords, X, Y, points, unDefData):
    """逐行移植，但额外记录每个格点最终 NW 里的站点下标。"""
    rowNum, colNum, pNum = len(Y), len(X), len(SCoords)
    G = [[0.0] * colNum for _ in range(rowNum)]
    traced = [[None] * colNum for _ in range(rowNum)]
    AllWeights = [0.0] * pNum
    NW = [[0.0] * points, [0.0] * points]
    for i in range(rowNum):
        for j in range(colNum):
            G[i][j] = unDefData
            SV = SW = 0.0
            NWIdx = 0
            for p in range(pNum):
                if SCoords[p][2] == unDefData:
                    AllWeights[p] = -1
                    continue
                if X[j] == SCoords[p][0] and Y[i] == SCoords[p][1]:
                    G[i][j] = SCoords[p][2]
                    break
                w = 1 / (math.pow(X[j] - SCoords[p][0], 2) + math.pow(Y[i] - SCoords[p][1], 2))
                AllWeights[p] = w
                if NWIdx < points:
                    NW[0][NWIdx] = w
                    NW[1][NWIdx] = p
                NWIdx += 1
            if G[i][j] == unDefData:
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
                G[i][j] = SV / SW
                traced[i][j] = [int(NW[1][p]) for p in range(points)]
    return G, traced


def true_topn(SCoords, x, y, points):
    cand = [(math.pow(x - s[0], 2) + math.pow(y - s[1], 2), k)
            for k, s in enumerate(SCoords) if s[2] != UNDEF]
    cand.sort()
    return [k for _, k in cand[:points]]


def main():
    print('=' * 78)
    print('E. 原版 IDW 的邻居选择：是否会把同一站点重复计入？')
    print('=' * 78)
    random.seed(20260828)
    pts = [[round(115.8 + random.random() * 1.0, 4),
            round(39.6 + random.random() * 0.8, 4),
            round(random.random() * 15, 3)] for _ in range(20)]
    n = 40
    X = [115.8 + i * (1.0 / (n - 1)) for i in range(n)]
    Y = [39.6 + i * (0.8 / (n - 1)) for i in range(n)]

    G, traced = java_idw_with_trace(pts, X, Y, 3, UNDEF)

    dup = 0
    not_top = 0
    total = 0
    examples = []
    for i in range(n):
        for j in range(n):
            idx = traced[i][j]
            if idx is None:
                continue
            total += 1
            if len(set(idx)) < len(idx):
                dup += 1
                if len(examples) < 3:
                    examples.append((i, j, idx, true_topn(pts, X[j], Y[i], 3)))
            elif sorted(idx) != sorted(true_topn(pts, X[j], Y[i], 3)):
                not_top += 1

    print(f'  参与统计的格点 {total}')
    print(f'  邻居槽位里有**重复站点**的格点: {dup}  ({dup / total * 100:.1f}%)')
    print(f'  无重复但选出的不是真正最近 3 个的格点: {not_top}  ({not_top / total * 100:.1f}%)')
    for i, j, got, want in examples:
        print(f'    例: 格点[{i}][{j}] 原版选中站点下标={got}（有重复），真正的最近3个={want}')

    # 量化影响：把重复槽位改成真正的 top-3，看结果差多少
    my = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            best = true_topn(pts, X[j], Y[i], 3)
            sw = sv = 0.0
            for k in best:
                w = 1 / (math.pow(X[j] - pts[k][0], 2) + math.pow(Y[i] - pts[k][1], 2))
                sv += w * pts[k][2]
                sw += w
            my[i][j] = sv / sw
    # 去掉原版的 5 点平滑，直接比"纯 IDW"部分
    d = [abs(G[i][j] - my[i][j]) for i in range(n) for j in range(n)]
    print(f'\n  原版（纯 IDW，未平滑）vs 真正的 top-3 权重平均：')
    print(f'    最大差 {max(d):.4f}   平均差 {sum(d) / len(d):.4f}')

    print()
    print('=' * 78)
    print('F. (0,0,0) 空行什么时候真的会造成偏差？')
    print('=' * 78)
    from precipitation_xunteng import xunteng_reference as xr

    # 情形 1：有效点很多 -> 空行进不了 top-3，无影响
    many = [[116.47, 39.80, 12.5], [0.0, 0.0, 0.0], [116.52, 39.75, 11.8],
            [116.30, 40.10, 9.1], [116.10, 39.90, 9.4]]
    # 情形 2：只有 2 个有效点 -> 第 3 个近邻只能是 (0,0,0)
    few = [[116.47, 39.80, 12.5], [0.0, 0.0, 0.0], [116.52, 39.75, 11.8],
           [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for tag, arr in (('有效点充足(3+)', many), ('只有 2 个有效点', few)):
        v1 = xr.interpolation_idw_neighbor(arr, [116.4], [39.8], 3, UNDEF)[0][0]
        clean = [r for r in arr if not (r[0] == 0.0 and r[1] == 0.0 and r[2] == 0.0)]
        v2 = xr.interpolation_idw_neighbor(clean, [116.4], [39.8], 3, UNDEF)[0][0]
        flag = '  <-- 明显偏差' if abs(v1 - v2) > 0.05 else ''
        print(f'  {tag:<16} 带空行={v1:8.4f}   剔掉空行={v2:8.4f}   差 {abs(v1 - v2):.4f}{flag}')


if __name__ == '__main__':
    main()
