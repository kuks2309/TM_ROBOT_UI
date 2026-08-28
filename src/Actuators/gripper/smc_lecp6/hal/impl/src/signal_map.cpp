#include "gripper_hal_impl/signal_map.hpp"

#include <vector>

namespace gripper::hal::impl
{
namespace
{

bool has_duplicate(const std::vector<int32_t> &indices)
{
    for (size_t i = 0; i < indices.size(); ++i)
    {
        for (size_t j = i + 1; j < indices.size(); ++j)
        {
            if (indices[i] == indices[j])
            {
                return true;
            }
        }
    }
    return false;
}

}

MapCheck validate(const SignalMap &map)
{
    if (map.do_bit_count <= 0 || map.di_bit_count <= 0)
    {
        return MapCheck{false, "이미지 크기 미설정(do_bit_count·di_bit_count)"};
    }

    std::vector<int32_t> outputs;
    for (uint8_t b = 0; b < kStepBitCount; ++b)
    {
        const int32_t index = map.step_index(b);
        if (index < 0)
        {
            return MapCheck{false, "step 비트 미매핑"};
        }
        if (index >= map.do_bit_count)
        {
            return MapCheck{false, "step 비트가 출력 이미지 범위 밖"};
        }
        outputs.push_back(index);
    }
    for (size_t i = 0; i < static_cast<size_t>(ControlLine::kCount); ++i)
    {
        const int32_t index = map.control_index(static_cast<ControlLine>(i));
        if (index < 0)
        {
            return MapCheck{false, "control 라인 미매핑"};
        }
        if (index >= map.do_bit_count)
        {
            return MapCheck{false, "control 라인이 출력 이미지 범위 밖"};
        }
        outputs.push_back(index);
    }
    if (has_duplicate(outputs))
    {
        return MapCheck{false, "출력 인덱스 중복"};
    }

    std::vector<int32_t> inputs;
    for (size_t i = 0; i < static_cast<size_t>(FeedbackSignal::kCount); ++i)
    {
        const int32_t index = map.feedback_index(static_cast<FeedbackSignal>(i));
        if (index < 0)
        {
            return MapCheck{false, "feedback 신호 미매핑"};
        }
        if (index >= map.di_bit_count)
        {
            return MapCheck{false, "feedback 신호가 입력 이미지 범위 밖"};
        }
        inputs.push_back(index);
    }
    if (map.magazine_1 < 0 || map.magazine_2 < 0)
    {
        return MapCheck{false, "magazine 감지점 미매핑"};
    }
    if (map.magazine_1 >= map.di_bit_count || map.magazine_2 >= map.di_bit_count)
    {
        return MapCheck{false, "magazine 감지점이 입력 이미지 범위 밖"};
    }
    inputs.push_back(map.magazine_1);
    inputs.push_back(map.magazine_2);
    if (has_duplicate(inputs))
    {
        return MapCheck{false, "입력 인덱스 중복"};
    }

    const int32_t step_word = map.step_index(0) / 16;
    for (uint8_t b = 1; b < kStepBitCount; ++b)
    {
        if (map.step_index(b) / 16 != step_word)
        {
            return MapCheck{false, "step 비트가 여러 워드에 걸침(단일 RMW 불가)"};
        }
    }
    if (map.control_index(ControlLine::kDrive) / 16 != step_word)
    {
        return MapCheck{false, "DRIVE 가 step 비트와 다른 워드(복귀 원자성 불가)"};
    }

    if (map.magazine_detected_level != 0 && map.magazine_detected_level != 1)
    {
        return MapCheck{false, "magazine 감지 레벨은 0 또는 1"};
    }
    if (map.feedback_stale_limit.count() <= 0)
    {
        return MapCheck{false, "feedback stale 한계는 양수"};
    }
    return MapCheck{true, ""};
}

}
