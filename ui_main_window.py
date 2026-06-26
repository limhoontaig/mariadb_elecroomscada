# ui_main_window.py 수정본
import os
import sqlite3
from datetime import datetime

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QDateEdit, QPushButton, QStackedWidget, QSplitter, 
                             QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog)
from PyQt5.QtCore import QTimer, QDate, Qt

# 🌟 신규 분리한 그래프 매니저 임포트
from ui_graph_manager import GraphManager

import db_manager
import excel_report
from ui_dialogs import ManualMeterInputDialog, FieldInspectionDialog 

class SCADAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_refresh)
        self.timer.start(10000) 
        self.last_hour = datetime.now().hour

    def initUI(self):
        self.setWindowTitle("래미안개포루체하임아파트 변전실 데이터 통합 관리 시스템 (Developed by 관리과장 임훈택)")
        self.resize(1400, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ==================== 상단 제어 센터 ====================
        top_ctrl = QGroupBox("운영 제어 센터")
        top_layout = QHBoxLayout(top_ctrl)
        top_layout.setSpacing(50)
        
        self.qdate = QDateEdit(QDate.currentDate())
        self.qdate.setCalendarPopup(True)
        self.qdate.setMinimumWidth(120) 
        self.qdate.setAlignment(Qt.AlignCenter) 
        self.qdate.setStyleSheet("font-size: 14px; padding: 3px; font-weight: bold;") 
        
        lbl_date_title = QLabel("<b>선택 날짜:</b>")
        lbl_date_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        
        self.btn_show_table = QPushButton("종합 데이터 표")
        self.btn_show_table.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; min-height: 35px;")
        self.btn_show_graph = QPushButton("부하 변동 그래프")
        self.btn_show_graph.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; min-height: 35px;")
        self.btn_export_excel = QPushButton("엑셀 운영일지 출력")
        self.btn_export_excel.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; min-height: 35px;")
        self.btn_meter_input = QPushButton("전력량계 검침량 입력") 
        self.btn_meter_input.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; min-height: 35px;")
        self.btn_field_inspection = QPushButton("현장 점검 입력")
        self.btn_field_inspection.setStyleSheet("background-color: #E67E22; color: white; font-weight: bold; min-height: 35px;")
        self.btn_field_inspection.clicked.connect(self.click_open_inspection_popup) # # 👈 레이아웃에 추가 이벤트 연결
        
        top_layout.addWidget(lbl_date_title)
        top_layout.addWidget(self.qdate)
        top_layout.addWidget(self.btn_show_table)
        top_layout.addWidget(self.btn_show_graph)
        top_layout.addWidget(self.btn_export_excel)
        top_layout.addWidget(self.btn_meter_input)
        top_layout.addWidget(self.btn_field_inspection)  # 👈 레이아웃에 추가  
        main_layout.addWidget(top_ctrl)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # ==================== 1. 테이블 탭 구성 ====================
        self.page_table = QWidget()
        table_layout = QVBoxLayout(self.page_table)
        splitter = QSplitter(Qt.Vertical)
        
        self.raw_table = QTableWidget()
        self.raw_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.raw_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)
        
        self.avg_table = QTableWidget()
        self.avg_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.avg_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)

        self.extreme_table = QTableWidget()
        self.extreme_table.setColumnCount(len(db_manager.COLUMN_LABELS))
        self.extreme_table.setHorizontalHeaderLabels(db_manager.COLUMN_LABELS)

        self.manual_table = QTableWidget()
        manual_headers = ["기록 일자"] + db_manager.METER_FIELDS 
        self.manual_table.setColumnCount(len(manual_headers))
        self.manual_table.setHorizontalHeaderLabels(manual_headers)

        splitter.addWidget(QLabel("● 실시간 계측 데이터 로그"))
        splitter.addWidget(self.raw_table)
        splitter.addWidget(QLabel("● 시간별 평균 전력 추이"))
        splitter.addWidget(self.avg_table)
        splitter.addWidget(QLabel("● 일일 최고(MAX) / 최저(MIN) 값 설비 통계"))
        splitter.addWidget(self.extreme_table)
        splitter.addWidget(QLabel("● 독립 계량장치 일일 지침 수동 로그 (manual_meter_logs)"))
        splitter.addWidget(self.manual_table)

        table_layout.addWidget(splitter)
        self.stack.addWidget(self.page_table)

        # ==================== 2. 그래프 탭 구성 (🌟대폭 다이어트) ====================
        # 복잡했던 레이아웃과 리스트 코드는 전부 ui_graph_manager 내부로 들어갔습니다.
        self.graph_manager = GraphManager(self) 
        self.stack.addWidget(self.graph_manager)

        # ==================== 3. 이벤트 시그널 연결 ====================
        self.btn_show_table.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_show_graph.clicked.connect(self.on_graph_tab_changed) # 변경
        self.btn_export_excel.clicked.connect(self.export_excel_click)
        self.btn_meter_input.clicked.connect(self.click_open_meter_popup)
        self.qdate.dateChanged.connect(self.auto_refresh)

        self.load_data()

    def on_graph_tab_changed(self):
        """그래프 탭으로 전환될 때 즉시 그래프를 그리도록 지시하는 함수"""
        self.stack.setCurrentIndex(1)
        self.graph_manager.update_graph()

    def load_data(self):
        selected_date = self.qdate.date().toString("yyyy-MM-dd")
        db_manager.calculate_daily_extremes(selected_date)
        
        try:
            conn = db_manager.get_db_raw_connection()
            c = conn.cursor()
            
            # 💡 [핵심 수정] % 기호를 %%로 두 번씩 적어줍니다 (Python 문자열 포맷팅 충돌 방지)
            query_raw = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), TIME_FORMAT(log_time, '%%H:%%i:%%s'), {', '.join([f'`{n}`' for n in db_manager.DATA_LABELS])} FROM raw_data WHERE log_date = %s ORDER BY log_time DESC"
            c.execute(query_raw, (selected_date,))
            self.display_table(self.raw_table, c.fetchall())
            
            # 💡 [핵심 수정] 여기도 %%Y, %%m, %%d, %%H, %%i, %%s로 변경
            query_avg = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), TIME_FORMAT(log_time, '%%H:%%i:%%s'), {', '.join([f'`{n}`' for n in db_manager.DATA_LABELS])} FROM hourly_avg WHERE log_date = %s ORDER BY log_time DESC"
            c.execute(query_avg, (selected_date,))
            self.display_table(self.avg_table, c.fetchall())
            
            # 💡 [핵심 수정] 여기도 %%Y, %%m, %%d로 변경
            query_ext = f"SELECT DATE_FORMAT(log_date, '%%Y-%%m-%%d'), extreme_type, {', '.join([f'`{n}`' for n in db_manager.DATA_LABELS])} FROM daily_extremes WHERE log_date = %s ORDER BY extreme_type DESC"
            c.execute(query_ext, (selected_date,))
            self.display_table(self.extreme_table, c.fetchall(), is_extreme=True)
            
            c.close()
            conn.close()

            if hasattr(db_manager, 'get_manual_meter_log_for_table'):
                manual_row = db_manager.get_manual_meter_log_for_table(selected_date)
                self.display_manual_table([manual_row])

        except Exception as e:
            print(f"UI 로딩 실패: {e}")

    def display_manual_table(self, rows):
        self.manual_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if c_idx > 0 and val != "-":
                    item.setForeground(Qt.darkGreen)
                self.manual_table.setItem(r_idx, c_idx, item)

    def display_table(self, table, rows, is_extreme=False):
        table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                txt = f"{val:.1f}" if isinstance(val, float) else str(val)
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignCenter)

                if is_extreme and c_idx > 1:
                    if row[1] == 'MAX': item.setForeground(Qt.red)
                    elif row[1] == 'MIN': item.setForeground(Qt.blue)
                table.setItem(r_idx, c_idx, item)

    def export_excel_click(self):
        """[오류 수정] 상단 버튼으로 운영일지 엑셀 출력 시 정확한 함수명 호출"""
        target_date_str = self.qdate.date().toString("yyyy-MM-dd")
        
        # 1단계: 안내 메시지창 표시
        reply = QMessageBox.question(
            self, 
            "운영일지 엑셀 출력 안내", 
            f"선택하신 날짜 [{target_date_str}]의 운영일지를 엑셀 파일로 출력합니다.\n\n"
            "다음 화면에서 엑셀 파일이 저장될 '컴퓨터 폴더(디렉토리)'를 지정해 주세요.\n"
            "진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.No:
            return

        # 2단계: 폴더 선택 창 열기
        dir_path = QFileDialog.getExistingDirectory(self, "엑셀 파일 저장 폴더 선택", "D:\\전기실_운전일지")
        if not dir_path:
            QMessageBox.warning(self, "출력 취소", "저장할 폴더가 선택되지 않아 엑셀 출력을 취소합니다.")
            return

        # 3단계: excel_report.py에 실제 존재하는 함수 호출로 수정
        try:
            # 💡 매개변수 구조를 excel_report.py의 정의에 맞춰 올바르게 호출합니다.
            excel_report.generate_excel_report(target_date_str, target_dir=dir_path)
            
            QMessageBox.information(
                self, 
                "출력 완료", 
                f"[{target_date_str}] 운영일지가 성공적으로 저장되었습니다.\n\n"
                f"저장위치: {dir_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "오류 발생", 
                f"엑셀 운영일지 생성 중 오류가 발생했습니다.\n"
                f"템플릿 파일이 정상적인 위치에 있는지 확인하세요.\n\n"
                f"에러 내용: {e}"
            )
        
    def auto_refresh(self):
        curr_hour = datetime.now().hour
        if curr_hour != self.last_hour:
            self.last_hour = curr_hour
            db_manager.calculate_hourly_avg()
        self.load_data()
        self.graph_manager.update_graph() # 분리한 객체의 함수 호출

    def click_open_meter_popup(self):
        current_date_str = self.qdate.date().toString("yyyy-MM-dd")
        dialog = ManualMeterInputDialog(None, self)
        result = dialog.exec_()
        
        if result == 1: 
            save_date = dialog.date_edit.date().toString("yyyy-MM-dd")
            final_data = {field: edit.text().strip() for field, edit in dialog.inputs.items()}

            # -----------------------------------------------------------------
            # 💡 [개선] 데이터 저장 방식을 3단계로 선택할 수 있는 커스텀 알림창 생성
            # -----------------------------------------------------------------
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("데이터 처리 방식 선택")
            msg_box.setText(f"[{save_date}] 수동 입력 지침 데이터를 어떻게 처리하시겠습니까?")
            
            # 3개의 버튼 추가 및 직관적인 텍스트 설정
            btn_save_only = msg_box.addButton("데이터 저장만", QMessageBox.ActionRole)
            btn_save_and_export = msg_box.addButton("데이터 저장 및 출력", QMessageBox.ActionRole)
            btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
            
            msg_box.setDefaultButton(btn_save_and_export) # 기본 포커스는 가장 많이 쓰는 '저장 및 출력'
            msg_box.exec_() # 알림창 실행
            
            clicked_button = msg_box.clickedButton()

            # 1️⃣ [취소]를 누른 경우: 아무 작업도 하지 않고 리턴 (팝업창으로 돌아갈 수 있도록)
            if clicked_button == btn_cancel:
                print("[INFO] 사용자가 저장을 취소했습니다.")
                return

            # 2️⃣ [데이터 저장만] 또는 [데이터 저장 및 출력] 공통: 우선 DB에 안전하게 저장
            try:
                db_manager.save_manual_meter_data(save_date, final_data)
                
                # -------------------------------------------------------------
                # 2-A. [데이터 저장만] 선택 시 로직
                # -------------------------------------------------------------
                if clicked_button == btn_save_only:
                    self.load_data() # 메인 화면 갱신
                    QMessageBox.information(self, "저장 완료", "데이터가 데이터베이스(DB)에 성공적으로 기록되었습니다.")
                    return
                
                # -------------------------------------------------------------
                # 2-B. [데이터 저장 및 출력] 선택 시 로직 (기존 안내 및 폴더 선택)
                # -------------------------------------------------------------
                elif clicked_button == btn_save_and_export:
                    # 폴더 지정 안내창 표시
                    folder_guide = QMessageBox.question(
                        self, 
                        "운영일지 저장 폴더 안내", 
                        "데이터 저장이 완료되었습니다.\n\n"
                        "이어서 전기실 운영일지 엑셀 파일 생성을 진행합니다.\n"
                        "다음 화면에서 파일이 저장될 '컴퓨터 폴더(디렉토리)'를 선택해 주세요.",
                        QMessageBox.Yes | QMessageBox.No, 
                        QMessageBox.Yes
                    )
                    
                    if folder_guide == QMessageBox.No:
                        self.load_data()
                        QMessageBox.information(self, "안내", "DB 저장은 완료되었으나, 사용자가 엑셀 출력을 취소했습니다.")
                        return

                    # 폴더 선택 창 열기
                    selected_dir = QFileDialog.getExistingDirectory(self, "운영일지 저장 폴더 선택", "D:\\전기실_운전일지")
                    if not selected_dir: 
                        self.load_data()
                        QMessageBox.warning(self, "출력 취소", "저장할 폴더가 선택되지 않아 엑셀 출력을 취소합니다.\n(DB 데이터는 안전하게 저장되었습니다.)")
                        return
                    
                    # 엑셀 파일 생성
                    excel_report.generate_excel_report(save_date, target_dir=selected_dir)
                    self.load_data()
                    
                    QMessageBox.information(
                        self, 
                        "처리 완료", 
                        f"데이터 DB 반영 및 엑셀 일지 작성이 모두 성공적으로 완료되었습니다.\n\n"
                        f"저장위치: {selected_dir}"
                    )
                    
            except Exception as e:
                QMessageBox.critical(self, "오류 발생", f"데이터 처리 중 에러가 발생했습니다: {e}")
    
    # ui_main_window.py 내의 기존 해당 함수를 아래 코드로 교체합니다.
    def click_open_inspection_popup(self):
        """[현장 점검 입력] 버튼을 눌렀을 때 실행되는 함수 (조회 날짜 무시, 무조건 '오늘'로 강제 고정)"""
        # 🌟 핵심 수정: 메인 화면의 self.qdate.date()를 무시하고, 무조건 실제 오늘 날짜(Today)를 따옵니다.
        today_date_str = datetime.now().strftime("%Y-%m-%d")
        
        # 팝업 다이얼로그를 띄울 때 오늘 날짜를 기본값으로 주입합니다.
        dialog = FieldInspectionDialog(today_date_str, self)
        result = dialog.exec_()
        
        if result == 1: # 사용자가 팝업창에서 OK(확인) 버튼을 누른 경우
            # 팝업창 내부의 날짜를 가져오더라도 무조건 오늘 날짜입니다.
            save_date = today_date_str 
            round_idx = dialog.combo_round.currentIndex() + 1 # 선택한 차수 (1, 2, 3)
            inspector = dialog.input_name.text().strip()
            
            # -------------------------------------------------------------
            # 선행 등록된 점검자가 있는지 '오늘 날짜' 기준으로 사전 검사
            # -------------------------------------------------------------
            existing_inspections = db_manager.get_field_inspections_for_date(save_date)
            target_round_data = existing_inspections.get(round_idx, {"name": "", "time": ""})
            
            # 만약 오늘 선택한 차수에 이미 기록이 존재한다면!
            if target_round_data["name"] != "":
                old_name = target_round_data["name"]
                old_time = target_round_data["time"]
                
                # 근무자에게 경고창을 띄우고 기존 정보를 고지합니다.
                reply = QMessageBox.question(
                    self, '⚠️ 오늘 점검 기록 중복 경고',
                    f"오늘({save_date}) 해당 차수에는 이미 등록된 점검 기록이 존재합니다.\n\n"
                    f"■ 차수: {round_idx}차 점검\n"
                    f"■ 기존 점검자: {old_name}\n"
                    f"■ 기록 시간: {old_time}\n\n"
                    f"현재 입력하신 [{inspector}] 성명으로 기존 기록을 덮어쓰시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.No:
                    print(f"[INFO] 오늘자 {round_idx}차 점검 입력이 취소되었습니다.")
                    return
            else:
                # 당일 최초 입력 시 확인창
                reply = QMessageBox.question(
                    self, '점검 등록 확인', 
                    f"오늘 날짜 [{save_date}] 기준으로 {round_idx}차 현장점검을 완료 처리하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                
                if reply == QMessageBox.No:
                    return
            
            # -------------------------------------------------------------
            # 💾 최종 데이터베이스 반영 (db_manager 내부에서 현재 컴퓨터 시간 주입)
            # -------------------------------------------------------------
            success = db_manager.save_field_inspection(save_date, round_idx, inspector)
            if success:
                QMessageBox.information(self, "저장 완료", f"오늘자({save_date}) {round_idx}차 현장 점검 기록이 완료되었습니다.")
                
                # 만약 메인 화면이 '오늘 날짜'를 보고 있었다면 표를 새로고침 해줍니다.
                current_view_date = self.qdate.date().toString("yyyy-MM-dd")
                if current_view_date == save_date:
                    self.load_data()
            else:
                QMessageBox.critical(self, "저장 실패", "데이터베이스 저장 중 에러가 발생했습니다.")