# db_manager.py
import os
import struct
from datetime import datetime, timedelta
import pymysql  # 💡 라이브러리 변경
from sqlalchemy import create_engine

# 💡 excel_report.py와의 호환성을 위해 기존 폴더 경로 정의를 다시 추가합니다.
DB_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'ElecRoomSCADA')

# 💡 MariaDB 접속 정보 설정 (본인 환경에 맞게 수정)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'scada_user',        # 💡 새로 만든 계정으로 변경
    'password': 'scada1234',     # 💡 새로 설정한 비밀번호로 변경
    'database': 'elecroomscada',
    'port': 3306,
    'autocommit': False
}

# 💡 다른 파일(plc_worker, excel_report 등)과의 호환성을 위해 변수 유지
DB_NAME = DB_CONFIG['database'] 

DATA_LABELS = [
    "실내온도", "외기온도", "SF운전시간", "EF운전시간", 
    "KEP_V_R", "KEP_V_S", "KEP_V_T", "KEP_V_R_S", "KEP_V_S_T", "KEP_V_T_R", 
    "KEP_A_R", "KEP_A_S", "KEP_A_T", 
    "KEP_frequency", "KEP_P_kW", "KEP_P_kWh", 
    "Tr1_A_R", "Tr1_A_S", "Tr1_A_T", "Tr1_V_R", "Tr1_V_S", "Tr1_V_T", "Tr1_V_R_S", "Tr1_V_S_T", "Tr1_V_T_R", "Tr1_P_kW", "Tr1_Temp",
    "Tr2_A_R", "Tr2_A_S", "Tr2_A_T", "Tr2_V_R", "Tr2_V_S", "Tr2_V_T", "Tr2_V_R_S", "Tr2_V_S_T", "Tr2_V_T_R", "Tr2_P_kW", "Tr2_Temp",
    "Tr3_A_R", "Tr3_A_S", "Tr3_A_T", "Tr3_V_R", "Tr3_V_S", "Tr3_V_T", "Tr3_V_R_S", "Tr3_V_S_T", "Tr3_V_T_R", "Tr3_P_kW", "Tr3_Temp"
]

COLUMN_LABELS = ["날짜", "시간/구분"] + DATA_LABELS

_db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
_engine = create_engine(_db_url)

def get_db_connection():
    """[방법 A] 판다스(그래프) 전용 함수"""
    # 🌟 pymysql.connect가 아니라, 미리 만든 SQLAlchemy '엔진' 객체를 리턴합니다!
    # 이 객체를 pandas에 넘겨줘야 UserWarning 경고가 발생하지 않습니다.
    return _engine

def get_db_raw_connection():
    """기존의 순수한 pymysql connection 객체가 강제로 필요한 경우 사용하는 보조 함수"""
    return pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        port=DB_CONFIG['port'],
        autocommit=DB_CONFIG['autocommit']
    )

def init_db():
    conn = get_db_raw_connection()
    c = conn.cursor()
    cols = ", ".join([f'`{name}` REAL' for name in DATA_LABELS])
    
    # 테이블 생성 (백틱 적용 및 VARCHAR 크기 명시)
    c.execute(f'CREATE TABLE IF NOT EXISTS raw_data (log_date DATE, log_time TIME, {cols}, PRIMARY KEY (log_date, log_time))')
    c.execute(f'CREATE TABLE IF NOT EXISTS hourly_avg (log_date DATE, log_time TIME, {cols}, PRIMARY KEY (log_date, log_time))')
    c.execute(f'CREATE TABLE IF NOT EXISTS daily_extremes (log_date DATE, `extreme_type` VARCHAR(10), {cols}, PRIMARY KEY (log_date, `extreme_type`))')
    
    # MariaDB 인덱스 문법
    try:
        c.execute('CREATE INDEX idx_raw_data_date_time ON raw_data (log_date, log_time)')
        c.execute('CREATE INDEX idx_hourly_avg_date_time ON hourly_avg (log_date, log_time)')
    except Exception:
        pass # 이미 인덱스가 존재할 경우 무시

    create_field_inspection_table()
    conn.commit()
    c.close()
    conn.close()

def calculate_hourly_avg():
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        now = datetime.now()
        last_hour = (now - timedelta(hours=1))
        target_date = last_hour.strftime('%Y-%m-%d')
        target_hour = last_hour.strftime('%H')
        
        avg_select = ", ".join([f'AVG(`{name}`)' for name in DATA_LABELS])
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        
        # 💡 SQLite의 ? -> %s 변경, LIKE 조건 수정
        query = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
        c.execute(query, (target_date, f"{target_hour}:%"))
        result = c.fetchone()

        if result and result[0] is not None:
            rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
            placeholders = ", ".join(["%s"] * len(DATA_LABELS))
            # 💡 REPLACE INTO 사용
            insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
            
            c.execute(insert_query, [target_date, f"{target_hour}:00:00"] + rounded_result)
            conn.commit()
    except Exception as e:
        print(f"평균 계산 오류: {e}")
    finally:
        c.close()
        conn.close()

