// zefg_plant.cpp — ZefgPlant 구현. 시맨틱스·실측 근거는 zefg_plant.hpp 머리주석 참조
// (HIL H0 실측 기록, src/Actuators/gripper/docs/hil/).
#include "hitbot_zefg/zefg_plant.hpp"

#include <cmath>
#include <cstddef>
#include <utility>
#include <vector>

#include "hitbot_zefg/zefg_registers.hpp"
#include "modbus_rtu/mock_slave.hpp"

namespace gripper::hitbot::sim
{

namespace mrtu = comm::modbus_rtu;

// ISerialLink 데코레이터 — 전 호출을 내장 MockSlaveLink 에 위임하되, write 프레임(fc06/fc10)에서
// 초기화 명령(0x0000=1)·목표 위치(0x0002) write 를 검출해 PendingCommands 에 래치한다.
// 상태를 즉시 전이시키지 않는다(래치 시맨틱스) — 소비는 ZefgPlant::step() 이 한다.
// 요청 파싱은 rtu_frame 파서를 재사용하지 않는다(MockSlaveLink 와 동일한 테스트 이중 구현 원칙).
class ZefgPlant::CommandObserverLink : public mrtu::ISerialLink
{
  public:
    CommandObserverLink(std::shared_ptr<mrtu::sim::MockSlaveLink> inner, std::shared_ptr<PendingCommands> pending)
        : inner_(std::move(inner)), pending_(std::move(pending))
    {
    }

    mrtu::Result<void> writeBytes(const std::vector<uint8_t> &data) override
    {
        observe(data);
        return inner_->writeBytes(data);
    }

    mrtu::Result<std::vector<uint8_t>> readBytes(size_t max_len, mrtu::TimePoint deadline) override
    {
        return inner_->readBytes(max_len, deadline);
    }

    void flushInput() override
    {
        inner_->flushInput();
    }

    bool isOpen() const override
    {
        return inner_->isOpen();
    }

  private:
    // 최소 파싱: unit(0)·fc(1)·addr(2,3)·워드(4,5). CRC·정식 응답 조립은 슬레이브 모형 소관.
    void observe(const std::vector<uint8_t> &frame)
    {
        if (frame.size() < 6 || frame[0] != kPlantUnitId)
            return;
        const uint8_t fc = frame[1];
        if (fc != 0x06 && fc != 0x10)
            return;
        const auto addr = static_cast<uint16_t>((frame[2] << 8) | frame[3]);
        const auto word = static_cast<uint16_t>((frame[4] << 8) | frame[5]);
        const uint16_t qty = (fc == 0x10) ? word : 1;
        const auto covers = [addr, qty](uint16_t reg) { return reg >= addr && reg < addr + qty; };
        if (covers(kRegTargetPosition))
            pending_->target = true;
        if (covers(kRegInitCommand) && writtenWord(fc, frame, addr, kRegInitCommand) == 1)
            pending_->init = true; // 1=초기화 [p5]
    }

    static uint16_t writtenWord(uint8_t fc, const std::vector<uint8_t> &frame, uint16_t addr, uint16_t reg)
    {
        if (fc == 0x06)
            return static_cast<uint16_t>((frame[4] << 8) | frame[5]);
        const size_t idx = 7 + 2 * static_cast<size_t>(reg - addr); // fc10 데이터부: byte 7 부터 워드열
        if (idx + 1 >= frame.size())
            return 0;
        return static_cast<uint16_t>((frame[idx] << 8) | frame[idx + 1]);
    }

