# -*- coding: utf-8 -*-
"""
wcontour.polygons —— wContour 1.6.1 `Contour.java` 等值面追踪（多边形装配）部分的 1:1 Python 移植。

对应上游 Java 方法（`wcontour/Contour.java`）：

* ``tracingPolygons(double[][] S0, List<PolyLine> cLineList, List<Border> borderList, double[] contour)``
* ``tracingPolygons_Ring(List<PolyLine> LineList, List<BorderPoint> borderList, Border aBorder,
  double[] contour, int[] pNums)``
* ``addPolygonHoles(List<Polygon> polygonList)``
* ``addPolygonHoles_Ring(List<Polygon> polygonList)``
* ``addHoles_Ring(List<Polygon> polygonList, List<List<PointD>> holeList)``

**未移植**（不在迅腾 `finishFromGrid` 链路上，见 PORTING_RULES.md 的文件划分）：
``tracingPolygons(List<PolyLine>, List<BorderPoint>, Extent, double[])``（Java L3046-3479）、
``createContourPolygons`` / ``createCutContourPolygons`` / ``createBorderContourPolygons`` /
``tracingClipPolygons`` / ``cutPolygon*`` / ``clipPolygon*``。

移植原则
========
逐行等价，不修正 Java 里看着多余/可疑的写法：

* ``PList = aBLine.pointList`` 是**共享引用**，``Collections.reverse(PList)`` 必须写成
  原地 ``PList.reverse()``（会翻转 Border 自己的点表）。
* ``new ArrayList<>(x)`` → ``list(x)``（浅拷贝）；``a = b`` 一律共享。
* ``addHoles_Ring`` 把 ``aBorder.LineList[j].pointList`` 原对象当洞传下去，不拷贝。
* 保留 Java 的变量名、循环边界、语句顺序；``(int)d`` → ``int(d)``。
"""

from .global_types import BorderPoint, Extent, Polygon, PolyLine
from .helpers import (
    getExtent,
    getExtentAndArea,
    isClockwise,
    pointInPolygon_poly,
    insertPoint2Border,
    insertPoint2Border_Ring,
)
from .polygons_trace import tracingPolygons_hasborder