def calculate_daily_extremes(target_date):
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        max_select = ", ".join([f'MAX(`{name}`)' for name in DATA_LABELS])
        min_select = ", ".join([f'MIN(`{name}`)' for name in DATA_LABELS])
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        placeholders = ", ".join(["%s"] * len(DATA_LABELS))
        
        query_max = f'SELECT {max_select} FROM raw_data WHERE log_date = %s'
        c.execute(query_max, (target_date,))
        max_res = c.fetchone()
        if max_res and max_res[0] is not None:
            insert_max = f'REPLACE INTO daily_extremes (log_date, `extreme_type`, {col_names}) VALUES (%s, %s, {placeholders})'
            c.execute(insert_max, [target_date, 'MAX'] + list(max_res))
            
        query_min = f'SELECT {min_select} FROM raw_data WHERE log_date = %s'
        c.execute(query_min, (target_date,))
        min_res = c.fetchone()
        if min_res and min_res[0] is not None:
            insert_min = f'REPLACE INTO daily_extremes (log_date, `extreme_type`, {col_names}) VALUES (%s, %s, {placeholders})'
            c.execute(insert_min, [target_date, 'MIN'] + list(min_res))
            
        conn.commit()
    except Exception as e:
        print(f"최고/최저 계산 오류: {e}")
    finally:
        c.close()
        conn.close()

METER_FIELDS = ["main_active", "main_reactive", "ind_mid", "ind_max", "ind_light", "street_mid", "street_max", "street_light", "geo_1", "geo_2", "geo_3"]

def create_manual_meter_table():
    conn = get_db_raw_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS manual_meter_logs (
            log_date DATE PRIMARY KEY,
            main_active REAL, main_reactive REAL, ind_mid REAL, ind_max REAL, ind_light REAL,
            street_mid REAL, street_max REAL, street_light REAL, geo_1 REAL, geo_2 REAL, geo_3 REAL
        )
    ''')
    conn.commit()
    c.close()
    conn.close()

def get_manual_meter_data(target_date):
    create_manual_meter_table()
    conn = get_db_raw_connection()
    c = conn.cursor()
    fields_str = ", ".join([f"`{f}`" for f in METER_FIELDS])
    c.execute(f'SELECT {fields_str} FROM manual_meter_logs WHERE log_date = %s', (target_date,))
    res = c.fetchone()
    c.close()
    conn.close()
    
    data_dict = {f: "" for f in METER_FIELDS}
    if res:
        for idx, field in enumerate(METER_FIELDS):
            data_dict[field] = str(res[idx]) if res[idx] is not None else ""
    return data_dict

def save_manual_meter_data(target_date, data_dict):
    create_manual_meter_table()
    conn = get_db_raw_connection()
    c = conn.cursor()
    fields_str = "log_date, " + ", ".join([f"`{f}`" for f in METER_FIELDS])
    placeholders = ", ".join(["%s"] * (len(METER_FIELDS) + 1))
    
    values = [target_date]
    for field in METER_FIELDS:
        val = data_dict.get(field, "")
        values.append(float(val) if val.strip() != "" else None)
        
    c.execute(f'REPLACE INTO manual_meter_logs ({fields_str}) VALUES ({placeholders})', values)
    conn.commit()
    c.close()
    conn.close()

def get_manual_meter_log_for_table(target_date):
    create_manual_meter_table()
    conn = get_db_raw_connection()
    c = conn.cursor()
    fields_str = ", ".join([f"`{f}`" for f in METER_FIELDS])
    c.execute(f"SELECT log_date, {fields_str} FROM manual_meter_logs WHERE log_date = %s", (target_date,))
    row = c.fetchone()
    c.close()
    conn.close()
    
    if row:
        return [str(row[0])] + [f"{v:.1f}" if isinstance(v, float) else str(v) if v is not None else "-" for v in row[1:]]
    else:
        return [target_date] + ["-"] * len(METER_FIELDS)

def create_field_inspection_table():
    conn = get_db_raw_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS field_inspection (
            inspection_date DATE,
            inspection_round INTEGER,
            inspector_name VARCHAR(100) NOT NULL,
            inspected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (inspection_date, inspection_round)
        )
    ''')
    conn.commit()
    c.close()
    conn.close()

def save_field_inspection(target_date, round_val, inspector_name):
    create_field_inspection_table()
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        # 💡 SQLite 전용 datetime('now', 'localtime') -> NOW() 변경
        c.execute('''
            REPLACE INTO field_inspection (inspection_date, inspection_round, inspector_name, inspected_at)
            VALUES (%s, %s, %s, NOW())
        ''', (target_date, round_val, inspector_name))
        conn.commit()
        return True
    except Exception as e:
        print(f"현장 점검 저장 오류: {e}")
        return False
    finally:
        c.close()
        conn.close()

def get_field_inspections_for_date(target_date):
    create_field_inspection_table()
    conn = get_db_raw_connection()
    c = conn.cursor()
    c.execute('''
        SELECT inspection_round, inspector_name, DATE_FORMAT(inspected_at, '%%H:%%M') 
        FROM field_inspection 
        WHERE inspection_date = %s
    ''', (target_date,))
    rows = c.fetchall()
    c.close()
    conn.close()
    
    result = {1: {"name": "", "time": ""}, 2: {"name": "", "time": ""}, 3: {"name": "", "time": ""}}
    for row in rows:
        round_num, name, time_str = row
        if round_num in result:
            result[round_num] = {"name": name, "time": time_str}
    return result