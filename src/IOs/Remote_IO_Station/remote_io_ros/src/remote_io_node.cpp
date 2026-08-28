// remote_io_node — Remote IO Station 의 ROS 조립층 (remote_io M4)
//
// 역할은 **얇은 조립**뿐이다. Modbus 접근·RMW·read-back·watchdog 은 전부 remote_io_hal 소유이고,
// 본 노드는 (a) 20ms 주기 구동 (b) legacy tc_io 공개 계약(io_resp/io_service/io_alarms) 변환
// (c) 기동 초기값 1회 적용 만 한다.
//
// 계약 파리티 근거: M0 인벤토리 §3·§4. 개선 이탈(DL)은 README 에 등재한다 — 요약하면
//  - legacy 의 read→unlock→write 비원자 구간이 없다(포트가 로컬 미러로 RMW, 단일 writer).
//  - legacy 의 while(true) 재연결 스레드가 없다(유계 백오프 + 노드 수명 소유).
//  - 읽기 실패 시 **발행하지 않는다** — legacy 는 실패해도 직전 값을 계속 내보냈다(§6-5).
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <cstring>
#include <chrono>
#include <memory>
#include <cstdio>
#include <string>
#include <thread>
#include <vector>

#include <rclcpp/rclcpp.hpp>
#include <tc_msgs/msg/amr_alarm.hpp>
#include <tc_msgs/msg/io.hpp>
#include <tc_msgs/srv/io.hpp>

#include "io_contract.hpp"
#include "remote_io_hal/remote_io_station_port.hpp"

namespace
{

using namespace std::chrono_literals;
namespace rio = remote_io::hal;
namespace rc = remote_io::ros_assembly;

// 스테이션 쓰기 마스터 단일성을 **프로세스 수준에서** 강제한다(ADR-003 Proposed).
// 토픽 수신 기반 판정은 소유권의 대리 지표일 뿐이다 — 스테이션 미도달이면 살아 있는 마스터도
// 발행이 0이라 "없음" 으로 오판되어 인스턴스가 누적된다. 추상 유닉스 소켓은 커널이 이름의
// 유일성을 보장하고 프로세스 종료 시 자동 해제되므로 잔여 lockfile 문제가 없다.
int acquireSingleInstanceLock(const std::string &name)
{
    const int fd = ::socket(AF_UNIX, SOCK_DGRAM | SOCK_CLOEXEC, 0);
    if (fd < 0)
        return -1;
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    // sun_path[0] = '\0' → 추상 네임스페이스(파일시스템 흔적 없음)
    const size_t n = std::min(name.size(), sizeof(addr.sun_path) - 2);
    std::memcpy(addr.sun_path + 1, name.data(), n);
    const socklen_t len = static_cast<socklen_t>(offsetof(sockaddr_un, sun_path) + 1 + n);
    if (::bind(fd, reinterpret_cast<sockaddr *>(&addr), len) < 0)
    {
        ::close(fd);
        return -1; // 이미 다른 인스턴스가 잡고 있다
    }
    return fd;
}

class RemoteIoNode : public rclcpp::Node
{
  public:
    RemoteIoNode() : rclcpp::Node("remote_io_node")
    {
        // ── 파라미터 (io.info 실측값을 기본값으로, 하드코딩 상수 없음) ──
        const auto ip = declare_parameter<std::string>("station.ip", "192.168.192.14");
        const int port = static_cast<int>(declare_parameter<int>("station.port", 502));
        di_word_count_ = static_cast<uint16_t>(declare_parameter<int>("layout.di_word_count", 5));
        do_word_count_ = static_cast<uint16_t>(declare_parameter<int>("layout.do_word_count", 6));
        const auto di_start = declare_parameter<int>("layout.di_start_addr", 0);
        const auto do_start = declare_parameter<int>("layout.do_start_addr", 2048);
        period_ms_ = declare_parameter<int>("publish_period_ms", 20);
        write_retries_ = declare_parameter<int>("write.retries", 3);
        write_backoff_ms_ = declare_parameter<int>("write.backoff_ms", 100);
        // 기동 초기 ON 비트 — **목록은 config 소유**. 기본값은 legacy 실측 8비트(인벤토리 §4).
        initial_on_bits_ = declare_parameter<std::vector<int64_t>>(
            "initial_on_bits", std::vector<int64_t>{1, 3, 5, 9, 11, 13, 90, 94});
        // 초기 이미지 적용 여부 — **기본 false(읽기 전용 기동)**.
        // DO 는 실제 장치를 구동하므로, 링크가 붙었다는 이유만으로 출력을 바꾸면 안 된다.
        // 전환 절차(cutover S1)는 쓰기 0 상태로 발행 파리티부터 확인한다. 운용 전환(S4)에서만 true.
        apply_initial_image_ = declare_parameter<bool>("apply_initial_image", false);
        // 워치독 — 마스터 두절 시 커플러가 출력을 안전 상태로 떨어뜨리는 장치 보호.
        // **기본 0 = 비활성**(현행 동작 유지). 값 자체는 현장 안전 정책이라 사용자 소유다.
        watchdog_timeout_ms_ = declare_parameter<int>("watchdog.timeout_ms", 0);
        watchdog_fault_action_ = declare_parameter<bool>("watchdog.master_fault_action", false);

        rio::StationLayout layout;
        layout.di_start_addr = static_cast<uint16_t>(di_start);
        layout.di_word_count = di_word_count_;
        layout.do_start_addr = static_cast<uint16_t>(do_start);
        layout.do_word_count = do_word_count_;

        rio::RemoteIoStationPort::Config cfg;
        cfg.client.host = ip;
        cfg.client.port = static_cast<uint16_t>(port);
        cfg.layout = layout;
        cfg.clock = [] { return std::chrono::steady_clock::now(); };
        port_ = std::make_unique<rio::RemoteIoStationPort>(cfg);

        io_pub_ = create_publisher<tc_msgs::msg::Io>("io_resp", 10);
        alarm_pub_ = create_publisher<tc_msgs::msg::AmrAlarm>("io_alarms", 10);
        srv_ = create_service<tc_msgs::srv::Io>(
            "io_service", [this](const std::shared_ptr<tc_msgs::srv::Io::Request> req,
                                 std::shared_ptr<tc_msgs::srv::Io::Response> res) {
                handleWrite(*req, *res);
            });

        timer_ = create_wall_timer(std::chrono::milliseconds(period_ms_), [this] { tick(); });
        RCLCPP_INFO(get_logger(), "remote_io_node 기동 — %s:%d DI %uw DO %uw, 주기 %dms", ip.c_str(),
                    port, static_cast<unsigned>(di_word_count_),
                    static_cast<unsigned>(do_word_count_), period_ms_);
    }

