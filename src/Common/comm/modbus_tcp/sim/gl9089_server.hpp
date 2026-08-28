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

#include "../test/mock_gl9089_server.hpp"

namespace comm::modbus_tcp::sim
{

namespace srv = ::comm::modbus_tcp::test;

inline constexpr uint16_t kRegWatchdogTimeout = 0x1020;
inline constexpr uint16_t kRegWatchdogErrorCounter = 0x1022;
inline constexpr uint16_t kRegMasterFaultAction = 0x1100;
inline constexpr uint16_t kRegAdapterStatus = 0x1119;
inline constexpr uint16_t kAdapterStatusErrWatchdogHi = 0x8000;

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
        addr.sin_port = 0;
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

    void setVirtualTime(int64_t ms)
    {
        vnow_ms_.store(ms, std::memory_order_relaxed);
    }

    void setEquipmentInputs(const std::vector<uint16_t> &di_words)
    {
        std::lock_guard<std::mutex> lk(mtx_);
        for (size_t i = 0; i < di_image_.size() && i < di_words.size(); ++i)
            di_image_[i] = di_words[i];
    }

    void dropClientFin()
    {
        drop_fin_.store(true);
    }
    void dropClientRst()
    {
        drop_rst_.store(true);
    }
    void setAccepting(bool on)
    {
        accepting_.store(on);
    }

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

    void setDiReadable(bool on)
    {
        di_readable_.store(on);
    }

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
                ::close(fd);
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
                return;
            if (drop_rst_.exchange(false))
            {
                linger lg{1, 0};
                ::setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof(lg));
                return;
            }
            if (!accepting_.load())
                return;
            if (!waitReadable(fd, 50))
                continue;
            auto req = srv::recvRequest(fd);
            if (req.size() < 12u)
                return;

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
                {
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

    void updateWatchdogOnTxnLocked()
    {
        const int64_t vnow = vnow_ms_.load(std::memory_order_relaxed);
        if (wd_enabled_ && last_txn_valid_)
        {
            const int64_t gap = vnow - last_txn_vtime_;
            if (gap >= wd_timeout_ms_)
            {
                ++wd_error_counter_;
                adapter_status_ |= kAdapterStatusErrWatchdogHi;
                for (uint16_t w = 0; w < cfg_.do_words; ++w)
                {
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
            tid = static_cast<uint16_t>(tid + 0x1234);
        const uint8_t fc = req[7];
        const uint16_t addr = static_cast<uint16_t>((req[8] << 8) | req[9]);

        updateWatchdogOnTxnLocked();

        if (exc_once_)
        {
            exc_once_ = false;
            const std::vector<uint8_t> pdu = {static_cast<uint8_t>(fc | 0x80), exc_code_};
            return srv::buildFrame(tid, 1, pdu);
        }

        if (fc == 0x06)
        {
            const uint16_t value = static_cast<uint16_t>((req[10] << 8) | req[11]);
            writeRegisterLocked(addr, value);
            const std::vector<uint8_t> pdu(req.begin() + 7, req.end());
            return srv::buildFrame(tid, 1, pdu);
        }
        if (fc == 0x03)
        {
            const bool di_region = (addr >= cfg_.di_start && addr < cfg_.di_start + cfg_.di_words);
            if (di_region && !di_readable_.load())
                return {};
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
        return {};
    }

    void writeRegisterLocked(uint16_t addr, uint16_t value)
    {
        ++write_counts_[addr];
        registers_[addr] = value;
        if (addr == kRegWatchdogTimeout)
        {
            wd_timeout_reg_ = value;
            wd_enabled_ = (value > 0);
            wd_timeout_ms_ = static_cast<int64_t>(value) * 100;
            wd_error_counter_ = 0;
        }
    }

    Config cfg_;
    int listen_fd_ = -1;
    uint16_t port_ = 0;
    std::thread thread_;
    std::atomic<bool> running_{true};

    mutable std::mutex mtx_;
    std::vector<uint16_t> di_image_;
    std::map<uint16_t, uint16_t> registers_;
    std::map<uint16_t, int> write_counts_;

    bool wd_enabled_ = false;
    uint16_t wd_timeout_reg_ = 0;
    int64_t wd_timeout_ms_ = 0;
    uint16_t wd_error_counter_ = 0;
    uint16_t adapter_status_ = 0;
    int64_t last_txn_vtime_ = 0;
    bool last_txn_valid_ = false;
    int wd_fire_count_ = 0;

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

}

#endif
