#include "magazine_table.hpp"

#include <algorithm>

namespace magazine_detect
{

namespace
{
// 파일 스코프 constexpr 이어야 한다 — 지역 배열로 내리면 slotName 이 댕글링 포인터를 반환한다.
// 순서는 슬롯 번호와 같다(앞/뒤 교차 배선 — 도면 일련번호와 4자리가 어긋난다).
constexpr const char * kSlotNames[kSlotCount] = {
  "앞 왼", "뒤 왼", "앞 중", "뒤 중", "앞 오", "뒤 오"};
}

const char * slotName(std::size_t slot)
{
  return slot < kSlotCount ? kSlotNames[slot] : "?";
}

std::optional<std::string> validate(const Config & cfg, std::size_t di_bit_count)
{
  if (cfg.debounce_ticks < 1) {
    return std::string("debounce_ticks 는 1 이상이어야 한다 (받은 값 ") +
           std::to_string(cfg.debounce_ticks) + ")";
  }
  for (std::size_t i = 0; i < kSlotCount; ++i) {
    const int b = cfg.di_bit[i];
    if (b < 0 || static_cast<std::size_t>(b) >= di_bit_count) {
      return "슬롯 " + std::to_string(i) + " 의 di_bit 가 범위 밖이다 (" +
             std::to_string(b) + ", 허용 0.." + std::to_string(di_bit_count - 1) + ")";
    }
    for (std::size_t j = i + 1; j < kSlotCount; ++j) {
      if (cfg.di_bit[j] == b) {
        return "슬롯 " + std::to_string(i) + " 과 " + std::to_string(j) +
               " 의 di_bit 가 같다 (" + std::to_string(b) + ")";
      }
    }
  }
  return std::nullopt;
}

MagazineTable::MagazineTable(Config cfg)
: cfg_(cfg)
{
}

bool MagazineTable::update(const std::vector<int32_t> & io_di)
{
  const int max_bit = *std::max_element(cfg_.di_bit.begin(), cfg_.di_bit.end());
  if (max_bit < 0 || io_di.size() <= static_cast<std::size_t>(max_bit)) {
    return false;
  }

  for (std::size_t i = 0; i < kSlotCount; ++i) {
    const bool level = io_di[static_cast<std::size_t>(cfg_.di_bit[i])] != 0;
    const bool raw = cfg_.detected_when_low ? !level : level;
    state_.raw[i] = raw;

    if (raw == state_.present[i]) {
      state_.pending[i] = 0;
      continue;
    }
    if (++state_.pending[i] >= cfg_.debounce_ticks) {
      state_.present[i] = raw;
      state_.pending[i] = 0;
    }
  }
  state_.valid = true;
  return true;
}

void MagazineTable::markStale()
{
  state_.valid = false;
  state_.pending.fill(0);
}

}
