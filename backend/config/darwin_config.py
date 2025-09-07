#!/usr/bin/env python3
"""
Darwin实时消费者配置管理工具
用于动态调整更新间隔和其他配置参数
"""

import requests
import json
import argparse
from datetime import datetime

class DarwinConfigManager:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
    
    def get_config(self):
        """获取当前配置"""
        try:
            response = requests.get(f"{self.base_url}/config")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取配置失败: {e}")
            return None
    
    def set_update_interval(self, seconds):
        """设置更新间隔"""
        try:
            response = requests.post(f"{self.base_url}/config/update-interval/{seconds}")
            response.raise_for_status()
            result = response.json()
            print(f"✅ {result['message']}")
            return True
        except Exception as e:
            print(f"❌ 设置更新间隔失败: {e}")
            return False
    
    def get_stats(self):
        """获取统计信息"""
        try:
            response = requests.get(f"{self.base_url}/debug/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取统计信息失败: {e}")
            return None
    
    def get_positions(self, limit=10):
        """获取位置信息"""
        try:
            response = requests.get(f"{self.base_url}/positions?limit={limit}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取位置信息失败: {e}")
            return None
    
    def cleanup_data(self):
        """手动清理数据"""
        try:
            response = requests.post(f"{self.base_url}/debug/cleanup")
            response.raise_for_status()
            result = response.json()
            print(f"✅ {result['message']}")
            return True
        except Exception as e:
            print(f"❌ 清理数据失败: {e}")
            return False
    
    def add_tiploc(self, tiploc, lat, lon, name=""):
        """添加TIPLOC坐标"""
        try:
            response = requests.post(
                f"{self.base_url}/tiplocs/{tiploc}",
                params={"lat": lat, "lon": lon, "name": name}
            )
            response.raise_for_status()
            result = response.json()
            print(f"✅ {result['message']}")
            return True
        except Exception as e:
            print(f"❌ 添加TIPLOC失败: {e}")
            return False
    
    def show_status(self):
        """显示系统状态"""
        print("🚂 Darwin实时火车位置服务状态")
        print("=" * 50)
        
        # 获取配置
        config = self.get_config()
        if config:
            print(f"📊 配置信息:")
            print(f"   更新间隔: {config['update_interval']} 秒")
            print(f"   最大数据年龄: {config['max_age_hours']} 小时")
            print(f"   数据库路径: {config['db_path']}")
            print(f"   Kafka配置: {'✅' if config['kafka_configured'] else '❌'}")
        
        # 获取统计信息
        stats = self.get_stats()
        if stats:
            print(f"\n📈 运行统计:")
            print(f"   内存中火车数: {stats['trains_in_memory']}")
            print(f"   总消息数: {stats['total_messages']}")
            print(f"   错误数: {stats['error_count']}")
            print(f"   消费者状态: {'🟢 活跃' if stats['consumer_active'] else '🔴 停止'}")
            if stats['last_update']:
                last_update = datetime.fromisoformat(stats['last_update'])
                print(f"   最后更新: {last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 获取最新位置
        positions = self.get_positions(5)
        if positions:
            print(f"\n🚂 最新火车位置 (前5个):")
            for pos in positions[:5]:
                state_emoji = {"enroute": "🚄", "dwell": "🚉", "stopped": "🛑"}.get(pos.get('state', ''), "❓")
                print(f"   {state_emoji} {pos['rid']}: ({pos['lat']:.4f}, {pos['lon']:.4f}) - {pos['state']}")

def main():
    parser = argparse.ArgumentParser(description="Darwin实时消费者配置管理")
    parser.add_argument("--url", default="http://localhost:8000", help="服务URL")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 状态命令
    subparsers.add_parser("status", help="显示系统状态")
    
    # 配置命令
    config_parser = subparsers.add_parser("config", help="配置管理")
    config_parser.add_argument("--interval", type=int, help="设置更新间隔（秒）")
    
    # 数据命令
    data_parser = subparsers.add_parser("data", help="数据管理")
    data_parser.add_argument("--cleanup", action="store_true", help="清理旧数据")
    data_parser.add_argument("--positions", type=int, default=10, help="显示位置数据")
    
    # TIPLOC命令
    tiploc_parser = subparsers.add_parser("tiploc", help="TIPLOC管理")
    tiploc_parser.add_argument("--add", nargs=4, metavar=("TIPLOC", "LAT", "LON", "NAME"), 
                              help="添加TIPLOC坐标")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = DarwinConfigManager(args.url)
    
    if args.command == "status":
        manager.show_status()
    
    elif args.command == "config":
        if args.interval:
            manager.set_update_interval(args.interval)
        else:
            config = manager.get_config()
            if config:
                print("📊 当前配置:")
                print(json.dumps(config, indent=2, ensure_ascii=False))
    
    elif args.command == "data":
        if args.cleanup:
            manager.cleanup_data()
        else:
            positions = manager.get_positions(args.positions)
            if positions:
                print(f"🚂 火车位置数据 (前{len(positions)}个):")
                for i, pos in enumerate(positions, 1):
                    print(f"{i:2d}. {pos['rid']} ({pos['uid']}) - {pos['state']}")
                    print(f"     位置: ({pos['lat']:.6f}, {pos['lon']:.6f})")
                    print(f"     时间: {pos['ts']}")
                    if pos.get('platform'):
                        print(f"     站台: {pos['platform']}")
                    print()
    
    elif args.command == "tiploc":
        if args.add:
            tiploc, lat, lon, name = args.add
            try:
                lat = float(lat)
                lon = float(lon)
                manager.add_tiploc(tiploc, lat, lon, name)
            except ValueError:
                print("❌ 纬度和经度必须是数字")

if __name__ == "__main__":
    main()