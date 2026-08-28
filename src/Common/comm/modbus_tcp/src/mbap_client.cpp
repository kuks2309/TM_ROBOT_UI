// MbapClient 구현 — POSIX 소켓, FC3/FC6 (수정안 2026-07-23-modbus-fix-proposals.md §1 #4·#5·#6)
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

void putBE16(std::vector<uint8_t> &buf, uint16_t v)
{
    buf.push_back(static_cast<uint8_t>(v >> 8));
    buf.push_back(static_cast<uint8_t>(v & 0xFF));
}

uint16_t getBE16(const uint8_t *p)
{
    return static_cast<uint16_t>((static_cast<uint16_t>(p[0]) << 8) | static_cast<uint16_t>(p[1]));
}

// 예외코드→TcpError 매핑(수정안 #4(b)). 근거: UserManual §8.2.11(txt:1365-1398) 예외코드 표 +
// "GL-9089 response exception code 01, 02, 03, 04 and 06."(txt:1398 — GL-9089가 실제 방출하는 부분집합).
// types.hpp의 TcpError는 계약 커널 동결본(coding SOP §3 공개 API 변경 트리거 대상)이라 확장하지 않고
// 기존 8종 값 중 의미가 가장 가까운 항목에 사상한다(⚠ 1:1 전용 코드가 없어 일부 수렴):
//   01 Illegal Function      -> kProtocol   (요청 FC 자체가 거부됨 — FC3/FC6 고정 사용 중 발생 시 프로토콜 이상)
//   02 Illegal Data Address  -> kOutOfRange (요청 주소가 슬레이브 유효범위 밖)
//   03 Illegal Data Value    -> kOutOfRange (요청 데이터 값이 허용범위 밖 — 주소류와 동일 "범위" 계열로 수렴)
//   04 Slave Device Failure  -> kProtocol   (장치측 처리 실패 — 프로토콜/장치 계층 이상으로 간주)
//   06 Slave Device Busy     -> kBusy       (명칭 그대로 1:1 대응)
// GL-9089가 방출하지 않는 05/08/0A 등(txt:1398 부정합)은 방어적으로 kProtocol.
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

} // namespace

MbapClient::MbapClient(MbapClientConfig config) : config_(std::move(config))
{
    // SIGPIPE-GLOBAL: 프로세스 전역 signal(SIGPIPE, SIG_IGN)을 설정하지 않는다. send()가 MSG_NOSIGNAL을
    // 쓰므로 이 클래스의 쓰기 경로에는 SIGPIPE가 발생하지 않으며(국소 처리로 충분), 라이브러리 계층이
    // 프로세스 전역 시그널 처분을 덮어쓰면 호스트/타 라이브러리의 SIGPIPE 정책을 파괴한다(계약: hpp 참조).
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
    link_up_ = false; // close가 링크상태 동시 갱신(수정안 #5(d) — legacy SOCK-4 재발 방지)
    rx_buffer_.clear();
}

void MbapClient::setLinkDown()
{
    close();
}