  private:
    // ── 20ms 틱 ──
    void tick()
    {
        auto snap = port_->read();

        rc::TickInput in;
        in.read_ok = static_cast<bool>(snap);
        in.err = snap ? rio::RemoteIoError::kNone : snap.error();
        in.was_connected = was_connected_;
        in.mirror_seeded = mirror_seeded_;
        in.initial_applied = initial_applied_;
        in.apply_initial_image = apply_initial_image_;
        in.watchdog_timeout_ms = watchdog_timeout_ms_;
        in.watchdog_configured = watchdog_configured_;
        in.current_error = error_code_;

        const auto plan = rc::planTick(in);   // 결정은 순수 함수가 소유한다(단위시험 대상)
        error_code_ = plan.error_code;

        if (!plan.publish_io)
        {
            // 읽기 실패 — 직전 값을 다시 내보내지 않는다(legacy §6-5 차단).
            was_connected_ = false;
            publishAlarmIfNeeded(false);
            return;
        }
        was_connected_ = true;

        if (plan.seed_mirror)
        {
            // 미러 기본값은 0 이라, 시드 없이 비트 하나만 써도 나머지 출력이 전부 0 으로 덮인다.
            // read() 의 do_words 는 포트 재기록 **이전** 관측값이라 재연결마다 시드하면
            // 재기록 결과를 덮는다 — 그래서 최초 1회만이다.
            if (auto sr = port_->seedOutputMirror(snap.value().do_words); !sr)
                RCLCPP_ERROR(get_logger(), "출력 미러 시드 실패(err=%d) — 쓰기 금지 상태",
                             static_cast<int>(sr.error()));
            else
            {
                mirror_seeded_ = true;
                RCLCPP_INFO(get_logger(), "출력 미러 시드(최초 1회) — 장치 관측 이미지 %zu워드",
                            snap.value().do_words.size());
            }
        }
        else if (plan.reconnected)
        {
            RCLCPP_INFO(get_logger(), "재연결 — 미러 재시드 안 함(포트 재기록이 이미지 소유)");
        }

        if (plan.configure_watchdog)
            configureWatchdogOnce();
        else if (plan.reconnected)
            noticeWatchdogDisabled();

        if (plan.apply_initial)
        {
            applyInitialImage();
            initial_applied_ = true;
        }
        else if (plan.reconnected && !apply_initial_image_ && !initial_notice_done_)
        {
            RCLCPP_INFO(get_logger(),
                        "읽기 전용 기동 — 초기 출력 이미지를 적용하지 않는다"
                        "(apply_initial_image=false). 출력은 장치 잔존값 그대로다.");
            initial_notice_done_ = true;
        }

        tc_msgs::msg::Io msg;
        msg.io_di = rc::expandBits(snap.value().di_words, di_word_count_ * 16u);
        msg.io_do = rc::expandBits(snap.value().do_words, do_word_count_ * 16u);
        io_pub_->publish(msg);

        publishAlarmIfNeeded(plan.reconnected);
        reportHealth();
    }

