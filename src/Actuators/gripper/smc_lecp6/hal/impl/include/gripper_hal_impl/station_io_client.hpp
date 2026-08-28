#ifndef GRIPPER_HAL_IMPL_STATION_IO_CLIENT_HPP_
#define GRIPPER_HAL_IMPL_STATION_IO_CLIENT_HPP_

#include <cstdint>
#include <vector>

#include "gripper_hal/types.hpp"

namespace gripper::hal::impl
{

struct BitCommand
{
    int32_t index = 0;
    bool level = false;
};

struct StationImage
{
    std::vector<int32_t> di;
    std::vector<int32_t> do_bits;
    uint32_t seq = 0;
    TimePoint stamp{};
    bool valid = false;
};

struct WriteAck
{
    bool transport_ok = false;
    bool received = false;
    std::vector<int32_t> echo_indices;
    std::vector<int32_t> echo_states;
};

class IStationIoClient
{
  public:
    virtual ~IStationIoClient() = default;

    virtual WriteAck write_bits(const std::vector<BitCommand> &commands) = 0;

    virtual StationImage image() const = 0;

    virtual bool link_up() const = 0;
};

}

#endif
