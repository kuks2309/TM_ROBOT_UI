// gl9089_server.hpp — Crevis GL-9089 스테이션 에뮬레이터 (SIL·단위테스트 공용).
//
// 제공하는 것:
//   (1) 상주 accept 루프 — 재연결 반복을 태울 수 있다.
//   (2) 레지스터 이미지(DI/DO + 0x1020·0x1022·0x1100·0x1119)와 가상시계 기반 watchdog 타이머 —
//       마지막 트랜잭션 이후 timeout 경과 시 발동(error counter 증가 · ERR_WATCHDOG 세트 ·
//       DO 이미지 fault 값 강제), 0x1020 재기록 시 클리어.
//   (3) 결함 주입 — 링크(FIN/RST/accept 거부) · 프로토콜(예외응답 · 부분프레임 · TID 불일치).
//
// 시간은 주입된 가상시계(setVirtualTime)만 쓴다 — watchdog·gap 판정의 유일 시간 소스.
// 프레임 헬퍼는 test/mock_gl9089_server.hpp 를 재사용한다(사본 금지).
#ifndef COMM_MODBUS_TCP_SIM_GL9089_SERVER_HPP_
#define COMM_MODBUS_TCP_SIM_GL9089_SERVER_HPP_

#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <cstdint>
#include <map>
#include <mutex>
#include <thread>
#include <vector>

#include "../test/mock_gl9089_server.hpp" // 프레임 헬퍼 재사용: buildFrame·recvRequest·sendAll·requestTid

namespace comm::modbus_tcp::sim
{

namespace srv = ::comm::modbus_tcp::test;

// GL-9089 특수 레지스터(운영 코드 modbus_signal_port.hpp 와 동일 주소) — SIL 서버측 모델.
inline constexpr uint16_t kRegWatchdogTimeout = 0x1020;         // §8.3.2 (txt:1457-1466), 100ms 단위
inline constexpr uint16_t kRegWatchdogErrorCounter = 0x1022;    // §8.3.2 (txt:1472-1474)
inline constexpr uint16_t kRegMasterFaultAction = 0x1100;       // §8.3.4 (txt:1519-1528)
inline constexpr uint16_t kRegAdapterStatus = 0x1119;           // §8.3.4 (txt:1548-1563)
inline constexpr uint16_t kAdapterStatusErrWatchdogHi = 0x8000; // hi byte 0x80 = ERR_WATCHDOG (txt:1559)

class Gl9089Server
{
  public:
    struct Config
    {
        uint16_t di_start = 0x0000;
        uint16_t di_words = 3;
        uint16_t do_start = 0x0800;
        uint16_t do_words = 3;
    };

    Gl9089Server() : Gl9089Server(Config{})
    {
    }
    explicit Gl9089Server(Config cfg) : cfg_(cfg), di_image_(cfg.di_words, 0)
    {
        listen_fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        const int reuse = 1;
        ::setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        addr.sin_port = 0; // OS 임의 포트 할당
        ::bind(listen_fd_, reinterpret_cast<sockaddr *>(&addr), sizeof(addr));
        socklen_t len = sizeof(addr);
        ::getsockname(listen_fd_, reinterpret_cast<sockaddr *>(&addr), &len);
        port_ = ntohs(addr.sin_port);
        ::listen(listen_fd_, 8);
        thread_ = std::thread([this] { run(); });
    }

    ~Gl9089Server()
    {
        running_ = false;
        if (listen_fd_ >= 0)
        {
            ::shutdown(listen_fd_, SHUT_RDWR);
            ::close(listen_fd_);
            listen_fd_ = -1;
        }
        if (thread_.joinable())
            thread_.join();
    }

    Gl9089Server(const Gl9089Server &) = delete;
    Gl9089Server &operator=(const Gl9089Server &) = delete;

    uint16_t port() const
    {
        return port_;
    }

    // ── orchestrator → 서버: 가상시계 주입(매 tick) ──
    void setVirtualTime(int64_t ms)
    {
        vnow_ms_.store(ms, std::memory_order_relaxed);
    }

    // ── orchestrator → 서버: 설비(수동측) DI 이미지 갱신(PassiveE23Model.react 결과 반영) ──
    void setEquipmentInputs(const std::vector<uint16_t> &di_words)
    {
        std::lock_guard<std::mutex> lk(mtx_);
        for (size_t i = 0; i < di_image_.size() && i < di_words.size(); ++i)
            di_image_[i] = di_words[i];
    }

    // ── 링크 장애 주입 ──
    void dropClientFin()
    {
        drop_fin_.store(true);
    } // 다음 루프: 응답 없이 close(FIN)
    void dropClientRst()
    {
        drop_rst_.store(true);
    } // 다음 루프: SO_LINGER0 + close(RST)
    void setAccepting(bool on)
    {
        accepting_.store(on);
    } // false: accept 즉시 close(피어 소멸 모사)

