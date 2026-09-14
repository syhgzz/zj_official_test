# 参考截图目录

把讯腾平台截图放到本目录，文件名含关键字即可被 `export_web.py` / `run_compare.py` 自动匹配：

| 图层 | 关键字 |
|---|---|
| XTSKPWV 大气可降水量 | 可降水 / PWV / pwv / pvw |
| XTSKJSXS 小时降水量 | 小时降水 / 降水量(小时) / jsxs |
| XTSKQW 气温 | 气温 / 温度 / QW |
| XTSKSD 湿度 | 湿度 / SD |
| XTSKQY 气压 | 气压 / QY |

放好后运行：

```bash
uv run python -m precipitation_xunteng.export_web --no-fetch   # 页面右侧出现参考图
uv run python -m precipitation_xunteng.run_compare --no-fetch  # 生成静态并排对比图
```
