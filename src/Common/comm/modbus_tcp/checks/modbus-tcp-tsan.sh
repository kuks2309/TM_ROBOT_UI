#!/usr/bin/env bash
# ⟦CI:modbus-tcp-tsan⟧ — debt-014 ① 동시성 계약 게이트.
# mbap_link_state_tsan_test 를 ThreadSanitizer 빌드로 실행 — link_up_ atomic 계약(교차 스레드
# isLinkUp 관측) 위반(data race) 시 FAIL. cmake 는 /usr/bin/cmake 고정(빌드환경 실측:
# /usr/local/bin/cmake libssl1.1 파손 — docs/debt/registry.md debt-006 경과).
set -u
PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$PKG_DIR/build/tsan"
CMAKE=/usr/bin/cmake

"$CMAKE" -S "$PKG_DIR" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DMODBUS_TCP_SANITIZE_THREAD=ON >/dev/null || { echo "❌ modbus-tcp-tsan: configure 실패"; exit 1; }
"$CMAKE" --build "$BUILD_DIR" -j >/dev/null || { echo "❌ modbus-tcp-tsan: build 실패"; exit 1; }

if [ ! -x "$BUILD_DIR/modbus_tcp_mbap_link_state_tsan_test" ]; then
  echo "❌ modbus-tcp-tsan: 테스트 바이너리 없음(GTest 미설치?)"
  exit 1
fi

# setarch -R: 프로세스 한정 ASLR 비활성 — Linux 6.8(vm.mmap_rnd_bits=32)에서 구형 TSan 런타임이
# "FATAL: ThreadSanitizer: unexpected memory mapping"으로 기동 실패하는 알려진 비호환의 표준 회피
# (실측: 본 환경 kernel 6.8.0-124, 2026-07-31 — root 불요·타 프로세스 무영향).
# halt_on_error=1: race 검출 즉시 비0 종료 → 게이트 FAIL
RUN="setarch $(uname -m) -R"
OUT="$($RUN env TSAN_OPTIONS="halt_on_error=1" "$BUILD_DIR/modbus_tcp_mbap_link_state_tsan_test" 2>&1)"
RC=$?
if echo "$OUT" | grep -q "unexpected memory mapping"; then
  echo "❌ modbus-tcp-tsan: TSan 런타임 기동 실패(ASLR 비호환 — setarch 회피도 실패). 환경 점검 필요"
  exit 1
fi
if [ "$RC" -eq 0 ]; then
  # 나머지 테스트 2종도 이미 TSan 빌드이므로 함께 실행(추가 커버리지 — 리뷰 minor 반영 2026-07-31)
  for extra in modbus_tcp_mbap_client_test modbus_tcp_mbap_client_fault_test; do
    if [ -x "$BUILD_DIR/$extra" ]; then
      if ! $RUN env TSAN_OPTIONS="halt_on_error=1" "$BUILD_DIR/$extra" >/dev/null 2>&1; then
        echo "❌ modbus-tcp-tsan: $extra TSan 실패"
        exit 1
      fi
    fi
  done
  echo "✅ modbus-tcp-tsan: TSan data race 0 (isLinkUp 교차관측 계약 유지, 3종 테스트)"
  exit 0
else
  echo "❌ modbus-tcp-tsan: TSan race 검출 또는 테스트 실패 — 아래 재실행으로 상세 확인:"
  echo "   $RUN env TSAN_OPTIONS=halt_on_error=1 $BUILD_DIR/modbus_tcp_mbap_link_state_tsan_test"
  exit 1
fi
