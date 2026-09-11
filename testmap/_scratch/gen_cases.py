# -*- coding: utf-8 -*-
"""
Generate ground-truth test cases for the wContour port.

Writes plain-token input files consumed by WContourDriver, plus a manifest.
Run with the project venv:
    E:\\work\\zj_official_test\\.venv\\Scripts\\python.exe gen_cases.py
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(HERE, 'cases')
RESPONSES = r'E:\work\zj_official_test\responses'
RAW = r'E:\work\zj_official_test\precipitation_xunteng\data\raw'

UNDEF = -9999.0


def write_case(name, S0, X, Y, contour, undef=UNDEF, note=''):
    """Write one driver input file; returns manifest entry."""
    m, n = S0.shape
    path = os.path.join(CASES, name + '.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'M {m}\nN {n}\nUNDEF {undef!r}\nNC {len(contour)}\n')
        f.write('X ' + ' '.join(repr(float(v)) for v in X) + '\n')
        f.write('Y ' + ' '.join(repr(float(v)) for v in Y) + '\n')
        f.write('CONTOUR ' + ' '.join(repr(float(v)) for v in contour) + '\n')
        f.write('GRID\n')
        for i in range(m):
            f.write(' '.join(repr(float(v)) for v in S0[i]) + '\n')
    return dict(name=name, m=int(m), n=int(n), nc=len(contour), undef=undef,
                note=note, input=path)


def radial(m, n, cx=None, cy=None, amp=1.0, sigma=None):
    cx = (n - 1) / 2 if cx is None else cx
    cy = (m - 1) / 2 if cy is None else cy
    sigma = min(m, n) / 4 if sigma is None else sigma
    X = np.arange(n, dtype=float)
    Y = np.arange(m, dtype=float)
    XX, YY = np.meshgrid(X, Y)
    return amp * np.exp(-(((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * sigma ** 2)))


def axis(n, lo=115.0, step=0.01):
    return lo + np.arange(n) * step


def main():
    os.makedirs(CASES, exist_ok=True)
    manifest = []

    # ---- 01: plain plane, no undef, 5x5 --------------------------------
    S0 = np.add.outer(np.arange(5, dtype=float), np.zeros(5))
    manifest.append(write_case('case01_plane_5x5', S0, axis(5, 116.0), axis(5, 39.0),
                               [0.5, 1.5, 2.5, 3.5], note='no undef, regular ramp'))

    # ---- 02: single radial hill, larger levels --------------------------
    S0 = radial(40, 40, amp=10.0, sigma=7.0)
    manifest.append(write_case('case02_radial_40x40', S0, axis(40), axis(40),
                               [0.5, 2.0, 5.0, 8.0], note='closed contours, no undef'))

    # ---- 03: radial hill with one undef hole ----------------------------
    S0 = radial(30, 30, amp=8.0, sigma=6.0)
    S0[10:16, 10:16] = UNDEF
    manifest.append(write_case('case03_undef_hole', S0, axis(30), axis(30),
                               [1.0, 3.0, 5.0, 7.0], note='square undef hole'))

    # ---- 04: undef hole in the middle of a high centre (ring path) ------
    S0 = radial(36, 36, amp=9.0, sigma=8.0)
    S0[16:20, 16:20] = UNDEF          # hole right at the peak -> Ring branch
    manifest.append(write_case('case04_undef_ring', S0, axis(36), axis(36),
                               [1.0, 3.0, 5.0, 7.0], note='undef at peak -> Ring branch'))

    # ---- 05: two hills + scattered undef patches ------------------------
    S0 = (radial(40, 40, cx=12, cy=13, amp=6.0, sigma=5.0)
          + radial(40, 40, cx=27, cy=26, amp=9.0, sigma=6.0))
    S0[3:6, 30:34] = UNDEF
    S0[33:37, 5:9] = UNDEF
    S0[19:21, 19:22] = UNDEF
    manifest.append(write_case('case05_two_hills_undef', S0, axis(40), axis(40),
                               [1.0, 2.0, 4.0, 6.0, 8.0], note='two centres + 3 undef patches'))

    # ---- 06: gradient + undef band across full width --------------------
    S0 = np.tile(np.linspace(0.0, 10.0, 40), (30, 1))
    S0[12:18, :] = UNDEF
    manifest.append(write_case('case06_undef_band', S0, axis(40), axis(30),
                               [1.0, 4.0, 7.0], note='undef band splits domain in two'))

    # ---- 07: degenerate - constant field --------------------------------
    S0 = np.full((12, 12), 3.0)
    manifest.append(write_case('case07_constant', S0, axis(12), axis(12),
                               [0.0, 0.1, 1.6, 7.0], note='constant field, heavy ties'))

    # ---- 08: values exactly on contour levels ---------------------------
    S0 = np.tile(np.arange(10, dtype=float), (10, 1))
    manifest.append(write_case('case08_exact_levels', S0, axis(10), axis(10),
                               [0.0, 3.0, 5.0, 9.0], note='many values exactly equal to levels'))

    # ---- 09: undef ring frame (data only in a ring) ---------------------
    S0 = radial(40, 40, amp=5.0, sigma=10.0)
    mask = np.zeros((40, 40), dtype=bool)
    mask[14:26, 14:26] = True
    S0[mask] = UNDEF
    S0[0:2, :] = UNDEF
    S0[-2:, :] = UNDEF
    manifest.append(write_case('case09_undef_ring_frame', S0, axis(40), axis(40),
                               [1.0, 2.5, 4.0], note='donut-shaped valid area'))

    # ---- real interface data -------------------------------------------
    real = load_real_cases()
    manifest.extend(real)

    with open(os.path.join(CASES, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f'wrote {len(manifest)} cases to {CASES}')
    for e in manifest:
        print(f"  {e['name']:<28} m={e['m']:<4} n={e['n']:<4} nc={e['nc']}  {e['note']}")


def extract_frame(data, target_ms):
    rows = [r for r in (data.get('rowsList') or []) if r.get('dataTime') == target_ms]
    if not rows:
        raise ValueError(f'no frame for {target_ms}')
    rows.sort(key=lambda r: r.get('currentRow', 0))
    xs = np.array([float(p.split(',')[0]) for p in rows[0]['gridLocations']])
    ys = np.array([float(r['gridLocations'][0].split(',')[1]) for r in rows])
    Z = np.array([[float(v) if v is not None else UNDEF for v in r['gridValues']] for r in rows])
    return Z, xs, ys


def beijing_mask(xs, ys, area_wkt):
    import shapely
    geom = shapely.from_wkt(area_wkt)
    XX, YY = np.meshgrid(xs, ys)
    try:
        return shapely.contains_xy(geom, XX, YY)
    except AttributeError:
        from shapely.vectorized import contains
        return contains(geom, XX, YY)


def load_real_cases():
    out = []
    resp_file = None
    for fn in os.listdir(RESPONSES):
        if 'XTSKJSXS' in fn and fn.endswith('.json'):
            resp_file = os.path.join(RESPONSES, fn)
    if resp_file:
        with open(resp_file, encoding='utf-8') as f:
            j = json.load(f)
        data = j['response']['data']
        frame_ms = data['dataTime']
        Z, xs, ys = extract_frame(data, frame_ms)
        contour = [0.0, 0.1, 1.6, 7.0, 15.0, 40.0, 50.0]
        out.append(write_case('case10_real_jsxs_1200', Z, xs, ys, contour,
                              note='interface XTSKJSXS 2026-08-28 12:00, no undef'))
        area = (data.get('groups') or [{}])[0].get('area')
        if area:
            inside = beijing_mask(xs, ys, area)
            Zc = Z.copy()
            Zc[~inside] = UNDEF
            out.append(write_case('case11_real_jsxs_1200_clip', Zc, xs, ys, contour,
                                  note=f'interface 12:00 clipped to beijing '
                                       f'({int((~inside).sum())} undef cells)'))

    # PWV 12:00 from the raw 00-12 cache (13 frames, keep only 12:00)
    rawf = os.path.join(RAW, 'XTSKPWV_2026-08-28_00-12.json')
    if os.path.exists(rawf):
        with open(rawf, encoding='utf-8') as f:
            rj = json.load(f)
        data = rj['data'] if 'data' in rj else rj['response']['data']
        frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
        if frames:
            Z, xs, ys = extract_frame(data, frames[-1])
            contour = [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0]
            out.append(write_case('case12_real_pwv_1200', Z, xs, ys, contour,
                                  note='interface XTSKPWV last frame (12:00)'))
    return out


if __name__ == '__main__':
    main()
