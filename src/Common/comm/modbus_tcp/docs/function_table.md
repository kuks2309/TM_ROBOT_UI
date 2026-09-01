# src/Common/comm/modbus_tcp — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/Common/comm/modbus_tcp/include/modbus_tcp/mbap_client.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 14 | MbapClient::isLinkUp | — | bool | link_up_ atomic relaxed 로드 | src/Common/comm/modbus_tcp/include/modbus_tcp/mbap_client.hpp:54 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | kMaxReadQuantity (상수) | readHoldingRegisters | FC3 최대 워드 수 125 | src/Common/comm/modbus_tcp/include/modbus_tcp/mbap_client.hpp:15 |
| 2 | kDefaultModbusPort (상수) | MbapClientConfig 기본값 | 기본 포트 502 | src/Common/comm/modbus_tcp/include/modbus_tcp/mbap_client.hpp:18 |

## src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | Result&lt;T&gt;::ok | v: T | Result | 성공값 래핑 생성 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:34 |
| 2 | Result&lt;T&gt;::err | e: TcpError | Result | 에러 래핑 생성 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:40 |
| 3 | Result&lt;T&gt;::has_value | — | bool | 성공 여부 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:46 |
| 4 | Result&lt;T&gt;::operator bool | — | bool | 성공 여부(명시 변환) | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:50 |
| 5 | Result&lt;T&gt;::value (const) | — | const T& | 값 접근(assert 보호) | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:54 |
| 6 | Result&lt;T&gt;::value | — | T& | 값 접근(비상수) | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:59 |
| 7 | Result&lt;T&gt;::error | — | TcpError | 에러코드(성공 시 kNone) | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:64 |
| 8 | Result&lt;void&gt;::ok | — | Result | void 성공 생성 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:79 |
| 9 | Result&lt;void&gt;::err | e: TcpError | Result | void 에러 생성 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:83 |
| 10 | Result&lt;void&gt;::has_value | — | bool | 성공 여부 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:87 |
| 11 | Result&lt;void&gt;::operator bool | — | bool | 성공 여부 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:91 |
| 12 | Result&lt;void&gt;::error | — | TcpError | 에러코드 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:95 |
| 13 | Result&lt;void&gt;::Result (private) | e, ok | — | 내부 생성자 | src/Common/comm/modbus_tcp/include/modbus_tcp/tcp_types.hpp:101 |

