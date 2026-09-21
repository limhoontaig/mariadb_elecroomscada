# plc_worker.py
import serial
import struct
import time
import configparser
import os
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from db_manager import DATA_LABELS, get_db_raw_connection
from ac_controller import ac_manager  # 💡 분리된 에어컨 매니저 호출

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

def get_com_port():
    config = configparser.ConfigParser()
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        return config['SETTINGS'].get('COM_PORT', 'COM3')
    return 'COM3'

COM_PORT = get_com_port()
BAUD_RATE = 19200         
MY_SLAVE_ID = 5           
NUM_WORDS = 52 

class CommSignal(QObject):
    status_changed = pyqtSignal(bool)

comm_signal = CommSignal()

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
                except Exception:
                    now = time.time()
                    if current_status != False or (now - last_emit_time > 3.0):
                        comm_signal.status_changed.emit(False)
                        current_status = False; last_emit_time = now
                    time.sleep(2)
                    continue 

            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                
                while len(buffer) >= 7:
                    if buffer[0] != MY_SLAVE_ID:
                        buffer = buffer[1:]
                        continue
                    
                    func_code = buffer[1]
                    
                    if func_code == 0x10:
                        expected_len = 7 + (NUM_WORDS * 2) + 2 
                        if len(buffer) < expected_len: break 
                        
                        packet = buffer[:expected_len]
                        if verify_crc(packet):
                            raw_values = packet[7:7+(NUM_WORDS * 2)]
                            raw_words = struct.unpack(f'>{NUM_WORDS}h', raw_values)
                            
                            word_1, word_2 = raw_words[15], raw_words[16]   
                            u_word1 = word_1 if word_1 >= 0 else word_1 + 65536
                            u_word2 = word_2 if word_2 >= 0 else word_2 + 65536
                            dint_mwh = (u_word2 << 16) + u_word1
                            if dint_mwh & 0x80000000: dint_mwh -= 0x100000000
                                
                            values = (list(raw_words[:15]) + [dint_mwh] + list(raw_words[17:]))
                            
                            insert_raw_data(values)
                            
                            # 💡 분리된 에어컨 매니저에게 데이터를 넘겨 판단 지시
                            ac_manager.check_and_control(
                                indoor_temp=values[0]/10.0, 
                                outdoor_temp=values[1]/10.0, 
                                dis_temp1=values[49]/10.0, 
                                dis_temp2=values[50]/10.0, 
                                total_load=values[14]
                            )
                            
                            buffer = buffer[expected_len:] 
                            now = time.time()
                            if current_status != True or (now - last_emit_time > 3.0):
                                comm_signal.status_changed.emit(True)
                                current_status = True; last_emit_time = now
                            last_success_time = time.time()
                        else:
                            buffer = buffer[1:]

                    elif func_code in (0x03, 0x04): 
                        expected_len = 8 
                        if len(buffer) < expected_len: break
                        
                        packet = buffer[:expected_len]
                        if verify_crc(packet):
                            start_addr = struct.unpack('>H', packet[2:4])[0]
                            num_words = struct.unpack('>H', packet[4:6])[0]
                            reply_data = []
                            
                            for i in range(num_words):
                                current_addr = start_addr + i
                                if current_addr == 0:
                                    reply_data.append(1)
                                elif current_addr == 1:
                                    reply_data.append(ac_manager.fan_control_cmd) # 💡 매니저의 상태값 전송
                                else:
                                    reply_data.append(0)
                            
                            byte_count = num_words * 2
                            reply_without_crc = struct.pack('>BBB', MY_SLAVE_ID, func_code, byte_count) + struct.pack(f'>{num_words}H', *reply_data)
                            ser.write(reply_without_crc + calculate_crc(reply_without_crc))
                            buffer = buffer[expected_len:]
                        else:
                            buffer = buffer[1:]
                    else:
                        buffer = buffer[1:]
            time.sleep(0.01)
            
        except Exception as e:
            if ser: ser.close(); ser = None
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
        
        adjusted_values = [val / 10.0 if label in DIV_BY_10 else (val / 100.0 if label in DIV_BY_100 else float(val)) for label, val in zip(DATA_LABELS, values)]
        placeholders = ", ".join(["%s"] * len(adjusted_values))
        col_names = ", ".join([f"`{name}`" for name in DATA_LABELS])
        
        c.execute(f"INSERT INTO raw_data (log_date, log_time, {col_names}) VALUES (%s, %s, {placeholders})", [l_date, l_time] + adjusted_values)
        conn.commit(); conn.close()
    except Exception as e:
        pass

def verify_crc(data):
    if len(data) < 4: return False
    calc_crc = calculate_crc(data[:-2])
    return data[-2:] == calc_crc or data[-2:] == calc_crc[::-1]

def calculate_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 0x0001 else crc >> 1
    return struct.pack('<H', crc)