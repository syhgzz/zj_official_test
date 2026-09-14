# -*- coding: utf-8 -*-
"""临时检查器：从模板里抽出 JS，做括号配平，并指出第一个不配平的位置。"""
import re
import sys

TPL = r'E:\work\zj_official_test\testmap\map_view_template.html'
OUT = r'E:\work\zj_official_test\testmap\_scratch\tpl_check.js'

html = open(TPL, encoding='utf-8').read()
blocks = re.findall(r'<script>(.*?)</script>', html, re.S)
print('script blocks:', len(blocks))
js = blocks[-1]
open(OUT, 'w', encoding='utf-8').write(js)


def scan(src):
    """返回 (final_depth, 未闭合的开括号所在行, 各类计数)。逐字符跳过字符串/注释。"""
    depth = 0
    i = 0
    line = 1
    stack = []
    counts = {'{': 0, '}': 0, '(': 0, ')': 0, '[': 0, ']': 0}
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == '\n':
            line += 1
            i += 1
            continue
        if ch == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if ch == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2)
            if j < 0:
                break
            line += src.count('\n', i, j)
            i = j + 2
            continue
        if ch in ('"', "'", '`'):
            q = ch
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    i += 1
                if src[i] == '\n':
                    line += 1
                i += 1
            i += 1
            continue
        if ch in counts:
            counts[ch] += 1
        if ch in '{[(':
            stack.append((ch, line))
        elif ch in '}])':
            want = {'}': '{', ']': '[', ')': '('}[ch]
            if stack and stack[-1][0] == want:
                stack.pop()
            else:
                print('  不匹配的闭合 %s 在第 %d 行' % (ch, line))
        i += 1
    return stack, counts


stack, counts = scan(js)
print('计数:', counts)
print('未闭合:', stack[:20])
print('总行数:', js.count('\n') + 1)
sys.exit(0 if not stack else 1)
