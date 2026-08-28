// LECP6 병렬 I/O 플랜트 모형 — 명령 비트를 받아 물리 상태와 13신호 피드백을 만든다.
//
// 시험이 플랜트를 직접 관찰한다(위치·알람 코드). 포트를 통해서만 보면 «장치가 실제로 그렇게
// 됐는가» 를 단언할 수 없다.
#ifndef GRIPPER_SIM_LECP6_PLANT_HPP_
#define GRIPPER_SIM_LECP6_PLANT_HPP_

#include <array>
#include <cstdint>
#include <utility>

#include "gripper_hal/types.hpp"

namespace gripper::sim
{

using hal::ControlLine;
using hal::Duration;
using hal::FeedbackSignal;

inline constexpr uint8_t kRegisteredSteps = 3;

struct StepData
{
    int32_t target_position = 0; // 임의 단위 — 열림이 클수록 큰 값
    Duration travel_time{0};     // 그 스텝까지 이동에 걸리는 시간
    bool pushing = false;        // 푸싱 동작이면 반력이 있어야 INP 가 선다
};

struct PlantConfig
{
    // 등록 스텝 1·2·3. close 가 길고 open 이 짧은 실측 경향을 반영한다.
    std::array<StepData, kRegisteredSteps> steps{};
    Duration busy_rise_delay{20};
    Duration origin_travel{400};
    Duration alarm_after_stalled{2500}; // 원점 미확립 구동이 알람으로 가는 시간
    int32_t magazine_grip_position = 0; // 이 위치 이하로 닫히면 매거진을 문 것으로 본다
};

class Lecp6Plant
{
  public:
    explicit Lecp6Plant(const PlantConfig &config) : cfg_(config)
    {
    }

    void setLine(ControlLine line, bool level);
    void setStep(uint8_t step);
    void advance(int64_t ms);

    uint16_t feedbackBits() const;
    std::pair<bool, bool> magazineDetected() const;

    void placeMagazine()
    {
        magazine_present_ = true;
    }
    void removeMagazine()
    {
        magazine_present_ = false;
        magazine_held_ = false;
    }
    // 2점 감지는 서로 독립인 센서다 — 한쪽만 서는 상황(정렬 틀어짐·배선 단선)을 재현한다.
    void setSensor2Enabled(bool enabled)
    {
        sensor_2_enabled_ = enabled;
    }
    // 시험이 임의로 알람을 주입한다(동작 중 이상 재현).
    void injectAlarm(uint8_t group)
    {
        alarm_group_ = group;
        alarm_ = true;
        servo_ready_ = false;
        busy_ = false;
        motion_active_ = false;
    }

    int32_t position() const
    {
        return position_;
    }
    uint8_t alarmCode() const
    {
        return alarm_ ? alarm_group_ : 0;
    }
    bool servoReady() const
    {
        return servo_ready_;
    }
    bool originEstablished() const
    {
        return origin_established_;
    }
    bool busy() const
    {
        return busy_;
    }
    // 컨트롤러가 지금 받고 있는 DRIVE 레벨 — 잔류 지령 유무를 시험이 직접 본다.
    int driveLevel() const
    {
        return drive_ ? 1 : 0;
    }
    // 입력 이미지 번호 — 피드백·매거진 스냅샷이 공유해야 same_image 판정이 선다.
    uint32_t imageSeq() const
    {
        return image_seq_;
    }

  private:
    void startMotion(int32_t target, Duration travel, bool pushing, bool is_origin);
    void finishMotion();

    PlantConfig cfg_;
    int64_t now_ms_ = 0;
    uint32_t image_seq_ = 1;

    bool svon_ = false;
    bool setup_ = false;
    bool drive_ = false;
    bool reset_ = false;
    uint8_t selected_step_ = 0;

    bool servo_ready_ = false;
    bool origin_established_ = false;
    bool busy_ = false;
    bool in_position_ = false;
    bool alarm_ = false;
    uint8_t alarm_group_ = 0;
    uint8_t executed_step_ = 0;

    int32_t position_ = 0;
    int32_t motion_target_ = 0;
    bool motion_pushing_ = false;
    int64_t motion_end_ms_ = 0;
    int64_t drive_edge_ms_ = -1;
    int64_t stall_start_ms_ = -1;
    bool motion_active_ = false;
    bool motion_is_origin_ = false;

    bool magazine_present_ = false;
    bool magazine_held_ = false;
    bool sensor_2_enabled_ = true;
};

} // namespace gripper::sim

#endif // GRIPPER_SIM_LECP6_PLANT_HPP_
