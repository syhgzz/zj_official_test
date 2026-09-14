# -*- coding: utf-8 -*-
"""
wcontour.polygons_trace —— wContour 1.6.1 `Contour.java` 中「把等值线与边界拼装成闭合多边形」
部分的 1:1 Python 移植。

本模块只包含两个方法：

* ``tracingPolygons_hasborder``  ← Java ``tracingPolygons(List<PolyLine>, List<BorderPoint>, boolean)``
  —— 私有三参数重载，因 Python 不能重载而同名方法改名（见 PORTING_RULES.md）。
  注意 Java 里另有两个 ``tracingPolygons`` 重载：
  ``tracingPolygons(double[][], List<PolyLine>, List<Border>, double[])``（公开入口，归 polygons.py）
  与 ``tracingPolygons(List<PolyLine>, List<BorderPoint>, Extent, double[])``
  （L3046-3479，只被 createContourPolygons / createCutContourPolygons 调用，**不移植**）。
* ``judgePolygonHighCenter``     ← Java ``judgePolygonHighCenter(List<Polygon>, List<Polygon>,
  List<PolyLine>, List<BorderPoint>)`` —— Java 里是**四个**形参，第四个 ``borderList`` 在
  L3996 被使用，故 Python 同样是四个形参。

移植原则（详见 PORTING_RULES.md）：逐行照抄，保留 Java 的变量名、语句顺序、
循环边界与 ``break``/``continue`` 位置；保留引用别名语义（``aPList``、
``aPolygon.OutLine.PointList`` 等是**共享**同一个 list，不做 copy）。

上游：meteoinfo/wContour, src/main/java/wcontour/Contour.java (LGPL-3.0)。
"""

from .global_types import Polygon, Extent, PolyLine
from .helpers import getExtentAndArea, isClockwise, pointInPolygon_poly

__all__ = ['tracingPolygons_hasborder', 'judgePolygonHighCenter']


# Java: Double.MAX_VALUE —— 1.7976931348623157E308
DOUBLE_MAX_VALUE = 1.7976931348623157e308
# Java: Double.MIN_VALUE —— 最小的**正**非零 double（denormal），4.9E-324，不是负的最大值
DOUBLE_MIN_VALUE = 5e-324


