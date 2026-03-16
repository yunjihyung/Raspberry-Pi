import mycamera
import cv2
import numpy as np
import time
from collections import deque, Counter
from gpiozero import DigitalOutputDevice, PWMOutputDevice, TonalBuzzer
from ultralytics import YOLO


# ==================================================
# MODE TIMING SETTINGS (초 단위)
# ==================================================
STOP_DURATION = 3.0
STOP_LOCK = 5.0

TRUMPET_DURATION = 3.0

STRAIGHT_DELAY = 1.0
STRAIGHT_DURATION = 4.0
STRAIGHT_LOCK = 0.0

# ============================
# SLOW 모드 설정
# ============================
SLOW_DURATION = 2.0
SLOW_LOCK = 6.0

# ============================
# GREEN 모드 설정
# ============================
GREEN_STOP_DURATION = 3.0
GREEN_LOCK = 6.0


# ==================================================
# Object Filter
# ==================================================
class ObjectFilter:
    def __init__(self, model_names, n=10, m=4, k=3, min_conf=0.5, min_size=90):
        self.history = deque(maxlen=n)
        self.m = m
        self.k = k
        self.min_conf = min_conf
        self.min_size = min_size
        self.model_names = model_names
            
    def push_and_decide(self, results, image):
        detected_cls = None
        max_conf = 0.0
        
        if results and len(results[0].boxes) > 0:
            best_box = None
            
            for box in results[0].boxes:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                width = abs(x2 - x1)

                if conf > self.min_conf and width >= self.min_size:
                    if conf > max_conf:
                        max_conf = conf
                        best_box = box
        
            if best_box:
                x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                detected_cls = self.model_names[int(best_box.cls[0])]
                print("detect", detected_cls, 'width', width, 'conf', max_conf)
                # OpenCV가 설치되어 있지 않으면 에러가 날 수 있으므로, 실제 환경에 맞게 조정 필요
                # cv2.rectangle(image, (x1,y1), (x2,y2), (0,255,255), 2)
                # cv2.putText(image, detected_cls, (x1, y1-5), 
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.7,(0,255,255),2)

        self.history.append(detected_cls)
        recent = list(self.history)[-self.m:]
        valid = [c for c in recent if c is not None]
        if not valid:
            return None

        best = Counter(valid).most_common(1)
        if best:
            cls, count = best[0]
            if count >= self.k:
                print("5 times sequential detect", cls)
                self.history.clear()
                return cls
            
        return None


# ==================================================
# Buzzer
# ==================================================
class Buzzer:
    def __init__(self, pin=12):
        try:
            # TonalBuzzer는 gpiozero 라이브러리에서 제공
            self.buzzer = TonalBuzzer(pin) 
            self.working = True
        except:
            self.buzzer = None
            self.working = False

    def beep(self, freq=261, duration=0.2):
        if self.working:
            try:
                self.buzzer.play(freq)
                time.sleep(duration)
            finally:
                self.buzzer.stop()
        else:
            print("(Virtual Beep)")


my_buzzer = Buzzer(pin=12)
def beep_horn(duration=0.2):
    my_buzzer.beep(261, duration)


# ==================================================
# Motor
# ==================================================
# PWMOutputDevice, DigitalOutputDevice는 gpiozero 라이브러리에서 제공
PWMA = PWMOutputDevice(18)
AIN1 = DigitalOutputDevice(22)
AIN2 = DigitalOutputDevice(27)

PWMB = PWMOutputDevice(23)
BIN1 = DigitalOutputDevice(25)
BIN2 = DigitalOutputDevice(24)


def motor_go(speed):
    AIN1.value = 0
    AIN2.value = 1
    PWMA.value = speed
    BIN1.value = 0
    BIN2.value = 1
    PWMB.value = speed


def motor_left(speed):
    AIN1.value = 0
    AIN2.value = 1
    PWMA.value = speed * 0.35
    BIN1.value = 0
    BIN2.value = 1
    PWMB.value = speed


def motor_right(speed):
    AIN1.value = 0
    AIN2.value = 1
    PWMA.value = speed
    BIN1.value = 0
    BIN2.value = 1
    PWMB.value = speed * 0.35


