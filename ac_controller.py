# ac_controller.py
import time
import threading
import broadlink
import configparser
import os
from PyQt5.QtCore import QObject, pyqtSignal

# 💡 [신규 추가] 백그라운드에서 메인 UI 화면으로 팝업창 신호를 안전하게 전달하는 통신병 역할
class ACSignals(QObject):
    alert_msg = pyqtSignal(str)

class ACController:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config = configparser.ConfigParser()
        self.signals = ACSignals() # 💡 매니저에 신호기 장착
        
        # ⚙️ 설정 기본값
        self.TEMP_START_1 = 28.5
        self.TEMP_START_2 = 31.0
        self.TEMP_STOP = 27.5
        self.TEMP_COLD = 26.0
        self.MAX_RUN_TIME = 3 * 3600  
        
        self.SIMULATION_MODE = False
        self.HUB1_IP = '192.168.2.4' 
        self.HUB2_IP = '192.168.2.5' 
        self.IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05" 
        self.IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

        self.ac_state = "STANDBY"
        self.ac_start_time = 0
        self.fan_control_cmd = 0 
        self.lead_ac = 1  
        
        self.load_settings()

    def load_settings(self):
        """💡 [크래시 방지] 설정 파일이 잘못되어도 튕기지 않고 기본값으로 끈질기게 버티도록 수정"""
        if os.path.exists(self.config_path):
            try:
                # utf-8-sig로 읽어 메모장의 숨겨진 인코딩(BOM) 에러를 방지
                self.config.read(self.config_path, encoding='utf-8-sig')
                if 'AC_SETTINGS' in self.config:
                    self.TEMP_START_1 = self.config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5)
                    self.TEMP_START_2 = self.config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0)
                    self.TEMP_STOP = self.config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5)
                    self.TEMP_COLD = self.config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0)
                    self.MAX_RUN_TIME = self.config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0) * 3600
            except Exception as e:
                print(f"[경고] config.ini 파일 형식 오류(오타 등)로 기본 온도를 적용합니다: {e}")

    def send_ir_task(self, ip_address, hex_code):
        if self.SIMULATION_MODE: return
        try:
            device = broadlink.hello(ip_address)
            device.auth()
            packet = bytes.fromhex(hex_code)
            device.send_data(packet)
        except Exception as e:
            print(f"[IR 발사 실패] ({ip_address}): {e}")

    def force_manual_control(self, action):
        current_time = time.time()
        if action == "ON_1":
            threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_ON_29C)).start()
            self.lead_ac = 1
            self.fan_control_cmd = 1          
            self.ac_state = "COOLING_1"       
            self.ac_start_time = current_time 
        elif action == "ON_2":
            threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_ON_29C)).start()
            self.lead_ac = 2
            self.fan_control_cmd = 1         
            self.ac_state = "COOLING_1"      
            self.ac_start_time = current_time
        elif action == "OFF_ALL":
            threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_OFF)).start()
            threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_OFF)).start()
            self.fan_control_cmd = 0         
            self.ac_state = "STANDBY"        

    def check_and_control(self, indoor_temp, outdoor_temp, dis_temp1, dis_temp2, total_load):
        if indoor_temp is None: return

        lag_ac = 2 if self.lead_ac == 1 else 1
        hubs = {1: self.HUB1_IP, 2: self.HUB2_IP}
        dis_temps = {1: dis_temp1, 2: dis_temp2}
        current_time = time.time()
        is_heavy_load = (outdoor_temp >= 32.0) or (total_load >= 1200)

        if self.ac_state == "STANDBY":
            if (indoor_temp >= self.TEMP_START_1) or (is_heavy_load and indoor_temp >= 27.0):
                # 💡 [메시지 작성 및 화면으로 전송]
                if indoor_temp >= self.TEMP_START_1:
                    msg = f"[일반 기동] 실내 온도 {indoor_temp:.1f}℃ 도달.\n선행 {self.lead_ac}호기 자동 가동을 시작합니다."
                else:
                    msg = f"[예측 기동 발동] 외기:{outdoor_temp:.1f}℃, 부하:{total_load}kW\n선제적으로 {self.lead_ac}호기 냉방을 시작합니다."
                print(msg)
                self.signals.alert_msg.emit(msg) # 👈 화면으로 팝업 띄우라는 신호 쏘기
                
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_1"
                self.ac_start_time = current_time

        elif self.ac_state == "STARTING_1":
            if dis_temps[self.lead_ac] <= self.TEMP_COLD:
                self.fan_control_cmd = 1 
                self.ac_state = "COOLING_1"
            elif current_time - self.ac_start_time > 300: 
                msg = f"[점검 요망] {self.lead_ac}호기 가동 5분 경과 후 찬바람 미감지.\n통신 및 전원 상태를 점검하세요."
                self.signals.alert_msg.emit(msg)
                print(msg)
                self.ac_start_time = current_time # 알람 폭탄 방지

        elif self.ac_state == "COOLING_1":
            if current_time - self.ac_start_time >= self.MAX_RUN_TIME:
                msg = f"[강제 교대 발동] {self.lead_ac}호기 연속 가동 제한 도달.\n{lag_ac}호기로 교대 운전을 시작합니다."
                self.signals.alert_msg.emit(msg)
                print(msg)

                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                time.sleep(2) 
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start() 
                self.lead_ac = lag_ac
                self.ac_start_time = current_time 
                self.ac_state = "STARTING_1" 
                
            elif indoor_temp >= self.TEMP_START_2:
                msg = f"[2단계 폭염 기동] 실내 온도 {indoor_temp:.1f}℃ 돌파.\n후행 {lag_ac}호기를 추가로 동시 가동합니다."
                self.signals.alert_msg.emit(msg)
                print(msg)
                
                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_2"
                self.ac_start_time = current_time
                
            elif (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                msg = f"[온도 안정화] 실내 온도 {indoor_temp:.1f}℃\n{self.lead_ac}호기 가동을 정지하고 대기 모드로 전환합니다."
                self.signals.alert_msg.emit(msg)
                print(msg)

                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start()
                self.lead_ac = lag_ac  
                self.fan_control_cmd = 0 
                self.ac_state = "STANDBY"

        elif self.ac_state == "STARTING_2":
            if dis_temps[lag_ac] <= self.TEMP_COLD:
                self.ac_state = "COOLING_2"
            elif current_time - self.ac_start_time > 300:
                msg = f"[점검 요망] 추가 가동한 {lag_ac}호기에서 찬바람 미감지."
                self.signals.alert_msg.emit(msg)
                print(msg)
                self.ac_start_time = current_time

        elif self.ac_state == "COOLING_2":
            if (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                msg = f"[전체 안정화] 실내 온도 {indoor_temp:.1f}℃\n가동 중인 모든 에어컨을 정지합니다."
                self.signals.alert_msg.emit(msg)
                print(msg)

                threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_OFF)).start()
                threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_OFF)).start()
                self.lead_ac = lag_ac  
                self.fan_control_cmd = 0 
                self.ac_state = "STANDBY"

ac_manager = ACController()