def tracingPolygons_hasborder(LineList, borderList, hasBorder):
    """Java: tracingPolygons(LineList, borderList, hasBorder) L3481-3754

    private static List<Polygon> tracingPolygons(List<PolyLine> LineList,
                                                List<BorderPoint> borderList,
                                                boolean hasBorder)

    按 ``hasBorder`` 把边界上的点（``borderList``）与等值线（``LineList``）串成闭合多边形：
    先对每个边界点做顺时针/逆时针两轮追踪生成 ``IsBorder = true`` 的边界多边形，
    再把 ``Type == "Close"`` 的等值线各自变成一个闭合多边形（按面积从大到小插入），
    最后交给 ``judgePolygonHighCenter`` 判定 ``IsHighCenter``。

    照抄要点：
    * ``aValue`` / ``bValue`` / ``cValue`` 在 ``hasBorder`` 块内**只初始化一次**，
      跨外层 ``for i`` 迭代保留上一轮的值（Java 中它们声明在循环外）。
    * ``aPList.append((borderList[pIdx]).Point)`` 与 ``aPolygon.OutLine.PointList = aPList``
      都是**引用共享**，绝不 copy。
    * ``timesArray = new int[borderList.size() - 1]``：Java 在 ``size() == 0`` 时抛
      NegativeArraySizeException，Python 侧 ``[0] * (len(borderList) - 1)`` 得空表。
    """
    if not LineList:
        return []

    aPolygonList = []
    aLineList = None
    aLine = None
    aPoint = None
    aPolygon = None
    aBound = None
    i = 0
    j = 0

    aLineList = list(LineList)

    # ---- Tracing border polygon
    if hasBorder:
        aPList = None
        newPList = None
        bP = None
        timesArray = [0] * (len(borderList) - 1)
        for i in range(0, len(timesArray)):
            timesArray[i] = 0

        pIdx = 0
        pNum = 0
        vNum = 0
        vvNum = 0
        aValue = 0.0
        bValue = 0.0
        cValue = 0.0
        lineBorderList = []

        pNum = len(borderList) - 1
        for i in range(0, pNum):
            if (borderList[i]).Id == -1:
                continue

            pIdx = i
            aPList = []
            lineBorderList.append(borderList[i])

            # ---- Clockwise traceing
            if timesArray[pIdx] < 2:
                aPList.append((borderList[pIdx]).Point)
                pIdx += 1
                if pIdx == pNum:
                    pIdx = 0

                vNum = 0
                vvNum = 0
                while True:
                    bP = borderList[pIdx]
                    if bP.Id == -1:  # ---- Not endpoint of contour
                        if timesArray[pIdx] == 1:
                            break

                        cValue = bP.Value
                        vvNum += 1
                        aPList.append(bP.Point)
                        timesArray[pIdx] += 1
                    else:  # ---- endpoint of contour
                        if timesArray[pIdx] == 2:
                            break

                        timesArray[pIdx] += 1
                        aLine = aLineList[bP.Id]
                        if vNum == 0:
                            aValue = aLine.Value
                            bValue = aLine.Value
                            vNum += 1
                        else:
                            if aLine.Value > aValue:
                                bValue = aLine.Value
                            elif aLine.Value < aValue:
                                aValue = aLine.Value

                            vNum += 1
                        newPList = list(aLine.PointList)
                        aPoint = newPList[0]
                        if not (bP.Point.X == aPoint.X and bP.Point.Y == aPoint.Y):  # ---- Start point
                            newPList.reverse()

                        aPList.extend(newPList)
                        for j in range(0, len(borderList) - 1):
                            if j != pIdx:
                                if (borderList[j]).Id == bP.Id:
                                    pIdx = j
                                    timesArray[pIdx] += 1
                                    break

                    if pIdx == i:
                        if len(aPList) > 0:
                            aPolygon = Polygon()
                            aPolygon.IsBorder = True
                            aPolygon.LowValue = aValue
                            aPolygon.HighValue = bValue
                            aBound = Extent()
                            aPolygon.Area = getExtentAndArea(aPList, aBound)
                            aPolygon.IsClockWise = True
                            aPolygon.StartPointIdx = len(lineBorderList) - 1
                            aPolygon.Extent = aBound
                            aPolygon.OutLine.PointList = aPList
                            aPolygon.OutLine.Value = aValue
                            aPolygon.IsHighCenter = True
                            aPolygon.HoleLines = []
                            if vvNum > 0:
                                if cValue < aValue:
                                    aPolygon.IsHighCenter = False
                                    aPolygon.HighValue = aValue
                            aPolygon.OutLine.Type = "Border"
                            aPolygonList.append(aPolygon)
                        break
                    pIdx += 1
                    if pIdx == pNum:
                        pIdx = 0

            # ---- Anticlockwise traceing
            pIdx = i
            if timesArray[pIdx] < 2:
                aPList = []
                aPList.append((borderList[pIdx]).Point)
                pIdx += -1
                if pIdx == -1:
                    pIdx = pNum - 1

                vNum = 0
                vvNum = 0
                while True:
                    bP = borderList[pIdx]
                    if bP.Id == -1:  # ---- Not endpoint of contour
                        if timesArray[pIdx] == 1:
                            break

                        cValue = bP.Value
                        vvNum += 1
                        aPList.append(bP.Point)
                        timesArray[pIdx] += 1
                    else:  # ---- endpoint of contour
                        if timesArray[pIdx] == 2:
                            break

                        timesArray[pIdx] += 1
                        aLine = aLineList[bP.Id]
                        if vNum == 0:
                            aValue = aLine.Value
                            bValue = aLine.Value
                            vNum += 1
                        else:
                            if aLine.Value > aValue:
                                bValue = aLine.Value
                            elif aLine.Value < aValue:
                                aValue = aLine.Value

                            vNum += 1
                        newPList = list(aLine.PointList)
                        aPoint = newPList[0]
                        if not (bP.Point.X == aPoint.X and bP.Point.Y == aPoint.Y):  # ---- Start point
                            newPList.reverse()

                        aPList.extend(newPList)
                        for j in range(0, len(borderList) - 1):
                            if j != pIdx:
                                if (borderList[j]).Id == bP.Id:
                                    pIdx = j
                                    timesArray[pIdx] += 1
                                    break

                    if pIdx == i:
                        if len(aPList) > 0:
                            aPolygon = Polygon()
                            aPolygon.IsBorder = True
                            aPolygon.LowValue = aValue
                            aPolygon.HighValue = bValue
                            aBound = Extent()
                            aPolygon.Area = getExtentAndArea(aPList, aBound)
                            aPolygon.IsClockWise = False
                            aPolygon.StartPointIdx = len(lineBorderList) - 1
                            aPolygon.Extent = aBound
                            aPolygon.OutLine.PointList = aPList
                            aPolygon.OutLine.Value = aValue
                            aPolygon.IsHighCenter = True
                            aPolygon.HoleLines = []
                            if vvNum > 0:
                                if cValue < aValue:
                                    aPolygon.IsHighCenter = False
                                    aPolygon.HighValue = aValue
                            aPolygon.OutLine.Type = "Border"
                            aPolygonList.append(aPolygon)
                        break
                    pIdx += -1
                    if pIdx == -1:
                        pIdx = pNum - 1

    # ---- tracing close polygons
    cPolygonlist = []
    isInserted = False
    for i in range(0, len(aLineList)):
        aLine = aLineList[i]
        if aLine.Type == "Close" and len(aLine.PointList) > 0:
            aPolygon = Polygon()
            aPolygon.IsBorder = False
            aPolygon.LowValue = aLine.Value
            aPolygon.HighValue = aLine.Value
            aBound = Extent()
            aPolygon.Area = getExtentAndArea(aLine.PointList, aBound)
            aPolygon.IsClockWise = isClockwise(aLine.PointList)
            aPolygon.Extent = aBound
            aPolygon.OutLine = aLine
            aPolygon.IsHighCenter = True
            aPolygon.HoleLines = []

            # ---- Sort from big to small
            isInserted = False
            for j in range(0, len(cPolygonlist)):
                if aPolygon.Area > (cPolygonlist[j]).Area:
                    cPolygonlist.insert(j, aPolygon)
                    isInserted = True
                    break
            if not isInserted:
                cPolygonlist.append(aPolygon)

    # ---- Juge isHighCenter for border polygons
    aPolygonList = judgePolygonHighCenter(aPolygonList, cPolygonlist, aLineList, borderList)

    return aPolygonList


