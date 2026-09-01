#!/usr/bin/env python3
"""리눅스 joydev(/dev/input/jsN)를 직접 읽어 축·버튼 이벤트를 출력하는 조이스틱 진단 CLI."""
import sys
import struct
import select

# 커널 joydev 이벤트 구조체(struct js_event): u32 time(ms) · s16 value · u8 type · u8 number = 8B.
JS_EVENT_SIZE = 8
JS_EVENT_FORMAT = 'IhBB'
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
# 열자마자 커널이 현재 상태를 쏟아내는 합성 이벤트 플래그 — type 에 OR 되어 온다.
JS_EVENT_INIT = 0x80

def main():
    """이벤트 루프 — select 0.1s 폴링, 축 값은 s16 최대치 32767 로 나눠 [-1, 1] 정규화.

    INIT 이벤트는 집계만 하고 출력하지 않는다(연결 직후 도배 방지).
    장치 부재·권한 없음은 안내 후 rc=1, Ctrl+C 시 감지된 축/버튼 수 요약.
    """
    device_path = sys.argv[1] if len(sys.argv) > 1 else '/dev/input/js0'

    print(f"조이스틱 테스트: {device_path}")
    print("종료: Ctrl+C")
    print("-" * 50)

    axes = {}
    buttons = {}

    try:
        with open(device_path, 'rb') as js:
            print(f"연결됨: {device_path}")
            print()

            while True:
                readable, _, _ = select.select([js], [], [], 0.1)
                if not readable:
                    continue

                event = js.read(JS_EVENT_SIZE)
                if not event:
                    break

                time, value, event_type, number = struct.unpack(JS_EVENT_FORMAT, event)

                is_init = bool(event_type & JS_EVENT_INIT)
                event_type &= ~JS_EVENT_INIT

                if event_type == JS_EVENT_AXIS:
                    normalized = value / 32767.0
                    axes[number] = normalized
                    if not is_init:
                        print(f"축 {number}: {normalized:+.3f} ({value:+6d})")

                elif event_type == JS_EVENT_BUTTON:
                    buttons[number] = bool(value)
                    state = "눌림" if value else "해제"
                    if not is_init:
                        print(f"버튼 {number}: {state}")

    except FileNotFoundError:
        print(f"오류: 장치를 찾을 수 없습니다 - {device_path}")
        print("조이스틱이 연결되어 있는지 확인하세요.")
        sys.exit(1)
    except PermissionError:
        print(f"오류: 장치 권한 없음 - {device_path}")
        print("해결: sudo usermod -a -G input $USER 후 재로그인")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n종료됨")
        print(f"감지된 축: {len(axes)}개")
        print(f"감지된 버튼: {len(buttons)}개")

if __name__ == '__main__':
    main()
