// gripper_hal 계약 타입 — 오류 코드, 결과 타입, 신호 어휘, 스냅샷, 상태 판정 함수.
#ifndef GRIPPER_HAL_TYPES_HPP_
#define GRIPPER_HAL_TYPES_HPP_

#include <chrono>
#include <cstdint>
#include <optional>
#include <utility>

namespace gripper::hal
{

using TimePoint = std::chrono::steady_clock::time_point;
using Duration = std::chrono::milliseconds;

enum class HalError : uint8_t
{
    kNone,
    kNotReady,     // 포트 미개방 / 하위 링크 없음
    kTimeout,      // 하위 통신 시간 초과
    kOutOfRange,   // 스텝 번호·신호 enum 범위 밖 (송신 없이 거부)
    kProtocol,     // read-back 불일치 등 프로토콜 정합 실패
    kStaleData,    // 스냅샷 미갱신
    kBusy,         // 하위 장치 busy
    kRejected,     // 정책상 거부
    kIndeterminate // 쓰기 적용 여부 확정 불가 — 재시도 전 상태 재확인 필요
};

// 성공이면 값을, 실패면 오류 코드를 담는다. err(kNone) 은 kProtocol 로 대체된다.
// 미검사 value() 는 std::bad_optional_access 를 던지고, rvalue 는 값을 이동 반환한다.
template <typename T> class [[nodiscard]] Result
{
  public:
    static Result ok(T v)
    {
        Result r;
        r.value_.emplace(std::move(v));
        return r;
    }
    static Result err(HalError e)
    {
        Result r;
        r.error_ = (e == HalError::kNone) ? HalError::kProtocol : e;
        return r;
    }
    bool has_value() const noexcept
    {
        return value_.has_value();
    }
    explicit operator bool() const noexcept
    {
        return has_value();
    }
    const T &value() const &
    {
        return value_.value();
    }
    T &value() &
    {
        return value_.value();
    }
    T value() &&
    {
        return std::move(value_.value());
    }
    HalError error() const noexcept
    {
        return value_.has_value() ? HalError::kNone : error_;
    }

  private:
    Result() = default;
    std::optional<T> value_;
    HalError error_ = HalError::kNone;
};

template <> class [[nodiscard]] Result<void>
{
  public:
    static Result ok()
    {
        return Result(HalError::kNone, true);
    }
    static Result err(HalError e)
    {
        return Result((e == HalError::kNone) ? HalError::kProtocol : e, false);
    }
    bool has_value() const noexcept
    {
        return ok_;
    }
    explicit operator bool() const noexcept
    {
        return ok_;
    }
    HalError error() const noexcept
    {
        return ok_ ? HalError::kNone : error_;
    }

  private:
    Result(HalError e, bool ok) : error_(e), ok_(ok)
    {
    }
    HalError error_;
    bool ok_;
};

// 구동 명령으로 유효한 스텝 번호 범위. 허용 스텝 목록은 config 소유.
inline constexpr uint8_t kStepMin = 1;
inline constexpr uint8_t kStepMax = 63;

// 컨트롤러 제어 라인. 스텝 비트는 여기 없다 — write_step 이 유일 경로.
// kCount 는 센티널이며 포트 입력으로 들어오면 kOutOfRange.
enum class ControlLine : uint8_t
{
    kSetup,       // 원점복귀 지령
    kHold,        // 감속정지·잔여 스트로크 보류 (HOLD 중 DRIVE 무효)
    kDrive,       // 스텝 실행
    kReset,       // 알람·동작 리셋
    kServoOn,     // 서보 ON
    kLockRelease, // 락 해제
    kCount
};

// 컨트롤러 피드백 신호. kOut0~kOut5 는 실행 스텝 번호 반향이자 알람 시 그룹 코드.
enum class FeedbackSignal : uint8_t
{
    kOut0,
    kOut1,
    kOut2,
    kOut3,
    kOut4,
    kOut5,
    kBusy,          // 동작 중
    kArea,          // Area1~Area2 구간 내
    kSetOn,         // 원점 확립
    kInPosition,    // 목표 위치 도달
    kServoReady,    // 서보 ON 상태
    kEmergencyStop, // negative-true: 정상 시 ON
    kAlarm,         // negative-true: 정상 시 ON
    kCount
};

// 판정 3상태. stale 스냅샷은 kUnknown 이며 정상/이상 어느 쪽도 아니다.
enum class SignalState : uint8_t
{
    kUnknown,
    kInactive,
    kActive
};

// 피드백 원자 스냅샷.
// 구현체 의무: stamp 는 입력 이미지 수신 시각(캐시 반환 시 재기록 금지), seq 는 그 이미지의
// 단조 증가 번호(같은 이미지에서 파생된 스냅샷은 같은 값), fresh 는 현재 상태를 대표할 때만 true.
struct FeedbackSnapshot
{
    uint16_t bits = 0; // FeedbackSignal 인덱스 LSB-first 원시 레벨
    bool fresh = false;
    uint32_t seq = 0;
    TimePoint stamp{};
};

static_assert(static_cast<unsigned>(FeedbackSignal::kCount) <= 16,
              "FeedbackSnapshot::bits 폭(16) 초과 — 저장 타입을 넓힐 것");

// 원시 레벨 조회. 극성·fresh 미적용이며 범위 밖 신호는 false.
inline bool get(const FeedbackSnapshot &snapshot, FeedbackSignal signal)
{
    const auto index = static_cast<uint8_t>(signal);
    return index < static_cast<uint8_t>(FeedbackSignal::kCount) && ((snapshot.bits >> index) & 0x1u) != 0;
}

// 도달 완료 스텝 반향(OUT0~OUT5 를 LSB-first 6비트로). stale 이면 판정 불가이므로 nullopt.
//
// 실측(2026-08-19, MK4 `/io_resp` 1샷): release 완료 상태에서 2(= profiles.release),
// 파지 중에는 0 이다. 즉 이 값은 «지시된 스텝» 이 아니라 **도달 완료한 스텝** 의 반향이며,
// 파지처럼 목표 위치에 닿지 못하고 멈추는 동작에서는 0 이 나온다.
// 1차 소스(SMC LECP6 Operation Manual LEC-OM00608 p.26-28)는 미보유 — 근거는 위 실측이다.
// 용도와 한계는 ADR-002(already-at-target-completion) 참조.
inline std::optional<uint8_t> step_echo(const FeedbackSnapshot &snapshot)
{
    static_assert(static_cast<uint8_t>(FeedbackSignal::kOut5) - static_cast<uint8_t>(FeedbackSignal::kOut0) == 5,
                  "kOut0~kOut5 가 연속 인덱스가 아니다 — step_echo 의 비트 조립 전제 붕괴");
    if (!snapshot.fresh)
    {
        return std::nullopt;
    }
    uint8_t step = 0;
    for (uint8_t i = 0; i < 6; ++i)
    {
        const auto signal = static_cast<FeedbackSignal>(static_cast<uint8_t>(FeedbackSignal::kOut0) + i);
        if (get(snapshot, signal))
        {
            step = static_cast<uint8_t>(step | (1u << i));
        }
    }
    return step;
}

// 알람 활성 여부. stale 이면 kUnknown.
inline SignalState alarm_state(const FeedbackSnapshot &snapshot)
{
    if (!snapshot.fresh)
    {
        return SignalState::kUnknown;
    }
    return get(snapshot, FeedbackSignal::kAlarm) ? SignalState::kInactive : SignalState::kActive;
}

// 비상정지 활성 여부. stale 이면 kUnknown.
inline SignalState emergency_stop_state(const FeedbackSnapshot &snapshot)
{
    if (!snapshot.fresh)
    {
        return SignalState::kUnknown;
    }
    return get(snapshot, FeedbackSignal::kEmergencyStop) ? SignalState::kInactive : SignalState::kActive;
}

// 스텝 실행(DRIVE) 착수 가능 여부 — fresh · BUSY=0 · SVRE=1 · SETON=1 · 무알람 · 무ESTOP.
inline bool is_ready_for_drive(const FeedbackSnapshot &snapshot)
{
    return snapshot.fresh && !get(snapshot, FeedbackSignal::kBusy) && get(snapshot, FeedbackSignal::kServoReady) &&
           get(snapshot, FeedbackSignal::kSetOn) && alarm_state(snapshot) == SignalState::kInactive &&
           emergency_stop_state(snapshot) == SignalState::kInactive;
}

// 원점복귀(SETUP) 착수 가능 여부 — SETON 은 요구하지 않는다.
inline bool is_ready_for_origin(const FeedbackSnapshot &snapshot)
{
    return snapshot.fresh && !get(snapshot, FeedbackSignal::kBusy) && get(snapshot, FeedbackSignal::kServoReady) &&
           alarm_state(snapshot) == SignalState::kInactive && emergency_stop_state(snapshot) == SignalState::kInactive;
}

// 매거진 감지 스냅샷. detected_* 는 극성 적용 완료값이며, seq 는 FeedbackSnapshot 과 같은 규칙.
struct MagazineSnapshot
{
    bool detected_1 = false;
    bool detected_2 = false;
    bool fresh = false;
    uint32_t seq = 0;
    TimePoint stamp{};
};

// 2점 모두 감지 여부. stale 이면 false.
inline bool both_detected(const MagazineSnapshot &snapshot)
{
    return snapshot.fresh && snapshot.detected_1 && snapshot.detected_2;
}

// 1점 이상 감지 여부. stale 이면 false.
inline bool any_detected(const MagazineSnapshot &snapshot)
{
    return snapshot.fresh && (snapshot.detected_1 || snapshot.detected_2);
}

// 두 스냅샷이 같은 입력 이미지에서 왔는지 — 다르면 조합 판정을 만들지 않는다.
inline bool same_image(const FeedbackSnapshot &feedback, const MagazineSnapshot &magazine)
{
    return feedback.fresh && magazine.fresh && feedback.seq == magazine.seq;
}

struct Health
{
    bool link_up = false;
    Duration snapshot_age{0};
    uint32_t error_count = 0;
    uint32_t last_seq = 0;
    HalError last_error = HalError::kNone;
};

} // namespace gripper::hal

#endif // GRIPPER_HAL_TYPES_HPP_
