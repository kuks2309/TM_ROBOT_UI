# src/IOs/Remote_IO_Station/remote_io_ros — 함수표 (모듈 로컬 권위본)

생성 근거: 전체 코드 리뷰 `docs/code_review/TM_Robot_UI-전체/2026-08-29.md` 의 본 패키지 섹션 발췌(동일 내용). 컬럼 양식 권위는 code_review SOP.

## src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp

선언 헤더 — 구현은 io_contract.cpp 소유(아래 표). 타입·선언 위치는 현재 워킹트리 실측.

| # | 심볼 | 종류 | 기능 | 위치(file:line) |
|---|---|---|---|---|
| d1 | AlarmCode | enum | legacy 알람 코드 4종(0·1101·1102·1103) | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:14 |
| d2 | expandBits | 선언 | 워드→비트 전개 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:24 |
| d3 | buildInitialImage | 선언 | 초기 출력 이미지 조립 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:28 |
| d4 | WriteRequestCheck / checkWriteRequest | struct+선언 | 쓰기 요청 검증 결과·검증 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:30 |
| d5 | AlarmDecision / decideAlarm | struct+선언 | 알람 발행 판단 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:39 |
| d6 | TickInput / TickPlan / planTick | struct+선언 | 틱 계획 상태기계 입출력 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:48 |
| d7 | shouldRetryWrite / clearOnWriteSuccess | 선언 | 쓰기 재시도·알람 해제 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.hpp:76 |

## src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | expandBits | words, bit_count | vector&lt;int32&gt; | 워드 이미지→비트 배열(LSB first, 부족 워드는 0) | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:6 |
| 2 | buildInitialImage | on_bits, do_word_count | vector&lt;uint16&gt; | ON 비트 목록→DO 이미지(범위 밖 있으면 빈 벡터로 전체 거부) | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:19 |
| 3 | checkWriteRequest | indices, states, do_word_count | WriteRequestCheck | 길이 일치·비공백·범위·0/1 값 검증(사유 문자열) | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:33 |
| 4 | decideAlarm | current: AlarmCode, reconnected_this_tick | AlarmDecision | 재연결 시 kNone 1회, 에러 지속 시 반복 발행 결정 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:51 |
| 5 | planTick | in: TickInput | TickPlan | 읽기 실패→알람 코드, 성공→발행+재연결 시 시드/초기이미지/워치독 1회 계획 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:60 |
| 6 | shouldRetryWrite | err, attempt, retries | bool | kNotConnected 즉시 중단, 그 외 attempt+1&lt;retries | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:85 |
| 7 | clearOnWriteSuccess | current | AlarmCode | kWritingFail 만 해제 | src/IOs/Remote_IO_Station/remote_io_ros/src/io_contract.cpp:92 |

## src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 8 | acquireSingleInstanceLock (anon ns) | name: string | int(fd) | 추상 유닉스 소켓 bind 로 단일 인스턴스 잠금 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:31 |
| 9 | RemoteIoNode::RemoteIoNode | — | — | 파라미터 13종 declare, 포트 구성, pub/srv/timer 생성 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:56 |
| 9a | RemoteIoNode.λ1 (clock) | — | TimePoint | steady_clock now | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:83 |
| 9b | RemoteIoNode.λ2 (srv 콜백) | req, res | void | handleWrite 위임 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:89 |
| 9c | RemoteIoNode.λ3 (timer 콜백) | — | void | tick 위임 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:94 |
| 10 | RemoteIoNode::tick (private) | — | void | read→planTick→시드/워치독/초기이미지→io_resp 발행→알람→health 로그 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:101 |
| 11 | RemoteIoNode::configureWatchdogOnce (private) | — | void | 워치독 구성 시도, 성공 시 플래그 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:171 |
| 12 | RemoteIoNode::noticeWatchdogDisabled (private) | — | void | timeout 0 경고 1회 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:187 |
| 13 | RemoteIoNode::reportHealth (private) | — | void | armed/reapply 변화 시에만 경고 로그 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:197 |
| 14 | RemoteIoNode::applyInitialImage (private) | — | void | initial_on_bits→이미지 조립→applyOutputImage | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:208 |
| 15 | RemoteIoNode::handleWrite (private) | req: Io::Request, res: Io::Response | void | 검증→BitCommand 변환→writeBits 재시도 루프(백오프 sleep)→알람 갱신 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:229 |
| 16 | RemoteIoNode::publishAlarmIfNeeded (private) | reconnected | void | decideAlarm 판단 시 AmrAlarm 발행 | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:271 |
| 17 | main | argc, argv | int | 단일 인스턴스 잠금→rclcpp::spin(RemoteIoNode) | src/IOs/Remote_IO_Station/remote_io_ros/src/remote_io_node.cpp:313 |

