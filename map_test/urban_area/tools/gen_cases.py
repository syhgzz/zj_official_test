# -*- coding: utf-8 -*-
"""
gen_cases.py —— 生成 wContour 移植对拍用的用例（合成算例 + 真实接口帧）。

用例文件是纯空白分隔的 token 文本，由 WContourDriver 读取：
    M <m> / N <n> / UNDEF <v> / NC <nc> / X <n 个> / Y <m 个> / CONTOUR <nc 个> / GRID <m*n 个>

S0[i][j]：i 是行(Y)，j 是列(X)，与 wContour 的约定一致。
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(HERE)
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
RUNDIR = os.environ.get('WCONTOUR_PARITY_DIR', os.path.join(HERE, '_parity_run'))
CASES = os.path.join(RUNDIR, 'cases')

DEFAULT_RESPONSES = os.path.join(PROJECT_DIR, 'responses')
DEFAULT_RAW = os.path.join(PACKAGE_DIR, 'data', 'raw')

UNDEF = -9999.0


def write_case(name, S0, X, Y, contour, undef=UNDEF, note=''):
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
    XX, YY = np.meshgrid(np.arange(n, dtype=float), np.arange(m, dtype=float))
    return amp * np.exp(-(((XX - cx) ** 2 + (YY - cy) ** 2) / (2 * sigma ** 2)))


def axis(n, lo=115.0, step=0.01):
    return lo + np.arange(n) * step


def synthetic_cases():
    """9 个合成算例：覆盖无缺测 / 缺测洞 / 缺测环 / 缺测带 / 常量场 / 值恰好落在等值线上 等分支。"""
    out = []
    S0 = np.add.outer(np.arange(5, dtype=float), np.zeros(5))
    out.append(write_case('case01_plane_5x5', S0, axis(5, 116.0), axis(5, 39.0),
                          [0.5, 1.5, 2.5, 3.5], note='no undef, regular ramp'))

    S0 = radial(40, 40, amp=10.0, sigma=7.0)
    out.append(write_case('case02_radial_40x40', S0, axis(40), axis(40),
                          [0.5, 2.0, 5.0, 8.0], note='closed contours, no undef'))

    S0 = radial(30, 30, amp=8.0, sigma=6.0)
    S0[10:16, 10:16] = UNDEF
    out.append(write_case('case03_undef_hole', S0, axis(30), axis(30),
                          [1.0, 3.0, 5.0, 7.0], note='square undef hole'))

    S0 = radial(36, 36, amp=9.0, sigma=8.0)
    S0[16:20, 16:20] = UNDEF
    out.append(write_case('case04_undef_ring', S0, axis(36), axis(36),
                          [1.0, 3.0, 5.0, 7.0], note='undef at peak -> Ring branch'))

    S0 = (radial(40, 40, cx=12, cy=13, amp=6.0, sigma=5.0)
          + radial(40, 40, cx=27, cy=26, amp=9.0, sigma=6.0))
    S0[3:6, 30:34] = UNDEF
    S0[33:37, 5:9] = UNDEF
    S0[19:21, 19:22] = UNDEF
    out.append(write_case('case05_two_hills_undef', S0, axis(40), axis(40),
                          [1.0, 2.0, 4.0, 6.0, 8.0], note='two centres + 3 undef patches'))

    S0 = np.tile(np.linspace(0.0, 10.0, 40), (30, 1))
    S0[12:18, :] = UNDEF
    out.append(write_case('case06_undef_band', S0, axis(40), axis(30),
                          [1.0, 4.0, 7.0], note='undef band splits domain in two'))

    S0 = np.full((12, 12), 3.0)
    out.append(write_case('case07_constant', S0, axis(12), axis(12),
                          [0.0, 0.1, 1.6, 7.0], note='constant field, heavy ties'))

    S0 = np.tile(np.arange(10, dtype=float), (10, 1))
    out.append(write_case('case08_exact_levels', S0, axis(10), axis(10),
                          [0.0, 3.0, 5.0, 9.0], note='values exactly equal to levels'))

    S0 = radial(40, 40, amp=5.0, sigma=10.0)
    S0[14:26, 14:26] = UNDEF
    S0[0:2, :] = UNDEF
    S0[-2:, :] = UNDEF
    out.append(write_case('case09_undef_ring_frame', S0, axis(40), axis(40),
                          [1.0, 2.5, 4.0], note='donut-shaped valid area'))
    return out


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
    except AttributeError:                                  # shapely < 2
        from shapely.vectorized import contains
        return contains(geom, XX, YY)


def load_payload(path):
    """兼容两种落盘格式（结果文件夹 / fetch_layers 缓存）。"""
    with open(path, encoding='utf-8') as f:
        j = json.load(f)
    resp = j['response'] if isinstance(j.get('response'), dict) else j
    return resp.get('data')


def real_cases(extra_inputs=()):
    """真实接口帧：结果文件夹里的 XTSKJSXS（含裁剪版）+ data/raw 里的 PWV。"""
    from jingyao_test.Urban_area.layer_config import LAYERS

    out = []
    resp_files = [p for p in extra_inputs]
    if not resp_files and os.path.isdir(DEFAULT_RESPONSES):
        resp_files = [os.path.join(DEFAULT_RESPONSES, f) for f in sorted(os.listdir(DEFAULT_RESPONSES))
                      if 'XTSKJSXS' in f and f.lower().endswith('.json')]
    for resp_file in resp_files:
        try:
            data = load_payload(resp_file)
        except Exception as e:
            print(f'  跳过 {os.path.basename(resp_file)}: {e}')
            continue
        if not data or 'rowsList' not in data:
            continue
        layer = data.get('layer')
        meta = LAYERS.get(layer)
        if not meta:
            continue
        contour = [float(k) for k in sorted(json.loads(meta['colorStr']), key=float)]
        frame_ms = data['dataTime']
        Z, xs, ys = extract_frame(data, frame_ms)
        out.append(write_case(f'case10_real_{layer.lower()}_1200', Z, xs, ys, contour,
                              note=f'interface {layer} 2026-08-28 12:00, no undef'))
        area = (data.get('groups') or [{}])[0].get('area')
        if area:
            inside = beijing_mask(xs, ys, area)
            Zc = Z.copy()
            Zc[~inside] = UNDEF
            out.append(write_case(f'case11_real_{layer.lower()}_1200_clip', Zc, xs, ys, contour,
                                  note=f'clipped to beijing ({int((~inside).sum())} undef cells)'))

    rawf = os.path.join(DEFAULT_RAW, 'XTSKPWV_2026-08-28_00-12.json')
    if os.path.exists(rawf):
        data = load_payload(rawf)
        frames = sorted({r.get('dataTime') for r in (data.get('rowsList') or [])})
        if frames:
            contour = [float(k) for k in sorted(json.loads(LAYERS['XTSKPWV']['colorStr']), key=float)]
            Z, xs, ys = extract_frame(data, frames[-1])
            out.append(write_case('case12_real_xtskpwv_1200', Z, xs, ys, contour,
                                  note='interface XTSKPWV last frame (12:00)'))
    return out


def main(extra_inputs=()):
    os.makedirs(CASES, exist_ok=True)
    manifest = synthetic_cases() + real_cases(extra_inputs)
    with open(os.path.join(CASES, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f'生成 {len(manifest)} 个用例 -> {CASES}')
    for e in manifest:
        print(f"  {e['name']:<30} m={e['m']:<4} n={e['n']:<4} nc={e['nc']}  {e['note']}")
    return manifest


if __name__ == '__main__':
    sys.path.insert(0, PROJECT_DIR)
    main(sys.argv[1:])
