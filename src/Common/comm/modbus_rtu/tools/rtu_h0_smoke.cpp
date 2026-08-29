// modbus_rtu_h0_smoke — 실기 H0(관측·읽기 전용) 스모크 도구.
// readHoldingRegisters 1회만 호출한다 — writeSingleRegister/writeMultipleRegisters 는 이 도구에서
// 절대 호출하지 않는다(그리퍼 zefg_c35_probe.py 와 동일한 H0 규율).
//
// usage: modbus_rtu_h0_smoke <device> [baud=115200] [unit=1] <addr> <qty>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>

#include "modbus_rtu/rtu_client.hpp"
#include "modbus_rtu/serial_port.hpp"

using comm::modbus_rtu::ISerialLink;
using comm::modbus_rtu::RtuClient;
using comm::modbus_rtu::RtuClientConfig;
using comm::modbus_rtu::RtuError;
using comm::modbus_rtu::SerialPortLink;

namespace
{

constexpr char kUsage[] = "usage: modbus_rtu_h0_smoke <device> [baud=115200] [unit=1] <addr> <qty>\n";

// 양수 정수 파싱(0x 접두 허용 — base 0). 실패 시 false.
bool parsePositive(const char *s, long *out)
{
    char *end = nullptr;
    errno = 0;
    const long v = std::strtol(s, &end, 0);
    if (end == s || *end != '\0' || errno != 0 || v <= 0)
        return false;
    *out = v;
    return true;
}

const char *errorName(RtuError e)
{
    switch (e)
    {
    case RtuError::kNone:
        return "kNone";
    case RtuError::kNotOpen:
        return "kNotOpen";
    case RtuError::kTimeout:
        return "kTimeout";
    case RtuError::kFrameShort:
        return "kFrameShort";
    case RtuError::kCrcMismatch:
        return "kCrcMismatch";
    case RtuError::kException:
        return "kException";
    case RtuError::kOutOfRange:
        return "kOutOfRange";
    case RtuError::kProtocol:
        return "kProtocol";
    }
    return "?";
}

} // namespace

int main(int argc, char **argv)
{
    const int nargs = argc - 1;
    if (nargs != 3 && nargs != 4 && nargs != 5)
    {
        std::fputs(kUsage, stderr);
        return 2;
    }

    const std::string device = argv[1];
    long baud = 115200;
    long unit = 1;
    long addr = 0;
    long qty = 0;

    int idx = 2;
    if (nargs >= 4 && !parsePositive(argv[idx++], &baud))
    {
        std::fputs(kUsage, stderr);
        return 2;
    }
    if (nargs == 5 && !parsePositive(argv[idx++], &unit))
    {
        std::fputs(kUsage, stderr);
        return 2;
    }
    if (!parsePositive(argv[idx++], &addr) || !parsePositive(argv[idx], &qty))
    {
        std::fputs(kUsage, stderr);
        return 2;
    }

    auto link_result = SerialPortLink::open(device, static_cast<int>(baud));
    if (!link_result)
    {
        std::fprintf(stderr, "open failed: %s\n", errorName(link_result.error()));
        return 1;
    }

    std::shared_ptr<ISerialLink> link = std::move(link_result.value());

    RtuClientConfig config;
    config.unit_id = static_cast<uint8_t>(unit);
    RtuClient client(link, config);

    auto result = client.readHoldingRegisters(static_cast<uint16_t>(addr), static_cast<uint16_t>(qty));
    if (!result)
    {
        std::fprintf(stderr, "read failed: %s\n", errorName(result.error()));
        return 1;
    }

    std::printf("addr=0x%04X qty=%u -> [", static_cast<unsigned>(addr), static_cast<unsigned>(qty));
    const auto &words = result.value();
    for (size_t i = 0; i < words.size(); ++i)
        std::printf("%s0x%04X", i ? " " : "", words[i]);
    std::printf("]\n");
    return 0;
}
