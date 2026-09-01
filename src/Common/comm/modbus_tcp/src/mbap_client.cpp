#include "modbus_tcp/mbap_client.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <utility>

namespace comm::modbus_tcp
{

namespace
{

// Modbus 는 와이어에서 빅엔디언 — 워드 직렬화/역직렬화는 전부 이 두 헬퍼를 거친다.
void putBE16(std::vector<uint8_t> &buf, uint16_t v)
{
    buf.push_back(static_cast<uint8_t>(v >> 8));
    buf.push_back(static_cast<uint8_t>(v & 0xFF));
}

uint16_t getBE16(const uint8_t *p)
{
    return static_cast<uint16_t>((static_cast<uint16_t>(p[0]) << 8) | static_cast<uint16_t>(p[1]));
}

// Modbus 예외코드 → TcpError. 01 Illegal Function/04 Device Failure 는 kProtocol,
// 02 Illegal Address/03 Illegal Value 는 kOutOfRange, 06 Busy 는 kBusy. 미지 코드는 kProtocol.
TcpError mapExceptionCode(uint8_t code)
{
    switch (code)
    {
    case 0x01:
        return TcpError::kProtocol;
    case 0x02:
        return TcpError::kOutOfRange;
    case 0x03:
        return TcpError::kOutOfRange;
    case 0x04:
        return TcpError::kProtocol;
    case 0x06:
        return TcpError::kBusy;
    default:
        return TcpError::kProtocol;
    }
}

}

MbapClient::MbapClient(MbapClientConfig config) : config_(std::move(config))
{
    rx_buffer_.reserve(256);
}

MbapClient::~MbapClient()
{
    close();
}

void MbapClient::close()
{
    if (fd_ >= 0)
    {
        ::close(fd_);
        fd_ = -1;
    }
    link_up_ = false;
    rx_buffer_.clear();
}

void MbapClient::setLinkDown()
{
    close();
}

Result<void> MbapClient::boundedConnect()
{
    close();

    // 블로킹 connect 는 OS 기본 타임아웃(수십 초)까지 걸릴 수 있어,
    // 논블로킹 + poll(POLLOUT) + SO_ERROR 검사로 connect_timeout 을 직접 강제한다.
    const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0)
    {
        return Result<void>::err(TcpError::kNotConnected);
    }