## src/Common/comm/modbus_tcp/sim/gl9089_server.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | Gl9089Server::Gl9089Server() | — | — | 기본 Config 위임 생성 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:48 |
| 2 | Gl9089Server::Gl9089Server(Config) | cfg | — | 소켓 bind/listen(포트 0 자동할당), 서비스 스레드 기동 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:51 |
| 3 | Gl9089Server::~Gl9089Server | — | — | running_=false, shutdown/close, join | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:68 |
| 4 | Gl9089Server::port | — | uint16 | 할당 포트 반환 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:84 |
| 5 | Gl9089Server::setVirtualTime | ms: int64 | void | 가상 시각 설정(워치독 판정 기준) | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:90 |
| 6 | Gl9089Server::setEquipmentInputs | di_words | void | DI 이미지 설정(mutex 보호) | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:95 |
| 7 | Gl9089Server::dropClientFin | — | void | 다음 서빙 루프에서 FIN 종료 주입 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:102 |
| 8 | Gl9089Server::dropClientRst | — | void | SO_LINGER(0) RST 종료 주입 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:106 |
| 9 | Gl9089Server::setAccepting | on: bool | void | 신규 연결 수락/즉시 종료 토글 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:110 |
| 10 | Gl9089Server::injectExceptionOnce | exc_code: uint8 | void | 다음 요청 1회 예외응답 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:115 |
| 11 | Gl9089Server::injectPartialFrameOnce | — | void | 다음 응답 1바이트씩 분할 송신 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:121 |
| 12 | Gl9089Server::injectTidMismatchOnce | — | void | 다음 응답 TID 왜곡 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:125 |
| 13 | Gl9089Server::setDiReadable | on: bool | void | DI 영역 FC3 무응답 토글 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:130 |
| 14 | Gl9089Server::connectionsAccepted | — | int | 누적 accept 수 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:135 |
| 15 | Gl9089Server::watchdogFireCount | — | int | 워치독 발화 횟수(mutex) | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:139 |
| 16 | Gl9089Server::writeCount | addr | int | 주소별 FC6 쓰기 횟수 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:144 |
| 17 | Gl9089Server::reg | addr | uint16 | 레지스터 판독(mutex) | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:150 |
| 18 | Gl9089Server::doWord | index | uint16 | DO 워드 판독 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:155 |
| 19 | Gl9089Server::adapterStatus | — | uint16 | 0x1119 판독 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:159 |
| 20 | Gl9089Server::watchdogErrorCounter | — | uint16 | 0x1022 판독 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:163 |
| 21 | Gl9089Server::waitReadable (static) | fd, timeout_ms | bool | poll POLLIN 대기 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:169 |
| 22 | Gl9089Server::run | — | void | accept 루프(50ms poll), 연결당 serveConn | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:176 |
| 23 | Gl9089Server::serveConn | fd | void | 요청 수신→handleLocked→응답 송신(분할/드롭 주입 처리) | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:198 |
| 24 | Gl9089Server::readRegisterLocked | addr | uint16 | DI 이미지/워치독/상태/일반 레지스터 판독 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:242 |
| 25 | Gl9089Server::updateWatchdogOnTxnLocked | — | void | 트랜잭션 간 가상시간 gap≥timeout 시 카운터++·ERR 비트·DO 클리어 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:258 |
| 26 | Gl9089Server::handleLocked | req | vector&lt;uint8&gt; | FC 분기(06 쓰기 에코 / 03 판독), 예외·TID 주입 반영 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:279 |
| 27 | Gl9089Server::writeRegisterLocked | addr, value | void | 레지스터 기록 + 0x1020 기록 시 워치독 재구성·카운터 0 리셋 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:321 |
| 2a | Gl9089Server.λ1 (스레드 본체) | — | — | run() 구동 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:65 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | kRegWatchdogTimeout (상수) | writeRegisterLocked | 0x1020 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:26 |
| 2 | kRegWatchdogErrorCounter (상수) | readRegisterLocked, watchdogErrorCounter | 0x1022 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:27 |
| 3 | kRegMasterFaultAction (상수) | (예약 — 파일 내 직접 사용 없음) | 0x1100 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:28 |
| 4 | kRegAdapterStatus (상수) | readRegisterLocked, adapterStatus | 0x1119 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:29 |
| 5 | kAdapterStatusErrWatchdogHi (상수) | updateWatchdogOnTxnLocked | ERR 비트 0x8000 | src/Common/comm/modbus_tcp/sim/gl9089_server.hpp:31 |

## src/Common/comm/modbus_tcp/src/mbap_client.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 15 | putBE16 (anon ns) | buf&, v: uint16 | void | 빅엔디언 16bit push | src/Common/comm/modbus_tcp/src/mbap_client.cpp:23 |
| 16 | getBE16 (anon ns) | p: const uint8* | uint16 | 빅엔디언 16bit 읽기 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:29 |
| 17 | mapExceptionCode (anon ns) | code: uint8 | TcpError | Modbus 예외코드→TcpError 매핑(01/04→Protocol, 02/03→OutOfRange, 06→Busy) | src/Common/comm/modbus_tcp/src/mbap_client.cpp:36 |
| 18 | MbapClient::MbapClient | config: MbapClientConfig | — | 설정 저장, rx_buffer_ 256 예약 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:57 |
| 19 | MbapClient::~MbapClient | — | — | close() 호출 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:62 |
| 20 | MbapClient::close | — | void | fd 닫기, link_up_=false, 버퍼 클리어 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:67 |
| 21 | MbapClient::setLinkDown | — | void | close() 위임 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:78 |
| 22 | MbapClient::boundedConnect | — | Result&lt;void&gt; | 논블로킹 connect + poll(connect_timeout) + SO_ERROR 검사 + SO_RCVTIMEO/SNDTIMEO 설정 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:83 |
| 23 | MbapClient::connect | — | Result&lt;void&gt; | boundedConnect 후 성공 시 백오프 리셋, 실패 시 지수 백오프 갱신 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:183 |
| 24 | MbapClient::ensureConnected | — | Result&lt;void&gt; | 링크 up 이면 통과, 백오프 창 내면 kNotConnected, 아니면 connect() | src/Common/comm/modbus_tcp/src/mbap_client.cpp:199 |
| 25 | MbapClient::recvAtLeast | n: size_t, deadline | Result&lt;void&gt; | rx_buffer_ 가 n 바이트 될 때까지 recv 루프(EINTR/EAGAIN 재시도, FIN→링크다운, 타임아웃 시 버퍼 클리어) | src/Common/comm/modbus_tcp/src/mbap_client.cpp:212 |
| 26 | MbapClient::recvFrame | deadline | Result&lt;vector&lt;uint8&gt;&gt; | MBAP 헤더 7B 수신 후 length 로 전체 프레임 추출·버퍼에서 제거 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:255 |
| 27 | MbapClient::transact | fc: uint8, pdu_body | Result&lt;vector&lt;uint8&gt;&gt; | 요청 조립(MBAP+TID)·송신 후 TID/PID/UID 일치 프레임까지 수신, 예외응답 매핑 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:281 |
| 28 | MbapClient::readHoldingRegisters | start_addr, quantity | Result&lt;vector&lt;uint16&gt;&gt; | FC3. quantity 1~125 검증, byte_count·프레임 길이 검증 후 워드 파싱 | src/Common/comm/modbus_tcp/src/mbap_client.cpp:355 |
| 29 | MbapClient::writeSingleRegister | addr, value | Result&lt;void&gt; | FC6. 에코 프레임의 addr/value 일치 검증(잉여 트레일링 바이트 허용) | src/Common/comm/modbus_tcp/src/mbap_client.cpp:389 |

