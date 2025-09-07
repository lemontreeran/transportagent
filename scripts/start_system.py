#!/usr/bin/env python3
"""
智能火车追踪系统启动器
集成Darwin API + 智能更新器 + Web服务器
"""

import subprocess
import sys
import time
import signal
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

class SmartSystemManager:
    def __init__(self):
        self.processes = []
        self.running = True
        
        # 加载环境变量
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
            print("✅ 加载了 .env 配置文件")
        else:
            print("⚠️  未找到 .env 文件，使用默认配置")
    
    def start_darwin_api(self, port=8000):
        """启动Darwin API服务器"""
        print("🚂 启动Darwin API服务器...")
        cmd = [
            sys.executable, "-m", "uvicorn",
            "darwin_realtime_consumer:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--log-level", "info"
        ]
        
        process = subprocess.Popen(cmd)
        self.processes.append(("Darwin API", process))
        return process
    
    def start_smart_updater(self, port=8001):
        """启动智能更新器API"""
        print("🧠 启动智能位置更新器...")
        cmd = [
            sys.executable, "smart_train_updater.py", "--api-mode"
        ]
        
        # 设置环境变量
        env = os.environ.copy()
        env["UVICORN_PORT"] = str(port)
        
        process = subprocess.Popen(cmd, env=env)
        self.processes.append(("Smart Updater", process))
        return process
    
    def start_websocket_server(self, ws_port=8002, api_port=8003):
        """启动WebSocket实时服务器"""
        print("⚡ 启动WebSocket实时服务器...")
        cmd = [
            sys.executable, "realtime_websocket_server.py",
            "--ws-port", str(ws_port),
            "--api-port", str(api_port)
        ]
        
        process = subprocess.Popen(cmd)
        self.processes.append(("WebSocket Server", process))
        return process
    
    def start_web_server(self, port=3000):
        """启动Web服务器"""
        print("🌐 启动Web服务器...")
        cmd = [sys.executable, "serve_web.py", "--port", str(port)]
        
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
            if process.poll() is None:  # 进程仍在运行
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
        print("🚂 智能火车追踪系统")
        print("="*60)
        
        # 显示配置信息
        config_info = [
            ("Darwin API", "http://localhost:8000"),
            ("智能更新器", "http://localhost:8001"),
            ("Web界面", "http://localhost:3000"),
            ("更新间隔", f"{os.getenv('NORMAL_UPDATE_INTERVAL', '60')}秒"),
            ("深夜间隔", f"{os.getenv('SLOW_UPDATE_INTERVAL', '300')}秒"),
            ("数据保留", f"{os.getenv('MAX_POSITION_AGE_HOURS', '24')}小时"),
        ]
        
        for key, value in config_info:
            print(f"{key:12}: {value}")
        
        print("\n📱 可用服务:")
        print("  🔗 Darwin API文档: http://localhost:8000/docs")
        print("  🔗 更新器API文档: http://localhost:8001/docs")
        print("  🚂 标准火车追踪: http://localhost:3000/enhanced-train-tracker.html")
        print("  ⚡ 高性能追踪: http://localhost:3000/high-performance-train-tracker.html")
        print("  📊 系统统计: http://localhost:8001/stats")
        print("  🔌 WebSocket: ws://localhost:8002")
        
        print("\n⚙️  环境变量配置:")
        env_vars = [
            "NORMAL_UPDATE_INTERVAL",
            "SLOW_UPDATE_INTERVAL", 
            "MAX_POSITION_AGE_HOURS",
            "PEAK_HOURS_START",
            "PEAK_HOURS_END"
        ]
        
        for var in env_vars:
            value = os.getenv(var, "未设置")
            print(f"  {var}: {value}")
        
        print("\n" + "="*60)
        print("⏹️  按 Ctrl+C 停止所有服务")
        print("="*60)
    
    def start_system(self, darwin_port=8000, updater_port=8001, web_port=3000, ws_port=8002, ws_api_port=8003):
        """启动完整系统"""
        print("🚀 启动智能火车追踪系统")
        
        # 设置信号处理器
        self.setup_signal_handlers()
        
        try:
            # 1. 启动Darwin API服务器
            self.start_darwin_api(darwin_port)
            
            # 等待Darwin API就绪
            if not self.wait_for_service(f"http://localhost:{darwin_port}/health", "Darwin API"):
                self.shutdown()
                return False
            
            # 2. 启动智能更新器
            self.start_smart_updater(updater_port)
            
            # 等待更新器就绪
            if not self.wait_for_service(f"http://localhost:{updater_port}/", "智能更新器"):
                self.shutdown()
                return False
            
            # 3. 启动WebSocket实时服务器
            self.start_websocket_server(ws_port, ws_api_port)
            
            # 等待WebSocket服务器就绪
            if not self.wait_for_service(f"http://localhost:{ws_api_port}/health", "WebSocket服务器"):
                self.shutdown()
                return False
            
            # 4. 启动Web服务器
            self.start_web_server(web_port)
            
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

def create_default_env():
    """创建默认的.env文件"""
    env_content = """# 智能火车追踪系统配置

# 更新间隔（秒）
NORMAL_UPDATE_INTERVAL=60
SLOW_UPDATE_INTERVAL=300

# 时间段配置
PEAK_HOURS_START=6
PEAK_HOURS_END=22

# 数据保留
MAX_POSITION_AGE_HOURS=24

# 性能配置
MAX_CONCURRENT_REQUESTS=10
UPDATE_BATCH_SIZE=100

# 初始化配置
FULL_SYNC_ON_STARTUP=true
INITIAL_DATA_AGE_MINUTES=1440
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ 创建了默认的 .env 配置文件")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能火车追踪系统")
    parser.add_argument("--darwin-port", type=int, default=8000, help="Darwin API端口")
    parser.add_argument("--updater-port", type=int, default=8001, help="智能更新器端口")
    parser.add_argument("--web-port", type=int, default=3000, help="Web服务器端口")
    parser.add_argument("--ws-port", type=int, default=8002, help="WebSocket端口")
    parser.add_argument("--ws-api-port", type=int, default=8003, help="WebSocket API端口")
    parser.add_argument("--create-env", action="store_true", help="创建默认.env文件")
    
    args = parser.parse_args()
    
    if args.create_env:
        create_default_env()
        return 0
    
    # 检查必要文件
    required_files = [
        "darwin_realtime_consumer.py",
        "smart_train_updater.py",
        "serve_web.py",
        "enhanced-train-tracker.html"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("❌ 缺少必要文件:")
        for file in missing_files:
            print(f"   - {file}")
        return 1
    
    # 检查.env文件
    if not Path(".env").exists():
        print("⚠️  未找到 .env 配置文件")
        print("💡 运行 'python start_smart_system.py --create-env' 创建默认配置")
        print("📝 或复制 .env.example 到 .env 并修改配置")
    
    # 启动系统
    manager = SmartSystemManager()
    success = manager.start_system(
        args.darwin_port, 
        args.updater_port, 
        args.web_port,
        args.ws_port,
        args.ws_api_port
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())