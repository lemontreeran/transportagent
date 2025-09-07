import os
import json
import threading
import time
import logging
from datetime import datetime, date, timezone, timedelta
from typing import Dict, Tuple, Optional, List, Any
from pathlib import Path
import sqlite3
from dataclasses import dataclass, asdict

from confluent_kafka import Consumer
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

"""
Realtime Darwin (JSON topic) -> train position estimator + HTTP API
- Consumes Kafka JSON (RDM Darwin Push Port JSON topic)
- Normalizes payload (wrapper with/without `bytes`; Location list/object)
- Estimates realtime position via time interpolation between TIPLOCs
- Exposes /positions & debug endpoints for quick inspection

Run:
  pip install confluent_kafka fastapi uvicorn pydantic
  export KAFKA_USERNAME=...
  export KAFKA_PASSWORD=...
  export KAFKA_GROUP=SC-062cd84d-9e2f-41ae-a702-d3f9c1a72cc3
  uvicorn darwin_realtime_consumer:app --host 0.0.0.0 --port 8000
"""

# ===== Configuration ===== #
@dataclass
class Config:
    # Kafka配置
    bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "pkc-z3p1v0.europe-west2.gcp.confluent.cloud:9092")
    topic: str = os.getenv("KAFKA_TOPIC", "prod-1010-Darwin-Train-Information-Push-Port-IIII2_0-JSON")
    username: str = os.getenv("KAFKA_USERNAME", "")
    password: str = os.getenv("KAFKA_PASSWORD", "")
    group_id: str = os.getenv("KAFKA_GROUP", "SC-062cd84d-9e2f-41ae-a702-d3f9c1a72cc3")
    auto_reset: str = os.getenv("KAFKA_AUTO_OFFSET", "earliest")
    
    # 更新配置
    update_interval: int = int(os.getenv("UPDATE_INTERVAL", "300"))  # 5分钟默认
    max_age_hours: int = int(os.getenv("MAX_AGE_HOURS", "24"))  # 24小时后清理旧数据
    
    # 数据库配置
    db_path: str = os.getenv("DB_PATH", "data/database/train_positions.db")
    
    # 日志配置
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

config = Config()

