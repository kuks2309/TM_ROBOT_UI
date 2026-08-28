// 원격 IO 스테이션 클라이언트 심(seam) — 그리퍼 백엔드가 보는 유일한 외부 창구.
//
// rclcpp 는 여기 없다. ROS 결선(io_service 클라이언트·io_resp 구독)은 조립층이 이 인터페이스를
// 구현해 주입한다. 그리퍼는 스테이션에 직접 쓰지 않는다(⟦CI:gripper-io-single-master⟧).
#ifndef GRIPPER_HAL_IMPL_STATION_IO_CLIENT_HPP_
#define GRIPPER_HAL_IMPL_STATION_IO_CLIENT_HPP_

#include <cstdint>
#include <vector>

#include "gripper_hal/types.hpp"

namespace gripper::hal::impl
{

// 절대 비트 인덱스(워드×16 + 비트, LSB-first)와 목표 레벨.
struct BitCommand
{
    int32_t index = 0;
    bool level = false;
};

// 스테이션 입력 이미지 1장. di/do_bits 는 비트당 0/1 이며 인덱스는 BitCommand 와 같은 규약.
// seq 는 이미지의 단조 증가 번호, stamp 는 수신 시각, valid=false 는 수신 이력 없음.
struct StationImage
{
    std::vector<int32_t> di;
    std::vector<int32_t> do_bits;
    uint32_t seq = 0;
    TimePoint stamp{};
    bool valid = false;
};

// 쓰기 1회의 결과. transport_ok 는 응답 수신 여부, received 는 스테이션의 쓰기 확정 여부,
// echo_* 는 응답이 되돌려 준 요청 사본이다.
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

    // 비트들을 한 요청으로 보낸다. 같은 워드의 비트는 스테이션이 단일 RMW 로 커밋한다.
    virtual WriteAck write_bits(const std::vector<BitCommand> &commands) = 0;

    // 최신 입력 이미지. 갱신은 구현체가 담당하며 호출은 부작용이 없다.
    virtual StationImage image() const = 0;

    virtual bool link_up() const = 0;
};

} // namespace gripper::hal::impl

#endif // GRIPPER_HAL_IMPL_STATION_IO_CLIENT_HPP_