def judgePolygonHighCenter(borderPolygons, closedPolygons, aLineList, borderList):
    """Java: judgePolygonHighCenter(borderPolygons, closedPolygons, aLineList, borderList) L3983-4068

    private static List<Polygon> judgePolygonHighCenter(List<Polygon> borderPolygons,
                                                        List<Polygon> closedPolygons,
                                                        List<PolyLine> aLineList,
                                                        List<BorderPoint> borderList)

    判定每个闭合等值线多边形的 ``IsHighCenter``（高分中心还是低分中心）：

    * 若 ``borderPolygons`` 为空，先用边界与等值线值造一个覆盖整个边界的 ``IsBorder = true``
      多边形（``min`` / ``max`` 分别取边界值以下最大、以上最小的等值线值；找不到时回落到边界值，
      并相应地把 ``IsHighCenter`` 置 false / true）。
    * 把 ``closedPolygons`` 追加到 ``borderPolygons`` 之后，再对每个 ``Type == "Close"`` 的
      多边形，向上遍历它之前的每一个多边形：若该多边形严格包含于前者范围内且落在其内部，
      则按内层多边形的 ``IsHighCenter`` 决定本层的 ``IsHighCenter``，随后 ``break``。

    照抄要点：
    * Java 的 ``Double.MIN_VALUE`` 是**最小正数** 4.9E-324（不是负的最大值），
      因此 ``min == Double.MIN_VALUE`` 这个判断语义特殊，照抄。
    * ``borderPolygons`` 是**原地**被 append / extend 修改的调用方 list，且最终被返回。
    * 逐行照抄也意味着：``newPList`` 在这里只是 ``pointInPolygon`` 的入参副本，
      ``if/else if``（而不是两个独立的 if）的写法、以及 ``break`` 的位置都保持一致。
    """
    i = 0
    j = 0
    aPolygon = None
    aLine = None
    newPList = []
    aBound = None
    aValue = 0.0
    aPoint = None

    if not borderPolygons:  # Add border polygon
        # Get max & min values
        aValue = borderList[0].Value
        max = DOUBLE_MAX_VALUE
        min = DOUBLE_MIN_VALUE
        for aPLine in aLineList:
            if aPLine.Value < aValue and aPLine.Value > min:
                min = aPLine.Value
            if aPLine.Value > aValue and aPLine.Value < max:
                max = aPLine.Value

        aPolygon = Polygon()
        if min == DOUBLE_MIN_VALUE:
            min = aValue
            aPolygon.IsHighCenter = False
        elif max == DOUBLE_MAX_VALUE:
            max = aValue
            aPolygon.IsHighCenter = True

        aLine = PolyLine()
        aLine.Type = "Border"
        aLine.Value = aValue
        newPList.clear()
        for aP in borderList:
            newPList.append(aP.Point)
        aLine.PointList = list(newPList)
        if len(aLine.PointList) > 0:
            aPolygon.IsBorder = True
            aPolygon.LowValue = min
            aPolygon.HighValue = max
            aBound = Extent()
            aPolygon.Area = getExtentAndArea(aLine.PointList, aBound)
            aPolygon.IsClockWise = isClockwise(aLine.PointList)
            aPolygon.Extent = aBound
            aPolygon.OutLine = aLine
            aPolygon.HoleLines = []
            borderPolygons.append(aPolygon)

    # ---- Add close polygons to form total polygons list
    borderPolygons.extend(closedPolygons)

    # ---- Juge IsHighCenter for close polygons
    cBound1 = None
    cBound2 = None
    polygonNum = len(borderPolygons)
    bPolygon = None
    for i in range(1, polygonNum):
        aPolygon = borderPolygons[i]
        if aPolygon.OutLine.Type == "Close":
            cBound1 = aPolygon.Extent
            aPoint = aPolygon.OutLine.PointList[0]
            for j in range(i - 1, -1, -1):
                bPolygon = borderPolygons[j]
                cBound2 = bPolygon.Extent
                newPList = list(bPolygon.OutLine.PointList)
                if pointInPolygon_poly(newPList, aPoint):
                    if (cBound1.xMin > cBound2.xMin and cBound1.yMin > cBound2.yMin
                            and cBound1.xMax < cBound2.xMax and cBound1.yMax < cBound2.yMax):
                        if bPolygon.IsHighCenter:
                            aPolygon.IsHighCenter = aPolygon.HighValue != bPolygon.LowValue
                        else:
                            aPolygon.IsHighCenter = aPolygon.LowValue == bPolygon.HighValue
                        break

    return borderPolygons
