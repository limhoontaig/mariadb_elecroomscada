# ac_controller.py
import time
import random
import broadlink

# -----------------------------------------------------------------
# [1] 설정 영역
# -----------------------------------------------------------------
# 시뮬레이션 모드 켜기/끄기 (True로 설정하면 실제 허브로 신호를 쏘지 않고 로그만 출력합니다)
SIMULATION_MODE = False

HUB1_IP = '192.168.2.5'
HUB2_IP = '192.168.2.86'

# 학습된 에어컨 리모컨 Hex 코드
IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05"
IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

# -----------------------------------------------------------------
# [2] 상태 관리 전역 변수
# -----------------------------------------------------------------
ac_state = "STANDBY"
ac_start_time = 0
fan_control_cmd = 0 

# -----------------------------------------------------------------
# [3] Broadlink IR 제어 함수
# -----------------------------------------------------------------
def send_ir(ip_address, hex_code):
    if SIMULATION_MODE:
        print(f"   [시뮬레이션] 📡 {ip_address}로 IR 신호 전송 완료 (패스)")
        return

    try:
        device = broadlink.hello(ip_address)
        device.auth()
        # base64가 아닌 16진수 문자열이므로 bytes.fromhex를 사용해야 합니다.
        packet = bytes.fromhex(hex_code)
        device.send_data(packet)
        print(f"📡 [IR 발사 성공] 대상 IP: {ip_address}")
    except Exception as e:
        print(f"❌ [IR 발사 실패] 허브 연결 확인 요망 ({ip_address}): {e}")

# -----------------------------------------------------------------
# [4] 메인 제어 로직
# -----------------------------------------------------------------
def check_and_control(indoor_temp, outdoor_temp, dis_temp1, dis_temp2):
    global ac_state, ac_start_time, fan_control_cmd

    if indoor_temp is None or outdoor_temp is None: 
        return

    if ac_state == "STANDBY":
        if indoor_temp >= 32.0 or outdoor_temp >= 34.0:
            print(f"\n🚨 온도 상승 경고 (실내:{indoor_temp:.1f}℃). 에어컨 1, 2호기 가동 지시!")
            send_ir(HUB1_IP, IR_TURN_ON_29C)
            send_ir(HUB2_IP, IR_TURN_ON_29C)
            
            ac_state = "STARTING"
            ac_start_time = time.time()

    elif ac_state == "STARTING":
        if dis_temp1 <= 20.0 or dis_temp2 <= 20.0:
            print("\n❄️ 에어컨 찬바람 확인! 환기팬 제어 변수를 '정지(1)'로 업데이트합니다.")
            fan_control_cmd = 1 
            ac_state = "COOLING"
        
        # 시뮬레이션 빠른 진행을 위해 대기 시간을 300초에서 10초로 임시 축소
        elif time.time() - ac_start_time > 10:
            print("\n⚠️ [경고] 에어컨 가동 신호를 보냈으나 센서에서 찬바람이 감지되지 않습니다!")

    elif ac_state == "COOLING":
        if indoor_temp <= 29.0 or outdoor_temp <= 30.0:
            print(f"\n✅ 온도 안정화 (실내:{indoor_temp:.1f}℃). 에어컨 정지 지시!")
            send_ir(HUB1_IP, IR_TURN_OFF)
            send_ir(HUB2_IP, IR_TURN_OFF)
            
            print("🔄 환기팬 제어 변수를 '자동 운전(0)'으로 복구합니다.")
            fan_control_cmd = 0 
            ac_state = "STANDBY"

# -----------------------------------------------------------------
# [5] 시뮬레이션 구동 루프
# -----------------------------------------------------------------
def run_simulation():
    print("=== 🌡️ 에어컨 자동 제어 시뮬레이터 시작 ===")
    
    # 초기 시작 온도
    sim_indoor = 25.0
    sim_outdoor = 28.0
    sim_dis1 = 25.0
    sim_dis2 = 25.0

    step = 1
    while True:
        print(f"\n--- [시간 흐름: {step} 틱] ---")

        # 상태에 따른 온도 변화 로직
        if ac_state == "STANDBY":
            # 대기 중: 에어컨이 꺼져 있으므로 온도가 서서히 상승
            sim_indoor = min(35.0, sim_indoor + random.uniform(0.5, 1.5))
            sim_outdoor = min(38.0, sim_outdoor + random.uniform(0.2, 1.0))
            # 토출구 온도는 실내 온도와 비슷하게 맞춰짐
            sim_dis1 = sim_indoor
            sim_dis2 = sim_indoor
            
        else: 
            # STARTING 또는 COOLING 상태: 에어컨 가동 중
            # 토출구 온도가 급격히 떨어짐 (찬바람 나옴)
            sim_dis1 = max(15.0, sim_dis1 - random.uniform(2.0, 4.0))
            sim_dis2 = max(15.0, sim_dis2 - random.uniform(2.0, 4.0))

            if ac_state == "COOLING":
                # 본격적으로 냉방이 시작되면 실내 온도가 떨어짐
                sim_indoor = max(20.0, sim_indoor - random.uniform(0.8, 1.8))
                # 실외 온도는 자연적으로 조금씩 변동
                sim_outdoor = max(18.0, sim_outdoor - random.uniform(0.1, 0.5))

        # 현재 모니터링 상태 출력
        print(f"상태: [{ac_state}] | 팬명령: {fan_control_cmd}")
        print(f"온도: 실내 {sim_indoor:.1f}℃ | 실외 {sim_outdoor:.1f}℃ | 토출1 {sim_dis1:.1f}℃ | 토출2 {sim_dis2:.1f}℃")

        # 제어기 호출
        check_and_control(sim_indoor, sim_outdoor, sim_dis1, sim_dis2)

        step += 1
        time.sleep(2) # 2초마다 갱신 (빠른 시뮬레이션을 위해)

if __name__ == "__main__":
    run_simulation()