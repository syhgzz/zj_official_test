# -*- coding: utf-8 -*-
"""_audit3.py —— 精确量化两个边界情况，避免结论夸大。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r'E:\work\zj_official_test')
from precipitation_xunteng import xunteng_reference as xr      # noqa: E402

UNDEF = -9999.0


def one(arr, x, y):
    return xr.interpolation_idw_neighbor(arr, [x], [y], 3, UNDEF)[0][0]


def clean(arr):
    return [r for r in arr if not (r[0] == 0.0 and r[1] == 0.0 and r[2] == 0.0)]


print('=' * 78)
print('G. (0,0,0) 空行的真实影响（用高精度看，不四舍五入）')
print('=' * 78)
cases = {
    '北京·有效点充足': ([[116.47, 39.80, 12.5], [0, 0, 0], [116.52, 39.75, 11.8],
                    [116.30, 40.10, 9.1], [0, 0, 0]], 116.4, 39.8),
    '北京·只有2个有效点': ([[116.47, 39.80, 12.5], [0, 0, 0], [116.52, 39.75, 11.8],
                     [0, 0, 0], [0, 0, 0]], 116.4, 39.8),
    '北京·只有1个有效点': ([[116.47, 39.80, 12.5], [0, 0, 0], [0, 0, 0]], 116.4, 39.8),
    '几内亚湾·3个有效点': ([[0.5, 0.5, 20.0], [0, 0, 0], [1.0, 0.2, 18.0],
                     [0.3, 1.1, 22.0], [0, 0, 0]], 0.6, 0.6),
}
for tag, (arr, x, y) in cases.items():
    v1 = one(arr, x, y)
    v2 = one(clean(arr), x, y)
    rel = abs(v1 - v2) / max(1e-12, abs(v2))
    flag = '  <== 明显偏差' if abs(v1 - v2) > 0.01 else ('  (可忽略)' if abs(v1 - v2) > 0 else '')
    print(f'  {tag:<20} 带空行={v1:.10f}  剔空行={v2:.10f}  绝对差={abs(v1 - v2):.3e}  相对差={rel:.2e}{flag}')

print()
print('  结论：空行的权重是 1/d²，北京离 (0,0) 约 15000（d²），相对另两个近邻的 d²≈0.005，')
print('        权重比约 3e-7，所以北京场景下影响 ~1e-7 量级，肉眼与出图都看不出来；')
print('        但如果数据本身就在 0° 附近（如上面几内亚湾那组），空行会变成"真·近邻"，直接污染结果。')
