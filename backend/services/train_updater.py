#!/usr/bin/env python3
"""
智能火车位置更新器
- 初始化时获取所有火车位置
- 运行时按时间间隔增量更新
- 支持环境变量配置
"""

import os
import json
import time
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
import sqlite3
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class UpdateConfig:
    """更新配置"""
    # 基础配置
    api_base_url: str = os.getenv("TRAIN_API_URL", "http://localhost:8000")
    db_path: str = os.getenv("TRAIN_DB_PATH", "train_positions.db")
    
    # 更新间隔配置（秒）
    initial_update_interval: int = int(os.getenv("INITIAL_UPDATE_INTERVAL", "30"))  # 初始化时30秒更新一次
    normal_update_interval: int = int(os.getenv("NORMAL_UPDATE_INTERVAL", "60"))    # 正常运行时60秒更新一次
    slow_update_interval: int = int(os.getenv("SLOW_UPDATE_INTERVAL", "300"))       # 深夜时5分钟更新一次
    
    # 时间段配置
    peak_hours_start: int = int(os.getenv("PEAK_HOURS_START", "6"))    # 早高峰开始时间
    peak_hours_end: int = int(os.getenv("PEAK_HOURS_END", "22"))       # 晚高峰结束时间
    
    # 数据保留配置
    max_position_age_hours: int = int(os.getenv("MAX_POSITION_AGE_HOURS", "24"))
    max_history_records: int = int(os.getenv("MAX_HISTORY_RECORDS", "10000"))
    
    # 性能配置
    batch_size: int = int(os.getenv("UPDATE_BATCH_SIZE", "100"))
    max_concurrent_requests: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    
    # 初始化配置
    full_sync_on_startup: bool = os.getenv("FULL_SYNC_ON_STARTUP", "true").lower() == "true"
    initial_data_age_minutes: int = int(os.getenv("INITIAL_DATA_AGE_MINUTES", "1440"))  # 24小时

