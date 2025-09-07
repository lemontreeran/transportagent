#!/usr/bin/env python3
"""
CRS到TIPLOC代码映射系统
将stations.json中的CRS代码映射到Darwin实时数据中的TIPLOC代码
"""

import json
import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class CRSTiplocMapper:
    def __init__(self, db_path="train_positions.db"):
        self.db_path = db_path
        self.crs_to_tiploc = {}
        self.tiploc_to_crs = {}
        
    def load_crs_tiploc_mappings(self):
        """加载CRS到TIPLOC的映射关系"""
        # 常见的CRS到TIPLOC映射
        mappings = {
            # 主要伦敦车站
            "PAD": "PADTON",      # Paddington
            "VIC": "VICTRIC",     # Victoria
            "WAT": "WATRLMN",     # Waterloo
            "LST": "LIVST",       # Liverpool Street
            "KGX": "KNGX",        # Kings Cross
            "EUS": "EUSTON",      # Euston
            "STP": "STPANCI",     # St Pancras
            "MYB": "MARYLBN",     # Marylebone
            "CHX": "CHARING",     # Charing Cross
            "LBG": "LNDNBDG",     # London Bridge
            "FST": "FENCHST",     # Fenchurch Street
            "MOG": "MOORGATE",    # Moorgate
            
            # 主要城市
            "BHM": "BRMNGM",      # Birmingham New Street
            "MAN": "MNCHSTR",     # Manchester
            "EDB": "EDINBGH",     # Edinburgh
            "GLC": "GLGW",        # Glasgow Central
            "LIV": "LVRPLCH",     # Liverpool
            "LEE": "LEEDS",       # Leeds
            "SHF": "SHEFFLD",     # Sheffield
            "NCL": "NWCSTLE",     # Newcastle
            "BRI": "BRISTOL",     # Bristol
            "CDF": "CRDFCEN",     # Cardiff Central
            "NOT": "NOTTGHM",     # Nottingham
            "LEI": "LEICSTR",     # Leicester
            "DBY": "DRBY",        # Derby
            "YRK": "YORK",        # York
            "BTH": "BATH",        # Bath Spa
            "EXD": "EXETER",      # Exeter
            "PLY": "PLYMOUTH",    # Plymouth
            "BTN": "BRIGHTON",    # Brighton
            "RDG": "RDNG",        # Reading
            "OXF": "OXFD",        # Oxford
            "CBG": "CMBDG",       # Cambridge
            
            # 伦敦周边重要站点
            "CLJ": "CLPHMJC",     # Clapham Junction
            "VXH": "VAUXHLM",     # Vauxhall
            "SRA": "STRATFD",     # Stratford
            "CRO": "CROYDON",     # Croydon
            "WIM": "WIMBLDON",    # Wimbledon
            "EPH": "ELPHNAC",     # Elephant & Castle
            "BAL": "BALHAM",      # Balham
            "PUT": "PUTNEY",      # Putney
            "RMD": "RICHMOND",    # Richmond
            "KTN": "KTON",        # Kingston
            "SUR": "SURBITON",    # Surbiton
            "WOK": "WOKING",      # Woking
            "GLD": "GUILDFD",     # Guildford
            
            # 机场
            "LHR": "HROW",        # Heathrow
            "LGW": "GTWK",        # Gatwick
            "STN": "STANSTED",    # Stansted
            
            # 其他重要站点
            "SOT": "SOTON",       # Southampton
            "PMS": "PMTH",        # Portsmouth
            "BOH": "BOMO",        # Bournemouth
            "DOV": "DOVER",       # Dover
            "CNT": "CANTERBY",    # Canterbury
            "ASH": "ASHFORD",     # Ashford
            "TON": "TUNBRIDGE",   # Tunbridge Wells
            "HAT": "HATFILD",     # Hatfield
            "STE": "STEVNGE",     # Stevenage
            "HIT": "HITCHIN",     # Hitchin
            "LTN": "LUTON",       # Luton
            "BDM": "BEDFORD",     # Bedford
            "MKC": "MKCENTRL",    # Milton Keynes Central
            "NTH": "NRTHMPTN",    # Northampton
            "COV": "COVENTRY",    # Coventry
            "WAR": "WARWICK",     # Warwick
            "STR": "STRATFRD",    # Stratford-upon-Avon
            "WOR": "WORCSTR",     # Worcester
            "HFD": "HEREFORD",    # Hereford
            "SHR": "SHRWSBY",     # Shrewsbury
            "CHE": "CHESTER",     # Chester
            "CRE": "CREWE",       # Crewe
            "STF": "STAFFRD",     # Stafford
            "WVH": "WVRMPTN",     # Wolverhampton
            "DUD": "DUDLEY",      # Dudley
            "WSB": "WALSALL",     # Walsall
            "TAM": "TAMWORTH",    # Tamworth
            "LIC": "LICHFLD",     # Lichfield
            "BUR": "BURTON",      # Burton-on-Trent
            "UTT": "UTTOXTR",     # Uttoxeter
            "STO": "STOKEOT",     # Stoke-on-Trent
            "MAC": "MACCLES",     # Macclesfield
            "STK": "STOCKPT",     # Stockport
            "WGN": "WIGAN",       # Wigan
            "PRE": "PRESTON",     # Preston
            "BLK": "BLACKPL",     # Blackpool
            "LAN": "LANCSTR",     # Lancaster
            "OXN": "OXENHLM",     # Oxenholme
            "KEN": "KENDAL",      # Kendal
            "WIN": "WINDRMR",     # Windermere
            "CAR": "CARLILE",     # Carlisle
            "PEN": "PENRITH",     # Penrith
            "APP": "APPLEBY",     # Appleby
            "KIR": "KIRKBY",      # Kirkby Stephen
            "GAR": "GARSDALE",    # Garsdale
            "RIB": "RIBBLHD",     # Ribblehead
            "HOR": "HORTON",      # Horton-in-Ribblesdale
            "SET": "SETTLE",      # Settle
            "GIG": "GIGGLES",     # Giggleswick
            "LNG": "LONGPRT",     # Long Preston
            "HEL": "HELLIFD",     # Hellifield
            "GIS": "GISBURN",     # Gisburn
            "CLI": "CLITHEROE",   # Clitheroe
            
            # 苏格兰
            "ABD": "ABRDEEN",     # Aberdeen
            "DND": "DUNDEE",      # Dundee
            "STG": "STIRLING",    # Stirling
            "PTH": "PERTH",       # Perth
            "INV": "IVRNESS",     # Inverness
            "KIL": "KILMRNCK",    # Kilmarnock
            "AYR": "AYR",         # Ayr
            "STR": "STRANRAR",    # Stranraer
            "DUM": "DUMFRIES",    # Dumfries
            "LOC": "LOCKERBY",    # Lockerbie
            "MOF": "MOFFAT",      # Moffat
            "BEA": "BEATTOCK",    # Beattock
            "CAR": "CARSTAIRS",   # Carstairs
            "MOB": "MOTHERWELL",  # Motherwell
            "HAM": "HAMILTON",    # Hamilton
            "LAR": "LARKHALL",    # Larkhall
            "LAN": "LANARK",      # Lanark
            
            # 威尔士
            "SWA": "SWANSEA",     # Swansea
            "NPT": "NEWPORT",     # Newport
            "CWL": "CWMBRAN",     # Cwmbran
            "ABG": "ABRGVNY",     # Abergavenny
            "HFD": "HEREFORD",    # Hereford (border)
            "SHR": "SHRWSBY",     # Shrewsbury (border)
            "WRX": "WREXHAM",     # Wrexham
            "CHE": "CHESTER",     # Chester (border)
            "RHY": "RHYL",        # Rhyl
            "LLD": "LLANDNO",     # Llandudno
            "BAN": "BANGOR",      # Bangor
            "HOL": "HOLYHEAD",    # Holyhead
            "PWL": "PWLLHELI",    # Pwllheli
            "POR": "PORTHMD",     # Porthmadog
            "FFE": "FFESTNG",     # Ffestiniog
            "BLA": "BLAENAU",     # Blaenau Ffestiniog
            "DOL": "DOLGELLY",    # Dolgellau
            "MAC": "MACHYNL",     # Machynlleth
            "ABE": "ABERYST",     # Aberystwyth
            "CAR": "CARDIGAN",    # Cardigan
            "FIS": "FISHGRD",     # Fishguard
            "HAV": "HAVERFRD",    # Haverfordwest
            "PEM": "PEMBROKE",    # Pembroke
            "TEN": "TENBY",       # Tenby
            "CAR": "CARMRHN",     # Carmarthen
            "LLA": "LLANELLI",    # Llanelli
            "NEA": "NEATH",       # Neath
            "PTA": "PTALBOT",     # Port Talbot
            "BGD": "BARGOED",     # Bargoed
            "CAE": "CAERPHLY",    # Caerphilly
            "PCD": "PENCOED",     # Pencoed
            "BRI": "BRIDGND",     # Bridgend
            "PYC": "PYCOMBE",     # Pyle
            "CST": "COWBRG",      # Cowbridge
            "RHO": "RHOOSE",      # Rhoose
            "BRY": "BARRY",       # Barry
            "BYI": "BARRYIS",     # Barry Island
            "CDI": "CARDIFF",     # Cardiff
            "CDF": "CRDFCEN",     # Cardiff Central
            "CQU": "CRDFQUY",     # Cardiff Queen Street
            "CBY": "CRDFBAY",     # Cardiff Bay
        }
        
        return mappings
    
    def load_stations_json(self, stations_file="stations.json"):
        """从stations.json加载车站数据"""
        try:
            with open(stations_file, 'r', encoding='utf-8') as f:
                stations = json.load(f)
            
            logger.info(f"从 {stations_file} 加载了 {len(stations)} 个车站")
            return stations
            
        except Exception as e:
            logger.error(f"加载stations.json失败: {e}")
            return []
    
    def create_mapping_database(self, stations_file="stations.json"):
        """创建CRS到TIPLOC的映射数据库"""
        try:
            # 加载预定义映射
            predefined_mappings = self.load_crs_tiploc_mappings()
            
            # 加载stations.json
            stations = self.load_stations_json(stations_file)
            
            with sqlite3.connect(self.db_path) as conn:
                # 创建映射表
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS crs_tiploc_mapping (
                        crs_code TEXT PRIMARY KEY,
                        tiploc_code TEXT,
                        station_name TEXT,
                        lat REAL,
                        lon REAL,
                        source TEXT,
                        updated_at TEXT
                    )
                """)
                
                # 插入预定义映射
                for crs, tiploc in predefined_mappings.items():
                    conn.execute("""
                        INSERT OR REPLACE INTO crs_tiploc_mapping 
                        (crs_code, tiploc_code, source, updated_at)
                        VALUES (?, ?, 'predefined', datetime('now'))
                    """, (crs, tiploc))
                
                # 处理stations.json中的数据
                updated_count = 0
                for station in stations:
                    crs_code = station.get('crsCode')
                    station_name = station.get('stationName')
                    lat = station.get('lat')
                    lon = station.get('long')
                    
                    if not crs_code:
                        continue
                    
                    # 检查是否已有预定义映射
                    cursor = conn.execute(
                        "SELECT tiploc_code FROM crs_tiploc_mapping WHERE crs_code = ?",
                        (crs_code,)
                    )
                    existing = cursor.fetchone()
                    
                    if existing:
                        tiploc_code = existing[0]
                    else:
                        # 尝试生成TIPLOC代码
                        tiploc_code = self.generate_tiploc_from_name(station_name)
                    
                    # 更新或插入映射
                    conn.execute("""
                        INSERT OR REPLACE INTO crs_tiploc_mapping 
                        (crs_code, tiploc_code, station_name, lat, lon, source, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'stations_json', datetime('now'))
                    """, (crs_code, tiploc_code, station_name, lat, lon))
                    
                    # 同时更新TIPLOC坐标表
                    conn.execute("""
                        INSERT OR REPLACE INTO tiploc_coords 
                        (tiploc, lat, lon, name, source, updated_at)
                        VALUES (?, ?, ?, ?, 'crs_mapping', datetime('now'))
                    """, (tiploc_code, lat, lon, station_name))
                    
                    updated_count += 1
                
                logger.info(f"更新了 {updated_count} 个CRS到TIPLOC的映射")
                return updated_count
                
        except Exception as e:
            logger.error(f"创建映射数据库失败: {e}")
            return 0
    
    def generate_tiploc_from_name(self, station_name):
        """从车站名称生成可能的TIPLOC代码"""
        if not station_name:
            return "UNKNOWN"
        
        # 简化的TIPLOC生成规则
        name = station_name.upper()
        
        # 移除常见词汇
        name = name.replace(" STATION", "")
        name = name.replace(" CENTRAL", "")
        name = name.replace(" PARKWAY", "")
        name = name.replace(" INTERNATIONAL", "")
        name = name.replace(" AIRPORT", "")
        name = name.replace(" & ", "")
        name = name.replace("-", "")
        name = name.replace("'", "")
        name = name.replace(" ", "")
        
        # 特殊处理
        special_cases = {
            "LONDON": "LONDON",
            "BIRMINGHAM": "BRMNGM",
            "MANCHESTER": "MNCHSTR",
            "EDINBURGH": "EDINBGH",
            "GLASGOW": "GLGW",
            "LIVERPOOL": "LVRPL",
            "SHEFFIELD": "SHEFFLD",
            "NEWCASTLE": "NWCSTLE",
            "NOTTINGHAM": "NOTTGHM",
            "LEICESTER": "LEICSTR",
            "COVENTRY": "COVNTRY",
            "WOLVERHAMPTON": "WVRMPTN",
            "SOUTHAMPTON": "SOTON",
            "PORTSMOUTH": "PMTH",
            "BOURNEMOUTH": "BOMO",
            "BRIGHTON": "BRIGHTN",
            "CANTERBURY": "CANTERBY",
            "GLOUCESTER": "GLOSTER",
            "WORCESTER": "WORCSTR",
            "SHREWSBURY": "SHRWSBY",
            "BLACKPOOL": "BLACKPL",
            "LANCASTER": "LANCSTR",
            "CARLISLE": "CARLILE",
            "ABERDEEN": "ABRDEEN",
            "INVERNESS": "IVRNESS",
            "KILMARNOCK": "KILMRNCK",
            "STRANRAER": "STRANRAR",
            "DUMFRIES": "DUMFRIES",
            "MOTHERWELL": "MOTHERWL",
            "HAMILTON": "HAMILTON",
        }
        
        if name in special_cases:
            return special_cases[name]
        
        # 截断到7个字符（TIPLOC最大长度）
        return name[:7]
    
    def get_tiploc_from_crs(self, crs_code):
        """根据CRS代码获取TIPLOC代码"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT tiploc_code FROM crs_tiploc_mapping WHERE crs_code = ?",
                    (crs_code,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
                
        except Exception as e:
            logger.error(f"查询TIPLOC失败: {e}")
            return None
    
    def get_coordinates_from_crs(self, crs_code):
        """根据CRS代码获取坐标"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT lat, lon FROM crs_tiploc_mapping WHERE crs_code = ?",
                    (crs_code,)
                )
                result = cursor.fetchone()
                return (result[0], result[1]) if result else None
                
        except Exception as e:
            logger.error(f"查询坐标失败: {e}")
            return None
    
    def update_tiploc_coords_from_crs(self):
        """使用CRS映射更新TIPLOC坐标表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 获取所有有坐标的CRS映射
                cursor = conn.execute("""
                    SELECT tiploc_code, lat, lon, station_name 
                    FROM crs_tiploc_mapping 
                    WHERE lat IS NOT NULL AND lon IS NOT NULL
                """)
                
                mappings = cursor.fetchall()
                updated_count = 0
                
                for tiploc, lat, lon, name in mappings:
                    conn.execute("""
                        INSERT OR REPLACE INTO tiploc_coords 
                        (tiploc, lat, lon, name, source, updated_at)
                        VALUES (?, ?, ?, ?, 'crs_mapping', datetime('now'))
                    """, (tiploc, lat, lon, name))
                    updated_count += 1
                
                logger.info(f"从CRS映射更新了 {updated_count} 个TIPLOC坐标")
                return updated_count
                
        except Exception as e:
            logger.error(f"更新TIPLOC坐标失败: {e}")
            return 0

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="CRS到TIPLOC映射工具")
    parser.add_argument("--db-path", default="train_positions.db", help="数据库路径")
    parser.add_argument("--stations-file", default="stations.json", help="stations.json文件路径")
    parser.add_argument("--create-mapping", action="store_true", help="创建CRS到TIPLOC映射")
    parser.add_argument("--update-coords", action="store_true", help="更新TIPLOC坐标")
    parser.add_argument("--lookup-crs", help="查询CRS代码对应的TIPLOC")
    
    args = parser.parse_args()
    
    mapper = CRSTiplocMapper(args.db_path)
    
    if args.create_mapping:
        count = mapper.create_mapping_database(args.stations_file)
        print(f"✅ 创建了 {count} 个CRS到TIPLOC映射")
    
    if args.update_coords:
        count = mapper.update_tiploc_coords_from_crs()
        print(f"✅ 更新了 {count} 个TIPLOC坐标")
    
    if args.lookup_crs:
        tiploc = mapper.get_tiploc_from_crs(args.lookup_crs)
        coords = mapper.get_coordinates_from_crs(args.lookup_crs)
        if tiploc:
            print(f"CRS {args.lookup_crs} -> TIPLOC {tiploc}")
            if coords:
                print(f"坐标: {coords[0]}, {coords[1]}")
        else:
            print(f"未找到CRS代码 {args.lookup_crs} 的映射")

if __name__ == "__main__":
    main()