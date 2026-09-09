import broadlink
import time

print("네트워크에서 Broadlink 기기를 찾는 중...")
# 동일한 와이파이(로컬 네트워크)에 있는 기기를 자동으로 찾습니다.
devices = broadlink.discover(timeout=5)

if not devices:
    print("기기를 찾을 수 없습니다. PC와 기기가 같은 네트워크에 있는지 확인하세요.")
    exit()

# 첫 번째로 발견된 기기 선택 및 인증
device = devices[0]
device.auth()
print(f"기기 연결 성공! (IP: {device.host[0]})")

# RM4 시리즈의 경우 클라우드 락이 걸려있을 수 있으므로 로컬 접근을 시도합니다.
# (앱에서 '장치 잠금(Lock device)'이 해제되어 있어야 파이썬에서 제어 가능합니다.)

print("\n--- 신호 학습 모드 시작 ---")
print("이제 실제 에어컨 리모컨을 RM4c mini를 향해 누르세요. (10초 대기)")

# 학습 모드 진입
device.enter_learning()

# 신호가 들어올 때까지 대기 (최대 10초)
ir_packet = None
for i in range(10):
    time.sleep(1)
    try:
        ir_packet = device.check_data()
        if ir_packet:
            break
    except broadlink.exceptions.StorageError:
        # 아직 데이터가 들어오지 않은 상태
        pass
    print(f"신호 대기 중... ({10-i}초 남음)")

# 결과 출력
if ir_packet:
    print("\n✅ 신호 캡처 성공!")
    print("아래의 16진수(Hex) 데이터를 복사하여 저장해 두세요. 이 데이터가 에어컨을 켜는/끄는 고유 신호입니다.")
    print("-" * 50)
    print(ir_packet.hex())
    print("-" * 50)
else:
    print("\n❌ 시간 초과: 신호를 감지하지 못했습니다. 다시 시도해 주세요.")