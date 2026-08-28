# 버퍼 매거진 재고. 배열 인덱스 = 슬롯 번호(0~5).
#
# 슬롯 순서는 앞/뒤가 교차한다 — 0 앞왼 · 1 뒤왼 · 2 앞중 · 3 뒤중 · 4 앞오 · 5 뒤오.
# 도면(시트 170)의 배선 일련번호와 6자리 중 4자리가 어긋나므로 도면 순서로 읽지 말 것.
# 레시피의 palletN 이 곧 슬롯 N 이다.

uint8 SLOT_COUNT=6

# 판정에 쓴 io_resp 를 받은 시각. 발행 시각이 아니다.
builtin_interfaces/Time stamp

# 디바운스 확정값. true = 매거진 있음.
bool[6] present

# 디바운스 전 원시 판정. 진단용이며 기계 분기에 쓰지 말 것.
bool[6] raw

# false 면 io_resp 가 끊긴 것이다. present 는 마지막 확정값이며 현재 재고가 아니다.
# io_resp 는 읽기 성공 시에만 나오므로 침묵이 곧 이상이다.
bool valid
