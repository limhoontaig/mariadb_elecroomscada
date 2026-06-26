# ui_dialogs.py
import sqlite3
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QGroupBox, QFormLayout, QLineEdit, QGridLayout, QDialogButtonBox, QMessageBox, QComboBox
from PyQt5.QtCore import QDate, Qt

import db_manager # DB 조회를 위해 가져옴

class ManualMeterInputDialog(QDialog):
    """독립된 3개 계량장치의 11개 지침을 날짜별로 통합 입력/수정하는 팝업 창"""
    def __init__(self, default_date_str=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("독립 계량장치 일일 지침 수동 입력/수정")
        self.resize(500, 330) 

        # 다이얼로그 전체 폰트 설정 (기존 폰트에서 크기 +1, 볼드 처리)
        current_font = self.font()                   
        current_font.setPointSize(current_font.pointSize() + 1) 
        current_font.setBold(True)                   
        self.setFont(current_font)                   
        
        # 메인 레이아웃 생성
        main_layout = QVBoxLayout()
        # [변경] 다이얼로그 안쪽 상부 여백을 20 -> 10으로 줄여 붕 뜨는 느낌 제거
        main_layout.setContentsMargins(15, 10, 15, 15)

        # 1. 날짜 선택 영역 및 안내 문구 수직 배치 구조로 변경
        date_section_layout = QVBoxLayout()
        date_section_layout.setSpacing(8) # 상단 라인과 아래 안내 문구 사이의 간격
        
        # [첫 번째 줄] 레이블 + 캘린더 콤보박스 (가로 배치)
        date_top_layout = QHBoxLayout()
        date_top_layout.setSpacing(10)
        
        date_label = QLabel("<span style='color: #2c3e50;'><b>검침/기록 대상 일자:</b></span>")
        date_top_layout.addWidget(date_label)
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        
        # --- 날짜 로직 분기 ---
        if default_date_str:
            target_date = QDate.fromString(default_date_str, "yyyy-MM-dd")
        else:
            target_date = QDate.currentDate().addDays(-1)
            
        self.date_edit.setDate(target_date)
        
        # 너비 고정
        self.date_edit.setMinimumWidth(130)
        self.date_edit.setMaximumWidth(150)
        self.date_edit.dateChanged.connect(self.load_date_data)
        date_top_layout.addWidget(self.date_edit)
        
        # 첫 줄 위젯들을 왼쪽으로 밀착
        date_top_layout.addStretch(1)
        date_section_layout.addLayout(date_top_layout)
        
        # [두 번째 줄] 근무자 안내 문구 (기존 10pt -> 14pt로 4포인트 크기 상향 및 진하게)
        notice_label = QLabel(
            "<span style='color: #e74c3c; font-size: 14pt; font-weight: bold;'>"
            "* 전날 전력량 입력을 위해 기본 '어제 날짜'로 지정되었습니다."
            "</span>"
        )
        date_section_layout.addWidget(notice_label)
        
        # 메인 레이아웃에 날짜 세션 전체 추가
        main_layout.addLayout(date_section_layout)
        
        # 그리드(계량기 양식)와의 사이 간격 조정
        main_layout.addSpacing(15)
        '''
        # 1. 날짜 선택 영역 (1라인 가로 배치 및 왼쪽 정렬 밀착)
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10) # 위젯 간의 가로 간격을 촘촘하게 10px로 제한
        
        # 날짜 레이블 색상 변경 (안정적인 톤)
        date_label = QLabel("<span style='color: #2c3e50;'><b>검침/기록 대상 일자:</b></span>")
        date_layout.addWidget(date_label)
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True) # 캘린더 팝업 허용 (언제든 변경 가능)
        
        # --- 날짜 로직 변경 분기 ---
        if default_date_str:
            # 부모 창에서 특정 날짜를 강제로 지정해 준 경우
            target_date = QDate.fromString(default_date_str, "yyyy-MM-dd")
        else:
            # 기본값: 오늘 기준 전날(-1일) 세팅
            target_date = QDate.currentDate().addDays(-1)
            
        self.date_edit.setDate(target_date)
        
        # [변경] 날짜 입력창이 뚱뚱해지지 않도록 너비를 딱 알맞게 고정
        self.date_edit.setMinimumWidth(130)
        self.date_edit.setMaximumWidth(150)
        
        # 날짜 변경 시 데이터를 새로 로드하는 이벤트 연결
        self.date_edit.dateChanged.connect(self.load_date_data)
        date_layout.addWidget(self.date_edit)
        
        # 근무자 혼돈 방지를 위한 안내 문구 (날짜창 바로 옆에 위치)
        notice_label = QLabel("<span style='color: #e74c3c; font-size: 10pt;'>* 전날 전력량 입력을 위해 기본 '어제 날짜'로 지정되었습니다.</span>")
        date_layout.addWidget(notice_label)
        
        # [핵심] 가로 레이아웃 우측에 스트레치를 넣어 모든 위젯을 왼쪽으로 콤팩트하게 밀착시킴
        date_layout.addStretch(1)
        
        
        # 메인 레이아웃에 날짜 라인 추가
        main_layout.addLayout(date_layout)
        # 날짜 라인과 하부 그리드(계량기 양식) 사이의 수직 간격을 촘촘하게 제어
        main_layout.addSpacing(5)
        '''
        # 전체 그룹을 2x2로 배치할 메인 그리드 레이아웃
        grid_layout = QGridLayout()
        self.inputs = {}
        
        # --- [0, 0] 메인 계량기 그룹 ---
        main_group = QGroupBox("메인 계량장치")
        main_form = QFormLayout()
        main_fields = [
            ('main_active', '메인 유효 (kWh)'),
            ('main_reactive', '메인 무효 (kVarh)')
        ]
        for field, label in main_fields:
            edit = QLineEdit()
            main_form.addRow(label, edit)
            self.inputs[field] = edit
        main_group.setLayout(main_form)
        grid_layout.addWidget(main_group, 0, 0)
        
        # --- [0, 1] 산업용 그룹 ---
        ind_group = QGroupBox("산업용 전력")
        ind_form = QFormLayout()
        ind_fields = [
            ('ind_mid', '중간부하'),
            ('ind_max', '최대부하'),
            ('ind_light', '경부하')
        ]
        for field, label in ind_fields:
            edit = QLineEdit()
            ind_form.addRow(label, edit)
            self.inputs[field] = edit
        ind_group.setLayout(ind_form)
        grid_layout.addWidget(ind_group, 0, 1)
        
        # --- [1, 0] 가로등 그룹 ---
        street_group = QGroupBox("가로등 전력")
        street_form = QFormLayout()
        street_fields = [
            ('street_mid', '중간부하'),
            ('street_max', '최대부하'),
            ('street_light', '경부하')
        ]
        for field, label in street_fields:
            edit = QLineEdit()
            street_form.addRow(label, edit)
            self.inputs[field] = edit
        street_group.setLayout(street_form)
        grid_layout.addWidget(street_group, 1, 0)
        
        # --- [1, 1] 지열 그룹 ---
        geo_group = QGroupBox("지열 시스템")
        geo_form = QFormLayout()
        geo_fields = [
            ('geo_1', '지열 1호기'),
            ('geo_2', '지열 2호기'),
            ('geo_3', '지열 3호기')
        ]
        for field, label in geo_fields:
            edit = QLineEdit()
            geo_form.addRow(label, edit)
            self.inputs[field] = edit
        geo_group.setLayout(geo_form)
        grid_layout.addWidget(geo_group, 1, 1)
        
        # 메인 레이아웃에 그리드 추가
        main_layout.addLayout(grid_layout)
        
        # 3. 저장 및 취소 버튼 영역
        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(QDialogButtonBox.Save)
        self.cancel_button = buttons.addButton(QDialogButtonBox.Cancel)
        
        self.save_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)
        
        main_layout.addWidget(buttons)
        self.setLayout(main_layout)
        
        # 최초 실행 시 데이터 로드
        self.load_date_data()

    def load_date_data(self):
        """날짜가 변경될 때마다 DB를 뒤져 해당 일자의 기존 수치를 양식에 표기합니다."""
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        current_data = db_manager.get_manual_meter_data(date_str)
        
        for field, value in current_data.items():
            if field in self.inputs: 
                self.inputs[field].setText(value)
            
    def validate_and_accept(self):
        """입력된 값들이 정상적인 숫자 포맷인지 최종 무결성 검사를 수행합니다."""
        for field, edit in self.inputs.items():
            text = edit.text().strip()
            if text:
                try:
                    float(text)
                except ValueError:
                    QMessageBox.warning(self, "포맷 오류", "지침 입력 값은 순수 숫자(또는 소수점)만 입력 가능합니다.")
                    edit.setFocus()
                    return  
                    
        self.accept()

    def close_dialog(self):
        self.done(QDialog.Rejected) 

    def get_final_inputs(self):
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        data_dict = {field: edit.text().strip() for field, edit in self.inputs.items()}
        return date_str, data_dict