# 设置日志
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== 数据库管理 ===== #
class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS train_positions (
                    rid TEXT PRIMARY KEY,
                    uid TEXT,
                    ts TEXT,
                    from_tpl TEXT,
                    to_tpl TEXT,
                    lat REAL,
                    lon REAL,
                    ratio REAL,
                    state TEXT,
                    platform TEXT,
                    updated_at TEXT,
                    raw_data TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tiploc_coords (
                    tiploc TEXT PRIMARY KEY,
                    lat REAL,
                    lon REAL,
                    name TEXT,
                    source TEXT,
                    updated_at TEXT
                )
            """)
            
            # 插入一些基础TIPLOC坐标
            self.load_default_tiplocs()
    
    def load_default_tiplocs(self):
        """加载默认的TIPLOC坐标"""
        default_tiplocs = [
            ("CRLN", 51.4863, 0.0361, "Charlton", "manual"),
            ("WOLWCDY", 51.4909, 0.0540, "Woolwich Dockyard", "manual"),
            ("WOLWCHA", 51.4916, 0.0694, "Woolwich Arsenal", "manual"),
            ("TUTBURY", 52.8730, -1.6870, "Tutbury & Hatton", "manual"),
            ("LONDON", 51.5074, -0.1278, "London", "manual"),
            ("BRMNGM", 52.4862, -1.8904, "Birmingham", "manual"),
            ("MNCHSTR", 53.4808, -2.2426, "Manchester", "manual"),
            ("EDINBGH", 55.9533, -3.1883, "Edinburgh", "manual"),
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            for tiploc, lat, lon, name, source in default_tiplocs:
                conn.execute("""
                    INSERT OR IGNORE INTO tiploc_coords 
                    (tiploc, lat, lon, name, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tiploc, lat, lon, name, source, datetime.now().isoformat()))
    
    def get_tiploc_coords(self, tiploc: str) -> Optional[Tuple[float, float]]:
        """获取TIPLOC坐标"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT lat, lon FROM tiploc_coords WHERE tiploc = ?", 
                (tiploc,)
            )
            result = cursor.fetchone()
            return (result[0], result[1]) if result else None
    
    def save_position(self, position_data: dict):
        """保存位置数据到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO train_positions 
                (rid, uid, ts, from_tpl, to_tpl, lat, lon, ratio, state, platform, updated_at, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_data.get("rid"),
                position_data.get("uid"),
                position_data.get("ts"),
                position_data.get("from_tpl"),
                position_data.get("to_tpl"),
                position_data.get("lat"),
                position_data.get("lon"),
                position_data.get("ratio"),
                position_data.get("state"),
                position_data.get("platform"),
                datetime.now().isoformat(),
                json.dumps(position_data)
            ))
    
    def get_all_positions(self, max_age_hours: int = 24) -> List[dict]:
        """获取所有位置数据"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT rid, uid, ts, from_tpl, to_tpl, lat, lon, ratio, state, platform, updated_at
                FROM train_positions 
                WHERE updated_at > ?
                ORDER BY updated_at DESC
            """, (cutoff_time.isoformat(),))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, max_age_hours: int = 24):
        """清理旧数据"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM train_positions WHERE updated_at < ?",
                (cutoff_time.isoformat(),)
            )
            deleted_count = cursor.rowcount
            logger.info(f"清理了 {deleted_count} 条旧的位置记录")

# 初始化数据库管理器
db_manager = DatabaseManager(config.db_path)

# ===== 状态管理 ===== #
class StateManager:
    def __init__(self):
        self.latest: Dict[str, dict] = {}  # rid -> latest position snapshot
        self.last_wrapper: Optional[dict] = None
        self.last_payload: Optional[dict] = None
        self.last_error: Optional[str] = None
        self.message_count: int = 0
        self.error_count: int = 0
        self.last_update: Optional[datetime] = None
        self.consumer_active: bool = False
        
    def update_position(self, rid: str, position_data: dict):
        """更新位置数据"""
        self.latest[rid] = position_data
        self.last_update = datetime.now()
        
        # 保存到数据库
        try:
            db_manager.save_position(position_data)
        except Exception as e:
            logger.error(f"保存位置数据到数据库失败: {e}")
    
    def get_all_positions(self) -> List[dict]:
        """获取所有位置数据（内存+数据库）"""
        # 合并内存中的数据和数据库中的数据
        memory_positions = list(self.latest.values())
        db_positions = db_manager.get_all_positions(config.max_age_hours)
        
        # 使用rid去重，优先使用内存中的数据
        positions_dict = {}
        
        # 先添加数据库中的数据
        for pos in db_positions:
            positions_dict[pos['rid']] = pos
        
        # 再添加内存中的数据（会覆盖数据库中的旧数据）
        for pos in memory_positions:
            positions_dict[pos['rid']] = pos
        
        return list(positions_dict.values())
    
    def cleanup_old_positions(self):
        """清理旧的位置数据"""
        cutoff_time = datetime.now() - timedelta(hours=config.max_age_hours)
        
        # 清理内存中的旧数据
        old_rids = []
        for rid, pos in self.latest.items():
            try:
                pos_time = datetime.fromisoformat(pos.get('ts', ''))
                if pos_time < cutoff_time:
                    old_rids.append(rid)
            except:
                # 如果时间解析失败，也清理掉
                old_rids.append(rid)
        
        for rid in old_rids:
            del self.latest[rid]
        
        if old_rids:
            logger.info(f"从内存中清理了 {len(old_rids)} 条旧的位置记录")
        
        # 清理数据库中的旧数据
        db_manager.cleanup_old_data(config.max_age_hours)

state_manager = StateManager()

# ===== Helpers ===== #

def coord_of(tpl: str) -> Optional[Tuple[float, float]]:
    """获取TIPLOC坐标"""
    return db_manager.get_tiploc_coords(tpl)


def parse_time_hms_local(s: str, ssd: str, tzinfo: Optional[timezone]) -> datetime:
    """Convert "HH:MM" or "HH:MM:SS" + service date (ssd) -> timezone-aware datetime."""
    if not s:
        raise ValueError("empty time string")
    fmt = "%H:%M" if len(s) == 5 else "%H:%M:%S"
    t = datetime.strptime(s, fmt).time()
    base = datetime.fromisoformat(ssd).date() if ssd else date.today()
    return datetime.combine(base, t, tzinfo=tzinfo)


def pick_time(loc: dict, key: str, ssd: str, tzinfo: Optional[timezone]) -> Optional[datetime]:
    """Priority: actual (at/atd) > expected (et) > public timetable (pt[a|d]) > working timetable (wt[a|d|p])."""
    node = loc.get(key)
    if isinstance(node, dict):
        for cand in ("at", "et"):
            v = node.get(cand)
            if v:
                return parse_time_hms_local(v, ssd, tzinfo)
    # fallback to planned
    for cand in (f"pt{key[-1]}", f"wt{key[-1]}", "wtp"):
        v = loc.get(cand)
        if v:
            return parse_time_hms_local(v, ssd, tzinfo)
    return None


def find_prev_next(locations: List[dict], ssd: str, now: datetime) -> Optional[Tuple[dict, dict, datetime, datetime]]:
    """Find last departed (prev) and next arriving/passing (next), with their times (tz‑aware)."""
    prev = None
    for i, loc in enumerate(locations):
        dep = pick_time(loc, "dep", ssd, now.tzinfo)
        arr = pick_time(loc, "arr", ssd, now.tzinfo)
        pas = loc.get("pass") if isinstance(loc.get("pass"), dict) else None
        pas_t = None
        if pas:
            x = pas.get("at") or pas.get("et")
            if x:
                pas_t = parse_time_hms_local(x, ssd, now.tzinfo)
        left_time = dep or pas_t or arr
        if left_time and left_time <= now:
            prev = (i, loc, left_time)
        if prev and i > prev[0]:
            next_time = pick_time(loc, "arr", ssd, now.tzinfo)
            if not next_time and pas and pas.get("et"):
                next_time = parse_time_hms_local(pas["et"], ssd, now.tzinfo)
            if next_time and next_time >= now:
                return prev[1], loc, prev[2], next_time
    return None


def lerp(a: float, b: float, t: float) -> float:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return a + (b - a) * t


def estimate_position(prev_loc: dict, next_loc: dict, t0: datetime, t1: datetime, now: datetime) -> Optional[dict]:
    p = coord_of(prev_loc.get("tpl"))
    n = coord_of(next_loc.get("tpl"))
    if not p or not n:
        return None
    total = (t1 - t0).total_seconds()
    ratio = 1.0 if total <= 0 else (now - t0).total_seconds() / total
    lat = lerp(p[0], n[0], ratio)
    lon = lerp(p[1], n[1], ratio)
    state = "enroute"
    # Dwell if arrived at next but not yet departed
    dep_next = pick_time(next_loc, "dep", t1.date().isoformat(), now.tzinfo)
    arr_next = pick_time(next_loc, "arr", t1.date().isoformat(), now.tzinfo)
    if arr_next and arr_next <= now and (not dep_next or dep_next > now):
        lat, lon, state = n[0], n[1], "dwell"
    return {"lat": lat, "lon": lon, "ratio": max(0.0, min(1.0, ratio)), "state": state}


# ===== Kafka消费者管理 ===== #
class KafkaConsumerManager:
    def __init__(self):
        self.consumer = None
        self.running = False
        self.thread = None
        
    def create_consumer(self):
        """创建Kafka消费者"""
        if not config.username or not config.password:
            logger.warning("Kafka用户名或密码未设置，将使用模拟数据")
            return None
            
        return Consumer({
            "bootstrap.servers": config.bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "PLAIN",
            "sasl.username": config.username,
            "sasl.password": config.password,
            "group.id": config.group_id,
            "auto.offset.reset": config.auto_reset,
            # 健壮性配置
            "client.dns.lookup": "use_all_dns_ips",
            "broker.address.family": "v4",
            "socket.keepalive.enable": True,
            "session.timeout.ms": 30000,
            "heartbeat.interval.ms": 10000,
        })
    
    def start(self):
        """启动消费者"""
        if self.running:
            return
            
        self.consumer = self.create_consumer()
        if self.consumer:
            self.consumer.subscribe([config.topic])
            self.running = True
            self.thread = threading.Thread(target=self.consume_loop, daemon=True)
            self.thread.start()
            logger.info("Kafka消费者已启动")
        else:
            # 启动模拟数据生成器
            self.running = True
            self.thread = threading.Thread(target=self.mock_data_loop, daemon=True)
            self.thread.start()
            logger.info("模拟数据生成器已启动")
    
    def stop(self):
        """停止消费者"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        logger.info("Kafka消费者已停止")
    
    def consume_loop(self):
        """消费循环"""
        state_manager.consumer_active = True
        last_cleanup = datetime.now()
        
        while self.running:
            try:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                    
                if msg.error():
                    state_manager.last_error = str(msg.error())
                    state_manager.error_count += 1
                    logger.error(f"Kafka错误: {msg.error()}")
                    continue
                
                self.process_message(msg)
                
                # 定期清理旧数据
                if datetime.now() - last_cleanup > timedelta(hours=1):
                    state_manager.cleanup_old_positions()
                    last_cleanup = datetime.now()
                    
            except Exception as e:
                state_manager.last_error = str(e)
                state_manager.error_count += 1
                logger.error(f"消费消息时出错: {e}")
                time.sleep(5)  # 出错时等待5秒再重试
        
        state_manager.consumer_active = False
    
    def mock_data_loop(self):
        """模拟数据生成循环"""
        state_manager.consumer_active = True
        
        # 扩展的模拟火车数据，覆盖更多路线
        mock_trains = [
            {"rid": "MOCK001", "uid": "L12345", "route": [("LONDON", "BRMNGM")], "speed": 0.001},
            {"rid": "MOCK002", "uid": "L67890", "route": [("MNCHSTR", "LONDON")], "speed": 0.0008},
            {"rid": "MOCK003", "uid": "L11111", "route": [("EDINBGH", "LONDON")], "speed": 0.0012},
            {"rid": "MOCK004", "uid": "L22222", "route": [("LONDON", "EDINBGH")], "speed": 0.0009},
            {"rid": "MOCK005", "uid": "L33333", "route": [("BRMNGM", "MNCHSTR")], "speed": 0.0007},
            {"rid": "MOCK006", "uid": "L44444", "route": [("LONDON", "MNCHSTR")], "speed": 0.0011},
            {"rid": "MOCK007", "uid": "L55555", "route": [("EDINBGH", "BRMNGM")], "speed": 0.0006},
            {"rid": "MOCK008", "uid": "L66666", "route": [("MNCHSTR", "EDINBGH")], "speed": 0.0010},
            {"rid": "MOCK009", "uid": "L77777", "route": [("BRMNGM", "LONDON")], "speed": 0.0013},
            {"rid": "MOCK010", "uid": "L88888", "route": [("LONDON", "CRLN")], "speed": 0.0015},
            {"rid": "MOCK011", "uid": "L99999", "route": [("CRLN", "WOLWCHA")], "speed": 0.0008},
            {"rid": "MOCK012", "uid": "L00000", "route": [("WOLWCHA", "LONDON")], "speed": 0.0012},
        ]
        
        # 为每个火车初始化进度
        for train in mock_trains:
            train["progress"] = 0.0  # 初始进度
            train["direction"] = 1   # 1为正向，-1为反向
        
        while self.running:
            try:
                import random
                
                for train in mock_trains:
                    # 生成模拟位置数据
                    from_tpl, to_tpl = train["route"][0]
                    from_coords = coord_of(from_tpl)
                    to_coords = coord_of(to_tpl)
                    
                    if from_coords and to_coords:
                        # 更新火车进度（模拟真实移动）
                        speed = train.get("speed", 0.001)
                        direction = train.get("direction", 1)
                        
                        # 更新进度
                        train["progress"] += speed * direction
                        
                        # 到达终点时反向
                        if train["progress"] >= 1.0:
                            train["progress"] = 1.0
                            train["direction"] = -1
                        elif train["progress"] <= 0.0:
                            train["progress"] = 0.0
                            train["direction"] = 1
                        
                        # 计算当前位置
                        ratio = train["progress"]
                        lat = from_coords[0] + (to_coords[0] - from_coords[0]) * ratio
                        lon = from_coords[1] + (to_coords[1] - from_coords[1]) * ratio
                        
                        # 确定状态
                        if ratio <= 0.05 or ratio >= 0.95:
                            state = "dwell"  # 在车站停靠
                        elif train["direction"] == 1:
                            state = "enroute"
                        else:
                            state = "enroute"
                        
                        # 随机添加一些停靠状态
                        if random.random() < 0.1:  # 10%概率停靠
                            state = "stopped"
                        
                        position_data = {
                            "rid": train["rid"],
                            "uid": train["uid"],
                            "ts": datetime.now().isoformat(),
                            "from_tpl": from_tpl if direction == 1 else to_tpl,
                            "to_tpl": to_tpl if direction == 1 else from_tpl,
                            "lat": lat,
                            "lon": lon,
                            "ratio": ratio,
                            "state": state,
                            "platform": random.choice([None, "1", "2", "3", "4", "5"]) if state == "dwell" else None,
                        }
                        
                        state_manager.update_position(train["rid"], position_data)
                        state_manager.message_count += 1
                
                # 使用较短的更新间隔进行演示（10秒）
                demo_interval = min(10, config.update_interval)
                time.sleep(demo_interval)
                
            except Exception as e:
                logger.error(f"生成模拟数据时出错: {e}")
                time.sleep(30)
        
        state_manager.consumer_active = False
    
    def process_message(self, msg):
        """处理Kafka消息"""
        try:
            wrapper = json.loads(msg.value().decode("utf-8"))
            state_manager.last_wrapper = wrapper
            state_manager.message_count += 1
            
            raw = wrapper.get("bytes")
            data = json.loads(raw) if raw else wrapper
            state_manager.last_payload = data

            # 使用消息时间戳作为时间基准
            ts_iso = data.get("ts")
            try:
                now = datetime.fromisoformat(ts_iso) if ts_iso else datetime.utcnow().replace(tzinfo=timezone.utc)
            except Exception:
                now = datetime.utcnow().replace(tzinfo=timezone.utc)

            uR = data.get("uR", {})
            TS = uR.get("TS") or {}
            rid = TS.get("rid")
            uid = TS.get("uid")
            ssd = TS.get("ssd") or now.date().isoformat()
            locs: Any = TS.get("Location") or []
            
            # 标准化Location为列表
            if isinstance(locs, dict):
                locs = [locs]
            if not rid or not locs:
                return

            res = find_prev_next(locs, ssd, now)
            if not res:
                # 单站更新：视为停靠
                if len(locs) == 1:
                    only = locs[0]
                    tpl = only.get("tpl")
                    coords = coord_of(tpl)
                    if coords:
                        plat = only.get("plat")
                        platform = plat if isinstance(plat, str) else (plat.get("") if isinstance(plat, dict) else None)
                        position_data = {
                            "rid": rid,
                            "uid": uid,
                            "ts": ts_iso or now.isoformat(),
                            "from_tpl": tpl,
                            "to_tpl": tpl,
                            "lat": coords[0],
                            "lon": coords[1],
                            "ratio": 0.0,
                            "state": "dwell",
                            "platform": platform,
                        }
                        state_manager.update_position(rid, position_data)
                    # 不再记录警告，静默跳过没有坐标的站点
                return

            prev_loc, next_loc, t0, t1 = res
            pos = estimate_position(prev_loc, next_loc, t0, t1, now)
            if not pos:
                # 回退：固定到有坐标的端点
                p = coord_of(prev_loc.get("tpl"))
                n = coord_of(next_loc.get("tpl"))
                if n or p:
                    lat, lon = (n or p)
                    pos = {"lat": lat, "lon": lon, "ratio": 0.0, "state": "unknown"}
                else:
                    # 静默跳过没有坐标数据的火车，不记录警告
                    return

            # 平台信息处理
            plat = None
            pfield = prev_loc.get("plat")
            if isinstance(pfield, str):
                plat = pfield
            elif isinstance(pfield, dict):
                plat = pfield.get("") or pfield.get("plat")

            position_data = {
                "rid": rid,
                "uid": uid,
                "ts": ts_iso or now.isoformat(),
                "from_tpl": prev_loc.get("tpl"),
                "to_tpl": next_loc.get("tpl"),
                "lat": pos["lat"],
                "lon": pos["lon"],
                "ratio": pos["ratio"],
                "state": pos["state"],
                "platform": plat,
            }
            
            state_manager.update_position(rid, position_data)
            
        except Exception as e:
            state_manager.last_error = str(e)
            state_manager.error_count += 1
            logger.error(f"处理消息时出错: {e}")

