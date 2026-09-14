# precipitation_xunteng —— 讯腾降水图算法复现与截图对比

按 `equiSurfaceImg生成图片代码流程.txt`（讯腾参考算法）复现降水量图绘制：**格网 → 等值面追踪 → 按色阶区间填色 → WGS84 线性映射渲染 PNG**，用 8.28 12:00 北京的接口返回数据出图，并与讯腾平台截图对比。

## 新增：参考算法逐行移植 + 出图测试程序（本轮）

上面那版复现的等值面是用 matplotlib `contourf` **近似**的（README 末尾"已知差异"里写着）。
本轮把它换成了**对 wContour 1.6.1 的逐行移植**，并用原始 Java 编译运行做了 5 阶段按位对拍。

```bash
# 出图：接口返回 JSON -> 8.28 00:00~12:00 每帧 256x256 PNG（+1024 预览 + 索引页）
uv run python -m precipitation_xunteng.test_grid_png --layer XTSKJSXS --preview

# 按行政边界裁剪 + 多图层
uv run python -m precipitation_xunteng.test_grid_png --clip --layer XTSKJSXS XTSKPWV

# HTML 形式看结果：忠实移植版出图 -> 喂给现有对照页（地图叠加 + 时刻滑块 + 色阶图例）
uv run python -m precipitation_xunteng.export_web_reference --layers XTSKJSXS XTSKPWV
uv run python -m precipitation_xunteng.serve_web --dir precipitation_xunteng/output/web_ref
#   → http://localhost:8765/precip_compare.html

# 复现"Python 移植 == 原始 Java"的对拍（需要 JDK，见 tools/README.md）
uv run python -m precipitation_xunteng.tools.run_parity --jdk <JDK目录>
```

**两个导出器的区别**

| | `export_web.py`（原有） | `export_web_reference.py`（本轮） |
|---|---|---|
| 数据来源 | 调接口（签名联网） | **只读本地接口返回 JSON** |
| 等值面 | matplotlib `contourf` 近似 | **wContour 1.6.1 逐行移植** |
| 色带 | 按数值区间 | 按 `IsHighCenter` 定位区间 |
| 产物目录 | `output/web/` | `output/web_ref/` |

两者产出的 `precip_layers.js` 同构，所以**同一个 `precip_compare.html` 都能用**；
页面上的图例文案、顺序一律取自 `layer_config.py` 的 `legendLabels` / `legendOrder` /
`showFirstBand`（「显示 0~0.1 白色档」会切到 `*_white.png`）。
清单里带了 `engine` 字段时，页面左侧「算法」说明会自动写成
「等值面追踪：wcontour-1.6.1-port（与原始 Java 逐行等价）…」。

**本轮新增的文件**

| 新增 | 说明 |
|---|---|
| `wcontour/` | wContour 1.6.1 等值面追踪子集的**逐行移植**（32 方法 / 3225 行 Java）。出处与许可见 `wcontour/NOTICE.md`（上游 LGPL-3.0），移植规则见 `wcontour/PORTING_RULES.md` |
| `xunteng_reference.py` | 参考 Java 的 `finishFromGrid` / `work` / `workPngOnly` / `getMapContent` 1:1 实现 |
| `test_grid_png.py` | 出图测试程序：读接口返回结果 JSON，逐帧出 256×256 PNG + `report.md` + `index.html` |
| `export_web_reference.py` | 用忠实移植版出图并生成对照网页（`output/web_ref/`），喂给现有 `precip_compare.html` |
| `tools/` | 对拍工具：编译原始 Java 导出 5 个阶段的真值，与 Python 移植逐字段比对 |
| `output/xunteng_png/` | 出图产物（`XTSKJSXS_2026-08-28_HHMM.png` / `_preview1024.png` / `report.md` / `index.html`） |

**验证结果（都不是"看起来对"）**

1. **与原始 Java 按位一致**：`tools/run_parity.py` 真编译真运行 wContour，把
   `S1` / `borders` / `contourLines` / `smoothLines` / `polygons` 五个阶段全部导出 JSON，
   12 个用例（9 合成 + 3 真实帧，含 198×192 的实际格网）**全部阶段逐点按位相等**。
2. **与旧的 contourf 版交叉比对**：同一帧两条独立实现，填色覆盖掩膜 **IoU = 0.9959**，
   共同填色像素里 **99.80% 的 RGB 完全相同**（差异来自抗锯齿边缘与平滑细节，
   与 README 末尾列的"已知差异"一致）。

**过程中发现的一个真问题（会影响出图对不对）**

