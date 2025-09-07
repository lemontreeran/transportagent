#!/usr/bin/env python3
"""
简单的Web服务器，用于提供HTML文件和处理CORS
"""

import http.server
import socketserver
import os
from urllib.parse import urlparse

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

def start_server(port=3000, directory="frontend"):
    """启动Web服务器"""
    # 确保目录存在
    if not os.path.exists(directory):
        directory = "."
    
    # 获取绝对路径
    abs_directory = os.path.abspath(directory)
    os.chdir(abs_directory)
    
    with socketserver.TCPServer(("", port), CORSHTTPRequestHandler) as httpd:
        print(f"🌐 Web服务器启动成功")
        print(f"📍 访问地址: http://localhost:{port}")
        print(f"📁 服务目录: {os.getcwd()}")
        print("\n可用页面:")
        print(f"  🚂 高性能版: http://localhost:{port}/templates/index.html")
        print(f"  🚂 增强版: http://localhost:{port}/templates/enhanced.html")
        print(f"  🚂 基础版: http://localhost:{port}/templates/basic.html")
        print("\n⏹️  按 Ctrl+C 停止服务")
        print("-" * 50)
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Web服务器已停止")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Web服务器")
    parser.add_argument("--port", type=int, default=3000, help="端口号 (默认: 3000)")
    parser.add_argument("--dir", default=".", help="服务目录 (默认: 当前目录)")
    
    args = parser.parse_args()
    start_server(args.port, args.dir)