class TrainPositionCache:
    """火车位置缓存"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.positions: Dict[str, dict] = {}  # rid -> position
        self.last_seen: Dict[str, datetime] = {}  # rid -> last_update_time
        self.position_history: Dict[str, List[dict]] = {}  # rid -> [positions]
        
    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 创建位置历史表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS position_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rid TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    state TEXT,
                    from_tpl TEXT,
                    to_tpl TEXT,
                    platform TEXT,
                    speed REAL,
                    bearing REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_rid_timestamp 
                ON position_history(rid, timestamp)
            """)
            
            # 创建当前位置表（快速查询）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS current_positions (
                    rid TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    state TEXT,
                    from_tpl TEXT,
                    to_tpl TEXT,
                    platform TEXT,
                    speed REAL,
                    bearing REAL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    def update_position(self, rid: str, position: dict):
        """更新火车位置"""
        old_position = self.positions.get(rid)
        self.positions[rid] = position
        self.last_seen[rid] = datetime.now()
        
        # 计算速度和方向（如果有历史位置）
        if old_position and 'lat' in old_position and 'lon' in old_position:
            speed, bearing = self._calculate_movement(old_position, position)
            position['speed'] = speed
            position['bearing'] = bearing
        
        # 保存到历史记录
        if rid not in self.position_history:
            self.position_history[rid] = []
        
        self.position_history[rid].append({
            **position,
            'timestamp': datetime.now().isoformat()
        })
        
        # 限制历史记录数量
        if len(self.position_history[rid]) > 50:
            self.position_history[rid] = self.position_history[rid][-50:]
    
    def _calculate_movement(self, old_pos: dict, new_pos: dict) -> tuple:
        """计算速度和方向"""
        try:
            from math import radians, cos, sin, asin, sqrt, atan2, degrees
            
            # 计算距离（Haversine公式）
            lat1, lon1 = radians(old_pos['lat']), radians(old_pos['lon'])
            lat2, lon2 = radians(new_pos['lat']), radians(new_pos['lon'])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            distance_km = 2 * asin(sqrt(a)) * 6371  # 地球半径
            
            # 计算时间差
            old_time = datetime.fromisoformat(old_pos.get('ts', datetime.now().isoformat()))
            new_time = datetime.fromisoformat(new_pos.get('ts', datetime.now().isoformat()))
            time_diff_hours = (new_time - old_time).total_seconds() / 3600
            
            # 计算速度 (km/h)
            speed = distance_km / time_diff_hours if time_diff_hours > 0 else 0
            
            # 计算方向
            y = sin(dlon) * cos(lat2)
            x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
            bearing = (degrees(atan2(y, x)) + 360) % 360
            
            return speed, bearing
            
        except Exception as e:
            logger.debug(f"计算移动参数失败: {e}")
            return 0.0, 0.0
    
    def get_active_trains(self, max_age_minutes: int = 60) -> List[dict]:
        """获取活跃的火车"""
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        active_trains = []
        
        for rid, last_seen in self.last_seen.items():
            if last_seen >= cutoff_time and rid in self.positions:
                active_trains.append({
                    'rid': rid,
                    'last_seen': last_seen.isoformat(),
                    **self.positions[rid]
                })
        
        return active_trains
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """清理旧数据"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # 清理内存中的旧数据
        old_rids = []
        for rid, last_seen in self.last_seen.items():
            if last_seen < cutoff_time:
                old_rids.append(rid)
        
        for rid in old_rids:
            self.positions.pop(rid, None)
            self.last_seen.pop(rid, None)
            self.position_history.pop(rid, None)
        
        logger.info(f"清理了 {len(old_rids)} 个旧的火车记录")
        
        # 清理数据库中的旧数据
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM position_history WHERE created_at < ?",
                (cutoff_time.isoformat(),)
            )
            logger.info(f"从数据库清理了 {cursor.rowcount} 条历史记录")

class SmartTrainUpdater:
    """智能火车更新器"""
    
    def __init__(self, config: UpdateConfig):
        self.config = config
        self.cache = TrainPositionCache(config.db_path)
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.last_full_sync = None
        
    async def start(self):
        """启动更新器"""
        logger.info("🚂 启动智能火车位置更新器")
        
        # 初始化数据库
        self.cache.init_db()
        
        # 创建HTTP会话
        connector = aiohttp.TCPConnector(limit=self.config.max_concurrent_requests)
        self.session = aiohttp.ClientSession(connector=connector)
        
        self.running = True
        
        try:
            # 初始化：获取所有火车位置
            if self.config.full_sync_on_startup:
                await self.full_sync()
            
            # 开始增量更新循环
            await self.update_loop()
            
        except Exception as e:
            logger.error(f"更新器运行失败: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """停止更新器"""
        logger.info("停止火车位置更新器")
        self.running = False
        
        if self.session:
            await self.session.close()
    
    async def full_sync(self):
        """完整同步所有火车位置"""
        logger.info("🔄 开始完整同步火车位置...")
        
        try:
            url = f"{self.config.api_base_url}/positions"
            params = {
                'limit': 10000,  # 获取更多数据
                'max_age_minutes': self.config.initial_data_age_minutes
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    positions = await response.json()
                    
                    logger.info(f"📥 获取到 {len(positions)} 个火车位置")
                    
                    # 批量更新缓存
                    for position in positions:
                        rid = position.get('rid')
                        if rid:
                            self.cache.update_position(rid, position)
                    
                    self.last_full_sync = datetime.now()
                    logger.info(f"✅ 完整同步完成，缓存了 {len(self.cache.positions)} 个火车位置")
                    
                else:
                    logger.error(f"获取火车位置失败: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"完整同步失败: {e}")
    
    async def incremental_update(self):
        """增量更新火车位置"""
        try:
            # 获取最近更新的位置
            url = f"{self.config.api_base_url}/positions"
            params = {
                'limit': 1000,
                'max_age_minutes': 30  # 只获取最近30分钟的更新
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    positions = await response.json()
                    
                    # 检查哪些是新的或更新的位置
                    new_count = 0
                    updated_count = 0
                    
                    for position in positions:
                        rid = position.get('rid')
                        if not rid:
                            continue
                        
                        # 检查是否是新位置或位置有变化
                        old_position = self.cache.positions.get(rid)
                        if not old_position:
                            new_count += 1
                        elif self._position_changed(old_position, position):
                            updated_count += 1
                        else:
                            continue  # 位置没有变化，跳过
                        
                        self.cache.update_position(rid, position)
                    
                    if new_count > 0 or updated_count > 0:
                        logger.info(f"📍 增量更新: {new_count} 新火车, {updated_count} 位置变化")
                    
                else:
                    logger.warning(f"增量更新失败: HTTP {response.status}")
                    
        except Exception as e:
            logger.error(f"增量更新失败: {e}")
    
    def _position_changed(self, old_pos: dict, new_pos: dict) -> bool:
        """检查位置是否有显著变化"""
        # 检查坐标变化（精度到小数点后4位，约11米）
        old_lat = round(old_pos.get('lat', 0), 4)
        old_lon = round(old_pos.get('lon', 0), 4)
        new_lat = round(new_pos.get('lat', 0), 4)
        new_lon = round(new_pos.get('lon', 0), 4)
        
        if old_lat != new_lat or old_lon != new_lon:
            return True
        
        # 检查状态变化
        if old_pos.get('state') != new_pos.get('state'):
            return True
        
        # 检查站台变化
        if old_pos.get('platform') != new_pos.get('platform'):
            return True
        
        return False
    
    def get_current_update_interval(self) -> int:
        """根据当前时间获取更新间隔"""
        current_hour = datetime.now().hour
        
        # 深夜时段（23:00-05:00）使用慢速更新
        if current_hour >= 23 or current_hour < 5:
            return self.config.slow_update_interval
        
        # 高峰时段使用正常更新
        elif self.config.peak_hours_start <= current_hour <= self.config.peak_hours_end:
            return self.config.normal_update_interval
        
        # 其他时段使用慢速更新
        else:
            return self.config.slow_update_interval
    
    async def update_loop(self):
        """主更新循环"""
        logger.info("🔄 开始增量更新循环")
        
        while self.running:
            try:
                # 执行增量更新
                await self.incremental_update()
                
                # 定期清理旧数据
                if datetime.now().minute % 30 == 0:  # 每30分钟清理一次
                    self.cache.cleanup_old_data(self.config.max_position_age_hours)
                
                # 定期完整同步（每6小时）
                if (self.last_full_sync is None or 
                    datetime.now() - self.last_full_sync > timedelta(hours=6)):
                    await self.full_sync()
                
                # 根据时间段调整更新间隔
                interval = self.get_current_update_interval()
                logger.debug(f"下次更新间隔: {interval}秒")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"更新循环错误: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟再重试
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'total_trains': len(self.cache.positions),
            'active_trains_1h': len(self.cache.get_active_trains(60)),
            'active_trains_6h': len(self.cache.get_active_trains(360)),
            'last_full_sync': self.last_full_sync.isoformat() if self.last_full_sync else None,
            'current_update_interval': self.get_current_update_interval(),
            'config': asdict(self.config)
        }

# API端点
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# 全局更新器实例
updater: Optional[SmartTrainUpdater] = None

def create_updater_app() -> FastAPI:
    """创建更新器API应用"""
    app = FastAPI(title="Smart Train Position Updater")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.on_event("startup")
    async def startup_event():
        global updater
        config = UpdateConfig()
        updater = SmartTrainUpdater(config)
        # 在后台启动更新器
        asyncio.create_task(updater.start())
    
    @app.on_event("shutdown")
    async def shutdown_event():
        global updater
        if updater:
            await updater.stop()
    
    @app.get("/")
    def root():
        return {
            "service": "Smart Train Position Updater",
            "version": "1.0",
            "description": "智能火车位置更新服务"
        }
    
    @app.get("/positions")
    def get_positions(
        limit: int = Query(default=1000, description="最大返回数量"),
        max_age_minutes: int = Query(default=60, description="最大数据年龄（分钟）")
    ):
        """获取当前火车位置"""
        if not updater:
            return []
        
        active_trains = updater.cache.get_active_trains(max_age_minutes)
        return active_trains[:limit]
    
    @app.get("/stats")
    def get_stats():
        """获取更新器统计信息"""
        if not updater:
            return {"error": "更新器未启动"}
        
        return updater.get_stats()
    
    @app.post("/sync")
    async def force_sync():
        """强制执行完整同步"""
        if not updater:
            return {"error": "更新器未启动"}
        
        await updater.full_sync()
        return {"message": "完整同步已执行"}
    
    return app

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能火车位置更新器")
    parser.add_argument("--config-file", help="配置文件路径")
    parser.add_argument("--api-mode", action="store_true", help="以API模式运行")
    
    args = parser.parse_args()
    
    if args.api_mode:
        # API模式
        import uvicorn
        app = create_updater_app()
        uvicorn.run(app, host="0.0.0.0", port=8001)
    else:
        # 独立模式
        config = UpdateConfig()
        updater = SmartTrainUpdater(config)
        
        try:
            await updater.start()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在停止...")
            await updater.stop()

if __name__ == "__main__":
    asyncio.run(main())