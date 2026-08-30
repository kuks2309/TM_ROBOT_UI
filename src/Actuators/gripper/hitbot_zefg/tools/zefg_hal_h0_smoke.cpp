// zefg_hal_h0_smoke — 실기 H0(관측·읽기 전용) 스모크: SerialPortLink→RtuClient→ZefgHal 전체
// C++ 체인을 실제 장치에 대고 readSnapshot 1회 수행한다. write 계열(commandInitialize·
// writeTargets)은 이 도구에서 절대 호출하지 않는다(zefg_c35_probe.py 와 동일한 H0 규율).
//
// usage: zefg_hal_h0_smoke <device> [baud=115200] [unit=1]
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

#include "hitbot_zefg/zefg_hal.hpp"
#include "modbus_rtu/rtu_client.hpp"
#include "modbus_rtu/serial_port.hpp"

using comm::modbus_rtu::ISerialLink;
using comm::modbus_rtu::RtuClient;
using comm::modbus_rtu::RtuClientConfig;
using gripper::hitbot::ClampStatus;
using gripper::hitbot::InitStatus;
using gripper::hitbot::ZefgHal;

namespace
{

const char *initName(InitStatus s)
{
    switch (s)
    {
    case InitStatus::kNotInitialized:
        return "NotInitialized";
    case InitStatus::kInitializing:
        return "Initializing";
    case InitStatus::kCompleted:
        return "Completed";
    }
    return "?";
}

const char *clampName(ClampStatus s)
{
    switch (s)
    {
    case ClampStatus::kInPlace:
        return "InPlace";
    case ClampStatus::kMoving:
        return "Moving";
    case ClampStatus::kClamping:
        return "Clamping";
    case ClampStatus::kDropping:
        return "Dropping";
    case ClampStatus::kUnknown:
        return "Unknown";
    }
    return "?";
}

} // namespace

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 4)
    {
        std::fputs("usage: zefg_hal_h0_smoke <device> [baud=115200] [unit=1]\n", stderr);
        return 2;
    }
    const std::string device = argv[1];
    const int baud = (argc >= 3) ? std::atoi(argv[2]) : 115200;
    const int unit = (argc == 4) ? std::atoi(argv[3]) : 1;
    if (baud <= 0 || unit <= 0 || unit > 247)
    {
        std::fputs("invalid baud/unit\n", stderr);
        return 2;
    }

    auto link_result = comm::modbus_rtu::SerialPortLink::open(device, baud);
    if (!link_result)
    {
        std::fprintf(stderr, "open failed (error=%d)\n", static_cast<int>(link_result.error()));
        return 1;
    }
    std::shared_ptr<ISerialLink> link = std::move(link_result.value());

    RtuClientConfig config;
    config.unit_id = static_cast<uint8_t>(unit);
    ZefgHal hal(std::make_shared<RtuClient>(link, config));

    auto snap = hal.readSnapshot();
    if (!snap)
    {
        std::fprintf(stderr, "readSnapshot failed (HalError=%d, exception=0x%02X)\n",
                     static_cast<int>(snap.error()), hal.lastExceptionCode());
        return 1;
    }

    const auto &s = snap.value();
    std::printf("init=%s clamp=%s position=%.3fmm speed=%.3fmm/s current=%.3fA exception=0x%02X\n",
                initName(s.init), clampName(s.clamp), static_cast<double>(s.position_mm),
                static_cast<double>(s.speed_mms), static_cast<double>(s.current_a), s.exception_code);

    const auto h = hal.health();
    std::printf("health: link_up=%d error_count=%u last_error=%d\n", h.link_up ? 1 : 0, h.error_count,
                static_cast<int>(h.last_error));
    return 0;
}
