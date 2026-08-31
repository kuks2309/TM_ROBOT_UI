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
    // 방어적 리셋: 데드라인·정지 판정 기점·모션 시작 위치·표본 이력은 각 전이 tick(kCheckInit/
    // kWriteTargets)이 사용 전 덮어쓰지만, 그 순서에 의존하지 않도록 초기화한다(덮어쓰기 전에 읽히면
    // 데드라인은 즉시 만료, 방향 판정은 닫힘 불성립 쪽 — 오탐 성공이 아니라 안전 측으로 드러남).
    init_deadline_ = now;
    motion_deadline_ = now;
    last_change_at_ = now;
    motion_start_position_mm_ = target.position_mm;
    first_label_set_ = false;
    label_changed_ = false;
    has_last_position_ = false;
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
    // 모션 시작 위치 = 목표 write 직전의 마지막 판독 위치(kCheckInit/kInitializing 폴링 스냅샷) —
    // kWaitMotion 의 닫힘/열기 방향 판정 기준(리뷰 F1).
    motion_start_position_mm_ = last_snapshot_.position_mm;
    const auto r = hal_.writeTargets(target_);
    if (!r)
    {
        // 값 거부(범위 밖 로컬 거부 kOutOfRange·장치 거부 kRejected)는 통신 오류가 아니다 —
        // kRejected 로 구분 보고한다(리뷰 Minor1). 그 외 hal 오류는 kCommError.
        const gripper::hal::HalError e = r.error();
        if (e == gripper::hal::HalError::kOutOfRange || e == gripper::hal::HalError::kRejected)
            fail(SeqOutcome::kRejected);
        else
            fail(SeqOutcome::kCommError);
        return;
    }
    moving_seen_ = false;
    first_label_set_ = false; // 첫 표본 라벨·위치 이력은 kWaitMotion 첫 폴링에서 채운다
    label_changed_ = false;
    has_last_position_ = false;
    last_change_at_ = now; // 정지 판정 창 기점(첫 표본에서 다시 갱신)
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

    // 판정 규약(Ruling 14 — 위치 동역학 우선, python 선례 zefg_serial.py move_to 와 동일 순서).
    // 근거: HIL 정본(src/Actuators/gripper/docs/hil/) §상태 레지스터 갱신 지연 실측 — 직전 상태가
    // Dropping 래치이면 실제 이동 중에도 0x0041 이 ≥1초 Dropping 을 유지하다 목표 직전에서야 Moving
    // 후 In place 로 갱신된다. 라벨·시간 유예만으로는 이동 중 표본을 낙하로 오판한다(실기 `낙하 감지
    // (pos 5.6mm)` — 실물은 정상 완주 중). 그래서 라벨은 "정지 후, 명령 후 한 번이라도 바뀌었을 때"만
    // 판정에 쓰고, 위치가 변하는 동안은 판정하지 않는다.
    if (!first_label_set_)
    {
        first_label_ = s.clamp; // 명령 후 첫 표본 = 직전 모션의 래치값일 수 있다
        first_label_set_ = true;
    }
    else if (s.clamp != first_label_)
    {
        label_changed_ = true;
    }
    if (has_last_position_)
    {
        if (std::fabs(s.position_mm - last_position_mm_) > kPositionStillEpsMm)
        {
            moving_seen_ = true; // 위치 동역학으로 이동 관측(라벨이 지연돼도)
            last_change_at_ = now;
        }
    }
    else
    {
        has_last_position_ = true;
        last_change_at_ = now;
    }
    last_position_mm_ = s.position_mm;
    if (s.clamp == ClampStatus::kMoving)
        moving_seen_ = true;

    const bool at_target = std::fabs(s.position_mm - target_.position_mm) <= cfg_.position_tolerance_mm;

    // ① 무이동 명령(Ruling 13, 실기 재현): Moving 을 본 적 없는데 이미 목표 위치면 래치 상태와 무관하게
    //    즉시 완료 — 같은 위치 재명령 시 장치는 움직이지 않아 0x0041 이 영영 갱신되지 않는다.
    if (!moving_seen_ && at_target)
    {
        succeed(SeqOutcome::kReached);
        return;
    }

    // ② 이동 중 판정 금지: 마지막 위치 변화 후 status_grace(정지 판정 창) 미만이면 라벨 무관 계속 폴링.
    if (now - last_change_at_ < cfg_.status_grace)
    {
        if (now >= motion_deadline_)
            fail(SeqOutcome::kTimeout);
        return;
    }

    // ③ 정지 후 종결. 실제 낙하는 반드시 Clamping 후 Dropping 으로의 라벨 변화가 동반되므로 여기서 검출.
    if (label_changed_)
    {
        if (s.clamp == ClampStatus::kDropping)
        {
            fail(SeqOutcome::kDropped);
            return;
        }
        if (s.clamp == ClampStatus::kClamping)
        {
            // 파지 성공(kClamped) 조건(코드가 강제, 리뷰 F1): 닫힘 방향(목표 > 모션 시작 위치)이고 현재
            // 위치가 목표 미달일 때만. 그 외 Clamping 은 경로 걸림(kObstructed) — 실기 Clamping 은 외력에
            // 저항 중인 과도 상태이기도 하다(HIL §백드라이브·힘 순응 실측: 외력 소멸 시 목표 복귀 후
            // InPlace) — 열기 방향에서 파지 성공으로 오판하지 않는다.
            const bool closing = target_.position_mm > motion_start_position_mm_;
            const bool short_of_target = s.position_mm < target_.position_mm;
            if (closing && short_of_target)
                succeed(SeqOutcome::kClamped);
            else
                fail(SeqOutcome::kObstructed);
            return;
        }
        if (s.clamp == ClampStatus::kInPlace && at_target)
        {
            succeed(SeqOutcome::kReached);
            return;
        }
    }
    else if (at_target)
    {
        succeed(SeqOutcome::kReached); // 라벨이 래치 그대로(미갱신)여도 정지 + 목표 위치면 도달
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
