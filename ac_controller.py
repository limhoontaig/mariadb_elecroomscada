# ac_controller.py
import time
import threading
import broadlink
import configparser
import os

class ACController:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.config = configparser.ConfigParser()
        
        # ⚙️ 설정 기본값
        self.TEMP_START_1 = 28.5
        self.TEMP_START_2 = 31.0
        self.TEMP_STOP = 27.5
        self.TEMP_COLD = 26.0
        self.MAX_RUN_TIME = 3 * 3600  
        
        # ⚙️ 기기 정보 및 상태 변수
        self.SIMULATION_MODE = False
        self.HUB1_IP = '192.168.2.5' 
        self.HUB2_IP = '192.168.2.4' 
        self.IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05" 
        self.IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

        self.ac_state = "STANDBY"
        self.ac_start_time = 0
        self.fan_control_cmd = 0 
        self.lead_ac = 1  
        
        self.load_settings()

    def load_settings(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding='utf-8')
            if 'AC_SETTINGS' in self.config:
                self.TEMP_START_1 = self.config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5)
                self.TEMP_START_2 = self.config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0)
                self.TEMP_STOP = self.config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5)
                self.TEMP_COLD = self.config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0)
                self.MAX_RUN_TIME = self.config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0) * 3600

    def send_ir_task(self, ip_address, hex_code):
        if self.SIMULATION_MODE:
            print(f"   [시뮬레이션] {ip_address}로 IR 신호 전송 완료")
            return
        try:
            device = broadlink.hello(ip_address)
            device.auth()
            packet = bytes.fromhex(hex_code)
            device.send_data(packet)
            print(f"[IR 발사 성공] 대상 IP: {ip_address}")
        except Exception as e:
            print(f"[IR 발사 실패] ({ip_address}): {e}")

    def force_manual_control(self, action):
        current_time = time.time()
        if action == "ON_1":
            print("\n[수동 제어] 1호기 강제 가동 및 환기팬 정지!")
            threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_ON_29C)).start()
            self.lead_ac = 1
            self.fan_control_cmd = 1          
            self.ac_state = "COOLING_1"       
            self.ac_start_time = current_time 
        elif action == "ON_2":
            print("\n[수동 제어] 2호기 강제 가동 및 환기팬 정지!")
            threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_ON_29C)).start()
            self.lead_ac = 2
            self.fan_control_cmd = 1         
            self.ac_state = "COOLING_1"      
            self.ac_start_time = current_time
        elif action == "OFF_ALL":
            print("\n[수동 제어] 전호기 강제 정지 및 환기팬 자동 복귀!")
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
                if indoor_temp >= self.TEMP_START_1:
                    print(f"\n[일반 기동] 실내 온도 {indoor_temp:.1f}C 도달. 선행 {self.lead_ac}호기 가동!")
                else:
                    print(f"\n[예측 기동 발동] 외기:{outdoor_temp:.1f}C, 부하:{total_load}kW (실내:{indoor_temp:.1f}C). 선행 {self.lead_ac}호기 가동!")
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_1"
                self.ac_start_time = current_time

        elif self.ac_state == "STARTING_1":
            if dis_temps[self.lead_ac] <= self.TEMP_COLD:
                print(f"[{self.lead_ac}호기 찬바람 확인] 환기팬 정지.")
                self.fan_control_cmd = 1 
                self.ac_state = "COOLING_1"
            elif current_time - self.ac_start_time > 300: 
                print(f"[{self.lead_ac}호기 찬바람 미감지] 점검 요망!")

        elif self.ac_state == "COOLING_1":
            if current_time - self.ac_start_time >= self.MAX_RUN_TIME:
                print(f"\n[강제 교대 발동] {self.lead_ac}호기 연속 가동 제한 도달. {lag_ac}호기로 교대합니다.")
                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                time.sleep(2) 
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start() 
                self.lead_ac = lag_ac
                self.ac_start_time = current_time 
                self.ac_state = "STARTING_1" 
            elif indoor_temp >= self.TEMP_START_2:
                print(f"\n[2단계 온도 상승] 실내 {indoor_temp:.1f}C. 후행 {lag_ac}호기 추가 가동!")
                threading.Thread(target=self.send_ir_task, args=(hubs[lag_ac], self.IR_TURN_ON_29C)).start()
                self.ac_state = "STARTING_2"
                self.ac_start_time = current_time
            elif (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                print(f"\n[온도 안정화 및 폭염 해제] 실내 {indoor_temp:.1f}C. {self.lead_ac}호기 정지 및 순번 교대!")
                threading.Thread(target=self.send_ir_task, args=(hubs[self.lead_ac], self.IR_TURN_OFF)).start()
                self.lead_ac = lag_ac  
                self.fan_control_cmd = 0 
                self.ac_state = "STANDBY"

        elif self.ac_state == "STARTING_2":
            if dis_temps[lag_ac] <= self.TEMP_COLD:
                print(f"[{lag_ac}호기 찬바람 확인] 2대 동시 냉방 돌입.")
                self.ac_state = "COOLING_2"
            elif current_time - self.ac_start_time > 300:
                print(f"[{lag_ac}호기 찬바람 미감지] 점검 요망!")

        elif self.ac_state == "COOLING_2":
            if (indoor_temp <= self.TEMP_STOP) and (not is_heavy_load):
                print(f"\n[전체 온도 안정화] 실내 {indoor_temp:.1f}C. 전호기 정지 및 순번 교대!")
                threading.Thread(target=self.send_ir_task, args=(self.HUB1_IP, self.IR_TURN_OFF)).start()
                threading.Thread(target=self.send_ir_task, args=(self.HUB2_IP, self.IR_TURN_OFF)).start()
                self.lead_ac = lag_ac  
                self.fan_control_cmd = 0 
                self.ac_state = "STANDBY"

# 프로그램 전체에서 하나만 공통으로 사용할 매니저 객체 생성
ac_manager = ACController()

if __name__ == "__main__":
    run_simulation()