`addShapeLayer` 里那条 `value >= key AND value < next` 的 ECQL 规则，
**不能直接拿 `polygon.LowValue` 当 `value`**：wContour 输出的多边形 `LowValue` 恒等于
`HighValue`，真正区分"这块区域在等值线之上还是之下"的是 `IsHighCenter`。实测 8.28 12:00
小时降水量的 17 个多边形里，覆盖全域的那个"背景多边形"是
`LowValue=HighValue=0.1, IsHighCenter=False`（带 12 个洞），而 12 块降水区是
`LowValue=HighValue=0.1, IsHighCenter=True` —— **两者 LowValue 一模一样，只有 `IsHighCenter` 不同**。
若只用 LowValue，背景会被错填成第二档（0.1~1.6 的绿色），整张图变成一片绿。

所以色带按 `IsHighCenter` 选：`True` → `[LowValue, 下一档)`，`False` → `[上一档, LowValue)`。
这是默认行为（`BAND_MODE='auto'`）。**如果你的 `getFeatureCollection` 确实只是
`featureBuilder.add(polygon.LowValue)`，请用 `--band-mode low` 复现你自己的行为**，
并确认平台出图是否也偏色 —— 这个点值得回头核一下原代码。


## 事实基线（实测）

1. 接口路径 `/api/v1/precipitation/layers`（无 `upns`）在本服务器返回 **500**（No static resource）；真实接口是 **`/api/v1/upns/precipitation/layers`**。参数：`layer, startTime, endTime, minLng, maxLng, minLat, maxLat`（毫秒时间戳，签名认证见 `lib/`）。
2. 接口返回的是**已插值格网**（`data.cols/rows/bbox` + `rowsList[{dataTime, currentRow, gridLocations, gridValues}]`）+ **行政边界裁剪多边形**（`data.groups[].area`，即 isclip 语义），最高约 30MB/层。
3. 图层数据（北京 2026-08-28 00:00~12:00）：
   - `XTSKJSXS` 小时降水量：13 帧（含 12:00）✓
   - `XTSKPWV` 大气可降水量(10分钟)：16 帧（含 12:00）✓
   - `XTSKPWV1H` 大气可降水量(小时)：**任何时间窗均 0 帧**（8-27~8-29、11:00~13:00 已实测）→ 参考截图"大气可降水量(小时)"无法用本接口数据复现，以 `XTSKPWV` 出图对照
   - `XTSKQW / XTSKSD / XTSKQY`（气温/湿度/气压）也有数据，可直接出图（色阶为按截图图例近似，见 `layer_config.py`）
4. 接口不返回色阶（也没有 legend 类接口，已实测 `/api/v1/upns/legend`、`/layers/legend`、`/colorScale` 等均为 500）；色阶在 `layer_config.py` 里配置。
   - `XTSKPWV` 大气可降水量：按截图图例 **20~75 每 5 一档（12 档）**，紫蓝→蓝→青→绿→黄→橙→红；页面图例按数值 75→20 从高到低排列，与平台一致。
   - 若拿到平台图例的精确色值，直接改 `layer_config.py` 里该层的 `colorStr` 即可。
5. **裁边开关**：`layer_config.py` 每层有 `clip`（默认 `False` = 不裁边），不裁边时色块铺满整个数据范围（与截图一致）；设为 `True` 则按平台返回的行政边界（`groups[].area`）裁剪等值面。
6. 出图是纯色块（无底图），参考截图带高德底图——对比以色块形状/颜色分布为准。

## 快速开始

```bash
# 1) 命令行出图 + 与截图并排对比（截图放 references/）
uv run python -m precipitation_xunteng.run_compare --no-fetch

# 2) 网页对比版：左地图（迅腾算法出图） + 右参考截图
uv run python -m precipitation_xunteng.export_web --no-fetch
uv run python -m precipitation_xunteng.serve_web      # http://localhost:8765/precip_compare.html

# 3) 算法参数（txt 全链路）与范围
uv run python -m precipitation_xunteng.export_web --no-fetch --k 3 --power 2 --cell-km 1 --pad 0.07
#    站点无历史值的要素（如小时降水量）默认走接口格网；想改用它做散点抽查：
uv run python -m precipitation_xunteng.export_web --no-fetch --platform-fallback

# 4) 只拉取原始数据并缓存
uv run python -m precipitation_xunteng.fetch_layers
```

参考截图放 `precipitation_xunteng/references/`（文件名含关键字即可自动匹配：`PWV`/`可降水`、`小时降水量`、`气温`、`湿度`、`气压`）。

## 网页对比页 `precip_compare.html`

打开：`http://localhost:8765/precip_compare.html`

两个来源，可随时切换（都是你给的那套 txt 代码：一个走段A+段B，一个只走段B）：

