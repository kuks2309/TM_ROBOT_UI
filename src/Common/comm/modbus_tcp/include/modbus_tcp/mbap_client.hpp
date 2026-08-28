// MbapClient — Modbus TCP(MBAP) 클라이언트, Crevis GL-9089 대상 (순수, ROS-free — ⟦CI:modbus-tcp-ros-free⟧)
// 승격 이관(ADR-000, 2026-07-31): pio_hal/modbus/mbap_client.hpp 에서 비트 동일 이관 —
// 변경은 namespace(comm::modbus_tcp)·타입 자립(tcp_types.hpp)·link_up_ atomic(debt-014 ①)뿐.
// 구현 범위: FC3(Read Holding Registers)·FC6(Write Single Register)만 — 수정안(review) #4(d) 확정 범위,
// 근거: Sensors/PIO/docs/reviews/2026-07-23-modbus-fix-proposals.md §1 표 #4.
//
// 동시성 규율(수정안 #5 + debt-014 ① 계약 명시):
//  - 본 클래스는 스스로 스레드를 만들지 않는다. connect/close/read/write 등 **모든 변이 호출은
//    단일 소유 스레드**가 수행해야 한다(동기 호출형 — 호출자가 주기 호출).
//  - 예외적으로 `isLinkUp()` 만 타 스레드 관측을 허용한다 — link_up_ 이 std::atomic 이므로
//    data race 없이 링크 상태를 읽을 수 있다(관측 전용 — 이 플래그로 다른 멤버 접근을 동기화하지
//    말 것). ⟦CI:modbus-tcp-tsan⟧ 게이트(checks/modbus-tcp-tsan.sh)가 이 계약을 TSan 으로 검증한다.
//  - 수정안 #5(e)(f)(g)의 전용 통신 스레드 생성·stop-token·join 은 **조립층(소유 스레드를 만드는
//    쪽, 예: pio_ros M4·rio_ros) 책임**이다 — 본 클래스 계약 밖(debt-014 ① 명시).
//  - 모든 블로킹 지점(connect/send/recv)은 소켓 타임아웃으로 유계.
//
// SIGPIPE 계약(SIGPIPE-GLOBAL): SIGPIPE는 send()의 MSG_NOSIGNAL로만 국소 처리한다. 본 클래스는
// 프로세스 전역 시그널 처분(signal/sigaction)을 변경하지 않는다 — 호스트 프로세스나 타 라이브러리의
// SIGPIPE 정책을 라이브러리 계층이 임의로 덮어쓰지 않는다는 계약이다.
//
// 인용: Crevis GL-9089 UserManual rev1.02 (references/IO/crevis/GL-9089/Crevis_GL-9089_UserManual_rev1.02.txt)
//   §8.1.2 MBAP Header (txt:889-916) · §8.2.3 FC3 (txt:1000-1021) · §8.2.6 FC6 (txt:1091-1111)
//   §8.2.11 Error Response (txt:1356-1398) · §8.3.3 0x1043 포트고정 (txt:1490)
#ifndef MODBUS_TCP_MBAP_CLIENT_HPP_
#define MODBUS_TCP_MBAP_CLIENT_HPP_

#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

#include "modbus_tcp/tcp_types.hpp"

namespace comm::modbus_tcp
{

// FC3 요청 워드수 상한. 근거: UserManual §8.2.4(FC4 Read Input Registers, txt:1032,1036) "read from 1 to
// approx. 125 contiguous input registers" + §8.2(txt:941) "Refer to MODBUS APPLICATION PROTOCOL
// SPECIFICATION V1.1a"(표준 공통 상한 125word). §8.2.3(FC3) 절 자체는 예제표가 FC2 예제와 동일하게
// 오기재된 문서 결함(검토보고서 DOC-1, 2026-07-22-crevis-conformance-review.md)이라 FC3 고유 수량 상한을
// 직접 명시하지 않는다 — ⚠ FC3 전용 상한 수치는 매뉴얼에 직접 명시되지 않아 FC4/표준 수렴값을 인용 채택
// (실기 재확인 권장 — 수정안 #6(c)와 동일 결론).
inline constexpr uint16_t kMaxReadQuantity = 125;

// GL-9089 고정 포트. 근거: UserManual §8.3.3(0x1043, txt:1490) "ModBus/TCP port, fixed 502"
inline constexpr uint16_t kDefaultModbusPort = 502;

struct MbapClientConfig
{
    std::string host;
    uint16_t port = kDefaultModbusPort;
    uint8_t unit_id = 1;           // MBAP Unit Identifier — 응답과 대조(§8.1.2 txt:903-907)
    Duration request_timeout{500}; // 요청 1건 전체 예산 200~1000ms(수정안 #5(e)) — 설정 인자
    Duration connect_timeout{500}; // connect() 자체의 유계 대기(non-blocking + poll)
    Duration backoff_initial{200}; // 재연결 지수 백오프 초기값(수정안 #5(b))
    Duration backoff_max{5000};    // 백오프 상한
};

// MbapClient — 소켓 1개를 RAII로 소유하는 동기 Modbus TCP 마스터.
// 복사/이동 모두 금지(소켓 fd 이중 소유 방지) — 호출자가 값이 아닌 단일 인스턴스로 소유해야 한다.
class MbapClient
{
  public:
    explicit MbapClient(MbapClientConfig config);
    ~MbapClient(); // RAII: 미close 소켓 정리(수정안 #5(b)) — "stop" 개념은 소멸자 close뿐

