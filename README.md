```
project/
│
├─ main.py              # 전체 실행 (카메라 + 라인추적 + YOLO + 상태머신 + 모터)
├─ motor.py             # 모터 제어 클래스
├─ rule_lane.py         # 노란 차선 검출 + 라인 기반 steering 제어
├─ yolo_worker.py       # YOLOv8을 별도 스레드로 실행해 실시간 인식
├─ state_manager.py     # 표지판 기반 상태머신 (좌/우/정지/직진/슬로우/부저 등)
├─ visualizer.py        # 화면 시각화 (라인, YOLO 박스, 텍스트)
├─ buzzer.py            # trumpet 표지판 → 부저 재생
├─ config.py            # YOLO/속도/정지시간 등 설정값
└─ mycamera.py          # PiCamera2 모듈 (기존 제공)
```
