// 신호 이름 ↔ 절대 비트 인덱스 대응. 인덱스의 정본은 config `signal_map`, 이미지 크기는 레이아웃,
// stale 한계는 `timeouts.feedback_stale_ms` 다. 여기에는 기본값을 두지 않는다 — 조립층이 채워 주입한다.
#ifndef GRIPPER_HAL_IMPL_SIGNAL_MAP_HPP_
#define GRIPPER_HAL_IMPL_SIGNAL_MAP_HPP_

#include <array>
#include <cstdint>

#include "gripper_hal/types.hpp"

namespace gripper::hal::impl
{

inline constexpr uint8_t kStepBitCount = 6;
inline constexpr int32_t kUnmapped = -1;

// 인덱스 배열은 enum 순서를 따른다 — step[0..5] = IN0~IN5,
// control[ControlLine], feedback[FeedbackSignal].
struct SignalMap
{
    std::array<int32_t, kStepBitCount> step{{kUnmapped, kUnmapped, kUnmapped, kUnmapped, kUnmapped, kUnmapped}};
    std::array<int32_t, static_cast<size_t>(ControlLine::kCount)> control{};
    std::array<int32_t, static_cast<size_t>(FeedbackSignal::kCount)> feedback{};
    int32_t magazine_1 = kUnmapped;
    int32_t magazine_2 = kUnmapped;
    int32_t magazine_detected_level = 0;
    // 스테이션 이미지 크기(레이아웃 주입값, 운영값 DO 6워드=96 · DI 5워드=80).
    // 0 은 미설정이며 validate() 가 거부한다 — 상한을 모르면 범위 밖 인덱스를 송신하게 된다.
    int32_t do_bit_count = 0;
    int32_t di_bit_count = 0;
    // 스냅샷 신선도 한계. 값의 출처는 config `timeouts.feedback_stale_ms` 이며 매거진에도 같이 적용된다.
    Duration feedback_stale_limit{0};

    SignalMap()
    {
        control.fill(kUnmapped);
        feedback.fill(kUnmapped);
    }

    // 제어 라인의 비트 인덱스. kCount 이상은 kUnmapped.
    int32_t control_index(ControlLine line) const
    {
        const auto i = static_cast<size_t>(line);
        return i < control.size() ? control[i] : kUnmapped;
    }

    // IN0~IN5 중 bit 번째의 비트 인덱스. 범위 밖은 kUnmapped.
    int32_t step_index(uint8_t bit) const
    {
        return bit < step.size() ? step[bit] : kUnmapped;
    }

    // 피드백 신호의 비트 인덱스. kCount 이상은 kUnmapped.
    int32_t feedback_index(FeedbackSignal signal) const
    {
        const auto i = static_cast<size_t>(signal);
        return i < feedback.size() ? feedback[i] : kUnmapped;
    }
};

struct MapCheck
{
    bool ok = false;
    const char *reason = "";
};

// 미매핑·음수 인덱스, DO/DI 각 영역 내 중복, 비양수 stale 한계를 거부한다.
MapCheck validate(const SignalMap &map);

} // namespace gripper::hal::impl

#endif // GRIPPER_HAL_IMPL_SIGNAL_MAP_HPP_
