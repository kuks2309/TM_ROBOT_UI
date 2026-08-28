// yaml 파라미터를 코어 설정 구조체로 옮긴다. rclcpp 를 모른다 — 노드가 파라미터를 읽어
// ParamBag 에 담고, 판정은 전부 여기서 한다(로봇 없이 시험 가능한 경계).
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

// 파라미터 원시값 묶음. 값이 없으면 키 자체가 없다 — 적재기가 «누락» 과 «0» 을 구분한다.
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

// 누락 키는 기본값으로 채우지 않고 거부한다 — 암묵 기본값으로 구동되지 않게(yaml 규율).
LoadResult loadMotionConfig(const ParamBag &params, MotionConfig &out);

// signal_map 을 절대 비트 인덱스로 적재한다. 이미지 크기는 레이아웃 주입이라 필수다.
LoadResult loadSignalMap(const ParamBag &params, SignalMap &out);

// 프로파일 이름은 계약이 정한 3종뿐이다.
bool profileFromName(const std::string &name, Profile &out);

} // namespace gripper::ros

#endif // GRIPPER_ROS_CONFIG_LOADER_HPP_
