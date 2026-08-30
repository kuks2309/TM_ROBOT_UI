// zefg_sequencer.hpp — Z-EFG-C35 시퀀서 FSM(Finite State Machine, ADR-005 단계④-3). ZefgHal 위에서
// 이동 명령 1건(초기화 확인→목표 write→완료 폴링)을 비블로킹 tick() 으로 완주시킨다.
//
// 계약:
// - tick() 1회당 hal 호출 ≤1회, 내부 sleep·시계 없음 — 시간은 인자 TimePoint 로만 흐른다.
// - 통신은 ZefgHal 만 소비한다. 하위 버스·링크 심볼은 이 층에 나타나지 않는다(단일 쓰기 마스터
//   게이트가 motion/src·include 를 차단 — checks/gripper-io-single-master.sh).
// - 터미널(kSucceeded/kFailed) 후 start() 재호출로 재사용한다.
#ifndef HITBOT_ZEFG_ZEFG_SEQUENCER_HPP_
#define HITBOT_ZEFG_ZEFG_SEQUENCER_HPP_

#include <cstdint>

#include "gripper_common/types.hpp"
#include "hitbot_zefg/zefg_hal.hpp"

namespace gripper::hitbot
{

enum class SeqState : uint8_t
{
    kIdle,
    kCheckInit,
    kInitializing,
    kWriteTargets,
    kWaitMotion,
    kSucceeded,
    kFailed
};

enum class SeqOutcome : uint8_t
{
    kNone,
    kReached,
    kClamped,
    kDropped,
    kTimeout,
    kCommError,
    kNotInitialized
};

struct SeqConfig
{
    gripper::hal::Duration init_timeout{5000}; // 실기: 전원 인가 자동 초기화 관찰 — 여유값 ⚠(실측 미보유, HIL 로 보정)
    gripper::hal::Duration motion_timeout{4000}; // 실측: 35mm@20mm/s 왕복 각 2.5~2.7s → 여유 4s
    float position_tolerance_mm = 0.5F;
    bool auto_initialize = true; // 미초기화 발견 시 commandInitialize 자동 수행
    // 상태 신선도 유예(브리프 승인 확장, 계획 블록 외). 실기·플랜트 공통으로 새 목표 위치 write
    // 후에도 직전 모션의 최종 상태(0x0041 래치, 예: Dropping)가 실제 이동 시작 전까지 유지된다 —
    // HIL 정본(src/Actuators/gripper/docs/hil/) §백드라이브·힘 순응 실측: 첫 폴링이 직전 래치
    // Dropping 을 읽어 정상 도달을 낙하로 오판하는 함정. kWaitMotion 은 Moving 관측 후 또는 이
    // 유예 경과 후에만 Dropping/Clamping 을 판정에 쓴다(python 선례:
    // src/TM_Robot_Task_Manager/tm_task_manager/hardware/zefg_serial.py move_to 의 STATUS_GRACE_S).
    // In place+위치 대조는 예외 — 무이동 명령(이미 목표 위치)의 즉시 성공을 보존한다.
    gripper::hal::Duration status_grace{300};
};

class ZefgSequencer
{
  public:
    ZefgSequencer(ZefgHal &hal, SeqConfig cfg = {});

    // kIdle/터미널에서만 수락 — 수락 시 목표·결과를 리셋하고 kCheckInit 부터 재시작한다.
    bool start(const MotionTarget &target, gripper::hal::TimePoint now);

    // 비블로킹 1스텝: 현재 상태를 처리하고 전이 후 상태를 반환한다(hal 호출 ≤1회).
    SeqState tick(gripper::hal::TimePoint now);

    SeqState state() const
    {
        return state_;
    }

    SeqOutcome outcome() const
    {
        return outcome_;
    }

    // 마지막으로 성공한 판독의 스냅샷(판독 실패 시 직전 값 유지).
    ZefgSnapshot lastSnapshot() const
    {
        return last_snapshot_;
    }

  private:
    void tickCheckInit(gripper::hal::TimePoint now);
    void tickInitializing(gripper::hal::TimePoint now);
    void tickWriteTargets(gripper::hal::TimePoint now);
    void tickWaitMotion(gripper::hal::TimePoint now);
    void fail(SeqOutcome why);
    void succeed(SeqOutcome how);

    ZefgHal &hal_; // 참조 소비(소유 없음) — 수명은 조립층 책임
    SeqConfig cfg_;
    SeqState state_ = SeqState::kIdle;
    SeqOutcome outcome_ = SeqOutcome::kNone;
    MotionTarget target_{0.0F, 0.0F, 0.0F};
    ZefgSnapshot last_snapshot_{};
    bool init_command_pending_ = false; // kCheckInit 이 예약한 초기화 명령(hal 호출 ≤1회/tick 유지)
    bool moving_seen_ = false;          // kWaitMotion 에서 Moving 관측 여부 — 신선도 게이트 해제 조건
    gripper::hal::TimePoint init_deadline_{};      // 초기화 예약 tick 기점 + init_timeout
    gripper::hal::TimePoint motion_deadline_{};    // 목표 write tick 기점 + motion_timeout
    gripper::hal::TimePoint status_fresh_after_{}; // 목표 write tick 기점 + status_grace
};

} // namespace gripper::hitbot

#endif // HITBOT_ZEFG_ZEFG_SEQUENCER_HPP_
