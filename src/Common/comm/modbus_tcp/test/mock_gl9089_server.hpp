#ifndef MODBUS_TCP_TEST_MOCK_GL9089_SERVER_HPP_
#define MODBUS_TCP_TEST_MOCK_GL9089_SERVER_HPP_

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cstdint>
#include <cstring>
#include <functional>
#include <thread>
#include <vector>

namespace comm::modbus_tcp::test
{

// 연결 1회를 핸들러 λ 로 서빙하는 최소 mock(테스트 픽스처). 루프백에 자동 포트로 listen 하며,
// 프레임 유틸(requestTid/recvRequest/buildFrame/sendAll)은 sim·타 패키지 테스트가 공유한다.
class MockGl9089Server
{
  public:
    using ConnHandler = std::function<void(int client_fd)>;

    MockGl9089Server()
    {
        listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        const int reuse = 1;
        ::setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = 0;
        ::bind(listen_fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
        socklen_t len = sizeof(addr);
        ::getsockname(listen_fd_, reinterpret_cast<sockaddr *>(&addr), &len);
        port_ = ntohs(addr.sin_port);
        ::listen(listen_fd_, 4);
    }

    ~MockGl9089Server()
    {
        const int fd = listen_fd_;
        listen_fd_ = -1;
        if (fd >= 0)
        {
            ::shutdown(fd, SHUT_RDWR);
            ::close(fd);
        }
        if (thread_.joinable())
        {
            thread_.join();
        }
    }

    MockGl9089Server(const MockGl9089Server &) = delete;
    MockGl9089Server &operator=(const MockGl9089Server &) = delete;

    uint16_t port() const
    {
        return port_;
    }

    // 다음 accept 되는 클라이언트 fd 의 SO_RCVTIMEO(ms) 예약 — 핸들러가 recv 에서 영구 대기하지 않게.
    void setRecvTimeout(std::chrono::milliseconds timeout)
    {
        recv_timeout_ = timeout;
    }

    // accept 1회 후 handler 를 별도 스레드에서 실행. 종료 대기는 join()/소멸자가 보장.
    void serveOnce(ConnHandler handler)
    {
        if (thread_.joinable())
        {
            thread_.join();
        }
        thread_ = std::thread([this, handler]() {
            const int client_fd = ::accept(listen_fd_, nullptr, nullptr);
            if (client_fd >= 0)
            {
                timeval tv{};
                tv.tv_sec = static_cast<time_t>(recv_timeout_.count() / 1000);
                tv.tv_usec = static_cast<suseconds_t>((recv_timeout_.count() % 1000) * 1000);
                ::setsockopt(client_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
                handler(client_fd);
                ::close(client_fd);
            }
        });
    }

    void join()
    {
        if (thread_.joinable())
        {
            thread_.join();
        }
    }

  private:
    int listen_fd_ = -1;
    uint16_t port_ = 0;
    std::thread thread_;
    std::chrono::milliseconds recv_timeout_{2000};
};

inline uint16_t requestTid(const std::vector<uint8_t> &req)
{
    return static_cast<uint16_t>((static_cast<uint16_t>(req[0]) << 8) | req[1]);
}

inline std::vector<uint8_t> recvRequest(int fd)
{
    uint8_t buf[300];
    const ssize_t n = ::recv(fd, buf, sizeof(buf), 0);
    if (n <= 0)
    {
        return {};
    }
    return std::vector<uint8_t>(buf, buf + n);
}

// MBAP 응답 프레임 조립 — length 필드는 unit id(1B) + PDU 길이(빅엔디언).
inline std::vector<uint8_t> buildFrame(uint16_t tid, uint8_t unit_id, const std::vector<uint8_t> &pdu)
{
    std::vector<uint8_t> f;
    f.push_back(static_cast<uint8_t>(tid >> 8));
    f.push_back(static_cast<uint8_t>(tid & 0xFF));
    f.push_back(0x00);
    f.push_back(0x00);
    const uint16_t length = static_cast<uint16_t>(1 + pdu.size());
    f.push_back(static_cast<uint8_t>(length >> 8));
    f.push_back(static_cast<uint8_t>(length & 0xFF));
    f.push_back(unit_id);
    f.insert(f.end(), pdu.begin(), pdu.end());
    return f;
}

inline void sendAll(int fd, const std::vector<uint8_t> &data)
{
    size_t off = 0;
    while (off < data.size())
    {
        const ssize_t n = ::send(fd, data.data() + off, data.size() - off, 0);
        if (n <= 0)
        {
            return;
        }
        off += static_cast<size_t>(n);
    }
}

}

#endif
