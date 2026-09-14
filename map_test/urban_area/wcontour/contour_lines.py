# -*- coding: utf-8 -*-
"""
wcontour.contour_lines —— wContour 1.6.1 `wcontour.Contour` 里与等值线追踪相关的
4 个方法的 1:1 Python 移植（**行为等价**，不做任何"优化"）。

上游来源
========
meteoinfo/wContour, ``src/main/java/wcontour/Contour.java`` (LGPL-3.0)。
原始 Java 源码随包放在 ``wcontour/_upstream/Contour.java``，本文件的行号区间均以它为准。

本模块包含（顺序与 Java 源码中出现的顺序一致）
=============================================

====================================  ==================================================
Python 函数名                          Java 方法（Java 行号区间）
====================================  ==================================================
``tracingContourLines``               ``tracingContourLines(...)``              L47-52
``createContourLines_UndefData``      ``createContourLines_UndefData(...)``     L427-564
``traceIsoline_UndefData``            ``traceIsoline_UndefData(...)``           L1819-2005
``isoline_UndefData``                 ``isoline_UndefData(...)``                L2195-2544
====================================  ==================================================

移植要点（照抄而**不是**修正的地方）
====================================
* Java 的 ``S0[i][j]`` 中 **i 是行(Y)索引、j 是列(X)索引**；本模块不做任何转置。
* ``S0`` / ``S`` / ``H`` / ``SB`` / ``HB`` 都会被**就地改写**；``X`` / ``Y`` 是只读坐标轴。
* ``S`` 与 ``H`` 在 ``createContourLines_UndefData`` 里是**在所有等值 W 的循环之外**
  一次性分配、然后跨 W 复用的（Java L503-504），不要挪进循环里。
* ``_endPointList`` 对应 Java 的 ``private static List<EndPoint> _endPointList``，
  是**模块级共享可变状态**，且这几个方法里**从不清空**它；``isoline_UndefData`` 每次
  ``_endPointList.add(aEndPoint)`` 加进去的都是**同一个** ``aEndPoint`` 对象引用。
* ``int[] ij3`` / ``double[] a3xy`` / ``boolean[] IsS`` 是 Java 的"出参"写法
  (``ij3[0]=i3; a3xy[0]=a3x; a3xy[1]=a3y; IsS[0]=isS;``)，Python 里用 list 承载，
  由 ``traceIsoline_UndefData`` **原地写入**，调用方再读回来。
* Java 的同名重载 ``pointInPolygon`` 按 PORTING_RULES 拆成 ``pointInPolygon_poly``
  (``List<PointD>``) / ``pointInPolygon_polygon`` (``Polygon``)；本模块只用到前者。
* 本模块这 4 个方法里**没有**整数除法，因此不需要 ``helpers.idiv``。
* ``traceIsoline_UndefData_bak`` (Java L2007-2193) 是上游废弃的备份实现，**未移植**；
  ``traceIsoline`` / ``isoline_Bottom`` / ``isoline_Left`` / ``isoline_Top`` /
  ``isoline_Right`` / ``isoline_Close`` 同样不在本次范围内。
* ``aLine.Type`` 的取值 ``"Border"`` / ``"Close"`` / ``"Error"`` 与 ``aLine.Value``、
  ``aLine.BorderIdx`` 的赋值时机与 Java 完全一致（后续 ``tracingPolygons`` 依赖它们）。
"""

from .global_types import EndPoint, PointD, PolyLine
from .helpers import doubleEquals, pointInPolygon_poly


# Java: private static List<EndPoint> _endPointList = new ArrayList<EndPoint>();
# 注意：静态字段，跨调用共享，且本模块的方法里从不清空它。
_endPointList = []


def tracingContourLines(S0, X, Y, nc, contour, undefData, borders, S1):
    """Java: tracingContourLines(double[][] S0, double[] X, double[] Y, int nc, double[] contour, double undefData, List<Border> borders, int[][] S1) L47-52

    Tracing contour lines from the grid data with undefine data.

    Java 原文只是把参数**重新排成** createContourLines_UndefData 的形参顺序后转发，
    不做任何其它处理。
    """
    contourLines = createContourLines_UndefData(S0, X, Y, nc, contour, S1, undefData, borders)

    return contourLines


