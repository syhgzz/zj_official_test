# -*- coding: utf-8 -*-
"""
wcontour.global_types —— wContour 1.6.1 `wcontour.global` 包的数据类 1:1 Python 移植。

移植原则
========
字段名、字段顺序、默认值、以及**对象共享语义**都与 Java 原版逐字对应：

* Java 未初始化的 `double` 字段 = ``0.0``，`int` = ``0``，`boolean` = ``False``。
* `new ArrayList<>()` → 每个实例一个独立 ``list``（在 ``__init__`` 里创建，绝不用类属性）。
* 引用语义必须保留：Java 里 ``a = b`` 共享同一个对象，Python 里也必须共享。
  典型例子：``Polygon.OutLine`` 与 ``BorderLine.pointList`` 会被多处共享，
  ``add_hole_plist`` 会**原地** ``reverse()`` 调用方传进来的那个 list。

上游来源
========
meteoinfo/wContour, src/main/java/wcontour/global/*.java (LGPL-3.0)。
原始 Java 源码随包放在 ``wcontour/_upstream/``，便于逐行核对。
"""


class PointD(object):
    """wcontour.global.PointD"""

    __slots__ = ('X', 'Y')

    def __init__(self, x=0.0, y=0.0):
        self.X = x
        self.Y = y

    def __repr__(self):
        return 'PointD(%r, %r)' % (self.X, self.Y)


class PointF(object):
    """wcontour.global.PointF（字段是 Java float）"""

    __slots__ = ('X', 'Y')

    def __init__(self, x=0.0, y=0.0):
        self.X = x
        self.Y = y


class IJPoint(object):
    """wcontour.global.IJPoint"""

    __slots__ = ('I', 'J')

    def __init__(self, i=0, j=0):
        self.I = i
        self.J = j


class Extent(object):
    """wcontour.global.Extent —— 无参构造不设值，四个字段默认 0.0。"""

    __slots__ = ('xMin', 'yMin', 'xMax', 'yMax')

    def __init__(self, min_x=0.0, max_x=0.0, min_y=0.0, max_y=0.0):
        self.xMin = min_x
        self.yMin = min_y
        self.xMax = max_x
        self.yMax = max_y

    def include(self, b_extent):
        """Java: Include(Extent)"""
        return (self.xMin <= b_extent.xMin and self.xMax >= b_extent.xMax
                and self.yMin <= b_extent.yMin and self.yMax >= b_extent.yMax)


class Line(object):
    """wcontour.global.Line"""

    __slots__ = ('P1', 'P2')

    def __init__(self, p1=None, p2=None):
        self.P1 = p1
        self.P2 = p2


class BorderLine(object):
    """wcontour.global.BorderLine"""

    __slots__ = ('area', 'extent', 'isOutLine', 'isClockwise', 'pointList', 'ijPointList')

    def __init__(self):
        self.area = 0.0
        self.extent = Extent()
        self.isOutLine = False
        self.isClockwise = False
        self.pointList = []
        self.ijPointList = []


class BorderPoint(object):
    """wcontour.global.BorderPoint"""

    __slots__ = ('Id', 'BorderIdx', 'BInnerIdx', 'Point', 'Value')

    def __init__(self):
        self.Id = 0
        self.BorderIdx = 0
        self.BInnerIdx = 0
        self.Point = PointD()
        self.Value = 0.0


class Border(object):
    """wcontour.global.Border"""

    __slots__ = ('LineList',)

    def __init__(self):
        self.LineList = []

    def getLineNum(self):
        return len(self.LineList)


class EndPoint(object):
    """wcontour.global.EndPoint"""

    __slots__ = ('sPoint', 'Point', 'Index', 'BorderIdx')

    def __init__(self):
        self.sPoint = PointD()
        self.Point = PointD()
        self.Index = 0
        self.BorderIdx = 0


class PolyLine(object):
    """wcontour.global.PolyLine"""

    __slots__ = ('Value', 'Type', 'BorderIdx', 'PointList')

    def __init__(self):
        self.Value = 0.0
        self.Type = None
        self.BorderIdx = 0
        self.PointList = []


class Polygon(object):
    """wcontour.global.Polygon"""

    __slots__ = ('IsBorder', 'IsInnerBorder', 'LowValue', 'HighValue', 'IsClockWise',
                 'StartPointIdx', 'IsHighCenter', 'Extent', 'Area', 'OutLine',
                 'HoleLines', 'HoleIndex')

    def __init__(self):
        self.IsBorder = False
        self.IsInnerBorder = False
        self.LowValue = 0.0
        self.HighValue = 0.0
        self.IsClockWise = False
        self.StartPointIdx = 0
        self.IsHighCenter = False
        self.Extent = Extent()
        self.Area = 0.0
        self.OutLine = PolyLine()
        self.HoleLines = []
        self.HoleIndex = 0

    def Clone(self):
        """Java: Clone() —— 注意 Extent 与 OutLine 是**共享**引用，不是深拷贝。"""
        p = Polygon()
        p.IsBorder = self.IsBorder
        p.LowValue = self.LowValue
        p.HighValue = self.HighValue
        p.IsClockWise = self.IsClockWise
        p.StartPointIdx = self.StartPointIdx
        p.IsHighCenter = self.IsHighCenter
        p.Extent = self.Extent
        p.Area = self.Area
        p.OutLine = self.OutLine
        p.HoleLines = list(self.HoleLines)
        p.HoleIndex = self.HoleIndex
        return p

    def HasHoles(self):
        return len(self.HoleLines) > 0

    def AddHole(self, a_polygon):
        """Java: AddHole(Polygon) —— 把另一个多边形的外环当成自己的洞（共享 PolyLine）。"""
        self.HoleLines.append(a_polygon.OutLine)

    def AddHole_plist(self, p_list):
        """Java: AddHole(List<PointD>) —— **原地** reverse 调用方的 list。"""
        from .helpers import isClockwise
        if isClockwise(p_list):
            p_list.reverse()

        a_line = PolyLine()
        a_line.PointList = p_list
        self.HoleLines.append(a_line)


class LPolygon(object):
    """wcontour.global.LPolygon"""

    __slots__ = ('value', 'isFirst', 'pointList')

    def __init__(self):
        self.value = 0.0
        self.isFirst = False
        self.pointList = None
