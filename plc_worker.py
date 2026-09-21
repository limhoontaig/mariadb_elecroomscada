import serial
import struct
import time
import configparser
import os
import random
import threading
import broadlink
from datetime import datetime, timedelta
from PyQt5.QtCore import QObject, pyqtSignal

from db_manager import DATA_LABELS, get_db_connection, get_db_raw_connection

config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_com_port():
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT', 'COM3')
    return 'COM3'

COM_PORT = get_com_port()
BAUD_RATE = 19200         
MY_SLAVE_ID = 5           
NUM_WORDS = 52 

# 전역 변수로 온도 기준값 선언
TEMP_START_1 = 28.0
TEMP_START_2 = 31.0
TEMP_STOP = 25.0
TEMP_COLD = 20.0
MAX_RUN_TIME = 3 * 3600  # 기본 3시간(초 단위)

ac_state = "STANDBY"
ac_start_time = 0
fan_control_cmd = 0
lead_ac = 1

def load_ac_settings():
    """config.ini에서 온도 및 교대 시간 설정값을 읽어옵니다."""
    global TEMP_START_1, TEMP_START_2, TEMP_STOP, TEMP_COLD, MAX_RUN_TIME
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        if 'AC_SETTINGS' in config:
            TEMP_START_1 = config['AC_SETTINGS'].getfloat('START_TEMP_1', 28.5)
            TEMP_START_2 = config['AC_SETTINGS'].getfloat('START_TEMP_2', 31.0)
            TEMP_STOP = config['AC_SETTINGS'].getfloat('STOP_TEMP', 27.5)
            TEMP_COLD = config['AC_SETTINGS'].getfloat('COLD_WIND_TEMP', 26.0)
            # 설정창에서 입력한 시간(Hour)을 초(Seconds) 단위로 변환하여 적용
            hours = config['AC_SETTINGS'].getfloat('MAX_RUN_HOURS', 3.0)
            MAX_RUN_TIME = hours * 3600

# 👇👇 [신규 추가] UI에서 버튼을 누르면 호출되는 수동 제어 함수 (load_ac_settings 함수 아래에 추가) 👇👇
def force_manual_control(action):
    global ac_state, lead_ac, fan_control_cmd, ac_start_time
    
    current_time = time.time()
    
    if action == "ON_1":
        print("\n[수동 제어] 1호기 강제 가동 및 환기팬 정지!")
        threading.Thread(target=send_ir_task, args=(HUB1_IP, IR_TURN_ON_29C)).start()
        lead_ac = 1
        fan_control_cmd = 1         # 💡 환기팬 즉시 정지 신호 전달
        ac_state = "COOLING_1"      # 💡 찬바람 대기(STARTING_1)를 생략하고 바로 냉방 모드 진입
        ac_start_time = current_time # 자동 교대 타이머 리셋
        
    elif action == "ON_2":
        print("\n[수동 제어] 2호기 강제 가동 및 환기팬 정지!")
        threading.Thread(target=send_ir_task, args=(HUB2_IP, IR_TURN_ON_29C)).start()
        lead_ac = 2
        fan_control_cmd = 1         # 💡 환기팬 즉시 정지 신호 전달
        ac_state = "COOLING_1"      # 💡 찬바람 대기 생략하고 바로 냉방 모드 진입
        ac_start_time = current_time
        
    elif action == "OFF_ALL":
        print("\n[수동 제어] 전호기 강제 정지 및 환기팬 자동 복귀!")
        threading.Thread(target=send_ir_task, args=(HUB1_IP, IR_TURN_OFF)).start()
        threading.Thread(target=send_ir_task, args=(HUB2_IP, IR_TURN_OFF)).start()
        fan_control_cmd = 0         # 💡 환기팬 자동 모드로 원복
        ac_state = "STANDBY"        # 시스템 대기 모드로 리셋

# 프로그램 시작 시 최초 1회 로드
load_ac_settings()

# 1. 시그널을 담을 전역 클래스 생성
class CommSignal(QObject):
    # bool 타입(True/False)을 전달하는 시그널 정의
    status_changed = pyqtSignal(bool)

