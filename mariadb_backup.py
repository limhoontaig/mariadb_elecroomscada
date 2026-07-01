import os
import subprocess
from datetime import datetime
from db_manager import DB_CONFIG

def backup_mariadb():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{DB_CONFIG['database']}_{timestamp}.sql"
    
    # 💡 다른 하드디스크(예: E드라이브)의 특정 폴더로 저장 경로 설정
    # (원하시는 백업 하드디스크 경로로 수정하세요)
    backup_dir = "E:\\db_backups" 
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    os.makedirs(backup_dir, exist_ok=True)
    
    # 💡 [핵심] 본인 PC의 실제 MariaDB bin 폴더 내 mysqldump.exe 경로를 입력하세요.
    # 경로에 공백이 있을 수 있으므로 파일 경로 전체를 정확히 적어줍니다.
    mysqldump_path = r"C:\Program Files\MariaDB 12.3\bin\mysqldump.exe" 
    
    cmd = [
        mysqldump_path,  # 💡 명령어 대신 절대 경로 사용
        f"-h{DB_CONFIG['host']}",
        f"-P{DB_CONFIG['port']}",
        f"-u{DB_CONFIG['user']}",
        f"-p{DB_CONFIG['password']}",
        DB_CONFIG['database']
    ]
    
    try:
        with open(backup_filepath, "w", encoding="utf-8") as f:
            subprocess.run(cmd, stdout=f, check=True)
        print(f"✅ DB 백업 성공: {backup_filepath}")
        return backup_filepath
    except subprocess.CalledProcessError as e:
        print(f"❌ DB 백업 실패: {e}")
        return None

if __name__ == "__main__":
    backup_mariadb()