#!/usr/bin/env python3
"""
实时WebSocket服务器
借鉴SignalBox.io的优化策略，提供高性能实时火车位置更新
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Set, List, Optional
import websockets
import sqlite3
from dataclasses import dataclass, asdict
import hashlib
import gzip
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TrainPosition:
    """优化的火车位置数据结构"""
    rid: str
    lat: float
    lon: float
    state: str
    ts: str
    speed: float = 0.0
    bearing: float = 0.0
    from_tpl: str = ""
    to_tpl: str = ""
    platform: str = ""

class PositionDelta:
    """位置变化检测器"""
    
    def __init__(self):
        self.last_positions: Dict[str, TrainPosition] = {}
        self.position_hashes: Dict[str, str] = {}
    
    def get_changes(self, current_positions: List[TrainPosition]) -> Dict[str, any]:
        """获取位置变化"""
        changes = {
            'added': [],      # 新增的火车
            'updated': [],    # 位置更新的火车
            'removed': [],    # 消失的火车
            'timestamp': datetime.now().isoformat()
        }
        
        current_rids = {pos.rid for pos in current_positions}
        last_rids = set(self.last_positions.keys())
        
        # 检测新增和更新
        for pos in current_positions:
            pos_hash = self._hash_position(pos)
            
            if pos.rid not in self.last_positions:
                # 新增的火车
                changes['added'].append(asdict(pos))
            elif self.position_hashes.get(pos.rid) != pos_hash:
                # 位置有变化的火车
                changes['updated'].append(asdict(pos))
            
            self.last_positions[pos.rid] = pos
            self.position_hashes[pos.rid] = pos_hash
        
        # 检测消失的火车
        removed_rids = last_rids - current_rids
        for rid in removed_rids:
            changes['removed'].append(rid)
            self.last_positions.pop(rid, None)
            self.position_hashes.pop(rid, None)
        
        return changes
    
    def _hash_position(self, pos: TrainPosition) -> str:
        """计算位置哈希值"""
        # 只对关键字段计算哈希，忽略微小变化
        key_data = f"{pos.rid}:{round(pos.lat, 4)}:{round(pos.lon, 4)}:{pos.state}:{pos.platform}"
        return hashlib.md5(key_data.encode()).hexdigest()

class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.connections: Set[websockets.WebSocketServerProtocol] = set()
        self.client_filters: Dict[websockets.WebSocketServerProtocol, dict] = {}
        self.delta_detector = PositionDelta()
        
    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """注册新连接"""
        self.connections.add(websocket)
        self.client_filters[websocket] = {}
        logger.info(f"新客户端连接，当前连接数: {len(self.connections)}")
        
        # 发送初始数据
        await self.send_initial_data(websocket)
    
    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """注销连接"""
        self.connections.discard(websocket)
        self.client_filters.pop(websocket, None)
        logger.info(f"客户端断开连接，当前连接数: {len(self.connections)}")
    
    async def send_initial_data(self, websocket: websockets.WebSocketServerProtocol):
        """发送初始数据"""
        try:
            # 获取当前所有火车位置
            positions = await self.get_current_positions()
            
            initial_data = {
                'type': 'initial',
                'data': [asdict(pos) for pos in positions],
                'count': len(positions),
                'timestamp': datetime.now().isoformat()
            }
            
            # 压缩大数据
            compressed_data = await self.compress_data(initial_data)
            await websocket.send(compressed_data)
            
        except Exception as e:
            logger.error(f"发送初始数据失败: {e}")
    
    async def broadcast_changes(self, positions: List[TrainPosition]):
        """广播位置变化"""
        if not self.connections:
            return
        
        # 检测变化
        changes = self.delta_detector.get_changes(positions)
        
        # 只有有变化时才广播
        if (changes['added'] or changes['updated'] or changes['removed']):
            message = {
                'type': 'delta',
                'changes': changes,
                'stats': {
                    'added': len(changes['added']),
                    'updated': len(changes['updated']),
                    'removed': len(changes['removed'])
                }
            }
            
            # 压缩数据
            compressed_data = await self.compress_data(message)
            
            # 并发发送给所有客户端
            if self.connections:
                await asyncio.gather(
                    *[self.send_to_client(ws, compressed_data) for ws in self.connections.copy()],
                    return_exceptions=True
                )
    
    async def send_to_client(self, websocket: websockets.WebSocketServerProtocol, data: str):
        """发送数据给单个客户端"""
        try:
            await websocket.send(data)
        except websockets.exceptions.ConnectionClosed:
            await self.unregister(websocket)
        except Exception as e:
            logger.error(f"发送数据失败: {e}")
            await self.unregister(websocket)
    
    async def compress_data(self, data: dict) -> str:
        """返回JSON数据（暂时禁用压缩）"""
        return json.dumps(data, separators=(',', ':'))
    
    async def get_current_positions(self) -> List[TrainPosition]:
        """从数据库获取当前位置"""
        try:
            # 连接到Darwin数据库
            with sqlite3.connect('data/database/train_positions.db') as conn:
                cursor = conn.execute("""
                    SELECT rid, lat, lon, state, ts, from_tpl, to_tpl, platform
                    FROM train_positions 
                    WHERE updated_at > datetime('now', '-6 hours')
                    ORDER BY updated_at DESC
                    LIMIT 2000
                """)
                
                positions = []
                for row in cursor.fetchall():
                    if row[1] and row[2]:  # 确保有坐标
                        pos = TrainPosition(
                            rid=row[0],
                            lat=float(row[1]),
                            lon=float(row[2]),
                            state=row[3] or 'unknown',
                            ts=row[4] or datetime.now().isoformat(),
                            from_tpl=row[5] or '',
                            to_tpl=row[6] or '',
                            platform=row[7] or ''
                        )
                        positions.append(pos)
                
                return positions
                
        except Exception as e:
            logger.error(f"获取位置数据失败: {e}")
            return []

class RealtimeServer:
    """实时WebSocket服务器"""
    
    def __init__(self, host='localhost', port=8002):
        self.host = host
        self.port = port
        self.ws_manager = WebSocketManager()
        self.running = False
        
    async def handle_client(self, websocket):
        """处理客户端连接"""
        await self.ws_manager.register(websocket)
        
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.ws_manager.unregister(websocket)
    
    async def handle_message(self, websocket, message):
        """处理客户端消息"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'ping':
                await websocket.send(json.dumps({'type': 'pong'}))
            elif msg_type == 'filter':
                # 设置客户端过滤器
                self.ws_manager.client_filters[websocket] = data.get('filters', {})
            elif msg_type == 'request_update':
                # 客户端请求立即更新
                await self.ws_manager.send_initial_data(websocket)
                
        except Exception as e:
            logger.error(f"处理客户端消息失败: {e}")
    
    async def position_update_loop(self):
        """位置更新循环"""
        while self.running:
            try:
                positions = await self.ws_manager.get_current_positions()
                await self.ws_manager.broadcast_changes(positions)
                
                # 根据连接数调整更新频率
                if len(self.ws_manager.connections) > 10:
                    await asyncio.sleep(2)  # 高负载时2秒更新
                else:
                    await asyncio.sleep(1)  # 低负载时1秒更新
                    
            except Exception as e:
                logger.error(f"位置更新循环错误: {e}")
                await asyncio.sleep(5)
    
    async def start_server(self):
        """启动服务器"""
        logger.info(f"🚀 启动实时WebSocket服务器 ws://{self.host}:{self.port}")
        
        self.running = True
        
        # 启动WebSocket服务器
        server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
            max_size=10**6,  # 1MB max message size
            compression='deflate'
        )
        
        # 启动位置更新循环
        update_task = asyncio.create_task(self.position_update_loop())
        
        logger.info(f"✅ WebSocket服务器运行在 ws://{self.host}:{self.port}")
        logger.info("📡 等待客户端连接...")
        
        try:
            await server.wait_closed()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在关闭服务器...")
        finally:
            self.running = False
            update_task.cancel()
            server.close()
            await server.wait_closed()

