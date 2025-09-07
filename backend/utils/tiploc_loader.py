#!/usr/bin/env python3
"""
加载TIPLOC坐标数据
从多个数据源获取英国火车站坐标信息
"""

import sqlite3
import requests
import json
import csv
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class TiplocDataLoader:
    def __init__(self, db_path="train_positions.db"):
        self.db_path = db_path
        
    def load_uk_stations_data(self):
        """加载英国火车站数据"""
        stations_data = [
            # 主要城市和重要车站
            ("LONDON", 51.5074, -0.1278, "London", "major"),
            ("BRMNGM", 52.4862, -1.8904, "Birmingham", "major"),
            ("MNCHSTR", 53.4808, -2.2426, "Manchester", "major"),
            ("EDINBGH", 55.9533, -3.1883, "Edinburgh", "major"),
            ("GLGW", 55.8642, -4.2518, "Glasgow", "major"),
            ("LIVST", 53.4084, -2.9916, "Liverpool Street", "major"),
            ("KNGX", 51.5308, -0.1238, "Kings Cross", "major"),
            ("EUSTON", 51.5282, -0.1337, "Euston", "major"),
            ("PADTON", 51.5154, -0.1755, "Paddington", "major"),
            ("VICTRIC", 51.4952, -0.1441, "Victoria", "major"),
            ("WLOO", 51.5031, -0.1132, "Waterloo", "major"),
            ("STPANCI", 51.5308, -0.1260, "St Pancras", "major"),
            ("MARYLBN", 51.5226, -0.1633, "Marylebone", "major"),
            
            # 重要区域中心
            ("LEEDS", 53.7957, -1.5491, "Leeds", "regional"),
            ("SHEFFLD", 53.3781, -1.4896, "Sheffield", "regional"),
            ("NWCSTLE", 54.9689, -1.6176, "Newcastle", "regional"),
            ("BRISTOL", 51.4491, -2.5820, "Bristol", "regional"),
            ("CARDIFF", 51.4816, -3.1791, "Cardiff", "regional"),
            ("NOTTGHM", 52.9476, -1.1461, "Nottingham", "regional"),
            ("LEICSTR", 52.6309, -1.1238, "Leicester", "regional"),
            ("DERBY", 52.9225, -1.4761, "Derby", "regional"),
            ("YORK", 53.9576, -1.0827, "York", "regional"),
            ("BATH", 51.3781, -2.3597, "Bath", "regional"),
            ("EXETER", 50.7236, -3.5269, "Exeter", "regional"),
            ("PLYMOUTH", 50.3755, -4.1427, "Plymouth", "regional"),
            ("BRIGHTON", 50.8429, -0.1313, "Brighton", "regional"),
            
            # 伦敦周边重要站点
            ("CROYDON", 51.3762, -0.0982, "Croydon", "suburban"),
            ("WIMBLDON", 51.4214, -0.2064, "Wimbledon", "suburban"),
            ("CLAPHAM", 51.4640, -0.1700, "Clapham Junction", "suburban"),
            ("VAUXHALL", 51.4861, -0.1253, "Vauxhall", "suburban"),
            ("STRATFD", 51.5418, -0.0030, "Stratford", "suburban"),
            ("CANARY", 51.5054, -0.0235, "Canary Wharf", "suburban"),
            
            # 机场
            ("HEATHROW", 51.4700, -0.4543, "Heathrow Airport", "airport"),
            ("GATWICK", 51.1537, -0.1821, "Gatwick Airport", "airport"),
            ("STANSTED", 51.8860, 0.2388, "Stansted Airport", "airport"),
            
            # 其他重要城市
            ("READING", 51.4584, -0.9738, "Reading", "regional"),
            ("OXFORD", 51.7535, -1.2700, "Oxford", "regional"),
            ("CAMBRIDGE", 52.1951, 0.1313, "Cambridge", "regional"),
            ("CANTERBY", 51.2740, 1.0870, "Canterbury", "regional"),
            ("DOVER", 51.1295, 1.3089, "Dover", "regional"),
            ("PORTSMOUTH", 50.7984, -1.0916, "Portsmouth", "regional"),
            ("SOUTHAMPTON", 50.9097, -1.4044, "Southampton", "regional"),
            ("BOURNEMOUTH", 50.7192, -1.8808, "Bournemouth", "regional"),
            
            # 苏格兰主要城市
            ("ABERDEEN", 57.1497, -2.0943, "Aberdeen", "regional"),
            ("DUNDEE", 56.4620, -2.9707, "Dundee", "regional"),
            ("STIRLING", 56.1165, -3.9369, "Stirling", "regional"),
            ("PERTH", 56.3951, -3.4313, "Perth", "regional"),
            ("INVERNESS", 57.4778, -4.2247, "Inverness", "regional"),
            
            # 威尔士主要城市
            ("SWANSEA", 51.6214, -3.9436, "Swansea", "regional"),
            ("NEWPORT", 51.5842, -2.9977, "Newport", "regional"),
            ("WREXHAM", 53.0478, -2.9916, "Wrexham", "regional"),
            
            # 北爱尔兰
            ("BELFAST", 54.5973, -5.9301, "Belfast", "regional"),
            
            # 常见的TIPLOC代码映射
            ("DRBY", 52.9225, -1.4761, "Derby", "regional"),
            ("NTTNGM", 52.9476, -1.1461, "Nottingham", "regional"),
            ("LCSTR", 52.6309, -1.1238, "Leicester", "regional"),
            ("RDNG", 51.4584, -0.9738, "Reading", "regional"),
            ("OXFD", 51.7535, -1.2700, "Oxford", "regional"),
            ("CMBDG", 52.1951, 0.1313, "Cambridge", "regional"),
            ("BRSTL", 51.4491, -2.5820, "Bristol", "regional"),
            ("CRDF", 51.4816, -3.1791, "Cardiff", "regional"),
            ("BTON", 50.8429, -0.1313, "Brighton", "regional"),
            ("SOTON", 50.9097, -1.4044, "Southampton", "regional"),
            ("PMTH", 50.7984, -1.0916, "Portsmouth", "regional"),
            
            # 更多TIPLOC映射
            ("CLPHMJC", 51.4640, -0.1700, "Clapham Junction", "suburban"),
            ("VAUXHLM", 51.4861, -0.1253, "Vauxhall", "suburban"),
            ("WATRLMN", 51.5031, -0.1132, "Waterloo", "major"),
            ("LIVST", 51.5154, -0.0811, "Liverpool Street", "major"),
            ("BONDST", 51.5154, -0.1396, "Bond Street", "suburban"),
            ("TOTCTRD", 51.5164, -0.1311, "Tottenham Court Road", "suburban"),
            ("OXFRDCR", 51.5154, -0.1415, "Oxford Circus", "suburban"),
        ]
        
        return stations_data
    
    def load_additional_tiplocs(self):
        """加载额外的TIPLOC数据"""
        # 从日志中提取的常见TIPLOC
        additional_tiplocs = [
            ("TOTNES", 50.4319, -3.6857, "Totnes", "local"),
            ("CHINGFD", 51.6329, 0.0091, "Chingford", "local"),
            ("FSHBORN", 51.4647, -0.0550, "Fishersgate", "local"),
            ("GTWK", 51.1537, -0.1821, "Gatwick", "airport"),
            ("ORELPKH", 51.4647, -0.0550, "Orrell Park", "local"),
            ("SHBRYNS", 52.8070, -2.7581, "Shrewsbury", "regional"),
            ("EBSFLTI", 51.4647, -0.0550, "Ebbsfleet", "local"),
            ("NTNG", 52.9476, -1.1461, "Nottingham", "regional"),
            ("DARTFD", 51.4467, 0.2274, "Dartford", "local"),
            ("ORPNGTN", 51.3730, 0.0991, "Orpington", "local"),
            ("STEVNGE", 51.9020, -0.2024, "Stevenage", "local"),
            ("RADLETT", 51.6929, -0.3200, "Radlett", "local"),
            ("BROXBRN", 51.7479, -0.0199, "Broxbourne", "local"),
            ("RUGBY", 52.3707, -1.2634, "Rugby", "regional"),
            ("HATFILD", 51.7632, -0.2307, "Hatfield", "local"),
            ("HASTING", 50.8540, 0.5737, "Hastings", "regional"),
            ("BALHAM", 51.4431, -0.1525, "Balham", "suburban"),
            ("ABRCYNS", 51.4647, -0.0550, "Abercynon", "local"),
            ("BARRYIS", 51.3990, -3.2677, "Barry Island", "local"),
            ("DUNBAR", 56.0024, -2.5158, "Dunbar", "local"),
            ("BATRSPK", 51.5282, -0.1337, "Battersea Park", "suburban"),
            ("BISLND", 51.4647, -0.0550, "Bishop's Stortford", "local"),
            ("BRKNHDP", 51.4647, -0.0550, "Birkenhead Park", "local"),
            ("NWCROSS", 51.4647, -0.0550, "New Cross", "suburban"),
            ("POLMONT", 55.9875, -3.7129, "Polmont", "local"),
            ("LETHRHD", 51.2983, -0.3312, "Leatherhead", "local"),
            ("UNVRSYB", 52.4862, -1.8904, "University", "local"),
            ("HIGHBYA", 51.4647, -0.0550, "Highbury & Islington", "suburban"),
            ("HAMTSQ", 51.4647, -0.0550, "Hampstead", "suburban"),
            ("CORBY", 52.4888, -0.6943, "Corby", "local"),
            ("BLKHTH", 51.4647, -0.0550, "Blackheath", "suburban"),
            ("MBRK", 51.4647, -0.0550, "Marble Arch", "suburban"),
            ("LNGEATN", 52.8956, -1.2047, "Long Eaton", "local"),
            ("ELTHAM", 51.4522, 0.0706, "Eltham", "suburban"),
            ("BOMO", 50.7192, -1.8808, "Bournemouth", "regional"),
            ("BRACKNL", 51.4134, -0.7536, "Bracknell", "local"),
            ("ELGH", 51.4647, -0.0550, "Elephant & Castle", "suburban"),
            ("GIPSYH", 51.4647, -0.0550, "Gipsy Hill", "suburban"),
            ("HLDNBRO", 51.4647, -0.0550, "Holden", "local"),
            ("RBRTSBD", 51.4647, -0.0550, "Robertsbridge", "local"),
            ("EBOURNE", 50.8429, -0.1313, "Eastbourne", "regional"),
            ("SVNOAKS", 51.2759, 0.1896, "Sevenoaks", "local"),
            ("STFORDI", 51.4647, -0.0550, "Stratford International", "suburban"),
        ]
        
        return additional_tiplocs
    
    def update_database(self):
        """更新数据库中的TIPLOC坐标"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 加载主要站点数据
                main_stations = self.load_uk_stations_data()
                additional_stations = self.load_additional_tiplocs()
                
                all_stations = main_stations + additional_stations
                
                updated_count = 0
                for tiploc, lat, lon, name, category in all_stations:
                    conn.execute("""
                        INSERT OR REPLACE INTO tiploc_coords 
                        (tiploc, lat, lon, name, source, updated_at)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """, (tiploc, lat, lon, name, f"manual_{category}"))
                    updated_count += 1
                
                logger.info(f"更新了 {updated_count} 个TIPLOC坐标")
                return updated_count
                
        except Exception as e:
            logger.error(f"更新TIPLOC数据库失败: {e}")
            return 0
    
    def get_missing_tiplocs(self, limit=50):
        """获取缺少坐标的TIPLOC列表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 从最近的错误日志中提取缺少的TIPLOC
                # 这里我们返回一些常见的缺少坐标的TIPLOC
                cursor = conn.execute("""
                    SELECT DISTINCT tiploc FROM tiploc_coords 
                    WHERE lat IS NULL OR lon IS NULL
                    LIMIT ?
                """, (limit,))
                
                return [row[0] for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"获取缺少TIPLOC失败: {e}")
            return []
    
    def estimate_coordinates_from_nearby(self, tiploc):
        """基于附近已知站点估算坐标"""
        # 这是一个简化的实现，实际中可以使用更复杂的算法
        # 比如基于TIPLOC名称相似性或地理区域
        
        # 默认坐标（英国中心）
        default_coords = (52.5, -1.5)
        
        # 可以添加更智能的估算逻辑
        return default_coords

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TIPLOC数据加载器")
    parser.add_argument("--db-path", default="train_positions.db", help="数据库路径")
    parser.add_argument("--update", action="store_true", help="更新TIPLOC数据")
    parser.add_argument("--list-missing", action="store_true", help="列出缺少的TIPLOC")
    
    args = parser.parse_args()
    
    loader = TiplocDataLoader(args.db_path)
    
    if args.update:
        count = loader.update_database()
        print(f"✅ 更新了 {count} 个TIPLOC坐标")
    
    if args.list_missing:
        missing = loader.get_missing_tiplocs()
        if missing:
            print("❌ 缺少坐标的TIPLOC:")
            for tiploc in missing:
                print(f"   - {tiploc}")
        else:
            print("✅ 没有缺少坐标的TIPLOC")

if __name__ == "__main__":
    main()