def tracingPolygons(S0, cLineList, borderList, contour):
    """Java: tracingPolygons(double[][], List<PolyLine>, List<Border>, double[]) L971-1185

    整个等值面装配链路的总入口：遍历每个 ``Border``，按 ``aBorder.getLineNum() == 1``
    分成"单线边界"与"带洞边界"两条分支；带洞分支调用 ``tracingPolygons_Ring`` 后按面积
    做**手写插入排序**（照抄 Java 的 while 写法），再 ``addHoles_Ring`` +
    ``addPolygonHoles_Ring``；最后统一把每个多边形外环校正为顺时针。
    """
    aPolygonList = []
    newPolygonList = []
    bPList = []
    lineList = []
    aBorderList = []
    aValue = 0.0

    # Borders loop
    for i in range(len(borderList)):
        aBorderList.clear()
        bPList.clear()
        lineList.clear()
        aPolygonList.clear()
        aBorder = borderList[i]

        aBLine = aBorder.LineList[0]
        PList = aBLine.pointList
        if not isClockwise(PList):  # Make sure the point list is clockwise
            PList.reverse()

        if aBorder.getLineNum() == 1:  # The border has just one line
            # Construct border point list
            for j in range(len(PList)):
                aPoint = PList[j]
                aBPoint = BorderPoint()
                aBPoint.Id = -1
                aBPoint.Point = aPoint
                aBPoint.Value = S0[aBLine.ijPointList[j].I][aBLine.ijPointList[j].J]
                aBorderList.append(aBPoint)

            # Find the contour lines of this border
            for j in range(len(cLineList)):
                aLine = cLineList[j]
                if aLine.BorderIdx == i:
                    lineList.append(aLine)  # Construct contour line list
                    # Construct border point list of the contour line
                    if aLine.Type == "Border":  # The contour line with the start/end point on the border
                        aPoint = aLine.PointList[0]
                        aBPoint = BorderPoint()
                        aBPoint.Id = len(lineList) - 1
                        aBPoint.Point = aPoint
                        aBPoint.Value = aLine.Value
                        bPList.append(aBPoint)
                        aPoint = aLine.PointList[len(aLine.PointList) - 1]
                        aBPoint = BorderPoint()
                        aBPoint.Id = len(lineList) - 1
                        aBPoint.Point = aPoint
                        aBPoint.Value = aLine.Value
                        bPList.append(aBPoint)

            if not lineList:  # No contour lines in this border, the polygon is the border
                # Judge the value of the polygon
                aijP = aBLine.ijPointList[0]
                aPolygon = Polygon()
                if S0[aijP.I][aijP.J] < contour[0]:
                    aValue = contour[0]
                    aPolygon.IsHighCenter = False
                else:
                    for j in range(len(contour) - 1, -1, -1):
                        if S0[aijP.I][aijP.J] > contour[j]:
                            aValue = contour[j]
                            break
                    aPolygon.IsHighCenter = True
                if len(PList) > 0:
                    aPolygon.IsBorder = True
                    aPolygon.HighValue = aValue
                    aPolygon.LowValue = aValue
                    aPolygon.Extent = Extent()
                    aPolygon.Area = getExtentAndArea(PList, aPolygon.Extent)
                    aPolygon.StartPointIdx = 0
                    aPolygon.IsClockWise = True
                    aPolygon.OutLine.Type = "Border"
                    aPolygon.OutLine.Value = aValue
                    aPolygon.OutLine.BorderIdx = i
                    aPolygon.OutLine.PointList = PList
                    aPolygon.HoleLines = []
                    aPolygonList.append(aPolygon)
            else:  # Has contour lines in this border
                # Insert the border points of the contour lines to the border point list of the border
                if len(bPList) > 0:
                    newBPList = insertPoint2Border(bPList, aBorderList)
                else:
                    newBPList = aBorderList
                # aPolygonList = TracingPolygons(lineList, newBPList, aBound, contour);
                aPolygonList = tracingPolygons_hasborder(lineList, newBPList, len(bPList) > 0)
            aPolygonList = addPolygonHoles(aPolygonList)
        else:  # ---- The border has holes
            aBLine = aBorder.LineList[0]
            # Find the contour lines of this border
            for j in range(len(cLineList)):
                aLine = cLineList[j]
                if aLine.BorderIdx == i:
                    lineList.append(aLine)
                    if aLine.Type == "Border":
                        aPoint = aLine.PointList[0]
                        aBPoint = BorderPoint()
                        aBPoint.Id = len(lineList) - 1
                        aBPoint.Point = aPoint
                        aBPoint.Value = aLine.Value
                        bPList.append(aBPoint)
                        aPoint = aLine.PointList[len(aLine.PointList) - 1]
                        aBPoint = BorderPoint()
                        aBPoint.Id = len(lineList) - 1
                        aBPoint.Point = aPoint
                        aBPoint.Value = aLine.Value
                        bPList.append(aBPoint)
            if not lineList:  # No contour lines in this border, the polygon is the border and the holes
                aijP = aBLine.ijPointList[0]
                aPolygon = Polygon()
                if S0[aijP.I][aijP.J] < contour[0]:
                    aValue = contour[0]
                    aPolygon.IsHighCenter = False
                else:
                    for j in range(len(contour) - 1, -1, -1):
                        if S0[aijP.I][aijP.J] > contour[j]:
                            aValue = contour[j]
                            break
                    aPolygon.IsHighCenter = True
                if len(PList) > 0:
                    aPolygon.IsBorder = True
                    aPolygon.HighValue = aValue
                    aPolygon.LowValue = aValue
                    aPolygon.Area = getExtentAndArea(PList, aPolygon.Extent)
                    aPolygon.StartPointIdx = 0
                    aPolygon.IsClockWise = True
                    aPolygon.OutLine.Type = "Border"
                    aPolygon.OutLine.Value = aValue
                    aPolygon.OutLine.BorderIdx = i
                    aPolygon.OutLine.PointList = PList
                    aPolygon.HoleLines = []
                    aPolygonList.append(aPolygon)
            else:
                pNums = [0] * aBorder.getLineNum()
                newBPList = insertPoint2Border_Ring(S0, bPList, aBorder, pNums)
                aPolygonList = tracingPolygons_Ring(lineList, newBPList, aBorder, contour, pNums)

                # Sort polygons by area
                sortList = []
                while len(aPolygonList) > 0:
                    isInsert = False
                    for j in range(len(sortList)):
                        if aPolygonList[0].Area > sortList[j].Area:
                            sortList.append(aPolygonList[0])
                            isInsert = True
                            break
                    if not isInsert:
                        sortList.append(aPolygonList[0])
                    aPolygonList.pop(0)
                aPolygonList = sortList
            holeList = []
            for j in range(aBorder.getLineNum()):
                # if aBorder.LineList[j].pointList.size() == pNums[j]:
                #     holeList.add(aBorder.LineList[j].pointList)
                holeList.append(aBorder.LineList[j].pointList)

            if len(holeList) > 0:
                addHoles_Ring(aPolygonList, holeList)
            aPolygonList = addPolygonHoles_Ring(aPolygonList)
        newPolygonList.extend(aPolygonList)

    # newPolygonList = AddPolygonHoles(newPolygonList);
    for nPolygon in newPolygonList:
        if not isClockwise(nPolygon.OutLine.PointList):
            nPolygon.OutLine.PointList.reverse()

    return newPolygonList


