# plc_worker.py
import serial
import struct
import time
import configparser
import os
from datetime import datetime, timedelta

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

def serial_receive_thread():
    try:
        ser = serial.Serial(port=COM_PORT, baudrate=BAUD_RATE, timeout=0.1)
        print(f"통신 엔진 가동 완료: {COM_PORT} @ {BAUD_RATE}")
    except Exception as e:
        print(f"시리얼 포트 개방 실패: {e}")
        return

    buffer = b""
    while True:
        try:
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
                            
                            # 50개 워드를 각각 안전하게 가져옵니다.
                            raw_words = struct.unpack(f'>{NUM_WORDS}h', raw_values)
                            
                            # KEP_P_mWh 가 위치한 D915, D916 자리 추출
                            word_1 = raw_words[15]   
                            word_2 = raw_words[16]   
                            
                            u_word1 = word_1 if word_1 >= 0 else word_1 + 65536
                            u_word2 = word_2 if word_2 >= 0 else word_2 + 65536
                            
                            # 💡 현장 계측기 값과 상하위 워드 순서 확인용 수식 (반전 필요시 아래 주석 체인지)
                            # dint_mwh = (u_word1 << 16) + u_word2
                            dint_mwh = (u_word2 << 16) + u_word1
                            
                            if dint_mwh & 0x80000000:
                                dint_mwh -= 0x100000000
                                
                            # 2개의 16비트 워드를 1개의 32비트 결합 데이터로 팩킹 후 리스트 재구성
                            values = (
                                list(raw_words[:15]) +    
                                [dint_mwh] +              
                                list(raw_words[17:])      
                            )
                            
                            insert_raw_data(values)
                            buffer = buffer[expected_len:] 
                        else:
                            buffer = buffer[1:]

                    elif func_code == 0x03:
                        expected_len = 8 
                        
                        if len(buffer) < expected_len:
                            break
                        
                        packet = buffer[:expected_len]
                        
                        if verify_crc(packet):
                            # 1. 요청 정보 추출
                            start_addr = struct.unpack('>H', packet[2:4])[0]
                            num_words = struct.unpack('>H', packet[4:6])[0]
                            
                            # 2. 응답 데이터 생성 (하트비트 로직 적용)
                            reply_data = []
                            HEARTBEAT_ADDR = 0 # PLC와 약속한 임의의 번지
                            
                            for i in range(num_words):
                                current_addr = start_addr + i
                                
                                if current_addr == HEARTBEAT_ADDR:
                                    # 요청한 주소가 하트비트 번지라면 1을 응답 (PC 살아있음!)
                                    reply_data.append(1)
                                else:
                                    # 그 외 주소는 기본값 0 (또는 다른 데이터) 응답
                                    reply_data.append(0)
                            
                            # 3. 응답 패킷 조립
                            byte_count = num_words * 2
                            reply_header = struct.pack('>BBB', MY_SLAVE_ID, 0x03, byte_count)
                            reply_body = struct.pack(f'>{num_words}H', *reply_data)
                            
                            reply_without_crc = reply_header + reply_body
                            crc_bytes = calculate_crc(reply_without_crc)
                            final_reply = reply_without_crc + crc_bytes
                            
                            # 4. 시리얼 포트로 송신 (안정성을 위한 미세 딜레이)
                            time.sleep(0.01) 
                            ser.write(final_reply)
                            
                            buffer = buffer[expected_len:]
                        else:
                            buffer = buffer[1:]
                    else:
                        buffer = buffer[1:]
                time.sleep(0.01)
        except Exception as e:
            print(f"시리얼 수신 스레드 예외 발생: {e}")
            break

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