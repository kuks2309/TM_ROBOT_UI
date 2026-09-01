#ifndef REMOTE_IO_ROS_IO_CONTRACT_HPP_
#define REMOTE_IO_ROS_IO_CONTRACT_HPP_

#include <cstdint>
#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::ros_assembly
{

// 레거시 tc_io 알람 코드 그대로 — 소비자가 숫자값에 의존한다.
// 1110(IO_CAN_FAIL)은 레거시에도 정의만 있고 미사용이라 이식하지 않는다.
enum class AlarmCode : int32_t
{
    kNone = 0,
    kDisconnect = 1101,
    kWritingFail = 1102,
    kReadingFail = 1103,
};

// 워드 이미지 → 비트 배열(LSB-first, 인덱스 = 워드×16 + 비트).
// 워드가 모자라면 나머지는 0 — 쓰레기 값을 내보내지 않는다.
std::vector<int32_t> expandBits(const std::vector<uint16_t> &words, size_t bit_count);

// 기동 초기 출력 이미지 조립. ON 비트가 하나라도 범위 밖이면 빈 벡터로 전체 거부
// — 일부만 조용히 적용하지 않는다(DO 는 실제 장치를 구동한다).
std::vector<uint16_t> buildInitialImage(const std::vector<int32_t> &on_bits, uint16_t do_word_count);

struct WriteRequestCheck
{
    bool ok = false;
    const char *reason = "";
};
// 쓰기 서비스 요청 검증 — 길이 일치·비공백·인덱스 범위·0/1 값. 실패 시 사유 문자열 동반.
WriteRequestCheck checkWriteRequest(const std::vector<int32_t> &indices,
                                    const std::vector<int32_t> &states, uint16_t do_word_count);

struct AlarmDecision
{
    bool publish = false;
    AlarmCode code = AlarmCode::kNone;
};
// 알람 발행 판단 — 에러 지속 중 매 틱 반복 발행, 재연결 틱에는 해제(kNone) 1회.
AlarmDecision decideAlarm(AlarmCode current, bool reconnected_this_tick);


struct TickInput
{
    bool read_ok = false;
    hal::RemoteIoError err = hal::RemoteIoError::kNone;
    bool was_connected = false;
    bool mirror_seeded = false;
    bool initial_applied = false;
    bool apply_initial_image = false;
    int watchdog_timeout_ms = 0;
    bool watchdog_configured = false;
    AlarmCode current_error = AlarmCode::kNone;
};

struct TickPlan
{
    bool reconnected = false;
    bool seed_mirror = false;
    bool apply_initial = false;
    bool configure_watchdog = false;
    bool publish_io = false;
    AlarmCode error_code = AlarmCode::kNone;
};

// 틱 계획 상태기계(순수 함수 — rclcpp 없이 단위시험된다). 읽기 실패면 발행 없이 알람 코드만,
// 성공이면 발행 + 재연결 틱에 한해 시드/초기이미지/워치독 구성을 1회 계획한다.
TickPlan planTick(const TickInput &in);

// 쓰기 재시도 판단 — kNotConnected 는 즉시 중단(미연결 재시도는 틱만 막는다), 그 외 예산 내 재시도.
bool shouldRetryWrite(hal::RemoteIoError err, int attempt, int retries);

// 쓰기 성공 시 kWritingFail 만 해제 — 다른 알람 코드는 각자의 해제 경로를 가진다.
AlarmCode clearOnWriteSuccess(AlarmCode current);

}

#endif
