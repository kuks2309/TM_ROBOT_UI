#ifndef MODBUS_TCP_MBAP_CLIENT_HPP_
#define MODBUS_TCP_MBAP_CLIENT_HPP_

#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

#include "modbus_tcp/tcp_types.hpp"

namespace comm::modbus_tcp
{

// FC3 1회 최대 읽기 워드 수 — Modbus 규격 상한 125(0x7D). 초과 요청은 송신 없이 거부한다.
inline constexpr uint16_t kMaxReadQuantity = 125;

// Modbus TCP 표준 포트.
inline constexpr uint16_t kDefaultModbusPort = 502;

// 접속·타이밍 설정. 시간 값은 전부 ms(Duration = std::chrono::milliseconds).
// 연결 실패 시 재시도 간격은 backoff_initial 에서 시작해 2배씩 backoff_max 까지 커진다.
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

// Modbus TCP(MBAP) 동기 클라이언트 — FC3/FC6 전용 단일 마스터.
// 장치 레지스터 의미론(워치독 주소 등)은 이 계층에 두지 않는다 — 소비자 HAL 소유.
// 변이 호출(connect/read/write)은 단일 소유 스레드 전용, isLinkUp() 만 교차 스레드 관측 허용.
class MbapClient
{
  public:
    explicit MbapClient(MbapClientConfig config);
    ~MbapClient();

    MbapClient(const MbapClient &) = delete;
    MbapClient &operator=(const MbapClient &) = delete;
    MbapClient(MbapClient &&) = delete;
    MbapClient &operator=(MbapClient &&) = delete;

    // 논블로킹 connect + poll 로 connect_timeout 을 강제. 실패 시 지수 백오프 창 갱신.
    Result<void> connect();

    // 소켓 폐기 + 링크다운 + 수신 버퍼 클리어. 재호출 안전.
    void close();

    // 링크 상태 관측 — 유일한 교차 스레드 안전 API(atomic relaxed).
    bool isLinkUp() const
    {
        return link_up_.load(std::memory_order_relaxed);
    }

    // FC3. quantity 1~125 밖이면 송신 없이 kOutOfRange. 응답의 byte_count·길이 교차 검증.
    Result<std::vector<uint16_t>> readHoldingRegisters(uint16_t start_addr, uint16_t quantity);

    // FC6. 에코 프레임의 addr/value 일치 검증(GL-9089 의 후행 여분 바이트는 허용).
    // 예외응답(FC|0x80)은 TcpError 로 매핑해 반환.
    Result<void> writeSingleRegister(uint16_t addr, uint16_t value);

  private:
    // 링크 up 이면 통과, 백오프 창 안이면 kNotConnected(즉시 재시도 억제), 그 외 connect().
    Result<void> ensureConnected();
    Result<void> boundedConnect();
    void setLinkDown();

    // 요청 조립(MBAP+TID)·송신 후 TID/PID/UID 일치 프레임까지 수신(불일치 프레임은 폐기·재동기).
    Result<std::vector<uint8_t>> transact(uint8_t fc, const std::vector<uint8_t> &pdu_body);

    // rx_buffer_ 가 n 바이트 이상 될 때까지 수신. EINTR/EAGAIN 재시도, FIN(0B)은 링크다운.
    Result<void> recvAtLeast(size_t n, TimePoint deadline);

    // MBAP length 필드로 프레임 1개를 재조립해 버퍼에서 꺼낸다.
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
