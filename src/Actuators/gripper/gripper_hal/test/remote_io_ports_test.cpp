// 원격 IO 백엔드 단위 시험 — 스텝 전개·범위 거부·오류 등급·극성·stale·seq 일치를 확인한다.
#include "gripper_hal_impl/remote_io_command_port.hpp"
#include "gripper_hal_impl/remote_io_feedback_port.hpp"
#include "gripper_hal_impl/remote_io_magazine_port.hpp"
#include "gripper_hal_impl/signal_map.hpp"

#include <cstdio>
#include <memory>

using namespace gripper::hal;
using namespace gripper::hal::impl;

static int fails = 0;
#define CHECK(c)                                                                                                       \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(c))                                                                                                      \
        {                                                                                                              \
            std::printf("FAIL: %s (line %d)\n", #c, __LINE__);                                                         \
            ++fails;                                                                                                   \
        }                                                                                                              \
    } while (0)

namespace
{

// 요청을 기록하고 응답을 조작하는 시험용 클라이언트.
class FakeStationIoClient : public IStationIoClient
{
  public:
    WriteAck write_bits(const std::vector<BitCommand> &commands) override
    {
        ++calls;
        last_request = commands;
        WriteAck ack;
        ack.transport_ok = transport_ok;
        ack.received = received;
        if (!transport_ok)
        {
            return ack;
        }
        for (const auto &c : commands)
        {
            ack.echo_indices.push_back(c.index + echo_index_shift);
            const bool echoed = echo_flip_level ? !c.level : c.level;
            ack.echo_states.push_back(echoed ? 1 : 0);
        }
        return ack;
    }

    StationImage image() const override
    {
        return image_;
    }

    bool link_up() const override
    {
        return link;
    }

    void set_image(StationImage img)
    {
        image_ = std::move(img);
    }

    int calls = 0;
    std::vector<BitCommand> last_request;
    bool transport_ok = true;
    bool received = true;
    bool link = true;
    int32_t echo_index_shift = 0;
    bool echo_flip_level = false;

  private:
    StationImage image_;
};

// gripper_stack.yaml signal_map 운영값과 같은 배치.
SignalMap operationalMap()
{
    SignalMap m;
    for (uint8_t b = 0; b < kStepBitCount; ++b)
    {
        m.step[b] = 80 + b;
    }
    m.control[static_cast<size_t>(ControlLine::kSetup)] = 86;
    m.control[static_cast<size_t>(ControlLine::kHold)] = 87;
    m.control[static_cast<size_t>(ControlLine::kDrive)] = 88;
    m.control[static_cast<size_t>(ControlLine::kReset)] = 89;
    m.control[static_cast<size_t>(ControlLine::kServoOn)] = 90;
    m.control[static_cast<size_t>(ControlLine::kLockRelease)] = 91;
    for (size_t i = 0; i < static_cast<size_t>(FeedbackSignal::kCount); ++i)
    {
        m.feedback[i] = static_cast<int32_t>(64 + i);
    }
    m.magazine_1 = 24;
    m.magazine_2 = 25;
    m.magazine_detected_level = 0;
    m.do_bit_count = 96; // DO 6워드 (io.info 운영값)
    m.di_bit_count = 80; // DI 5워드
    m.feedback_stale_limit = Duration{300};
    return m;
}

StationImage imageWith(size_t bit_count, uint32_t seq, TimePoint stamp)
{
    StationImage img;
    img.di.assign(bit_count, 0);
    img.do_bits.assign(bit_count, 0);
    img.seq = seq;
    img.stamp = stamp;
    img.valid = true;
    return img;
}

} // namespace

