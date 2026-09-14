# -*- coding: utf-8 -*-
"""
wcontour.helpers —— wContour 1.6.1 `wcontour.Contour` 基础工具方法的 1:1 Python 移植。

上游（唯一权威）
================
meteoinfo/wContour, src/main/java/wcontour/Contour.java (LGPL-3.0)，
以及 wcontour/global/BorderPoint.java、wcontour/global/PointD.java。
原始 Java 源码随包放在 ``wcontour/_upstream/``，移植规则见 ``PORTING_RULES.md``。

移植原则
========
**行为等价**，不是"重写得更漂亮"：

* 保留 Java 的变量名、循环变量名、循环边界、语句顺序；
* 保留引用/别名语义：Java 里 ``a = b`` 共享同一对象，Python 里也共享，
  绝不顺手 ``.copy()``；``new ArrayList<>(x)`` → ``list(x)``（浅拷贝）；
* Java ``double`` → Python ``float``，``double[]`` → ``list``，
  ``double[][] S0`` → ``list[list[float]]``（``S0[i][j]``：i 是行/Y，j 是列/X）；
* 看起来可疑但必须照抄的边界处理一律照抄，不"修正"、不合并、不提前 return。

``idiv`` / ``imod`` 是本移植层**新增**的辅助函数（Java 里没有同名方法），
用来复现 Java ``int / int``（向零截断）与 ``int % int``（结果符号随被除数）的语义。
"""

from .global_types import BorderPoint, Extent, PointD


def idiv(a, b):
    """本移植层新增辅助函数（Java 无同名方法）：复现 Java `int / int` 的语义。

    Java 的整数除法**向零截断**，而 Python 的 `//` 是向下取整：

        Java:   -7 / 2 == -3        Python: -7 // 2 == -4
        Java:    7 / 2 ==  3        Python:  7 // 2 ==  3

    本函数返回与 Java 相同的商（`a` 与 `b` 异号时对 `abs(a) // abs(b)` 取负）。
    `b == 0` 时抛 ZeroDivisionError，对应 Java 的 ArithmeticException。
    """
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q


def imod(a, b):
    """本移植层新增辅助函数（Java 无同名方法）：复现 Java `int % int` 的语义。

    Java 的余数定义为 ``a - (a / b) * b``，其中 `/` 是向零截断的整数除法，
    因此结果的符号**跟着被除数走**：

        Java:   -7 % 2 == -1        Python: -7 % 2 ==  1
        Java:    7 % -2 ==  1       Python:  7 % -2 == -1

    `b == 0` 时抛 ZeroDivisionError，对应 Java 的 ArithmeticException。
    """
    return a - idiv(a, b) * b


def doubleEquals(a, b):
    """Java: doubleEquals(double a, double b) L8078-8085"""
    difference = abs(a * 0.00001)
    if abs(a - b) <= difference:
        return True
    else:
        return False


def getExtent(pList):
    """Java: getExtent(List<PointD> pList) L7562-7597"""
    aPoint = pList[0]
    minX = aPoint.X
    maxX = aPoint.X
    minY = aPoint.Y
    maxY = aPoint.Y
    for i in range(1, len(pList)):
        aPoint = pList[i]
        if aPoint.X < minX:
            minX = aPoint.X

        if aPoint.X > maxX:
            maxX = aPoint.X

        if aPoint.Y < minY:
            minY = aPoint.Y

        if aPoint.Y > maxY:
            maxY = aPoint.Y

    aExtent = Extent()
    aExtent.xMin = minX
    aExtent.yMin = minY
    aExtent.xMax = maxX
    aExtent.yMax = maxY

    return aExtent


def getExtentAndArea(pList, aExtent):
    """Java: getExtentAndArea(List<PointD> pList, Extent aExtent) L7599-7634

    注意：`aExtent` 是**原地改写**（Java 传引用），返回值是面积 `bArea`。
    """
    aPoint = pList[0]
    minX = aPoint.X
    maxX = aPoint.X
    minY = aPoint.Y
    maxY = aPoint.Y
    for i in range(1, len(pList)):
        aPoint = pList[i]
        if aPoint.X < minX:
            minX = aPoint.X

        if aPoint.X > maxX:
            maxX = aPoint.X

        if aPoint.Y < minY:
            minY = aPoint.Y

        if aPoint.Y > maxY:
            maxY = aPoint.Y

    aExtent.xMin = minX
    aExtent.yMin = minY
    aExtent.xMax = maxX
    aExtent.yMax = maxY
    bArea = (maxX - minX) * (maxY - minY)

    return bArea


def isClockwise(pointList):
    """Java: isClockwise(List<PointD> pointList) L7642-7675"""
    yMax = 0.0
    yMaxIdx = 0
    for i in range(0, len(pointList) - 1):
        aPoint = pointList[i]
        if i == 0:
            yMax = aPoint.Y
            yMaxIdx = 0
        elif yMax < aPoint.Y:
            yMax = aPoint.Y
            yMaxIdx = i

    p1Idx = yMaxIdx - 1
    p2Idx = yMaxIdx
    p3Idx = yMaxIdx + 1
    if yMaxIdx == 0:
        p1Idx = len(pointList) - 2

    p1 = pointList[p1Idx]
    p2 = pointList[p2Idx]
    p3 = pointList[p3Idx]
    if (p3.X - p1.X) * (p2.Y - p1.Y) - (p2.X - p1.X) * (p3.Y - p1.Y) > 0:
        return True
    else:
        return False


