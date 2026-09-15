# urban_area

城市经纬度范围标点图。

双击 `city_bbox_map.html` 打开，不用装东西。三个城市的范围框和中心点画在高德底图上，
点框或圆点看四至坐标，下方表格列出中心和跨度。

底图要联网才显示；离线或 Key 失效时标点和表格照常，只是地图是白的。

## 两个文件

- `city_bbox_map.html` — 页面本体
- `wmts_map_config.js` — 高德 Key，页面会读同目录的这个文件，别分开

## 改城市

页面里的 `CITIES` 数组，一项一个城市：

```js
{ name: '珠海', bbox: [113.7944, 22.1600, 113.8119, 22.1780], color: '#2f9e44' }
```

`bbox` 顺序是 `minLng, minLat, maxLng, maxLat`（左下 → 右上）。