    // ── 프로토콜 결함 주입(1회성) ──
    void injectExceptionOnce(uint8_t exc_code)
    {
        std::lock_guard<std::mutex> lk(mtx_);
        exc_once_ = true;
        exc_code_ = exc_code;
    }
    void injectPartialFrameOnce()
    {
        partial_once_.store(true);
    }
    void injectTidMismatchOnce()
    {
        tid_mismatch_once_.store(true);
    }

    // F07(스냅샷 단절)/F11(짧은 DI 프레임) 모델: DI 영역 FC3 읽기에 무응답(드롭) → 클라이언트 timeout →
    // ModbusSignalPort.read() 실패 → orchestrator 가 fresh=false 스냅샷을 FSM 에 주입(낡은 DI 미사용).
    void setDiReadable(bool on)
    {
        di_readable_.store(on);
    }

    // ── 관측(판정) ──
    int connectionsAccepted() const
    {
        return connections_.load();
    }
    int watchdogFireCount() const
    {
        std::lock_guard<std::mutex> lk(mtx_);
        return wd_fire_count_;
    }
    int writeCount(uint16_t addr)
    {
        std::lock_guard<std::mutex> lk(mtx_);
        auto it = write_counts_.find(addr);
        return it == write_counts_.end() ? 0 : it->second;
    }
    uint16_t reg(uint16_t addr)
    {
        std::lock_guard<std::mutex> lk(mtx_);
        return readRegisterLocked(addr);
    }
    uint16_t doWord(uint16_t index)
    {
        return reg(static_cast<uint16_t>(cfg_.do_start + index));
    }
    uint16_t adapterStatus()
    {
        return reg(kRegAdapterStatus);
    }
    uint16_t watchdogErrorCounter()
    {
        return reg(kRegWatchdogErrorCounter);
    }

  private:
    static bool waitReadable(int fd, int timeout_ms)
    {
        pollfd p{fd, POLLIN, 0};
        const int r = ::poll(&p, 1, timeout_ms);
        return r > 0 && (p.revents & POLLIN) != 0;
    }

    void run()
    {
        while (running_.load())
        {
            if (listen_fd_ < 0)
                break;
            if (!waitReadable(listen_fd_, 50))
                continue;
            const int fd = ::accept(listen_fd_, nullptr, nullptr);
            if (fd < 0)
                continue;
            connections_.fetch_add(1);
            if (!accepting_.load())
            {
                ::close(fd); // 피어 소멸 모사 — accept 즉시 close(FIN)
                continue;
            }
            serveConn(fd);
            ::close(fd);
        }
    }

    void serveConn(int fd)
    {
        while (running_.load())
        {
            if (drop_fin_.exchange(false))
                return; // FIN: 응답 없이 close
            if (drop_rst_.exchange(false))
            {
                linger lg{1, 0};
                ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg)); // RST on close
                return;
            }
            if (!accepting_.load())
                return; // 진행 중 연결을 강제 종료(피어 소멸)
            if (!waitReadable(fd, 50))
                continue; // running_/장애플래그 주기 재점검
            auto req = srv::recvRequest(fd);
            if (req.size() < 12u)
                return; // recv==0(FIN) 또는 불량 프레임 → 연결 종료

