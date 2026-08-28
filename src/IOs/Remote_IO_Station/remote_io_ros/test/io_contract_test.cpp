// legacy tc_io 공개 계약 변환·정책 파리티 (remote_io M4)
//
// 20ms 타이머 자체가 아니라 **무엇을 담아 내보내는가 / 언제 알람을 내는가** 를 고정한다.
// 근거는 M0 인벤토리 §3(ROS 계약)·§4(주기·initValue) 의 legacy 실측값이다.
#include "../src/io_contract.hpp"

#include <gtest/gtest.h>

namespace
{

using namespace remote_io::ros_assembly;

// ── io_resp 비트 전개 (인벤토리 §3: 인덱스 = 워드×16 + 비트, LSB-first) ──

TEST(ExpandBits, LsbFirstWithinWord)
{
    // 워드0 = 0x0005 → 비트 0·2 가 1
    auto b = expandBits({0x0005}, 16);
    EXPECT_EQ(b[0], 1);
    EXPECT_EQ(b[1], 0);
    EXPECT_EQ(b[2], 1);
    EXPECT_EQ(b[15], 0);
}

TEST(ExpandBits, WordBoundaryIsIndexTimesSixteen)
{
    // 워드1 의 비트 1 → 전체 인덱스 17
    auto b = expandBits({0x0000, 0x0002}, 32);
    EXPECT_EQ(b[17], 1);
    EXPECT_EQ(b[16], 0);
}

TEST(ExpandBits, OperationalSizesMatchLegacyResize)
{
    // legacy: io_di resize(80) = DI 5워드, io_do resize(96) = DO 6워드 (cpp:506-507)
    EXPECT_EQ(expandBits(std::vector<uint16_t>(5, 0), 5 * 16).size(), 80u);
    EXPECT_EQ(expandBits(std::vector<uint16_t>(6, 0), 6 * 16).size(), 96u);
}

TEST(ExpandBits, MissingWordsYieldZerosNotGarbage)
{
    auto b = expandBits({0xFFFF}, 32); // 워드 1개뿐인데 32비트 요구
    EXPECT_EQ(b.size(), 32u);
    EXPECT_EQ(b[0], 1);
    EXPECT_EQ(b[16], 0);
}

// ── 기동 초기값 (인벤토리 §4: 96비트 중 8비트만 1) ──

TEST(InitialImage, LegacyEightBitsMapToExpectedWords)
{
    const std::vector<int32_t> legacy = {1, 3, 5, 9, 11, 13, 90, 94};
    auto img = buildInitialImage(legacy, 6);
    ASSERT_EQ(img.size(), 6u);
    // 1·3·5·9·11·13 → 워드0 의 비트들
    EXPECT_EQ(img[0], 0x2A2Au);
    // 90 → 워드5 비트10, 94 → 워드5 비트14
    EXPECT_EQ(img[5], static_cast<uint16_t>((1u << 10) | (1u << 14)));
    for (size_t w : {1u, 2u, 3u, 4u})
        EXPECT_EQ(img[w], 0u);
}

TEST(InitialImage, OutOfRangeBitRejectsWholeImage)
{
    // 조용히 무시하면 "설정한 초기값이 안 걸린 채 기동"이 된다 — 전체를 거부한다.
    EXPECT_TRUE(buildInitialImage({0, 96}, 6).empty());
    EXPECT_TRUE(buildInitialImage({-1}, 6).empty());
}

TEST(InitialImage, EmptyListIsAllZero)
{
    auto img = buildInitialImage({}, 6);
    ASSERT_EQ(img.size(), 6u);
    for (uint16_t w : img)
        EXPECT_EQ(w, 0u);
}

// ── io_service 요청 검증 (legacy 미검사 구간을 막는다) ──

TEST(WriteRequest, LengthMismatchRejected)
{
    auto c = checkWriteRequest({0, 1}, {1}, 6);
    EXPECT_FALSE(c.ok);
}

TEST(WriteRequest, OutOfRangeIndexRejected)
{
    EXPECT_FALSE(checkWriteRequest({96}, {1}, 6).ok);
    EXPECT_FALSE(checkWriteRequest({-1}, {1}, 6).ok);
    EXPECT_TRUE(checkWriteRequest({95}, {1}, 6).ok); // 상한은 word*16-1
}

TEST(WriteRequest, NonBinaryStateRejected)
{
    EXPECT_FALSE(checkWriteRequest({0}, {2}, 6).ok);
}

TEST(WriteRequest, EmptyRejected)
{
    EXPECT_FALSE(checkWriteRequest({}, {}, 6).ok);
}

// ── 알람 정책 (인벤토리 §3: 에러 지속 중 매 틱 반복, 재연결 시 0 발행) ──

TEST(Alarm, RepeatsWhileErrorStands)
{
    auto d = decideAlarm(AlarmCode::kReadingFail, false);
    EXPECT_TRUE(d.publish);
    EXPECT_EQ(d.code, AlarmCode::kReadingFail);
    // 두 번째 틱에도 같은 코드가 다시 나간다 — legacy 관측 동작
    auto d2 = decideAlarm(AlarmCode::kReadingFail, false);
    EXPECT_TRUE(d2.publish);
}

TEST(Alarm, SilentWhenHealthy)
{
    auto d = decideAlarm(AlarmCode::kNone, false);
    EXPECT_FALSE(d.publish);
}

TEST(Alarm, ReconnectPublishesClearOnce)
{
    auto d = decideAlarm(AlarmCode::kDisconnect, true);
    EXPECT_TRUE(d.publish);
    EXPECT_EQ(d.code, AlarmCode::kNone); // 재연결은 해제(0) 를 알린다
}

TEST(Alarm, CodesMatchLegacyNumbers)
{
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kNone), 0);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kDisconnect), 1101);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kWritingFail), 1102);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kReadingFail), 1103);
}

