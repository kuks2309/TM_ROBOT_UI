// gripper_hal 계약 검증 — 극성 판정·착수 조건·인터록 헬퍼·Result 규약을 실행으로 확인한다.
#include "gripper_hal/command_port.hpp"
#include "gripper_hal/feedback_port.hpp"
#include "gripper_hal/magazine_port.hpp"
#include "gripper_hal/types.hpp"
#include <cstdio>
#include <type_traits>

using namespace gripper::hal;
static int fails = 0;
#define CHECK(c)                                                                                                       \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(c))                                                                                                      \
        {                                                                                                              \
            std::printf("FAIL: %s (line %d)\n", #c, __LINE__);                                                         \
            ++fails;                                                                                                   \
        }                                                                                                              \
    } while (0)

static uint16_t bit(FeedbackSignal s)
{
    return static_cast<uint16_t>(1u << static_cast<uint8_t>(s));
}

int main()
{
    // 정상 상태: SVRE=1, SETON=1, ALARM=1(정상), ESTOP=1(정상), BUSY=0
    FeedbackSnapshot ok{};
    ok.bits = bit(FeedbackSignal::kServoReady) | bit(FeedbackSignal::kSetOn) | bit(FeedbackSignal::kAlarm) |
              bit(FeedbackSignal::kEmergencyStop);
    ok.fresh = true;
    ok.seq = 7;
    CHECK(alarm_state(ok) == SignalState::kInactive);
    CHECK(emergency_stop_state(ok) == SignalState::kInactive);
    CHECK(is_ready_for_drive(ok));
    CHECK(is_ready_for_origin(ok));

    // stale 은 판정 불가 — 정상으로도 이상으로도 만들지 않는다
    FeedbackSnapshot stale = ok;
    stale.fresh = false;
    CHECK(alarm_state(stale) == SignalState::kUnknown);
    CHECK(emergency_stop_state(stale) == SignalState::kUnknown);
    CHECK(!is_ready_for_drive(stale));
    CHECK(!is_ready_for_origin(stale));

    // stale 스냅샷은 직전 정상값이 남아 있어도 정상으로 판정하지 않는다
    FeedbackSnapshot stale_with_good_bits = ok;
    stale_with_good_bits.fresh = false;
    CHECK(alarm_state(stale_with_good_bits) != SignalState::kInactive);

    // ALARM 비트가 0 이면 알람(negative-true)
    FeedbackSnapshot alarmed = ok;
    alarmed.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kAlarm));
    CHECK(alarm_state(alarmed) == SignalState::kActive);
    CHECK(!is_ready_for_drive(alarmed));
    CHECK(!is_ready_for_origin(alarmed));

    // ESTOP 비트 0 = 비상정지
    FeedbackSnapshot estop = ok;
    estop.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kEmergencyStop));
    CHECK(emergency_stop_state(estop) == SignalState::kActive);
    CHECK(!is_ready_for_drive(estop));
    CHECK(!is_ready_for_origin(estop));

    // BUSY 중에는 착수 불가
    FeedbackSnapshot busy = ok;
    busy.bits |= bit(FeedbackSignal::kBusy);
    CHECK(!is_ready_for_drive(busy));
    CHECK(!is_ready_for_origin(busy));

    // SETON=0 이면 DRIVE 는 불가, 원점복귀는 가능
    FeedbackSnapshot noseton = ok;
    noseton.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kSetOn));
    CHECK(!is_ready_for_drive(noseton));
    CHECK(is_ready_for_origin(noseton));

    // 서보 미확립이면 착수 불가
    FeedbackSnapshot nosvre = ok;
    nosvre.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kServoReady));
    CHECK(!is_ready_for_drive(nosvre));
    CHECK(!is_ready_for_origin(nosvre));

    // 매거진 인터록 헬퍼
    MagazineSnapshot m{};
    m.fresh = true;
    m.seq = 7;
    m.detected_1 = true;
    m.detected_2 = true;
    CHECK(both_detected(m));
    CHECK(any_detected(m));
    CHECK(same_image(ok, m)); // 같은 입력 이미지에서 온 스냅샷 쌍
    m.detected_2 = false;
    CHECK(!both_detected(m));
    CHECK(any_detected(m));
    m.fresh = false;
    CHECK(!both_detected(m));
    CHECK(!any_detected(m)); // stale 은 판정 불가
    CHECK(!same_image(ok, m));

    // seq 불일치는 조합 판정 금지
    MagazineSnapshot other_image{};
    other_image.fresh = true;
    other_image.seq = 8;
    CHECK(!same_image(ok, other_image));

    // Result 계약: 실패는 값 없음 + 오류 코드, 성공은 그 반대
    auto e = Result<int>::err(HalError::kTimeout);
    CHECK(!e.has_value());
    CHECK(e.error() == HalError::kTimeout);
    auto v = Result<int>::ok(42);
    CHECK(v.has_value());
    CHECK(v.value() == 42);
    CHECK(v.error() == HalError::kNone);
    auto ve = Result<void>::err(HalError::kOutOfRange);
    CHECK(!ve.has_value());
    CHECK(ve.error() == HalError::kOutOfRange);

    // err(kNone) 은 kNone 으로 남지 않는다
    CHECK(Result<int>::err(HalError::kNone).error() != HalError::kNone);
    CHECK(Result<void>::err(HalError::kNone).error() != HalError::kNone);

    // 값 없는 Result 의 value() 는 예외를 던진다
    bool threw = false;
    try
    {
        (void)Result<int>::err(HalError::kNotReady).value();
    }
    catch (const std::bad_optional_access &)
    {
        threw = true;
    }
    CHECK(threw);

    // rvalue value() 는 참조가 아니라 값을 반환한다
    const int moved = Result<int>::ok(7).value();
    CHECK(moved == 7);
    static_assert(std::is_same_v<decltype(Result<int>::ok(1).value()), int>,
                  "rvalue value() 는 참조가 아니라 값을 반환해야 한다");

    // 스텝 번호 ↔ 6비트 왕복 항등
    for (uint8_t step = kStepMin; step <= kStepMax; ++step)
    {
        uint8_t rebuilt = 0;
        for (int i = 0; i < 6; ++i)
        {
            rebuilt |= static_cast<uint8_t>(((step >> i) & 1) << i);
        }
        CHECK(rebuilt == step);
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
