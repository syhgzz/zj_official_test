# -*- coding: utf-8 -*-
"""_audit4.py —— 修正后的 (0,0,0) 空行实验：只有 <3 个有效点且数据在 0 度附近时才会咬人。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'E:\work\zj_official_test')
from precipitation_xunteng import xunteng_reference as xr      # noqa: E402

UNDEF = -9999.0
ZERO = [0.0, 0.0, 0.0]


def one(arr, x, y):
    return xr.interpolation_idw_neighbor(arr, [x], [y], 3, UNDEF)[0][0]


def clean(arr):
    return [r for r in arr if r != ZERO]


cases = [
    ('北京  有效点充足(5个)', [[116.47, 39.80, 12.5], ZERO, [116.52, 39.75, 11.8],
                          [116.30, 40.10, 9.1], [116.10, 39.90, 9.4]], 116.4, 39.8),
    ('北京  只有2个有效点', [[116.47, 39.80, 12.5], ZERO, [116.52, 39.75, 11.8],
                        ZERO, ZERO], 116.4, 39.8),
    ('0度附近 有效点充足(3个)', [[0.5, 0.5, 20.0], ZERO, [1.0, 0.2, 18.0],
                           [0.3, 1.1, 22.0], ZERO], 0.6, 0.6),
    ('0度附近 只有2个有效点', [[0.5, 0.5, 20.0], ZERO, [1.0, 0.2, 18.0],
                         ZERO, ZERO], 0.6, 0.6),
    ('0度附近 只有1个有效点', [[0.5, 0.5, 20.0], ZERO, ZERO, ZERO, ZERO], 0.6, 0.6),
]
print('=' * 78)
print('G. (0,0,0) 空行的真实影响 (高精度)')
print('=' * 78)
for tag, arr, x, y in cases:
    v1, v2 = one(arr, x, y), one(clean(arr), x, y)
    d = abs(v1 - v2)
    rel = d / max(1e-12, abs(v2))
    verdict = '明显偏差' if d > 0.05 else ('可忽略' if d > 0 else '完全无影响')
    print('  %-22s 带空行=%12.8f  剔空行=%12.8f  绝对差=%.3e  相对=%.2e  -> %s'
          % (tag, v1, v2, d, rel, verdict))
