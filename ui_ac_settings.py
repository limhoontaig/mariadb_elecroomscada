# ui_ac_settings.py

import os
import configparser
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QLabel, QPushButton, QDoubleSpinBox, QMessageBox)
from ac_controller import ac_manager  # 💡 분리된 에어컨 매니저 호출

class ACSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 에어컨 자동/수동 제어 (관리자 전용)")
        self.setFixedSize(350, 420)
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config = configparser.ConfigParser()
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        group_auto = QGroupBox("자동 제어 및 교대 시간 설정")
        auto_layout = QVBoxLayout()
        
        self.spin_start1 = QDoubleSpinBox(); self.spin_start1.setRange(20.0, 35.0); self.spin_start1.setSingleStep(0.5)
        self.spin_start2 = QDoubleSpinBox(); self.spin_start2.setRange(20.0, 35.0); self.spin_start2.setSingleStep(0.5)
        self.spin_stop = QDoubleSpinBox(); self.spin_stop.setRange(15.0, 35.0); self.spin_stop.setSingleStep(0.5)
        self.spin_cold = QDoubleSpinBox(); self.spin_cold.setRange(10.0, 35.0); self.spin_cold.setSingleStep(0.5)
        self.spin_hours = QDoubleSpinBox(); self.spin_hours.setRange(1.0, 24.0); self.spin_hours.setSingleStep(1.0)

        self.add_row(auto_layout, "1단계 기동 온도 (℃):", self.spin_start1)
        self.add_row(auto_layout, "2단계 기동 온도 (℃):", self.spin_start2)
        self.add_row(auto_layout, "정지 (교대) 온도 (℃):", self.spin_stop)
        self.add_row(auto_layout, "찬바람 인식 온도 (℃):", self.spin_cold)
        self.add_row(auto_layout, "최대 연속 가동 교대 (시간):", self.spin_hours)
        
        btn_save = QPushButton("설정 저장 및 자동 로직 반영")
        btn_save.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 10px;")
        btn_save.clicked.connect(self.save_settings)
        auto_layout.addWidget(btn_save)
        group_auto.setLayout(auto_layout)
        layout.addWidget(group_auto)

        group_manual = QGroupBox("수동 원격 제어 (즉시 동작)")
        manual_layout = QHBoxLayout()
        
        btn_on_1 = QPushButton("1호기 켜기")
        btn_on_1.setStyleSheet("background-color: #3498db; color: white; padding: 8px;")
        btn_on_1.clicked.connect(lambda: self.trigger_manual("ON_1"))
        
        btn_on_2 = QPushButton("2호기 켜기")
        btn_on_2.setStyleSheet("background-color: #9b59b6; color: white; padding: 8px;")
        btn_on_2.clicked.connect(lambda: self.trigger_manual("ON_2"))
        
        btn_off_all = QPushButton("전체 끄기")
        btn_off_all.setStyleSheet("background-color: #e74c3c; color: white; padding: 8px; font-weight: bold;")
        btn_off_all.clicked.connect(lambda: self.trigger_manual("OFF_ALL"))
        
        manual_layout.addWidget(btn_on_1)
        manual_layout.addWidget(btn_on_2)
        manual_layout.addWidget(btn_off_all)
        group_manual.setLayout(manual_layout)
        layout.addWidget(group_manual)
        self.setLayout(layout)

    def add_row(self, layout, label_text, widget):
        row = QHBoxLayout()
        row.addWidget(QLabel(label_text))
        row.addWidget(widget)
        layout.addLayout(row)

    def load_settings(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'AC_SETTINGS' in self.config:
                self.spin_start1.setValue(self.config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5))
                self.spin_start2.setValue(self.config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0))
                self.spin_stop.setValue(self.config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5))
                self.spin_cold.setValue(self.config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0))
                self.spin_hours.setValue(self.config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0))

    def save_settings(self):
        if 'AC_SETTINGS' not in self.config:
            self.config['AC_SETTINGS'] = {}
        self.config['AC_SETTINGS']['START_TEMP_1'] = str(self.spin_start1.value())
        self.config['AC_SETTINGS']['START_TEMP_2'] = str(self.spin_start2.value())
        self.config['AC_SETTINGS']['STOP_TEMP'] = str(self.spin_stop.value())
        self.config['AC_SETTINGS']['COLD_WIND_TEMP'] = str(self.spin_cold.value())
        self.config['AC_SETTINGS']['MAX_RUN_HOURS'] = str(self.spin_hours.value())

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)
        
        ac_manager.load_settings()  # 💡 매니저 설정 즉시 리프레시
        QMessageBox.information(self, "저장 완료", "자동 설정값이 즉시 반영되었습니다.")

    def trigger_manual(self, action):
        ac_manager.force_manual_control(action)  # 💡 매니저의 제어 함수 즉시 호출
        action_names = {"ON_1": "1호기 켜기", "ON_2": "2호기 켜기", "OFF_ALL": "전체 에어컨 끄기"}
        QMessageBox.information(self, "수동 제어", f"[{action_names[action]}] 명령이 전송되었습니다.\n자동 타이머가 초기화됩니다.")