# 다른 파일에서 접근할 수 있도록 인스턴스 생성
comm_signal = CommSignal()

# =================================================================
# ⚙️ [에어컨 제어 로직 설정 구역]
# =================================================================
SIMULATION_MODE = False  

HUB1_IP = '192.168.2.4' 
HUB2_IP = '192.168.2.5' 

IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05" 
IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

ac_state = "STANDBY"
ac_start_time = 0
fan_control_cmd = 0 # PLC가 읽어갈 환기팬 제어 명령 (0:자동, 1:정지)
lead_ac = 1  

def send_ir_task(ip_address, hex_code):
    """Modbus 통신 지연을 막기 위해 백그라운드 스레드에서 실행되는 IR 함수"""
    if SIMULATION_MODE:
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

# 💡 함수 괄호 안에 total_load 추가
def check_and_control(indoor_temp, outdoor_temp, dis_temp1, dis_temp2, total_load):
    global ac_state, ac_start_time, fan_control_cmd, lead_ac

    if indoor_temp is None: return

    lag_ac = 2 if lead_ac == 1 else 1
    hubs = {1: HUB1_IP, 2: HUB2_IP}
    dis_temps = {1: dis_temp1, 2: dis_temp2}
    
    current_time = time.time()

    # 💡 [핵심] 예측 제어 조건: 외기가 32도 이상이거나, 총부하가 1200kW 이상일 때 True
    is_heavy_load = (outdoor_temp >= 32.0) or (total_load >= 1200)

    if ac_state == "STANDBY":
        # 조건 1: 실내 온도가 기본 기동 온도(예: 29.5도)에 도달했거나
        # 조건 2: (예측 제어 조건 발동) AND (실내가 26.0도 이상으로 냉방이 필요한 상태일 때)
        if (indoor_temp >= TEMP_START_1) or (is_heavy_load and indoor_temp >= 27.0):
           
            # 터미널 창에 기동 사유를 명확히 출력해 줍니다.
            if indoor_temp >= TEMP_START_1:
                print(f"\n[일반 기동] 실내 온도 {indoor_temp:.1f}C 도달. 선행 {lead_ac}호기 가동!")
            else:
                print(f"\n[예측 기동 발동] 외기:{outdoor_temp:.1f}C, 부하:{total_load}kW (실내:{indoor_temp:.1f}C). 선행 {lead_ac}호기 가동!")
                
            threading.Thread(target=send_ir_task, args=(hubs[lead_ac], IR_TURN_ON_29C)).start()
            ac_state = "STARTING_1"
            ac_start_time = current_time

    elif ac_state == "STARTING_1":
        if dis_temps[lead_ac] <= TEMP_COLD:
            print(f"[{lead_ac}호기 찬바람 확인] 환기팬 정지.")
            fan_control_cmd = 1 
            ac_state = "COOLING_1"
        elif current_time - ac_start_time > 300: 
            print(f"[{lead_ac}호기 찬바람 미감지] 점검 요망!")

    elif ac_state == "COOLING_1":
        # 3시간(타이머 설정값) 이상 연속 가동 시 강제 교대
        if current_time - ac_start_time >= MAX_RUN_TIME:
            print(f"\n[강제 교대 발동] {lead_ac}호기 연속 가동 제한 도달. {lag_ac}호기로 교대합니다.")
            threading.Thread(target=send_ir_task, args=(hubs[lag_ac], IR_TURN_ON_29C)).start()
            time.sleep(2) 
            threading.Thread(target=send_ir_task, args=(hubs[lead_ac], IR_TURN_OFF)).start() 
            lead_ac = lag_ac
            ac_start_time = current_time 
            ac_state = "STARTING_1" 
            
        elif indoor_temp >= TEMP_START_2:
            print(f"\n[2단계 온도 상승] 실내 {indoor_temp:.1f}C. 후행 {lag_ac}호기 추가 가동!")
            threading.Thread(target=send_ir_task, args=(hubs[lag_ac], IR_TURN_ON_29C)).start()
            ac_state = "STARTING_2"
            ac_start_time = current_time
            
        elif (indoor_temp <= TEMP_STOP) or (not is_heavy_load):
            print(f"\n[온도 안정화] 실내 {indoor_temp:.1f}C. {lead_ac}호기 정지 및 순번 교대!")
            threading.Thread(target=send_ir_task, args=(hubs[lead_ac], IR_TURN_OFF)).start()
            lead_ac = lag_ac  
            fan_control_cmd = 0 
            ac_state = "STANDBY"

    elif ac_state == "STARTING_2":
        if dis_temps[lag_ac] <= TEMP_COLD:
            print(f"[{lag_ac}호기 찬바람 확인] 2대 동시 냉방 돌입.")
            ac_state = "COOLING_2"
        elif current_time - ac_start_time > 300:
            print(f"[{lag_ac}호기 찬바람 미감지] 점검 요망!")

    elif ac_state == "COOLING_2":
        if (indoor_temp <= TEMP_STOP) or (not is_heavy_load):
            print(f"\n[전체 온도 안정화] 실내 {indoor_temp:.1f}C. 전호기 정지 및 순번 교대!")
            threading.Thread(target=send_ir_task, args=(HUB1_IP, IR_TURN_OFF)).start()
            threading.Thread(target=send_ir_task, args=(HUB2_IP, IR_TURN_OFF)).start()
            lead_ac = lag_ac  
            fan_control_cmd = 0 
            ac_state = "STANDBY"