    MbapClient(const MbapClient &) = delete;
    MbapClient &operator=(const MbapClient &) = delete;
    MbapClient(MbapClient &&) = delete;
    MbapClient &operator=(MbapClient &&) = delete;

    // 명시적 연결 시도. 실패 시 지수 백오프 스케줄을 갱신한다(다음 ensureConnected 유예).
    // connect_timeout으로 유계(non-blocking connect + poll) — 절대 무한정 블로킹하지 않는다.
    Result<void> connect();

    // 소켓 close + 링크상태 동시 갱신(수정안 #5(d) — const 아님, legacy SOCK-4 재발 방지).
    void close();

    // 타 스레드 관측 허용(유일한 교차 스레드 API — 상단 동시성 규율 참조). 관측 전용 플래그이므로
    // relaxed 로 충분하다 — 이 값으로 다른 멤버 접근을 동기화하지 않는다(acquire 의미 불필요).
    bool isLinkUp() const
    {
        return link_up_.load(std::memory_order_relaxed);
    }

    // FC3 Read Holding Registers. quantity==0 이거나 kMaxReadQuantity 초과면 송신 없이 kOutOfRange.
    // 링크가 끊겨 있으면 백오프 일정에 따라 재연결을 먼저 시도(ensureConnected)한 뒤 진행한다.
    Result<std::vector<uint16_t>> readHoldingRegisters(uint16_t start_addr, uint16_t quantity);

    // FC6 Write Single Register. 정상 응답은 요청 그대로의 에코(주소·값) — 불일치 시 kProtocol.
    Result<void> writeSingleRegister(uint16_t addr, uint16_t value);

  private:
    Result<void> ensureConnected();
    Result<void> boundedConnect(); // 실제 소켓 connect (non-blocking + poll로 유계)
    void setLinkDown();            // recv==0(FIN)/소켓 오류 공통 처리 — fd close + link_up_=false

    // 요청 1건 처리 공통 경로. fc는 이 함수의 지역 변수로 요청 PDU 조립에 쓰이고, 같은 지역 변수를
    // 그대로 예외/정상 판정에 재사용한다 — 별도 인자로 중복 전달하지 않음으로써 legacy modbus.h:554
    // (WRITE_COIL을 예외검사에 오전달) 유형의 결함을 시그니처 수준에서 원천 차단한다(수정안 #4(a)).
    Result<std::vector<uint8_t>> transact(uint8_t fc, const std::vector<uint8_t> &pdu_body);

    // rx_buffer_에 최소 n바이트가 쌓일 때까지 recv() 반복(부분 수신 재조립, 수정안 #6(a)).
    // deadline 초과 시 kTimeout, recv()==0(FIN) 시 즉시 링크다운 후 kNotConnected.
    Result<void> recvAtLeast(size_t n, TimePoint deadline);

    // MBAP 7B 완독 → Length 필드로 잔여 PDU 바이트수 산출 → 재조립. 프레임 경계를 넘는 초과 수신분은
    // rx_buffer_에 남겨 다음 호출에 보존한다("초과 수신 보존", 수정안 #6(a)).
    Result<std::vector<uint8_t>> recvFrame(TimePoint deadline);

    MbapClientConfig config_;
    int fd_ = -1;
    // debt-014 ①: 교차 스레드 관측(isLinkUp) 허용을 위한 atomic — 그 외 멤버는 여전히 단일 소유 스레드 전용.
    std::atomic<bool> link_up_{false};
    uint16_t next_tid_ = 1;
    Duration current_backoff_{0};
    TimePoint next_connect_attempt_{};
    std::vector<uint8_t> rx_buffer_;
};

} // namespace comm::modbus_tcp

#endif // MODBUS_TCP_MBAP_CLIENT_HPP_
