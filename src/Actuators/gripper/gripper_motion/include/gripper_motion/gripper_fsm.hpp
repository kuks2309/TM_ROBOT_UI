// GripperFsm — 그리퍼 시퀀스 상태기계. 포트 3종만 소비하며 ROS·필드버스 계층을 모른다.
//
// 블로킹하지 않는다: 모든 대기는 tick() 안의 시각 비교로 처리하므로 호출자가 주기를 소유한다.
#ifndef GRIPPER_MOTION_GRIPPER_FSM_HPP_
#define GRIPPER_MOTION_GRIPPER_FSM_HPP_

#include <functional>
#include <memory>

#include "gripper_hal/command_port.hpp"
#include "gripper_hal/feedback_port.hpp"
#include "gripper_hal/magazine_port.hpp"
#include "gripper_motion/fsm_types.hpp"

namespace gripper::motion
{

struct Ports
{
    std::shared_ptr<hal::IGripperCommandPort> command;
    std::shared_ptr<hal::IGripperFeedbackPort> feedback;
    std::shared_ptr<hal::IMagazineDetectPort> magazine;
};

class GripperFsm
{
  public:
    using Clock = std::function<TimePoint()>;

    // 설정이 validate() 를 통과하지 못하면 모든 request 를 거부한다(미검증 설정으로 구동 금지).
    GripperFsm(Ports ports, const MotionConfig &config, Clock clock = nullptr);

    // 명령 접수 — 프로파일 검증과 인터록 판정을 여기서 끝낸다. 거부 시 송신 0회.
    // bypass_interlock=true 시 이 명령에 한해 매거진 인터록 가드를 건너뛴다(기본 false=적용).
    hal::Result<void> request(MotionCommand command, Profile profile, bool bypass_interlock = false);

    // 상태를 1회 전진시킨다. 완료·실패 시 finished=true.
    MotionTick tick();

    MotionState state() const
    {
        return state_;
    }

    MotionResult last_result() const
    {
        return result_;
    }

    // 진행 중 시퀀스를 중단한다 — 지령을 내리고 BUSY 하강(정지 확인)까지 tick 으로 기다린다.
    void abort();

    // 정지를 확인할 시간이 없는 종료 경로(lifecycle 비활성화)용 즉시 마감.
    // 확인하지 못한 채 끝내므로 결과는 «정지 미보장» 이다 — 확인한 척하지 않는다.
    void finalizeStop();

    // 알람 이력이 명령 경계를 넘어 보존되는지 — 원점복귀 성공으로만 소거된다.
    bool homing_required() const
    {
        return homing_required_;
    }

    // 마지막 종료에서 출력 복귀가 실패했는지 — 실패 사유와 독립이다.
    bool restore_failed() const
    {
        return restore_failed_;
    }

  private:
    bool needsHoming(const hal::FeedbackSnapshot &fb) const;
    bool originReferenceHeld(const hal::FeedbackSnapshot &fb) const;
    // IN0~5·DRIVE·SETUP·RESET 을 한 곳에서 복귀시킨다. 하나라도 실패하면 false.
    bool restoreOutputs();
    // 인터록 대상 모션(profile 또는 원점복귀)에 대한 정책을 고른다.
    InterlockPolicy policyFor(MotionCommand command, Profile profile) const;
    MotionResult guardBeforeDrive(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    // SETUP 인가 직전 게이트 — 원점복귀는 스트로크 끝까지 여는 최대 행정이라 별도로 막는다.
    MotionResult guardBeforeOrigin(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    // 원점복귀 정책만 떼어낸 판정 — 행정 중 매거진이 들어오는 경우를 매 tick 감시한다.
    MotionResult originInterlock(const hal::MagazineSnapshot &mgz) const;
    MotionResult checkInterlock(Profile profile, const hal::MagazineSnapshot &mgz) const;
    MotionResult verifyComplete(const hal::FeedbackSnapshot &fb, const hal::MagazineSnapshot &mgz) const;
    uint8_t stepOf(Profile profile) const;
    void enter(MotionState next);
    MotionTick fail(MotionResult reason);
    MotionTick finish();
    bool expired(const Duration &limit) const;

    Ports ports_;
    MotionConfig config_;
    Clock clock_;
    bool config_valid_ = false;

    MotionState state_ = MotionState::kIdle;
    MotionResult result_ = MotionResult::kNone;
    MotionCommand command_ = MotionCommand::kProfile;
    Profile profile_ = Profile::kHome;
    bool bypass_interlock_ = false;  // per-goal 매거진 인터록 우회(request 마다 갱신)
    // 냉시동은 원점 미확립이므로 true 로 시작한다. 알람을 만나면 다시 선다.
    bool homing_required_ = true;
    // homing_required_ 가 «냉시동이라 모른다» 에서 온 것인지 «기준을 잃었다» 에서 온 것인지
    // 구분한다. 전자만 하드웨어 상태(originReferenceHeld)로 해소할 수 있다.
    bool cold_start_ = true;
    bool reset_asserted_ = false;
    bool restore_failed_ = false;
    // 단계 진입 시 1회만 인가한다 — 매 tick 재기입은 원격 IO 왕복을 무의미하게 늘린다.
    bool phase_wrote_ = false;
    // BUSY 상승을 «봤다» 는 사실을 단계 안에서 래치한다. 실측(MK4 2026-08-20)에서
    // 이미 목표 위치인 명령의 BUSY 펄스가 60ms 로 drive_hold(100ms)보다 짧아,
    // 레벨만 보면 상승을 보고도 처리하지 못한 채 타임아웃했다. enter() 에서 리셋된다.
    bool busy_seen_ = false;
    TimePoint phase_start_{};
    TimePoint request_start_{};
    // 마지막으로 fresh 스냅샷을 본 시각 — feedback_stale_limit 판정의 기준.
    TimePoint last_fresh_{};
    // SETUP 을 올린 시각 — setup_hold 최소 유지시간의 기준.
    TimePoint setup_high_at_{};
};

} // namespace gripper::motion

#endif // GRIPPER_MOTION_GRIPPER_FSM_HPP_
