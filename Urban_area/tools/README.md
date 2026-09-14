# tools —— 「Python 移植 vs 原始 Java」对拍工具

这个目录的存在意义只有一个：**证明 `precipitation_xunteng/wcontour/` 里那套等值面追踪
与原始 Java（wContour 1.6.1）行为一致**，而不是"看起来差不多"。

做法是把上游 Java 源码**真编译真运行**，把它每个阶段的结果导出成 JSON，再让 Python 移植
跑同样的输入，逐阶段、逐字段、逐点比对。浮点要求**按位相等**。

## 一键复现

```bash
uv run python -m precipitation_xunteng.tools.run_parity --jdk <JDK目录>
```

没装 JDK 的话，下一个便携版解压即可（不改系统 PATH）：

```
https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse
```

退出码 0 = 全部用例、全部阶段一致。

## 它到底比了什么

`WContourDriver.java` 调用的就是参考代码用的那四个入口：

```java
int[][] S1 = new int[m][n];
List<Border>   borders = Contour.tracingBorders(S0, X, Y, S1, undefData);
List<PolyLine> cLines  = Contour.tracingContourLines(S0, X, Y, nc, contour, undefData, borders, S1);
List<PolyLine> sLines  = Contour.smoothLines(cLines);
List<Polygon>  polys   = Contour.tracingPolygons(S0, sLines, borders, contour);
```

导出 **5 个阶段**，所以出问题时能定位到具体哪一层，而不是只看到"最后的图不一样"：

| 阶段 | 内容 |
|---|---|
| `S1` | `tracingBorders` 写回的标记矩阵（0 缺测 / 1 边界 / 2 内部） |
| `borders` | 每条 `BorderLine` 的点表、ij 索引表、`area`、`extent`、`isOutLine`、`isClockwise` |
| `contourLines` | 平滑**前**的等值线（`value` / `type` / `borderIdx` / 点表） |
| `smoothLines` | `smoothLines` 之后的等值线 |
| `polygons` | 最终多边形全字段 + 外环 + 每个洞的点表 |

> `smoothLines` 会**就地改写** `PointList`，所以驱动里在调用前先做了快照。

## 用例（`gen_cases.py`）

9 个合成算例专门去踩各条分支：

| 用例 | 考的是什么 |
|---|---|
| `case01_plane_5x5` | 最小规模、无缺测 |
| `case02_radial_40x40` | 闭合等值线、无缺测 |
| `case03_undef_hole` | 中间一个缺测方块 |
| `case04_undef_ring` | 缺测压在峰值上（走 `tracingPolygons_Ring`） |
| `case05_two_hills_undef` | 双中心 + 3 块缺测 |
| `case06_undef_band` | 缺测带把区域切成两半（多个 Border） |
| `case07_constant` | 常量场，大量值与等值线重合 |
| `case08_exact_levels` | 值**恰好等于**等值线（最容易暴露 `>=`/`<` 边界） |
| `case09_undef_ring_frame` | 环形有效区 + 上下缺测边 |

3 个真实用例取自接口数据：8.28 12:00 的 `XTSKJSXS`（原始 / 按行政边界裁剪后）与 `XTSKPWV`。

## 结果

```
12/12 用例 5 个阶段全部按位一致
```

包括 198×192 的真实格网：边界 1 个、等值线 16~27 条、多边形 17~28 个，
点表最长 6952 点，全部逐点相同。

## 过程中真正抓到的问题（说明这个对拍不是走过场）

1. **Java `float` 精度**：`BSplineScanning` 里 `float t; for (t = 0; t <= 1; t += 0.05F)`
   是**单精度**累加，Python 用 double 写会差 ~1e-9。已用 `struct` 显式做 float32 舍入
   （`wcontour/smoothing.py` 的 `_f32`）。
2. **`tracingPolygons(LineList, borderList, Extent, double[])` 不用移植**：
   调用图分析（`analyze_contour_closure.py`）显示它只被 `createContourPolygons` /
   `createCutContourPolygons` 调用，不在参考链路上，省掉 434 行。
3. **`judgePolygonHighCenter` 其实是 4 个形参**（多了 `borderList`，在函数体内被真正使用），
   任务书里写的 3 个是错的。

## 文件

| 文件 | 说明 |
|---|---|
| `run_parity.py` | 编排：找 JDK → 编译 → 生成用例 → 跑真值 → 比对 |
| `WContourDriver.java` | 调 wContour 四个入口并把 5 个阶段导出成 JSON |
| `gen_cases.py` | 合成 + 真实用例生成（纯 token 文本格式） |
| `compare.py` | 逐阶段比对（可单独跑：`python compare.py case10_real_xtskjsxs_1200`） |
| `analyze_contour_closure.py` | 从入口方法算调用闭包，用来确定"到底要移植哪些方法" |
| `_parity_run/` | 运行产物：`cases/` 用例、`truth/` Java 真值、`src/` `classes/` 编译中间件 |