| 图层源 | 走法 | 覆盖范围 | 出图引擎 |
|---|---|---|---|
| **复刻迅腾算法**（默认） | txt **段A + 段B**：站点散点 → 包围盒外扩 0.07° → 1km 格网 → IDW(3 近邻) → 等值面填色 → PNG | 站点包围盒 ±0.07°（北京站点约 `115.764~116.883, 39.568~40.473`） | wContour 1.6.1 逐行移植 |
| **接口格网** | txt **段B**：接口返回的服务端场（格网）→ 等值面填色 → PNG | 接口格网范围（`115.322~117.618, 39.375~41.096`） | 同上 |

> 两个来源都由 `export_web_reference.py`（忠实移植版）产出，落在 `output/web_ref/`；
> 页面信息区会显示 `等值面引擎：wcontour-1.6.1-port（色带 auto）`。

**当前对外地址**

| URL | 产物目录 | 引擎 |
|---|---|---|
| `http://localhost:8765/precip_compare.html` | `output/web_ref/` | **wContour 逐行移植**（忠实复刻） |
| `http://localhost:8766/web_ref/precip_compare.html` | 同上 | 同上 |
| `http://localhost:8766/web/precip_compare.html` | `output/web/` | matplotlib contourf 近似版 |

**① 左侧「讯腾降水图 · 对照控制台」**

| 区域 | 内容 |
|---|---|
| 状态行 | 彩色圆点 + 文案（就绪 / 本时刻无散点、复刻算法不可用 / JS 错误） |
| 信息区 | 图层、时刻、**算法（当前图层源）**、地图范围 bbox、算法参数与引擎、叠加图文件名、参考截图 |
| 图层与时刻 | 要素图层下拉 + 时刻滑块（该层全部时刻） |
| **图层源** | 两个按钮切换：**复刻迅腾算法** / **接口格网**（切换时自动缩放到对应范围） |
| 底图与透明度 | 高德 / 天地图 / WMTS 开关 + 四个透明度滑块 + 「显示 0~0.1 白色档」开关 |
| 操作 | 重新加载（重绘并缩放至图层范围）、打开叠加图 |
| 色阶图例 | 按平台图例原色与顺序（PWV 高→低、降水量 低→高） |

**小时降水量为什么「复刻迅腾算法」不可用**：该要素没有站点历史值（`rain` 全 null），拿不到散点，自然跑不了段A；切到「接口格网」即正常出图。
也可用 `export_web.py --platform-fallback` 让接口格网在站点位置抽样当散点（近似验证链路）。

**② 右侧「参考截图」**

| 区域 | 内容 |
|---|---|
| 已匹配 | `references/` 自动匹配到的截图下拉 |
| 按钮 | 本地选择…（直接挑本机任意截图）、新窗口打开 |
| 图片 | 参考截图预览 |
| 静态并排对比图 | `run_compare` 生成的"左截图 / 右算法图"缩略图，点击可放大对照 |

URL 直达：`precip_compare.html?layer=XTSKPWV&time=12:00`。

**图层覆盖范围**：有散点时按 txt 算法定义域 = 站点包围盒 ±0.07°（北京站点约 `115.764~116.883, 39.568~40.473`）；无散点走接口格网时 = 接口给的格网范围（`115.322~117.618, 39.375~41.096`）。

**站点散点来源**：优先取 `/api/v1/upns/stations/{code}/history` 的该时刻实测值；若该要素没有站点历史（实测 `rain` 全为 null），该帧自动改走接口格网（页面状态栏会提示）；也可加 `--platform-fallback`，用接口格网在站点位置抽样当散点，强行走"散点→IDW"链路（页面会标注输入来源）。

**为什么必须用 HTTP 打开**：① 高德 `ImageLayer` 叠加本地 PNG 在 `file://` 下不渲染；② WMTS Capabilities 需要跨源 fetch；③ 高德 Key 白名单按域名生效，实测 `http://localhost:8765` 可出底图，`http://127.0.0.1:8765` 不出（白名单未含 IP），所以用 `localhost` 访问。

**WMTS 现状**：`114.255.16.109:7010/sj_raster/...` 的 ak 当前返回 `$ERROR_NO_RIGHT`（`Access key auth fail`），与 `wmts_demo` 受限情况一致，页面按钮显示「WMTS：不可用」，不影响高德/天地图与叠加图层。

## 目录