class FieldInspectionDialog(QDialog):
    """현장 점검 근무자 입력 및 차수 선택 팝업 창"""
    def __init__(self, default_date_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("현장 일일 점검 기록 입력")
        self.resize(400, 250)

        current_font = self.font()
        current_font.setPointSize(current_font.pointSize() + 1)
        current_font.setBold(True)
        self.setFont(current_font)

        layout = QVBoxLayout(self)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("점검 일자:"))
        self.date_edit = QDateEdit(QDate.fromString(default_date_str, "yyyy-MM-dd"))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setEnabled(False)  
        date_layout.addWidget(self.date_edit)
        layout.addLayout(date_layout)

        round_layout = QHBoxLayout()
        round_layout.addWidget(QLabel("점검 차수:"))
        self.combo_round = QComboBox()
        self.combo_round.addItems(["오전 점검", "오후 점검", "야간 점검"])
        round_layout.addWidget(self.combo_round)
        layout.addLayout(round_layout)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("점검자 성명:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("성명을 입력하세요")
        name_layout.addWidget(self.input_name)
        layout.addLayout(name_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_and_accept(self):
        if not self.input_name.text().strip():
            QMessageBox.warning(self, "입력 오류", "점검자 성명을 정확히 입력해 주세요.")
            self.input_name.setFocus()
            return
        self.accept()