// ── 틱 결정 — 이번 수정 7건이 여기서 고정된다 ──
//
// 노드 본문은 rclcpp 때문에 단위시험이 어렵다. 결정을 순수 함수로 뽑아 두면
// "어떤 조건에서 무엇을 하는가" 가 회귀 없이 남는다.

TickInput base()
{
    TickInput in;
    in.read_ok = true;
    in.was_connected = true;
    in.mirror_seeded = true;
    in.initial_applied = true;
    in.apply_initial_image = false;
    in.watchdog_timeout_ms = 0;
    in.watchdog_configured = false;
    in.current_error = AlarmCode::kNone;
    return in;
}

TEST(PlanTick, ReadFailureNeverPublishes)
{
    auto in = base();
    in.read_ok = false;
    in.err = remote_io::hal::RemoteIoError::kTimeout;
    const auto p = planTick(in);
    EXPECT_FALSE(p.publish_io);              // stale 을 신선한 값으로 위장하지 않는다
    EXPECT_EQ(p.error_code, AlarmCode::kReadingFail);
}

TEST(PlanTick, NotConnectedMapsToDisconnectAlarm)
{
    auto in = base();
    in.read_ok = false;
    in.err = remote_io::hal::RemoteIoError::kNotConnected;
    EXPECT_EQ(planTick(in).error_code, AlarmCode::kDisconnect);
}

TEST(PlanTick, SteadyTickPublishesAndKeepsAlarm)
{
    auto in = base();
    in.current_error = AlarmCode::kWritingFail;
    const auto p = planTick(in);
    EXPECT_TRUE(p.publish_io);
    EXPECT_FALSE(p.reconnected);
    EXPECT_FALSE(p.seed_mirror);
    EXPECT_EQ(p.error_code, AlarmCode::kWritingFail); // 정상 틱이 알람을 지우지 않는다
}

// HIGH-2 회귀 방지 — 시드는 최초 1회
TEST(PlanTick, SeedsOnlyOnFirstLink)
{
    auto in = base();
    in.was_connected = false;
    in.mirror_seeded = false;
    EXPECT_TRUE(planTick(in).seed_mirror);

    in.mirror_seeded = true;   // 이후 재연결
    EXPECT_FALSE(planTick(in).seed_mirror);  // 재시드하면 포트 재기록 결과를 덮는다
}

// HIGH-3 회귀 방지 — 초기 이미지는 생애 1회
TEST(PlanTick, InitialImageAppliedOncePerProcess)
{
    auto in = base();
    in.was_connected = false;
    in.apply_initial_image = true;
    in.initial_applied = false;
    EXPECT_TRUE(planTick(in).apply_initial);

    in.initial_applied = true; // 재연결
    EXPECT_FALSE(planTick(in).apply_initial); // io_service 로 설정한 출력을 덮지 않는다
}

TEST(PlanTick, InitialImageNeverAppliedWhenDisabled)
{
    auto in = base();
    in.was_connected = false;
    in.apply_initial_image = false;
    in.initial_applied = false;
    EXPECT_FALSE(planTick(in).apply_initial); // 기본은 읽기 전용 기동
}

// HIGH-1 회귀 방지 — 워치독은 timeout>0 일 때 1회 구성
TEST(PlanTick, WatchdogConfiguredOnceWhenEnabled)
{
    auto in = base();
    in.was_connected = false;
    in.watchdog_timeout_ms = 500;
    in.watchdog_configured = false;
    EXPECT_TRUE(planTick(in).configure_watchdog);

    in.watchdog_configured = true;
    EXPECT_FALSE(planTick(in).configure_watchdog);
}

TEST(PlanTick, WatchdogNotConfiguredWhenTimeoutZero)
{
    auto in = base();
    in.was_connected = false;
    in.watchdog_timeout_ms = 0;
    EXPECT_FALSE(planTick(in).configure_watchdog); // 값은 사용자 소유 — 코드가 고르지 않는다
}

TEST(PlanTick, ReconnectClearsAlarm)
{
    auto in = base();
    in.was_connected = false;
    in.current_error = AlarmCode::kDisconnect;
    const auto p = planTick(in);
    EXPECT_TRUE(p.reconnected);
    EXPECT_EQ(p.error_code, AlarmCode::kNone);
}

// HIGH-4 회귀 방지 — 미연결이면 재시도하지 않는다
TEST(ShouldRetryWrite, NotConnectedStopsImmediately)
{
    EXPECT_FALSE(shouldRetryWrite(remote_io::hal::RemoteIoError::kNotConnected, 0, 3));
}

TEST(ShouldRetryWrite, OtherErrorsRetryUntilBudget)
{
    using E = remote_io::hal::RemoteIoError;
    EXPECT_TRUE(shouldRetryWrite(E::kProtocol, 0, 3));
    EXPECT_TRUE(shouldRetryWrite(E::kProtocol, 1, 3));
    EXPECT_FALSE(shouldRetryWrite(E::kProtocol, 2, 3)); // 마지막 시도 뒤에는 슬립하지 않는다
}

// 리뷰 Q6 — 쓰기 성공이 읽기 상태를 대변하지 않게
TEST(ClearOnWriteSuccess, ClearsOnlyWritingFail)
{
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kWritingFail), AlarmCode::kNone);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kReadingFail), AlarmCode::kReadingFail);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kDisconnect), AlarmCode::kDisconnect);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kNone), AlarmCode::kNone);
}

} // namespace
