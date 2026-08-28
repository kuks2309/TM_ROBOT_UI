#ifndef REMOTE_IO_ROS_IO_CONTRACT_HPP_
#define REMOTE_IO_ROS_IO_CONTRACT_HPP_

#include <cstdint>
#include <vector>

#include "remote_io_hal/types.hpp"

namespace remote_io::ros_assembly
{

enum class AlarmCode : int32_t
{
    kNone = 0,
    kDisconnect = 1101,
    kWritingFail = 1102,
    kReadingFail = 1103,
};

std::vector<int32_t> expandBits(const std::vector<uint16_t> &words, size_t bit_count);

std::vector<uint16_t> buildInitialImage(const std::vector<int32_t> &on_bits, uint16_t do_word_count);

struct WriteRequestCheck
{
    bool ok = false;
    const char *reason = "";
};
WriteRequestCheck checkWriteRequest(const std::vector<int32_t> &indices,
                                    const std::vector<int32_t> &states, uint16_t do_word_count);

struct AlarmDecision
{
    bool publish = false;
    AlarmCode code = AlarmCode::kNone;
};
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

TickPlan planTick(const TickInput &in);

bool shouldRetryWrite(hal::RemoteIoError err, int attempt, int retries);

AlarmCode clearOnWriteSuccess(AlarmCode current);

}

#endif