Result<void> MbapClient::boundedConnect()
{
    close(); // 이전 fd가 있으면 먼저 정리(RAII) — 재연결 전 close(수정안 #5(b))

    const int fd = ::socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0)
    {
        return Result<void>::err(TcpError::kNotConnected);
    }

    // FCNTL-UNCHECKED(부수): F_GETFL/F_SETFL 반환값 검사 — 실패 시 O_NONBLOCK 미적용/플래그 오염을
    // 안고 진행하면 이후 connect/recv 동작을 오판하므로 즉시 close 후 kNotConnected.
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
    { // EINPROGRESS — poll()로 connect_timeout만큼만 유계 대기(블로킹 connect 금지, 수정안 #5(e))
        for (;;)
        { // SOCK-EINTR-CONNECT: poll이 EINTR(-1)이면 남은 deadline으로 재계산 후 재폴링(헛끊김 방지)
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
                    continue; // 시그널 인터럽트 — connect는 계속 진행 중, 남은 시간으로 재폴링
                }
                ::close(fd);
                return Result<void>::err(TcpError::kNotConnected);
            }
            if (pr == 0)
            {
                ::close(fd);
                return Result<void>::err(TcpError::kTimeout);
            }
            break; // POLLOUT — connect 완료 후보
        }
        int so_err = 0;
        socklen_t len = sizeof(so_err);
        // CONNECT-SOERR-UNCHECKED(부수): getsockopt 자체 실패 시 so_err는 갱신되지 않아 실패한 연결을
        // '성공'으로 오판할 수 있다 — getsockopt 성공 && so_err==0일 때만 연결 성공으로 인정.
        if (::getsockopt(fd, SOL_SOCKET, SO_ERROR, &so_err, &len) < 0 || so_err != 0)
        {
            ::close(fd);
            return Result<void>::err(TcpError::kNotConnected);
        }
    }

    if (::fcntl(fd, F_SETFL, orig_flags) < 0)
    { // blocking 모드 복귀 실패 검사(FCNTL-UNCHECKED)
        ::close(fd);
        return Result<void>::err(TcpError::kNotConnected);
    }

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
        current_backoff_ = Duration{0}; // 성공 시 백오프 초기화
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
        return Result<void>::err(TcpError::kNotConnected); // 백오프 유예 중 — 이번 호출은 재시도 생략
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
            // MBAP-1: 타임아웃 시 부분수신 바이트를 폐기한다 — 지속연결에서 잔여 바이트가 다음 transact의
            // 새 응답 앞에 이어붙어 프레임 desync를 일으키는 것을 원천 차단(락스텝 단일요청 전제).
            rx_buffer_.clear();
            return Result<void>::err(TcpError::kTimeout);
        }
        auto remaining = std::chrono::duration_cast<Duration>(deadline - now);
        if (remaining.count() < 1)
        {
            remaining = Duration{1}; // 0 타임아웃은 일부 OS에서 "무제한 대기"로 해석되므로 최소 1ms 보장
        }
        timeval tv{};
        tv.tv_sec = static_cast<time_t>(remaining.count() / 1000);
        tv.tv_usec = static_cast<suseconds_t>((remaining.count() % 1000) * 1000);
        ::setsockopt(fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

        const ssize_t k = ::recv(fd_, chunk, sizeof(chunk), 0);
        if (k == 0)
        { // 피어 FIN — 즉시 링크다운(수정안 #5(a))
            setLinkDown();
            return Result<void>::err(TcpError::kNotConnected);
        }
        if (k < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)
            {
                // SOCK-EINTR-RECV: EINTR(시그널 인터럽트)을 EAGAIN과 동일하게 continue — 시그널 한 번에
                // 정상 링크를 헛끊고 재연결 백오프에 빠지는 것을 방지. 바깥 루프에서 deadline 재확인.
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
    auto hr = recvAtLeast(7, deadline); // MBAP 헤더 7B 완독(수정안 #6(a))
    if (!hr)
    {
        return Result<std::vector<uint8_t>>::err(hr.error());
    }
    const uint16_t length = getBE16(&rx_buffer_[4]); // MBAP Length(txt:901,913) — UnitID+PDU 바이트수
    if (length == 0)
    {
        rx_buffer_.clear(); // 프로토콜상 최소 UnitID 1바이트는 있어야 함 — 재동기 위해 폐기
        return Result<std::vector<uint8_t>>::err(TcpError::kFrameShort);
    }
    const size_t total = 7 + static_cast<size_t>(length) - 1; // 헤더7 + (Length-1)의 나머지 PDU
    auto br = recvAtLeast(total, deadline);
    if (!br)
    {
        return Result<std::vector<uint8_t>>::err(br.error());
    }
    std::vector<uint8_t> frame(rx_buffer_.begin(), rx_buffer_.begin() + static_cast<long>(total));
    // 프레임 경계를 넘는 초과 수신분은 지우지 않고 rx_buffer_에 남겨 다음 호출에 보존(수정안 #6(a))
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
    putBE16(req, tid);    // Transaction Identifier
    putBE16(req, 0x0000); // Protocol Identifier=0(txt:897-899)
    // Length: UnitID(1)+FC(1)+body — 16bit 폭 그대로 계산(legacy LEN-1의 uint8 축소캐스팅 재발 방지, #6(c))
    putBE16(req, static_cast<uint16_t>(1 + 1 + pdu_body.size()));
    req.push_back(config_.unit_id);
    req.push_back(fc);
    req.insert(req.end(), pdu_body.begin(), pdu_body.end());

    const auto deadline = std::chrono::steady_clock::now() + config_.request_timeout;
    // 전량 송신 — SOCK-EINTR-SEND: send가 EINTR(시그널 인터럽트)이면 재시도(continue), 부분전송은
    // 남은 구간을 이어서 전송(SO_SNDTIMEO로 유계). MSG_NOSIGNAL로 SIGPIPE는 국소 처리(수정안 #5(c)).
    size_t off = 0;
    while (off < req.size())
    {
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

    // 수신 → 프레임검증(TID/PID/UID) → 예외검사 → 파싱 순서 고정(수정안 #4(c)).
    // TID/PID/UID 불일치 프레임은 폐기하고 같은 deadline 내에서 재동기(수정안 #6(b)).
    for (;;)
    {
        auto rr = recvFrame(deadline); // "수신"
        if (!rr)
        {
            return Result<std::vector<uint8_t>>::err(rr.error());
        }
        const std::vector<uint8_t> &frame = rr.value();

        // "프레임검증": TID/PID/UID 대조 — 불일치는 폐기 후 다음 프레임 대기(재동기)
        const uint16_t resp_tid = getBE16(&frame[0]);
        const uint16_t resp_pid = getBE16(&frame[2]);
        const uint8_t resp_uid = frame[6];
        if (resp_pid != 0x0000 || resp_uid != config_.unit_id || resp_tid != tid)
        {
            continue;
        }
        if (frame.size() < 8)
        {
            return Result<std::vector<uint8_t>>::err(TcpError::kFrameShort);
        }

        // "예외검사": resp[7] == (요청 FC | 0x80) — fc는 위에서 이미 조립에 쓴 지역 변수를 그대로 재사용
        // (별도 인자 전달 없음 — 수정안 #4(a) "인자 오전달 원천 차단").
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
        // "파싱"은 호출자(readHoldingRegisters/writeSingleRegister)가 담당 — 여기서는 검증된 프레임만 반환.
        return Result<std::vector<uint8_t>>::ok(frame);
    }
}

Result<std::vector<uint16_t>> MbapClient::readHoldingRegisters(uint16_t start_addr, uint16_t quantity)
{
    if (quantity == 0 || quantity > kMaxReadQuantity)
    {
        return Result<std::vector<uint16_t>>::err(TcpError::kOutOfRange); // 송신 없이 사전 거부(#6(c))
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
    // 응답 ByteCount와 실수신 길이 교차검증(수정안 #6(d)) — 둘 다 quantity*2와 일치해야 함
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
    // FC6 응답 길이 규약 — 매뉴얼 §8.2.6은 "echo of the request"(표준 12B, txt:1104-1110)만
    // 명시하나, 실 Crevis GL-9089 펌웨어는 16B를 반환한다: MBAP LEN=0x000A, addr/value 에코 뒤에
    // 매뉴얼 미문서화 4바이트(성공 시 0x00000000)가 덧붙는다. HIL 실측(2026-07-24, 원격 amr04, debt-016):
    //   REQ  00 01 00 00 00 06 01 06 10 20 00 C8
    //   RESP 00 01 00 00 00 0A 01 06 10 20 00 C8 00 00 00 00   ← 끝 4B 여분
    // legacy(tc_io modbus.h:542-557)는 FC6 응답을 검증하지 않아 이 불일치에 무영향이었다. 매뉴얼↔실기
    // 펌웨어 불일치이므로 길이는 에코 필드가 존재하는 하한(>=12)만 요구하고 후행 여분은 허용한다.
    // write 정합성은 addr/value 에코 대조로 유지 — 실패는 예외응답(FC|0x80)을 transact가 이미 처리하고,
    // 상위 configureWatchdog/writeBatch는 FC3 read-back으로 독립 재검증한다(방어 축소 없음).
    const std::vector<uint8_t> &frame = r.value();
    if (frame.size() < 12 || getBE16(&frame[8]) != addr || getBE16(&frame[10]) != value)
    {
        return Result<void>::err(TcpError::kProtocol);
    }
    return Result<void>::ok();
}

} // namespace comm::modbus_tcp
