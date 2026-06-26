# ui_dialogs.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QGroupBox, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox, QComboBox
from PyQt5.QtCore import QDate, Qt
import db_manager 

class ManualMeterInputDialog(QDialog):
    """독립된 계량장치의 지침을 입력/수정하는 데이터 팝업 창 (리모델링 Ver)"""
    def __init__(self, default_date_str=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("독립 계량장치 일일 지침 수동 입력/수정")
        self.resize(500, 400) 
        
        current_font = self.font()                   
        current_font.setPointSize(current_font.pointSize() + 1) 
        current_font.setBold(True)                   
        self.setFont(current_font)                   
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)

        # 상단 날짜 고정 영역
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("검침 기준 일자:"))
        self.date_edit = QDateEdit(QDate.fromString(default_date_str, "yyyy-MM-dd"))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setEnabled(False) # 메인화면 날짜와 오차 방지를 위해 잠금 
        date_layout.addWidget(self.date_edit)
        main_layout.addLayout(date_layout)

        # 입력 폼 그리드 배치
        group_box = QGroupBox("항목별 당일 지침 (KWH / ℃)")
        form_layout = QFormLayout(group_box)
        
        self.inputs = {}
        for field in db_manager.METER_FIELDS:
            self.inputs[field] = QLineEdit()
            self.inputs[field].setPlaceholderText("0.0")
            form_layout.addRow(QLabel(f"▶ {field}:"), self.inputs[field])
            
        main_layout.addWidget(group_box)

        # 확인 / 취소 버튼 구성
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttons.accepted.connect(self.save_data)
        self.buttons.rejected.connect(self.reject)
        main_layout.addWidget(self.buttons)
        
        # 💡 오픈 시점에 기존 데이터가 있다면 자동 로딩하여 편의성 극대화
        self.load_existing_data(default_date_str)

    def load_existing_data(self, target_date):
        """💡 리모델링 신규 기능: 기존에 등록해 둔 수동 지침이 있다면 칸에 자동으로 채워줍니다."""
        row = db_manager.get_manual_meter_by_date(target_date)
        if row:
            for field in db_manager.METER_FIELDS:
                if row.get(field) is not None:
                    self.inputs[field].setText(str(row[field]))

    def save_data(self):
        """[UI 기능] 입력된 텍스트 폼 데이터를 검증한 후 db_manager 창구에 저장을 요청합니다."""
        target_date = self.date_edit.date().toString("yyyy-MM-dd")
        data_dict = {}
        
        try:
            for field in db_manager.METER_FIELDS:
                text = self.inputs[field].text().strip()
                data_dict[field] = float(text) if text else 0.0
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "지침 칸에는 숫자(소수점)만 입력할 수 있습니다.")
            return

        # 💡 리모델링 핵심: 비즈니스 연산 저장을 db_manager 통합 창구에 위임
        if db_manager.save_manual_meter_logs(target_date, data_dict):
            QMessageBox.information(self, "저장 완료", f"[{target_date}] 수동 지침 기록이 성공적으로 반영되었습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "오류", "데이터베이스 저장 중 실패했습니다.")


class FieldInspectionDialog(QDialog):
    """현장 순찰 기록을 전담 등록하는 팝업 창 (리모델링 Ver)"""
    def __init__(self, default_date_str=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("현장 순찰 일지 등록")
        self.resize(400, 220)
        
        current_font = self.font()
        current_font.setPointSize(current_font.pointSize() + 1)
        current_font.setBold(True)
        self.setFont(current_font)

        layout = QVBoxLayout(self)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("점검 일자:"))
        self.date_edit = QDateEdit(QDate.fromString(default_date_str, "yyyy-MM-dd"))
        self.date_edit.setEnabled(False)  
        date_layout.addWidget(self.date_edit)
        layout.addLayout(date_layout)

        round_layout = QHBoxLayout()
        round_layout.addWidget(QLabel("점검 차수:"))
        self.combo_round = QComboBox()
        self.combo_round.addItems(["1차 오전점검", "2차 오후점검", "3차 야간점검"])
        round_layout.addWidget(self.combo_round)
        layout.addLayout(round_layout)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("점검자 성명:"))
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("성명을 입력하세요")
        name_layout.addWidget(self.input_name)
        layout.addLayout(name_layout)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        self.buttons.accepted.connect(self.validate_and_save)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def validate_and_save(self):
        """[UI 기능] 차수 중복 여부 및 기입 사항을 검증한 뒤 저장을 요청합니다."""
        save_date = self.date_edit.date().toString("yyyy-MM-dd")
        round_idx = self.combo_round.currentIndex() + 1 # 1, 2, 3차 인덱스 치환
        inspector = self.input_name.text().strip()

        if not inspector:
            QMessageBox.warning(self, "입력 누락", "점검자 성명을 공백 없이 입력해 주세요.")
            return

        # 💡 리모델링 핵심: db_manager API를 사용하여 중복 여부 확인 (SQL 제거)
        exists = db_manager.check_inspection_exists(save_date, round_idx)
        if exists:
            reply = QMessageBox.question(
                self, '기록 덮어쓰기 안내', 
                f"해당 날짜에 [{round_idx}차 점검] 기록이 이미 존재합니다.\n새로운 점검자 [{inspector}]로 덮어쓰시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No: return

        # 저장 위임
        if db_manager.save_field_inspection(save_date, round_idx, inspector):
            QMessageBox.information(self, "등록 완료", f"{save_date}부 {round_idx}차 현장 순찰 일지가 완수되었습니다.")
            self.accept()
        else:
            QMessageBox.critical(self, "오류", "순찰 일지 저장 중 문제가 발생했습니다.")