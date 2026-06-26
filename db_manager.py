# db_manager.py
import os
import pymysql  # 💡 핵심 개선: 호환성이 가장 뛰어난 PyMySQL 채택
from datetime import datetime, timedelta

# =========================================================================
# [설정 및 전역 변수] 기본 경로 및 데이터 라벨 정의
# =========================================================================
DB_DIR = os.path.join(os.environ['LOCALAPPDATA'], 'ElecRoomSCADA')
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

# MariaDB 접속 정보 설정 (PyMySQL 규격)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',        # 💡 새로 만든 계정으로 변경
    'password': 'scada1234',     # 💡 새로 설정한 비밀번호로 변경
    'database': 'elecroomscada',
    'port': 3306,
    'charset': 'utf8mb4'
}

# 50개 워드 데이터 매핑용 한글 라벨 (순서 절대 변경 금지)
DATA_LABELS = [
    "실내온도", "외기온도", "SF운전시간", "EF운전시간", 
    "KEP_V_R", "KEP_V_S", "KEP_V_T", "KEP_V_R_S", "KEP_V_S_T", "KEP_V_T_R", 
    "KEP_A_R", "KEP_A_S", "KEP_A_T", 
    "KEP_frequency", "KEP_P_kW", "KEP_P_kWh", 
    "Tr1_A_R", "Tr1_A_S", "Tr1_A_T", "Tr1_V_R", "Tr1_V_S", "Tr1_V_T", "Tr1_V_R_S", "Tr1_V_S_T", "Tr1_V_T_R", "Tr1_P_kW", "Tr1_Temp",
    "Tr2_A_R", "Tr2_A_S", "Tr2_A_T", "Tr2_V_R", "Tr2_V_S", "Tr2_V_T", "Tr2_V_R_S", "Tr2_V_S_T", "Tr2_V_T_R", "Tr2_P_kW", "Tr2_Temp",
    "Tr3_A_R", "Tr3_A_S", "Tr3_A_T", "Tr3_V_R", "Tr3_V_S", "Tr3_V_T", "Tr3_V_R_S", "Tr3_V_S_T", "Tr3_V_T_R", "Tr3_P_kW", "Tr3_Temp"
]

# 수동 검침용 10개 필드 정의
METER_FIELDS = [
    "main_active", "main_reactive", 
    "ind_mid", "ind_max", "ind_light", 
    "street_mid", "street_max", "street_light", 
    "geo_1", "geo_2", "geo_3"
]

# =========================================================================
# [커넥션 빌더] 안전한 데이터베이스 연결 및 통로 개방
# =========================================================================
def get_db_raw_connection():
    """안전한 MariaDB Connection 객체를 반환합니다."""
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as err:
        print(f"[DB 커넥션 오류] 연결 실패: {err}")
        raise err

