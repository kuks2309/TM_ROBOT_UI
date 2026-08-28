// mock_gl9089_server.hpp — 인프로세스 mock GL-9089 TCP 서버 (테스트 전용 픽스처)
// mbap_client_test.cpp · modbus_signal_port_test.cpp 공용. 127.0.0.1 임의 포트(OS 할당)로 listen하고,
// 백그라운드 스레드에서 accept 1회 + 테스트가 제공한 핸들러로 결함 주입(FIN/RST/부분전송/예외응답 등)을
// 수행한다. 운영 코드(MbapClient/ModbusSignalPort)는 스레드를 쓰지 않지만, 소켓 상대편을 흉내 내는 본
// 테스트 하니스는 std::thread 사용이 표준적이며 무해하다(테스트 프로세스 한정, 매 테스트에서 join).
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
        addr.sin_port = 0; // OS가 임의 포트 할당
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
            ::shutdown(fd, SHUT_RDWR); // accept() 중이던 스레드를 즉시 깨움
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

    // 수락한 client fd 의 recv 상한. 클라이언트가 핸들러 기대치보다 적게 보내도 recv 가 풀리도록 한다.
    void setRecvTimeout(std::chrono::milliseconds timeout)
    {
        recv_timeout_ = timeout;
    }

    // 백그라운드에서 accept 1회 + handler 실행. 이전 호출의 스레드가 남아있으면(핸들러가 이미 끝났다는
    // 전제 하에) 먼저 join한다 — 여러 접속 국면(예: 최초연결→끊김→재연결)을 순차 호출로 구성한다.
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

// 요청 프레임에서 MBAP Transaction Identifier(상위 2바이트, big-endian) 추출.
inline uint16_t requestTid(const std::vector<uint8_t> &req)
{
    return static_cast<uint16_t>((static_cast<uint16_t>(req[0]) << 8) | req[1]);
}

// 서버측에서 recv() — 요청 1건(최대 300B) 수신. 짧은 read는 그대로 반환(테스트 목적상 단순화 —
// 실제 요청은 FC3/FC6이라 항상 300B 미만 1개 패킷으로 도착).
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

// MBAP+PDU 프레임 조립(테스트 응답 생성용). pdu = FC + 나머지 바이트열.
inline std::vector<uint8_t> buildFrame(uint16_t tid, uint8_t unit_id, const std::vector<uint8_t> &pdu)
{
    std::vector<uint8_t> f;
    f.push_back(static_cast<uint8_t>(tid >> 8));
    f.push_back(static_cast<uint8_t>(tid & 0xFF));
    f.push_back(0x00);
    f.push_back(0x00); // Protocol Identifier = 0
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

} // namespace comm::modbus_tcp::test

#endif // MODBUS_TCP_TEST_MOCK_GL9089_SERVER_HPP_