| 文件 | 说明 |
|---|---|
| `wcontour/` | **（本轮新增）** wContour 1.6.1 等值面追踪子集的逐行移植：`global_types` 数据类、`helpers` 工具、`borders` 边界、`contour_lines` 等值线、`smoothing` B 样条、`polygons` / `polygons_trace` 多边形装配。`_upstream/` 是随包携带的原始 Java 源码，`NOTICE.md` 记许可（LGPL-3.0）与移植范围 |
| `xunteng_reference.py` | **（本轮新增）** 参考 Java `finishFromGrid` / `work` / `workPngOnly` / `getMapContent` 的 1:1 实现（段 A 散点+IDW、段 B 格网+等值面两条入口都在） |
| `test_grid_png.py` | 出图测试程序：读接口返回结果 JSON，逐帧出 256×256 PNG + `report.md` + `index.html` |
| `export_web_reference.py` | **（本轮新增）** 用忠实移植版出图并生成对照网页（`output/web_ref/`）：读本地 JSON、不联网、不调 API，产物与现有 `precip_compare.html` 同构 |
| `tools/` | **（本轮新增）** 与原始 Java 的对拍工具（编译上游源码导出真值 + 逐阶段比对），见 `tools/README.md` |
| `layer_config.py` | 图层配置：编码/名称/单位/colorStr 色阶/参考图匹配关键字 |
| `eqs_algorithm.py` | 算法核心（与 txt 步骤 1:1 对照：格网解析、等值面填色、渲染、色阶解析） |
| `fetch_layers.py` | 调接口并缓存原始 json 到 `data/raw/` |
| `run_compare.py` | 命令行出图 + 与参考截图并排对比 + `report.md` / `compare_index.html` |
| `export_web.py` | 导出网页版：各时刻出图 + `precip_layers.js` 清单 + 参考截图副本 |
| `serve_web.py` | 本地 HTTP 服务，浏览 `output/web/precip_compare.html` |
| `web/precip_compare.html` | 对比页模板（高德 + 天地图 + WMTS + 讯腾出图 + 参考截图面板） |
| `references/` | 讯腾平台参考截图（用户放置） |
| `output/` | 出图 PNG（256×256/4x 预览）、`report.md`、`compare_index.html` |
| `output/web/` | 网页版：`precip_compare.html`、`layers/*.png`、`refs/`、`precip_layers.js` |
| `data/raw/` | 接口原始响应缓存 |
| `algo_compare.py` | （可选，已停用）早前的"我的实验算法 vs 讯腾"对比模块，保留备查 |

## txt 算法步骤 ↔ 本程序映射

| txt 步骤 | 本程序 |
|---|---|
| 1 散点解析/包围盒 | `parse_scatter_stations` / `expand_bbox`（algo_compare 备用） |
| 2 外扩 0.07° | `expand_bbox` |
| 3 1km 格距算 cols/rows | `grid_size_from_km`（Haversine, R=6378.137） |
| 4 createGridXY + IDW(3, -9999) | `create_grid_xy` / `idw_neighbor`（平台接口已给格网，故主流程跳过该段） |
| 5 色阶解析 | `parse_color_str` |
| 6 坐标轴→bbox | `frame_bbox` |
| 7 等值面追踪 | **（现用）** `wcontour.polygons.tracingPolygons` —— 与 GeoTools/wContour 逐行等价；旧的 matplotlib `contourf` 近似保留在 `render_equi_surface` 里做交叉比对 |
| 8 区间填色规则 | **（现用）** `xunteng_reference.color_for_polygon`：按 `IsHighCenter` 定位 `[k, k2)` 色带，比最低档还低/比最高档还高则不填色；`contourf(extend='max')` 版保留 |
| 9 渲染 256×256 PNG | **（现用）** `xunteng_reference.get_map_content`（WGS84 线性映射，透明底，无坐标轴，抗锯齿）；预览图按 `--preview` 输出 1024 |

## 已知差异（非"对不上"项）

> 前两条只适用于 `wcontour/` 移植版**之外**的那条 `contourf` 近似链路；
> `xunteng_reference.py` 走的是逐行移植，等值面追踪已与原始 Java 按位一致（见 `tools/`）。

- （仅 contourf 版）等值线平滑（smoothLines）细节与 GeoTools 不完全一致，色块边界可能轻微差异。
- （仅 contourf 版）contourf 断点区间与 ECQL `>= / <` 仅在"值恰好等于断点"的像素边界处有差别。
- matplotlib 抗锯齿与 StreamingRenderer 渲染观感略有不同（多边形几何已一致）。
- 参考截图带底图、算法图无底图。
- 接口的"小时档"PWV（`XTSKPWV1H`）无数据，只能用 10 分钟档对照。
- `wcontour` 是 LGPL-3.0 的衍生移植，分发时需保留上游版权与许可（见 `wcontour/NOTICE.md`）。
