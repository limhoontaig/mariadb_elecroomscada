# maria_main.py
import sys
import threading
import time
from PyQt5.QtWidgets import QApplication, QSplashScreen, QDesktopWidget, QMessageBox
from PyQt5.QtCore import Qt, QCoreApplication, QThread, pyqtSignal, QSharedMemory
from PyQt5.QtGui import QCursor, QFont

# 최상위 관리 모듈 로드
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
        # 1단계: DB 초기화 
        self.progress_signal.emit("⚡ 데이터베이스 연결 및 구성 중...")
        db_manager.init_db()
        time.sleep(0.3) 
        
        # 2단계: PLC 통신 스레드 기동 
        # (주의: 여기서 데몬 스레드로 확실하게 띄워주어야 통신이 먹통되지 않습니다)
        self.progress_signal.emit("🔌 PLC 통신 엔진 시작 중...")
        t = threading.Thread(target=plc_worker.serial_receive_thread, daemon=True)
        t.start()
        time.sleep(0.3)
        
        # 3단계: 준비 완료 신호
        self.progress_signal.emit("🖥️ 시스템 화면 생성 중...")
        self.finished_signal.emit()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 프로그램 중복 실행 방지
    shared_memory = QSharedMemory("LS_PLC_SCADA_Shared_Memory")
    if not shared_memory.create(1):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("실행 경고")
        msg.setText("이미 프로그램이 실행중에 있습니다. 필요시 실행되고 있는 프로그램을 중지하고 다시 실행하여 주시기 바랍니다.")
        msg.exec_()
        sys.exit(0)
    
    # 1. Splash Screen 즉시 생성 및 표시
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
    
    for _ in range(5):
        QCoreApplication.processEvents()
    
    worker = InitWorker()
    
    worker.progress_signal.connect(
        lambda msg: splash.showMessage(f"\n\n\n\n{msg}", Qt.AlignCenter | Qt.AlignVCenter, Qt.white)
    )
    
    win = None
    
    def on_init_finished():
        global win
        from ui_main_window import SCADAWindow 
        
        win = SCADAWindow()
        center_window(win)

        # 💡 [가장 중요한 핵심 코드] 통신 모듈과 메인 화면 라벨을 여기서 연결해야 화면에 '통신 정상'이 뜹니다.
        import plc_worker
        plc_worker.comm_signal.status_changed.connect(win.update_rs485_status)
        
        win.setWindowFlags(win.windowFlags() | Qt.WindowStaysOnTopHint)
        win.show()
        
        win.setWindowFlags(win.windowFlags() & ~Qt.WindowStaysOnTopHint) 
        win.show()
        win.raise_()
        win.activateWindow()
        
        splash.finish(win)
        app.restoreOverrideCursor()

    worker.finished_signal.connect(on_init_finished)
    worker.start()
    
    sys.exit(app.exec_())