# -*- coding: utf-8 -*-
"""
crosscheck_contourf.py —— 用两条**互相独立**的实现给同一帧出图，逐像素交叉比对：

  A) 参考算法链路：wContour 逐行移植的等值面追踪 + 区间填色（本轮交付）
  B) 既有实现：eqs_algorithm.render_equi_surface（matplotlib contourf 近似）

两者算法不同（等值线追踪/闭合成面 vs marching-squares 直接填色），若在色带覆盖上
高度一致，说明 A 的**色带语义与渲染映射**没搞错（追踪本身的正确性已由 Java 真值对拍保证）。
"""
import os
import sys

import numpy as np

sys.path.insert(0, r'E:\work\zj_official_test')

from precipitation_xunteng import eqs_algorithm as eqs        # noqa: E402
from precipitation_xunteng import xunteng_reference as xr      # noqa: E402
from precipitation_xunteng.layer_config import LAYERS          # noqa: E402

OUT = r'E:\work\zj_official_test\precipitation_xunteng\output'
SIZE = 1024


def render_reference(Z, xs, ys, breaks, colors, path):
    """A) 参考算法：等值面追踪 -> 按 IsHighCenter 选色带 -> 渲染。"""
    polys, info = xr.equi_surface_from_grid([row[:] for row in Z.tolist()],
                                            [float(v) for v in xs],
                                            [float(v) for v in ys], breaks, False)
    bbox = xr.frame_bbox(xs, ys)
    n = xr.get_map_content(polys, {'bbox': bbox, 'width': SIZE, 'height': SIZE},
                           path, breaks, colors, 1.0)
    return polys, info, n


def rgba_bands(img):
    """把 RGBA 图变成 0..len(colors) 的色带编号矩阵；-1 = 透明（未填色）。"""
    a = (img[:, :, 3] > 8)
    rgb = img[:, :, :3]
    keys = np.unique(rgb[a].reshape(-1, 3), axis=0) if a.any() else np.zeros((0, 3), np.uint8)
    out = np.full(img.shape[:2], -1, np.int16)
    for i, c in enumerate(keys):
        m = a & np.all(rgb == c, axis=2)
        out[m] = i
    return out, keys


def main():
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.image import imread

    layer = 'XTSKJSXS'
    meta = LAYERS[layer]
    breaks, colors = xr.parse_legend_color_map(meta['colorStr'])

    import json
    resp = os.path.join(r'E:\work\zj_official_test\responses',
                        '降水页_降雨图层格网数据_降水量(小时)_XTSKJSXS_None_'
                        '20260910_153138_api_v1_upns_precipitation_layers.json')
    data = json.load(open(resp, encoding='utf-8'))['response']['data']
    Z, xs, ys, _ = eqs.extract_frame(data, data['dataTime'])
    print(f'帧: 2026-08-28 12:00  格网 {len(ys)}x{len(xs)}  '
          f'值 {np.nanmin(Z):.2f}~{np.nanmax(Z):.2f}')

    p_a = os.path.join(OUT, '_xcheck_ref.png')
    p_b = os.path.join(OUT, '_xcheck_contourf.png')

    polys, info, n_drawn = render_reference(Z, xs, ys, breaks, colors, p_a)
    print(f'A 参考算法: {info}  已填色多边形 {n_drawn}')

    eqs.render_equi_surface(Z, xs, ys, breaks, colors, p_b,
                            width=SIZE, height=SIZE, undef=-9999.0)
    print('B contourf : 已出图')

    A = imread(p_a)
    B = imread(p_b)
    if A.shape[2] == 3:
        A = np.dstack([A, np.ones(A.shape[:2], A.dtype)])
    if B.shape[2] == 3:
        B = np.dstack([B, np.ones(B.shape[:2], B.dtype)])
    A = (A * 255).astype(np.uint8) if A.dtype.kind == 'f' else A
    B = (B * 255).astype(np.uint8) if B.dtype.kind == 'f' else B

    ma = A[:, :, 3] > 8
    mb = B[:, :, 3] > 8
    inter = int((ma & mb).sum())
    union = int((ma | mb).sum())
    print(f'\n覆盖掩膜(非透明像素): A={int(ma.sum())}  B={int(mb.sum())}  '
          f'交集={inter}  并集={union}  IoU={inter / union:.4f}')
    both = ma & mb
    if both.any():
        da = np.all(A[:, :, :3] == B[:, :, :3], axis=2)
        agree = int((both & da).sum())
        print(f'两图都填色的像素中，RGB 完全一致的占比: {agree / int(both.sum()):.4f}')
    print('\n各色带像素数（0=未填色）:')
    ba, ka = rgba_bands(A)
    bb, kb = rgba_bands(B)
    print(f'  A 参考算法 色带数(不含透明)={len(ka)}: '
          f'{ {i: int((ba == i).sum()) for i in range(len(ka))} }')
    print(f'  B contourf 色带数(不含透明)={len(kb)}: '
          f'{ {i: int((bb == i).sum()) for i in range(len(kb))} }')
    print(f'  两者"已填色"像素差: {abs(int(ma.sum()) - int(mb.sum()))} '
          f'({abs(int(ma.sum()) - int(mb.sum())) / max(1, int(mb.sum())) * 100:.2f}% of B)')


if __name__ == '__main__':
    main()
