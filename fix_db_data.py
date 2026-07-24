# fix_db_data.py
import db_manager

def fix_database_errors():
    target_date = "2026-07-10"
    target_hour = "21"
    error_times = ["21:48:45", "21:48:46"]

    # 1. DB 연결
    conn = db_manager.get_db_raw_connection()
    c = conn.cursor()

    try:
        # ---------------------------------------------------------
        # [Step 1] 오류가 발생한 시간의 원시 데이터(raw_data) 삭제
        # ---------------------------------------------------------
        delete_query = "DELETE FROM raw_data WHERE log_date = %s AND log_time IN (%s, %s)"
        c.execute(delete_query, (target_date, error_times[0], error_times[1]))
        print(f"✅ {c.rowcount}개의 오류 레코드가 원시 데이터에서 삭제되었습니다.")

        # ---------------------------------------------------------
        # [Step 2] 21시 구간의 시간당 평균값(hourly_avg) 재계산 및 덮어쓰기
        # ---------------------------------------------------------
        avg_select = ", ".join([f'AVG(`{name}`)' for name in db_manager.DATA_LABELS])
        col_names = ", ".join([f'`{name}`' for name in db_manager.DATA_LABELS])
        
        # 삭제된 데이터를 제외하고 21:00:00 ~ 21:59:59 사이의 평균을 다시 구함
        query_avg = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
        c.execute(query_avg, (target_date, f"{target_hour}:%"))
        result = c.fetchone()
        
        if result and result[0] is not None:
            # db_manager.py와 동일하게 소수점 1자리 반올림 적용
            rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
            placeholders = ", ".join(["%s"] * len(db_manager.DATA_LABELS))
            
            # REPLACE INTO를 사용하여 기존의 잘못된 21시 평균 데이터를 덮어씀
            insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
            c.execute(insert_query, [target_date, f"{target_hour}:00:00"] + rounded_result)
            print("✅ 21시 평균값이 성공적으로 재계산되어 반영되었습니다.")

        conn.commit()

    except Exception as e:
        print(f"❌ 데이터베이스 처리 중 오류 발생: {e}")
        conn.rollback()
    finally:
        c.close()
        conn.close()

    # ---------------------------------------------------------
    # [Step 3] 일일 최고/최저값(daily_extremes) 재계산
    # ---------------------------------------------------------
    # db_manager.py에 이미 구현된 함수를 그대로 활용하여 7월 10일 전체의 MAX/MIN 통계를 갱신합니다.
    db_manager.calculate_daily_extremes(target_date)
    print(f"✅ {target_date} 일자의 전체 최고(MAX) / 최저(MIN) 값이 재계산되었습니다.")

if __name__ == "__main__":
    fix_database_errors()