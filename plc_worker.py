# plc_worker.py
import serial
import struct
import time
import configparser
import os
from datetime import datetime, timedelta
from PyQt5.QtCore import QObject, pyqtSignal

from db_manager import DATA_LABELS, get_db_connection, get_db_raw_connection  # 💡 db_manager에서는 경로와 라벨만 가져옴

config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_com_port():
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT', 'COM3')
    return 'COM3' # 기본값


COM_PORT = get_com_port()
BAUD_RATE = 19200         
MY_SLAVE_ID = 5           
NUM_WORDS = 50   

# 1. 시그널을 담을 전역 클래스 생성
class CommSignal(QObject):
    # bool 타입(True/False)을 전달하는 시그널 정의
    status_changed = pyqtSignal(bool)

# 다른 파일에서 접근할 수 있도록 인스턴스 생성
comm_signal = CommSignal()

def serial_receive_thread():
    time.sleep(1) # 화면이 켜질 시간을 잠시 벌어줍니다.
    
    current_status = None
    last_success_time = time.time()
    
    # ⭐ [핵심 추가] 혹시 메인 화면이 신호를 놓쳤을 경우를 대비한 '주기적 알림 타이머'
    last_emit_time = time.time() 
    
    ser = None
    buffer = b""

    while True:
        try:
            # 1. 포트 개방 시도 및 단절 처리
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(port=COM_PORT, baudrate=BAUD_RATE, timeout=0.1)
                    print(f"통신 엔진 가동 완료: {COM_PORT} @ {BAUD_RATE}")
                    buffer = b"" 
                    last_success_time = time.time() 
                except Exception as e:
                    now = time.time()
                    # ⭐ 상태가 바뀌었거나, 마지막으로 알려준 지 3초가 지났다면 다시 신호 발송!
                    if current_status != False or (now - last_emit_time > 3.0):
                        try:
                            comm_signal.status_changed.emit(False)
                        except RuntimeError:
                            pass
                        current_status = False
                        last_emit_time = now
                        
                    time.sleep(2)
                    continue 

            # 2. 5초 이상 아무런 데이터가 들어오지 않으면 (PLC 꺼짐 등)
            if time.time() - last_success_time > 5.0:
                now = time.time()
                # ⭐ 마찬가지로 3초마다 현재 단절 상태를 메인 화면에 갱신
                if current_status != False or (now - last_emit_time > 3.0):  
                    try:
                        comm_signal.status_changed.emit(False)
                    except RuntimeError:
                        pass
                    current_status = False
                    last_emit_time = now

            # 3. 데이터 정상 수신 처리
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                
                while len(buffer) >= 7:
                    if buffer[0] != MY_SLAVE_ID:
                        buffer = buffer[1:]
                        continue
                    
                    func_code = buffer[1]
                    if func_code == 0x10:
                        expected_len = 7 + (NUM_WORDS * 2) + 2 
                        
                        if len(buffer) < expected_len: 
                            break 
                        
                        packet = buffer[:expected_len]
                        
                        if verify_crc(packet):
                            raw_values = packet[7:7+(NUM_WORDS * 2)]
                            raw_words = struct.unpack(f'>{NUM_WORDS}h', raw_values)
                            
                            word_1 = raw_words[15]   
                            word_2 = raw_words[16]   
                            u_word1 = word_1 if word_1 >= 0 else word_1 + 65536
                            u_word2 = word_2 if word_2 >= 0 else word_2 + 65536
                            
                            dint_mwh = (u_word2 << 16) + u_word1
                            if dint_mwh & 0x80000000:
                                dint_mwh -= 0x100000000
                                
                            values = (
                                list(raw_words[:15]) +    
                                [dint_mwh] +              
                                list(raw_words[17:])      
                            )
                            
                            insert_raw_data(values)
                            buffer = buffer[expected_len:] 

                            # ⭐ 정상 수신 시 초록불 갱신 (3초 동기화 적용)
                            now = time.time()
                            if current_status != True or (now - last_emit_time > 3.0):
                                try:
                                    comm_signal.status_changed.emit(True)
                                except RuntimeError:
                                    pass
                                current_status = True
                                last_emit_time = now
                                
                            last_success_time = time.time()

                        else:
                            buffer = buffer[1:]

                    elif func_code in (0x03, 0x04): 
                        expected_len = 8 
                        if len(buffer) < expected_len:
                            break
                        
                        packet = buffer[:expected_len]
                        
                        if verify_crc(packet):
                            start_addr = struct.unpack('>H', packet[2:4])[0]
                            num_words = struct.unpack('>H', packet[4:6])[0]
                            
                            reply_data = []
                            HEARTBEAT_ADDR = 0 
                            
                            for i in range(num_words):
                                current_addr = start_addr + i
                                if current_addr == HEARTBEAT_ADDR:
                                    reply_data.append(1)
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

                            # ⭐ 정상 응답 시 초록불 갱신 (3초 동기화 적용)
                            now = time.time()
                            if current_status != True or (now - last_emit_time > 3.0):
                                try:
                                    comm_signal.status_changed.emit(True)
                                except RuntimeError:
                                    pass
                                current_status = True
                                last_emit_time = now
                                
                            last_success_time = time.time()

                        else:
                            buffer = buffer[1:]
                    else:
                        buffer = buffer[1:]

            time.sleep(0.01)
            
        except Exception as e:
            print(f"시리얼 수신 스레드 예외 발생: {e}")
            if ser:
                ser.close()
                ser = None
                
            # ⭐ 치명적 에러 시 빨간불 갱신 (3초 동기화 적용)
            now = time.time()
            if current_status != False or (now - last_emit_time > 3.0):
                try:
                    comm_signal.status_changed.emit(False)
                except RuntimeError:
                    pass
                current_status = False
                last_emit_time = now
            
            time.sleep(1)

def insert_raw_data(values):
    if len(values) < len(DATA_LABELS): return
    try:
        conn = get_db_raw_connection()
        c = conn.cursor()
        now = datetime.now()
        l_date, l_time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')
        
        DIV_BY_10 = {"실내온도", "외기온도", "SF운전시간", "EF운전시간", "Tr1_Temp", "Tr2_Temp", "Tr3_Temp"}
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