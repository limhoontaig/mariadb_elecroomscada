# migrate_db.py
import os
import sqlite3
import pymysql
# 기존 db_manager에서 설정값들을 가져옵니다.
from db_manager import DB_CONFIG, DB_DIR, DATA_LABELS, METER_FIELDS

# 1. 원본 SQLite3 파일 경로 지정
SQLITE_PATH = os.path.join(DB_DIR, "plc_logging_real.db")

def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ 원본 SQLite 파일이 존재하지 않습니다: {SQLITE_PATH}")
        return

    print("복사를 시작합니다...")
    
    # DB 연결
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cursor = sqlite_conn.cursor()
    
    maria_conn = pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        port=DB_CONFIG['port']
    )
    maria_cursor = maria_conn.cursor()

    # --- [테이블 1] raw_data 이관 ---
    print("⏳ raw_data 테이블 이관 중...")
    sqlite_cursor.execute("SELECT * FROM raw_data")
    rows = sqlite_cursor.fetchall()
    if rows:
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        placeholders = ", ".join(["%s"] * (len(DATA_LABELS) + 2))
        # MariaDB에는 REPLACE INTO를 사용하여 중복 방지
        query = f"REPLACE INTO raw_data (log_date, log_time, {col_names}) VALUES ({placeholders})"
        maria_cursor.executemany(query, rows)
        maria_conn.commit()
        print(f"✅ raw_data 완료 ({len(rows)}개 행 이동)")

    # --- [테이블 2] hourly_avg 이관 ---
    print("⏳ hourly_avg 테이블 이관 중...")
    sqlite_cursor.execute("SELECT * FROM hourly_avg")
    rows = sqlite_cursor.fetchall()
    if rows:
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        placeholders = ", ".join(["%s"] * (len(DATA_LABELS) + 2))
        query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES ({placeholders})"
        maria_cursor.executemany(query, rows)
        maria_conn.commit()
        print(f"✅ hourly_avg 완료 ({len(rows)}개 행 이동)")

    # --- [테이블 3] daily_extremes 이관 ---
    print("⏳ daily_extremes 테이블 이관 중...")
    sqlite_cursor.execute("SELECT * FROM daily_extremes")
    rows = sqlite_cursor.fetchall()
    if rows:
        col_names = ", ".join([f'`{name}`' for name in DATA_LABELS])
        placeholders = ", ".join(["%s"] * (len(DATA_LABELS) + 2))
        query = f"REPLACE INTO daily_extremes (log_date, `extreme_type`, {col_names}) VALUES ({placeholders})"
        maria_cursor.executemany(query, rows)
        maria_conn.commit()
        print(f"✅ daily_extremes 완료 ({len(rows)}개 행 이동)")

    # --- [테이블 4] manual_meter_logs (계량기 검침) 이관 ---
    print("⏳ manual_meter_logs 테이블 이관 중...")
    try:
        sqlite_cursor.execute("SELECT * FROM manual_meter_logs")
        rows = sqlite_cursor.fetchall()
        if rows:
            fields_str = "log_date, " + ", ".join([f"`{f}`" for f in METER_FIELDS])
            placeholders = ", ".join(["%s"] * (len(METER_FIELDS) + 1))
            query = f"REPLACE INTO manual_meter_logs ({fields_str}) VALUES ({placeholders})"
            maria_cursor.executemany(query, rows)
            maria_conn.commit()
            print(f"✅ manual_meter_logs 완료 ({len(rows)}개 행 이동)")
    except sqlite3.OperationalError:
        print("ℹ️ manual_meter_logs 테이블이 SQLite에 없어 건너뜁니다.")

    # --- [테이블 5] field_inspection (현장 점검) 이관 ---
    print("⏳ field_inspection 테이블 이관 중...")
    try:
        sqlite_cursor.execute("SELECT * FROM field_inspection")
        rows = sqlite_cursor.fetchall()
        if rows:
            query = "REPLACE INTO field_inspection (inspection_date, inspection_round, inspector_name, inspected_at) VALUES (%s, %s, %s, %s)"
            maria_cursor.executemany(query, rows)
            maria_conn.commit()
            print(f"✅ field_inspection 완료 ({len(rows)}개 행 이동)")
    except sqlite3.OperationalError:
        print("ℹ️ field_inspection 테이블이 SQLite에 없어 건너뜁니다.")

    # 연결 종료
    sqlite_cursor.close()
    sqlite_conn.close()
    maria_cursor.close()
    maria_conn.close()
    print("🎉 모든 데이터가 MariaDB(elecroomscada)로 성공적으로 이관되었습니다!")

if __name__ == "__main__":
    migrate()