def motor_stop():
    PWMA.value = 0
    PWMB.value = 0
    AIN1.value = AIN2.value = 0
    BIN1.value = BIN2.value = 0


# ==================================================
# Vision (lane)
# ==================================================
def img_preprocess(image):
    h, _, _ = image.shape
    roi = image[h//2:, :, :]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower_yellow = np.array([15, 80, 80])
    upper_yellow = np.array([40, 255, 255])

    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask = cv2.GaussianBlur(mask, (5,5), 0)
    mask = cv2.erode(mask, None, iterations=1)
    mask = cv2.dilate(mask, None, iterations=2)
    return mask


# ==================================================
# Red Line Detect (finish line)
# ==================================================
def detect_red_line(image):
    h, w, _ = image.shape
    roi = image[int(h * 0.95):, :, :]  # 하단 5%만 감지

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 120, 70])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 120, 70])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 | mask2

    red_ratio = np.sum(mask > 0) / mask.size

    # ROI 영역에서 빨간색이 3% 이상일 때 True 반환
    return red_ratio > 0.03


# ==================================================
# find_line
# ==================================================
def find_line(mask, side="right"):
    h, w = mask.shape
    row0 = int(h * 0.9)
    roi = mask[row0:, :]

    if side == "right":
        roi = roi[:, w//2+30:]
        offset_x = w//2 + 30 
    else:
        roi = roi[:, :w//2-30]
        offset_x = 0

    contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 400:
        return None

    pts = c.reshape(-1,2)
    max_y = np.max(pts[:,1])
    xs_at_max_y = pts[pts[:,1] == max_y][:,0]

    if len(xs_at_max_y) == 0:
        return None

    edge_x = np.min(xs_at_max_y) if side == "right" else np.max(xs_at_max_y)
    cx = int(edge_x + offset_x)
    cy = int(h + (row0 + max_y))

    return cx, cy


# ==================================================
# Control Logic
# ==================================================
def control_logic(cx, width, follow_side, base_offset=130, dead_zone=20, speed=0.4):
    if cx is None:
        return "lost"

    offset = -base_offset if follow_side == "right" else base_offset
    target_cx = cx + offset
    error = target_cx - (width//2)

    if abs(error) < dead_zone:
        motor_go(speed)
        return "straight"

    if error > 0:
        motor_right(speed)
        return "right"

    motor_left(speed)
    return "left"


# ==================================================
# MAIN
# ==================================================
def main():
    print("Loading YOLO model...")
    model = YOLO("best_strong4.pt")
    # mycamera는 사용자 정의 라이브러리, 실제 환경에 맞게 수정 필요
    camera = mycamera.MyPiCamera(640, 480) 
    obj_filter = ObjectFilter(model_names=model.names)
    
    start_flag = False

    follow_side = "left"
    base_offset = 140
    run_speed = 0.5

    # safe driving
    lost_count = 0
    hold_frames = 1
    hard_lost_stop = 300
    search_speed = 0.5

    # ======================================================
    # Finish line logic — STATE MACHINE 방식 (수정된 부분)
    # ======================================================
    RED_LINE_MODE = True
    START_IGNORE_TIME = 3.0  # 출발 직후 오인식 방지용
    
    # 0: 첫 빨간선 대기중, 1: 첫 빨간선 밟고 지나가는 중, 2: 첫 빨간선 완전히 통과함
    red_state = 0   
    
    no_red_count = 0       
    NO_RED_THRESHOLD = 5   # 5프레임 연속으로 빨간색이 안 보여야 "선이 끝났다"고 인정

    # -----------------------------
    # LOCK VARIABLES 아래는 기본설정. 변경하지말것
    # -----------------------------
    stop_active_until = 0
    stop_lock_until = 0

    trumpet_lock_until = 0

    straight_delay_until = 0
    straight_active_until = 0
    straight_lock_until = 0

    slow_active_until = 0
    slow_lock_until = 0

    green_stop_until = 0
    green_lock_until = 0

    frame_count = 0
    yolo_interval = 3

    try:
        start_time = time.time()
        while camera.isOpened():
            ret, image = camera.read()
            if not ret:
                break
            
            image = cv2.flip(image, -1)
            now = time.time()

            if now - start_time > 3:
                start_flag = True

            frame_count += 1
            h_img, w_img, _ = image.shape

            base_offset = 140 if follow_side == "right" else 160
            mode = "GO"
            yolo_detect = "None"

            # ======================================================
            # SPEED OVERRIDE (SLOW 모드)
            # ======================================================
            current_speed = run_speed
            if now < slow_active_until:
                current_speed = 0.25
                mode = f"SLOW {slow_active_until - now:.1f}s"

            # ======================================================
            # STOP ACTIVE
            # ======================================================
            if now < stop_active_until:
                mode = f"STOP {stop_active_until - now:.1f}s"
                motor_stop()
                draw_debug(image, None, None, follow_side, mode, yolo_detect, base_offset)
                show(image)
                continue

            # ======================================================
            # STOP LOCK
            # ======================================================
            if stop_active_until <= now < stop_lock_until:
                mode = f"STOP_LOCK {stop_lock_until - now:.1f}s"
                

            # ======================================================
            # GREEN STOP
            # ======================================================
            if now < green_stop_until:
                mode = f"GREEN_STOP {green_stop_until - now:.1f}s"
                motor_stop()
                draw_debug(image, None, None, follow_side, mode, yolo_detect, base_offset)
                show(image)
                continue

            # ======================================================
            # STRAIGHT MODES
            # ======================================================
            if now < straight_delay_until:
                mode = "GO"

            elif straight_delay_until <= now < straight_active_until:
                mode = f"FORCE_STRAIGHT {straight_active_until - now:.1f}s"
                motor_go(current_speed)
                draw_debug(image, None, None, follow_side, mode, yolo_detect, base_offset)
                show(image)
                continue

            elif straight_active_until <= now < straight_lock_until:
                mode = f"STRAIGHT_LOCK {straight_lock_until - now:.1f}s"
                motor_go(current_speed)
                draw_debug(image, None, None, follow_side, mode, yolo_detect, base_offset)
                show(image)
                continue

            # ======================================================
            # YOLO DETECT
            # ======================================================
            if frame_count % yolo_interval == 0:
                results = model(image, imgsz=320, conf=0.5, verbose=False)
                cls = obj_filter.push_and_decide(results, image)
                yolo_detect = cls

                if cls in ["stop","traffic_red"]:
                    if now > stop_lock_until:
                        stop_active_until = now + STOP_DURATION
                        stop_lock_until = stop_active_until + STOP_LOCK

                elif cls in ["traffic_yellow","slow"]:
                    if now > slow_lock_until:
                        slow_active_until = now + SLOW_DURATION
                        slow_lock_until = slow_active_until + SLOW_LOCK

                elif cls == "trumpet":
                    if now > trumpet_lock_until:
                        beep_horn(0.2)
                        trumpet_lock_until = now + TRUMPET_DURATION

                elif cls == "left":
                    follow_side = "left"
                elif cls == "right":
                    follow_side = "right"

                elif cls == "straight":
                    straight_delay_until = now + STRAIGHT_DELAY
                    straight_active_until = straight_delay_until + STRAIGHT_DURATION
                    straight_lock_until = straight_active_until + STRAIGHT_LOCK

                elif cls == "traffic_green":
                    if now > green_lock_until:
                        green_stop_until = now + GREEN_STOP_DURATION
                        green_lock_until = green_stop_until + GREEN_LOCK
                        follow_side = "right"


            # ======================================================
            # FINISH LINE (RED LINE) LOGIC - 상태 기반
            # ======================================================
            if RED_LINE_MODE:
                # 1. 출발 직후 3초간은 무시
                if now - start_time > START_IGNORE_TIME:
                    
                    is_red_now = detect_red_line(image)

                    # [State 0] 첫 번째 빨간 선을 아직 못 본 상태
                    if red_state == 0:
                        if is_red_now:
                            print(">>> [RED LINE 1] 진입! (Start Passing)")
                            red_state = 1
                            no_red_count = 0

                    # [State 1] 첫 번째 빨간 선 위를 지나가는 중 (끊김 방지 버퍼 적용)
                    elif red_state == 1:
                        if is_red_now:
                            no_red_count = 0 # 빨간색이 보이면 카운트 리셋
                        else:
                            no_red_count += 1 # 안 보이면 카운트 증가
                        
                        # 안전장치: 연속으로 N프레임 이상 빨간색이 안 보여야 "통과 완료"로 인정
                        if no_red_count > NO_RED_THRESHOLD:
                            print(f">>> [RED LINE 1] 통과 완료! (Passed safely after {NO_RED_THRESHOLD} frames gap)")
                            red_state = 2

                    # [State 2] 첫 선을 통과했고, 두 번째 선(종료선)을 기다리는 중
                    elif red_state == 2:
                        if is_red_now:
                            print(">>> [RED LINE 2] 종료 선 감지! — FINISH STOP")
                            motor_stop()
                            mode = "FINISH_STOP"
                            draw_debug(image, None, None, follow_side, mode, yolo_detect, base_offset)
                            show(image)
                            
                            time.sleep(1) # 종료 전 1초 대기
                            exit()
                                

            # ======================================================
            # LANE FOLLOW
            # ======================================================
            mask = img_preprocess(image)
            found = find_line(mask, follow_side)
            
            if start_flag:
                if found:
                    cx, cy = found
                    lost_count = 0
                    direction = control_logic(cx, w_img, follow_side,
                                              base_offset=base_offset,
                                              dead_zone=5,
                                              speed=current_speed)
                
                else:
                    cx, cy = None, None
                    lost_count += 1

                    if lost_count <= hold_frames:
                        motor_go(0.25)
                        direction = "lost-short"
                    else:
                        if follow_side == "left":
                            motor_left(search_speed)
                            direction = "search-left"
                        else:
                            motor_right(search_speed)
                            direction = "search-right"

                        if lost_count >= hard_lost_stop:
                            motor_stop()
                            direction = "HARD-LOST-STOP"
                
                mode = direction.upper()
                draw_debug(image, cx, cy, follow_side, mode, yolo_detect, base_offset)

                show(image)
                roi_img = mask[int(mask.shape[0]*0.9):,:].copy()
                left_roi_x = (640//2) -30
                right_roi_x =(640//2) +30
                cv2.circle(roi_img,(left_roi_x,20),color=(255,255,255),radius=5)
                cv2.circle(roi_img,(right_roi_x,20),color=(255,255,255),radius=5)
                cv2.imshow("mask", roi_img)

            else:
                motor_stop()
                print("setting...")

            # ======================================================
            # 방향키 FOLLOW_SIDE 변경
            # ======================================================
            key = cv2.waitKey(1) & 0xFF
            if key == 81:
                follow_side = "left"
            elif key == 83:
                follow_side = "right"
            
            # 'q' 키를 누르면 종료
            if key == ord('q'):
                break

    finally:
        motor_stop()
        camera.release()
        cv2.destroyAllWindows()


# ==================================================
# DEBUG Visualization
# ==================================================
def draw_debug(image, cx, cy, follow_side, mode, yolo_detect, base_offset):
    h, w, _ = image.shape

    cv2.line(image, (w//2, 0), (w//2, h), (255,255,255), 2)
    cv2.putText(image, f"Side: {follow_side}", (10,40), cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)
    cv2.putText(image, f"Detect: {yolo_detect}", (10,70), cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,200,200),2)
    cv2.putText(image, f"Mode: {mode}", (10,100), cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,0),3)

    if cx is not None and cy is not None:
        cv2.circle(image, (cx, cy), 6, (0,255,0), -1)
        cv2.putText(image, f"cx={cx}", (cx+10, cy),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

        offset = -base_offset if follow_side == "right" else base_offset
        target = int(np.clip(cx + offset, 0, w-1))
        cv2.circle(image, (target, cy), 6, (255,0,0), -1)
        cv2.putText(image, f"target={target}", (target+10, cy+20),
                    cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,0,0),2)


def show(image):
    cv2.imshow("Frame", image)
    cv2.waitKey(1)


if __name__ == "__main__":
    main()