# =================================================================
# 🔄 [시리얼 통신 및 데이터 처리]
# =================================================================
def serial_receive_thread():
    time.sleep(1) 
    current_status = None
    last_success_time = time.time()
    last_emit_time = time.time() 
    ser = None
    buffer = b""

    while True:
        try:
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(port=COM_PORT, baudrate=BAUD_RATE, timeout=0.1)
                    print(f"통신 엔진 가동 완료: {COM_PORT} @ {BAUD_RATE}")
                    buffer = b"" 
                    last_success_time = time.time() 
                except Exception as e:
                    now = time.time()
                    if current_status != False or (now - last_emit_time > 3.0):
                        try: comm_signal.status_changed.emit(False)
                        except RuntimeError: pass
                        current_status = False; last_emit_time = now
                    time.sleep(2)
                    continue 

            if time.time() - last_success_time > 5.0:
                now = time.time()
                if current_status != False or (now - last_emit_time > 3.0):  
                    try: comm_signal.status_changed.emit(False)
                    except RuntimeError: pass
                    current_status = False; last_emit_time = now

            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                
                while len(buffer) >= 7:
                    if buffer[0] != MY_SLAVE_ID:
                        buffer = buffer[1:]
                        continue
                    
                    func_code = buffer[1]
                    
                    # 📥 [PLC -> PC: 데이터 저장 및 제어 로직 실행]
                    if func_code == 0x10:
                        expected_len = 7 + (NUM_WORDS * 2) + 2 
                        if len(buffer) < expected_len: break 
                        
                        packet = buffer[:expected_len]
                        if verify_crc(packet):
                            raw_values = packet[7:7+(NUM_WORDS * 2)]
                            raw_words = struct.unpack(f'>{NUM_WORDS}h', raw_values)
                            
                            word_1 = raw_words[15]   
                            word_2 = raw_words[16]   
                            u_word1 = word_1 if word_1 >= 0 else word_1 + 65536
                            u_word2 = word_2 if word_2 >= 0 else word_2 + 65536
                            dint_mwh = (u_word2 << 16) + u_word1
                            if dint_mwh & 0x80000000: dint_mwh -= 0x100000000
                                
                            values = (list(raw_words[:15]) + [dint_mwh] + list(raw_words[17:]))
                            
                            # 1. DB에 저장
                            insert_raw_data(values)
                            
                            # 2. 에어컨 온도 로직 판단
                            indoor_temp = values[0] / 10.0
                            outdoor_temp = values[1] / 10.0
                            ac1_temp = values[49] / 10.0
                            ac2_temp = values[50] / 10.0
                            total_load = values[14]
                            check_and_control(indoor_temp, outdoor_temp, ac1_temp, ac2_temp, total_load)
                            
                            buffer = buffer[expected_len:] 
                            now = time.time()
                            if current_status != True or (now - last_emit_time > 3.0):
                                try: comm_signal.status_changed.emit(True)
                                except RuntimeError: pass
                                current_status = True; last_emit_time = now
                            last_success_time = time.time()
                        else:
                            buffer = buffer[1:]

                    # [PC -> PLC: 환기팬 제어 상태값 전달]
                    elif func_code in (0x03, 0x04): 
                        expected_len = 8 
                        if len(buffer) < expected_len: break
                        
                        packet = buffer[:expected_len]
                        if verify_crc(packet):
                            start_addr = struct.unpack('>H', packet[2:4])[0]
                            num_words = struct.unpack('>H', packet[4:6])[0]
                            
                            reply_data = []
                            HEARTBEAT_ADDR = 0 
                            FAN_CMD_ADDR = 1  #  PLC가 환기팬 명령을 읽어갈 주소 (1번 번지)
                            
                            for i in range(num_words):
                                current_addr = start_addr + i
                                if current_addr == HEARTBEAT_ADDR:
                                    reply_data.append(1)
                                elif current_addr == FAN_CMD_ADDR:
                                    reply_data.append(fan_control_cmd) # 에어컨 로직 결과(0 또는 1) 전송
                                else:
                                    reply_data.append(0)
                            
                            byte_count = num_words * 2
                            reply_header = struct.pack('>BBB', MY_SLAVE_ID, func_code, byte_count)
                            reply_body = struct.pack(f'>{num_words}H', *reply_data)
                            
                            reply_without_crc = reply_header + reply_body
                            crc_bytes = calculate_crc(reply_without_crc)
                            final_reply = reply_without_crc + crc_bytes
                            
                            time.sleep(0.01) 
                            ser.write(final_reply)
                            buffer = buffer[expected_len:]

                            now = time.time()
                            if current_status != True or (now - last_emit_time > 3.0):
                                try: comm_signal.status_changed.emit(True)
                                except RuntimeError: pass
                                current_status = True; last_emit_time = now
                            last_success_time = time.time()
                        else:
                            buffer = buffer[1:]
                    else:
                        buffer = buffer[1:]

            time.sleep(0.01)
            
        except Exception as e:
            print(f"시리얼 수신 스레드 예외 발생: {e}")
            if ser:
                ser.close(); ser = None
            now = time.time()
            if current_status != False or (now - last_emit_time > 3.0):
                try: comm_signal.status_changed.emit(False)
                except RuntimeError: pass
                current_status = False; last_emit_time = now
            time.sleep(1)

