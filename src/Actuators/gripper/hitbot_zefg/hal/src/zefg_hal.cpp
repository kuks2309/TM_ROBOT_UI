#include "hitbot_zefg/zefg_hal.hpp"

#include <cstring>

namespace gripper::hitbot
{

InitStatus decodeInitStatus(uint16_t raw)
{
    if (raw == 0)
        return InitStatus::kNotInitialized;
    if (raw == 5)
        return InitStatus::kCompleted;
    return InitStatus::kInitializing;
}

ClampStatus decodeClampStatus(uint16_t raw)
{
    switch (raw)
    {
    case 0:
        return ClampStatus::kInPlace;
    case 1:
        return ClampStatus::kMoving;
    case 2:
        return ClampStatus::kClamping;
    case 3:
        return ClampStatus::kDropping;
    default:
        return ClampStatus::kUnknown;
    }
}

float wordsToFloat(uint16_t hi, uint16_t lo)
{
    const uint32_t bits = (static_cast<uint32_t>(hi) << 16) | static_cast<uint32_t>(lo);
    float value;
    std::memcpy(&value, &bits, sizeof(value));
    return value;
}

std::array<uint16_t, 2> floatToWords(float value)
{
    uint32_t bits;
    std::memcpy(&bits, &value, sizeof(bits));
    return {static_cast<uint16_t>(bits >> 16), static_cast<uint16_t>(bits & 0xFFFFu)};
}

namespace
{
// RtuError→HalError 고정 매핑(에러 매핑 고정표): kNotOpen→kNotReady, kTimeout→kTimeout,
// kCrcMismatch/kFrameShort/kProtocol→kProtocol, kException→kRejected, kOutOfRange→kOutOfRange.
gripper::hal::HalError mapRtuError(comm::modbus_rtu::RtuError e)
{
    using comm::modbus_rtu::RtuError;
    switch (e)
    {
    case RtuError::kNotOpen:
        return gripper::hal::HalError::kNotReady;
    case RtuError::kTimeout:
        return gripper::hal::HalError::kTimeout;
    case RtuError::kCrcMismatch:
    case RtuError::kFrameShort:
    case RtuError::kProtocol:
        return gripper::hal::HalError::kProtocol;
    case RtuError::kException:
        return gripper::hal::HalError::kRejected;
    case RtuError::kOutOfRange:
        return gripper::hal::HalError::kOutOfRange;
    case RtuError::kNone:
    default:
        return gripper::hal::HalError::kProtocol; // err(kNone) 은 계약상 발생하지 않음(방어적 승격)
    }
}
} // namespace

ZefgHal::ZefgHal(std::shared_ptr<comm::modbus_rtu::RtuClient> client) : client_(std::move(client))
{
}

gripper::hal::HalError ZefgHal::mapAndRecord(comm::modbus_rtu::RtuError e)
{
    const gripper::hal::HalError mapped = mapRtuError(e);
    // 예외 코드는 래치 방식으로 보존한다 — 이 통신이 예외가 아니어도 직전에 관측된 마지막
    // 슬레이브 예외 코드를 그대로 유지해 다음 readSnapshot()/lastExceptionCode() 에 동반시킨다.
    if (e == comm::modbus_rtu::RtuError::kException)
        last_exception_code_ = client_->lastExceptionCode();
    last_error_ = mapped;
    ++error_count_;
    return mapped;
}

void ZefgHal::recordSuccess()
{
    last_error_ = gripper::hal::HalError::kNone;
}

void ZefgHal::recordLocalRejection(gripper::hal::HalError e)
{
    last_error_ = e;
    ++error_count_;
}

gripper::hal::Result<void> ZefgHal::commandInitialize()
{
    auto r = client_->writeSingleRegister(kRegInitCommand, 1);
    if (!r)
        return gripper::hal::Result<void>::err(mapAndRecord(r.error()));
    recordSuccess();
    return gripper::hal::Result<void>::ok();
}

gripper::hal::Result<void> ZefgHal::writeTargets(const MotionTarget &target)
{
    if (target.position_mm < kPositionMin || target.position_mm > kPositionMax || target.speed_mms < kSpeedMin ||
        target.speed_mms > kSpeedMax || target.current_a < kCurrentMin || target.current_a > kCurrentMax)
    {
        recordLocalRejection(gripper::hal::HalError::kOutOfRange);
        return gripper::hal::Result<void>::err(gripper::hal::HalError::kOutOfRange);
    }

    // speed→current→position 순(position 이 트리거이므로 마지막 — 매뉴얼 p6 예제 순서 준거).
    const auto speed_words = floatToWords(target.speed_mms);
    auto r_speed = client_->writeMultipleRegisters(kRegTargetSpeed, {speed_words[0], speed_words[1]});
    if (!r_speed)
        return gripper::hal::Result<void>::err(mapAndRecord(r_speed.error()));

    const auto current_words = floatToWords(target.current_a);
    auto r_current = client_->writeMultipleRegisters(kRegTargetCurrent, {current_words[0], current_words[1]});
    if (!r_current)
        return gripper::hal::Result<void>::err(mapAndRecord(r_current.error()));

    const auto position_words = floatToWords(target.position_mm);
    auto r_position = client_->writeMultipleRegisters(kRegTargetPosition, {position_words[0], position_words[1]});
    if (!r_position)
        return gripper::hal::Result<void>::err(mapAndRecord(r_position.error()));

    recordSuccess();
    return gripper::hal::Result<void>::ok();
}

gripper::hal::Result<ZefgSnapshot> ZefgHal::readSnapshot()
{
    auto r = client_->readHoldingRegisters(kRegInitStatus, 8);
    if (!r)
        return gripper::hal::Result<ZefgSnapshot>::err(mapAndRecord(r.error()));

    const auto &w = r.value();
    ZefgSnapshot snap;
    snap.init = decodeInitStatus(w[0]);
    snap.clamp = decodeClampStatus(w[1]);
    snap.position_mm = wordsToFloat(w[2], w[3]);
    snap.speed_mms = wordsToFloat(w[4], w[5]);
    snap.current_a = wordsToFloat(w[6], w[7]);
    snap.exception_code = last_exception_code_;
    recordSuccess();
    return gripper::hal::Result<ZefgSnapshot>::ok(snap);
}

gripper::hal::Health ZefgHal::health() const
{
    gripper::hal::Health h;
    h.link_up = (last_error_ != gripper::hal::HalError::kNotReady);
    h.error_count = error_count_;
    h.last_error = last_error_;
    return h;
}

uint8_t ZefgHal::lastExceptionCode() const
{
    return last_exception_code_;
}

} // namespace gripper::hitbot
