#!/usr/bin/env python3
"""
停止所有火车追踪系统服务
"""

import subprocess
import signal
import os
import sys
import time

def find_and_kill_processes():
    """查找并终止相关进程"""
    
    # 要查找的进程关键词
    process_keywords = [
        "darwin_api.py",
        "websocket_server.py", 
        "web_server.py",
        "train_updater.py",
        "start.py",
        "main.py",
        "backend.services.web_server",
        "backend.api.darwin_api",
        "backend.api.websocket_server"
    ]
    
    # 要检查的端口
    ports = [8000, 8001, 8002, 8003, 3000]
    
    killed_processes = []
    
    print("🔍 查找运行中的服务...")
    
    # 方法1: 通过进程名查找
    for keyword in process_keywords:
        try:
            # 使用pgrep查找进程
            result = subprocess.run(
                ["pgrep", "-f", keyword], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            print(f"🔪 终止进程: {keyword} (PID: {pid})")
                            os.kill(int(pid), signal.SIGTERM)
                            killed_processes.append(f"{keyword} (PID: {pid})")
                            time.sleep(0.5)  # 给进程一点时间优雅退出
                        except ProcessLookupError:
                            print(f"  ⚠️  进程 {pid} 已经不存在")
                        except PermissionError:
                            print(f"  ❌ 没有权限终止进程 {pid}")
                            
        except FileNotFoundError:
            # pgrep命令不存在，跳过
            pass
    
    # 方法2: 通过端口查找进程
    print("\n🔍 检查占用的端口...")
    for port in ports:
        try:
            # 使用lsof查找占用端口的进程
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            print(f"🔪 终止占用端口 {port} 的进程 (PID: {pid})")
                            os.kill(int(pid), signal.SIGTERM)
                            killed_processes.append(f"Port {port} (PID: {pid})")
                            time.sleep(0.5)
                        except ProcessLookupError:
                            print(f"  ⚠️  进程 {pid} 已经不存在")
                        except PermissionError:
                            print(f"  ❌ 没有权限终止进程 {pid}")
                            
        except FileNotFoundError:
            # lsof命令不存在，跳过
            pass
    
    return killed_processes

def force_kill_if_needed():
    """如果还有进程存在，强制终止"""
    print("\n⏳ 等待进程优雅退出...")
    time.sleep(2)
    
    # 再次检查是否还有进程
    still_running = []
    
    try:
        result = subprocess.run(
            ["pgrep", "-f", "darwin_api.py|websocket_server.py|web_server.py|train_updater.py"], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    still_running.append(pid)
    except FileNotFoundError:
        pass
    
    if still_running:
        print("💀 强制终止剩余进程...")
        for pid in still_running:
            try:
                print(f"💀 强制终止进程 (PID: {pid})")
                os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"  ❌ 没有权限强制终止进程 {pid}")

def kill_port_processes():
    """直接终止占用特定端口的进程"""
    ports = [8000, 8001, 8002, 8003, 3000]
    killed = []
    
    for port in ports:
        try:
            # 使用netstat查找占用端口的进程 (macOS)
            result = subprocess.run(
                ["netstat", "-anv", "-p", "tcp"], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if f".{port} " in line and "LISTEN" in line:
                        # 提取进程信息
                        parts = line.split()
                        if len(parts) > 8:
                            try:
                                # 在macOS上，使用lsof更可靠
                                lsof_result = subprocess.run(
                                    ["lsof", "-ti", f":{port}"], 
                                    capture_output=True, 
                                    text=True
                                )
                                if lsof_result.returncode == 0:
                                    pids = lsof_result.stdout.strip().split('\n')
                                    for pid in pids:
                                        if pid:
                                            print(f"🔪 终止占用端口 {port} 的进程 (PID: {pid})")
                                            os.kill(int(pid), signal.SIGTERM)
                                            killed.append(f"Port {port} (PID: {pid})")
                                            time.sleep(0.5)
                            except (ValueError, ProcessLookupError, PermissionError) as e:
                                print(f"  ⚠️  无法终止端口 {port} 的进程: {e}")
                                
        except FileNotFoundError:
            pass
    
    return killed

def main():
    """主函数"""
    print("🛑 停止火车追踪系统...")
    print("=" * 50)
    
    # 方法1: 查找并终止进程
    killed1 = find_and_kill_processes()
    
    # 方法2: 直接终止占用端口的进程
    print("\n🔍 检查端口占用...")
    killed2 = kill_port_processes()
    
    all_killed = killed1 + killed2
    
    if all_killed:
        print(f"\n✅ 已终止 {len(all_killed)} 个进程:")
        for process in all_killed:
            print(f"  • {process}")
        
        # 强制终止剩余进程
        force_kill_if_needed()
        
    else:
        print("ℹ️  没有找到运行中的服务")
    
    print("\n🎉 系统已停止!")
    print("\n重新启动请运行:")
    print("  python3 start.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  停止操作被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 停止过程中出错: {e}")
        sys.exit(1)