# main.py
import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QSplashScreen, QDesktopWidget
from PyQt5.QtCore import Qt, QCoreApplication, QThread, pyqtSignal
from PyQt5.QtGui import QCursor, QFont

# 최상위 관리 모듈 로드 (윈도우 로드는 지연 가능하도록 아래에서 하거나 그대로 둠)
import db_manager
import plc_worker

def center_window(widget):
    """위젯을 화면 중앙으로 이동시키는 함수"""
    qr = widget.frameGeometry()
    cp = QDesktopWidget().availableGeometry().center()
    qr.moveCenter(cp)
    widget.move(qr.topLeft())

# 초기화를 담당할 백그라운드 스레드
class InitWorker(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def run(self):
        # 1단계: DB 초기화 (가장 오래 걸리는 작업)
        self.progress_signal.emit("⚡ 데이터베이스 연결 및 구성 중...")
        db_manager.init_db()
        time.sleep(0.3) 
        
        # 2단계: PLC 통신 스레드 기동
        self.progress_signal.emit("🔌 PLC 통신 엔진 시작 중...")
        t = threading.Thread(target=plc_worker.serial_receive_thread, daemon=True)
        t.start()
        time.sleep(0.3)
        
        # 3단계: 준비 완료 신호
        self.progress_signal.emit("🖥️ 시스템 화면 생성 중...")
        self.finished_signal.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 1. Splash Screen 즉시 생성 및 표시 (메인 스레드 가볍게 유지)
    splash = QSplashScreen()
    splash.setFixedSize(600, 400)
    splash.setStyleSheet("""
        QSplashScreen {
            background-color: #2c3e50;
            color: white;
            border: 3px solid #34495e;
            border-radius: 15px;
        }
    """)
    
    font = QFont("Malgun Gothic", 18, QFont.Bold)
    splash.setFont(font)
    center_window(splash)
    splash.show()
    splash.raise_()
    
    app.setOverrideCursor(QCursor(Qt.WaitCursor))
    splash.showMessage("\n\n\n\n🚀 시스템 엔진 기동 준비 중...", 
                       Qt.AlignCenter | Qt.AlignVCenter, Qt.white)
    
    # Splash 화면을 OS가 즉시 그리도록 강제 이벤트를 처리
    # 이 시점에는 무거운 객체가 전혀 없으므로 Splash가 0.1초 만에 팍 뜹니다.
    for _ in range(5):
        QCoreApplication.processEvents()
    
    # 2. 백그라운드 스레드 생성 및 시작
    worker = InitWorker()
    
    # 진행 메시지 반영
    worker.progress_signal.connect(
        lambda msg: splash.showMessage(f"\n\n\n\n{msg}", Qt.AlignCenter | Qt.AlignVCenter, Qt.white)
    )
    
    # 전역 참조용 메인 윈도우 변수 선언 (가비지 컬렉션 방지)
    win = None
    
    # ⭐ [핵심 개선] DB 초기화 등이 '완전히 끝난 후' 메인 윈도우를 비로서 임포트하고 생성합니다.
    def on_init_finished():
        global win
        
        # 메인 윈도우 모듈을 이 시점에 로드하여 초기 기동 속도를 극대화
        from ui_main_window import SCADAWindow 
        
        # DB 작업이 끝난 평온한 상태에서 메인 창 생성
        win = SCADAWindow()
        center_window(win)
        
        # 최상단 고정으로 메인 화면 표시
        win.setWindowFlags(win.windowFlags() | Qt.WindowStaysOnTopHint)
        win.show()
        
        # 고정 해제 및 포커스 집중
        win.setWindowFlags(win.windowFlags() & ~Qt.WindowStaysOnTopHint) 
        win.show()
        win.raise_()
        win.activateWindow()
        
        # 로딩 창 깔끔하게 종료
        splash.finish(win)
        app.restoreOverrideCursor()

    worker.finished_signal.connect(on_init_finished)
    
    # 3. 백그라운드 초기화 작업 시작
    worker.start()
    
    sys.exit(app.exec_())