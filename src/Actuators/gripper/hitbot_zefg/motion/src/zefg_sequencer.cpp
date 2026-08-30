// zefg_sequencer.cpp — ZefgSequencer FSM 구현(ADR-005 단계④-3). 전이 시맨틱스는 계획
// docs/superpowers/plans/ §Task 3 인터페이스 블록, 신선도 게이트는 브리프 승인 확장(헤더 SeqConfig
// 주석의 HIL 근거 인용 참조).
#include "hitbot_zefg/zefg_sequencer.hpp"

#include <cmath>

namespace gripper::hitbot
{

ZefgSequencer::ZefgSequencer(ZefgHal &hal, SeqConfig cfg) : hal_(hal), cfg_(cfg)
{
}

bool ZefgSequencer::start(const MotionTarget &target, gripper::hal::TimePoint now)
{
    if (state_ != SeqState::kIdle && state_ != SeqState::kSucceeded && state_ != SeqState::kFailed)
        return false; // 진행 중 재진입 거부 — 완주/실패(터미널) 후에만 재사용
    target_ = target;
    outcome_ = SeqOutcome::kNone;
    init_command_pending_ = false;
    moving_seen_ = false;
    start_time_ = now;
    state_ = SeqState::kCheckInit;
    return true;
}

SeqState ZefgSequencer::tick(gripper::hal::TimePoint now)
{
    switch (state_)
    {
    case SeqState::kCheckInit:
        tickCheckInit(now);
        break;
    case SeqState::kInitializing:
        tickInitializing(now);
        break;
    case SeqState::kWriteTargets:
        tickWriteTargets(now);
        break;
    case SeqState::kWaitMotion:
        tickWaitMotion(now);
        break;
    case SeqState::kIdle:
    case SeqState::kSucceeded:
    case SeqState::kFailed:
        break; // 유휴·터미널 — start() 대기, hal 호출 없음
    }
    return state_;
}

void ZefgSequencer::tickCheckInit(gripper::hal::TimePoint now)
{
    const auto snap = hal_.readSnapshot();
    if (!snap)
    {
        fail(SeqOutcome::kCommError); // 모든 hal 오류는 kCommError 로 환원(계획 §Task 3 전이 시맨틱스)
        return;
    }
    last_snapshot_ = snap.value();
    if (last_snapshot_.init == InitStatus::kCompleted)
    {
        state_ = SeqState::kWriteTargets;
        return;
    }
    if (!cfg_.auto_initialize)
    {
        fail(SeqOutcome::kNotInitialized);
        return;
    }
    // hal 호출 ≤1회/tick — 이번 tick 은 판독을 이미 썼으므로 초기화 명령은 다음 tick 에 송신한다.
    init_command_pending_ = true;
    init_deadline_ = now + cfg_.init_timeout;
    state_ = SeqState::kInitializing;
}

void ZefgSequencer::tickInitializing(gripper::hal::TimePoint now)
{
    if (init_command_pending_)
    {
        if (!hal_.commandInitialize())
        {
            fail(SeqOutcome::kCommError);
            return;
        }
        init_command_pending_ = false; // 이후 tick 은 완료 폴링
        return;
    }
    const auto snap = hal_.readSnapshot();
    if (!snap)
    {
        fail(SeqOutcome::kCommError);
        return;
    }
    last_snapshot_ = snap.value();
    if (last_snapshot_.init == InitStatus::kCompleted)
    {
        state_ = SeqState::kWriteTargets;
        return;
    }
    if (now >= init_deadline_)
        fail(SeqOutcome::kTimeout);
}

void ZefgSequencer::tickWriteTargets(gripper::hal::TimePoint now)
{
    // 범위 밖(kOutOfRange) 포함 모든 hal 오류를 kCommError 로 환원한다(계획 전이 시맨틱스 고정).
    if (!hal_.writeTargets(target_))
    {
        fail(SeqOutcome::kCommError);
        return;
    }
    moving_seen_ = false;
    status_fresh_after_ = now + cfg_.status_grace; // 신선도 유예 기점 = 목표 write 시각
    motion_deadline_ = now + cfg_.motion_timeout;
    state_ = SeqState::kWaitMotion;
}

void ZefgSequencer::tickWaitMotion(gripper::hal::TimePoint now)
{
    const auto snap = hal_.readSnapshot();
    if (!snap)
    {
        fail(SeqOutcome::kCommError);
        return;
    }
    last_snapshot_ = snap.value();
    const ZefgSnapshot &s = last_snapshot_;

    if (s.clamp == ClampStatus::kMoving)
        moving_seen_ = true;

    // In place + 위치 대조는 신선도 게이트 예외 — 무이동 명령(이미 목표 위치)의 즉시 성공 보존.
    if (s.clamp == ClampStatus::kInPlace &&
        std::fabs(s.position_mm - target_.position_mm) <= cfg_.position_tolerance_mm)
    {
        succeed(SeqOutcome::kReached);
        return;
    }

    // 상태 신선도 게이트: 장치는 새 목표 write 후에도 직전 모션의 최종 상태(0x0041 래치)를 실제
    // 이동 시작 전까지 유지한다 — HIL 정본(src/Actuators/gripper/docs/hil/) §백드라이브·힘 순응
    // 실측(첫 폴링이 직전 래치 Dropping 을 읽는 오탐 함정). Dropping/Clamping 은 Moving 관측 후
    // 또는 status_grace 경과 후에만 판정에 쓴다(헤더 SeqConfig.status_grace 주석·python 선례 참조).
    const bool fresh = moving_seen_ || now >= status_fresh_after_;
    if (fresh && s.clamp == ClampStatus::kClamping)
    {
        succeed(SeqOutcome::kClamped); // 물체 파지 — 닫기 방향에서는 정상 완료
        return;
    }
    if (fresh && s.clamp == ClampStatus::kDropping)
    {
        fail(SeqOutcome::kDropped);
        return;
    }

    if (now >= motion_deadline_)
        fail(SeqOutcome::kTimeout); // 판정 불가 상태 지속 — 마지막 스냅샷은 lastSnapshot() 으로 노출
}

void ZefgSequencer::fail(SeqOutcome why)
{
    state_ = SeqState::kFailed;
    outcome_ = why;
}

void ZefgSequencer::succeed(SeqOutcome how)
{
    state_ = SeqState::kSucceeded;
    outcome_ = how;
}

} // namespace gripper::hitbot
