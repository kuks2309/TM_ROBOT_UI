// gripper_common 계약 검증 — 벤더 무관 공용 타입의 의미 불변식 (hal contract_check 관례 승계)
#include "gripper_common/magazine_port.hpp"
#include "gripper_common/types.hpp"
#include <cstdio>
#include <type_traits>

using namespace gripper::hal;

// IMagazineDetectPort 공개 표면 — 추상 인터페이스 + read/health 반환형 고정 (컴파일 타임 검증)
static_assert(std::is_abstract_v<IMagazineDetectPort>, "IMagazineDetectPort 는 추상 인터페이스여야 한다");
static_assert(std::is_same_v<decltype(std::declval<IMagazineDetectPort &>().read()), Result<MagazineSnapshot>>,
              "IMagazineDetectPort::read() 반환형은 Result<MagazineSnapshot> 이어야 한다");
static_assert(std::is_same_v<decltype(std::declval<const IMagazineDetectPort &>().health()), Health>,
              "IMagazineDetectPort::health() 반환형은 Health 여야 한다");

static int fails = 0;
#define CHECK(c)                                                                                                       \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(c))                                                                                                      \
        {                                                                                                              \
            std::printf("FAIL: %s (line %d)\n", #c, __LINE__);                                                         \
            ++fails;                                                                                                   \
        }                                                                                                              \
    } while (0)

int main()
{
    // Result<void> — ok/err 의미 + kNone 오류의 kProtocol 승격
    CHECK(Result<void>::ok().has_value());
    CHECK(Result<void>::ok().error() == HalError::kNone);
    CHECK(!Result<void>::err(HalError::kTimeout).has_value());
    CHECK(Result<void>::err(HalError::kTimeout).error() == HalError::kTimeout);
    CHECK(Result<void>::err(HalError::kNone).error() == HalError::kProtocol);

    // Result<T>
    auto ok = Result<int>::ok(7);
    CHECK(ok && ok.value() == 7 && ok.error() == HalError::kNone);
    auto err = Result<int>::err(HalError::kStaleData);
    CHECK(!err && err.error() == HalError::kStaleData);
    CHECK(Result<int>::err(HalError::kNone).error() == HalError::kProtocol);

    // MagazineSnapshot 헬퍼 — fresh=false 는 무조건 미검출 판정
    MagazineSnapshot m{};
    m.detected_1 = true;
    m.detected_2 = true;
    m.fresh = false;
    CHECK(!both_detected(m) && !any_detected(m));
    m.fresh = true;
    CHECK(both_detected(m) && any_detected(m));
    m.detected_2 = false;
    CHECK(!both_detected(m) && any_detected(m));

    // Health 기본값
    Health h{};
    CHECK(!h.link_up && h.error_count == 0 && h.last_error == HalError::kNone);

    if (fails == 0)
    {
        std::printf("common_contract_check: all OK\n");
        return 0;
    }
    std::printf("common_contract_check: %d FAIL\n", fails);
    return 1;
}
