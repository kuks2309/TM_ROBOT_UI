// Modbus RTU 프레이밍 — 순수 함수(무 I/O). 장치 지식 없음(ADR-005 D2).
// 프레임 형식 근거: Z-EFG-C35 Product Manual V20240120 p6-8 예제(검증 벡터 6종, 실기 실증).
#ifndef MODBUS_RTU_RTU_FRAME_HPP_
#define MODBUS_RTU_RTU_FRAME_HPP_

#include <cstddef>
#include <cstdint>
#include <vector>

#include "modbus_rtu/rtu_types.hpp"

namespace comm::modbus_rtu
{

inline constexpr uint16_t kMaxReadQuantity = 125;
inline constexpr uint16_t kMaxWriteQuantity = 123;
inline constexpr size_t kWriteAckLength = 8;
inline constexpr size_t kExceptionFrameLength = 5;

uint16_t crc16(const uint8_t *data, size_t len);
void appendCrc(std::vector<uint8_t> &frame);
bool checkCrc(const std::vector<uint8_t> &frame);

// 범위 밖 인자는 송신 없이 빈 vector (호출측이 kOutOfRange 로 매핑).
std::vector<uint8_t> buildReadHoldingRequest(uint8_t unit, uint16_t start_addr, uint16_t quantity);
std::vector<uint8_t> buildWriteSingleRequest(uint8_t unit, uint16_t addr, uint16_t value);
std::vector<uint8_t> buildWriteMultipleRequest(uint8_t unit, uint16_t start_addr, const std::vector<uint16_t> &words);

// 정상 응답 총 길이. 0x03: 5+2*qty, 0x06/0x10: 8, 미지원 fc: 0.
size_t expectedResponseLength(uint8_t fc, uint16_t quantity);

// exc_out 은 널 허용 — kException 일 때만 기록.
Result<std::vector<uint16_t>> parseReadHoldingResponse(const std::vector<uint8_t> &frame, uint8_t unit,
                                                       uint16_t expected_quantity, uint8_t *exc_out);
Result<void> parseWriteAck(const std::vector<uint8_t> &frame, uint8_t unit, uint8_t fc, uint16_t addr,
                           uint8_t *exc_out);

} // namespace comm::modbus_rtu

#endif // MODBUS_RTU_RTU_FRAME_HPP_