# HTTP API服务器（用于健康检查和统计）
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def create_api_app(ws_manager: WebSocketManager) -> FastAPI:
    """创建API应用"""
    app = FastAPI(title="Realtime Train WebSocket API")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    def root():
        return {
            "service": "实时火车位置WebSocket服务",
            "websocket_url": "ws://localhost:8002",
            "connections": len(ws_manager.connections),
            "status": "running"
        }
    
    @app.get("/stats")
    def get_stats():
        return {
            "active_connections": len(ws_manager.connections),
            "total_trains": len(ws_manager.delta_detector.last_positions),
            "server_time": datetime.now().isoformat()
        }
    
    @app.get("/health")
    def health_check():
        return {"status": "ok", "connections": len(ws_manager.connections)}
    
    return app

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="实时WebSocket火车位置服务器")
    parser.add_argument("--host", default="localhost", help="服务器主机")
    parser.add_argument("--ws-port", type=int, default=8002, help="WebSocket端口")
    parser.add_argument("--api-port", type=int, default=8003, help="API端口")
    
    args = parser.parse_args()
    
    # 创建服务器
    server = RealtimeServer(args.host, args.ws_port)
    
    # 创建API应用
    api_app = create_api_app(server.ws_manager)
    
    # 启动API服务器
    import uvicorn
    api_config = uvicorn.Config(
        api_app, 
        host=args.host, 
        port=args.api_port,
        log_level="info"
    )
    api_server = uvicorn.Server(api_config)
    
    # 并发运行WebSocket和API服务器
    await asyncio.gather(
        server.start_server(),
        api_server.serve()
    )

if __name__ == "__main__":
    asyncio.run(main())