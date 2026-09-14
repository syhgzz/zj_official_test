# NOTICE —— 第三方代码出处与许可

## wContour 的 Python 移植（本目录下的 `*.py`）

`global_types.py` / `helpers.py` / `smoothing.py` / `borders.py` / `contour_lines.py` /
`polygons.py` / `polygons_trace.py` 是 **wContour 1.6.1** 部分方法的逐行移植（derivative work），
不是独立实现。

| 项 | 内容 |
|---|---|
| 上游项目 | [meteoinfo/wContour](https://github.com/meteoinfo/wContour) |
| 作者 | Yaqiang Wang (王亚强), yaqiang.wang@gmail.com |
| 版本 | 1.6.1（`Contour.getVersion()` 返回 `1.6.1R1`） |
| 原始文件 | `src/main/java/wcontour/Contour.java`（8087 行）与 `src/main/java/wcontour/global/*.java` |
| 许可 | **LGPL-3.0**（见 `_upstream/LICENSE.md`） |
| 原始源码副本 | `_upstream/`（随包携带，便于逐行核对；与上游 master 一致） |

由于上游是 LGPL-3.0，**本目录下这些移植文件同样是 LGPL-3.0**，
在分发时需要一并遵守 LGPL-3.0 的条款（保留版权声明与许可文本）。

### 移植范围

只移植了迅腾 `equiSurfaceImg` 参考代码实际用到的调用闭包（32 个方法，约 3225 行 Java）：

```
tracingBorders → tracingContourLines(=createContourLines_UndefData)
    → isoline_UndefData → traceIsoline_UndefData
    → traceBorder
→ smoothLines → BSplineScanning/BSpline/f0..f3/fb
→ tracingPolygons → tracingPolygons(hasBorder) → judgePolygonHighCenter
    → tracingPolygons_Ring → addPolygonHoles / addPolygonHoles_Ring / addHoles_Ring
    → 以及 pointInPolygon / isClockwise / getExtent / getExtentAndArea /
       insertPoint2Border / insertPoint2Border_Ring / doubleEquals 等辅助方法
```

**没有移植**（不在参考链路上）：IDW 插值的 KDTree 版实现、streamline 系列、
`cutPolygon*` / `clipPolygon*` / `tracingClipPolygons` 裁剪系列、
`tracingPolygons(LineList, BorderPoint, Extent, double[])`、
`isoline_Bottom/Left/Top/Right/Close`、`traceIsoline` 及 `*_bak` 备份方法。

### 移植约定

见 `PORTING_RULES.md`。核心是：**保留 Java 的变量名、循环边界、语句顺序与引用/别名语义**，
不"修正"上游看起来可疑的写法；只有 Python 确实做不到的才等价改写
（例如 `List.get(-1)` 在 Java 抛异常、Python 会回绕，这类退化输入已在各处注明）。

### 与上游的已知等价改写

| 位置 | Java | Python | 原因 |
|---|---|---|---|
| `smoothing.BSplineScanning` | `float t; t += 0.05F` | `_f32(t + _F005)` | 显式模拟 float32 累加，否则与 Java 差 ~1e-9 |
| `borders.tracingBorders` | `for (…; j < list.size(); …)` 且循环体内 `remove` | `while j < len(list)` | Java 每轮重求 `size()`，`range()` 只求一次 |
| `helpers.idiv` / `imod` | `int / int`、`int % int` | 显式实现向零截断 | Python `//` `%` 是向下取整 |

正确性由 `tools/run_parity.py` 对拍保证：编译上游 Java 真跑一遍，5 个阶段全部按位一致。
