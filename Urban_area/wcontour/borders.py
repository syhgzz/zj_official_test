# -*- coding: utf-8 -*-
"""
wcontour.borders —— wContour 1.6.1 `Contour.tracingBorders` / `Contour.traceBorder`
的 1:1 Python 移植（LGPL-3.0）。

对应上游：`_upstream/Contour.java`
    * ``tracingBorders(double[][] S0, double[] X, double[] Y, int[][] S1, double undefData)``
  L66-412
    * ``traceBorder(int[][] S1, int i1, int i2, int j1, int j2, int[] ij3)`` L1575-1817

移植约定（见 ``PORTING_RULES.md``）：

* ``S1`` 是调用方传入的 ``int[][]``，本模块**就地改写**它（``list[list[int]]``），
  绝不重新赋值成新对象。
* Java 里 ``S1[i][j]``：``i`` 是行(Y)索引，``j`` 是列(X)索引，不做转置。
* 循环边界（``m - 1``、``n - 1``、``>= 1``、``< m - 1`` 等）以及 ``while (true)`` +
  ``isContinue`` 的写法逐字照抄；凡是 Java 在循环体内会改变集合长度、因而循环条件
  会被**动态求值**的 ``for`` 循环，一律写成等价的 ``while``，以免 Python ``range()``
  一次性求值改变行为。
* ``a = b`` 表示共享同一对象；``new ArrayList<>()`` → ``[]``；``new Border()`` → ``Border()``。
"""

from .global_types import Border, BorderLine, IJPoint, PointD
from .helpers import doubleEquals, getExtentAndArea, isClockwise, pointInPolygon_poly