    // 워치독은 링크 확립 후 1회 구성한다. 구성 성공분은 포트가 재연결 시 자동 재무장한다.
    void configureWatchdogOnce()
    {
        rio::WatchdogConfig cfg;
        cfg.timeout = rio::Duration{watchdog_timeout_ms_};
        cfg.master_fault_action_enable = watchdog_fault_action_;
        if (auto r = port_->configureWatchdog(cfg); !r)
            RCLCPP_ERROR(get_logger(), "워치독 구성 실패(err=%d) — 보호 미확립",
                         static_cast<int>(r.error()));
        else
        {
            watchdog_configured_ = true;
            RCLCPP_INFO(get_logger(), "워치독 구성 — timeout %dms · fault_action=%s",
                        watchdog_timeout_ms_, watchdog_fault_action_ ? "on" : "off");
        }
    }

    void noticeWatchdogDisabled()
    {
        if (watchdog_notice_done_ || watchdog_timeout_ms_ > 0)
            return;
        RCLCPP_WARN(get_logger(),
                    "워치독 비활성(watchdog.timeout_ms=0) — 마스터 두절 시 출력이 그대로 "
                    "유지된다. 현장 안전 정책에 따라 값을 지정할 것.");
        watchdog_notice_done_ = true;
    }

    // 보호 상태를 주기적으로 드러낸다 — 'armed=false' 가 어디에도 안 보이면 없는 것과 같다.
    void reportHealth()
    {
        const auto h = port_->health();
        if (h.watchdog_armed == last_health_armed_ && h.reapply_pending == last_health_reapply_)
            return;
        last_health_armed_ = h.watchdog_armed;
        last_health_reapply_ = h.reapply_pending;
        RCLCPP_WARN(get_logger(), "포트 상태 변화 — watchdog_armed=%s reapply_pending=%s",
                    h.watchdog_armed ? "true" : "false", h.reapply_pending ? "true" : "false");
    }

    void applyInitialImage()
    {
        std::vector<int32_t> bits;
        bits.reserve(initial_on_bits_.size());
        for (int64_t b : initial_on_bits_)
            bits.push_back(static_cast<int32_t>(b));

        const auto img = rc::buildInitialImage(bits, do_word_count_);
        if (img.empty())
        {
            RCLCPP_ERROR(get_logger(), "initial_on_bits 에 범위 밖 인덱스가 있어 초기값을 적용하지 "
                                       "않았습니다 — 설정을 고치기 전까지 출력은 장치 잔존값입니다");
            return;
        }
        if (auto r = port_->applyOutputImage(img); !r)
            RCLCPP_ERROR(get_logger(), "초기 출력 이미지 적용 실패(err=%d)",
                         static_cast<int>(r.error()));
        else
            RCLCPP_INFO(get_logger(), "초기 출력 이미지 적용 — ON %zu비트", initial_on_bits_.size());
    }