## src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 33 | excResp | tid, fc, code | vector&lt;uint8&gt; | 예외응답 프레임 | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:20 |
| 34 | fastClient | port | MbapClientConfig | 200ms + backoff 5s 설정 | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:25 |
| 35 | runExceptionCase | code, expected | void | 예외코드 매핑 공용 케이스 | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:36 |
| 36 | TEST(MbapClientFault, ExceptionIllegalFunctionMapsToProtocol) | — | — | 0x01→Protocol | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:54 |
| 37 | TEST(MbapClientFault, ExceptionIllegalDataValueMapsToOutOfRange) | — | — | 0x03→OutOfRange | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:58 |
| 38 | TEST(MbapClientFault, ExceptionSlaveDeviceFailureMapsToProtocol) | — | — | 0x04→Protocol | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:62 |
| 39 | TEST(MbapClientFault, UnknownExceptionCodeMapsToProtocol) | — | — | 0x0A→Protocol | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:66 |
| 40 | TEST(MbapClientFault, InvalidHostFailsThenBackoffSuppressesImmediateRetry) | — | — | 잘못된 호스트 + 백오프 억제 | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:71 |
| 41 | TEST(MbapClientFault, ConnectRefusedPortFails) | — | — | 거부 포트 실패 | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:87 |
| 42 | TEST(MbapClientFault, WriteSingleRegisterEchoMismatchIsProtocol) | — | — | 에코 값+1 왜곡 kProtocol | src/Common/comm/modbus_tcp/test/mbap_client_fault_test.cpp:96 |

## src/Common/comm/modbus_tcp/test/mbap_client_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 11 | emptySignalHandler | int | void | SIGALRM no-op 핸들러 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:27 |
| 12 | countSigpipeHandler | int | void | SIGPIPE 카운트 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:32 |
| 13 | fastConfig | port | MbapClientConfig | 300ms 타임아웃 설정 생성 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:37 |
| 14 | TEST(MbapClient, ReadHoldingRegistersHappyPath) | — | — | FC3 정상 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:47 |
| 15 | TEST(MbapClient, WriteSingleRegisterHappyPath) | — | — | FC6 정상 에코 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:70 |
| 16 | TEST(MbapClient, WriteSingleRegisterAcceptsCrevis16ByteEchoWithTrailingBytes) | — | — | Crevis 트레일링 바이트 허용 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:89 |
| 17 | TEST(MbapClient, WriteSingleRegisterRejectsMismatchedValueEcho) | — | — | 에코 값 불일치 kProtocol | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:109 |
| 18 | TEST(MbapClient, ExceptionIllegalDataAddressMapsToOutOfRange) | — | — | 예외 0x02 매핑 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:129 |
| 19 | TEST(MbapClient, ExceptionSlaveDeviceBusyMapsToBusy) | — | — | 예외 0x06 매핑 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:149 |
| 20 | TEST(MbapClient, Recv0FinTriggersLinkDown) | — | — | FIN→kNotConnected·링크다운 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:169 |
| 21 | TEST(MbapClient, PartialReceiveReassemblesAcrossMultipleRecvCalls) | — | — | 1바이트 분할 재조립 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:186 |
| 22 | TEST(MbapClient, TidMismatchDiscardsAndResyncs) | — | — | TID 불일치 폐기 후 재동기 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:213 |
| 23 | TEST(MbapClient, QuantityAboveLimitRejectedClientSideWithoutNetworkIo) | — | — | 126 워드 클라이언트측 거부 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:235 |
| 24 | TEST(MbapClient, ByteCountMismatchRejectedAsFrameShort) | — | — | byte_count 불일치 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:248 |
| 25 | TEST(MbapClient, TimeoutWhenNoResponse) | — | — | 무응답 kTimeout | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:267 |
| 26 | TEST(MbapClient, ReconnectAfterFinSucceedsOnNextCall) | — | — | FIN 후 백오프 지나 재연결 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:286 |
| 27 | TEST(MbapClient, PartialThenTimeoutClearsBufferSoNextTransactResyncs) | — | — | 타임아웃 시 버퍼 클리어 재동기 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:321 |
| 28 | TEST(MbapClient, PidMismatchDiscardsAndResyncs) | — | — | PID 불일치 폐기 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:351 |
| 29 | TEST(MbapClient, UidMismatchDiscardsAndResyncs) | — | — | UID 불일치 폐기 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:376 |
| 30 | TEST(MbapClient, PeerResetDuringWriteDoesNotCrashProcess) | — | — | RST 중 쓰기 무크래시 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:398 |
| 31 | TEST(MbapClient, RecvInterruptedBySignalRetriesInsteadOfDroppingLink) | — | — | EINTR 재시도(ITIMER 20ms) | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:414 |
| 32 | TEST(MbapClient, WriteToResetPeerDoesNotRaiseSigpipe) | — | — | MSG_NOSIGNAL 로 SIGPIPE 0회 | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:461 |

