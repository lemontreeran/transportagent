#!/usr/bin/env python3
"""
简单启动脚本
避免复杂的配置，直接启动服务
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def main():
    print("🚂 简单火车追踪系统启动")
    print("=" * 40)
    
    processes = []
    
    try:
        # 1. 启动API服务器
        print("🔌 启动API服务器...")
        api_process = subprocess.Popen([
            sys.executable, "train_api.py"
        ])
        processes.append(api_process)
        print("✅ API服务器已启动 (端口 8000)")
        
        # 等待API启动
        time.sleep(3)
        
        # 2. 启动Web服务器
        print("🌐 启动Web服务器...")
        web_process = subprocess.Popen([
            sys.executable, "-m", "http.server", "8080"
        ])
        processes.append(web_process)
        print("✅ Web服务器已启动 (端口 8080)")
        
        # 等待Web服务器启动
        time.sleep(2)
        
        print("\n🎉 系统启动完成！")
        print("\n📱 访问地址:")
        print("   🗺️ 增强版地图: http://localhost:8080/enhanced-train-tracker.html")
        print("   📊 原版地图: http://localhost:8080/index.html")
        print("   🧪 简单测试: http://localhost:8080/train-tracker.html")
        
        print("\n⏹️ 按 Ctrl+C 停止所有服务")
        print("-" * 40)
        
        # 自动打开浏览器
        try:
            webbrowser.open("http://localhost:8080/enhanced-train-tracker.html")
            print("🌍 浏览器已自动打开")
        except:
            print("💡 请手动打开浏览器访问上述地址")
        
        # 保持运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        print("✅ 所有服务已停止")
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        for process in processes:
            try:
                process.terminate()
            except:
                pass

if __name__ == "__main__":
    main()