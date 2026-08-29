// zefg_registers.hpp — HITBOT Z-EFG-C35 Modbus RTU 레지스터 계약 (전 항목 인용, ADR-005 단계④-1).
// 1차 source: Z-EFG-C35 Product Manual V20240120 (references/hitbot/z-efg-c35/).
// 영점 매핑은 HIL 실측이 정본(근거: gripper HIL H0 실측 기록, src/Actuators/gripper/docs/hil/) —
// 매뉴얼 p6 예제와 방향이 반대이므로 아래 주석에 명시한다.
#ifndef HITBOT_ZEFG_ZEFG_REGISTERS_HPP_
#define HITBOT_ZEFG_ZEFG_REGISTERS_HPP_

#include <array>
#include <cstdint>

namespace gripper::hitbot
{

inline constexpr uint16_t kRegInitCommand = 0x0000;    // W int: 1=초기화 [p5]
inline constexpr uint16_t kRegTargetPosition = 0x0002; // W float mm 0~35 [p5]
inline constexpr uint16_t kRegTargetSpeed = 0x0004;    // W float mm/s 1~100 [p5]
inline constexpr uint16_t kRegTargetCurrent = 0x0006;  // W float A 0.1~0.5 [p5]
inline constexpr uint16_t kRegInitStatus = 0x0040;     // R int: 0 미초기화 / 5 완료 / 기타 진행중 [p5]
inline constexpr uint16_t kRegClampStatus = 0x0041;    // R int: 0 InPlace/1 Moving/2 Clamping/3 Dropping [p5]
inline constexpr uint16_t kRegPositionFb = 0x0042;     // R float mm [p5]
inline constexpr uint16_t kRegSpeedFb = 0x0044;        // R float mm/s [p5]
inline constexpr uint16_t kRegCurrentFb = 0x0046;      // R float A [p5]

inline constexpr float kPositionMin = 0.0F, kPositionMax = 35.0F; // [p2 스트로크]
inline constexpr float kSpeedMin = 1.0F, kSpeedMax = 100.0F;      // [p5]
inline constexpr float kCurrentMin = 0.1F, kCurrentMax = 0.5F;    // [p5]

// 영점 실측: 표시 0mm=실물 완전 열림 · 35mm=완전 닫힘 — 매뉴얼 p6 예제와 반대, 실측 정본
// (근거: gripper HIL H0 실측 기록).
enum class InitStatus : uint8_t
{
    kNotInitialized,
    kInitializing,
    kCompleted
};

enum class ClampStatus : uint8_t
{
    kInPlace = 0,
    kMoving = 1,
    kClamping = 2,
    kDropping = 3,
    kUnknown = 255
};

InitStatus decodeInitStatus(uint16_t raw);   // 0→Not, 5→Completed, 그 외→Initializing [p5]
ClampStatus decodeClampStatus(uint16_t raw); // 0..3 외→kUnknown

// IEEE754 단정도, 상위워드 우선(hi<<16|lo) — 레지스터 실측값 0x420C0000=35.0 로 워드 순서 확정.
float wordsToFloat(uint16_t hi, uint16_t lo);
std::array<uint16_t, 2> floatToWords(float value); // 역변환: {hi, lo}

} // namespace gripper::hitbot

#endif // HITBOT_ZEFG_ZEFG_REGISTERS_HPP_
