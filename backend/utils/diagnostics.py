#!/usr/bin/env python3
"""
诊断位置计算问题
分析为什么火车有数据但没有位置输出
"""

import sqlite3
import requests
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database_status(db_path="train_positions.db"):
    """检查数据库状态"""
    try:
        with sqlite3.connect(db_path) as conn:
            # 检查TIPLOC坐标数量
            cursor = conn.execute("SELECT COUNT(*) FROM tiploc_coords WHERE lat IS NOT NULL AND lon IS NOT NULL")
            tiploc_count = cursor.fetchone()[0]
            
            # 检查CRS映射数量
            cursor = conn.execute("SELECT COUNT(*) FROM crs_tiploc_mapping")
            mapping_count = cursor.fetchone()[0]
            
            # 检查火车位置数量
            cursor = conn.execute("SELECT COUNT(*) FROM train_positions")
            position_count = cursor.fetchone()[0]
            
            # 检查最近的火车位置
            cursor = conn.execute("""
                SELECT rid, from_tpl, to_tpl, lat, lon, state, updated_at 
                FROM train_positions 
                ORDER BY updated_at DESC 
                LIMIT 5
            """)
            recent_positions = cursor.fetchall()
            
            print("📊 数据库状态:")
            print(f"   TIPLOC坐标: {tiploc_count}")
            print(f"   CRS映射: {mapping_count}")
            print(f"   火车位置: {position_count}")
            
            if recent_positions:
                print("\n🚂 最近的火车位置:")
                for pos in recent_positions:
                    print(f"   {pos[0]}: {pos[1]} -> {pos[2]} ({pos[3]}, {pos[4]}) - {pos[5]} @ {pos[6]}")
            else:
                print("\n❌ 没有火车位置数据")
            
            return tiploc_count, mapping_count, position_count
            
    except Exception as e:
        logger.error(f"检查数据库失败: {e}")
        return 0, 0, 0

def check_api_status():
    """检查API状态"""
    try:
        # 检查统计信息
        response = requests.get("http://localhost:8000/debug/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print("\n📡 API统计:")
            print(f"   内存中火车: {stats.get('trains_in_memory', 0)}")
            print(f"   总消息数: {stats.get('total_messages', 0)}")
            print(f"   错误数: {stats.get('error_count', 0)}")
            print(f"   消费者活跃: {stats.get('consumer_active', False)}")
            print(f"   最后更新: {stats.get('last_update', 'N/A')}")
            
            if stats.get('last_error'):
                print(f"   最后错误: {stats['last_error']}")
        
        # 检查位置端点
        response = requests.get("http://localhost:8000/positions", timeout=5)
        if response.status_code == 200:
            positions = response.json()
            print(f"\n🎯 位置端点: 返回 {len(positions)} 个位置")
            
            if positions:
                print("   示例位置:")
                for i, pos in enumerate(positions[:3]):
                    print(f"     {i+1}. {pos.get('rid', 'N/A')}: ({pos.get('lat', 'N/A')}, {pos.get('lon', 'N/A')})")
            
            return len(positions)
        else:
            print(f"❌ 位置端点错误: {response.status_code}")
            return 0
            
    except Exception as e:
        logger.error(f"检查API失败: {e}")
        return 0

def check_tiploc_coverage():
    """检查TIPLOC覆盖率"""
    try:
        # 获取最后的载荷数据
        response = requests.get("http://localhost:8000/debug/last-payload", timeout=5)
        if response.status_code == 200:
            payload = response.json()
            
            # 提取TIPLOC
            tiplocs = set()
            uR = payload.get("uR", {})
            TS = uR.get("TS", {})
            locations = TS.get("Location", [])
            
            if isinstance(locations, dict):
                locations = [locations]
            
            for loc in locations:
                tpl = loc.get("tpl")
                if tpl:
                    tiplocs.add(tpl)
            
            print(f"\n🗺️  最后消息中的TIPLOC: {len(tiplocs)}")
            
            if tiplocs:
                # 检查这些TIPLOC是否有坐标
                with sqlite3.connect("train_positions.db") as conn:
                    found_coords = 0
                    missing_tiplocs = []
                    
                    for tiploc in list(tiplocs)[:10]:  # 检查前10个
                        cursor = conn.execute(
                            "SELECT lat, lon FROM tiploc_coords WHERE tiploc = ? AND lat IS NOT NULL AND lon IS NOT NULL",
                            (tiploc,)
                        )
                        result = cursor.fetchone()
                        
                        if result:
                            found_coords += 1
                            print(f"   ✅ {tiploc}: ({result[0]}, {result[1]})")
                        else:
                            missing_tiplocs.append(tiploc)
                            print(f"   ❌ {tiploc}: 无坐标")
                    
                    print(f"\n📈 坐标覆盖率: {found_coords}/{len(list(tiplocs)[:10])} (样本)")
                    
                    if missing_tiplocs:
                        print(f"\n🔍 缺少坐标的TIPLOC示例: {missing_tiplocs[:5]}")
            
    except Exception as e:
        logger.error(f"检查TIPLOC覆盖率失败: {e}")

def suggest_fixes():
    """建议修复方案"""
    print("\n🔧 建议的修复步骤:")
    print("1. 检查Darwin消费者是否正在接收真实数据")
    print("2. 验证TIPLOC坐标映射是否正确")
    print("3. 检查位置计算逻辑")
    print("4. 确认数据库连接和事务处理")
    
    print("\n💡 可以尝试的命令:")
    print("   # 重启Darwin消费者")
    print("   pkill -f darwin_realtime_consumer")
    print("   python3 start_darwin.py")
    print("")
    print("   # 手动添加更多TIPLOC坐标")
    print("   python3 load_tiploc_data.py --update")
    print("")
    print("   # 检查特定火车")
    print("   curl -s http://localhost:8000/debug/last-payload | jq .")

def main():
    print("🔍 诊断火车位置问题")
    print("=" * 50)
    
    # 检查数据库
    tiploc_count, mapping_count, position_count = check_database_status()
    
    # 检查API
    api_positions = check_api_status()
    
    # 检查TIPLOC覆盖率
    check_tiploc_coverage()
    
    # 分析问题
    print("\n📋 问题分析:")
    if tiploc_count == 0:
        print("❌ 没有TIPLOC坐标数据")
    elif api_positions == 0 and position_count > 0:
        print("⚠️  数据库有位置但API返回空 - 可能是查询或过滤问题")
    elif api_positions == 0 and position_count == 0:
        print("⚠️  没有位置数据 - 可能是坐标匹配问题")
    else:
        print("✅ 系统看起来正常")
    
    # 建议修复
    suggest_fixes()

if __name__ == "__main__":
    main()