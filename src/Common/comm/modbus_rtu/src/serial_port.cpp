#include "modbus_rtu/serial_port.hpp"

#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

#include <cerrno>
#include <utility>

namespace comm::modbus_rtu
{

namespace
{

// 지원 baud → termios speed_t. 그 외는 0(호출측이 open 시도 없이 kOutOfRange 로 매핑).
speed_t baudToSpeed(int baud)
{
    switch (baud)
    {
    case 9600:
        return B9600;
    case 19200:
        return B19200;
    case 38400:
        return B38400;
    case 57600:
        return B57600;
    case 115200:
        return B115200;
    default:
        return 0;
    }
}

} // namespace

SerialPortLink::SerialPortLink(int fd) : fd_(fd)
{
}

SerialPortLink::~SerialPortLink()
{
    if (fd_ >= 0)
        ::close(fd_);
}

Result<std::unique_ptr<SerialPortLink>> SerialPortLink::open(const std::string &device, int baud)
{
    const speed_t speed = baudToSpeed(baud);
    if (speed == 0)
        return Result<std::unique_ptr<SerialPortLink>>::err(RtuError::kOutOfRange);

    const int fd = ::open(device.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0)
        return Result<std::unique_ptr<SerialPortLink>>::err(RtuError::kNotOpen);

    termios tty{};
    if (::tcgetattr(fd, &tty) != 0)
    {
        ::close(fd);
        return Result<std::unique_ptr<SerialPortLink>>::err(RtuError::kNotOpen);
    }

    ::cfmakeraw(&tty);
    tty.c_cflag |= static_cast<tcflag_t>(CLOCAL | CREAD);
    tty.c_cflag &= static_cast<tcflag_t>(~PARENB); // no parity
    tty.c_cflag &= static_cast<tcflag_t>(~CSTOPB); // 1 stop bit
    tty.c_cflag &= static_cast<tcflag_t>(~CSIZE);
    tty.c_cflag |= CS8; // 8 data bits (8N1)
    ::cfsetispeed(&tty, speed);
    ::cfsetospeed(&tty, speed);
    tty.c_cc[VMIN] = 0;  // non-blocking read — select() 가 데드라인을 관리
    tty.c_cc[VTIME] = 0;

    if (::tcsetattr(fd, TCSANOW, &tty) != 0)
    {
        ::close(fd);
        return Result<std::unique_ptr<SerialPortLink>>::err(RtuError::kNotOpen);
    }

    // D4 단일 마스터 원칙을 커널 레벨로도 강제 — 같은 장치를 다른 프로세스가 동시에 열지 못하게
    // 배타 모드로 표시한다(최종 리뷰 I9). pty 슬레이브에도 적용 가능(둘 다 tty 라인 디시플린).
    if (::ioctl(fd, TIOCEXCL) != 0)
    {
        ::close(fd);
        return Result<std::unique_ptr<SerialPortLink>>::err(RtuError::kNotOpen);
    }

    return Result<std::unique_ptr<SerialPortLink>>::ok(std::unique_ptr<SerialPortLink>(new SerialPortLink(fd)));
}

Result<void> SerialPortLink::writeBytes(const std::vector<uint8_t> &data)
{
    if (fd_ < 0)
        return Result<void>::err(RtuError::kNotOpen);

    size_t total = 0;
    while (total < data.size())
    {
        const ssize_t n = ::write(fd_, data.data() + total, data.size() - total);
        if (n < 0)
        {
            if (errno == EINTR)
                continue;
            return Result<void>::err(RtuError::kNotOpen);
        }
        total += static_cast<size_t>(n);
    }
    return Result<void>::ok();
}

Result<std::vector<uint8_t>> SerialPortLink::readBytes(size_t max_len, TimePoint deadline)
{
    if (fd_ < 0)
        return Result<std::vector<uint8_t>>::err(RtuError::kNotOpen);
    if (max_len == 0)
        return Result<std::vector<uint8_t>>::ok(std::vector<uint8_t>{});

    // 루프 밖 1회 할당 — EINTR/EAGAIN/n==0 재시도마다 재할당하지 않는다(최종 리뷰 Minor).
    std::vector<uint8_t> buf(max_len);
    for (;;)
    {
        const TimePoint now = std::chrono::steady_clock::now();
        if (now >= deadline)
            return Result<std::vector<uint8_t>>::err(RtuError::kTimeout);

        const auto remaining = std::chrono::duration_cast<std::chrono::microseconds>(deadline - now);
        timeval tv{};
        tv.tv_sec = static_cast<time_t>(remaining.count() / 1000000);
        tv.tv_usec = static_cast<suseconds_t>(remaining.count() % 1000000);

        fd_set set;
        FD_ZERO(&set);
        FD_SET(fd_, &set);

        const int rc = ::select(fd_ + 1, &set, nullptr, nullptr, &tv);
        if (rc < 0)
        {
            if (errno == EINTR)
                continue;
            return Result<std::vector<uint8_t>>::err(RtuError::kTimeout);
        }
        if (rc == 0)
            return Result<std::vector<uint8_t>>::err(RtuError::kTimeout); // select 데드라인 초과

        const ssize_t n = ::read(fd_, buf.data(), max_len);
        if (n < 0)
        {
            if (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)
                continue; // select 가 readable 이라 했지만 경합으로 못 읽었을 수 있음 — 데드라인까지 재시도
            return Result<std::vector<uint8_t>>::err(RtuError::kTimeout);
        }
        if (n == 0)
            continue; // 아직 미도착 — 데드라인까지 재시도

        buf.resize(static_cast<size_t>(n));
        return Result<std::vector<uint8_t>>::ok(std::move(buf));
    }
}

void SerialPortLink::flushInput()
{
    if (fd_ >= 0)
        ::tcflush(fd_, TCIFLUSH);
}

bool SerialPortLink::isOpen() const
{
    return fd_ >= 0;
}

} // namespace comm::modbus_rtu
