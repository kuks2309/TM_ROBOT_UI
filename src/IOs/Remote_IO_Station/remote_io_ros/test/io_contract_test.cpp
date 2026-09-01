// io_contract 순수 함수 계약 시험(rclcpp 미링크) — 비트 전개·초기 이미지·요청 검증·
// 알람 판단·planTick 상태기계·쓰기 재시도/해제. 레거시 tc_io 파리티가 기준선.
#include "../src/io_contract.hpp"

#include <gtest/gtest.h>

namespace
{

using namespace remote_io::ros_assembly;


TEST(ExpandBits, LsbFirstWithinWord)
{
    auto b = expandBits({0x0005}, 16);
    EXPECT_EQ(b[0], 1);
    EXPECT_EQ(b[1], 0);
    EXPECT_EQ(b[2], 1);
    EXPECT_EQ(b[15], 0);
}

TEST(ExpandBits, WordBoundaryIsIndexTimesSixteen)
{
    auto b = expandBits({0x0000, 0x0002}, 32);
    EXPECT_EQ(b[17], 1);
    EXPECT_EQ(b[16], 0);
}

TEST(ExpandBits, OperationalSizesMatchLegacyResize)
{
    EXPECT_EQ(expandBits(std::vector<uint16_t>(5, 0), 5 * 16).size(), 80u);
    EXPECT_EQ(expandBits(std::vector<uint16_t>(6, 0), 6 * 16).size(), 96u);
}

TEST(ExpandBits, MissingWordsYieldZerosNotGarbage)
{
    auto b = expandBits({0xFFFF}, 32);
    EXPECT_EQ(b.size(), 32u);
    EXPECT_EQ(b[0], 1);
    EXPECT_EQ(b[16], 0);
}


TEST(InitialImage, LegacyEightBitsMapToExpectedWords)
{
    const std::vector<int32_t> legacy = {1, 3, 5, 9, 11, 13, 90, 94};
    auto img = buildInitialImage(legacy, 6);
    ASSERT_EQ(img.size(), 6u);
    EXPECT_EQ(img[0], 0x2A2Au);
    EXPECT_EQ(img[5], static_cast<uint16_t>((1u << 10) | (1u << 14)));
    for (size_t w : {1u, 2u, 3u, 4u})
        EXPECT_EQ(img[w], 0u);
}

TEST(InitialImage, OutOfRangeBitRejectsWholeImage)
{
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


TEST(WriteRequest, LengthMismatchRejected)
{
    auto c = checkWriteRequest({0, 1}, {1}, 6);
    EXPECT_FALSE(c.ok);
}

TEST(WriteRequest, OutOfRangeIndexRejected)
{
    EXPECT_FALSE(checkWriteRequest({96}, {1}, 6).ok);
    EXPECT_FALSE(checkWriteRequest({-1}, {1}, 6).ok);
    EXPECT_TRUE(checkWriteRequest({95}, {1}, 6).ok);
}

TEST(WriteRequest, NonBinaryStateRejected)
{
    EXPECT_FALSE(checkWriteRequest({0}, {2}, 6).ok);
}

TEST(WriteRequest, EmptyRejected)
{
    EXPECT_FALSE(checkWriteRequest({}, {}, 6).ok);
}


TEST(Alarm, RepeatsWhileErrorStands)
{
    auto d = decideAlarm(AlarmCode::kReadingFail, false);
    EXPECT_TRUE(d.publish);
    EXPECT_EQ(d.code, AlarmCode::kReadingFail);
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
    EXPECT_EQ(d.code, AlarmCode::kNone);
}

TEST(Alarm, CodesMatchLegacyNumbers)
{
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kNone), 0);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kDisconnect), 1101);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kWritingFail), 1102);
    EXPECT_EQ(static_cast<int32_t>(AlarmCode::kReadingFail), 1103);
}


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
    EXPECT_FALSE(p.publish_io);
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
    EXPECT_EQ(p.error_code, AlarmCode::kWritingFail);
}

TEST(PlanTick, SeedsOnlyOnFirstLink)
{
    auto in = base();
    in.was_connected = false;
    in.mirror_seeded = false;
    EXPECT_TRUE(planTick(in).seed_mirror);

    in.mirror_seeded = true;
    EXPECT_FALSE(planTick(in).seed_mirror);
}

TEST(PlanTick, InitialImageAppliedOncePerProcess)
{
    auto in = base();
    in.was_connected = false;
    in.apply_initial_image = true;
    in.initial_applied = false;
    EXPECT_TRUE(planTick(in).apply_initial);

    in.initial_applied = true;
    EXPECT_FALSE(planTick(in).apply_initial);
}

TEST(PlanTick, InitialImageNeverAppliedWhenDisabled)
{
    auto in = base();
    in.was_connected = false;
    in.apply_initial_image = false;
    in.initial_applied = false;
    EXPECT_FALSE(planTick(in).apply_initial);
}

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
    EXPECT_FALSE(planTick(in).configure_watchdog);
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

TEST(ShouldRetryWrite, NotConnectedStopsImmediately)
{
    EXPECT_FALSE(shouldRetryWrite(remote_io::hal::RemoteIoError::kNotConnected, 0, 3));
}

TEST(ShouldRetryWrite, OtherErrorsRetryUntilBudget)
{
    using E = remote_io::hal::RemoteIoError;
    EXPECT_TRUE(shouldRetryWrite(E::kProtocol, 0, 3));
    EXPECT_TRUE(shouldRetryWrite(E::kProtocol, 1, 3));
    EXPECT_FALSE(shouldRetryWrite(E::kProtocol, 2, 3));
}

TEST(ClearOnWriteSuccess, ClearsOnlyWritingFail)
{
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kWritingFail), AlarmCode::kNone);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kReadingFail), AlarmCode::kReadingFail);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kDisconnect), AlarmCode::kDisconnect);
    EXPECT_EQ(clearOnWriteSuccess(AlarmCode::kNone), AlarmCode::kNone);
}

}
