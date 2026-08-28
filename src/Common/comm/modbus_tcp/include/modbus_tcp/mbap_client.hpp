#ifndef MODBUS_TCP_MBAP_CLIENT_HPP_
#define MODBUS_TCP_MBAP_CLIENT_HPP_

#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

#include "modbus_tcp/tcp_types.hpp"

namespace comm::modbus_tcp
{

inline constexpr uint16_t kMaxReadQuantity = 125;

inline constexpr uint16_t kDefaultModbusPort = 502;

struct MbapClientConfig
{
    std::string host;
    uint16_t port = kDefaultModbusPort;
    uint8_t unit_id = 1;
    Duration request_timeout{500};
    Duration connect_timeout{500};
    Duration backoff_initial{200};
    Duration backoff_max{5000};
};

class MbapClient
{
  public:
    explicit MbapClient(MbapClientConfig config);
    ~MbapClient();

    MbapClient(const MbapClient &) = delete;
    MbapClient &operator=(const MbapClient &) = delete;
    MbapClient(MbapClient &&) = delete;
    MbapClient &operator=(MbapClient &&) = delete;

    Result<void> connect();

    void close();

    bool isLinkUp() const
    {
        return link_up_.load(std::memory_order_relaxed);
    }

    Result<std::vector<uint16_t>> readHoldingRegisters(uint16_t start_addr, uint16_t quantity);

    Result<void> writeSingleRegister(uint16_t addr, uint16_t value);

  private:
    Result<void> ensureConnected();
    Result<void> boundedConnect();
    void setLinkDown();

    Result<std::vector<uint8_t>> transact(uint8_t fc, const std::vector<uint8_t> &pdu_body);

    Result<void> recvAtLeast(size_t n, TimePoint deadline);

    Result<std::vector<uint8_t>> recvFrame(TimePoint deadline);

    MbapClientConfig config_;
    int fd_ = -1;
    std::atomic<bool> link_up_{false};
    uint16_t next_tid_ = 1;
    Duration current_backoff_{0};
    TimePoint next_connect_attempt_{};
    std::vector<uint8_t> rx_buffer_;
};

}

#endif
