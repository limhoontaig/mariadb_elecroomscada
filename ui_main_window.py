# ui_main_window.py
import os
from datetime import datetime
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QDateEdit, QPushButton, QStackedWidget, QSplitter, 
                             QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog)
from PyQt5.QtCore import QTimer, QDate, Qt

# 💡 백엔드 컴포넌트 임포트 분리
import db_manager
import excel_report
from ui_graph_manager import GraphManager
from ui_dialogs import ManualMeterInputDialog, FieldInspectionDialog 

class SCADAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
        # 10초 주기 자동 화면 동기화 타이머 가동
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(10000) 
        self.last_hour = datetime.now().hour

    def initUI(self):
        self.setWindowTitle("변전실 데이터 통합 관리 시스템 (리모델링 Ver)")
        self.resize(1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ==================== 상단 제어 센터 ====================\
        top_ctrl = QHBoxLayout()
        top_ctrl.addWidget(QLabel("조회/기준 일자:"))
        
        self.qdate = QDateEdit(QDate.currentDate())
        self.qdate.setCalendarPopup(True)
        self.qdate.dateChanged.connect(self.load_data) # 날짜 변경 시 즉시 동기화
        top_ctrl.addWidget(self.qdate)
        
        # UI 기능 버튼 배열
        self.btn_refresh = QPushButton("🔄 수동 새로고침")
        self.btn_refresh.clicked.connect(self.load_data)
        top_ctrl.addWidget(self.btn_refresh)
        
        self.btn_meter_input = QPushButton("📝 수동 검침/지침 입력")
        self.btn_meter_input.clicked.connect(self.open_manual_meter_dialog)
        top_ctrl.addWidget(self.btn_meter_input)
        
        self.btn_inspect_input = QPushButton("🏃 현장 순찰 일지 등록")
        self.btn_inspect_input.clicked.connect(self.open_field_inspection_dialog)
        top_ctrl.addWidget(self.btn_inspect_input)
        
        self.btn_excel = QPushButton("📊 엑셀 운영일지 출력")
        self.btn_excel.clicked.connect(self.export_excel_report)
        top_ctrl.addWidget(self.btn_excel)
        
        main_layout.addLayout(top_ctrl)

        # ==================== 중앙 분할 레이아웃 (표 / 그래프) ====================
        splitter = QSplitter(Qt.Horizontal)
        
        # 왼쪽 구역: 데이터 그리드 뷰 표 생성
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        
        table_group = QGroupBox("실시간 PLC 수집 트랙 로그 (24시간 데이터 리스트)")
        table_vbox = QVBoxLayout(table_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(len(db_manager.DATA_LABELS) + 2)
        self.table.setHorizontalHeaderLabels(["수집일자", "수집시간"] + db_manager.DATA_LABELS)
        table_vbox.addWidget(self.table)
        left_layout.addWidget(table_group)
        
        splitter.addWidget(left_widget)
        
        # 오른쪽 구역: 그래프 매니저 연동
        self.graph_manager = GraphManager(self)
        splitter.addWidget(self.graph_manager)
        
        # 좌우 화면 비율 조정 (표 6 : 그래프 4)
        splitter.setSizes([840, 560])
        main_layout.addWidget(splitter)
        
        # 최초 1회 데이터 로드 실행
        self.load_data()

    def load_data(self):
        """[UI 기능] 선택된 날짜의 모든 데이터를 DB 창구로부터 호출하여 화면에 바인딩합니다."""
        selected_date_str = self.qdate.date().toString("yyyy-MM-dd")
        
        # 💡 리모델링 핵심: db_manager API 호출로 위임 (SQL문 완전 제거)
        rows = db_manager.get_realtime_grid_data(selected_date_str)
        
        self.table.setRowCount(0)
        if not rows:
            return
            
        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                if value is None:
                    item_text = "-"
                elif isinstance(value, float):
                    item_text = f"{value:.1f}"
                else:
                    item_text = str(value)
                    
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(item_text))
                
        # 데이터가 변경되었으므로 우측 그래프도 동기화 갱신 트리거
        if hasattr(self, 'graph_manager'):
            self.graph_manager.update_graph()

    def auto_refresh(self):
        """[UI 기능] 10초 주기로 현재 보고 있는 화면을 자동으로 갱신합니다."""
        current_date = QDate.currentDate()
        # 만약 메인 화면이 오늘 날짜를 보고 있다면 실시간 갱신 처리
        if self.qdate.date() == current_date:
            self.load_data()
            
        # 정시 정각 주기 체크 로직 (통계 연산 스케줄링 방어선)
        now_hour = datetime.now().hour
        if now_hour != self.last_hour:
            self.last_hour = now_hour
            print(f"[알림] {now_hour}시 정각 통계 동기화 상태 점검 완료.")

    def open_manual_meter_dialog(self):
        """[다이어로그 팝업] 수동 지침 입력 창을 엽니다."""
        date_str = self.qdate.date().toString("yyyy-MM-dd")
        dialog = ManualMeterInputDialog(default_date_str=date_str, parent=self)
        if dialog.exec_():
            self.load_data()

    def open_field_inspection_dialog(self):
        """[다이어로그 팝업] 현장 순찰 등록 창을 엽니다."""
        date_str = self.qdate.date().toString("yyyy-MM-dd")
        dialog = FieldInspectionDialog(default_date_str=date_str, parent=self)
        if dialog.exec_():
            self.load_data()

    def export_excel_report(self):
        """[엑셀 출력 버튼 연동] 지정 폴더에 운영일지를 작성하여 저장합니다."""
        selected_date_str = self.qdate.date().toString("yyyy-MM-dd")
        
        # 사용자 편의용 기본 파일명 제안
        default_name = f"{selected_date_str}_전기실_운영일지.xlsx"
        target_dir = QFileDialog.getExistingDirectory(self, "운영일지 저장 폴더 선택")
        
        if not target_dir:
            return # 사용자가 취소한 경우 리턴
            
        try:
            # 💡 3단계에서 리모델링한 안전 엑셀 엔진 호출
            success = excel_report.generate_excel_report(selected_date_str, target_dir=target_dir)
            if success:
                QMessageBox.information(self, "출력 완료", f"지정하신 폴더에 운영일지가 성공적으로 생성되었습니다!\n파일: {default_name}")
            else:
                QMessageBox.warning(self, "출력 실패", "데이터베이스 누락 또는 파일 권한으로 인해 엑셀 작성에 실패했습니다.\n콘솔 로그를 확인하세요.")
        except Exception as e:
            QMessageBox.critical(self, "시스템 에러", f"엑셀 리포트 처리 중 치명적 오류 발생:\n{e}")