# -*- coding: utf-8 -*-
"""
wcontour.smoothing —— wContour 1.6.1 ``Contour`` 中「平滑（Smoothing）」相关方法的
1:1 Python 移植（行为等价，不是重写）。

对应 Java 源码：``wcontour/_upstream/Contour.java``（= Contour.java）

    * ``smoothLines(List<PolyLine> aLineList)``          L912-950
    * ``BSplineScanning(List<PointD> pointList, int sum)`` L5190-5246
    * ``BSpline(List<PointD> pointList, double t, int i)`` L5248-5266
    * ``f0(double t)`` / ``f1`` / ``f2`` / ``f3``        L5268-5282
    * ``fb(double t, double[] fs)``                      L5284-5289

移植约定（见 ``PORTING_RULES.md``）：

* 逐行照抄：变量名、循环边界、语句顺序、看着多余的分支一律保留。
* 保留引用/别名语义：
  - ``smoothLines`` **原地改写** ``aline.PointList``，而 ``newLineList`` 里放的还是
    同一个 ``PolyLine`` 对象（``Value`` / ``Type`` / ``BorderIdx`` 一并保留）；
  - ``BSplineScanning`` 会**原地**修改传入的 ``pointList``（``remove(0)`` + 7 次 ``add``）；
  - ``fb`` **原地**写调用方传入的 ``fs``，不返回新 list；
  - ``BSpline`` 返回 ``double[]`` → Python ``list``（``[0.0, 0.0]`` 起）。
* Java ``double[] X = new double[n]`` → ``X = [0.0] * n``。
* Java ``float t;``（BSplineScanning 的循环变量）→ Python ``float``（本仓库约定：
  ``global_types.PointF`` 的 float 字段同样用 Python float），循环累加 ``t += 0.05``。
"""

import struct

from .global_types import PointD

# ---------------------------------------------------------------------------
# Java float（32 位）语义
# ---------------------------------------------------------------------------
# BSplineScanning 里 `float t;` + `for (t = 0; t <= 1; t += 0.05F)`：t 是**单精度**变量，
# 每次累加都在 float 上做舍入，然后再**加宽成 double** 传给 BSpline(double t, ...)。
# 用 Python 的 double 直接 `t += 0.05` 会累积出 ~1e-9 的差别（对拍 Java 真值时会被抓到），
# 所以这里显式做 float32 舍入。
_F005 = struct.unpack('f', struct.pack('f', 0.05))[0]


def _f32(x):
    """把 double 舍入到 Java float（IEEE-754 binary32），模拟 Java 的 float 变量。"""
    return struct.unpack('f', struct.pack('f', x))[0]



def smoothLines(aLineList):
    """Java: smoothLines(List<PolyLine> aLineList) L912-950

    对每条折线做 B 样条平滑。**原地**把 ``aline.PointList`` 换成平滑后的新 list，
    返回的 ``newLineList`` 里装的是**原来那些 PolyLine 对象本身**（不是新对象），
    因此 ``Value`` / ``Type`` / ``BorderIdx`` 都保持原样。

    注意 Java 的三个分支是顺序的三个 ``if``（不是 if/else-if），照抄：
    ``size() <= 1`` 直接 ``continue``（该线不会进入返回的 list）；
    ``size() == 2`` 先插两个 1/4、3/4 点（插完后 size 变成 4，故不会再进第三个 if）；
    ``size() == 3`` 插一个 1/2 点。

    :param aLineList: List[PolyLine]
    :return: List[PolyLine] —— 平滑后的折线列表（与输入共享 PolyLine 对象）
    """
    newLineList = []
    for i in range(len(aLineList)):
        aline = aLineList[i]
        newPList = list(aline.PointList)
        if len(newPList) <= 1:
            continue

        if len(newPList) == 2:
            bP = PointD()
            aP = newPList[0]
            cP = newPList[1]
            bP.X = (cP.X - aP.X) / 4 + aP.X
            bP.Y = (cP.Y - aP.Y) / 4 + aP.Y
            newPList.insert(1, bP)
            bP = PointD()
            bP.X = (cP.X - aP.X) / 4 * 3 + aP.X
            bP.Y = (cP.Y - aP.Y) / 4 * 3 + aP.Y
            newPList.insert(2, bP)
        if len(newPList) == 3:
            bP = PointD()
            aP = newPList[0]
            cP = newPList[1]
            bP.X = (cP.X - aP.X) / 2 + aP.X
            bP.Y = (cP.Y - aP.Y) / 2 + aP.Y
            newPList.insert(1, bP)
        newPList = BSplineScanning(newPList, len(newPList))
        aline.PointList = newPList
        newLineList.append(aline)

    return newLineList


