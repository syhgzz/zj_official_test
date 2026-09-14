# -*- coding: utf-8 -*-
"""定位不配平：输出每个函数的括号净增量，找出在哪一段开始跑偏。"""
import re

TPL = r'E:\work\zj_official_test\testmap\map_view_template.html'
js = re.findall(r'<script>(.*?)</script>', open(TPL, encoding='utf-8').read(), re.S)[-1]

# 逐行统计（粗算，够用来定位；字符串/注释里的括号会算进来，所以只看趋势）
depth_b = depth_p = 0
rows = []
for ln, line in enumerate(js.split('\n'), 1):
    code = re.sub(r'//.*', '', line)
    db = code.count('{') - code.count('}')
    dp = code.count('(') - code.count(')')
    depth_b += db
    depth_p += dp
    rows.append((ln, db, dp, depth_b, depth_p, line.strip()[:70]))

print('行    {净  (净  {累计  (累计   代码')
for r in rows:
    if r[5].startswith('function ') or r[5].startswith('/* ---') or r[5].startswith('var f0'):
        print('%4d  %+2d  %+2d   %3d    %3d   %s' % r)

print('\n最大 { 累计:', max(r[3] for r in rows), ' 最终 { 累计:', rows[-1][3])
print('最大 ( 累计:', max(r[4] for r in rows), ' 最终 ( 累计:', rows[-1][4])

# 最后一行 { 累计回到 0 的位置 -> 之后就是没闭合的那一段
zero = [r[0] for r in rows if r[3] == 0]
print('\n{ 累计为 0 的最后几行:', zero[-5:])
zero_p = [r[0] for r in rows if r[4] == 0]
print('( 累计为 0 的最后几行:', zero_p[-5:])