## src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp

| # | 함수 | 입력 | 출력 | 기능 | 위치(file:line) |
|---|---|---|---|---|---|
| 1 | TEST(ExpandBits, LsbFirstWithinWord) | — | — | 워드 내 LSB first | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:13 |
| 2 | TEST(ExpandBits, WordBoundaryIsIndexTimesSixteen) | — | — | 워드 경계 = ×16 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:22 |
| 3 | TEST(ExpandBits, OperationalSizesMatchLegacyResize) | — | — | 80/96 비트 크기 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:29 |
| 4 | TEST(ExpandBits, MissingWordsYieldZerosNotGarbage) | — | — | 부족 워드 0 채움 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:35 |
| 5 | TEST(InitialImage, LegacyEightBitsMapToExpectedWords) | — | — | 레거시 8비트→0x2A2A 등 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:44 |
| 6 | TEST(InitialImage, OutOfRangeBitRejectsWholeImage) | — | — | 96/-1 전체 거부 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:55 |
| 7 | TEST(InitialImage, EmptyListIsAllZero) | — | — | 빈 목록 0 이미지 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:61 |
| 8 | TEST(WriteRequest, LengthMismatchRejected) | — | — | 길이 불일치 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:70 |
| 9 | TEST(WriteRequest, OutOfRangeIndexRejected) | — | — | 96/-1 거부, 95 허용 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:76 |
| 10 | TEST(WriteRequest, NonBinaryStateRejected) | — | — | 값 2 거부 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:83 |
| 11 | TEST(WriteRequest, EmptyRejected) | — | — | 빈 요청 거부 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:88 |
| 12 | TEST(Alarm, RepeatsWhileErrorStands) | — | — | 에러 지속 반복 발행 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:94 |
| 13 | TEST(Alarm, SilentWhenHealthy) | — | — | 정상 시 침묵 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:103 |
| 14 | TEST(Alarm, ReconnectPublishesClearOnce) | — | — | 재연결 kNone 1회 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:109 |
| 15 | TEST(Alarm, CodesMatchLegacyNumbers) | — | — | 0/1101/1102/1103 고정 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:116 |
| 16 | base | — | TickInput | 정상 정착 상태 픽스처 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:125 |
| 17 | TEST(PlanTick, ReadFailureNeverPublishes) | — | — | 읽기 실패 무발행+1103 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:139 |
| 18 | TEST(PlanTick, NotConnectedMapsToDisconnectAlarm) | — | — | 미연결→1101 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:149 |
| 19 | TEST(PlanTick, SteadyTickPublishesAndKeepsAlarm) | — | — | 정착 틱 발행+알람 유지 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:157 |
| 20 | TEST(PlanTick, SeedsOnlyOnFirstLink) | — | — | 최초 링크만 시드 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:168 |
| 21 | TEST(PlanTick, InitialImageAppliedOncePerProcess) | — | — | 프로세스당 1회 적용 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:179 |
| 22 | TEST(PlanTick, InitialImageNeverAppliedWhenDisabled) | — | — | 비활성 시 미적용 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:191 |
| 23 | TEST(PlanTick, WatchdogConfiguredOnceWhenEnabled) | — | — | 활성 시 1회 구성 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:200 |
| 24 | TEST(PlanTick, WatchdogNotConfiguredWhenTimeoutZero) | — | — | timeout 0 미구성 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:212 |
| 25 | TEST(PlanTick, ReconnectClearsAlarm) | — | — | 재연결 알람 해제 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:220 |
| 26 | TEST(ShouldRetryWrite, NotConnectedStopsImmediately) | — | — | 미연결 즉시 중단 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:230 |
| 27 | TEST(ShouldRetryWrite, OtherErrorsRetryUntilBudget) | — | — | 예산 내 재시도 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:235 |
| 28 | TEST(ClearOnWriteSuccess, ClearsOnlyWritingFail) | — | — | 1102 만 해제 | src/IOs/Remote_IO_Station/remote_io_ros/test/io_contract_test.cpp:243 |
