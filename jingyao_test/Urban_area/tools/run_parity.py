# -*- coding: utf-8 -*-
"""
run_parity.py —— 一键复现「Python 移植 vs 原始 Java」的等值面逐阶段对拍。

流程
====
  1. 找 JDK（--jdk 指定 > JAVA_HOME > PATH 上的 javac）
  2. 把 wcontour/_upstream/ 的原始 Java 源码摆成 javac 认的目录结构并编译，
     连同一个导出真值的驱动 WContourDriver.java
  3. 生成用例（9 个合成算例 + 真实接口帧）
  4. 跑 Java：tracingBorders → tracingContourLines → smoothLines → tracingPolygons，
     把 S1 / borders / contourLines / smoothLines / polygons **全部阶段**写成 JSON
  5. 跑 Python 移植，与真值逐阶段比对（浮点按位相等才算过）

用法
====
    # 需要 JDK；本机没有的话可以下载便携版 Temurin，例如
    #   https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse
    uv run python -m precipitation_xunteng.tools.run_parity --jdk D:\\jdk-21.0.12.1+1

    uv run python -m precipitation_xunteng.tools.run_parity --jdk <JDK> --keep   # 保留中间产物

退出码：全部阶段一致返回 0，否则 1。
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.dirname(HERE)
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
UPSTREAM = os.path.join(PACKAGE_DIR, 'wcontour', '_upstream')
RUNDIR = os.path.join(HERE, '_parity_run')

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

os.environ.setdefault('WCONTOUR_PARITY_DIR', RUNDIR)


def find_jdk(explicit):
    """返回 (javac, java) 的绝对路径。"""
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get('JAVA_HOME'):
        cands.append(os.environ['JAVA_HOME'])
    for c in cands:
        jc = os.path.join(c, 'bin', 'javac.exe' if os.name == 'nt' else 'javac')
        jv = os.path.join(c, 'bin', 'java.exe' if os.name == 'nt' else 'java')
        if os.path.exists(jc) and os.path.exists(jv):
            return jc, jv
    jc = shutil.which('javac')
    jv = shutil.which('java')
    if jc and jv:
        return jc, jv
    return None, None


def prepare_sources(src_root):
    """把 _upstream 的 Java 源码摆成 <src_root>/wcontour/... 供 javac 解析包名。"""
    pkg = os.path.join(src_root, 'wcontour')
    gpkg = os.path.join(pkg, 'global')
    os.makedirs(gpkg, exist_ok=True)
    shutil.copy2(os.path.join(UPSTREAM, 'Contour.java'), os.path.join(pkg, 'Contour.java'))
    for f in glob.glob(os.path.join(UPSTREAM, 'global', '*.java')):
        shutil.copy2(f, os.path.join(gpkg, os.path.basename(f)))
    driver = os.path.join(HERE, 'WContourDriver.java')
    shutil.copy2(driver, os.path.join(src_root, 'WContourDriver.java'))
    return pkg


def compile_java(javac, src_root, classes_dir):
    os.makedirs(classes_dir, exist_ok=True)
    sources = glob.glob(os.path.join(src_root, '**', '*.java'), recursive=True)
    cmd = [javac, '-encoding', 'UTF-8', '-nowarn', '-d', classes_dir,
           '-sourcepath', src_root] + sources
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    out = (r.stdout or '') + (r.stderr or '')
    # javac 的中文提示在部分终端会乱码，这里只保留非 "unchecked" 的关键行
    keys = [l for l in out.splitlines()
            if l.strip() and 'unchecked' not in l and 'Xlint' not in l]
    if r.returncode != 0:
        print('!! Java 编译失败:')
        print('\n'.join(keys[:40]))
    return r.returncode == 0


def run_java(java, classes_dir, case_file, truth_file):
    r = subprocess.run([java, '-cp', classes_dir, 'WContourDriver', case_file, truth_file],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode, (r.stdout or '').strip(), (r.stderr or '').strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description='wContour Python 移植 vs 原始 Java 对拍')
    ap.add_argument('--jdk', default=None, help='JDK 根目录（含 bin/javac）')
    ap.add_argument('--input', nargs='+', default=None,
                    help='额外用作真实用例的接口返回 JSON（默认自动扫 responses/）')
    ap.add_argument('--keep', action='store_true', help='保留中间产物（默认也保留，便于排查）')
    ap.add_argument('--only', nargs='+', default=None, help='只比对指定的用例名')
    args = ap.parse_args(argv)

    javac, java = find_jdk(args.jdk)
    if not javac:
        print('!! 找不到 JDK。用 --jdk <JDK目录> 指定，或设置 JAVA_HOME。')
        print('   便携版下载: https://api.adoptium.net/v3/binary/latest/21/ga/'
              'windows/x64/jdk/hotspot/normal/eclipse')
        return 2
    print(f'JDK: {javac}')

    src_root = os.path.join(RUNDIR, 'src')
    classes_dir = os.path.join(RUNDIR, 'classes')
    truth_dir = os.path.join(RUNDIR, 'truth')
    for d in (src_root, classes_dir, truth_dir):
        os.makedirs(d, exist_ok=True)

    print('[1/4] 准备 Java 源码 ...')
    prepare_sources(src_root)
    print('[2/4] 编译 wContour + WContourDriver ...')
    if not compile_java(javac, src_root, classes_dir):
        return 2

    print('[3/4] 生成用例 ...')
    import jingyao_test.Urban_area.tools.gen_cases as gen_cases
    manifest = gen_cases.main(args.input or ())

    print('[4/4] 跑 Java 真值 + Python 比对 ...')
    n_java_ok = 0
    for e in manifest:
        truth = os.path.join(truth_dir, e['name'] + '.json')
        code, out, err = run_java(java, classes_dir, e['input'], truth)
        if code == 0:
            n_java_ok += 1
        else:
            print(f"  !! Java 失败 {e['name']}: {err[:200]}")
    print(f'  Java 真值导出 {n_java_ok}/{len(manifest)} 个用例')

    import jingyao_test.Urban_area.tools.compare as compare
    rc = compare.main(args.only or [], truth_dir=truth_dir)
    print(f'\n中间产物: {RUNDIR}')
    return rc


if __name__ == '__main__':
    sys.exit(main())