def tracingPolygons_Ring(LineList, borderList, aBorder, contour, pNums):
    """Java: tracingPolygons_Ring(List<PolyLine>, List<BorderPoint>, Border, double[], int[]) L4070-4503

    带洞边界（``aBorder.getLineNum() > 1``）的多边形状态机：对每个轮廓线端点分别做
    **顺时针**与**逆时针**两次 tracing，用 ``timesArray`` 控制每条边界点最多被走 2 次；
    之后处理 ``Type == "Close"`` 的闭合轮廓线并判断 ``IsHighCenter``。

    注意 ``PList``/``newPList`` 的引用与翻转语义：``newPList = list(aLine.PointList)``
    是浅拷贝，再按需对**副本**原地 reverse；而 ``aPolygon.OutLine.PointList = aPList``
    以及 ``aLine.PointList = list(aBorder.LineList[0].pointList)`` 均按 Java 原样。
    """
    aPolygonList = []
    aLineList = list(LineList)

    # ---- Tracing border polygon
    timesArray = [0] * len(borderList)
    for i in range(len(timesArray)):
        timesArray[i] = 0
    aValue = 0.0
    bValue = 0.0
    cValue = 0.0
    lineBorderList = []

    pNum = len(borderList)
    for i in range(pNum):
        if borderList[i].Id == -1:
            continue
        pIdx = i
        lineBorderList.append(borderList[i])

        sameBorderIdx = False  # The two end points of the contour line are on same inner border
        innerStart = False
        # ---- Clockwise traceing
        if timesArray[pIdx] < 2:
            bP = borderList[pIdx]
            innerStart = bP.BorderIdx > 0
            innerIdx = bP.BInnerIdx
            aPList = []
            bIdxList = []
            aPList.append(bP.Point)
            borderIdx1 = bP.BorderIdx
            borderIdx2 = borderIdx1
            pIdx += 1
            innerIdx += 1
            if innerIdx == pNums[borderIdx1] - 1:
                pIdx = pIdx - (pNums[borderIdx1] - 1)
            vNum = 0
            isRepeat = False
            while True:
                bP = borderList[pIdx]
                # ---- Not endpoint of contour
                if bP.Id == -1:
                    if timesArray[pIdx] == 1:
                        break
                    cValue = bP.Value
                    aPList.append(bP.Point)
                    timesArray[pIdx] += 1
                    bIdxList.append(pIdx)
                # ---- endpoint of contour
                else:
                    if timesArray[pIdx] == 2:
                        for bidx in bIdxList:
                            timesArray[bidx] -= 1
                        break
                    timesArray[pIdx] += 1
                    bIdxList.append(pIdx)
                    aLine = aLineList[bP.Id]
                    # ---- Set high and low value of the polygon
                    if vNum == 0:
                        aValue = aLine.Value
                        bValue = aLine.Value
                        vNum += 1
                    elif aValue == bValue:
                        if aLine.Value > aValue:
                            bValue = aLine.Value
                        elif aLine.Value < aValue:
                            aValue = aLine.Value
                        vNum += 1
                    newPList = list(aLine.PointList)
                    aPoint = newPList[0]
                    # ---- Not start point
                    if not (bP.Point.X == aPoint.X and bP.Point.Y == aPoint.Y):
                        newPList.reverse()
                    aPList.extend(newPList)
                    # ---- Find corresponding border point
                    for j in range(len(borderList)):
                        if j != pIdx:
                            bP1 = borderList[j]
                            if bP1.Id == bP.Id:
                                pIdx = j
                                innerIdx = bP1.BInnerIdx
                                timesArray[pIdx] += 1
                                bIdxList.append(pIdx)
                                borderIdx2 = bP1.BorderIdx
                                if bP.BorderIdx > 0 and bP.BorderIdx == bP1.BorderIdx:
                                    sameBorderIdx = True
                                if innerStart and bP1.BorderIdx == 0:
                                    for bidx in bIdxList:
                                        timesArray[bidx] -= 1
                                    isRepeat = True
                                break
                    if isRepeat:
                        break

                # ---- Return to start point, tracing finish
                if pIdx == i:
                    if len(aPList) > 0:
                        if sameBorderIdx:
                            isTooBig = False
                            baseNum = 0
                            for idx in range(bP.BorderIdx):
                                baseNum += pNums[idx]
                            sIdx = baseNum
                            eIdx = baseNum + pNums[bP.BorderIdx]
                            theIdx = sIdx
                            for idx in range(sIdx, eIdx):
                                if idx not in bIdxList:
                                    theIdx = idx
                                    break
                            if pointInPolygon_poly(aPList, borderList[theIdx].Point):
                                isTooBig = True

                            if isTooBig:
                                break
                        aPolygon = Polygon()
                        aPolygon.IsBorder = True
                        aPolygon.IsInnerBorder = sameBorderIdx
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
                        if aValue == bValue:
                            if cValue < aValue:
                                aPolygon.IsHighCenter = False
                        aPolygon.OutLine.Type = "Border"
                        aPolygon.HoleLines = []
                        aPolygonList.append(aPolygon)
                    break
                pIdx += 1
                innerIdx += 1
                if borderIdx1 != borderIdx2:
                    borderIdx1 = borderIdx2

                if innerIdx == pNums[borderIdx1] - 1:
                    pIdx = pIdx - (pNums[borderIdx1] - 1)
                    innerIdx = 0

        sameBorderIdx = False
        # ---- Anticlockwise traceing
        pIdx = i
        if timesArray[pIdx] < 2:
            aPList = []
            bIdxList = []
            bP = borderList[pIdx]
            innerStart = bP.BorderIdx > 0
            innerIdx = bP.BInnerIdx
            aPList.append(bP.Point)
            borderIdx1 = bP.BorderIdx
            borderIdx2 = borderIdx1
            pIdx += -1
            innerIdx += -1
            if innerIdx == -1:
                pIdx = pIdx + (pNums[borderIdx1] - 1)
            vNum = 0
            isRepeat = False
            while True:
                bP = borderList[pIdx]
                # ---- Not endpoint of contour
                if bP.Id == -1:
                    if timesArray[pIdx] == 1:
                        break
                    cValue = bP.Value
                    aPList.append(bP.Point)
                    bIdxList.append(pIdx)
                    timesArray[pIdx] += 1
                # ---- endpoint of contour
                else:
                    if timesArray[pIdx] == 2:
                        for bidx in bIdxList:
                            timesArray[bidx] -= 1
                        break
                    timesArray[pIdx] += 1
                    bIdxList.append(pIdx)
                    aLine = aLineList[bP.Id]
                    if vNum == 0:
                        aValue = aLine.Value
                        bValue = aLine.Value
                        vNum += 1
                    elif aValue == bValue:
                        if aLine.Value > aValue:
                            bValue = aLine.Value
                        elif aLine.Value < aValue:
                            aValue = aLine.Value
                        vNum += 1
                    newPList = list(aLine.PointList)
                    aPoint = newPList[0]
                    # ---- Start point
                    if not (bP.Point.X == aPoint.X and bP.Point.Y == aPoint.Y):
                        newPList.reverse()
                    aPList.extend(newPList)
                    for j in range(len(borderList)):
                        if j != pIdx:
                            bP1 = borderList[j]
                            if bP1.Id == bP.Id:
                                pIdx = j
                                innerIdx = bP1.BInnerIdx
                                timesArray[pIdx] += 1
                                bIdxList.append(pIdx)
                                borderIdx2 = bP1.BorderIdx
                                if bP.BorderIdx > 0 and bP.BorderIdx == bP1.BorderIdx:
                                    sameBorderIdx = True
                                if innerStart and bP1.BorderIdx == 0:
                                    for bidx in bIdxList:
                                        timesArray[bidx] -= 1
                                    isRepeat = True
                                break
                    if isRepeat:
                        break

                if pIdx == i:
                    if len(aPList) > 0:
                        if sameBorderIdx:
                            isTooBig = False
                            baseNum = 0
                            for idx in range(bP.BorderIdx):
                                baseNum += pNums[idx]
                            sIdx = baseNum
                            eIdx = baseNum + pNums[bP.BorderIdx]
                            theIdx = sIdx
                            for idx in range(sIdx, eIdx):
                                if idx not in bIdxList:
                                    theIdx = idx
                                    break
                            if pointInPolygon_poly(aPList, borderList[theIdx].Point):
                                isTooBig = True

                            if isTooBig:
                                break
                        aPolygon = Polygon()
                        aPolygon.IsBorder = True
                        aPolygon.IsInnerBorder = sameBorderIdx
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
                        if aValue == bValue:
                            if cValue < aValue:
                                aPolygon.IsHighCenter = False
                        aPolygon.OutLine.Type = "Border"
                        aPolygon.HoleLines = []
                        aPolygonList.append(aPolygon)
                    break
                pIdx += -1
                innerIdx += -1
                if borderIdx1 != borderIdx2:
                    borderIdx1 = borderIdx2
                if innerIdx == -1:
                    pIdx = pIdx + pNums[borderIdx1]
                    innerIdx = pNums[borderIdx1] - 1

    # ---- tracing close polygons
    cPolygonlist = []
    for i in range(len(aLineList)):
        aLine = aLineList[i]
        if aLine.Type == "Close":
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
            for j in range(len(cPolygonlist)):
                if aPolygon.Area > cPolygonlist[j].Area:
                    cPolygonlist.insert(j, aPolygon)
                    isInserted = True
                    break
            if not isInserted:
                cPolygonlist.append(aPolygon)

    # ---- Juge isHighCenter for border polygons
    if not aPolygonList:
        aLine = PolyLine()
        aLine.Type = "Border"
        # aLine.Value = contour[0];
        aLine.Value = borderList[0].Value
        aLine.PointList = list(aBorder.LineList[0].pointList)

        if len(aLine.PointList) > 0:
            aPolygon = Polygon()
            aPolygon.LowValue = aLine.Value
            aPolygon.HighValue = aLine.Value
            aBound = Extent()
            aPolygon.Area = getExtentAndArea(aLine.PointList, aBound)
            aPolygon.IsClockWise = isClockwise(aLine.PointList)
            aPolygon.Extent = aBound
            aPolygon.OutLine = aLine
            aPolygon.IsHighCenter = False
            aPolygonList.append(aPolygon)

    # ---- Add close polygons to form total polygons list
    aPolygonList.extend(cPolygonlist)

    # ---- Juge siHighCenter for close polygons
    polygonNum = len(aPolygonList)
    for i in range(polygonNum - 1, -1, -1):
        aPolygon = aPolygonList[i]
        if aPolygon.OutLine.Type == "Close":
            cBound1 = aPolygon.Extent
            aValue = aPolygon.LowValue
            aPoint = aPolygon.OutLine.PointList[0]
            for j in range(i - 1, -1, -1):
                bPolygon = aPolygonList[j]
                cBound2 = bPolygon.Extent
                bValue = bPolygon.LowValue
                newPList = list(bPolygon.OutLine.PointList)
                if pointInPolygon_poly(newPList, aPoint):
                    if (cBound1.xMin > cBound2.xMin and cBound1.yMin > cBound2.yMin
                            and cBound1.xMax < cBound2.xMax and cBound1.yMax < cBound2.yMax):
                        if aValue < bValue:
                            aPolygon.IsHighCenter = False
                        elif aValue == bValue:
                            if bPolygon.IsHighCenter:
                                aPolygon.IsHighCenter = False
                        break

    return aPolygonList


