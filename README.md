```
project/
│
├─ main.py              # 전체 시스템 실행 (카메라 입력 → 차선 검출 → YOLO 이벤트 → 상태 머신 → 모터 제어)
├─ main_run.py          # 실제 주행 실행 스크립트 (전체 모듈 통합 실행)
│
├─ config.py            # 시스템 설정값 관리 (속도, YOLO 추론 주기, 정지 시간 등)
│
├─ motor.py             # GPIO 기반 모터 제어 모듈 (전진, 좌회전, 우회전, 정지)
├─ buzzer.py            # 부저 제어 모듈 (trumpet 표지판 인식 시 경적 재생)
│
├─ mycamera.py          # Raspberry Pi 카메라 입력 모듈
│
├─ rule_lane.py         # OpenCV 기반 노란 차선 검출 및 라인 추종 제어
├─ safe.py              # 주행 안전 보조 로직 (라인 분실 / 안전 정지 처리)
│
├─ yolo_worker.py       # YOLO 객체 인식 모듈 (별도 스레드 기반 실시간 추론)
├─ state_manager.py     # 객체 인식 결과 기반 상태 머신 관리
│                        (STOP / SLOW / LEFT / RIGHT / STRAIGHT / GREEN 등)
│
├─ visualizer.py        # 디버그 시각화 모듈
│                        (차선 위치, YOLO 검출 박스, 상태 텍스트 출력)
│
├─ README.md            # 프로젝트 설명 문서
│
└─ model/
    │
    ├─ best_strong4.pt  # 학습된 YOLO 모델 weight
    │
    ├─ EDA.ipynb        # 데이터 탐색 및 분석 노트북
    ├─ modeling.ipynb   # YOLO 학습 및 모델 실험 노트북
    └─ model_test.ipynb # 모델 성능 테스트 및 추론 확인
```
