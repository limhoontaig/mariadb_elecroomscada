# mariadb_backup.py
import os
import subprocess
from db_manager import DB_CONFIG

def backup_mariadb(save_filepath):
    """
    사용자가 UI에서 선택한 save_filepath 경로에 MariaDB 데이터를 .sql 파일로 백업합니다.
    반환값: (success_bool, message_or_path)
    """
    # 사용자가 대화창에서 선택한 파일의 절대 경로가 save_filepath로 전달됩니다.
    backup_dir = os.path.dirname(save_filepath)
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception as e:
        return False, f"백업 폴더 생성 실패: {str(e)}"
    
    # 본인 PC의 실제 MariaDB bin 폴더 내 mysqldump.exe 절대 경로
    mysqldump_path = r"C:\Program Files\MariaDB 12.3\bin\mysqldump.exe" 
    
    cmd = [
        mysqldump_path,
        f"-h{DB_CONFIG['host']}",
        f"-P{DB_CONFIG['port']}",
        f"-u{DB_CONFIG['user']}",
        f"-p{DB_CONFIG['password']}",
        DB_CONFIG['database']
    ]
    
    try:
        # 파일 쓰기 모드로 실행하여 덤프 데이터 출력 저장
        with open(save_filepath, "w", encoding="utf-8") as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
            
        print(f"[Backup Success] {save_filepath}")
        return True, save_filepath
        
    except subprocess.CalledProcessError as e:
        if os.path.exists(save_filepath):
            os.remove(save_filepath)
        error_msg = e.stderr if e.stderr else "mysqldump 프로세스 실행 오류"
        print(f"[Backup Error] {error_msg}")
        return False, error_msg
        
    except Exception as e:
        if os.path.exists(save_filepath):
            os.remove(save_filepath)
        print(f"[Backup Error] {str(e)}")
        return False, str(e)

if __name__ == "__main__":
    backup_mariadb()