    const int orig_flags = ::fcntl(fd, F_GETFL, 0);
    if (orig_flags < 0)
    {
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }
    if (::fcntl(fd, F_SETFL, orig_flags | O_NONBLOCK) < 0)
    {
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(config_.port);
    if (::inet_pton(AF_INET, config_.host.c_str(), &addr.sin_addr) != 1)
    {
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }

    const auto connect_deadline = std::chrono::steady_clock::now() + config_.connect_timeout;
    const int rc = ::connect(fd, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
    if (rc < 0 && errno != EINPROGRESS)
    {
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }
    if (rc < 0)
    {
        for (;;)
        {
            const auto now = std::chrono::steady_clock::now();
            if (now >= connect_deadline)
            {
                ::close(fd);
                return Result<void>::err(TcpError::kTimeout);
            }
            const auto remain = std::chrono::duration_cast<Duration>(connect_deadline - now);
            const int timeout_ms = static_cast<int>(std::max<int64_t>(remain.count(), 1));
            pollfd pfd{fd, POLLOUT, 0};
            const int pr = ::poll(&pfd, 1, timeout_ms);
            if (pr < 0)
            {
                if (errno == EINTR)
                {
                    continue;
                }
                ::close(fd);
                return Result<void>::err(TcpError::kNotConnected);
            }
            if (pr == 0)
            {
                ::close(fd);
                return Result<void>::err(TcpError::kTimeout);
            }
            break;
        }
        int so_err = 0;
        socklen_t len = sizeof(so_err);
        if (::getsockopt(fd, SOL_SOCKET, SO_ERROR, &so_err, &len) < 0 || so_err != 0)
        {
            ::close(fd);
            return Result<void>::err(TcpError::kNotConnected);
        }
    }

    if (::fcntl(fd, F_SETFL, orig_flags) < 0)
    {
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }

    // 개별 recv/send 가 무한 블로킹하지 않게 기본 상한을 건다.
    // 수신 데드라인은 recvAtLeast 가 남은 시간으로 매 회 다시 조정한다.
    timeval tv{};
    const auto ms = config_.request_timeout.count();
    tv.tv_sec = static_cast<time_t>(ms / 1000);
    tv.tv_usec = static_cast<suseconds_t>((ms % 1000) * 1000);
    ::setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    ::setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    fd_ = fd;
    link_up_ = true;
    rx_buffer_.clear();
    return Result<void>::ok();
}

Result<void> MbapClient::connect()
{
    auto r = boundedConnect();
    if (r)
    {
        current_backoff_ = Duration{0};
    }
    else
    {
        current_backoff_ = current_backoff_.count() == 0 ? config_.backoff_initial
                                                         : std::min(current_backoff_ * 2, config_.backoff_max);
        next_connect_attempt_ = std::chrono::steady_clock::now() + current_backoff_;
    }
    return r;
}

Result<void> MbapClient::ensureConnected()
{
    if (link_up_)
    {
        return Result<void>::ok();
    }
    if (std::chrono::steady_clock::now() < next_connect_attempt_)
    {
        return Result<void>::err(TcpError::kNotConnected);
    }
    return connect();
}

Result<void> MbapClient::recvAtLeast(size_t n, TimePoint deadline)
{
    uint8_t chunk[512];
    while (rx_buffer_.size() < n)
    {
        const auto now = std::chrono::steady_clock::now();
        if (now >= deadline)
        {
            // 부분 수신분을 남기면 다음 트랜잭션이 낡은 프레임 조각과 어긋난다 — 비워서 재동기.
            rx_buffer_.clear();
            return Result<void>::err(TcpError::kTimeout);
        }
        auto remaining = std::chrono::duration_cast<Duration>(deadline - now);
        if (remaining.count() < 1)
        {
            remaining = Duration{1};
        }
        timeval tv{};
        tv.tv_sec = static_cast<time_t>(remaining.count() / 1000);
        tv.tv_usec = static_cast<suseconds_t>((remaining.count() % 1000) * 1000);
        ::setsockopt(fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

        const ssize_t k = ::recv(fd_, chunk, sizeof(chunk), 0);
        if (k == 0)
        {
            // 0 바이트 = 상대 FIN — 링크 폐기(다음 호출에서 백오프 후 재연결).
            setLinkDown();
            return Result<void>::err(TcpError::kNotConnected);
        }
        if (k < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
            {
                continue;
            }
            setLinkDown();
            return Result<void>::err(TcpError::kNotConnected);
        }
        rx_buffer_.insert(rx_buffer_.end(), chunk, chunk + k);
    }
    return Result<void>::ok();
}

Result<std::vector<uint8_t>> MbapClient::recvFrame(TimePoint deadline)
{
    auto hr = recvAtLeast(7, deadline);
    if (!hr)
    {
        return Result<std::vector<uint8_t>>::err(hr.error());
    }
    // MBAP length 필드(오프셋 4~5)는 unit id 를 포함한 이후 바이트 수 —
    // 전체 프레임 = 헤더 6B + length. unit id 가 헤더 7B 에 이미 포함돼 있어 -1.
    const uint16_t length = getBE16(&rx_buffer_[4]);
    if (length == 0)
    {
        rx_buffer_.clear();
        return Result<std::vector<uint8_t>>::err(TcpError::kFrameShort);
    }
    const size_t total = 7 + static_cast<size_t>(length) - 1;
    auto br = recvAtLeast(total, deadline);
    if (!br)
    {
        return Result<std::vector<uint8_t>>::err(br.error());
    }
    std::vector<uint8_t> frame(rx_buffer_.begin(), rx_buffer_.begin() + static_cast<long>(total));
    rx_buffer_.erase(rx_buffer_.begin(), rx_buffer_.begin() + static_cast<long>(total));
    return Result<std::vector<uint8_t>>::ok(std::move(frame));
}

Result<std::vector<uint8_t>> MbapClient::transact(uint8_t fc, const std::vector<uint8_t> &pdu_body)
{
    auto conn = ensureConnected();
    if (!conn)
    {
        return Result<std::vector<uint8_t>>::err(conn.error());
    }

    const uint16_t tid = next_tid_++;
    std::vector<uint8_t> req;
    req.reserve(7 + 1 + pdu_body.size());
    putBE16(req, tid);
    putBE16(req, 0x0000);
    putBE16(req, static_cast<uint16_t>(1 + 1 + pdu_body.size()));
    req.push_back(config_.unit_id);
    req.push_back(fc);
    req.insert(req.end(), pdu_body.begin(), pdu_body.end());

    const auto deadline = std::chrono::steady_clock::now() + config_.request_timeout;
    size_t off = 0;
    while (off < req.size())
    {
        // MSG_NOSIGNAL: 상대가 끊은 소켓에 써도 SIGPIPE 로 프로세스가 죽지 않게(EPIPE 로 받는다).
        const ssize_t sent = ::send(fd_, req.data() + off, req.size() - off, MSG_NOSIGNAL);
        if (sent < 0)
        {
            if (errno == EINTR)
            {
                continue;
            }
            setLinkDown();
            return Result<std::vector<uint8_t>>::err(TcpError::kNotConnected);
        }
        off += static_cast<size_t>(sent);
    }

    for (;;)
    {
        auto rr = recvFrame(deadline);
        if (!rr)
        {
            return Result<std::vector<uint8_t>>::err(rr.error());
        }
        const std::vector<uint8_t> &frame = rr.value();

        const uint16_t resp_tid = getBE16(&frame[0]);
        const uint16_t resp_pid = getBE16(&frame[2]);
        const uint8_t resp_uid = frame[6];
        if (resp_pid != 0x0000 || resp_uid != config_.unit_id || resp_tid != tid)
        {
            // 낡은/무관 응답 잔재 — 폐기하고 같은 데드라인 안에서 내 TID 프레임을 재수신.
            continue;
        }
        if (frame.size() < 8)
        {
            return Result<std::vector<uint8_t>>::err(TcpError::kFrameShort);
        }

        if (frame[7] == static_cast<uint8_t>(fc | 0x80))
        {
            if (frame.size() < 9)
            {
                return Result<std::vector<uint8_t>>::err(TcpError::kFrameShort);
            }
            return Result<std::vector<uint8_t>>::err(mapExceptionCode(frame[8]));
        }
        if (frame[7] != fc)
        {
            return Result<std::vector<uint8_t>>::err(TcpError::kProtocol);
        }
        return Result<std::vector<uint8_t>>::ok(frame);
    }
}

Result<std::vector<uint16_t>> MbapClient::readHoldingRegisters(uint16_t start_addr, uint16_t quantity)
{
    if (quantity == 0 || quantity > kMaxReadQuantity)
    {
        return Result<std::vector<uint16_t>>::err(TcpError::kOutOfRange);
    }
    std::vector<uint8_t> body;
    putBE16(body, start_addr);
    putBE16(body, quantity);
    auto r = transact(0x03, body);
    if (!r)
    {
        return Result<std::vector<uint16_t>>::err(r.error());
    }
    const std::vector<uint8_t> &frame = r.value();
    if (frame.size() < 9)
    {
        return Result<std::vector<uint16_t>>::err(TcpError::kFrameShort);
    }
    const uint8_t byte_count = frame[8];
    const size_t expected_data_bytes = static_cast<size_t>(quantity) * 2;
    if (byte_count != expected_data_bytes || frame.size() != 9 + expected_data_bytes)
    {
        return Result<std::vector<uint16_t>>::err(TcpError::kFrameShort);
    }
    std::vector<uint16_t> out;
    out.reserve(quantity);
    for (uint16_t i = 0; i < quantity; ++i)
    {
        out.push_back(getBE16(&frame[9 + 2 * static_cast<size_t>(i)]));
    }
    return Result<std::vector<uint16_t>>::ok(std::move(out));
}

Result<void> MbapClient::writeSingleRegister(uint16_t addr, uint16_t value)
{
    std::vector<uint8_t> body;
    putBE16(body, addr);
    putBE16(body, value);
    auto r = transact(0x06, body);
    if (!r)
    {
        return Result<void>::err(r.error());
    }
    const std::vector<uint8_t> &frame = r.value();
    // 정규 FC6 에코는 12B. GL-9089 는 후행 여분 바이트를 붙여 오므로(HIL 실측)
    // 길이 초과는 허용하고 addr/value 에코 일치만 대조한다.
    if (frame.size() < 12 || getBE16(&frame[8]) != addr || getBE16(&frame[10]) != value)
    {
        return Result<void>::err(TcpError::kProtocol);
    }
    return Result<void>::ok();
}

}