    // ── io_service 쓰기 ──
    void handleWrite(const tc_msgs::srv::Io::Request &req, tc_msgs::srv::Io::Response &res)
    {
        res.indices_resp = req.indices;
        res.states_resp = req.states;
        res.received = false;

        const auto chk = rc::checkWriteRequest(req.indices, req.states, do_word_count_);
        if (!chk.ok)
        {
            RCLCPP_WARN(get_logger(), "io_service 요청 거부 — %s", chk.reason);
            return; // 요청 결함은 알람 대상이 아니다(장비 이상이 아니라 호출자 오류)
        }

        std::vector<rio::BitCommand> bits;
        bits.reserve(req.indices.size());
        for (size_t i = 0; i < req.indices.size(); ++i)
            bits.push_back(
                rio::BitCommand{static_cast<uint16_t>(req.indices[i]), req.states[i] != 0});

        // legacy 파리티: 최대 3회, 시도 간 100ms(인벤토리 §4).
        // **미연결이면 재시도하지 않고 즉시 실패한다** — legacy 도 그렇다(io_manager_node.cpp:296-300).
        // 재시도해봐야 링크가 그 사이 살아날 리 없고, 슬립만큼 틱을 막는다.
        //
        // ⚠ 이 콜백은 타이머와 **같은 실행자**에서 직렬화된다(기본 SingleThreadedExecutor +
        // MutuallyExclusive 콜백 그룹). 슬립 총량은 (retries-1)×backoff = 200ms 이고
        // 여기에 writeBits 의 Modbus 왕복(워드당 FC6+FC3, 최악 request_timeout×요청수)이 더해진다.
        // 실행자를 분리하면 포트의 "변이 호출은 단일 소유 스레드" 계약이 깨지므로,
        // 직렬화 게이트 없이 분리하지 말 것 — 근본 해법은 쓰기 큐(ADR-002 Proposed).
        for (int attempt = 0; attempt < write_retries_; ++attempt)
        {
            auto r = port_->writeBits(bits);
            if (r)
            {
                res.received = true;
                // 쓰기 성공은 **쓰기 실패 알람만** 해제한다 — 읽기 실패·미연결까지 지우면
                // 쓰기 결과가 읽기 상태를 대변하게 된다.
                error_code_ = rc::clearOnWriteSuccess(error_code_);
                return;
            }
            if (!rc::shouldRetryWrite(r.error(), attempt, write_retries_))
            {
                if (r.error() == rio::RemoteIoError::kNotConnected)
                    RCLCPP_WARN(get_logger(),
                                "io_service — 미연결, 재시도 없이 실패 반환(legacy 파리티)");
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(write_backoff_ms_));
        }
        error_code_ = rc::AlarmCode::kWritingFail;
        RCLCPP_ERROR(get_logger(), "io_service 쓰기 %d회 실패", write_retries_);
    }

    void publishAlarmIfNeeded(bool reconnected)
    {
        const auto d = rc::decideAlarm(error_code_, reconnected);
        if (!d.publish)
            return;
        tc_msgs::msg::AmrAlarm a;
        a.code = static_cast<int32_t>(d.code);
        a.state = false; // legacy 도 세트하지 않는다(인벤토리 §3) — 소비자 파리티 유지
        alarm_pub_->publish(a);
    }

    std::unique_ptr<rio::RemoteIoStationPort> port_;
    rclcpp::Publisher<tc_msgs::msg::Io>::SharedPtr io_pub_;
    rclcpp::Publisher<tc_msgs::msg::AmrAlarm>::SharedPtr alarm_pub_;
    rclcpp::Service<tc_msgs::srv::Io>::SharedPtr srv_;
    rclcpp::TimerBase::SharedPtr timer_;

    uint16_t di_word_count_ = 0;
    uint16_t do_word_count_ = 0;
    int period_ms_ = 20;
    int write_retries_ = 3;
    int write_backoff_ms_ = 100;
    std::vector<int64_t> initial_on_bits_;
    bool apply_initial_image_ = false;
    bool initial_notice_done_ = false;
    bool mirror_seeded_ = false;
    bool initial_applied_ = false;
    int watchdog_timeout_ms_ = 0;
    bool watchdog_fault_action_ = false;
    bool watchdog_configured_ = false;
    bool watchdog_notice_done_ = false;
    bool last_health_armed_ = false;
    bool last_health_reapply_ = false;
    int lock_fd_ = -1;

    rc::AlarmCode error_code_ = rc::AlarmCode::kNone;
    bool was_connected_ = false;
};

} // namespace

int main(int argc, char **argv)
{
    // 쓰기 마스터 단일성 강제(ADR-003 Proposed) — 중복 기동은 스스로 종료한다.
    const int lock = acquireSingleInstanceLock("remote_io_node.station.write-master");
    if (lock < 0)
    {
        std::fprintf(stderr,
                     "remote_io_node: 이미 다른 인스턴스가 스테이션 쓰기 마스터를 잡고 있다 — "
                     "중복 기동을 거부한다(마스터는 0 또는 1).\n");
        return 1;
    }
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<RemoteIoNode>());
    rclcpp::shutdown();
    ::close(lock);
    return 0;
}
