#include "gripper_hal/command_port.hpp"
#include "gripper_hal/feedback_port.hpp"
#include "gripper_common/magazine_port.hpp"
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
    FeedbackSnapshot ok{};
    ok.bits = bit(FeedbackSignal::kServoReady) | bit(FeedbackSignal::kSetOn) | bit(FeedbackSignal::kAlarm) |
              bit(FeedbackSignal::kEmergencyStop);
    ok.fresh = true;
    ok.seq = 7;
    CHECK(alarm_state(ok) == SignalState::kInactive);
    CHECK(emergency_stop_state(ok) == SignalState::kInactive);
    CHECK(is_ready_for_drive(ok));
    CHECK(is_ready_for_origin(ok));

    FeedbackSnapshot stale = ok;
    stale.fresh = false;
    CHECK(alarm_state(stale) == SignalState::kUnknown);
    CHECK(emergency_stop_state(stale) == SignalState::kUnknown);
    CHECK(!is_ready_for_drive(stale));
    CHECK(!is_ready_for_origin(stale));

    FeedbackSnapshot stale_with_good_bits = ok;
    stale_with_good_bits.fresh = false;
    CHECK(alarm_state(stale_with_good_bits) != SignalState::kInactive);

    FeedbackSnapshot alarmed = ok;
    alarmed.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kAlarm));
    CHECK(alarm_state(alarmed) == SignalState::kActive);
    CHECK(!is_ready_for_drive(alarmed));
    CHECK(!is_ready_for_origin(alarmed));

    FeedbackSnapshot estop = ok;
    estop.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kEmergencyStop));
    CHECK(emergency_stop_state(estop) == SignalState::kActive);
    CHECK(!is_ready_for_drive(estop));
    CHECK(!is_ready_for_origin(estop));

    FeedbackSnapshot busy = ok;
    busy.bits |= bit(FeedbackSignal::kBusy);
    CHECK(!is_ready_for_drive(busy));
    CHECK(!is_ready_for_origin(busy));

    FeedbackSnapshot noseton = ok;
    noseton.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kSetOn));
    CHECK(!is_ready_for_drive(noseton));
    CHECK(is_ready_for_origin(noseton));

    FeedbackSnapshot nosvre = ok;
    nosvre.bits &= static_cast<uint16_t>(~bit(FeedbackSignal::kServoReady));
    CHECK(!is_ready_for_drive(nosvre));
    CHECK(!is_ready_for_origin(nosvre));

    MagazineSnapshot m{};
    m.fresh = true;
    m.seq = 7;
    m.detected_1 = true;
    m.detected_2 = true;
    CHECK(both_detected(m));
    CHECK(any_detected(m));
    CHECK(same_image(ok, m));
    m.detected_2 = false;
    CHECK(!both_detected(m));
    CHECK(any_detected(m));
    m.fresh = false;
    CHECK(!both_detected(m));
    CHECK(!any_detected(m));
    CHECK(!same_image(ok, m));

    MagazineSnapshot other_image{};
    other_image.fresh = true;
    other_image.seq = 8;
    CHECK(!same_image(ok, other_image));

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

    CHECK(Result<int>::err(HalError::kNone).error() != HalError::kNone);
    CHECK(Result<void>::err(HalError::kNone).error() != HalError::kNone);

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

    const int moved = Result<int>::ok(7).value();
    CHECK(moved == 7);
    static_assert(std::is_same_v<decltype(Result<int>::ok(1).value()), int>,
                  "rvalue value() 는 참조가 아니라 값을 반환해야 한다");

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