### 전역 변수 / 모듈 상수

| # | 변수 | 사용처(함수) | 기능 | 위치(file:line) |
|---|---|---|---|---|
| 1 | g_sigpipe_count (가변) | countSigpipeHandler, TEST #32 | SIGPIPE 발생 카운터 (sig_atomic_t) | src/Common/comm/modbus_tcp/test/mbap_client_test.cpp:31 |

## src/Common/comm/modbus_tcp/test/mbap_link_state_tsan_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 43 | serveFc3Ok | fd, n_requests | void | FC3 n회 정상 서빙 | src/Common/comm/modbus_tcp/test/mbap_link_state_tsan_test.cpp:22 |
| 44 | TEST(MbapLinkStateTsan, CrossThreadIsLinkUpObservationIsRaceFree) | — | — | 관측 스레드 + 20회 FC3, TSan 무결성 | src/Common/comm/modbus_tcp/test/mbap_link_state_tsan_test.cpp:44 |
| 44a | TEST….λ1 (observer) | — | — | isLinkUp 스핀 관측 스레드 | src/Common/comm/modbus_tcp/test/mbap_link_state_tsan_test.cpp:59 |

## src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | MockGl9089Server::MockGl9089Server | — | — | 루프백 listen(자동 포트) | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:26 |
| 2 | MockGl9089Server::~MockGl9089Server | — | — | shutdown/close/join | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:42 |
| 3 | MockGl9089Server::port | — | uint16 | 포트 반환 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:60 |
| 4 | MockGl9089Server::setRecvTimeout | timeout: ms | void | 클라이언트 fd SO_RCVTIMEO 예약 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:66 |
| 5 | MockGl9089Server::serveOnce | handler: ConnHandler | void | accept 1회 후 handler 실행 스레드 기동 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:72 |
| 5a | serveOnce.λ1 | — | — | accept→timeout 설정→handler→close | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:78 |
| 6 | MockGl9089Server::join | — | void | 서빙 스레드 join | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:92 |
| 7 | requestTid | req | uint16 | 요청 TID 추출 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:107 |
| 8 | recvRequest | fd | vector&lt;uint8&gt; | recv 1회(최대 300B) | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:112 |
| 9 | buildFrame | tid, unit_id, pdu | vector&lt;uint8&gt; | MBAP 응답 프레임 조립 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:124 |
| 10 | sendAll | fd, data | void | 전량 송신 루프 | src/Common/comm/modbus_tcp/test/mock_gl9089_server.hpp:139 |

## src/Common/comm/modbus_tcp/test/mock_gl9089_server_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 45 | connectTo | port | int(fd) | 루프백 connect 헬퍼 | src/Common/comm/modbus_tcp/test/mock_gl9089_server_test.cpp:19 |
| 46 | TEST(MockGl9089Server, RecvTimeoutUnblocksHandlerOnRequestShortfall) | — | — | recv 타임아웃으로 핸들러 해방 | src/Common/comm/modbus_tcp/test/mock_gl9089_server_test.cpp:38 |
| 47 | TEST(MockGl9089Server, NormalExchangeStillWorks) | — | — | 정상 왕복 | src/Common/comm/modbus_tcp/test/mock_gl9089_server_test.cpp:70 |
