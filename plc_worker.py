# plc_worker.py
import serial
import struct
import time
from datetime import datetime
import db_manager 

COM_PORT = 'COM3'         
BAUD_RATE = 19200         
MY_SLAVE_ID = 5           
NUM_WORDS = 50            

def calculate_crc(data):
    """Modbus RTU 표준 패킷 검증용 CRC-16 연산 함수"""
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def parse_plc_payload(payload):
    """
    PLC로부터 수신한 100바이트 바이너리 페이로드를 
    50개의 정수형(Word) 데이터 배열로 파싱 및 10/100 배율 보정을 수행합니다.
    """
    # Big-Endian unsigned short(H) 50개 파싱
    fmt = '>' + 'H' * NUM_WORDS
    raw_words = struct.unpack(fmt, payload)
    
    # 하드웨어 사양에 따른 소수점 보정 필드 그룹화
    DIV_BY_10 = {"실내온도", "외기온도", "SF운전시간", "EF운전시간", "Tr1_Temp", "Tr2_Temp", "Tr3_Temp"}
    DIV_BY_100 = {"KEP_A_R", "KEP_A_S", "KEP_A_T", "KEP_frequency", "KEP_V_R", "KEP_V_S", "KEP_V_T", "KEP_V_R_S", "KEP_V_S_T", "KEP_V_T_R", "KEP_P_mWh"}
    
    adjusted_values = []
    for label, val in zip(db_manager.DATA_LABELS, raw_words):
        if label in DIV_BY_10: 
            adjusted_values.append(val / 10.0)
        elif label in DIV_BY_100: 
            adjusted_values.append(val / 100.0)
        else: 
            adjusted_values.append(float(val))
            
    return adjusted_values

def serial_receive_thread():
    """백그라운드에서 PLC 패킷을 실시간 수신하여 정제 및 저장을 요청하는 메인 루프 스레드"""
    try:
        ser = serial.Serial(port=COM_PORT, baudrate=BAUD_RATE, timeout=0.1)
        print(f"🔌 [통신 엔진] {COM_PORT} 포트가 성공적으로 개방되었습니다. (@{BAUD_RATE}bps)")
    except Exception as e:
        print(f"❌ [통신 엔진 에러] 시리얼 포트 개방 실패: {e}")
        return

    buffer = b""
    while True:
        try:
            if ser.in_waiting > 0:
                buffer += ser.read(ser.in_waiting)
                
                while len(buffer) >= 7:
                    # 국번 확인 코드 (Slave ID 매칭)
                    if buffer[0] != MY_SLAVE_ID:
                        buffer = buffer[1:]
                        continue
                    
                    # 펑션코드 확인 (Modbus Write Multiple Registers: 0x10)
                    func_code = buffer[1]
                    if func_code == 0x10:
                        expected_len = 7 + (NUM_WORDS * 2) + 2 
                        
                        if len(buffer) < expected_len: 
                            break # 데이터가 다 올 때까지 대기
                        
                        packet = buffer[:expected_len]
                        buffer = buffer[expected_len:]
                        
                        # CRC 패킷 검증 연산
                        received_crc = struct.unpack('<H', packet[-2:])[0]
                        calc_crc = calculate_crc(packet[:-2])
                        
                        if received_crc != calc_crc:
                            print(f"⚠️ [통신 경고] Modbus 패킷 CRC 에러 검출 -> 패킷 폐기")
                            continue
                        
                        # 데이터 페이로드 영역 추출
                        payload = packet[7:-2]
                        
                        # 데이터 정제 함수 호출
                        adjusted_data = parse_plc_payload(payload)
                        
                        # 현재 시간 생성
                        now = datetime.now()
                        log_date = now.strftime('%Y-%m-%d')
                        log_time = now.strftime('%H:%M:%S')
                        
                        # db_manager 창구에 안전하게 저장 위임
                        success = db_manager.save_plc_raw_data(log_date, log_time, adjusted_data)
                        if success:
                            print(f"💾 [통신 엔진] PLC 수집 데이터가 MariaDB에 정상 실시간 동기화되었습니다. ({log_time})")
                        else:
                            print(f"❌ [DB 경고] db_manager가 PLC 데이터를 수락하지 못했습니다.")
                            
                    else:
                        # 알 수 없는 펑션코드 처리 방어선
                        buffer = buffer[1:]
                        
            time.sleep(0.01) # 무한루프로 인한 CPU 과부하 방지 점검용 미세 휴식
            
        except Exception as loop_err:
            print(f"⚠️ [통신 엔진 백그라운드 에러] 루프 예외 발생: {loop_err}")
            time.sleep(1) # 에러 폭주 방지용 지연