def createContourLines_UndefData(S0, X, Y, nc, contour, S1, undefData, borders):
    """Java: createContourLines_UndefData(double[][] S0, double[] X, double[] Y, int nc, double[] contour, int[][] S1, double undefData, List<Border> borders) L427-564

    Create contour lines from the grid data with undefine data.

    会**就地**改写 S0（加上 dShift）与 SB/HB/S/H 内部数组；S1 只读。
    """
    contourLineList = []
    cLineList = None
    m, n, i, j = 0, 0, 0, 0
    m = len(S0)      # ---- Y
    n = len(S0[0])   # ---- X

    # ---- Add a small value to aviod the contour point as same as data point
    dShift = 0.0
    dShift = contour[0] * 0.00001
    if dShift == 0:
        dShift = 0.00001
    for i in range(m):
        for j in range(n):
            if not doubleEquals(S0[i][j], undefData):  # S0[i, j] = S0[i, j] + (contour[1] - contour[0]) * 0.0001;
                S0[i][j] = S0[i][j] + dShift

    # ---- Define if H S are border
    SB = [[[0] * (n - 1) for _ in range(m)] for _ in range(2)]
    HB = [[[0] * n for _ in range(m - 1)] for _ in range(2)]  # ---- Which border and trace direction
    for i in range(m):
        for j in range(n):
            if j < n - 1:
                SB[0][i][j] = -1
                SB[1][i][j] = -1
            if i < m - 1:
                HB[0][i][j] = -1
                HB[1][i][j] = -1
    aBorder = None
    aBLine = None
    ijPList = None
    k, si, sj = 0, 0, 0
    aijP, bijP = None, None
    for i in range(len(borders)):
        aBorder = borders[i]
        for j in range(aBorder.getLineNum()):
            aBLine = aBorder.LineList[j]
            ijPList = aBLine.ijPointList
            for k in range(len(ijPList) - 1):
                aijP = ijPList[k]
                bijP = ijPList[k + 1]
                if aijP.I == bijP.I:
                    si = aijP.I
                    sj = min(aijP.J, bijP.J)
                    SB[0][si][sj] = i
                    if bijP.J > aijP.J:  # ---- Trace from top
                        SB[1][si][sj] = 1
                    else:
                        SB[1][si][sj] = 0    # ----- Trace from bottom
                else:
                    sj = aijP.J
                    si = min(aijP.I, bijP.I)
                    HB[0][si][sj] = i
                    if bijP.I > aijP.I:  # ---- Trace from left
                        HB[1][si][sj] = 0
                    else:
                        HB[1][si][sj] = 1    # ---- Trace from right

    # ---- Define horizontal and vertical arrays with the position of the tracing value, -2 means no tracing point.
    S = [[0.0] * (n - 1) for _ in range(m)]
    H = [[0.0] * n for _ in range(m - 1)]
    w = 0.0      # ---- Tracing value
    c = 0
    # ArrayList _endPointList = new ArrayList();    //---- Contour line end points for insert to border
    for c in range(nc):
        w = contour[c]
        for i in range(m):
            for j in range(n):
                if j < n - 1:
                    if S1[i][j] != 0 and S1[i][j + 1] != 0:
                        if (S0[i][j] - w) * (S0[i][j + 1] - w) < 0:  # ---- Has tracing value
                            S[i][j] = (w - S0[i][j]) / (S0[i][j + 1] - S0[i][j])
                        else:
                            S[i][j] = -2
                    else:
                        S[i][j] = -2
                if i < m - 1:
                    if S1[i][j] != 0 and S1[i + 1][j] != 0:
                        if (S0[i][j] - w) * (S0[i + 1][j] - w) < 0:  # ---- Has tracing value
                            H[i][j] = (w - S0[i][j]) / (S0[i + 1][j] - S0[i][j])
                        else:
                            H[i][j] = -2
                    else:
                        H[i][j] = -2

        cLineList = isoline_UndefData(S0, X, Y, w, S, H, SB, HB, len(contourLineList))
        contourLineList.extend(cLineList)

    # ---- Set border index for close contours
    aLine = None
    # List pList = new ArrayList();
    aPoint = None
    for i in range(len(borders)):
        aBorder = borders[i]
        aBLine = aBorder.LineList[0]
        # Java: for (j = 0; j < contourLineList.size(); j++)
        # —— Java 每轮都重新取 size()，这里用 while 保留同一语义
        #    （remove 后紧跟同下标的 add，size 不变）。
        j = 0
        while j < len(contourLineList):
            aLine = contourLineList[j]
            if aLine.Type == "Close":
                aPoint = aLine.PointList[0]
                if pointInPolygon_poly(aBLine.pointList, aPoint):
                    aLine.BorderIdx = i
            contourLineList.pop(j)
            contourLineList.insert(j, aLine)
            j += 1

    return contourLineList


