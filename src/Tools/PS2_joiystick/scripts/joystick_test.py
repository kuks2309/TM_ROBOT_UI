#!/usr/bin/env python3
import sys
import struct
import select

JS_EVENT_SIZE = 8
JS_EVENT_FORMAT = 'IhBB'
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

def main():
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
