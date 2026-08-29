#include "modbus_rtu/rtu_frame.hpp"

#include <gtest/gtest.h>

namespace
{

using namespace comm::modbus_rtu;

std::vector<uint8_t> hex(std::initializer_list<int> bytes)
{
    std::vector<uint8_t> v;
    for (int b : bytes)
        v.push_back(static_cast<uint8_t>(b));
    return v;
}

// 매뉴얼 p6-8 검증 벡터 6종 — zefg_c35_probe.py selftest 6/6 및 실기 H0/H2 로 실증된 프레임.
TEST(RtuFrame, BuildMatchesManualVectors)
{
    EXPECT_EQ(buildWriteSingleRequest(1, 0x0000, 0x0001),
              hex({0x01, 0x06, 0x00, 0x00, 0x00, 0x01, 0x48, 0x0A}));
    EXPECT_EQ(buildWriteMultipleRequest(1, 0x0002, {0x0000, 0x0000}),
              hex({0x01, 0x10, 0x00, 0x02, 0x00, 0x02, 0x04, 0x00, 0x00, 0x00, 0x00, 0x72, 0x76}));
    EXPECT_EQ(buildWriteMultipleRequest(1, 0x0004, {0x4248, 0x0000}),
              hex({0x01, 0x10, 0x00, 0x04, 0x00, 0x02, 0x04, 0x42, 0x48, 0x00, 0x00, 0x66, 0x32}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0041, 1), hex({0x01, 0x03, 0x00, 0x41, 0x00, 0x01, 0xD4, 0x1E}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0042, 2), hex({0x01, 0x03, 0x00, 0x42, 0x00, 0x02, 0x64, 0x1F}));
    EXPECT_EQ(buildReadHoldingRequest(1, 0x0046, 2), hex({0x01, 0x03, 0x00, 0x46, 0x00, 0x02, 0x25, 0xDE}));
}

TEST(RtuFrame, QuantityRangeGuardsReturnEmpty)
{
    EXPECT_TRUE(buildReadHoldingRequest(1, 0, 0).empty());
    EXPECT_TRUE(buildReadHoldingRequest(1, 0, 126).empty());
    EXPECT_TRUE(buildWriteMultipleRequest(1, 0, {}).empty());
    EXPECT_TRUE(buildWriteMultipleRequest(1, 0, std::vector<uint16_t>(124, 0)).empty());
}

TEST(RtuFrame, ExpectedResponseLength)
{
    EXPECT_EQ(expectedResponseLength(0x03, 1), 7u);
    EXPECT_EQ(expectedResponseLength(0x03, 2), 9u);
    EXPECT_EQ(expectedResponseLength(0x06, 0), 8u);
    EXPECT_EQ(expectedResponseLength(0x10, 0), 8u);
    EXPECT_EQ(expectedResponseLength(0x04, 1), 0u);
}

TEST(RtuFrame, ParseReadHappyPath)
{
    // 매뉴얼 p7: read 0x0041 qty1 응답 = 01 03 02 00 00 B8 44
    auto r = parseReadHoldingResponse(hex({0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x44}), 1, 1, nullptr);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x0000}));
}

TEST(RtuFrame, ParseReadTwoWordsBigEndian)
{
    std::vector<uint8_t> f = hex({0x01, 0x03, 0x04, 0x42, 0x48, 0x00, 0x00});
    appendCrc(f);
    auto r = parseReadHoldingResponse(f, 1, 2, nullptr);
    ASSERT_TRUE(r);
    EXPECT_EQ(r.value(), (std::vector<uint16_t>{0x4248, 0x0000}));
}

TEST(RtuFrame, ParseDetectsCrcMismatch)
{
    auto r = parseReadHoldingResponse(hex({0x01, 0x03, 0x02, 0x00, 0x00, 0xB8, 0x45}), 1, 1, nullptr);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kCrcMismatch);
}

TEST(RtuFrame, ParseDetectsShortFrame)
{
    auto r = parseReadHoldingResponse(hex({0x01, 0x03}), 1, 1, nullptr);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kFrameShort);
}

TEST(RtuFrame, ParseExceptionFrameExposesCode)
{
    std::vector<uint8_t> f = hex({0x01, 0x83, 0x02});
    appendCrc(f);
    uint8_t code = 0;
    auto r = parseReadHoldingResponse(f, 1, 1, &code);
    EXPECT_FALSE(r);
    EXPECT_EQ(r.error(), RtuError::kException);
    EXPECT_EQ(code, 0x02);
}

TEST(RtuFrame, ParseRejectsWrongUnitOrHeader)
{
    std::vector<uint8_t> wrong_unit = hex({0x02, 0x03, 0x02, 0x00, 0x00});
    appendCrc(wrong_unit);
    EXPECT_EQ(parseReadHoldingResponse(wrong_unit, 1, 1, nullptr).error(), RtuError::kProtocol);

    // write ack: 매뉴얼 p6 — 01 10 00 02 00 02 E0 08
    EXPECT_TRUE(parseWriteAck(hex({0x01, 0x10, 0x00, 0x02, 0x00, 0x02, 0xE0, 0x08}), 1, 0x10, 0x0002, nullptr));
    EXPECT_EQ(parseWriteAck(hex({0x01, 0x10, 0x00, 0x03, 0x00, 0x02, 0xB1, 0xC8}), 1, 0x10, 0x0002, nullptr).error(),
              RtuError::kProtocol);
}

} // namespace
