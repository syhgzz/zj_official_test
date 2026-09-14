# -*- coding: utf-8 -*-
"""
wcontour —— wContour 1.6.1 等值面追踪子集的 1:1 Python 移植（LGPL-3.0）。

只移植迅腾 `equiSurfaceImg` 参考实现用到的调用链：

    tracingBorders -> tracingContourLines -> smoothLines -> tracingPolygons

上游：meteoinfo/wContour, src/main/java/wcontour/Contour.java (LGPL-3.0)
原始 Java 源码见 `_upstream/`，移植规则见 `PORTING_RULES.md`。

注意：本包内的函数是**逐行等价移植**，保留了 Java 原版的变量名与写法
（包括看起来可疑但必须照抄的边界处理）。不要在这里做"优化"。
"""

__all__ = [
    'global_types',
    'helpers',
    'smoothing',
    'borders',
    'contour_lines',
    'polygons',
    'polygons_trace',
]
