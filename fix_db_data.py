# fix_db_data.py
import db_manager

def fix_database_errors():
    target_date = "2026-08-05"
    # 여러 시간대의 오류 발생 시간 목록
    error_times = ["16:47:42", "16:48:42", "16:49:42", "15:27:48", "15:26:48"]

    # 입력된 시간 데이터("HH:MM:SS")에서 시간("HH")만 추출하여 중복을 제거한 리스트 생성
    # 예: ["16", "15"]
    target_hours = list(set([time_str.split(":")[0] for time_str in error_times]))

    # 1. DB 연결
    conn = db_manager.get_db_raw_connection()
    c = conn.cursor()

    try:
        # ---------------------------------------------------------
        # [Step 1] 오류가 발생한 시간의 원시 데이터(raw_data) 일괄 삭제
        # ---------------------------------------------------------
        time_placeholders = ", ".join(["%s"] * len(error_times))
        delete_query = f"DELETE FROM raw_data WHERE log_date = %s AND log_time IN ({time_placeholders})"
        c.execute(delete_query, [target_date] + error_times)
        print(f"✅ {c.rowcount}개의 오류 레코드가 원시 데이터에서 삭제되었습니다.")

        # ---------------------------------------------------------
        # [Step 2] 추출된 각 시간대별(hourly_avg) 평균값 재계산 및 덮어쓰기
        # ---------------------------------------------------------
        avg_select = ", ".join([f'AVG(`{name}`)' for name in db_manager.DATA_LABELS])
        col_names = ", ".join([f'`{name}`' for name in db_manager.DATA_LABELS])
        
        # target_hours 리스트에 들어있는 시간(예: '15', '16')만큼 반복 실행
        for hour in target_hours:
            query_avg = f"SELECT {avg_select} FROM raw_data WHERE log_date = %s AND log_time LIKE %s"
            c.execute(query_avg, (target_date, f"{hour}:%"))
            result = c.fetchone()
            
            if result and result[0] is not None:
                # 소수점 1자리 반올림 적용
                rounded_result = [round(float(val), 1) if val is not None else 0.0 for val in result]
                placeholders = ", ".join(["%s"] * len(db_manager.DATA_LABELS))
                
                insert_query = f"REPLACE INTO hourly_avg (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
                c.execute(insert_query, [target_date, f"{hour}:00:00"] + rounded_result)
                print(f"✅ {hour}시 평균값이 성공적으로 재계산되어 반영되었습니다.")
            else:
                print(f"⚠️ {hour}시에 남아있는 원시 데이터가 없어 평균을 계산하지 못했습니다.")

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
    db_manager.calculate_daily_extremes(target_date)
    print(f"✅ {target_date} 일자의 전체 최고(MAX) / 최저(MIN) 값이 재계산되었습니다.")

if __name__ == "__main__":
    fix_database_errors()