def traceIsoline_UndefData(i1, i2, H, S, j1, j2, X, Y, a2x, ij3, a3xy, IsS):
    """Java: traceIsoline_UndefData(int i1, int i2, double[][] H, double[][] S, int j1, int j2, double[] X, double[] Y, double a2x, int[] ij3, double[] a3xy, boolean[] IsS) L1819-2005

    从当前点按方向找下一个等值点，找到就把对应的 H/S 位置置 -2（就地消费）。

    ``ij3`` / ``a3xy`` / ``IsS`` 是三个"出参"数组，函数末尾原地写入
    ``ij3[0]=i3; ij3[1]=j3; a3xy[0]=a3x; a3xy[1]=a3y; IsS[0]=isS;``。
    返回 ``canTrace``：False 表示本方向已无路可走（调用方据此把 aLine.Type 置 "Error"）。
    注意：即使返回 False，出参也照样被写入（照抄 Java）。
    """
    canTrace = True
    a3x = 0.0
    a3y = 0.0
    i3 = 0
    j3 = 0
    isS = True
    if i1 < i2:  # ---- Trace from bottom
        if H[i2][j2] != -2 and H[i2][j2 + 1] != -2:
            if H[i2][j2] < H[i2][j2 + 1]:
                a3x = X[j2]
                a3y = Y[i2] + H[i2][j2] * (Y[i2 + 1] - Y[i2])
                i3 = i2
                j3 = j2
                H[i3][j3] = -2
                isS = False
            else:
                a3x = X[j2 + 1]
                a3y = Y[i2] + H[i2][j2 + 1] * (Y[i2 + 1] - Y[i2])
                i3 = i2
                j3 = j2 + 1
                H[i3][j3] = -2
                isS = False
        elif H[i2][j2] != -2 and H[i2][j2 + 1] == -2:
            a3x = X[j2]
            a3y = Y[i2] + H[i2][j2] * (Y[i2 + 1] - Y[i2])
            i3 = i2
            j3 = j2
            H[i3][j3] = -2
            isS = False
        elif H[i2][j2] == -2 and H[i2][j2 + 1] != -2:
            a3x = X[j2 + 1]
            a3y = Y[i2] + H[i2][j2 + 1] * (Y[i2 + 1] - Y[i2])
            i3 = i2
            j3 = j2 + 1
            H[i3][j3] = -2
            isS = False
        elif S[i2 + 1][j2] != -2:
            a3x = X[j2] + S[i2 + 1][j2] * (X[j2 + 1] - X[j2])
            a3y = Y[i2 + 1]
            i3 = i2 + 1
            j3 = j2
            S[i3][j3] = -2
            isS = True
        else:
            canTrace = False
    elif j1 < j2:  # ---- Trace from left
        if S[i2][j2] != -2 and S[i2 + 1][j2] != -2:
            if S[i2][j2] < S[i2 + 1][j2]:
                a3x = X[j2] + S[i2][j2] * (X[j2 + 1] - X[j2])
                a3y = Y[i2]
                i3 = i2
                j3 = j2
                S[i3][j3] = -2
                isS = True
            else:
                a3x = X[j2] + S[i2 + 1][j2] * (X[j2 + 1] - X[j2])
                a3y = Y[i2 + 1]
                i3 = i2 + 1
                j3 = j2
                S[i3][j3] = -2
                isS = True
        elif S[i2][j2] != -2 and S[i2 + 1][j2] == -2:
            a3x = X[j2] + S[i2][j2] * (X[j2 + 1] - X[j2])
            a3y = Y[i2]
            i3 = i2
            j3 = j2
            S[i3][j3] = -2
            isS = True
        elif S[i2][j2] == -2 and S[i2 + 1][j2] != -2:
            a3x = X[j2] + S[i2 + 1][j2] * (X[j2 + 1] - X[j2])
            a3y = Y[i2 + 1]
            i3 = i2 + 1
            j3 = j2
            S[i3][j3] = -2
            isS = True
        elif H[i2][j2 + 1] != -2:
            a3x = X[j2 + 1]
            a3y = Y[i2] + H[i2][j2 + 1] * (Y[i2 + 1] - Y[i2])
            i3 = i2
            j3 = j2 + 1
            H[i3][j3] = -2
            isS = False
        else:
            canTrace = False

    elif X[j2] < a2x:  # ---- Trace from top
        if H[i2 - 1][j2] != -2 and H[i2 - 1][j2 + 1] != -2:
            if H[i2 - 1][j2] > H[i2 - 1][j2 + 1]:  # ---- < changed to >
                a3x = X[j2]
                a3y = Y[i2 - 1] + H[i2 - 1][j2] * (Y[i2] - Y[i2 - 1])
                i3 = i2 - 1
                j3 = j2
                H[i3][j3] = -2
                isS = False
            else:
                a3x = X[j2 + 1]
                a3y = Y[i2 - 1] + H[i2 - 1][j2 + 1] * (Y[i2] - Y[i2 - 1])
                i3 = i2 - 1
                j3 = j2 + 1
                H[i3][j3] = -2
                isS = False
        elif H[i2 - 1][j2] != -2 and H[i2 - 1][j2 + 1] == -2:
            a3x = X[j2]
            a3y = Y[i2 - 1] + H[i2 - 1][j2] * (Y[i2] - Y[i2 - 1])
            i3 = i2 - 1
            j3 = j2
            H[i3][j3] = -2
            isS = False
        elif H[i2 - 1][j2] == -2 and H[i2 - 1][j2 + 1] != -2:
            a3x = X[j2 + 1]
            a3y = Y[i2 - 1] + H[i2 - 1][j2 + 1] * (Y[i2] - Y[i2 - 1])
            i3 = i2 - 1
            j3 = j2 + 1
            H[i3][j3] = -2
            isS = False
        elif S[i2 - 1][j2] != -2:
            a3x = X[j2] + S[i2 - 1][j2] * (X[j2 + 1] - X[j2])
            a3y = Y[i2 - 1]
            i3 = i2 - 1
            j3 = j2
            S[i3][j3] = -2
            isS = True
        else:
            canTrace = False
    else:  # ---- Trace from right
        if S[i2 + 1][j2 - 1] != -2 and S[i2][j2 - 1] != -2:
            if S[i2 + 1][j2 - 1] > S[i2][j2 - 1]:  # ---- < changed to >
                a3x = X[j2 - 1] + S[i2 + 1][j2 - 1] * (X[j2] - X[j2 - 1])
                a3y = Y[i2 + 1]
                i3 = i2 + 1
                j3 = j2 - 1
                S[i3][j3] = -2
                isS = True
            else:
                a3x = X[j2 - 1] + S[i2][j2 - 1] * (X[j2] - X[j2 - 1])
                a3y = Y[i2]
                i3 = i2
                j3 = j2 - 1
                S[i3][j3] = -2
                isS = True
        elif S[i2 + 1][j2 - 1] != -2 and S[i2][j2 - 1] == -2:
            a3x = X[j2 - 1] + S[i2 + 1][j2 - 1] * (X[j2] - X[j2 - 1])
            a3y = Y[i2 + 1]
            i3 = i2 + 1
            j3 = j2 - 1
            S[i3][j3] = -2
            isS = True
        elif S[i2 + 1][j2 - 1] == -2 and S[i2][j2 - 1] != -2:
            a3x = X[j2 - 1] + S[i2][j2 - 1] * (X[j2] - X[j2 - 1])
            a3y = Y[i2]
            i3 = i2
            j3 = j2 - 1
            S[i3][j3] = -2
            isS = True
        elif H[i2][j2 - 1] != -2:
            a3x = X[j2 - 1]
            a3y = Y[i2] + H[i2][j2 - 1] * (Y[i2 + 1] - Y[i2])
            i3 = i2
            j3 = j2 - 1
            H[i3][j3] = -2
            isS = False
        else:
            canTrace = False

    ij3[0] = i3
    ij3[1] = j3
    a3xy[0] = a3x
    a3xy[1] = a3y
    IsS[0] = isS

    return canTrace


