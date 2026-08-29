// RtuClient — Modbus RTU 마스터. 버스에는 마스터가 하나뿐이라는 전제(ADR-005 D2, RS485 반이중) 하에
// 전 호출을 뮤텍스로 직렬화한다. 잠금 보유 중 link_ 의 blocking I/O(writeBytes/readBytes) 를 수행하는
// 것은 이 설계의 **의도된** 선택이다 — RS485 반이중 버스는 물리적으로 동시에 두 트랜잭션을 진행할 수
// 없으므로, 직렬화가 회피 대상이 아니라 정확성 요구사항 그 자체다(concurrency-coding.md §2 lock 범위
// 최소 원칙에 대한 의도적 예외 — 근거를 여기 명시).
#ifndef MODBUS_RTU_RTU_CLIENT_HPP_
#define MODBUS_RTU_RTU_CLIENT_HPP_

#include <cstdint>
#include <memory>
#include <mutex>
#include <vector>

#include "modbus_rtu/rtu_types.hpp"
#include "modbus_rtu/serial_link.hpp"

namespace comm::modbus_rtu
{

struct RtuClientConfig
{
    uint8_t unit_id = 1;
    Duration request_timeout{500};
    int retries = 2;
    Duration retry_gap{50};
};

// 최악의 경우 버스 락 점유 시간(최종 리뷰 I6): 실패 트랜잭션 1건이 버스(뮤텍스 mutex_)를 점유하는
// 최대 시간은 대략 (retries+1)×request_timeout + retries×retry_gap 이다 — 기본값
// (retries=2, request_timeout=500ms, retry_gap=50ms) 기준 3×500ms + 2×50ms = 1.6s. 그 사이 같은
// 버스의 다른 트랜잭션은 mutex_ 대기로 차단된다(D2 단일 마스터 직렬화의 대가 — rtu_client.cpp 상단
// 주석 참조).
class RtuClient
{
  public:
    RtuClient(std::shared_ptr<ISerialLink> link, RtuClientConfig config);

    Result<std::vector<uint16_t>> readHoldingRegisters(uint16_t addr, uint16_t qty);
    Result<void> writeSingleRegister(uint16_t addr, uint16_t value);
    Result<void> writeMultipleRegisters(uint16_t addr, const std::vector<uint16_t> &words);

    uint8_t lastExceptionCode() const;

  private:
    // 공통 트랜잭션 골격(정의는 rtu_client.cpp — 이 TU 안에서만 인스턴스화되는 사설 템플릿).
    // parse_fn(frame, exc_out) 은 수신 완료된 프레임을 해석해 Result<T> 로 변환한다.
    template <typename T, typename ParseFn> Result<T> transact(const std::vector<uint8_t> &request, uint8_t fc,
                                                                 uint16_t qty_for_len, ParseFn parse_fn);

    std::shared_ptr<ISerialLink> link_;
    RtuClientConfig config_;
    mutable std::mutex mutex_; // link_ I/O 전체 + last_exception_ 보호(버스 유일 마스터 직렬화)
    uint8_t last_exception_ = 0;
};

} // namespace comm::modbus_rtu

#endif // MODBUS_RTU_RTU_CLIENT_HPP_
