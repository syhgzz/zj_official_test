# -*- coding: utf-8 -*-
"""逐脚本块做括号配平，确认是否存在真的不配平。"""
import re

TPL = r'E:\work\zj_official_test\testmap\map_view_template.html'
html = open(TPL, encoding='utf-8').read()
blocks = re.findall(r'<script>(.*?)</script>', html, re.S)

def scan(src):
    stack = []
    i, line, n = 0, 1, len(src)
    counts = {'{': 0, '}': 0, '(': 0, ')': 0, '[': 0, ']': 0}
    while i < n:
        ch = src[i]
        if ch == '\n':
            line += 1; i += 1; continue
        if ch == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i); i = n if j < 0 else j; continue
        if ch == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2)
            if j < 0: break
            line += src.count('\n', i, j); i = j + 2; continue
        if ch in ('"', "'", '`'):
            q = ch; i += 1
            while i < n and src[i] != q:
                if src[i] == '\\': i += 1
                if i < n and src[i] == '\n': line += 1
                i += 1
            i += 1; continue
        if ch in counts: counts[ch] += 1
        if ch in '{[(': stack.append((ch, line))
        elif ch in '}])':
            want = {'}': '{', ']': '[', ')': '('}[ch]
            if stack and stack[-1][0] == want: stack.pop()
            else: print('   不匹配闭合 %s @%d' % (ch, line))
        i += 1
    return stack, counts

bad = False
for k, b in enumerate(blocks):
    st, c = scan(b)
    print('block %d: 括号净差 {=%+d (=%+d [=%+d  未闭合=%s'
          % (k, c['{'] - c['}'], c['('] - c[')'], c['['] - c[']'], st[:4]))
    if st: bad = True
print('结论:', '存在不配平' if bad else '全部配平')