# ===== FastAPI for Google Maps polling ===== #
app = FastAPI(title="Darwin Train Realtime Locator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 应用启动和关闭处理 ===== #
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("🚂 Darwin实时火车位置服务启动")
    logger.info(f"配置: 更新间隔={config.update_interval}秒, 最大数据年龄={config.max_age_hours}小时")
    
    # 清理启动时的旧数据
    try:
        state_manager.cleanup_old_positions()
        logger.info("启动时数据清理完成")
    except Exception as e:
        logger.error(f"启动时数据清理失败: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("正在关闭Darwin实时火车位置服务...")
    kafka_manager.stop()
    logger.info("服务已关闭")

# 创建并启动Kafka消费者管理器
kafka_manager = KafkaConsumerManager()
kafka_manager.start()

# ===== 根端点 ===== #
@app.get("/")
def root():
    """根端点，提供API信息"""
    return {
        "service": "Darwin实时火车位置服务",
        "version": "2.0",
        "endpoints": {
            "positions": "/positions - 获取所有火车位置",
            "position": "/positions/{rid} - 获取特定火车位置",
            "config": "/config - 获取配置信息",
            "stats": "/debug/stats - 获取统计信息",
            "tiplocs": "/tiplocs - 获取TIPLOC坐标",
            "health": "/health - 健康检查"
        },
        "features": [
            "实时位置估算",
            "可配置更新间隔",
            "数据持久化",
            "自动数据清理",
            "模拟数据支持"
        ]
    }


class Position(BaseModel):
    rid: str
    uid: Optional[str] = None
    ts: str
    from_tpl: str
    to_tpl: str
    lat: float
    lon: float
    ratio: float
    state: str
    platform: Optional[str] = None


@app.get("/positions")
def get_positions(
    limit: int = Query(default=1000, description="最大返回数量"),
    state: Optional[str] = Query(default=None, description="按状态过滤 (enroute, dwell, stopped)"),
    max_age_minutes: int = Query(default=1440, description="最大数据年龄（分钟）")
):
    """获取所有火车位置"""
    try:
        positions = state_manager.get_all_positions()
        
        # 按时间过滤
        cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
        filtered_positions = []
        
        for pos in positions:
            try:
                # 尝试解析时间戳，优先使用updated_at（更可靠）
                pos_time_str = pos.get('updated_at') or pos.get('ts', '')
                if not pos_time_str:
                    continue
                
                # 处理不同的时间戳格式
                if '+' in pos_time_str and 'T' in pos_time_str:
                    # 处理带时区的ISO格式: 2025-09-05T13:33:01.3680409+01:00
                    pos_time = datetime.fromisoformat(pos_time_str.replace('+01:00', '+00:00'))
                else:
                    # 处理标准ISO格式: 2025-09-06T00:40:25.841988
                    pos_time = datetime.fromisoformat(pos_time_str)
                
                # 如果没有时区信息，假设为UTC
                if pos_time.tzinfo is None:
                    pos_time = pos_time.replace(tzinfo=timezone.utc)
                
                # 转换为当前时区进行比较
                now_utc = datetime.now(timezone.utc)
                cutoff_utc = now_utc - timedelta(minutes=max_age_minutes)
                
                if pos_time >= cutoff_utc:
                    # 按状态过滤
                    if state is None or pos.get('state') == state:
                        filtered_positions.append(pos)
            except Exception as e:
                # 如果时间解析失败，记录错误但继续处理
                logger.debug(f"时间解析失败 {pos.get('rid', 'unknown')}: {e}")
                continue
        
        # 按时间排序并限制数量
        filtered_positions.sort(key=lambda x: x.get('ts', ''), reverse=True)
        return filtered_positions[:limit]
        
    except Exception as e:
        logger.error(f"获取位置数据时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions/{rid}", response_model=Position)
def get_position(rid: str):
    """获取特定火车的位置"""
    try:
        # 先从内存中查找
        position = state_manager.latest.get(rid)
        if position:
            return position
        
        # 如果内存中没有，从数据库查找
        positions = db_manager.get_all_positions(config.max_age_hours)
        for pos in positions:
            if pos['rid'] == rid:
                return pos
        
        raise HTTPException(status_code=404, detail=f"火车 {rid} 未找到")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取火车 {rid} 位置时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Debug endpoints ----
@app.get("/health")
def health():
    return {
        "status": "ok", 
        "bootstrap": config.bootstrap, 
        "topic": config.topic,
        "consumer_active": state_manager.consumer_active,
        "trains_count": len(state_manager.latest)
    }

@app.get("/config")
def get_config():
    """获取当前配置"""
    return {
        "update_interval": config.update_interval,
        "max_age_hours": config.max_age_hours,
        "db_path": config.db_path,
        "log_level": config.log_level,
        "kafka_configured": bool(config.username and config.password),
    }

@app.post("/config/update-interval/{seconds}")
def update_interval(seconds: int):
    """更新数据更新间隔"""
    if seconds < 60:  # 最小1分钟
        raise HTTPException(status_code=400, detail="更新间隔不能少于60秒")
    if seconds > 3600:  # 最大1小时
        raise HTTPException(status_code=400, detail="更新间隔不能超过3600秒")
    
    config.update_interval = seconds
    logger.info(f"更新间隔已设置为 {seconds} 秒")
    return {"message": f"更新间隔已设置为 {seconds} 秒", "update_interval": seconds}

@app.get("/debug/stats")
def debug_stats():
    """获取系统统计信息"""
    return {
        "trains_in_memory": len(state_manager.latest),
        "total_messages": state_manager.message_count,
        "error_count": state_manager.error_count,
        "consumer_active": state_manager.consumer_active,
        "last_update": state_manager.last_update.isoformat() if state_manager.last_update else None,
        "has_wrapper": state_manager.last_wrapper is not None,
        "has_payload": state_manager.last_payload is not None,
        "last_error": state_manager.last_error,
        "config": asdict(config),
    }

@app.get("/debug/last-wrapper")
def debug_last_wrapper():
    """获取最后的Kafka包装器数据"""
    return state_manager.last_wrapper or {}

@app.get("/debug/last-payload")
def debug_last_payload():
    """获取最后的Darwin载荷数据"""
    return state_manager.last_payload or {}

@app.get("/debug/last-error")
def debug_last_error():
    """获取最后的错误信息"""
    return {"error": state_manager.last_error}

@app.get("/debug/raw-positions")
def debug_raw_positions():
    """获取原始位置数据用于调试"""
    try:
        # 直接从数据库获取最新的几条记录
        positions = db_manager.get_all_positions(config.max_age_hours)
        
        # 返回前5条记录用于调试
        debug_data = {
            "total_in_db": len(positions),
            "memory_count": len(state_manager.latest),
            "sample_positions": positions[:5] if positions else [],
            "sample_memory": list(state_manager.latest.values())[:5] if state_manager.latest else []
        }
        
        return debug_data
        
    except Exception as e:
        logger.error(f"获取调试位置数据失败: {e}")
        return {"error": str(e)}

@app.post("/debug/cleanup")
def debug_cleanup():
    """手动清理旧数据"""
    try:
        state_manager.cleanup_old_positions()
        return {"message": "数据清理完成"}
    except Exception as e:
        logger.error(f"手动清理数据时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tiplocs")
def get_tiplocs():
    """获取所有TIPLOC坐标"""
    try:
        with sqlite3.connect(config.db_path) as conn:
            cursor = conn.execute("SELECT * FROM tiploc_coords ORDER BY tiploc")
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"获取TIPLOC数据时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tiplocs/{tiploc}")
def add_tiploc(tiploc: str, lat: float, lon: float, name: str = "", source: str = "manual"):
    """添加或更新TIPLOC坐标"""
    try:
        with sqlite3.connect(config.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO tiploc_coords 
                (tiploc, lat, lon, name, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tiploc.upper(), lat, lon, name, source, datetime.now().isoformat()))
        
        logger.info(f"已添加/更新TIPLOC: {tiploc} -> ({lat}, {lon})")
        return {"message": f"TIPLOC {tiploc} 已添加/更新", "tiploc": tiploc, "lat": lat, "lon": lon}
        
    except Exception as e:
        logger.error(f"添加TIPLOC时出错: {e}")
        raise HTTPException(status_code=500, detail=str(e))