int main()
{
    const SignalMap map = operationalMap();
    CHECK(validate(map).ok);

    // 신호맵 검증: 이미지 크기 미설정·범위 밖 인덱스 거부
    {
        SignalMap no_size = map;
        no_size.do_bit_count = 0;
        CHECK(!validate(no_size).ok);

        SignalMap out_of_image = map;
        out_of_image.control[static_cast<size_t>(ControlLine::kServoOn)] = 5000;
        CHECK(!validate(out_of_image).ok);

        SignalMap di_out = map;
        di_out.magazine_2 = 80; // DI 80비트 → 인덱스 80 은 범위 밖
        CHECK(!validate(di_out).ok);
    }

    // 미검증 맵으로 만든 포트는 한 번도 송신하지 않는다(원자성·범위 보장 부재)
    {
        SignalMap split = map;
        split.step[5] = 96; // 워드 6 — 단일 RMW 불가
        CHECK(!validate(split).ok);

        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort cmd(client, split);
        CHECK(!cmd.map_valid());
        auto w = cmd.write_step(32);
        CHECK(!w && w.error() == HalError::kNotReady);
        auto l = cmd.write_line(ControlLine::kDrive, true);
        CHECK(!l && l.error() == HalError::kNotReady);
        auto c = cmd.clear_step_and_drive();
        CHECK(!c && c.error() == HalError::kNotReady);
        CHECK(client->calls == 0);
        CHECK(!cmd.health().link_up);

        RemoteIoFeedbackPort fb(client, split, [] { return TimePoint{}; });
        auto f = fb.read();
        CHECK(!f && f.error() == HalError::kNotReady);
        RemoteIoMagazinePort mgz(client, split, [] { return TimePoint{}; });
        auto m = mgz.read();
        CHECK(!m && m.error() == HalError::kNotReady);
    }

    // 신호맵 검증: 중복·미매핑·비양수 stale 은 거부
    {
        SignalMap dup = map;
        dup.control[static_cast<size_t>(ControlLine::kDrive)] = 80;
        CHECK(!validate(dup).ok);

        SignalMap unmapped = map;
        unmapped.magazine_2 = kUnmapped;
        CHECK(!validate(unmapped).ok);

        SignalMap zero_stale = map;
        zero_stale.feedback_stale_limit = Duration{0};
        CHECK(!validate(zero_stale).ok);
    }

    // 스텝 3 = IN0·IN1 ON, 나머지 OFF — 6비트가 한 요청으로 나간다
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);
        CHECK(port.write_step(3));
        CHECK(client->calls == 1);
        CHECK(client->last_request.size() == 6);
        CHECK(client->last_request[0].index == 80 && client->last_request[0].level);
        CHECK(client->last_request[1].index == 81 && client->last_request[1].level);
        CHECK(!client->last_request[2].level && !client->last_request[5].level);
    }

    // 범위 밖 스텝은 송신 없이 kOutOfRange
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);
        auto r = port.write_step(0);
        CHECK(!r && r.error() == HalError::kOutOfRange);
        auto r2 = port.write_step(64);
        CHECK(!r2 && r2.error() == HalError::kOutOfRange);
        CHECK(client->calls == 0);
    }

    // 제어 라인 구동과 kCount 거부
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);
        CHECK(port.write_line(ControlLine::kDrive, true));
        CHECK(client->last_request.size() == 1);
        CHECK(client->last_request[0].index == 88 && client->last_request[0].level);
        auto r = port.write_line(ControlLine::kCount, true);
        CHECK(!r && r.error() == HalError::kOutOfRange);
        CHECK(client->calls == 1);
    }

    // 복귀는 IN0~IN5 + DRIVE 를 한 요청에 0 으로
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);
        CHECK(port.clear_step_and_drive());
        CHECK(client->calls == 1);
        CHECK(client->last_request.size() == 7);
        bool all_low = true;
        for (const auto &c : client->last_request)
        {
            all_low = all_low && !c.level;
        }
        CHECK(all_low);
        CHECK(client->last_request[6].index == 88);
    }

    // 오류 등급: 링크 down · 미응답 · 미확정 · echo 불일치
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);

        client->link = false;
        auto down = port.write_line(ControlLine::kServoOn, true);
        CHECK(!down && down.error() == HalError::kNotReady);
        CHECK(client->calls == 0);

        client->link = true;
        client->transport_ok = false;
        auto lost = port.write_line(ControlLine::kServoOn, true);
        CHECK(!lost && lost.error() == HalError::kIndeterminate);

        client->transport_ok = true;
        client->received = false;
        auto unconfirmed = port.write_line(ControlLine::kServoOn, true);
        CHECK(!unconfirmed && unconfirmed.error() == HalError::kIndeterminate);

        client->received = true;
        client->echo_index_shift = 1;
        auto mismatched = port.write_line(ControlLine::kServoOn, true);
        CHECK(!mismatched && mismatched.error() == HalError::kProtocol);

        // 레벨 왜곡도 프로토콜 오류다 — DRIVE=0 요청에 1 을 되돌려주는 응답을 통과시키면 안 된다
        client->echo_index_shift = 0;
        client->echo_flip_level = true;
        auto flipped = port.write_line(ControlLine::kDrive, false);
        CHECK(!flipped && flipped.error() == HalError::kProtocol);
        client->echo_flip_level = false;

        CHECK(port.health().error_count == 5);
        CHECK(port.health().last_error == HalError::kProtocol);
    }

    // 피드백: 수신 이력 없으면 오류가 아니라 fresh=false
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoFeedbackPort port(client, map, [] { return TimePoint{} + Duration{1000}; });
        auto r = port.read();
        CHECK(r);
        CHECK(!r.value().fresh && r.value().seq == 0);
        CHECK(port.health().snapshot_age > map.feedback_stale_limit); // "나이 0ms" 로 보이면 오독된다
    }

    // 피드백: 정상 신호 전개 + 극성 판정
    {
        auto client = std::make_shared<FakeStationIoClient>();
        const TimePoint now = TimePoint{} + Duration{1000};
        auto img = imageWith(96, 7, now);
        img.di[74] = 1; // servo_ready
        img.di[72] = 1; // set_on
        img.di[75] = 1; // emergency_stop (negative-true: 1 = 정상)
        img.di[76] = 1; // alarm (negative-true: 1 = 정상)
        client->set_image(img);

        RemoteIoFeedbackPort port(client, map, [now] { return now + Duration{100}; });
        auto r = port.read();
        CHECK(r);
        const FeedbackSnapshot s = r.value();
        CHECK(s.fresh && s.seq == 7);
        CHECK(get(s, FeedbackSignal::kServoReady) && get(s, FeedbackSignal::kSetOn));
        CHECK(alarm_state(s) == SignalState::kInactive);
        CHECK(emergency_stop_state(s) == SignalState::kInactive);
        CHECK(is_ready_for_drive(s));
        CHECK(port.health().last_seq == 7);
    }

    // 피드백: stale 한계를 넘으면 fresh=false 이고 판정은 kUnknown
    {
        auto client = std::make_shared<FakeStationIoClient>();
        const TimePoint now = TimePoint{} + Duration{1000};
        auto img = imageWith(96, 8, now);
        img.di[76] = 1;
        client->set_image(img);

        RemoteIoFeedbackPort port(client, map, [now] { return now + Duration{301}; });
        auto r = port.read();
        CHECK(r);
        CHECK(!r.value().fresh);
        CHECK(alarm_state(r.value()) == SignalState::kUnknown);
        CHECK(!is_ready_for_drive(r.value()));
    }

    // 피드백: 이미지가 신호 인덱스를 못 담으면 kProtocol
    {
        auto client = std::make_shared<FakeStationIoClient>();
        client->set_image(imageWith(70, 9, TimePoint{}));
        RemoteIoFeedbackPort port(client, map, [] { return TimePoint{}; });
        auto r = port.read();
        CHECK(!r && r.error() == HalError::kProtocol);
        CHECK(port.health().error_count == 1);
    }

    // 매거진: 원시 0 = 감지(NC), 같은 이미지면 피드백과 seq 가 일치
    {
        auto client = std::make_shared<FakeStationIoClient>();
        const TimePoint now = TimePoint{} + Duration{1000};
        auto img = imageWith(96, 11, now);
        img.di[24] = 0; // 감지
        img.di[25] = 1; // 미감지
        img.di[76] = 1;
        img.di[75] = 1;
        client->set_image(img);

        const auto clock = [now] { return now + Duration{50}; };
        RemoteIoMagazinePort mgz(client, map, clock);
        RemoteIoFeedbackPort fb(client, map, clock);

        auto m = mgz.read();
        auto f = fb.read();
        CHECK(m && f);
        CHECK(m.value().detected_1 && !m.value().detected_2);
        CHECK(!both_detected(m.value()) && any_detected(m.value()));
        CHECK(same_image(f.value(), m.value()));
    }

    // 매거진: 극성이 뒤집힌 변형에서는 1 이 감지
    {
        auto client = std::make_shared<FakeStationIoClient>();
        const TimePoint now = TimePoint{} + Duration{1000};
        auto img = imageWith(96, 12, now);
        img.di[24] = 1;
        img.di[25] = 1;
        client->set_image(img);

        SignalMap inverted = map;
        inverted.magazine_detected_level = 1;
        img.di[24] = 0xFF; // 0/1 이 아닌 원시값도 "참"으로 정규화되어야 한다
        client->set_image(img);
        RemoteIoMagazinePort mgz(client, inverted, [now] { return now; });
        auto m = mgz.read();
        CHECK(m && both_detected(m.value()));
    }

    // 링크가 끊기면 캐시 이미지가 아무리 최신이어도 fresh 가 아니다
    {
        auto client = std::make_shared<FakeStationIoClient>();
        const TimePoint now = TimePoint{} + Duration{1000};
        auto img = imageWith(96, 13, now);
        img.di[74] = 1;
        img.di[72] = 1;
        img.di[75] = 1;
        img.di[76] = 1;
        img.di[24] = 0;
        img.di[25] = 0;
        client->set_image(img);
        const auto clock = [now] { return now + Duration{10}; };

        RemoteIoFeedbackPort fb(client, map, clock);
        RemoteIoMagazinePort mgz(client, map, clock);
        auto f_up = fb.read();
        CHECK(f_up && f_up.value().fresh && is_ready_for_drive(f_up.value()));

        client->link = false;
        auto f_down = fb.read();
        auto m_down = mgz.read();
        CHECK(f_down && !f_down.value().fresh);
        CHECK(alarm_state(f_down.value()) == SignalState::kUnknown);
        CHECK(!is_ready_for_drive(f_down.value()));
        CHECK(m_down && !m_down.value().fresh && !both_detected(m_down.value()));
    }

    // 신호맵 검증: 한 요청으로 나가는 비트가 워드를 넘으면 거부(단일 RMW 불가)
    {
        SignalMap split = map;
        split.step[5] = 96; // 워드 6 — IN0~IN4 는 워드 5
        CHECK(!validate(split).ok);

        SignalMap drive_elsewhere = map;
        drive_elsewhere.control[static_cast<size_t>(ControlLine::kDrive)] = 100;
        CHECK(!validate(drive_elsewhere).ok);
    }

    // 미확정이 프로토콜 위반보다 우선한다
    {
        auto client = std::make_shared<FakeStationIoClient>();
        RemoteIoCommandPort port(client, map);
        client->received = false;
        client->echo_index_shift = 1;
        auto r = port.write_line(ControlLine::kServoOn, true);
        CHECK(!r && r.error() == HalError::kIndeterminate);
    }

    // 클라이언트가 비어 있으면 송신 없이 kNotReady
    {
        RemoteIoCommandPort port(nullptr, map);
        auto r = port.write_step(1);
        CHECK(!r && r.error() == HalError::kNotReady);
        RemoteIoFeedbackPort fb(nullptr, map, [] { return TimePoint{}; });
        auto f = fb.read();
        CHECK(f && !f.value().fresh);
        RemoteIoMagazinePort mgz(nullptr, map, [] { return TimePoint{}; });
        auto m = mgz.read();
        CHECK(m && !m.value().fresh);
        CHECK(mgz.health().snapshot_age > map.feedback_stale_limit);
    }

    std::printf(fails ? "FAILED: %d\n" : "ALL PASS (%d fail)\n", fails);
    return fails ? 1 : 0;
}
