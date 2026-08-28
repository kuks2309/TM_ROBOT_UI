#ifndef GRIPPER_HAL_IMPL_SIGNAL_MAP_HPP_
#define GRIPPER_HAL_IMPL_SIGNAL_MAP_HPP_

#include <array>
#include <cstdint>

#include "gripper_hal/types.hpp"

namespace gripper::hal::impl
{

inline constexpr uint8_t kStepBitCount = 6;
inline constexpr int32_t kUnmapped = -1;

struct SignalMap
{
    std::array<int32_t, kStepBitCount> step{{kUnmapped, kUnmapped, kUnmapped, kUnmapped, kUnmapped, kUnmapped}};
    std::array<int32_t, static_cast<size_t>(ControlLine::kCount)> control{};
    std::array<int32_t, static_cast<size_t>(FeedbackSignal::kCount)> feedback{};
    int32_t magazine_1 = kUnmapped;
    int32_t magazine_2 = kUnmapped;
    int32_t magazine_detected_level = 0;
    int32_t do_bit_count = 0;
    int32_t di_bit_count = 0;
    Duration feedback_stale_limit{0};

    SignalMap()
    {
        control.fill(kUnmapped);
        feedback.fill(kUnmapped);
    }

    int32_t control_index(ControlLine line) const
    {
        const auto i = static_cast<size_t>(line);
        return i < control.size() ? control[i] : kUnmapped;
    }

    int32_t step_index(uint8_t bit) const
    {
        return bit < step.size() ? step[bit] : kUnmapped;
    }

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

MapCheck validate(const SignalMap &map);

}

#endif