def BSplineScanning(pointList, sum):
    """Java: BSplineScanning(List<PointD> pointList, int sum) L5190-5246

    逐段（每 4 个控制点一段）以 0.05 步长采样三次 B 样条。

    照抄要点：

    * ``sum < 4`` 返回 ``null`` → Python ``None``；
    * 首尾点相同时视为闭合线：**原地** ``remove(0)`` 后再 ``add`` 7 个点
      （``get(0)..get(6)``，注意每次 ``add`` 读到的是当前 list 的内容 —— 前 7 个元素在
      追加过程中不变），随后 ``sum = pointList.size()`` 重新取长度；
    * 闭合线只在 ``i > 3`` 时收集采样点，最后再补一个首点；
      非闭合线则把原始首点插到最前、原始末点追加到最后；
    * ``t`` 是 Java ``float``，``for (t = 0; t <= 1; t += 0.05F)`` 即 t 取
      0.0, 0.05, ..., 0.95 共 20 次（累加到第 21 次时 t > 1 退出）。
      **这里用 ``_f32`` 显式模拟 float32 累加**，否则与 Java 真值会有 ~1e-9 的逐点差异。

    :param pointList: List[PointD] —— **会被原地修改**（闭合线分支）
    :param sum: int —— Java 传入的是 ``pointList.size()``
    :return: List[PointD]，或 ``None``
    """
    t = 0.0
    i = 0
    X = 0.0
    Y = 0.0
    aPoint = None
    newPList = []

    if sum < 4:
        return None

    isClose = False
    aPoint = pointList[0]
    bPoint = pointList[sum - 1]
    if aPoint.X == bPoint.X and aPoint.Y == bPoint.Y:
        pointList.pop(0)
        pointList.append(pointList[0])
        pointList.append(pointList[1])
        pointList.append(pointList[2])
        pointList.append(pointList[3])
        pointList.append(pointList[4])
        pointList.append(pointList[5])
        pointList.append(pointList[6])
        isClose = True

    sum = len(pointList)
    for i in range(sum - 3):
        t = _f32(0.0)
        while t <= 1:
            xy = BSpline(pointList, t, i)
            X = xy[0]
            Y = xy[1]
            if isClose:
                if i > 3:
                    aPoint = PointD()
                    aPoint.X = X
                    aPoint.Y = Y
                    newPList.append(aPoint)
            else:
                aPoint = PointD()
                aPoint.X = X
                aPoint.Y = Y
                newPList.append(aPoint)
            t = _f32(t + _F005)

    if isClose:
        newPList.append(newPList[0])
    else:
        newPList.insert(0, pointList[0])
        newPList.append(pointList[len(pointList) - 1])

    return newPList


def BSpline(pointList, t, i):
    """Java: BSpline(List<PointD> pointList, double t, int i) L5248-5266

    用第 ``i..i+3`` 个控制点与基函数 ``f[0..3]`` 求参数 ``t`` 处的样条点。

    Java ``double[] f = new double[4]; fb(t, f);`` → ``f = [0.0] * 4; fb(t, f)``（原地填充）。
    返回值 Java 是 ``double[] xy = new double[2]`` → Python ``[0.0, 0.0]``。

    :return: List[float] —— ``[X, Y]``
    """
    f = [0.0] * 4
    fb(t, f)
    j = 0
    X = 0.0
    Y = 0.0
    aPoint = None
    for j in range(4):
        aPoint = pointList[i + j]
        X = X + f[j] * aPoint.X
        Y = Y + f[j] * aPoint.Y

    xy = [0.0] * 2
    xy[0] = X
    xy[1] = Y

    return xy


def f0(t):
    """Java: f0(double t) L5268-5270 —— 三次 B 样条基函数。"""
    return 1.0 / 6 * (-t + 1) * (-t + 1) * (-t + 1)


def f1(t):
    """Java: f1(double t) L5272-5274 —— 三次 B 样条基函数。"""
    return 1.0 / 6 * (3 * t * t * t - 6 * t * t + 4)


def f2(t):
    """Java: f2(double t) L5276-5278 —— 三次 B 样条基函数。"""
    return 1.0 / 6 * (-3 * t * t * t + 3 * t * t + 3 * t + 1)


def f3(t):
    """Java: f3(double t) L5280-5282 —— 三次 B 样条基函数。"""
    return 1.0 / 6 * t * t * t


def fb(t, fs):
    """Java: fb(double t, double[] fs) L5284-5289

    **原地**把四个基函数值写进调用方传入的 ``fs``（Java 返回 void），不返回新 list。
    """
    fs[0] = f0(t)
    fs[1] = f1(t)
    fs[2] = f2(t)
    fs[3] = f3(t)
