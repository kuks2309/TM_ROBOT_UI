// legacy tc_io 공개 계약의 **순수 변환·정책 부분** (remote_io M4)
//
// ROS 없이 시험할 수 있도록 노드에서 분리한다 — 20ms 발행 자체가 아니라 "무엇을 담아
// 내보내는가"와 "언제 알람을 내는가"가 파리티의 실체이기 때문이다.
//
// 근거: M0 인벤토리 §3(ROS 계약)·§4(주기·initValue). 인덱스 = 워드번호×16 + 비트(LSB-first),
// io_board_data.h 의 IN_*/OUT_* 상수와 1:1.
#ifndef REMOTE_IO_ROS_IO_CONTRACT_HPP_
#define REMOTE_IO_ROS_IO_CONTRACT_HPP_

#include <cstdint>
#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::ros_assembly
{

// legacy 알람 코드 (인벤토리 §3 표) — 1110(IO_CAN_FAIL)은 legacy 에서도 정의만 있고 미사용이라
// 여기서도 만들지 않는다(사도 상수 이식 금지).
enum class AlarmCode : int32_t
{
    kNone = 0,
    kDisconnect = 1101,
    kWritingFail = 1102,
    kReadingFail = 1103,
};

// 워드 벡터 → 비트 배열(int32 0/1). legacy 는 io_di 를 80, io_do 를 96 으로 resize 한 뒤
// std::bitset<16> LSB-first 로 전개한다(cpp:506-507, 528-551).
std::vector<int32_t> expandBits(const std::vector<uint16_t> &words, size_t bit_count);

// 기동 초기값 이미지 — **ON 목록은 호출자(config)가 소유**한다. 코드 하드코딩 금지
// (ADR-001(remote_io) — legacy 는 cpp:170-178 에 8비트를 박아 뒀다).
// 범위 밖 인덱스가 있으면 빈 벡터를 돌려준다(조용한 무시 금지).
std::vector<uint16_t> buildInitialImage(const std::vector<int32_t> &on_bits, uint16_t do_word_count);

// 서비스 요청 검증 — indices/states 길이 불일치·범위 밖·상태값 비 0/1 은 거부.
// legacy 는 길이 불일치를 검사하지 않아 인덱스 초과 접근 위험이 있었다(§6 결함군).
struct WriteRequestCheck
{
    bool ok = false;
    const char *reason = "";
};
WriteRequestCheck checkWriteRequest(const std::vector<int32_t> &indices,
                                    const std::vector<int32_t> &states, uint16_t do_word_count);

// 알람 발행 판정 — legacy 는 error_code != 0 인 동안 20ms 마다 **반복 발행**하고,
// 해제 경로는 재연결 1회 발행뿐이다(cpp:562-567, 218-224). 그 관측 동작을 그대로 재현한다.
struct AlarmDecision
{
    bool publish = false;
    AlarmCode code = AlarmCode::kNone;
};
AlarmDecision decideAlarm(AlarmCode current, bool reconnected_this_tick);

// ── 틱 결정 (노드 상태머신의 순수 부분) ──
//
// 조립층의 결정을 rclcpp 없이 시험 가능한 형태로 분리한다. 상태 플래그가 늘어날수록
// "어떤 조건에서 무엇을 하는가" 가 노드 본문에 흩어져 회귀가 조용히 들어온다.

struct TickInput
{
    bool read_ok = false;
    hal::RemoteIoError err = hal::RemoteIoError::kNone; // read_ok=false 일 때만 의미
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

// 읽기 결과와 현재 상태로 이번 틱에 할 일을 정한다.
//  - 시드는 **최초 1회**(재연결마다 하면 재기록 결과를 덮는다)
//  - 초기 이미지는 **생애 1회**(legacy 는 생성자에서만 부른다)
//  - 읽기 실패 시 **발행하지 않는다**(stale 위장 금지)
TickPlan planTick(const TickInput &in);

// 쓰기 재시도 판정 — 미연결이면 재시도하지 않는다(legacy 파리티, 콜백이 틱을 막는 것 방지).
bool shouldRetryWrite(hal::RemoteIoError err, int attempt, int retries);

// 쓰기 성공 시 해제할 알람 — **쓰기 실패(1102)만** 해제한다.
// 읽기 실패(1103)·미연결(1101)까지 지우면 쓰기 성공이 읽기 상태를 대변하게 된다.
AlarmCode clearOnWriteSuccess(AlarmCode current);

} // namespace remote_io::ros_assembly

#endif // REMOTE_IO_ROS_IO_CONTRACT_HPP_
