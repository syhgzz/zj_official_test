# wContour 1.6.1 → Python 逐行移植规则（强制）

目标：**行为等价**，不是"重写得更漂亮"。任何"顺手优化"都算 bug。

上游源码（唯一权威）：`wcontour/_upstream/Contour.java`（以及 `_upstream/global/*.java`）。
这是 meteoinfo/wContour 1.6.1 的原始 Java 源码副本，与上游 master 一致（LGPL-3.0）。

## 铁律

1. **不许改算法**。不要"修正"看着别扭的地方：死代码、无用变量、可疑的边界、奇怪的
   索引偏移、重复赋值的 `aValue`，一律照抄。Java 里怎么写的，Python 就怎么写。
2. **保留 Java 的变量名、循环变量名、循环边界、语句顺序**。方法名保留 Java 的
   `camelCase`（如 `tracingBorders`），不要改成 snake_case。
3. **保留引用/别名语义**。`a = b` 表示共享同一对象，绝不能顺手 `.copy()`。
   `Collections.reverse(x)` → `x.reverse()`（原地，同一个 list 对象）。
   `new ArrayList<>(x)` → `list(x)`（浅拷贝，新对象）。
4. Java 的 `double[][] S0` → Python `list[list[float]]`，下标 `S0[i][j]`，
   **i 是行(Y)索引，j 是列(X)索引**，不要转置。
5. `java.util.List` 的方法对应关系：

   | Java | Python |
   |---|---|
   | `a.size()` | `len(a)` |
   | `a.get(i)` | `a[i]` |
   | `a.set(i, v)` | `a[i] = v` |
   | `a.add(v)` | `a.append(v)` |
   | `a.add(i, v)` | `a.insert(i, v)` |
   | `a.remove(0)` | `a.pop(0)` |
   | `a.remove(obj)` | `a.remove(obj)`（按值删第一个） |
   | `a.isEmpty()` | `not a` |
   | `a.clear()` | `a.clear()` |
   | `a.contains(v)` | `v in a` |
   | `Collections.reverse(a)` | `a.reverse()` |
   | `new ArrayList<>(a)` | `list(a)` |
   | `Strings.equals(s)` | `== s`（字符串用 `==`） |

6. 整数除法：Java `int/int` **向零截断**，Python `//` 是向下取整。
   - 能证明操作数非负时用 `//`；
   - 否则用 `helpers.idiv(a, b)`（等价 Java 语义）。
   取模同理用 `helpers.imod(a, b)`（Java `%` 取被除数符号）。
   `(int) someDouble` → `int(some_double)`（Python 对 float 的 `int()` 同样是向零截断，
   与 Java 一致）。
7. 数值类型：Java `double` → Python `float`。注意 Java 里 `1/2` 若两个操作数都是 int
   结果是 `0`；若有一个是 double 才是 `0.5`。照抄类型语义。
8. `null` → `None`；`true/false` → `True/False`。
9. 数组：`double[] X = new double[n]` → `X = [0.0] * n`；
   `int[][] S1 = new int[m][n]` 由调用方传入（会**原地改写**）。
10. `Math.floor/abs/sqrt/max/min/pow` → `math.floor` / `builtins.abs` / `math.sqrt` /
    `max` / `min` / `math.pow`（能确定非负时也可 `**`）。
11. 对象字段用 `wcontour/global_types.py` 里已经定义好的类，**不要新建类**，
    也不要给类加字段。若确实缺字段，停下来在返回结果里说明，不要自己加。
12. 每个函数都要有 docstring，第一行写清楚对应的 Java 方法名，并标注 Java 源码行号区间，
    例如：`"""Java: tracingBorders(...) L66-412"""`。行号区间仅供参考，**以实际源码为准**：
    请自己打开 Java 文件，从方法签名读到配对的大括号结束，不要只看行号截断。

## 文件与模块划分（不要跨文件调用未约定的函数）

```
wcontour/
  global_types.py    数据类（已完成，只读）
  helpers.py         idiv, imod, doubleEquals, getExtent, getExtentAndArea,
                     isClockwise, pointInPolygon(2 个重载), insertPoint2Border,
                     insertPoint2Border_Ring
  smoothing.py       smoothLines, BSplineScanning, BSpline, f0, f1, f2, f3, fb
  borders.py         tracingBorders, traceBorder
  contour_lines.py   tracingContourLines, createContourLines_UndefData,
                     traceIsoline_UndefData, isoline_UndefData
  polygons_trace.py  tracingPolygons_hasborder, judgePolygonHighCenter
                     （注意：`tracingPolygons(LineList, borderList, bBound, contour)`
                      L3046-3479 只被 createContourPolygons / createCutContourPolygons
                     调用，不在迅腾 finishFromGrid 链路上，**不要移植**）
  polygons.py        tracingPolygons(S0, cLineList, borderList, contour),
                     tracingPolygons_Ring, addPolygonHoles, addPolygonHoles_Ring,
                     addHoles_Ring
```

依赖方向（**禁止反向 import，禁止循环 import**）：

```
global_types ← helpers ← borders ← contour_lines
                       ← polygons_trace ← polygons
                       ← smoothing
```

Java 里同名重载在 Python 里**不能重名**，按下表命名（一定要用这些名字，其它模块会按这个调）：

- `pointInPolygon(List<PointD>, PointD)` → `pointInPolygon_poly`
- `pointInPolygon(Polygon, PointD)` → `pointInPolygon_polygon`
- `tracingPolygons(LineList, borderList, hasBorder)` → `tracingPolygons_hasborder`
- 公开入口保持原样：`tracingBorders` / `tracingContourLines` / `smoothLines` /
  `tracingPolygons` / `tracingPolygons_Ring` / `addPolygonHoles` / `addPolygonHoles_Ring` /
  `addHoles_Ring` / `judgePolygonHighCenter`

## 完成前自检

1. `python -m py_compile <你写的文件>` 通过。
2. 用项目 venv 导入一下：`E:\work\zj_official_test\.venv\Scripts\python.exe -c "import ..."`。
3. 抽查 2~3 个方法，逐行对照 Java，确认没有漏语句、没有把 `i/j` 写反。
4. 在返回值里报告：你实现了哪些函数、各自对应 Java 行号、以及任何你不确定/存疑的地方。
