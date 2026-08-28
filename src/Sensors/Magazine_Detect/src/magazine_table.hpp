#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace magazine_detect
{

// 버퍼 매거진 자리 수 — 모든 배열 크기의 단일 출처.
inline constexpr std::size_t kSlotCount = 6;

// 슬롯→DI 비트 매핑과 판독 정책. di_bit 는 슬롯 순서대로의 DI 비트 번호(배선상 앞/뒤 교차),
// detected_when_low=true 면 원시 0(LOW)을 적재로 읽는다(센서 negative-true 극성).
// debounce_ticks: 확정까지 필요한 연속 일치 프레임 수 — 1틱 = io_resp 1프레임(발행 주기 20ms).
struct Config
{
  std::array<int, kSlotCount> di_bit{};
  bool detected_when_low = true;
  int debounce_ticks = 50;
};

// 설정 검증 — debounce_ticks>=1·비트 범위·중복 검사. 통과 시 nullopt, 실패 시 사유 문자열.
// 잘못된 배선 매핑은 조용히 틀리므로 기동 시점에 걸러내는 용도.
std::optional<std::string> validate(const Config & cfg, std::size_t di_bit_count);

// 슬롯 판독 상태. present 는 디바운스 확정값, raw 는 매 프레임 즉시값,
// pending 은 확정값과 다른 원시값이 이어진 프레임 수, valid=false 는 입력 두절(stale).
struct SlotState
{
  std::array<bool, kSlotCount> present{};
  std::array<bool, kSlotCount> raw{};
  std::array<int, kSlotCount> pending{};
  bool valid = false;
};

// 자리 이름(범위 밖은 "?"). 로그·진단 전용 — 기계 분기에 쓰지 않는다.
const char * slotName(std::size_t slot);

// io_resp DI 프레임을 슬롯 재고로 바꾸는 판독 코어(ROS 무관).
// 생성자는 검증하지 않는다 — 호출자가 validate 로 먼저 거른다.
class MagazineTable
{
public:
  explicit MagazineTable(Config cfg);

  // 한 프레임 반영 + 디바운스. io_di 가 매핑 최대 비트보다 짧으면 false·상태 불변
  // — 짧은 프레임을 0 으로 읽으면 LOW=적재 극성에서 「전부 있음」이 되기 때문.
  bool update(const std::vector<int32_t> & io_di);

  // 입력 두절 표시. valid 만 내리고 present 확정값은 보존한다 — 지우면 「전부 비었다」가 된다.
  void markStale();

  const SlotState & state() const { return state_; }
  const Config & config() const { return cfg_; }

private:
  Config cfg_;
  SlotState state_;
};

}
