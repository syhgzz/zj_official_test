# 审计报告：现在的测试程序 vs 迅腾参考算法规格

审计对象：`E:\work\zj_official_test\precipitation_xunteng`
对照依据：用户提供的 `equiSurfaceImg` 参考代码（段A `work` / 段B `finishFromGrid` / `getMapContent`）
证据脚本：`audit/audit1_idw.py`、`audit2_neighbors.py`、`audit3_zerorow.py`、`audit4_cases.py`

---

## 一、结论速览

| 链路 | 对不对 | 依据 |
|---|---|---|
| 步骤 7 等值面追踪（段B 核心） | ✅ **对，且是最硬的那种对** | 12/12 用例 × 5 阶段**按位相等** |
| 步骤 1/2/3/5/6/10 | ✅ 逐条一致 | 代码比对 + `createGridXY_Num` 实测逐点相同 |
| 步骤 4 IDW（段A 核心） | ❌ **不对，两处偏差** | 见 §三.1 |
| 步骤 8 色带映射 | ⚠️ **规则对，取值没依据** | 见 §三.2 |
| 步骤 9 渲染 | ⚠️ 几何一致，观感略有差异 | 见 §三.3 |

---

## 二、逐条对照

| 规格 | 我的实现 | 结论 |
|---|---|---|
| 步骤1 `minX==0 \|\| l<minX` 写法、按下标写 `trainData`、`vales`、`validCount`、空则抛异常 | `xunteng_reference.work()` | ✅ 逐字保留（包括 `minX==0` 这个可疑写法） |
| 步骤2 `BigDecimalUtil.add/subtract(±0.07)` | `bd_add` / `bd_subtract`（走 `Decimal`） | ✅ 语义一致 |
| 步骤3 `cellSide=1.0`、Haversine R=6378.137、`floor`、不足 2 兜底 2 | `grid_size_from_km()` | ✅ |
| 步骤4 `createGridXY_Num` = `Xlb + i*(Xrt-Xlb)/(n-1)` | `create_grid_xy_num()` | ✅ 实测 7 点逐点相同（实验 D） |
| 步骤4 `interpolation_IDW_Neighbor(...,3,-9999.0)` | `interpolation_idw_neighbor()` | ❌ **两处不同**，见 §三.1 |
| 步骤5 colorStr → TreeMap 升序 → `dataInterval` | `parse_legend_color_map()` | ✅ |
| 步骤6 `xAxis[0]`/`xAxis[末]` + `minY>maxY` 交换 | `frame_bbox()` | ✅ |
| 步骤7 `tracingBorders→tracingContourLines→smoothLines→tracingPolygons` | `wcontour/` 逐行移植 | ✅ **12/12 用例 5 阶段按位一致** |
| 步骤7 `isclip` 读行政边界裁剪、失败回退 | shapely 裁剪 + 回退 | ⚠️ 行为等价，但**接口不同**：原版 `GeoJSONUtil.loadArea` 自己取边界，我这里要显式传 `clip_wkt` |
| 步骤8 `value>=k AND value<下一个k`、末档 `>=k` | `color_for_value()` | ✅ 规则求值顺序与边界一致 |
| 步骤9 256×256、WGS84、抗锯齿 | `get_map_content()` | ⚠️ 都是 WGS84 线性映射，几何一致；抗锯齿观感与 StreamingRenderer 略有差异 |
| 步骤10 `imageOnly` → `dispose` → `WorkResult(img,...)` | `WorkResult` | ✅ |

---

## 三、三处"不对"的详细说明

### 1. 段 A 的 IDW：两处偏差（❌）

#### (a) 少了末尾的 5 点平滑

`Interpolate.java` 的 `interpolation_IDW_Neighbor(...,unDefData)` 在 IDW 之后还有一段：

```java
//---- Smooth with 5 points
double s = 0.5;
for (i = 1; i < rowNum - 1; i++) {
    for (j = 1; j < colNum - 1; j++) {
        GCoords[i][j] = GCoords[i][j] + s / 4 * (GCoords[i+1][j] + GCoords[i-1][j]
                        + GCoords[i][j+1] + GCoords[i][j-1] - 4 * GCoords[i][j]);
    }
}
```

**我的实现没有这一步。** 实测（20 站点 / 40×40 格网，同一批散点）：

| 区域 | 点数 | 不一致 | 最大差 | RMSE |
|---|---|---|---|---|
| 内部点（受平滑影响） | 1444 | **1444（100%）** | **2.1076** | **0.5282** |
| 边界点（不平滑） | 156 | 38 | 2.0871 | 0.6246 |

#### (b) 原版 IDW 会把**同一个站点重复计入**（上游 bug，我复现的是"正确"版本）

`Interpolate.java` L210-229 维护 top-N 权重的循环：

```java
for (p = 0; p < pNum; p++) {
    w = AllWeights[p];
    if (w == -1) continue;
    aMin = NW[0][0]; aP = 0;
    for (l = 1; l < points; l++) {
        if (NW[0][l] < aMin) { aMin = NW[0][l]; aP = l; }
    }
    if (w > aMin) { NW[0][aP] = w; NW[1][aP] = p; }   // <-- p 可能已经在 NW 里了
}
```

它对**已经入选的站点**也照样跑：只要 `w > 当前最小槽位`，就把该站点写进最小槽位，**但不移除它原来占的槽位** → 同一站点占两个槽位，`SV/SW` 把它算两次。

实测（20 站点 / 40×40 格网，逐格点记录 `NW` 里的站点下标）：

