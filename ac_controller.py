import time
import random
import broadlink

# -----------------------------------------------------------------
# [1] 설정 영역
# -----------------------------------------------------------------
SIMULATION_MODE = True  # 로직 테스트를 위해 임시로 True로 둡니다.

HUB1_IP = '192.168.2.5' #[cite: 2]
HUB2_IP = '192.168.2.4' #[cite: 2]

# 학습된 에어컨 리모컨 Hex 코드[cite: 2]
IR_TURN_ON_29C  = "260040006200013c103211120f120f120f330f120f120f120f120f120f111011101110111011101110321033103210111011103210321011101110321011101110000d05" 
IR_TURN_OFF = "260040006300013c0f330f130f120f120f330f120f120f120f3210330f120f120f1210111011101110111011101110110f120f330f120f330f120f130e130e340f000d05"

# -----------------------------------------------------------------
# [2] 상태 관리 전역 변수
# -----------------------------------------------------------------
ac_state = "STANDBY"
ac_start_time = 0
fan_control_cmd = 0 
lead_ac = 1  # 선행 가동할 에어컨 순번 (1 또는 2)

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
        packet = bytes.fromhex(hex_code)
        device.send_data(packet)
        print(f"📡 [IR 발사 성공] 대상 IP: {ip_address}")
    except Exception as e:
        print(f"❌ [IR 발사 실패] 허브 연결 확인 요망 ({ip_address}): {e}")

# -----------------------------------------------------------------
# [4] 메인 제어 로직 (교차 기동 적용)
# -----------------------------------------------------------------
def check_and_control(indoor_temp, outdoor_temp, dis_temp1, dis_temp2):
    global ac_state, ac_start_time, fan_control_cmd, lead_ac

    if indoor_temp is None: 
        return

    # 선행(Lead) 및 후행(Lag) 에어컨 매핑
    lag_ac = 2 if lead_ac == 1 else 1
    hubs = {1: HUB1_IP, 2: HUB2_IP}
    dis_temps = {1: dis_temp1, 2: dis_temp2}

    # 🟢 [상태 1: 대기 상태]
    if ac_state == "STANDBY":
        if indoor_temp >= 28.0:
            print(f"\n🚨 [1단계 온도 상승] 실내 {indoor_temp:.1f}℃. 선행 {lead_ac}호기 가동 지시!")
            send_ir(hubs[lead_ac], IR_TURN_ON_29C)
            ac_state = "STARTING_1"
            ac_start_time = time.time()

    # 🟡 [상태 2: 1대 가동 확인]
    elif ac_state == "STARTING_1":
        if dis_temps[lead_ac] <= 20.0:
            print(f"❄️ {lead_ac}호기 찬바람 확인! 환기팬 정지.")
            fan_control_cmd = 1 
            ac_state = "COOLING_1"
        elif time.time() - ac_start_time > 10: # 시뮬레이션 빠른 진행 위해 10초
            print(f"⚠️ {lead_ac}호기 찬바람 미감지!")

    # 🔵 [상태 3: 1대 냉방 중] -> 2단계 온도 감시 또는 정지
    elif ac_state == "COOLING_1":
        if indoor_temp >= 31.0:
            print(f"\n🚨🚨 [2단계 온도 상승] 실내 {indoor_temp:.1f}℃. 추가 냉방 필요! 후행 {lag_ac}호기 가동 지시!")
            send_ir(hubs[lag_ac], IR_TURN_ON_29C)
            ac_state = "STARTING_2"
            ac_start_time = time.time()
        elif indoor_temp <= 25.0:
            print(f"\n✅ 온도 안정화 (실내:{indoor_temp:.1f}℃). {lead_ac}호기 정지 및 순번 교대!")
            send_ir(hubs[lead_ac], IR_TURN_OFF)
            lead_ac = lag_ac  # 💡 여기서 다음번 가동 순서를 바꿉니다.
            fan_control_cmd = 0 
            ac_state = "STANDBY"

    # 🟠 [상태 4: 2대 동시 가동 확인]
    elif ac_state == "STARTING_2":
        if dis_temps[lag_ac] <= 20.0:
            print(f"❄️ {lag_ac}호기 찬바람 확인! 2대 동시 냉방 돌입.")
            ac_state = "COOLING_2"
        elif time.time() - ac_start_time > 10:
            print(f"⚠️ {lag_ac}호기 찬바람 미감지!")

    # 🟣 [상태 5: 2대 동시 냉방 중] -> 전체 정지
    elif ac_state == "COOLING_2":
        if indoor_temp <= 25.0:
            print(f"\n✅ 전체 온도 안정화 (실내:{indoor_temp:.1f}℃). 전호기 정지 및 순번 교대!")
            send_ir(HUB1_IP, IR_TURN_OFF)
            send_ir(HUB2_IP, IR_TURN_OFF)
            lead_ac = lag_ac  # 순서 교체
            fan_control_cmd = 0 
            ac_state = "STANDBY"

# -----------------------------------------------------------------
# [5] 시뮬레이션 구동 루프
# -----------------------------------------------------------------
def run_simulation():
    print("=== 🌡️ 에어컨 교번 제어 시뮬레이터 시작 ===")
    sim_indoor = 25.0
    sim_dis1 = 25.0
    sim_dis2 = 25.0

    step = 1
    while True:
        print(f"\n--- [{step} 틱] 선행순번: {lead_ac}호기 ---")

        if ac_state == "STANDBY":
            sim_indoor = min(35.0, sim_indoor + random.uniform(0.5, 1.5))
            sim_dis1 = sim_indoor
            sim_dis2 = sim_indoor
        elif ac_state in ["STARTING_1", "COOLING_1"]:
            if lead_ac == 1:
                sim_dis1 = max(15.0, sim_dis1 - random.uniform(2.0, 4.0))
            else:
                sim_dis2 = max(15.0, sim_dis2 - random.uniform(2.0, 4.0))
            if ac_state == "COOLING_1":
                sim_indoor = max(20.0, sim_indoor - random.uniform(0.3, 0.8)) # 1대 가동 시 천천히 하강
        else:
            sim_dis1 = max(15.0, sim_dis1 - random.uniform(2.0, 4.0))
            sim_dis2 = max(15.0, sim_dis2 - random.uniform(2.0, 4.0))
            if ac_state == "COOLING_2":
                sim_indoor = max(20.0, sim_indoor - random.uniform(1.0, 2.0)) # 2대 가동 시 빠르게 하강

        print(f"상태: [{ac_state}] | 팬명령: {fan_control_cmd}")
        print(f"온도: 실내 {sim_indoor:.1f}℃ | 토출1 {sim_dis1:.1f}℃ | 토출2 {sim_dis2:.1f}℃")

        check_and_control(sim_indoor, 0, sim_dis1, sim_dis2) # 실외 온도는 생략
        step += 1
        time.sleep(1.5)

if __name__ == "__main__":
    run_simulation()