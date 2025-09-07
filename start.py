#!/usr/bin/env python3
"""
火车实时追踪系统 - 简化启动脚本
"""

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

class TrainTrackingSystem:
    def __init__(self):
        self.processes = []
        self.running = True
        
    def start_darwin_api(self, port=8000):
        """启动Darwin API服务器"""
        print("🚂 启动Darwin API服务器...")
        cmd = [
            sys.executable, "-m", "uvicorn",
            "backend.api.darwin_api:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--log-level", "info"
        ]
        
        process = subprocess.Popen(cmd)
        self.processes.append(("Darwin API", process))
        return process
    
    def start_websocket_server(self, ws_port=8002, api_port=8003):
        """启动WebSocket实时服务器"""
        print("⚡ 启动WebSocket实时服务器...")
        cmd = [
            sys.executable, "-m", "backend.api.websocket_server",
            "--ws-port", str(ws_port),
            "--api-port", str(api_port)
        ]
        
        process = subprocess.Popen(cmd)
        self.processes.append(("WebSocket Server", process))
        return process
    
    def start_web_server(self, port=3000):
        """启动Web服务器"""
        print("🌐 启动Web服务器...")
        cmd = [sys.executable, "-m", "backend.services.web_server", "--port", str(port), "--dir", "frontend"]
        
        process = subprocess.Popen(cmd)
        self.processes.append(("Web Server", process))
        return process
    
    def wait_for_service(self, url, service_name, max_attempts=30):
        """等待服务启动"""
        import requests
        
        for i in range(max_attempts):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ {service_name} 已就绪")
                    return True
            except:
                pass
            
            print(f"⏳ 等待 {service_name} 启动... ({i+1}/{max_attempts})")
            time.sleep(1)
        
        print(f"❌ {service_name} 启动超时")
        return False
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            print(f"\n🛑 收到信号 {signum}，正在关闭系统...")
            self.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def shutdown(self):
        """关闭所有进程"""
        print("🔄 正在关闭所有服务...")
        self.running = False
        
        for name, process in self.processes:
            if process.poll() is None:
                print(f"⏹️  关闭 {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"🔨 强制关闭 {name}...")
                    process.kill()
        
        print("✅ 所有服务已关闭")
    
    def monitor_processes(self):
        """监控进程状态"""
        while self.running:
            for name, process in self.processes:
                if process.poll() is not None:
                    print(f"❌ {name} 进程已退出 (退出码: {process.returncode})")
                    self.running = False
                    break
            
            time.sleep(2)
    
    def print_system_info(self):
        """打印系统信息"""
        print("\n" + "="*60)
        print("🚂 火车实时追踪系统")
        print("="*60)
        print("📱 可用页面:")
        print("  🚂 Leaflet版 (推荐): http://localhost:3000/templates/leaflet_enhanced.html")
        print("  🚂 高性能版: http://localhost:3000/templates/index.html")
        print("  🚂 增强版: http://localhost:3000/templates/enhanced.html")
        print("  🚂 基础版: http://localhost:3000/templates/basic.html")
        print("\n📡 API服务:")
        print("  🔗 Darwin API: http://localhost:8000")
        print("  📊 WebSocket API: http://localhost:8003")
        print("  🔌 WebSocket: ws://localhost:8002")
        print("="*60)
        print("⏹️  按 Ctrl+C 停止所有服务")
        print("="*60)
    
    def start_system(self):
        """启动完整系统"""
        print("🚀 启动火车实时追踪系统")
        
        # 检查必要文件
        required_files = [
            "backend/api/darwin_api.py",
            "backend/api/websocket_server.py", 
            "backend/services/web_server.py",
            "frontend/templates/index.html"
        ]
        
        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)
        
        if missing_files:
            print("❌ 缺少必要文件:")
            for file in missing_files:
                print(f"   - {file}")
            return False
        
        # 设置信号处理器
        self.setup_signal_handlers()
        
        try:
            # 1. 启动Darwin API服务器
            self.start_darwin_api(8000)
            
            # 等待Darwin API就绪
            if not self.wait_for_service("http://localhost:8000/health", "Darwin API"):
                self.shutdown()
                return False
            
            # 2. 启动WebSocket服务器
            self.start_websocket_server(8002, 8003)
            
            # 等待WebSocket服务器就绪
            if not self.wait_for_service("http://localhost:8003/health", "WebSocket服务器"):
                self.shutdown()
                return False
            
            # 3. 启动Web服务器
            self.start_web_server(3000)
            
            # 等待Web服务器启动
            time.sleep(2)
            
            # 显示系统信息
            self.print_system_info()
            
            # 监控进程
            self.monitor_processes()
            
        except Exception as e:
            print(f"❌ 系统启动失败: {e}")
            self.shutdown()
            return False
        
        return True

def main():
    """主函数"""
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 需要Python 3.8或更高版本")
        return 1
    
    # 检查是否在项目根目录
    if not Path("backend").exists():
        print("❌ 请在项目根目录运行此脚本")
        return 1
    
    # 启动系统
    system = TrainTrackingSystem()
    success = system.start_system()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())