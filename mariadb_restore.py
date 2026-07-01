import os
import subprocess
import pymysql
# 💡 파일 선택기를 위한 tkinter 라이브러리 추가
import tkinter as tk
from tkinter import filedialog

# 사무실 PC의 MariaDB 접속 정보 설정
OFFICE_DB_CONFIG = {
    'host': 'localhost',
    'user': 'scada_user',        
    'password': 'scada1234',     
    'database': 'elecroomscada',
    'port': 3306
}

def select_backup_file():
    """Windows 파일 탐색기 창을 띄워 .sql 백업 파일을 선택하도록 합니다."""
    # tkinter 윈도우 창이 화면에 나타나는 것을 숨김 처리
    root = tk.Tk()
    root.withdraw()
    
    # 💡 항상 최상단에 파일 선택 창이 뜨도록 설정 (다른 창에 가려지는 것 방지)
    root.attributes('-topmost', True)
    
    print("📂 복원할 백업 파일(.sql)을 선택해 주세요...")
    
    # 파일 탐색기 창 띄우기
    file_path = filedialog.askopenfilename(
        title="복원할 MariaDB 백업 파일 선택",
        filetypes=[("SQL Files", "*.sql"), ("All Files", "*.*")],
        initialdir=os.getcwd()  # 현재 프로그램이 실행된 폴더를 기본 위치로 지정
    )
    
    return file_path

def restore_mariadb(sql_filepath):
    """지정한 .sql 백업 파일을 사무실 DB에 복원합니다."""
    if not sql_filepath:
        print("❌ 파일 선택이 취소되었습니다.")
        return False
        
    if not os.path.exists(sql_filepath):
        print(f"❌ 복원할 SQL 파일을 찾을 수 없습니다: {sql_filepath}")
        return False

    mysql_path = r"C:\MariaDB2\bin\mysql.exe" 
    
    print("-" * 50)
    print(f"🔄 복원 대상 파일: {os.path.basename(sql_filepath)}")
    print("-" * 50)

    # 1. 기존 DB 삭제 및 재생성 (초기화)
    try:
        conn = pymysql.connect(
            host=OFFICE_DB_CONFIG['host'],
            user=OFFICE_DB_CONFIG['user'],
            password=OFFICE_DB_CONFIG['password'],
            port=OFFICE_DB_CONFIG['port']
        )
        cursor = conn.cursor()
        
        print("🧹 기존 데이터베이스 정리를 시작합니다...")
        cursor.execute(f"DROP DATABASE IF EXISTS `{OFFICE_DB_CONFIG['database']}`")
        cursor.execute(f"CREATE DATABASE `{OFFICE_DB_CONFIG['database']}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
        
        cursor.close()
        conn.close()
        print("✨ 데이터베이스 초기화 완료.")
    except Exception as e:
        print(f"❌ DB 초기화 중 오류 발생: {e}")
        return False

    # 2. mysql 명령어를 이용한 복원 진행
    cmd = [
        mysql_path,
        "--no-defaults",
        f"-h{OFFICE_DB_CONFIG['host']}",
        f"-P{OFFICE_DB_CONFIG['port']}",
        f"-u{OFFICE_DB_CONFIG['user']}",
        f"-p{OFFICE_DB_CONFIG['password']}",
        OFFICE_DB_CONFIG['database']
    ]
    
    try:
        print("📥 데이터 복원을 시작합니다. 잠시만 기다려주세요...")
        with open(sql_filepath, "r", encoding="utf-8") as f:
            subprocess.run(cmd, stdin=f, check=True)
            
        print(f"\n✅ 성공: 현재 사무실 DB가 현장 데이터로 동기화되었습니다!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ DB 복원 실패 (명령어 에러): {e}")
        return False
    except Exception as e:
        print(f"❌ 복원 중 알 수 없는 오류 발생: {e}")
        return False

if __name__ == "__main__":
    # 1. 실행하자마자 파일 선택기를 띄움
    selected_file = select_backup_file()
    
    # 2. 사용자가 파일을 선택했다면 복원 프로세스 작동
    if selected_file:
        restore_mariadb(selected_file)
    else:
        print("❌ 복원 작업이 사용자에 의해 취소되었습니다.")

