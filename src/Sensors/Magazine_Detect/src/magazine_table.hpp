#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace magazine_detect
{

// 버퍼 자리 수. 배열 크기의 단일 출처.
inline constexpr std::size_t kSlotCount = 6;

// 슬롯 → DI 비트 매핑과 판독 규약. 전부 config 소유다 — 기체·배선이 바뀌면 따라간다.
struct Config
{
  std::array<int, kSlotCount> di_bit{};
  bool detected_when_low = true;  // 원시 0 = 매거진 있음
  int debounce_ticks = 50;        // 값이 바뀐 상태로 연속 N 프레임이어야 확정
};

// 통과하면 nullopt, 아니면 사람이 읽는 사유.
std::optional<std::string> validate(const Config & cfg, std::size_t di_bit_count);

struct SlotState
{
  std::array<bool, kSlotCount> present{};  // 디바운스 확정값
  std::array<bool, kSlotCount> raw{};      // 디바운스 전 원시 판정
  std::array<int, kSlotCount> pending{};   // 확정값과 다른 상태가 이어진 프레임 수
  bool valid = false;                      // 마지막 갱신이 신선한가
};

// 자리 이름. 로그·진단 전용이며 기계 분기에 쓰지 않는다.
const char * slotName(std::size_t slot);

class MagazineTable
{
public:
  explicit MagazineTable(Config cfg);

  // 한 프레임 반영. io_di 가 매핑된 최대 비트보다 짧으면 false 이고 상태를 바꾸지 않는다.
  // 짧은 프레임의 빈 자리를 0 으로 읽으면 「전부 매거진 있음」이 되어 반대로 위험하다.
  bool update(const std::vector<int32_t> & io_di);

  // 입력이 끊겼음을 표시한다. present 는 마지막 확정값을 유지한다 —
  // 지우면 「전부 비었다」가 되어, 그것 역시 사실이 아니다.
  void markStale();

  const SlotState & state() const { return state_; }
  const Config & config() const { return cfg_; }

private:
  Config cfg_;
  SlotState state_;
};

}  // namespace magazine_detect
