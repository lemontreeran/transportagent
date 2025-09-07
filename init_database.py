#!/usr/bin/env python3
"""
数据库初始化脚本
初始化火车追踪系统所需的所有数据库表和基础数据
"""

import sqlite3
import os
import sys
from pathlib import Path

# 添加backend路径到sys.path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from utils.tiploc_mapper import CRSTiplocMapper
from utils.tiploc_loader import TiplocDataLoader
from services.train_updater import TrainPositionCache

def init_database():
    """初始化数据库"""
    db_path = "Data/database/train_positions.db"
    
    print("🚀 开始初始化数据库...")
    
    # 确保数据库目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 1. 初始化基础表结构
    print("📊 创建基础表结构...")
    cache = TrainPositionCache(db_path)
    cache.init_db()
    
    # 2. 创建TIPLOC坐标表
    print("🗺️  创建TIPLOC坐标表...")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tiploc_coords (
                tiploc_code TEXT PRIMARY KEY,
                lat REAL,
                lon REAL,
                station_name TEXT,
                source TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # 3. 创建CRS到TIPLOC映射
    print("🔗 创建CRS到TIPLOC映射...")
    mapper = CRSTiplocMapper(db_path)
    stations_file = "Data/static/stations.json"
    
    if os.path.exists(stations_file):
        mapping_count = mapper.create_mapping_database(stations_file)
        print(f"✅ 创建了 {mapping_count} 个CRS到TIPLOC映射")
    else:
        print(f"⚠️  警告: 找不到 {stations_file}，跳过CRS映射创建")
    
    # 4. 加载TIPLOC坐标数据
    print("📍 加载TIPLOC坐标数据...")
    loader = TiplocDataLoader(db_path)
    coord_count = loader.update_database()
    print(f"✅ 更新了 {coord_count} 个TIPLOC坐标")
    
    # 5. 检查数据库状态
    print("🔍 检查数据库状态...")
    with sqlite3.connect(db_path) as conn:
        # 检查各表的记录数
        tables = [
            ('position_history', '位置历史'),
            ('current_positions', '当前位置'),
            ('crs_tiploc_mapping', 'CRS映射'),
            ('tiploc_coords', 'TIPLOC坐标')
        ]
        
        for table_name, display_name in tables:
            try:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  📋 {display_name}: {count} 条记录")
            except sqlite3.OperationalError:
                print(f"  ❌ {display_name}: 表不存在")
    
    print("🎉 数据库初始化完成！")
    print(f"📁 数据库文件: {db_path}")
    print("\n现在可以启动系统了:")
    print("  python3 start.py")

if __name__ == "__main__":
    try:
        init_database()
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        sys.exit(1)