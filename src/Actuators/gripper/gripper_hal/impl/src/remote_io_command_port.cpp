#include "gripper_hal_impl/remote_io_command_port.hpp"

#include <chrono>

namespace gripper::hal::impl
{
namespace
{

bool echo_matches(const std::vector<BitCommand> &commands, const WriteAck &ack)
{
    if (ack.echo_indices.size() != commands.size() || ack.echo_states.size() != commands.size())
    {
        return false;
    }
    for (size_t i = 0; i < commands.size(); ++i)
    {
        if (ack.echo_indices[i] != commands[i].index || (ack.echo_states[i] != 0) != commands[i].level)
        {
            return false;
        }
    }
    return true;
}

}

Result<void> RemoteIoCommandPort::fail(HalError error)
{
    ++error_count_;
    last_error_ = error;
    return Result<void>::err(error);
}

Result<void> RemoteIoCommandPort::write_step(uint8_t step)
{
    if (!map_valid_)
    {
        return fail(HalError::kNotReady);
    }
    if (step < kStepMin || step > kStepMax)
    {
        return fail(HalError::kOutOfRange);
    }

    std::vector<BitCommand> commands;
    commands.reserve(kStepBitCount);
    for (uint8_t bit = 0; bit < kStepBitCount; ++bit)
    {
        const int32_t index = map_.step_index(bit);
        if (index < 0)
        {
            return fail(HalError::kOutOfRange);
        }
        commands.push_back(BitCommand{index, ((step >> bit) & 0x1u) != 0});
    }
    return commit(commands);
}

Result<void> RemoteIoCommandPort::write_line(ControlLine line, bool level)
{
    if (!map_valid_)
    {
        return fail(HalError::kNotReady);
    }
    const int32_t index = map_.control_index(line);
    if (index < 0)
    {
        return fail(HalError::kOutOfRange);
    }
    return commit({BitCommand{index, level}});
}

Result<void> RemoteIoCommandPort::clear_step_and_drive()
{
    if (!map_valid_)
    {
        return fail(HalError::kNotReady);
    }
    std::vector<BitCommand> commands;
    commands.reserve(kStepBitCount + 1);
    for (uint8_t bit = 0; bit < kStepBitCount; ++bit)
    {
        const int32_t index = map_.step_index(bit);
        if (index < 0)
        {
            return fail(HalError::kOutOfRange);
        }
        commands.push_back(BitCommand{index, false});
    }
    const int32_t drive = map_.control_index(ControlLine::kDrive);
    if (drive < 0)
    {
        return fail(HalError::kOutOfRange);
    }
    commands.push_back(BitCommand{drive, false});
    return commit(commands);
}

Result<void> RemoteIoCommandPort::commit(const std::vector<BitCommand> &commands)
{
    if (commands.empty())
    {
        return fail(HalError::kOutOfRange);
    }
    if (!map_valid_)
    {
        return fail(HalError::kNotReady);
    }
    if (!client_ || !client_->link_up())
    {
        return fail(HalError::kNotReady);
    }

    const WriteAck ack = client_->write_bits(commands);
    if (!ack.transport_ok)
    {
        return fail(HalError::kIndeterminate);
    }
    if (!ack.received)
    {
        return fail(HalError::kIndeterminate);
    }
    if (!echo_matches(commands, ack))
    {
        return fail(HalError::kProtocol);
    }
    last_error_ = HalError::kNone;
    return Result<void>::ok();
}

Health RemoteIoCommandPort::health() const
{
    Health h;
    h.link_up = map_valid_ && client_ && client_->link_up();
    h.error_count = error_count_;
    h.last_error = last_error_;
    const StationImage image = client_ ? client_->image() : StationImage{};
    h.last_seq = image.valid ? image.seq : 0;
    h.snapshot_age = image.valid ? std::chrono::duration_cast<Duration>(clock_() - image.stamp)
                                 : map_.feedback_stale_limit + Duration{1};
    return h;
}

}
