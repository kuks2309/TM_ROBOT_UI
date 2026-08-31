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
    kNotInitialized,
    kObstructed, // 파지 조건 밖의 Clamping(열기 방향 등) — 경로 걸림(리뷰 F1, 컨트롤러 승인 확장)
    kRejected // 목표 값 거부(범위 밖 로컬 거부·장치 거부) — 통신 오류와 구분(리뷰 Minor1)
};

struct SeqConfig
{
    gripper::hal::Duration init_timeout{5000}; // 실기: 전원 인가 자동 초기화 관찰 — 여유값 ⚠(실측 미보유, HIL 로 보정)
    gripper::hal::Duration motion_timeout{4000}; // 실측: 35mm@20mm/s 왕복 각 2.5~2.7s → 여유 4s
    float position_tolerance_mm = 0.5F;
    bool auto_initialize = true; // 미초기화 발견 시 commandInitialize 자동 수행
    // 정지 판정 창(브리프 승인 확장 필드 — Ruling 14 로 의미 재정의): 위치가 이 시간 동안
    // kPositionStillEpsMm 이내로 머물러야 "정지"로 보고 종결 판정한다. 근거: HIL 정본
    // (src/Actuators/gripper/docs/hil/) §상태 레지스터 갱신 지연 실측 — 직전 상태가 Dropping 래치이면
    // 실제 이동 중에도 0x0041 이 ≥1초 Dropping 을 유지하다 목표 직전에서야 Moving 후 In place 로
    // 갱신된다(In place 출발은 50ms 내 Moving). 라벨·시간 유예만으로는 이동 중 표본을 낙하로 오판
    // (실기 `낙하 감지 (pos 5.6mm)`). 규약(python 선례 zefg_serial.py move_to 와 동일): ① Moving 을
    // 본 적 없는데 이미 목표 위치면 무이동 성공 ② 위치가 변하는 동안은 라벨 무관 계속 폴링 ③ 정지
    // 후에만 종결 — 명령 후 라벨이 한 번이라도 바뀌었으면 라벨로, 래치 그대로면 위치 대조로만.
    gripper::hal::Duration status_grace{300};
};

// 위치 정지 판정 허용 변화량(직전 표본 대비) — 이 값을 초과해 움직이면 이동 중으로 본다
// (python 선례 POSITION_STILL_EPS_MM, 실측 25Hz 궤적의 표본 간 이동량 0.8mm 대비 충분히 작음).
inline constexpr float kPositionStillEpsMm = 0.1F;

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
    bool moving_seen_ = false; // Moving 라벨 또는 위치 변화 관측 — 무이동(①) 판정 배제 조건
    float motion_start_position_mm_ = 0.0F; // 목표 write 직전 판독 위치 — 닫힘/열기 방향 판정 기준(리뷰 F1)
    ClampStatus first_label_ = ClampStatus::kUnknown; // 명령 후 첫 표본의 라벨(래치값)
    bool first_label_set_ = false;
    bool label_changed_ = false; // 첫 표본과 다른 라벨을 한 번이라도 관측 — 정지 후 라벨 판정 허용 조건
    float last_position_mm_ = 0.0F; // 직전 표본 위치 — 위치 동역학(정지/이동) 판정용
    bool has_last_position_ = false;
    gripper::hal::TimePoint init_deadline_{};   // 초기화 예약 tick 기점 + init_timeout
    gripper::hal::TimePoint motion_deadline_{}; // 목표 write tick 기점 + motion_timeout
    gripper::hal::TimePoint last_change_at_{}; // 마지막 위치 변화 시각 — 정지 판정 창(status_grace) 기점
};

} // namespace gripper::hitbot

#endif // HITBOT_ZEFG_ZEFG_SEQUENCER_HPP_
