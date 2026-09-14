# -*- coding: utf-8 -*-
"""
serve_web.py —— 启动本地静态服务，浏览降水图对照页

为什么必须用 HTTP 打开：
  1. 高德 ImageLayer 叠加本地 PNG（file:// 下浏览器跨源限制，图层不渲染）；
  2. WMTS Capabilities 需要跨源 fetch；
  3. 高德 Key 白名单按域名生效，用 http://localhost:PORT 打开（127.0.0.1 可能不在白名单）。

用法：
    uv run python -m precipitation_xunteng.serve_web            # 默认 8765
    uv run python -m precipitation_xunteng.serve_web --port 9000
"""

import argparse
import functools
import http.server
import os
import socketserver
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

WEB_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'web')


class ThreadedServer(socketserver.ThreadingTCPServer):
    """
    每个连接一个线程。

    原先是单线程 TCPServer：浏览器（或 playwright）关页面时留下的那条连接没人读
    也没人关，服务端就卡死在那次 read 上，进程还在、端口还在听，但后面所有请求
    一律超时（实测复现：netstat 里一条 Established + 一条 CloseWait，请求全 20s 超时）。
    """

    daemon_threads = True
    # 不设 allow_reuse_address（原因见 main 里的说明，默认值就是 False）。


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """
    一律禁掉浏览器缓存。

    原因：页面每次导出后图层文件名会变（_grid/_xt/_ref/_xtref…），而 precip_layers.js
    是当普通脚本加载的；浏览器一旦缓存了旧清单，清单里指向的 PNG 已不存在（404），
    叠加图就会静默消失（底图正常、就是没有色块）。这里对 HTML/JS/PNG 全部加 no-store。
    """

    # 空闲连接超时后主动断开：半死连接不会一直占着线程（原先单线程时会把服务卡死）
    timeout = 15

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        # 允许同源/跨源把 PNG 画到 canvas（部分地图渲染器会带 crossOrigin 取图）
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def log_message(self, fmt, *args):        # 静音逐条请求日志（只保留启动信息）
        pass


def main():
    ap = argparse.ArgumentParser(description='本地浏览降水图对照页')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--dir', default=WEB_OUT_DIR)
    args = ap.parse_args()

    if not os.path.isdir(args.dir):
        raise SystemExit(f'目录不存在: {args.dir}\n请先运行: uv run python -m precipitation_xunteng.export_web')

    handler = functools.partial(NoCacheHandler, directory=args.dir)
    # 注意：**不要**设 allow_reuse_address / SO_REUSEADDR。
    # Windows 上 SO_REUSEADDR 的语义是"允许别人抢占同一个端口"（不是 Linux 那种
    # 仅仅绕过 TIME_WAIT），开了之后能悄悄绑上已被占用的端口，两个服务抢同一个端口、
    # 请求落到哪个进程看运气。保持默认（不设该选项）时，端口被占用会直接报错，这才安全。
    with ThreadedServer(('127.0.0.1', args.port), handler) as httpd:
        # 打印真正存在的页面：--dir 指到哪就以哪为准（可以是 output/ 也可以是 output/web_ref/）
        page = next((p for p in (os.path.join(args.dir, 'precip_compare.html'),
                                 os.path.join(args.dir, 'web_ref', 'precip_compare.html'))
                     if os.path.exists(p)), None)
        base = f'http://localhost:{args.port}/'
        print(f'目录  : {args.dir}')
        if page:
            print(f'对照页: {base}{os.path.relpath(page, args.dir).replace(os.sep, "/")}')
        for extra in ('xunteng_png/index.html', 'web/precip_compare.html'):
            if os.path.exists(os.path.join(args.dir, extra)):
                print(f'其它  : {base}{extra}')
        print('Ctrl+C 停止')
        httpd.serve_forever()


if __name__ == '__main__':
    main()
