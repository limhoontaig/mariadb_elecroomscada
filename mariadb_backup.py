# mariadb_backup.py 에 아래 함수를 추가하거나 교체합니다.
import os
import subprocess
from datetime import datetime
from db_manager import DB_CONFIG

# config.ini 파일 읽기
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_backup_dir():
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('BACKUP_DIR', r'D:\db_backups\yearly_regular')
    return r'D:\db_backups\yearly_regular'

def auto_backup_by_year():
    """
    [정기 백업] 연도별로 하나의 파일(예: elecroomscada_2026.sql)을 생성하여 
    그 해 전체 데이터를 매번 최신 상태로 갱신(덮어쓰기)합니다.
    """
    current_year = datetime.now().strftime("%Y")
    backup_filename = f"{DB_CONFIG['database']}_{current_year}.sql"
    
    # 💡 정기 백업이 저장될 고정 폴더 설정 (원하는 경로로 수정 가능)
    backup_dir = get_backup_dir()
    
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception as e:
        print(f"[정기 백업 실패] 폴더 생성 오류: {str(e)}")
        return False
        
    backup_filepath = os.path.join(backup_dir, backup_filename)
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
        with open(backup_filepath, "w", encoding="utf-8") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
        print(f"⏰ [정기 백업 성공] {backup_filepath} (최신화 완료)")
        return True
    except Exception as e:
        print(f"❌ [정기 백업 실패] 오류 발생: {str(e)}")
        return False

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