def isoline_UndefData(S0, X, Y, W, S, H, SB, HB, lineNum):
    """Java: isoline_UndefData(double[][] S0, double[] X, double[] Y, double W, double[][] S, double[][] H, int[][][] SB, int[][][] HB, int lineNum) L2195-2544

    对单个等值 W 追踪等值线：先沿边界 (SB/HB 标记的 border) 追出 Type="Border" 的线，
    再在内部追出 Type="Close" 的闭合线。

    就地写：``S``、``H``（把消费过的等值点置 -2），以及模块级 ``_endPointList``。
    ``S0`` / ``X`` / ``Y`` / ``SB`` / ``HB`` 只读。
    """
    cLineList = []
    m, n, i, j = 0, 0, 0, 0
    m = len(S0)
    n = len(S0[0])

    i1, i2, j1, j2 = 0, 0, 0, 0
    i3, j3 = 0, 0
    a2x = 0.0
    a2y = 0.0
    a3x = 0.0
    a3y = 0.0
    sx = 0.0
    sy = 0.0
    aPoint = None
    aLine = None
    pList = None
    isS = True
    aEndPoint = EndPoint()
    # ---- Tracing from border
    for i in range(m):
        for j in range(n):
            if j < n - 1:
                if SB[0][i][j] > -1:  # ---- Border
                    if S[i][j] != -2:
                        pList = []
                        i2 = i
                        j2 = j
                        a2x = X[j2] + S[i2][j2] * (X[j2 + 1] - X[j2])    # ---- x of first point
                        a2y = Y[i2]                   # ---- y of first point
                        if SB[1][i][j] == 0:  # ---- Bottom border
                            i1 = -1
                            aEndPoint.sPoint.X = X[j + 1]
                            aEndPoint.sPoint.Y = Y[i]
                        else:
                            i1 = i2
                            aEndPoint.sPoint.X = X[j]
                            aEndPoint.sPoint.Y = Y[i]
                        j1 = j2
                        aPoint = PointD()
                        aPoint.X = a2x
                        aPoint.Y = a2y
                        pList.append(aPoint)

                        aEndPoint.Index = lineNum + len(cLineList)
                        aEndPoint.Point = aPoint
                        aEndPoint.BorderIdx = SB[0][i][j]
                        _endPointList.append(aEndPoint)

                        aLine = PolyLine()
                        aLine.Type = "Border"
                        aLine.BorderIdx = SB[0][i][j]
                        while True:
                            ij3 = [i3, j3]
                            a3xy = [a3x, a3y]
                            IsS = [isS]
                            if traceIsoline_UndefData(i1, i2, H, S, j1, j2, X, Y, a2x, ij3, a3xy, IsS):
                                i3 = ij3[0]
                                j3 = ij3[1]
                                a3x = a3xy[0]
                                a3y = a3xy[1]
                                isS = IsS[0]
                                aPoint = PointD()
                                aPoint.X = a3x
                                aPoint.Y = a3y
                                pList.append(aPoint)
                                if isS:
                                    if SB[0][i3][j3] > -1:
                                        if SB[1][i3][j3] == 0:
                                            aEndPoint.sPoint.X = X[j3 + 1]
                                            aEndPoint.sPoint.Y = Y[i3]
                                        else:
                                            aEndPoint.sPoint.X = X[j3]
                                            aEndPoint.sPoint.Y = Y[i3]
                                        break
                                elif HB[0][i3][j3] > -1:
                                    if HB[1][i3][j3] == 0:
                                        aEndPoint.sPoint.X = X[j3]
                                        aEndPoint.sPoint.Y = Y[i3]
                                    else:
                                        aEndPoint.sPoint.X = X[j3]
                                        aEndPoint.sPoint.Y = Y[i3 + 1]
                                    break
                                a2x = a3x
                                # a2y = a3y;
                                i1 = i2
                                j1 = j2
                                i2 = i3
                                j2 = j3
                            else:
                                aLine.Type = "Error"
                                break
                        S[i][j] = -2
                        if len(pList) > 1 and aLine.Type != "Error":
                            aEndPoint.Point = aPoint
                            _endPointList.append(aEndPoint)

                            aLine.Value = W
                            aLine.PointList = pList
                            cLineList.append(aLine)
                        else:
                            _endPointList.pop(len(_endPointList) - 1)

            if i < m - 1:
                if HB[0][i][j] > -1:  # ---- Border
                    if H[i][j] != -2:
                        pList = []
                        i2 = i
                        j2 = j
                        a2x = X[j2]
                        a2y = Y[i2] + H[i2][j2] * (Y[i2 + 1] - Y[i2])
                        i1 = i2
                        if HB[1][i][j] == 0:
                            j1 = -1
                            aEndPoint.sPoint.X = X[j]
                            aEndPoint.sPoint.Y = Y[i]
                        else:
                            j1 = j2
                            aEndPoint.sPoint.X = X[j]
                            aEndPoint.sPoint.Y = Y[i + 1]
                        aPoint = PointD()
                        aPoint.X = a2x
                        aPoint.Y = a2y
                        pList.append(aPoint)

                        aEndPoint.Index = lineNum + len(cLineList)
                        aEndPoint.Point = aPoint
                        aEndPoint.BorderIdx = HB[0][i][j]
                        _endPointList.append(aEndPoint)

                        aLine = PolyLine()
                        aLine.Type = "Border"
                        aLine.BorderIdx = HB[0][i][j]
                        while True:
                            ij3 = [i3, j3]
                            a3xy = [a3x, a3y]
                            IsS = [isS]
                            if traceIsoline_UndefData(i1, i2, H, S, j1, j2, X, Y, a2x, ij3, a3xy, IsS):
                                i3 = ij3[0]
                                j3 = ij3[1]
                                a3x = a3xy[0]
                                a3y = a3xy[1]
                                isS = IsS[0]
                                aPoint = PointD()
                                aPoint.X = a3x
                                aPoint.Y = a3y
                                pList.append(aPoint)
                                if isS:
                                    if SB[0][i3][j3] > -1:
                                        if SB[1][i3][j3] == 0:
                                            aEndPoint.sPoint.X = X[j3 + 1]
                                            aEndPoint.sPoint.Y = Y[i3]
                                        else:
                                            aEndPoint.sPoint.X = X[j3]
                                            aEndPoint.sPoint.Y = Y[i3]
                                        break
                                elif HB[0][i3][j3] > -1:
                                    if HB[1][i3][j3] == 0:
                                        aEndPoint.sPoint.X = X[j3]
                                        aEndPoint.sPoint.Y = Y[i3]
                                    else:
                                        aEndPoint.sPoint.X = X[j3]
                                        aEndPoint.sPoint.Y = Y[i3 + 1]
                                    break
                                a2x = a3x
                                # a2y = a3y;
                                i1 = i2
                                j1 = j2
                                i2 = i3
                                j2 = j3
                            else:
                                aLine.Type = "Error"
                                break
                        H[i][j] = -2
                        if len(pList) > 1 and aLine.Type != "Error":
                            aEndPoint.Point = aPoint
                            _endPointList.append(aEndPoint)

                            aLine.Value = W
                            aLine.PointList = pList
                            cLineList.append(aLine)
                        else:
                            _endPointList.pop(len(_endPointList) - 1)

    # ---- Clear border points
    for j in range(n - 1):
        if S[0][j] != -2:
            S[0][j] = -2
        if S[m - 1][j] != -2:
            S[m - 1][j] = -2

    for i in range(m - 1):
        if H[i][0] != -2:
            H[i][0] = -2
        if H[i][n - 1] != -2:
            H[i][n - 1] = -2

    # ---- Tracing close lines
    for i in range(1, m - 2):
        for j in range(1, n - 1):
            if H[i][j] != -2:
                pointList = []
                i2 = i
                j2 = j
                a2x = X[j2]
                a2y = Y[i] + H[i][j2] * (Y[i + 1] - Y[i])
                j1 = -1
                i1 = i2
                sx = a2x
                sy = a2y
                aPoint = PointD()
                aPoint.X = a2x
                aPoint.Y = a2y
                pointList.append(aPoint)
                aLine = PolyLine()
                aLine.Type = "Close"

                while True:
                    ij3 = [0, 0]
                    a3xy = [0.0, 0.0]
                    IsS = [False]
                    if traceIsoline_UndefData(i1, i2, H, S, j1, j2, X, Y, a2x, ij3, a3xy, IsS):
                        i3 = ij3[0]
                        j3 = ij3[1]
                        a3x = a3xy[0]
                        a3y = a3xy[1]
                        # isS = IsS[0];
                        aPoint = PointD()
                        aPoint.X = a3x
                        aPoint.Y = a3y
                        pointList.append(aPoint)
                        if abs(a3y - sy) < 0.000001 and abs(a3x - sx) < 0.000001:
                            break

                        a2x = a3x
                        # a2y = a3y;
                        i1 = i2
                        j1 = j2
                        i2 = i3
                        j2 = j3
                        # If X[j2] < a2x && i2 = 0 )
                        #     aLine.type = "Error"
                        #     Exit Do
                        # End If
                    else:
                        aLine.Type = "Error"
                        break
                H[i][j] = -2
                if len(pointList) > 1 and aLine.Type != "Error":
                    aLine.Value = W
                    aLine.PointList = pointList
                    cLineList.append(aLine)

    for i in range(1, m - 1):
        for j in range(1, n - 2):
            if S[i][j] != -2:
                pointList = []
                i2 = i
                j2 = j
                a2x = X[j2] + S[i][j] * (X[j2 + 1] - X[j2])
                a2y = Y[i]
                j1 = j2
                i1 = -1
                sx = a2x
                sy = a2y
                aPoint = PointD()
                aPoint.X = a2x
                aPoint.Y = a2y
                pointList.append(aPoint)
                aLine = PolyLine()
                aLine.Type = "Close"

                while True:
                    ij3 = [0, 0]
                    a3xy = [0.0, 0.0]
                    IsS = [False]
                    if traceIsoline_UndefData(i1, i2, H, S, j1, j2, X, Y, a2x, ij3, a3xy, IsS):
                        i3 = ij3[0]
                        j3 = ij3[1]
                        a3x = a3xy[0]
                        a3y = a3xy[1]
                        # isS = IsS[0];
                        aPoint = PointD()
                        aPoint.X = a3x
                        aPoint.Y = a3y
                        pointList.append(aPoint)
                        if abs(a3y - sy) < 0.000001 and abs(a3x - sx) < 0.000001:
                            break

                        a2x = a3x
                        # a2y = a3y;
                        i1 = i2
                        j1 = j2
                        i2 = i3
                        j2 = j3
                    else:
                        aLine.Type = "Error"
                        break
                S[i][j] = -2
                if len(pointList) > 1 and aLine.Type != "Error":
                    aLine.Value = W
                    aLine.PointList = pointList
                    cLineList.append(aLine)

    return cLineList
