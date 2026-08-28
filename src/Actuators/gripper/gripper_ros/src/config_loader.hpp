#ifndef GRIPPER_ROS_CONFIG_LOADER_HPP_
#define GRIPPER_ROS_CONFIG_LOADER_HPP_

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "gripper_hal_impl/signal_map.hpp"
#include "gripper_motion/fsm_types.hpp"

namespace gripper::ros
{

using hal::impl::SignalMap;
using motion::MotionConfig;
using motion::Profile;

struct ParamBag
{
    std::map<std::string, int64_t> ints;
    std::map<std::string, std::string> strings;
    std::vector<int64_t> allowed_steps;
};

struct LoadResult
{
    bool ok = false;
    std::string reason;
};

LoadResult loadMotionConfig(const ParamBag &params, MotionConfig &out);

LoadResult loadSignalMap(const ParamBag &params, SignalMap &out);

bool profileFromName(const std::string &name, Profile &out);

}

#endif
