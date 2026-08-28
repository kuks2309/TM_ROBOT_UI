#include "io_contract.hpp"

namespace remote_io::ros_assembly
{

std::vector<int32_t> expandBits(const std::vector<uint16_t> &words, size_t bit_count)
{
    std::vector<int32_t> out(bit_count, 0);
    for (size_t i = 0; i < bit_count; ++i)
    {
        const size_t w = i / 16;
        if (w >= words.size())
            break;
        out[i] = ((words[w] >> (i % 16)) & 0x1u) ? 1 : 0;
    }
    return out;
}

std::vector<uint16_t> buildInitialImage(const std::vector<int32_t> &on_bits, uint16_t do_word_count)
{
    std::vector<uint16_t> img(do_word_count, 0);
    const int32_t limit = static_cast<int32_t>(do_word_count) * 16;
    for (int32_t b : on_bits)
    {
        if (b < 0 || b >= limit)
            return {};
        img[static_cast<size_t>(b) / 16] =
            static_cast<uint16_t>(img[static_cast<size_t>(b) / 16] | (1u << (b % 16)));
    }
    return img;
}

WriteRequestCheck checkWriteRequest(const std::vector<int32_t> &indices,
                                    const std::vector<int32_t> &states, uint16_t do_word_count)
{
    if (indices.size() != states.size())
        return {false, "indices/states 길이 불일치"};
    if (indices.empty())
        return {false, "빈 요청"};
    const int32_t limit = static_cast<int32_t>(do_word_count) * 16;
    for (size_t i = 0; i < indices.size(); ++i)
    {
        if (indices[i] < 0 || indices[i] >= limit)
            return {false, "인덱스 범위 밖"};
        if (states[i] != 0 && states[i] != 1)
            return {false, "상태값이 0/1 이 아님"};
    }
    return {true, ""};
}

AlarmDecision decideAlarm(AlarmCode current, bool reconnected_this_tick)
{
    if (reconnected_this_tick)
        return {true, AlarmCode::kNone};
    if (current != AlarmCode::kNone)
        return {true, current};
    return {false, AlarmCode::kNone};
}

TickPlan planTick(const TickInput &in)
{
    TickPlan p;
    if (!in.read_ok)
    {
        p.error_code = (in.err == hal::RemoteIoError::kNotConnected) ? AlarmCode::kDisconnect
                                                                    : AlarmCode::kReadingFail;
        return p;
    }

    p.publish_io = true;
    p.reconnected = !in.was_connected;
    if (!p.reconnected)
    {
        p.error_code = in.current_error;
        return p;
    }

    p.seed_mirror = !in.mirror_seeded;
    p.apply_initial = in.apply_initial_image && !in.initial_applied;
    p.configure_watchdog = in.watchdog_timeout_ms > 0 && !in.watchdog_configured;
    p.error_code = AlarmCode::kNone;
    return p;
}

bool shouldRetryWrite(hal::RemoteIoError err, int attempt, int retries)
{
    if (err == hal::RemoteIoError::kNotConnected)
        return false;
    return attempt + 1 < retries;
}

AlarmCode clearOnWriteSuccess(AlarmCode current)
{
    return current == AlarmCode::kWritingFail ? AlarmCode::kNone : current;
}

}