def tracingBorders(S0, X, Y, S1, undefData):
    """Java: tracingBorders(double[][] S0, double[] X, double[] Y, int[][] S1, double undefData) L66-412

    追踪含缺测数据的格点场的边界线。

    :param S0: 输入格点数据（``list[list[float]]``，第一维是 Y，第二维是 X）
    :param X: X 坐标数组
    :param Y: Y 坐标数组
    :param S1: 数据标志数组（``list[list[int]]``，**调用方所有，本函数原地改写**）
    :param undefData: 缺测值
    :return: ``list[Border]``
    """
    borderLines = []

    m = 0
    n = 0
    i = 0
    j = 0
    m = len(S0)    # Y
    n = len(S0[0])    # X

    # S1 = new int[m][n];    //---- New array (0 with undefine data, 1 with data)
    for i in range(0, m):
        for j in range(0, n):
            if doubleEquals(S0[i][j], undefData):    # Undefine data
                S1[i][j] = 0
            else:
                S1[i][j] = 1

    # ---- Border points are 1, undefine points are 0, inside data points are 2
    # l - Left; r - Right; b - Bottom; t - Top; lb - LeftBottom; rb - RightBottom;
    # lt - LeftTop; rt - RightTop
    l = 0
    r = 0
    b = 0
    t = 0
    lb = 0
    rb = 0
    lt = 0
    rt = 0
    for i in range(1, m - 1):
        for j in range(1, n - 1):
            if S1[i][j] == 1:    # data point
                l = S1[i][j - 1]
                r = S1[i][j + 1]
                b = S1[i - 1][j]
                t = S1[i + 1][j]
                lb = S1[i - 1][j - 1]
                rb = S1[i - 1][j + 1]
                lt = S1[i + 1][j - 1]
                rt = S1[i + 1][j + 1]

                if l > 0 and r > 0 and b > 0 and t > 0 and lb > 0 and rb > 0 and lt > 0 and rt > 0:
                    S1[i][j] = 2    # Inside data point
                if l + r + b + t + lb + rb + lt + rt <= 2:
                    S1[i][j] = 0    # Data point, but not more than 3 continued data points together.
                #                     So they can't be traced as a border (at least 4 points together).

    # ---- Remove isolated data points (up, down, left and right points are all undefine data).
    isContinue = False
    while True:
        isContinue = False
        for i in range(1, m - 1):
            for j in range(1, n - 1):
                if S1[i][j] == 1:    # data point
                    l = S1[i][j - 1]
                    r = S1[i][j + 1]
                    b = S1[i - 1][j]
                    t = S1[i + 1][j]
                    lb = S1[i - 1][j - 1]
                    rb = S1[i - 1][j + 1]
                    lt = S1[i + 1][j - 1]
                    rt = S1[i + 1][j + 1]
                    if (l == 0 and r == 0) or (b == 0 and t == 0):
                        # Up, down, left and right points are all undefine data
                        S1[i][j] = 0
                        isContinue = True
                    if ((lt == 0 and r == 0 and b == 0) or (rt == 0 and l == 0 and b == 0)
                            or (lb == 0 and r == 0 and t == 0) or (rb == 0 and l == 0 and t == 0)):
                        S1[i][j] = 0
                        isContinue = True
        if not isContinue:    # untile no more isolated data point.
            break

    # Deal with grid data border points
    for j in range(0, n):    # Top and bottom border points
        if S1[0][j] == 1:
            if S1[1][j] == 0:    # up point is undefine
                S1[0][j] = 0
            elif j == 0:
                if S1[0][j + 1] == 0:
                    S1[0][j] = 0
            elif j == n - 1:
                if S1[0][n - 2] == 0:
                    S1[0][j] = 0
            elif S1[0][j - 1] == 0 and S1[0][j + 1] == 0:
                S1[0][j] = 0
        if S1[m - 1][j] == 1:
            if S1[m - 2][j] == 0:    # down point is undefine
                S1[m - 1][j] = 0
            elif j == 0:
                if S1[m - 1][j + 1] == 0:
                    S1[m - 1][j] = 0
            elif j == n - 1:
                if S1[m - 1][n - 2] == 0:
                    S1[m - 1][j] = 0
            elif S1[m - 1][j - 1] == 0 and S1[m - 1][j + 1] == 0:
                S1[m - 1][j] = 0

    for i in range(0, m):    # Left and right border points
        if S1[i][0] == 1:
            if S1[i][1] == 0:    # right point is undefine
                S1[i][0] = 0
            elif i == 0:
                if S1[i + 1][0] == 0:
                    S1[i][0] = 0
            elif i == m - 1:
                if S1[m - 2][0] == 0:
                    S1[i][0] = 0
            elif S1[i - 1][0] == 0 and S1[i + 1][0] == 0:
                S1[i][0] = 0
        if S1[i][n - 1] == 1:
            if S1[i][n - 2] == 0:    # left point is undefine
                S1[i][n - 1] = 0
            elif i == 0:
                if S1[i + 1][n - 1] == 0:
                    S1[i][n - 1] = 0
            elif i == m - 1:
                if S1[m - 2][n - 1] == 0:
                    S1[i][n - 1] = 0
            elif S1[i - 1][n - 1] == 0 and S1[i + 1][n - 1] == 0:
                S1[i][n - 1] = 0

    # ---- Generate S2 array from S1, add border to S2 with undefine data.
    S2 = [[0] * (n + 2) for _ in range(m + 2)]
    for i in range(0, m + 2):
        for j in range(0, n + 2):
            if i == 0 or i == m + 1:    # bottom or top border
                S2[i][j] = 0
            elif j == 0 or j == n + 1:    # left or right border
                S2[i][j] = 0
            else:
                S2[i][j] = S1[i - 1][j - 1]

    # ---- Using times number of each point during chacing process.
    UNum = [[0] * (n + 2) for _ in range(m + 2)]
    for i in range(0, m + 2):
        for j in range(0, n + 2):
            if S2[i][j] == 1:
                l = S2[i][j - 1]
                r = S2[i][j + 1]
                b = S2[i - 1][j]
                t = S2[i + 1][j]
                lb = S2[i - 1][j - 1]
                rb = S2[i - 1][j + 1]
                lt = S2[i + 1][j - 1]
                rt = S2[i + 1][j + 1]
                # ---- Cross point with two boder lines, will be used twice.
                if l == 1 and r == 1 and b == 1 and t == 1 and ((lb == 0 and rt == 0) or (rb == 0 and lt == 0)):
                    UNum[i][j] = 2
                else:
                    UNum[i][j] = 1
            else:
                UNum[i][j] = 0

    # ---- Tracing borderlines
    aPoint = None
    aijPoint = None
    aBLine = None
    pointList = None
    ijPList = None
    sI = 0
    sJ = 0
    i1 = 0
    j1 = 0
    i2 = 0
    j2 = 0
    i3 = 0
    j3 = 0
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if S2[i][j] == 1:    # Tracing border from any border point
                pointList = []
                ijPList = []
                aPoint = PointD()
                aPoint.X = X[j - 1]
                aPoint.Y = Y[i - 1]
                aijPoint = IJPoint()
                aijPoint.I = i - 1
                aijPoint.J = j - 1
                pointList.append(aPoint)
                ijPList.append(aijPoint)
                sI = i
                sJ = j
                i2 = i
                j2 = j
                i1 = i2
                j1 = -1    # Trace from left firstly

                while True:
                    ij3 = [0, 0]
                    ij3[0] = i3
                    ij3[1] = j3
                    if traceBorder(S2, i1, i2, j1, j2, ij3):
                        i3 = ij3[0]
                        j3 = ij3[1]
                        i1 = i2
                        j1 = j2
                        i2 = i3
                        j2 = j3
                        UNum[i3][j3] = UNum[i3][j3] - 1
                        if UNum[i3][j3] == 0:
                            S2[i3][j3] = 3    # Used border point
                    else:
                        break

                    aPoint = PointD()
                    aPoint.X = X[j3 - 1]
                    aPoint.Y = Y[i3 - 1]
                    aijPoint = IJPoint()
                    aijPoint.I = i3 - 1
                    aijPoint.J = j3 - 1
                    pointList.append(aPoint)
                    ijPList.append(aijPoint)
                    if i3 == sI and j3 == sJ:
                        break
                UNum[i][j] = UNum[i][j] - 1
                if UNum[i][j] == 0:
                    S2[i][j] = 3    # Used border point
                #                     UNum[i][j] = UNum[i][j] - 1;
                if len(pointList) > 1:
                    aBLine = BorderLine()
                    aBLine.area = getExtentAndArea(pointList, aBLine.extent)
                    aBLine.isOutLine = True
                    aBLine.isClockwise = True
                    aBLine.pointList = pointList
                    aBLine.ijPointList = ijPList
                    borderLines.append(aBLine)

    # ---- Form borders
    borders = []
    aBorder = None
    aLine = None
    bLine = None
    # ---- Sort borderlines with area from small to big.
    # For inside border line analysis
    i = 1
    while i < len(borderLines):
        aLine = borderLines[i]
        j = 0
        while j < i:
            bLine = borderLines[j]
            if aLine.area > bLine.area:
                borderLines.pop(i)
                borderLines.insert(j, aLine)
                break
            j = j + 1
        i = i + 1
    lineList = None
    if len(borderLines) == 1:    # Only one boder line
        aLine = borderLines[0]
        if not isClockwise(aLine.pointList):
            aLine.pointList.reverse()
            aLine.ijPointList.reverse()
        aLine.isClockwise = True
        lineList = []
        lineList.append(aLine)
        aBorder = Border()
        aBorder.LineList = lineList
        borders.append(aBorder)
    else:    # muti border lines
        i = 0
        while i < len(borderLines):
            if i == len(borderLines):
                break

            aLine = borderLines[i]
            if not isClockwise(aLine.pointList):
                aLine.pointList.reverse()
                aLine.ijPointList.reverse()
            aLine.isClockwise = True
            lineList = []
            lineList.append(aLine)
            # Try to find the boder lines are inside of aLine.
            j = i + 1
            while j < len(borderLines):
                if j == len(borderLines):
                    break

                bLine = borderLines[j]
                if (bLine.extent.xMin > aLine.extent.xMin and bLine.extent.xMax < aLine.extent.xMax
                        and bLine.extent.yMin > aLine.extent.yMin and bLine.extent.yMax < aLine.extent.yMax):
                    aPoint = bLine.pointList[0]
                    if pointInPolygon_poly(aLine.pointList, aPoint):    # bLine is inside of aLine
                        bLine.isOutLine = False
                        if isClockwise(bLine.pointList):
                            bLine.pointList.reverse()
                            bLine.ijPointList.reverse()
                        bLine.isClockwise = False
                        lineList.append(bLine)
                        borderLines.pop(j)
                        j = j - 1
                j = j + 1
            aBorder = Border()
            aBorder.LineList = lineList
            borders.append(aBorder)
            i = i + 1

    return borders