# =========================================================================
# [초기화 로직] 프로그램 기동 시 테이블 자동 생성 (MariaDB 표준 문법)
# =========================================================================
def init_db():
    """메인 진입(main.py) 시 호출되어 MariaDB 내부 필수 테이블들을 검사 및 생성합니다."""
    conn = get_db_raw_connection()
    c = conn.cursor()
    
    # 1. 실시간 수집 raw_data 테이블 생성
    columns_str = ", ".join([f"`{name}` DOUBLE DEFAULT NULL" for name in DATA_LABELS])
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS raw_data (
            idx INT AUTO_INCREMENT PRIMARY KEY,
            log_date VARCHAR(10) NOT NULL,
            log_time VARCHAR(8) NOT NULL,
            {columns_str},
            INDEX idx_date_time (log_date, log_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')

    # 2. 전력 분석용 최고/최저 통계 daily_extremes 테이블 생성
    extremes_cols = ", ".join([f"`{name}` DOUBLE DEFAULT NULL" for name in DATA_LABELS])
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS daily_extremes (
            log_date VARCHAR(10) NOT NULL,
            extreme_type VARCHAR(10) NOT NULL,
            {extremes_cols},
            PRIMARY KEY (log_date, extreme_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')

    # 3. 수동 검침 데이터 manual_meter_logs 테이블 생성
    c.execute('''
        CREATE TABLE IF NOT EXISTS manual_meter_logs (
            log_date DATE PRIMARY KEY,
            main_active REAL,
            main_reactive REAL,
            ind_mid REAL,
            ind_max REAL,
            ind_light REAL,
            street_mid REAL,
            street_max REAL,
            street_light REAL,
            geo_1 REAL,
            geo_2 REAL,
            geo_3 REAL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')

    # 4. 현장 점검 기록 field_inspection 테이블 생성
    c.execute('''
        CREATE TABLE IF NOT EXISTS field_inspection (
            inspection_date VARCHAR(10) NOT NULL,
            inspection_round INT NOT NULL,
            inspector_name VARCHAR(50) NOT NULL,
            inspected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (inspection_date, inspection_round)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    ''')

    conn.commit()
    c.close()
    conn.close()
    print("✅ [DB 초기화 완료] MariaDB 모든 시스템 테이블이 정상 준비되었습니다.")

# =========================================================================
# [C.R.U.D 비즈니스 함수 API] 외부 파일용 인터페이스
# =========================================================================

def save_plc_raw_data(log_date, log_time, adjusted_values):
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        placeholders = ", ".join(["%s"] * len(adjusted_values))
        col_names = ", ".join([f"`{name}`" for name in DATA_LABELS])
        query = f"INSERT INTO raw_data (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
        
        c.execute(query, [log_date, log_time] + adjusted_values)
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB 오류] PLC 데이터 저장 실패: {e}")
        return False
    finally:
        c.close()
        conn.close()

def get_latest_realtime_data():
    conn = get_db_raw_connection()
    c = conn.cursor(pymysql.cursors.DictCursor) # 💡 PyMySQL용 딕셔너리 변환 문법 보정
    try:
        c.execute("SELECT * FROM raw_data ORDER BY log_date DESC, log_time DESC LIMIT 1")
        return c.fetchone()
    finally:
        c.close()
        conn.close()

def save_field_inspection(target_date, round_val, inspector_name):
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        query = '''
            INSERT INTO field_inspection (inspection_date, inspection_round, inspector_name, inspected_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE inspector_name = VALUES(inspector_name), inspected_at = NOW()
        '''
        c.execute(query, (target_date, round_val, inspector_name))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB 오류] 현장 점검 기록 저장 실패: {e}")
        return False
    finally:
        c.close()
        conn.close()

def get_field_inspections_for_date(target_date):
    conn = get_db_raw_connection()
    c = conn.cursor()
    data = {1: {"name": "", "time": ""}, 2: {"name": "", "time": ""}, 3: {"name": "", "time": ""}}
    try:
        c.execute('''
            SELECT inspection_round, inspector_name, DATE_FORMAT(inspected_at, '%%H:%%M') 
            FROM field_inspection 
            WHERE inspection_date = %s
        ''', (target_date,))
        rows = c.fetchall()
        for r in rows:
            r_idx, name, t_str = r[0], r[1], r[2]
            if r_idx in data:
                data[r_idx] = {"name": name, "time": t_str}
        return data
    finally:
        c.close()
        conn.close()

def create_manual_meter_table(): pass

def get_realtime_grid_data(selected_date):
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        query = "SELECT log_date, log_time, " + ", ".join([f"`{name}`" for name in DATA_LABELS]) + " FROM raw_data WHERE log_date = %s ORDER BY log_time ASC"
        c.execute(query, (selected_date,))
        return c.fetchall()
    finally:
        c.close()
        conn.close()

def check_inspection_exists(target_date, round_idx):
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT inspector_name FROM field_inspection WHERE inspection_date = %s AND inspection_round = %s', (target_date, round_idx))
        return c.fetchone() is not None
    finally:
        c.close()
        conn.close()

def get_excel_extremes_data(selected_date):
    conn = get_db_raw_connection()
    c = conn.cursor()
    extremes_dict = {}
    try:
        c.execute('SELECT * FROM daily_extremes WHERE log_date = %s', (selected_date,))
        rows = c.fetchall()
        columns = [desc[0] for desc in c.description] if c.description else []
        
        if 'extreme_type' in columns:
            type_idx = columns.index('extreme_type')
            for r in rows:
                ext_type = r[type_idx]
                for col_name in DATA_LABELS:
                    if col_name in columns:
                        val = r[columns.index(col_name)]
                        extremes_dict[(ext_type, col_name)] = round(float(val), 1) if val is not None else "-"
        return extremes_dict
    finally:
        c.close()
        conn.close()

def get_excel_manual_meters(selected_date, prev_date, prev_month_date):
    conn = get_db_raw_connection()
    c = conn.cursor()
    meter_data = {"금일": {}, "전일": {}, "전월": {}}
    fields_str = ", ".join(METER_FIELDS)
    try:
        for label, t_date in [("금일", selected_date), ("전일", prev_date), ("전월", prev_month_date)]:
            c.execute(f'SELECT {fields_str} FROM manual_meter_logs WHERE log_date = %s', (t_date,))
            res = c.fetchone()
            if res:
                meter_data[label] = {field: res[idx] for idx, field in enumerate(METER_FIELDS)}
            else:
                meter_data[label] = {field: None for field in METER_FIELDS}
        return meter_data
    finally:
        c.close()
        conn.close()

def get_excel_hourly_averages(selected_date):
    conn = get_db_raw_connection()
    c = conn.cursor()
    hourly_data = {}
    avg_selects = ", ".join([f'AVG(`{name}`)' for name in DATA_LABELS])
    try:
        # 💡 PyMySQL 안전 문법 적용을 위해 HOUR() 추출문 인라인 정렬
        c.execute(f'''
            SELECT HOUR(log_time) as hour, {avg_selects} 
            FROM raw_data 
            WHERE log_date = %s 
            GROUP BY HOUR(log_time)
        ''', (selected_date,))
        rows = c.fetchall()
        for r in rows:
            hour = int(r[0]) if r[0] is not None else 0
            for idx, label in enumerate(DATA_LABELS):
                if r[idx + 1] is not None:
                    hourly_data[(hour, label)] = round(float(r[idx + 1]), 1)
        return hourly_data
    finally:
        c.close()
        conn.close()

def get_graph_data_by_date(target_date):
    conn = get_db_raw_connection()
    c = conn.cursor(pymysql.cursors.DictCursor) # 💡 PyMySQL용 딕셔너리 리스트 추출 반환
    try:
        query = "SELECT log_time, " + ", ".join([f"`{name}`" for name in DATA_LABELS]) + " FROM raw_data WHERE log_date = %s ORDER BY log_time ASC"
        c.execute(query, (target_date,))
        return c.fetchall()
    finally:
        c.close()
        conn.close()

def get_manual_meter_by_date(target_date):
    conn = get_db_raw_connection()
    c = conn.cursor(pymysql.cursors.DictCursor)
    try:
        c.execute("SELECT * FROM manual_meter_logs WHERE log_date = %s", (target_date,))
        return c.fetchone()
    finally:
        c.close()
        conn.close()

def save_manual_meter_logs(target_date, data_dict):
    conn = get_db_raw_connection()
    c = conn.cursor()
    try:
        fields = ["log_date"] + METER_FIELDS
        placeholders = ", ".join(["%s"] * len(fields))
        update_clause = ", ".join([f"`{f}` = VALUES(`{f}`)" for f in METER_FIELDS])
        
        query = f"""
            INSERT INTO manual_meter_logs ({", ".join([f"`{f}`" for f in fields])})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        values = [target_date] + [data_dict.get(f, 0.0) for f in METER_FIELDS]
        c.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB 오류] 수동 검침 데이터 저장 실패: {e}")
        return False
    finally:
        c.close()
        conn.close()