def insert_raw_data(values):
    if len(values) < len(DATA_LABELS): return
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        now = datetime.now()
        l_date, l_time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
        
        DIV_BY_10 = {"실내온도", "외기온도", "SF운전시간", "EF운전시간", "Tr1_Temp", "Tr2_Temp", "Tr3_Temp", "에어콘01온도", "에어콘02온도"}
        DIV_BY_100 = {"KEP_A_R", "KEP_A_S", "KEP_A_T", "KEP_frequency", "KEP_V_R", "KEP_V_S", "KEP_V_T", "KEP_V_R_S", "KEP_V_S_T", "KEP_V_T_R", "KEP_P_mWh"}
        
        adjusted_values = []
        for label, val in zip(DATA_LABELS, values):
            if label in DIV_BY_10: adjusted_values.append(val / 10.0)
            elif label in DIV_BY_100: adjusted_values.append(val / 100.0)
            else: adjusted_values.append(float(val))

        placeholders = ", ".join(["%s"] * len(adjusted_values))
        col_names = ", ".join([f"`{name}`" for name in DATA_LABELS])
        
        query = f"INSERT INTO raw_data (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})"
        c.execute(query, [l_date, l_time] + adjusted_values)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB 저장 오류: {e}")

def verify_crc(data):
    if len(data) < 4: return False
    body = data[:-2]
    recv_crc = data[-2:]
    calc_crc = calculate_crc(body)
    return recv_crc == calc_crc or recv_crc == calc_crc[::-1]

def calculate_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return struct.pack('<H', crc)