def addPolygonHoles(polygonList):
    """Java: addPolygonHoles(List<Polygon>) L4505-4558

    把 ``IsBorder == False`` 的多边形按包含关系挂成其它多边形的洞（``AddHole`` 共享
    ``OutLine`` 引用），并返回"带洞外环 + 全部洞多边形"的新列表。
    """
    holePolygons = []
    for i in range(len(polygonList)):
        aPolygon = polygonList[i]
        if not aPolygon.IsBorder:
            aPolygon.HoleIndex = 1
            holePolygons.append(aPolygon)

    if not holePolygons:
        return polygonList
    else:
        newPolygons = []
        for i in range(1, len(holePolygons)):
            aPolygon = holePolygons[i]
            for j in range(i - 1, -1, -1):
                bPolygon = holePolygons[j]
                if bPolygon.Extent.include(aPolygon.Extent):
                    if pointInPolygon_poly(bPolygon.OutLine.PointList, aPolygon.OutLine.PointList[0]):
                        aPolygon.HoleIndex = bPolygon.HoleIndex + 1
                        bPolygon.AddHole(aPolygon)
                        break
        hole1Polygons = []
        for i in range(len(holePolygons)):
            if holePolygons[i].HoleIndex == 1:
                hole1Polygons.append(holePolygons[i])

        for i in range(len(polygonList)):
            aPolygon = polygonList[i]
            if aPolygon.IsBorder == True:
                for j in range(len(hole1Polygons)):
                    bPolygon = hole1Polygons[j]
                    if aPolygon.Extent.include(bPolygon.Extent):
                        if pointInPolygon_poly(aPolygon.OutLine.PointList, bPolygon.OutLine.PointList[0]):
                            aPolygon.AddHole(bPolygon)
                newPolygons.append(aPolygon)
        newPolygons.extend(holePolygons)

        return newPolygons