def pointInPolygon_poly(poly, aPoint):
    """Java: pointInPolygon(List<PointD> poly, PointD aPoint) L1434-1473

    （Java 同名重载之一；另一个是 pointInPolygon_polygon。）
    """
    inside = False
    nPoints = len(poly)

    if nPoints < 3:
        return False

    xOld = poly[nPoints - 1].X
    yOld = poly[nPoints - 1].Y
    for i in range(0, nPoints):
        xNew = poly[i].X
        yNew = poly[i].Y
        if xNew > xOld:
            x1 = xOld
            x2 = xNew
            y1 = yOld
            y2 = yNew
        else:
            x1 = xNew
            x2 = xOld
            y1 = yNew
            y2 = yOld

        # ---- edge "open" at left end
        if ((xNew < aPoint.X) == (aPoint.X <= xOld)
                and (aPoint.Y - y1) * (x2 - x1) < (y2 - y1) * (aPoint.X - x1)):
            inside = not inside

        xOld = xNew
        yOld = yNew

    return inside


def pointInPolygon_polygon(aPolygon, aPoint):
    """Java: pointInPolygon(Polygon aPolygon, PointD aPoint) L1482-1498"""
    if aPolygon.HasHoles():
        isIn = pointInPolygon_poly(aPolygon.OutLine.PointList, aPoint)
        if isIn:
            for aLine in aPolygon.HoleLines:
                if pointInPolygon_poly(aLine.PointList, aPoint):
                    isIn = False
                    break

        return isIn
    else:
        return pointInPolygon_poly(aPolygon.OutLine.PointList, aPoint)


def insertPoint2Border(bPList, aBorderList):
    """Java: insertPoint2Border(List<BorderPoint> bPList, List<BorderPoint> aBorderList) L7789-7816

    `list(aBorderList)` 对应 Java 的 `new ArrayList<>(aBorderList)`：浅拷贝，
    返回的是**新** list（元素仍是共享的 BorderPoint 对象），原 list 不被改写。
    """
    BorderList = list(aBorderList)

    for i in range(0, len(bPList)):
        bP = bPList[i]
        p3 = bP.Point
        aBPoint = BorderList[0]
        p1 = aBPoint.Point
        for j in range(1, len(BorderList)):
            aBPoint = BorderList[j]
            p2 = aBPoint.Point
            if (p3.X - p1.X) * (p3.X - p2.X) <= 0:
                if (p3.Y - p1.Y) * (p3.Y - p2.Y) <= 0:
                    if (p3.X - p1.X) * (p2.Y - p1.Y) - (p2.X - p1.X) * (p3.Y - p1.Y) == 0:
                        BorderList.insert(j, bP)
                        break

            p1 = p2

    return BorderList


def insertPoint2Border_Ring(S0, bPList, aBorder, pNums):
    """Java: insertPoint2Border_Ring(double[][] S0, List<BorderPoint> bPList, Border aBorder, int[] pNums) L8029-8076

    `bP` 是 `bPList.get(i).clone()`：Java 的 BorderPoint.clone() 新建对象并逐字段
    赋值，但 `Point` 仍与原对象**共享引用**（见 global/BorderPoint.java L20-30），
    这里按同样的语义内联展开（global_types.py 只读，不新增方法）。
    `p1` / `p2` 则是 `PointD.clone()`，即真正新建的 PointD（global/PointD.java L36-39）。
    `pNums` 是 int[]，**原地改写**（Java 传引用）。
    """
    newBPList = []
    tempBPList = []
    tempBPList1 = []

    for k in range(0, aBorder.getLineNum()):
        aBLine = aBorder.LineList[k]
        tempBPList.clear()
        for i in range(0, len(aBLine.pointList)):
            aBPoint = BorderPoint()
            aBPoint.Id = -1
            aBPoint.BorderIdx = k
            aBPoint.Point = aBLine.pointList[i]
            aBPoint.Value = S0[aBLine.ijPointList[i].I][aBLine.ijPointList[i].J]
            tempBPList.append(aBPoint)
        for i in range(0, len(bPList)):
            bP = BorderPoint()
            bP.Id = bPList[i].Id
            bP.BorderIdx = bPList[i].BorderIdx
            bP.BInnerIdx = bPList[i].BInnerIdx
            bP.Point = bPList[i].Point
            bP.Value = bPList[i].Value
            bP.BorderIdx = k
            p3 = bP.Point
            p1 = PointD(tempBPList[0].Point.X, tempBPList[0].Point.Y)
            for j in range(1, len(tempBPList)):
                p2 = PointD(tempBPList[j].Point.X, tempBPList[j].Point.Y)
                if (p3.X - p1.X) * (p3.X - p2.X) <= 0:
                    if (p3.Y - p1.Y) * (p3.Y - p2.Y) <= 0:
                        if (p3.X - p1.X) * (p2.Y - p1.Y) - (p2.X - p1.X) * (p3.Y - p1.Y) == 0:
                            tempBPList.insert(j, bP)
                            break

                p1 = p2
        tempBPList1.clear()
        for i in range(0, len(tempBPList)):
            bP = tempBPList[i]
            bP.BInnerIdx = i
            tempBPList1.append(bP)
        pNums[k] = len(tempBPList1)
        newBPList.extend(tempBPList1)

    return newBPList
