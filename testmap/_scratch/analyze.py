# -*- coding: utf-8 -*-
"""Transitive call closure of Contour.java from the reference finishFromGrid entry points."""
import re
import json

SRC = r'E:\deepseek_harness_workspace\testmap\_scratch\wcontour\Contour.java'
lines = open(SRC, encoding='utf-8', errors='replace').read().split('\n')

# --- strip comments/strings, line by line (offsets not needed) ---
def strip_line(s, in_block):
    out = []
    i, n = 0, len(s)
    while i < n:
        if in_block:
            j = s.find('*/', i)
            if j < 0:
                return ''.join(out), True
            i = j + 2; in_block = False; continue
        if s.startswith('//', i):
            break
        if s.startswith('/*', i):
            in_block = True; i += 2; continue
        c = s[i]
        if c == '"':
            i += 1
            while i < n:
                if s[i] == '\\':
                    i += 2; continue
                if s[i] == '"':
                    i += 1; break
                i += 1
            out.append('""'); continue
        if c == "'":
            i += 1
            while i < n:
                if s[i] == '\\':
                    i += 2; continue
                if s[i] == "'":
                    i += 1; break
                i += 1
            out.append("''"); continue
        out.append(c); i += 1
    return ''.join(out), in_block

clean = []
in_block = False
for s in lines:
    c, in_block = strip_line(s, in_block)
    clean.append(c)

# --- locate method definitions (signature may span lines) ---
sig_start = re.compile(r'^\s{4}(?:public|private|protected)\s+(?:static\s+)?')
methods = []
i = 0
N = len(clean)
while i < N:
    if sig_start.match(clean[i]):
        j = i
        buf = []
        while j < N and '{' not in clean[j]:
            buf.append(clean[j]); j += 1
            if j - i > 8:
                break
        if j < N and '{' in clean[j]:
            sig = ' '.join(x.strip() for x in buf + [clean[j].split('{')[0]])
            m = re.search(r'(\w+)\s*\((.*)\)\s*$', sig.replace('  ', ' ').strip(), re.S)
            if m:
                name, args = m.group(1), m.group(2)
                if name not in ('if', 'for', 'while', 'switch', 'catch'):
                    # brace count from line j
                    depth = 0
                    k = j
                    started = False
                    while k < N:
                        depth += clean[k].count('{') - clean[k].count('}')
                        if '{' in clean[k]:
                            started = True
                        if started and depth == 0:
                            break
                        k += 1
                    ret = sig.split(name)[0]
                    ret = re.sub(r'^\s{4}(?:public|private|protected)\s+(?:static\s+)?', '', ret).strip()
                    methods.append(dict(name=name, args=' '.join(args.split()),
                                        ret=ret, lineno=i + 1, endline=k + 1,
                                        bstart=j, bend=k))
                    i = k + 1
                    continue
    i += 1

by_name = {}
for d in methods:
    by_name.setdefault(d['name'], []).append(d)

print(f'parsed methods: {len(methods)}')

def body(d):
    return '\n'.join(clean[d['bstart']:d['bend'] + 1])

calls = {}
for d in methods:
    b = body(d)
    found = set()
    for other in methods:
        if other is d:
            continue
        if re.search(r'\b' + re.escape(other['name']) + r'\s*\(', b):
            found.add(other['name'])
    calls.setdefault(d['name'], set()).update(found)

ENTRY = {'tracingBorders', 'tracingContourLines', 'smoothLines', 'tracingPolygons'}
need = set()
stack = list(ENTRY)
while stack:
    cur = stack.pop()
    if cur in need:
        continue
    need.add(cur)
    for nxt in calls.get(cur, ()):
        stack.append(nxt)
need = {n for n in need if n in by_name}

print('\n=== REQUIRED (transitive closure) ===')
total = 0
for d in methods:
    if d['name'] in need:
        ln = d['endline'] - d['lineno'] + 1
        total += ln
        print(f"{d['lineno']:>5}-{d['endline']:<5} {ln:>5}L  {d['ret']:<28} {d['name']}({d['args'][:78]})")
print(f'\nTOTAL JAVA LINES TO PORT: {total}')

print('\n=== NOT REQUIRED ===')
for d in methods:
    if d['name'] not in need:
        print(f"{d['lineno']:>5}-{d['endline']:<5} {d['name']}")

print('\n=== call edges among required ===')
for d in methods:
    if d['name'] in need:
        print(f"  {d['name']} -> {sorted(c for c in calls[d['name']] if c in need)}")

json.dump([{k: v for k, v in d.items() if k in ('name', 'args', 'ret', 'lineno', 'endline')}
           for d in methods if d['name'] in need],
          open(r'E:\deepseek_harness_workspace\testmap\_scratch\required_methods.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