def addPolygonHoles_Ring(polygonList):
    """Java: addPolygonHoles_Ring(List<Polygon>) L4560-4613

    与 ``addPolygonHoles`` 同构，但"洞"的判定条件是
    ``!aPolygon.IsBorder || aPolygon.IsInnerBorder``，外环判定条件是
    ``aPolygon.IsBorder && !aPolygon.IsInnerBorder``。
    """
    holePolygons = []
    for i in range(len(polygonList)):
        aPolygon = polygonList[i]
        if not aPolygon.IsBorder or aPolygon.IsInnerBorder:
            aPolygon.HoleIndex = 1
            holePolygons.append(aPolygon)

    if not holePolygons:
        return polygonList
    else:
        newPolygons = []
        for i in range(1, len(holePolygons)):
            aPolygon = holePolygons[i]
            for j in range(i - 1, -1, -1):
                bPolygon = holePolygons[j]
                if bPolygon.Extent.include(aPolygon.Extent):
                    if pointInPolygon_poly(bPolygon.OutLine.PointList, aPolygon.OutLine.PointList[0]):
                        aPolygon.HoleIndex = bPolygon.HoleIndex + 1
                        bPolygon.AddHole(aPolygon)
                        break
        hole1Polygons = []
        for i in range(len(holePolygons)):
            if holePolygons[i].HoleIndex == 1:
                hole1Polygons.append(holePolygons[i])

        for i in range(len(polygonList)):
            aPolygon = polygonList[i]
            if aPolygon.IsBorder and not aPolygon.IsInnerBorder:
                for j in range(len(hole1Polygons)):
                    bPolygon = hole1Polygons[j]
                    if aPolygon.Extent.include(bPolygon.Extent):
                        if pointInPolygon_poly(aPolygon.OutLine.PointList, bPolygon.OutLine.PointList[0]):
                            aPolygon.AddHole(bPolygon)
                newPolygons.append(aPolygon)
        newPolygons.extend(holePolygons)

        return newPolygons


def addHoles_Ring(polygonList, holeList):
    """Java: addHoles_Ring(List<Polygon>, List<List<PointD>>) L4615-4637

    把边界（洞）点表逐个塞进能完整包含它的多边形：要求多边形的 Extent 包含该点表的
    Extent，且该点表的**每一个点**都在多边形外环内部。命中即 ``AddHole_plist``
    （Java 的 ``AddHole(List<PointD>)``，会**原地** reverse 传入的那个 list）并 break。
    """
    for i in range(len(holeList)):
        holePs = holeList[i]
        aExtent = getExtent(holePs)
        for j in range(len(polygonList) - 1, -1, -1):
            aPolygon = polygonList[j]
            if aPolygon.Extent.include(aExtent):
                isHole = True
                for aP in holePs:
                    if not pointInPolygon_poly(aPolygon.OutLine.PointList, aP):
                        isHole = False
                        break
                if isHole:
                    aPolygon.AddHole_plist(holePs)
                    break
