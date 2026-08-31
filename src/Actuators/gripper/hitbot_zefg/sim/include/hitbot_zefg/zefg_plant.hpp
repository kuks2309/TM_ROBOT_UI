// zefg_plant.hpp — Z-EFG-C35 결정론 플랜트(SIL, Software-In-the-Loop). MockSlaveLink 를 내장해
// 레지스터 시맨틱스를 모형화하고, link() 로 노출한 ISerialLink 를 진짜 RtuClient 에 주입한다 —
// mock/실기 모두 같은 RtuClient·ZefgHal 코드 경로를 지난다(ADR-005 단계④, 단계③ 검증 사슬 승계).
//
// 시맨틱스 실측 근거(HIL H0 실측 기록, src/Actuators/gripper/docs/hil/):
// - 전원 인가 시 자동 초기화 완료(0x0040=5)·위치 표시 35.0mm 관측 — setPowerOnInitialized(true) 기본.
// - 래치 유지: 새 목표 위치 write 후에도 직전 모션의 최종 상태(0x0041, 예: Dropping)는 실제 이동이
//   시작되기 전까지 유지된다(§백드라이브·힘 순응 실측 — 새 모션 write 후 첫 폴링이 직전 래치
//   Dropping 을 그대로 읽은 실기 관측). 본 플랜트도 write 즉시가 아니라 다음 step() 에서 kMoving 전이.
// - 파지(Clamping) 유지 전류는 전류 제한 부근에서 변동(§백드라이브) — 모형은 목표 전류로 고정.
// - Dropping 은 다음 모션 시작까지 래치(H0 재수행: 유휴 중에도 clamp=Dropping 유지 관측).
// - 무이동 명령: 목표가 현재 위치와 같으면 장치는 움직이지 않고 0x0041 도 갱신하지 않는다(실기 재현:
//   열림 0.0mm·Dropping 래치에서 0.0mm 재명령 → 상태 불변). 플랜트도 kMoving 전이 없이 래치 유지.
// - 라벨 지연(§상태 레지스터 갱신 지연 실측): Dropping 래치 출발 이동은 실제 이동 중에도 0x0041 이
//   ≥1초 Dropping 을 유지하다 목표 직전에서야 Moving 후 In place 로 갱신된다(In place 출발은 50ms 내
//   Moving). 플랜트는 Dropping 출발 시 이동 중 라벨을 Dropping 으로 유지하고 남은 거리 ≤ 1 스텝에서
//   kMoving 1 tick 후 kInPlace 로 모형화. Clamping 래치 출발의 지연 여부는 ⚠ 미실측 — 확장하지 않음.
// - 한계(모형 단순화): 실기 Clamping 은 외력이 사라지면 목표로 복귀해 InPlace 가 되는 과도 상태
//   이기도 하다(§백드라이브·힘 순응 실측: 외력 제거 시 자동 복귀 관측) — 본 플랜트는 장애물 도달
//   시 kClamping 종결(위치 고정)로 단순화한다. 복귀 거동 모형화는 후속 필요 시(리뷰 F2).
#ifndef HITBOT_ZEFG_ZEFG_PLANT_HPP_
#define HITBOT_ZEFG_ZEFG_PLANT_HPP_

#include <cstdint>
#include <memory>

#include "modbus_rtu/rtu_types.hpp"   // Duration
#include "modbus_rtu/serial_link.hpp" // ISerialLink

namespace comm::modbus_rtu::sim
{
class MockSlaveLink; // 내장 목 슬레이브 — 정의는 modbus_rtu/mock_slave.hpp(cpp 에서만 포함)
}

namespace gripper::hitbot::sim
{

struct PlantConfig
{
    float initial_position_mm = 35.0F; // 초기화 완료 시 위치 — HIL H0: 전원 인가 후 표시 35.0mm 관측
    comm::modbus_rtu::Duration tick{10}; // step() 1회가 진행시키는 모형 시간
};

// 초기화 명령 소비(kInitializing 전이 step) 후 완료(0x0040=5)까지 추가 step 수.
// 실기 소요시간 실측 미보유(전원 인가 자동 초기화라 별도 관측 없음) ⚠ — 결정론 sim 값.
inline constexpr int kPlantInitTicks = 5;

// RTU unit id — HIL H0: 0x0080 slave ID = 1(공장 기본값) 판독.
inline constexpr uint8_t kPlantUnitId = 1;

class ZefgPlant
{
  public:
    explicit ZefgPlant(PlantConfig cfg = {});

    // 내부 MockSlaveLink 를 명령 관찰 데코레이터로 감싼 링크 — RtuClient 에 주입한다.
    std::shared_ptr<comm::modbus_rtu::ISerialLink> link();

    // tick 1회: 수신 명령 소비(초기화/목표 — 래치 시맨틱스로 이 시점에 전이), 초기화 진행,
    // 목표를 향한 speed×tick 위치 램프, 상태·피드백 레지스터 갱신.
    void step();

    void insertObstacleAt(float mm); // 파지 모형: 이동 경로 장애물 — 도달 시 kClamping·위치 고정
    void dropObject();               // 낙하 주입 — kDropping 래치(다음 모션 시작까지 유지)
    void setPowerOnInitialized(bool initialized); // true(기본): 초기화 완료 상태 시작 / false: 미초기화

  private:
    class CommandObserverLink; // ISerialLink 데코레이터 — write 프레임에서 명령 이벤트 검출(cpp 정의)
    struct PendingCommands
    {
        bool init = false;   // 0x0000=1 write 수신 [p5]
        bool target = false; // 0x0002(목표 위치) write 수신 — position 이 모션 트리거 [p6 예제 순서]
    };

    void syncRegisters(); // 상태·피드백을 0x0040~0x0047 에 반영(float 상위워드 우선, floatToWords 재사용)
    void beginMotion();   // 목표 write 소비 — kMoving 전이 + 램프 파라미터 확정
    void advanceMotion(); // 램프 1 tick: 장애물 도달 kClamping / 목표 도달 kInPlace

    PlantConfig cfg_;
    std::shared_ptr<comm::modbus_rtu::sim::MockSlaveLink> slave_;
    std::shared_ptr<PendingCommands> pending_;
    std::shared_ptr<comm::modbus_rtu::ISerialLink> observer_;

    uint16_t init_raw_ = 0;  // 0x0040 원시값 (0 미초기화 / 5 완료 / 기타 진행중 [p5])
    uint16_t clamp_raw_ = 0; // 0x0041 원시값 — 래치: step()·주입 API 에서만 갱신
    float position_mm_ = 0.0F;
    float speed_fb_mms_ = 0.0F;
    float current_fb_a_ = 0.0F;

    int init_ticks_left_ = 0;
    bool moving_ = false;
    bool label_delay_ = false; // Dropping 래치 출발 이동 — 이동 중 라벨 Dropping 유지(§상태 레지스터 갱신 지연)
    float motion_start_mm_ = 0.0F;
    float motion_target_mm_ = 0.0F;
    float motion_step_mm_ = 0.0F;     // 부호 포함(진행 방향) — 위치 램프용
    double motion_step_abs_mm_ = 0.0; // 크기(double) — tick 수 산출 전용(결정론 계약, 리뷰 Minor)
    float motion_current_a_ = 0.0F;
    int motion_tick_ = 0;
    int motion_total_ticks_ = 0;
    bool has_obstacle_ = false;
    float obstacle_mm_ = 0.0F;
};

} // namespace gripper::hitbot::sim

#endif // HITBOT_ZEFG_ZEFG_PLANT_HPP_