def traceBorder(S1, i1, i2, j1, j2, ij3):
    """Java: traceBorder(int[][] S1, int i1, int i2, int j1, int j2, int[] ij3) L1575-1817

    由当前边界点 ``(i2, j2)`` 与来向 ``(i1, j1)`` 决定下一个边界点。

    ``ij3`` 是调用方传入的 ``int[]``（Python ``list[int]``，长度 2），
    本函数**原地写入** ``ij3[0]`` / ``ij3[1]``；而 ``S1`` 只读。
    返回 boolean（Java ``canTrace``）。
    """
    canTrace = True
    a = 0
    b = 0
    c = 0
    d = 0
    if i1 < i2:    # ---- Trace from bottom
        if S1[i2][j2 - 1] == 1 and S1[i2][j2 + 1] == 1:
            a = S1[i2 - 1][j2 - 1]
            b = S1[i2 + 1][j2]
            c = S1[i2 + 1][j2 - 1]
            if (a != 0 and b == 0) or (a == 0 and b != 0 and c != 0):
                ij3[0] = i2
                ij3[1] = j2 - 1
            else:
                ij3[0] = i2
                ij3[1] = j2 + 1
        elif S1[i2][j2 - 1] == 1 and S1[i2 + 1][j2] == 1:
            a = S1[i2 + 1][j2 - 1]
            b = S1[i2 + 1][j2 + 1]
            c = S1[i2][j2 - 1]
            d = S1[i2][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2
                    ij3[1] = j2 - 1
                else:
                    ij3[0] = i2 + 1
                    ij3[1] = j2
            else:
                ij3[0] = i2
                ij3[1] = j2 - 1
        elif S1[i2][j2 + 1] == 1 and S1[i2 + 1][j2] == 1:
            a = S1[i2 + 1][j2 - 1]
            b = S1[i2 + 1][j2 + 1]
            c = S1[i2][j2 - 1]
            d = S1[i2][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2
                    ij3[1] = j2 + 1
                else:
                    ij3[0] = i2 + 1
                    ij3[1] = j2
            else:
                ij3[0] = i2
                ij3[1] = j2 + 1
        elif S1[i2][j2 - 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 - 1
        elif S1[i2][j2 + 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 + 1
        elif S1[i2 + 1][j2] == 1:
            ij3[0] = i2 + 1
            ij3[1] = j2
        else:
            canTrace = False
    elif j1 < j2:    # ---- Trace from left
        if S1[i2 + 1][j2] == 1 and S1[i2 - 1][j2] == 1:
            a = S1[i2 + 1][j2 - 1]
            b = S1[i2][j2 + 1]
            c = S1[i2 + 1][j2 + 1]
            if (a != 0 and b == 0) or (a == 0 and b != 0 and c != 0):
                ij3[0] = i2 + 1
                ij3[1] = j2
            else:
                ij3[0] = i2 - 1
                ij3[1] = j2
        elif S1[i2 + 1][j2] == 1 and S1[i2][j2 + 1] == 1:
            c = S1[i2 - 1][j2]
            d = S1[i2 + 1][j2]
            a = S1[i2 - 1][j2 + 1]
            b = S1[i2 + 1][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2 + 1
                    ij3[1] = j2
                else:
                    ij3[0] = i2
                    ij3[1] = j2 + 1
            else:
                ij3[0] = i2 + 1
                ij3[1] = j2
        elif S1[i2 - 1][j2] == 1 and S1[i2][j2 + 1] == 1:
            c = S1[i2 - 1][j2]
            d = S1[i2 + 1][j2]
            a = S1[i2 - 1][j2 + 1]
            b = S1[i2 + 1][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2 - 1
                    ij3[1] = j2
                else:
                    ij3[0] = i2
                    ij3[1] = j2 + 1
            else:
                ij3[0] = i2 - 1
                ij3[1] = j2
        elif S1[i2 + 1][j2] == 1:
            ij3[0] = i2 + 1
            ij3[1] = j2
        elif S1[i2 - 1][j2] == 1:
            ij3[0] = i2 - 1
            ij3[1] = j2
        elif S1[i2][j2 + 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 + 1
        else:
            canTrace = False
    elif i1 > i2:    # ---- Trace from top
        if S1[i2][j2 - 1] == 1 and S1[i2][j2 + 1] == 1:
            a = S1[i2 + 1][j2 - 1]
            b = S1[i2 - 1][j2]
            c = S1[i2 - 1][j2 + 1]
            if (a != 0 and b == 0) or (a == 0 and b != 0 and c != 0):
                ij3[0] = i2
                ij3[1] = j2 - 1
            else:
                ij3[0] = i2
                ij3[1] = j2 + 1
        elif S1[i2][j2 - 1] == 1 and S1[i2 - 1][j2] == 1:
            a = S1[i2 - 1][j2 - 1]
            b = S1[i2 - 1][j2 + 1]
            c = S1[i2][j2 - 1]
            d = S1[i2][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2
                    ij3[1] = j2 - 1
                else:
                    ij3[0] = i2 - 1
                    ij3[1] = j2
            else:
                ij3[0] = i2
                ij3[1] = j2 - 1
        elif S1[i2][j2 + 1] == 1 and S1[i2 - 1][j2] == 1:
            a = S1[i2 - 1][j2 - 1]
            b = S1[i2 - 1][j2 + 1]
            c = S1[i2][j2 - 1]
            d = S1[i2][j2 + 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2
                    ij3[1] = j2 + 1
                else:
                    ij3[0] = i2 - 1
                    ij3[1] = j2
            else:
                ij3[0] = i2
                ij3[1] = j2 + 1
        elif S1[i2][j2 - 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 - 1
        elif S1[i2][j2 + 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 + 1
        elif S1[i2 - 1][j2] == 1:
            ij3[0] = i2 - 1
            ij3[1] = j2
        else:
            canTrace = False
    elif j1 > j2:    # ---- Trace from right
        if S1[i2 + 1][j2] == 1 and S1[i2 - 1][j2] == 1:
            a = S1[i2 + 1][j2 + 1]
            b = S1[i2][j2 - 1]
            c = S1[i2 - 1][j2 - 1]
            if (a != 0 and b == 0) or (a == 0 and b != 0 and c != 0):
                ij3[0] = i2 + 1
                ij3[1] = j2
            else:
                ij3[0] = i2 - 1
                ij3[1] = j2
        elif S1[i2 + 1][j2] == 1 and S1[i2][j2 - 1] == 1:
            c = S1[i2 - 1][j2]
            d = S1[i2 + 1][j2]
            a = S1[i2 - 1][j2 - 1]
            b = S1[i2 + 1][j2 - 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2 + 1
                    ij3[1] = j2
                else:
                    ij3[0] = i2
                    ij3[1] = j2 - 1
            else:
                ij3[0] = i2 + 1
                ij3[1] = j2
        elif S1[i2 - 1][j2] == 1 and S1[i2][j2 - 1] == 1:
            c = S1[i2 - 1][j2]
            d = S1[i2 + 1][j2]
            a = S1[i2 - 1][j2 - 1]
            b = S1[i2 + 1][j2 - 1]
            if a == 0 or b == 0 or c == 0 or d == 0:
                if (a == 0 and d == 0) or (b == 0 and c == 0):
                    ij3[0] = i2 - 1
                    ij3[1] = j2
                else:
                    ij3[0] = i2
                    ij3[1] = j2 - 1
            else:
                ij3[0] = i2 - 1
                ij3[1] = j2
        elif S1[i2 + 1][j2] == 1:
            ij3[0] = i2 + 1
            ij3[1] = j2
        elif S1[i2 - 1][j2] == 1:
            ij3[0] = i2 - 1
            ij3[1] = j2
        elif S1[i2][j2 - 1] == 1:
            ij3[0] = i2
            ij3[1] = j2 - 1
        else:
            canTrace = False

    return canTrace
