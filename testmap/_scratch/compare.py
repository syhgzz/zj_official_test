# -*- coding: utf-8 -*-
"""
compare.py —— 把 wcontour Python 移植的结果与原始 Java (WContourDriver) 的
真值 JSON 逐阶段数值比对。

用法:
    python compare.py                 # 比对 cases/ 下全部用例
    python compare.py case10_real_jsxs_1200
    python compare.py --dump case01_plane_5x5   # 同时把 Python 结果写成 json 便于手工 diff

比对阶段（任一阶段不一致都会报出来）:
    S1 (tracingBorders 的标记矩阵)
    borders      (Border / BorderLine 全字段)
    contourLines (平滑前的等值线)
    smoothLines  (平滑后的等值线)
    polygons     (最终多边形：字段 + 外环 + 洞)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, 'cases')
TRUTH = os.path.join(HERE, 'truth')
sys.path.insert(0, r'E:\work\zj_official_test')

from precipitation_xunteng.wcontour import borders as wb            # noqa: E402
from precipitation_xunteng.wcontour import contour_lines as wcl     # noqa: E402
from precipitation_xunteng.wcontour import smoothing as wsm         # noqa: E402
from precipitation_xunteng.wcontour import polygons as wp           # noqa: E402
from precipitation_xunteng.wcontour.global_types import (           # noqa: E402
    Border, BorderLine, BorderPoint, Extent, IJPoint, PointD, PolyLine, Polygon)


# --------------------------------------------------------------------- input

def load_case(name):
    path = os.path.join(CASES, name + '.txt')
    with open(path, encoding='utf-8') as f:
        tok = f.read().split()
    p = [0]

    def nxt():
        v = tok[p[0]]
        p[0] += 1
        return v

    def expect(s):
        v = nxt()
        assert v == s, f'expected {s} got {v}'

    expect('M'); m = int(nxt())
    expect('N'); n = int(nxt())
    expect('UNDEF'); undef = float(nxt())
    expect('NC'); nc = int(nxt())
    expect('X'); X = [float(nxt()) for _ in range(n)]
    expect('Y'); Y = [float(nxt()) for _ in range(m)]
    expect('CONTOUR'); contour = [float(nxt()) for _ in range(nc)]
    expect('GRID')
    S0 = [[float(nxt()) for _ in range(n)] for _ in range(m)]
    return dict(m=m, n=n, undef=undef, nc=nc, X=X, Y=Y, contour=contour, S0=S0)


# ------------------------------------------------------------------ pipeline

def run_pipeline(case):
    S0, X, Y, contour = case['S0'], case['X'], case['Y'], case['contour']
    undef, nc = case['undef'], case['nc']
    m, n = case['m'], case['n']

    S1 = [[0] * n for _ in range(m)]
    bl = wb.tracingBorders(S0, X, Y, S1, undef)
    cl = wcl.tracingContourLines(S0, X, Y, nc, contour, undef, bl, S1)

    # snapshot before smoothing (smoothLines mutates PointList in place)
    pre = [([(p.X, p.Y) for p in l.PointList], l.Value, l.Type, l.BorderIdx) for l in cl]
    sl = wsm.smoothLines(cl)
    polys = wp.tracingPolygons(S0, sl, bl, contour)

    out = {}
    out['S1'] = [list(r) for r in S1]
    out['borders'] = [dict(
        lineNum=b.getLineNum(),
        lines=[dict(area=l.area,
                    extent=[l.extent.xMin, l.extent.yMin, l.extent.xMax, l.extent.yMax],
                    isOutLine=l.isOutLine, isClockwise=l.isClockwise,
                    points=[[p.X, p.Y] for p in l.pointList],
                    ij=[[q.I, q.J] for q in l.ijPointList]) for l in b.LineList]
    ) for b in bl]
    out['contourLines'] = [dict(value=v, type=t, borderIdx=bi,
                                points=[[x, y] for x, y in pts]) for pts, v, t, bi in pre]
    out['smoothLines'] = [_pline(l) for l in sl]
    out['polygons'] = [_polygon(g) for g in polys]
    return out


def _pline(l):
    return dict(value=l.Value, type=l.Type, borderIdx=l.BorderIdx,
                points=[[p.X, p.Y] for p in l.PointList])


def _polygon(g):
    return dict(
        isBorder=g.IsBorder, isInnerBorder=g.IsInnerBorder,
        lowValue=g.LowValue, highValue=g.HighValue, isClockWise=g.IsClockWise,
        startPointIdx=g.StartPointIdx, isHighCenter=g.IsHighCenter,
        area=g.Area,
        extent=[g.Extent.xMin, g.Extent.yMin, g.Extent.xMax, g.Extent.yMax],
        nHoles=len(g.HoleLines),
        outline=_pline(g.OutLine),
        holes=[_pline(h) for h in g.HoleLines],
    )


# -------------------------------------------------------------------- compare

class Diff(Exception):
    pass


def near(a, b):
    """Java 端 null 代表 NaN/Inf，统一按 NaN 处理。"""
    fa = float('nan') if a is None else float(a)
    fb = float('nan') if b is None else float(b)
    if fa != fa and fb != fb:
        return True, 0.0
    if fa != fa or fb != fb:
        return False, float('inf')
    d = abs(fa - fb)
    return (fa == fb), d


def cmp_num(path, a, b, errs, maxd):
    ok, d = near(a, b)
    maxd[0] = max(maxd[0], d if d == d else 0.0)
    if not ok:
        errs.append(f'{path}: java={a!r} py={b!r} delta={d}')
    return ok


def cmp_int(path, a, b, errs):
    if a != b:
        errs.append(f'{path}: java={a!r} py={b!r}')
        return False
    return True


def cmp_bool(path, a, b, errs):
    if bool(a) != bool(b):
        errs.append(f'{path}: java={a!r} py={b!r}')
        return False
    return True


def cmp_str(path, a, b, errs):
    if a != b:
        errs.append(f'{path}: java={a!r} py={b!r}')
        return False
    return True


def cmp_points(path, ja, pa, errs, maxd, limit=6):
    if len(ja) != len(pa):
        errs.append(f'{path}: 点数 java={len(ja)} py={len(pa)}')
        return False
    bad = 0
    for k, (jp, pp) in enumerate(zip(ja, pa)):
        ok1 = cmp_num(f'{path}[{k}].X', jp[0], pp[0], errs if bad < limit else [], maxd)
        ok2 = cmp_num(f'{path}[{k}].Y', jp[1], pp[1], errs if bad < limit else [], maxd)
        if not (ok1 and ok2):
            bad += 1
    if bad:
        errs.append(f'{path}: {bad}/{len(ja)} 个点的坐标不一致')
        return False
    return True


def cmp_polyline(path, j, p, errs, maxd):
    ok = True
    ok &= cmp_num(path + '.value', j['value'], p['value'], errs, maxd)
    ok &= cmp_str(path + '.type', j['type'], p['type'], errs)
    ok &= cmp_int(path + '.borderIdx', j['borderIdx'], p['borderIdx'], errs)
    ok &= cmp_points(path + '.points', j['points'], p['points'], errs, maxd)
    return bool(ok)


def compare_stage(stage, j, p, errs, maxd):
    """返回该阶段是否一致。"""
    n0 = len(errs)
    if stage == 'S1':
        if len(j) != len(p):
            errs.append(f'S1 行数 java={len(j)} py={len(p)}')
        else:
            for i, (jr, pr) in enumerate(zip(j, p)):
                if list(jr) != list(pr):
                    errs.append(f'S1[{i}] 不一致')
                    break
    elif stage == 'borders':
        if len(j) != len(p):
            errs.append(f'borders 数量 java={len(j)} py={len(p)}')
        else:
            for i, (jb, pb) in enumerate(zip(j, p)):
                cmp_int(f'borders[{i}].lineNum', jb['lineNum'], pb['lineNum'], errs)
                for k, (jl, pl) in enumerate(zip(jb['lines'], pb['lines'])):
                    bp = f'borders[{i}].lines[{k}]'
                    cmp_num(bp + '.area', jl['area'], pl['area'], errs, maxd)
                    for f in range(4):
                        cmp_num(f'{bp}.extent[{f}]', jl['extent'][f], pl['extent'][f], errs, maxd)
                    cmp_bool(bp + '.isOutLine', jl['isOutLine'], pl['isOutLine'], errs)
                    cmp_bool(bp + '.isClockwise', jl['isClockwise'], pl['isClockwise'], errs)
                    cmp_points(bp + '.points', jl['points'], pl['points'], errs, maxd)
                    if len(jl['ij']) != len(pl['ij']):
                        errs.append(f'{bp}.ij 数量 java={len(jl["ij"])} py={len(pl["ij"])}')
                    else:
                        for q, (ji, pi) in enumerate(zip(jl['ij'], pl['ij'])):
                            if list(ji) != list(pi):
                                errs.append(f'{bp}.ij[{q}] java={ji} py={pi}')
                                break
    elif stage in ('contourLines', 'smoothLines'):
        if len(j) != len(p):
            errs.append(f'{stage} 数量 java={len(j)} py={len(p)}')
        else:
            for i, (jl, pl) in enumerate(zip(j, p)):
                cmp_polyline(f'{stage}[{i}]', jl, pl, errs, maxd)
    elif stage == 'polygons':
        if len(j) != len(p):
            errs.append(f'polygons 数量 java={len(j)} py={len(p)}')
        else:
            for i, (jg, pg) in enumerate(zip(j, p)):
                bp = f'polygons[{i}]'
                cmp_bool(bp + '.isBorder', jg['isBorder'], pg['isBorder'], errs)
                cmp_bool(bp + '.isInnerBorder', jg['isInnerBorder'], pg['isInnerBorder'], errs)
                cmp_num(bp + '.lowValue', jg['lowValue'], pg['lowValue'], errs, maxd)
                cmp_num(bp + '.highValue', jg['highValue'], pg['highValue'], errs, maxd)
                cmp_bool(bp + '.isClockWise', jg['isClockWise'], pg['isClockWise'], errs)
                cmp_int(bp + '.startPointIdx', jg['startPointIdx'], pg['startPointIdx'], errs)
                cmp_bool(bp + '.isHighCenter', jg['isHighCenter'], pg['isHighCenter'], errs)
                cmp_num(bp + '.area', jg['area'], pg['area'], errs, maxd)
                for f in range(4):
                    cmp_num(f'{bp}.extent[{f}]', jg['extent'][f], pg['extent'][f], errs, maxd)
                cmp_int(bp + '.nHoles', jg['nHoles'], pg['nHoles'], errs)
                cmp_polyline(bp + '.outline', jg['outline'], pg['outline'], errs, maxd)
                for h, (jh, ph) in enumerate(zip(jg['holes'], pg['holes'])):
                    cmp_polyline(f'{bp}.holes[{h}]', jh, ph, errs, maxd)
    return len(errs) == n0


STAGES = ['S1', 'borders', 'contourLines', 'smoothLines', 'polygons']


def run_one(name, dump=False, verbose=False):
    with open(os.path.join(TRUTH, name + '.json'), encoding='utf-8') as f:
        jtruth = json.load(f)
    case = load_case(name)
    t0 = time.time()
    py = run_pipeline(case)
    dt = time.time() - t0

    if dump:
        with open(os.path.join(HERE, 'py_' + name + '.json'), 'w', encoding='utf-8') as f:
            json.dump(py, f, ensure_ascii=False)

    result = {}
    allok = True
    for st in STAGES:
        errs, maxd = [], [0.0]
        ok = compare_stage(st, jtruth[st], py[st], errs, maxd)
        result[st] = (ok, maxd[0], errs)
        allok &= ok
    return allok, result, dt, py, jtruth


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    dump = '--dump' in sys.argv
    verbose = '-v' in sys.argv
    names = args or sorted(f[:-5] for f in os.listdir(TRUTH) if f.endswith('.json'))

    npass = 0
    for name in names:
        try:
            ok, result, dt, py, jtruth = run_one(name, dump=dump, verbose=verbose)
        except Exception as e:
            import traceback
            print(f'[ERROR] {name}: {type(e).__name__}: {e}')
            if verbose:
                traceback.print_exc()
            continue
        npass += ok
        head = 'PASS' if ok else 'FAIL'
        print(f'[{head}] {name}  ({dt:.2f}s)')
        for st in STAGES:
            ok_s, maxd, errs = result[st]
            jn = len(jtruth[st]) if isinstance(jtruth[st], list) else jtruth[st]
            flag = 'ok  ' if ok_s else 'DIFF'
            md = f' maxΔ={maxd:.3e}' if maxd else ''
            extra = '' if ok_s else f'  java_items={len(jn) if hasattr(jn, "__len__") else jn}'
            print(f'    {flag} {st:<13}{md}{extra}')
            if not ok_s:
                for e in errs[:6]:
                    print(f'         - {e}')
                if len(errs) > 6:
                    print(f'         ... 另有 {len(errs) - 6} 条')
    print(f'\n{ npass }/{len(names)} 用例全部阶段一致')


if __name__ == '__main__':
    main()
