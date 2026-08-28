#include <gtest/gtest.h>

#include <vector>

#include "magazine_table.hpp"

using magazine_detect::Config;
using magazine_detect::MagazineTable;
using magazine_detect::kSlotCount;
using magazine_detect::validate;

namespace
{

// 4호기 실측 매핑. 앞/뒤 교차라 도면 배선 순서와 다르다.
Config makeConfig(int debounce = 1)
{
  Config c;
  c.di_bit = {26, 29, 27, 30, 28, 31};
  c.detected_when_low = true;
  c.debounce_ticks = debounce;
  return c;
}

// 전부 비어 있는(원시 1) 80비트 프레임.
std::vector<int32_t> emptyFrame()
{
  return std::vector<int32_t>(80, 1);
}

}  // namespace

TEST(Validate, 정상설정통과)
{
  EXPECT_FALSE(validate(makeConfig(), 80).has_value());
}

TEST(Validate, 비트범위밖거부)
{
  Config c = makeConfig();
  c.di_bit[3] = 80;  // 0..79 밖
  EXPECT_TRUE(validate(c, 80).has_value());
}

TEST(Validate, 중복비트거부)
{
  // 중복을 통과시키면 두 자리가 같은 센서를 보고 한 자리가 영영 안 바뀐다.
  Config c = makeConfig();
  c.di_bit[4] = c.di_bit[0];
  EXPECT_TRUE(validate(c, 80).has_value());
}

TEST(Validate, 디바운스0거부)
{
  Config c = makeConfig(0);
  EXPECT_TRUE(validate(c, 80).has_value());
}

TEST(Update, 극성_원시0이적재)
{
  MagazineTable t(makeConfig(1));
  auto f = emptyFrame();
  f[29] = 0;  // 슬롯 1 = 뒤 왼
  ASSERT_TRUE(t.update(f));
  EXPECT_TRUE(t.state().present[1]);
  for (std::size_t i = 0; i < kSlotCount; ++i) {
    if (i != 1) {EXPECT_FALSE(t.state().present[i]) << "슬롯 " << i;}
  }
}

TEST(Update, 슬롯매핑이앞뒤교차)
{
  // 비트 27 은 «앞 중» = 슬롯 2 다. 도면 배선 순서로 읽으면 슬롯 1 이 되어 틀린다.
  MagazineTable t(makeConfig(1));
  auto f = emptyFrame();
  f[27] = 0;
  ASSERT_TRUE(t.update(f));
  EXPECT_TRUE(t.state().present[2]);
  EXPECT_FALSE(t.state().present[1]);
}

TEST(Update, 짧은프레임은상태를바꾸지않는다)
{
  MagazineTable t(makeConfig(1));
  auto f = emptyFrame();
  f[31] = 0;
  ASSERT_TRUE(t.update(f));
  ASSERT_TRUE(t.state().present[5]);

  std::vector<int32_t> shortFrame(20, 0);  // 매핑 최대 비트(31)를 못 담는다
  EXPECT_FALSE(t.update(shortFrame));
  EXPECT_TRUE(t.state().present[5]) << "짧은 프레임이 상태를 덮었다";
}

TEST(Debounce, 도달전에는확정되지않는다)
{
  MagazineTable t(makeConfig(3));
  auto f = emptyFrame();
  f[26] = 0;
  t.update(f);
  EXPECT_FALSE(t.state().present[0]) << "1 프레임 만에 확정됐다";
  t.update(f);
  EXPECT_FALSE(t.state().present[0]);
  t.update(f);
  EXPECT_TRUE(t.state().present[0]) << "3 프레임에도 확정되지 않았다";
}

TEST(Debounce, 중간에되돌아오면누적이초기화된다)
{
  MagazineTable t(makeConfig(3));
  auto on = emptyFrame(); on[26] = 0;
  auto off = emptyFrame();
  t.update(on);
  t.update(on);
  t.update(off);   // 채터링 — 누적이 0 으로
  t.update(on);
  t.update(on);
  EXPECT_FALSE(t.state().present[0]) << "채터링인데 확정됐다";
}

TEST(Update, raw는디바운스와무관하게즉시반영)
{
  MagazineTable t(makeConfig(50));
  auto f = emptyFrame();
  f[30] = 0;
  ASSERT_TRUE(t.update(f));
  EXPECT_TRUE(t.state().raw[3]);
  EXPECT_FALSE(t.state().present[3]);
}

TEST(Stale, 확정값을지우지않는다)
{
  // stale 에 present 를 지우면 「전부 비었다」가 되어 그것도 사실이 아니다.
  MagazineTable t(makeConfig(1));
  auto f = emptyFrame();
  f[29] = 0;
  ASSERT_TRUE(t.update(f));
  ASSERT_TRUE(t.state().valid);

  t.markStale();
  EXPECT_FALSE(t.state().valid);
  EXPECT_TRUE(t.state().present[1]) << "stale 이 마지막 확정값을 지웠다";
}

TEST(Stale, 갱신되면다시유효해진다)
{
  MagazineTable t(makeConfig(1));
  t.markStale();
  ASSERT_FALSE(t.state().valid);
  ASSERT_TRUE(t.update(emptyFrame()));
  EXPECT_TRUE(t.state().valid);
}

TEST(Update, 극성반전설정)
{
  Config c = makeConfig(1);
  c.detected_when_low = false;
  MagazineTable t(c);
  auto f = std::vector<int32_t>(80, 0);
  f[26] = 1;
  ASSERT_TRUE(t.update(f));
  EXPECT_TRUE(t.state().present[0]);
}