            std::vector<uint8_t> frame;
            bool partial = partial_once_.exchange(false);
            {
                std::lock_guard<std::mutex> lk(mtx_);
                frame = handleLocked(req);
            }
            if (frame.empty())
                continue;
            if (partial)
            {
                for (uint8_t b : frame)
                { // 부분 프레임: 1바이트씩 송신(재조립 강제, RECV-1)
                    const uint8_t one = b;
                    if (::send(fd, &one, 1, MSG_NOSIGNAL) <= 0)
                        return;
                }
            }
            else
            {
                srv::sendAll(fd, frame);
            }
        }
    }

    uint16_t readRegisterLocked(uint16_t addr)
    {
        if (addr >= cfg_.di_start && addr < cfg_.di_start + cfg_.di_words)
        {
            return di_image_[static_cast<size_t>(addr - cfg_.di_start)];
        }
        if (addr == kRegWatchdogErrorCounter)
            return wd_error_counter_;
        if (addr == kRegAdapterStatus)
            return adapter_status_;
        auto it = registers_.find(addr);
        return it == registers_.end() ? 0 : it->second;
    }

    // watchdog: 가상시계 기준 마지막 트랜잭션 이후 timeout 경과 시 발동(매뉴얼 통신 watchdog 모델).
    void updateWatchdogOnTxnLocked()
    {
        const int64_t vnow = vnow_ms_.load(std::memory_order_relaxed);
        if (wd_enabled_ && last_txn_valid_)
        {
            const int64_t gap = vnow - last_txn_vtime_;
            if (gap >= wd_timeout_ms_)
            {
                ++wd_error_counter_;                            // 0x1022 증가 (txt:1472-1474)
                adapter_status_ |= kAdapterStatusErrWatchdogHi; // 0x1119 hi=0x80 (txt:1559)
                for (uint16_t w = 0; w < cfg_.do_words; ++w)
                { // DO 출력 fault값(0) 강제
                    registers_[static_cast<uint16_t>(cfg_.do_start + w)] = 0;
                }
                ++wd_fire_count_;
            }
        }
        last_txn_vtime_ = vnow;
        last_txn_valid_ = true;
    }

    std::vector<uint8_t> handleLocked(const std::vector<uint8_t> &req)
    {
        uint16_t tid = srv::requestTid(req);
        if (tid_mismatch_once_.exchange(false))
            tid = static_cast<uint16_t>(tid + 0x1234); // TID 불일치(RECV-2)
        const uint8_t fc = req[7];
        const uint16_t addr = static_cast<uint16_t>((req[8] << 8) | req[9]);

        updateWatchdogOnTxnLocked(); // 모든 유효 트랜잭션이 watchdog 재무장(gap 리셋)

        if (exc_once_)
        { // 예외응답(EXC-1/2): fc|0x80 + exception code
            exc_once_ = false;
            const std::vector<uint8_t> pdu = {static_cast<uint8_t>(fc | 0x80), exc_code_};
            return srv::buildFrame(tid, 1, pdu);
        }

        if (fc == 0x06)
        { // Write Single Register
            const uint16_t value = static_cast<uint16_t>((req[10] << 8) | req[11]);
            writeRegisterLocked(addr, value);
            const std::vector<uint8_t> pdu(req.begin() + 7, req.end()); // FC6 정상응답=요청 에코
            return srv::buildFrame(tid, 1, pdu);
        }
        if (fc == 0x03)
        { // Read Holding Registers
            const bool di_region = (addr >= cfg_.di_start && addr < cfg_.di_start + cfg_.di_words);
            if (di_region && !di_readable_.load())
                return {}; // F07/F11: DI 읽기 드롭(무응답)
            const uint16_t qty = static_cast<uint16_t>((req[10] << 8) | req[11]);
            std::vector<uint8_t> pdu = {0x03, static_cast<uint8_t>(qty * 2)};
            for (uint16_t k = 0; k < qty; ++k)
            {
                const uint16_t v = readRegisterLocked(static_cast<uint16_t>(addr + k));
                pdu.push_back(static_cast<uint8_t>(v >> 8));
                pdu.push_back(static_cast<uint8_t>(v & 0xFF));
            }
            return srv::buildFrame(tid, 1, pdu);
        }
        return {}; // 미지원 FC — 드롭
    }

    void writeRegisterLocked(uint16_t addr, uint16_t value)
    {
        ++write_counts_[addr];
        registers_[addr] = value;
        if (addr == kRegWatchdogTimeout)
        {
            wd_timeout_reg_ = value;
            wd_enabled_ = (value > 0);
            wd_timeout_ms_ = static_cast<int64_t>(value) * 100; // 100ms 단위 (txt:1464-1465)
            // 매뉴얼: 0x1020 기록이 watchdog error counter 를 리셋(txt:1467-1468,1472-1474).
            wd_error_counter_ = 0;
            // WDV-2/debt-013 최악 모델: ERR_WATCHDOG(0x1119 hi=0x80) 는 어댑터 리셋 전까지 래치될 수 있어
            //   0x1020 재기록으로 지워지는지 매뉴얼 문면상 미확정("changing" 해석). 여기서는 지우지 않고 래치를
            //   유지한다 — 이 경우에도 counter 리셋 기반 WDV-2 게이팅으로 '같은 발동 재기록 1회'가 성립해야 한다
            //   (modbus_signal_port.cpp last_handled_watchdog_counter_ 로직 검증).
        }
    }

    Config cfg_;
    int listen_fd_ = -1;
    uint16_t port_ = 0;
    std::thread thread_;
    std::atomic<bool> running_{true};

    mutable std::mutex mtx_;
    std::vector<uint16_t> di_image_;         // 설비→AMR 입력 이미지
    std::map<uint16_t, uint16_t> registers_; // DO 이미지·0x1020·0x1100 등
    std::map<uint16_t, int> write_counts_;   // FC6 주소별 기록 횟수(판정)

    // watchdog 상태
    bool wd_enabled_ = false;
    uint16_t wd_timeout_reg_ = 0;
    int64_t wd_timeout_ms_ = 0;
    uint16_t wd_error_counter_ = 0; // 0x1022
    uint16_t adapter_status_ = 0;   // 0x1119
    int64_t last_txn_vtime_ = 0;
    bool last_txn_valid_ = false;
    int wd_fire_count_ = 0;

    // 결함 주입
    bool exc_once_ = false;
    uint8_t exc_code_ = 0x02;
    std::atomic<bool> partial_once_{false};
    std::atomic<bool> tid_mismatch_once_{false};
    std::atomic<bool> drop_fin_{false};
    std::atomic<bool> drop_rst_{false};
    std::atomic<bool> accepting_{true};
    std::atomic<bool> di_readable_{true};

    std::atomic<int64_t> vnow_ms_{0};
    std::atomic<int> connections_{0};
};

} // namespace comm::modbus_tcp::sim

#endif // COMM_MODBUS_TCP_SIM_GL9089_SERVER_HPP_