- 邻居槽位存在**重复站点**的格点：**482 / 1600 = 30.1%**
- 无重复但选错的格点：**0 / 1600 = 0%**（即不重复时选的就是真最近 3 个）
- 例：格点 `[0][31]` 原版选中下标 `[2, 9, 2]`，真正的最近 3 个是 `[9, 2, 18]`
- 与"真正的 top-3 权重平均"相比：**最大差 2.2241，平均差 0.2426**
- 因为平滑只作用于内部点，这也解释了上表**边界点也有 38 个不一致**

> 所以这一条要分两面看：**原版有这个 bug，我写的是干净的 top-3**。要 1:1 复现原版，得把这个重复行为也照抄。

### 2. 步骤 8：规则是对的，但 `value` 取哪个字段没有依据（⚠️）

真实帧（8.28 12:00 小时降水量，198×192 格网）的等值面多边形：

- 多边形 **17 个，全部 `LowValue == HighValue`**（17/17 = 100%）
- 面积最大的（=背景）：`area=3.9519`，`LowValue=HighValue=0.1`，`IsHighCenter=False`
- 面积最大的降水区：`area=0.4012`，`LowValue=HighValue=0.1`，`IsHighCenter=True`
  → **两者 LowValue 完全相同，只有 `IsHighCenter` 不同**

按三种取值方式，各档面积占比：

| 取值方式 | 结果 |
|---|---|
| 只用 `LowValue` | `#34E498`(0.1~1.6档) **99.5%** ＋ `#24B458`(1.6~7档) 0.5% → **整张图一片绿** |
| 只用 `HighValue` | 同上，99.5% |
| 按 `IsHighCenter` | `#FCFCFC00`(0~0.1档, 透明) **80.8%** ＋ `#34E498` 18.6% ＋ `#24B458` 0.5% → **正确** |

结论：`getFeatureCollection` 里那个 `value` 属性**必须**携带"在等值线之上还是之下"的信息
（例如 `IsHighCenter ? LowValue : 上一档`），否则平台出图会是整片绿。
**`getFeatureCollection` 没有给我，这一条我无法定论**，只能按 `IsHighCenter` 推断（默认 `BAND_MODE='auto'`），
并用 `--band-mode low|high` 复现另外两种行为。**请核对这一处。**

### 3. 步骤 9：渲染（⚠️）

GeoTools `StreamingRenderer` + `ReferencedEnvelope(WGS84)` 在本例（图层 CRS 与显示 CRS 同为 WGS84）
就是经纬度线性映射，所以几何上是等价的；差异只在抗锯齿/边缘像素。
另外做等值面裁剪时，原版靠 `GeoJSONUtil.loadArea` 自己取行政边界，我的接口要求显式传入 —— 行为等价但**调用方式不同**。

---

## 四、你算法本身的另外两个缺陷

### 缺陷 A（潜在，北京不触发）：跳过 null 会在 `trainData` 里留下 `(0,0,0)` 幽灵站点

`work()` 按下标写 `trainData[i]`，遇到 null 就 `continue` → 被跳过的行**保持 `(0,0,0)`**。
而 IDW 只过滤 `v == -9999`；`(0,0,0)` 的 `v` 是 0，**不会被过滤**，于是变成"位于 0°N 0°E、值=0"的站点。

实测影响（实验 G）：

| 场景 | 带空行 | 剔掉空行 | 绝对差 | 判定 |
|---|---|---|---|---|
| 北京 · ≥3 有效点 | 12.22399185 | 12.22399185 | 0 | 完全无影响 |
| 北京 · 2 有效点 | 12.34265745 | 12.34266055 | 3.1e-06 | 可忽略 |
| 0° 附近 · 3 有效点 | 19.99344262 | 19.99344262 | 0 | 完全无影响 |
| 0° 附近 · 2 有效点 | 19.37579618 | 19.88235294 | **0.5066** | **明显偏差 (2.55%)** |
| 0° 附近 · 1 有效点 | 18.94736842 | 20.00000000 | **1.053** | **明显偏差 (5.26%)** |

→ 北京数据安全；**数据范围一旦靠近 0° 就真会错**。

### 缺陷 B（你们自己在注释里也提到了）：`minX == 0 ||` 的包围盒写法

只要真实经度/纬度落在 0 或负值区，包围盒就会被 `0` 这个初值带偏（跨 0° 时尤其明显）。
北京（116°E / 39°N）不受影响，但这是个定时炸弹。

---

## 五、测试程序覆盖到哪里

| 步骤 | 有无真值对拍 |
|---|---|
| 7 等值面追踪 | ✅ 12/12 用例 × 5 阶段按位一致（`tools/run_parity.py`，用便携版 JDK 真编译真运行原始 Java） |
| 4 IDW | ❌ 无对拍，只有手写检查（本报告 §三.1） |
| 8 色带映射 | ❌ 无对拍 —— 因为 `getFeatureCollection` 不在手上，**没有可对拍的真值** |
| 9 渲染 | ⚠️ 只与 matplotlib `contourf` 版做了交叉比对（IoU 0.9959） |

---

## 六、建议的修复顺序

1. **先确认 §三.2 的 `getFeatureCollection`**（这是唯一会影响"平台出图对不对"的一条）
2. 要给段 A 出图 → 把 IDW 补成原版：加 5 点平滑 + 复现重复计权行为
3. 数据可能靠近 0° → 修 `trainData` 的下标写法（用 `validCount` 递增写入）和包围盒初值
4. 想扩测试覆盖 → 给 IDW 也接上 Java 真值对拍（`Interpolate.java` 可以一起编译）