    std::shared_ptr<mrtu::sim::MockSlaveLink> inner_;
    std::shared_ptr<PendingCommands> pending_;
};

ZefgPlant::ZefgPlant(PlantConfig cfg)
    : cfg_(cfg), slave_(std::make_shared<mrtu::sim::MockSlaveLink>(kPlantUnitId)),
      pending_(std::make_shared<PendingCommands>()), observer_(std::make_shared<CommandObserverLink>(slave_, pending_))
{
    setPowerOnInitialized(true); // HIL H0: 전원 인가 시 자동 초기화 완료(0x0040=5) 관측 — 기본 시작 상태
}

std::shared_ptr<mrtu::ISerialLink> ZefgPlant::link()
{
    return observer_;
}

void ZefgPlant::setPowerOnInitialized(bool initialized)
{
    init_raw_ = initialized ? 5U : 0U; // 5=완료 / 0=미초기화 [p5]
    clamp_raw_ = 0;                    // InPlace — HIL H0: 유휴 시 0 관측
    position_mm_ = cfg_.initial_position_mm; // 미초기화 시 위치 피드백 실측 미보유 ⚠ — 초기 위치 유지 모형
    speed_fb_mms_ = 0.0F;
    current_fb_a_ = 0.0F;
    moving_ = false;
    init_ticks_left_ = 0;
    pending_->init = false;
    pending_->target = false;
    syncRegisters();
}

void ZefgPlant::insertObstacleAt(float mm)
{
    has_obstacle_ = true;
    obstacle_mm_ = mm;
}

void ZefgPlant::dropObject()
{
    // 낙하 상태는 다음 모션 시작까지 래치 — HIL H0 재수행: 유휴 중에도 clamp=Dropping 유지 관측.
    clamp_raw_ = 3; // Dropping [p5]
    moving_ = false;
    has_obstacle_ = false;
    speed_fb_mms_ = 0.0F;
    current_fb_a_ = 0.0F;
    syncRegisters();
}

void ZefgPlant::step()
{
    // 1) 수신 명령 소비 — 래치 시맨틱스: 전이는 write 수신 시점이 아니라 여기서 일어난다
    //    (HIL §백드라이브·힘 순응 실측 — 직전 래치 상태가 write 후 첫 폴링까지 유지).
    if (pending_->init)
    {
        pending_->init = false;
        init_raw_ = 1; // "기타 진행중" [p5] — 구체 진행값 실측 미보유 ⚠, 1 로 모형화
        init_ticks_left_ = kPlantInitTicks;
        moving_ = false;
    }
    else if (init_ticks_left_ > 0)
    {
        --init_ticks_left_;
        if (init_ticks_left_ == 0)
        {
            init_raw_ = 5; // 완료 [p5]
            clamp_raw_ = 0;
            position_mm_ = cfg_.initial_position_mm; // HIL H0: 초기화 완료 후 표시 35.0mm 관측
        }
    }

    // 2) 목표 소비 또는 램프 진행.
    if (pending_->target)
    {
        pending_->target = false;
        if (init_raw_ == 5)
            beginMotion();
        // 미초기화 상태의 목표 write 는 무시 ⚠ — 매뉴얼 p5 에 미초기화 동작 명세 없음(보수적 모형).
    }
    else if (moving_)
    {
        advanceMotion();
    }

    syncRegisters();
}

// 동일 위치 판정 허용 오차 — 레지스터 float 왕복의 부동소수 오차만 흡수한다(무이동 명령 모형 전용).
constexpr float kSamePositionEpsMm = 1e-3F;

void ZefgPlant::beginMotion()
{
    motion_target_mm_ =
        wordsToFloat(slave_->reg(kRegTargetPosition), slave_->reg(static_cast<uint16_t>(kRegTargetPosition + 1)));
    // 무이동 명령(실기 재현 — HIL: 열림 0.0mm 에 Dropping 이 래치된 상태에서 0.0mm 를 재명령하면 장치는
    // 움직이지 않고 0x0041 도 갱신하지 않는다): 목표가 현재 위치와 같으면 kMoving 전이·InPlace 갱신
    // 없이 직전 래치 상태·위치·속도 피드백을 그대로 유지한다. 판정은 동일 위치(오차 1e-3mm)로 한정 —
    // 스텝 미만 미소 이동 시 장치 거동은 실측 미보유 ⚠(모형은 통상 램프로 처리).
    if (std::fabs(motion_target_mm_ - position_mm_) <= kSamePositionEpsMm)
        return;
    const float speed =
        wordsToFloat(slave_->reg(kRegTargetSpeed), slave_->reg(static_cast<uint16_t>(kRegTargetSpeed + 1)));
    motion_current_a_ =
        wordsToFloat(slave_->reg(kRegTargetCurrent), slave_->reg(static_cast<uint16_t>(kRegTargetCurrent + 1)));
    motion_start_mm_ = position_mm_;

    // tick 당 진행량·총 tick 수는 double 로 산출 — float 로 계산하면 20mm/s×10ms 가 0.2 아래로
    // 반올림되어 총 tick 이 1 늘어난다(결정론 계약: tick 수 = ceil(거리/속도/tick), 계획 §Task 2).
    const double tick_s = static_cast<double>(cfg_.tick.count()) / 1000.0;
    const double step_mm = static_cast<double>(speed) * tick_s;
    const double distance = std::fabs(static_cast<double>(motion_target_mm_) - static_cast<double>(motion_start_mm_));
    const float dir = (motion_target_mm_ >= motion_start_mm_) ? 1.0F : -1.0F;
    motion_step_mm_ = dir * static_cast<float>(step_mm);
    motion_step_abs_mm_ = step_mm; // 장애물 도달 tick 산출도 같은 double 값으로(결정론 일관성)
    motion_tick_ = 0;
    motion_total_ticks_ = (step_mm > 0.0) ? static_cast<int>(std::ceil(distance / step_mm)) : 0;
    moving_ = true;
    clamp_raw_ = 1; // Moving [p5] — 여기(목표 소비 step)에서 비로소 전이(래치 시맨틱스)
    speed_fb_mms_ = speed; // 모형은 명령 속도를 그대로 피드백(실측 평균 기울기 차이는 HIL ⚠ 기록 참조)
    current_fb_a_ = motion_current_a_;
}

void ZefgPlant::advanceMotion()
{
    ++motion_tick_;

    // 장애물 우선 판정(경로 위에 있으면 목표 도달보다 먼저 만난다) — 도달 시 파지: 위치 고정.
    // 도달 tick 은 beginMotion 총 tick 과 동일하게 double 기반 정수 산출(리뷰 Minor — float 거리
    // 비교는 나눠떨어지지 않는 조합에서 반올림으로 tick 이 어긋날 수 있다).
    const bool toward_increase = motion_step_mm_ > 0.0F;
    const bool obstacle_on_path =
        has_obstacle_ && (toward_increase ? (obstacle_mm_ > motion_start_mm_ && obstacle_mm_ <= motion_target_mm_)
                                          : (obstacle_mm_ < motion_start_mm_ && obstacle_mm_ >= motion_target_mm_));
    const double obstacle_dist = std::fabs(static_cast<double>(obstacle_mm_) - static_cast<double>(motion_start_mm_));
    const int obstacle_ticks =
        (motion_step_abs_mm_ > 0.0) ? static_cast<int>(std::ceil(obstacle_dist / motion_step_abs_mm_)) : 0;
    if (obstacle_on_path && motion_tick_ >= obstacle_ticks)
    {
        position_mm_ = obstacle_mm_;
        moving_ = false;
        clamp_raw_ = 2; // Clamping [p5] — 전류 제한으로 유지(HIL §백드라이브: 유지 = 순응 거동)
        speed_fb_mms_ = 0.0F;
        current_fb_a_ = motion_current_a_; // 유지 전류 모형 — 실측은 제한 부근 변동(§백드라이브)
        return;
    }

    if (motion_tick_ >= motion_total_ticks_)
    {
        position_mm_ = motion_target_mm_;
        moving_ = false;
        clamp_raw_ = 0; // InPlace [p5]
        speed_fb_mms_ = 0.0F;
        current_fb_a_ = 0.0F; // 유휴 모형(실측 유휴 전류는 미소 오프셋 — HIL H0)
        return;
    }

    position_mm_ = motion_start_mm_ + motion_step_mm_ * static_cast<float>(motion_tick_);
}

void ZefgPlant::syncRegisters()
{
    slave_->setRegister(kRegInitStatus, init_raw_);
    slave_->setRegister(kRegClampStatus, clamp_raw_);
    const auto pos = floatToWords(position_mm_); // {hi, lo} — 상위워드 우선(실측 0x420C0000=35.0)
    slave_->setRegister(kRegPositionFb, pos[0]);
    slave_->setRegister(static_cast<uint16_t>(kRegPositionFb + 1), pos[1]);
    const auto spd = floatToWords(speed_fb_mms_);
    slave_->setRegister(kRegSpeedFb, spd[0]);
    slave_->setRegister(static_cast<uint16_t>(kRegSpeedFb + 1), spd[1]);
    const auto cur = floatToWords(current_fb_a_);
    slave_->setRegister(kRegCurrentFb, cur[0]);
    slave_->setRegister(static_cast<uint16_t>(kRegCurrentFb + 1), cur[1]);
}

} // namespace gripper::hitbot::sim
