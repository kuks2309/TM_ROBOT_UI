#!/usr/bin/env bash
# drawio Layer B(렌더 시각 검증) 환경 부트스트랩 (Linux, 멱등)
#
# 구성 요소:
#   1. drawio 데스크톱 AppImage (~/.local/opt/drawio) — 루트 불필요.
#      Layer B 양쪽 방식(GUI 창 캡처 · --export)이 모두 이 실행 파일을 쓴다.
#   2. xvfb — --export 를 디스플레이 없이 돌리는 데 필요 (루트 필요)
#   3. wmctrl / xdotool — GUI 캡처가 창을 맨 앞으로 올리는 데 필요 (루트 필요)
#
# 루트가 필요한 2·3 은 sudo 가 되면 설치하고, 안 되면 안내만 하고 계속한다
# (1 만 있어도 --export 는 DISPLAY 가 있으면 동작한다).
#
# 사용:
#   bash setup_env.sh            # 없는 것만 설치
#   bash setup_env.sh --check    # 점검만 (설치 안 함)
#   bash setup_env.sh --force    # AppImage 재다운로드
# 종료 코드: 0 = Layer B 사용 가능 / 1 = drawio 없음(핵심 의존성 실패)
set -uo pipefail

DRAWIO_DIR="$HOME/.local/opt/drawio"
DRAWIO_BIN="$DRAWIO_DIR/drawio"
REPO="jgraph/drawio-desktop"

CHECK_ONLY=0
FORCE=0
for a in "$@"; do
  case "$a" in
    --check) CHECK_ONLY=1 ;;
    --force) FORCE=1 ;;
    *) echo "unknown arg: $a" >&2; exit 64 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }

# 이미 있는 drawio 를 찾는다 (패키지 설치본·flatpak 포함 — 중복 다운로드 방지)
find_existing_drawio() {
  local c
  for c in drawio drawio-desktop; do
    have "$c" && { command -v "$c"; return 0; }
  done
  for c in "$DRAWIO_BIN" "$HOME/.local/bin/drawio" \
           /opt/drawio/drawio /opt/drawio-desktop/drawio; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  if have flatpak && flatpak info com.jgraph.drawio.desktop >/dev/null 2>&1; then
    echo "flatpak run com.jgraph.drawio.desktop"; return 0
  fi
  return 1
}

# ── [1/3] drawio 데스크톱 ─────────────────────────────────────────────
echo "== [1/3] drawio 데스크톱 =="
EXISTING="$(find_existing_drawio || true)"
if [ -n "$EXISTING" ] && [ "$FORCE" = 0 ]; then
  echo "  ✓ 이미 있음: $EXISTING"
elif [ "$CHECK_ONLY" = 1 ]; then
  echo "  · 없음 → 설치 단계가 AppImage 구성 (~170MB)"
else
  mkdir -p "$DRAWIO_DIR"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  ok=0
  # 자산명은 drawio-x86_64-<버전>.AppImage — 접미사 매칭만으로는 안 잡힌다
  if have gh && gh release download --repo "$REPO" \
       --pattern 'drawio-x86_64-*.AppImage' --dir "$TMP" >/dev/null 2>&1; then
    ok=1
  else
    URL="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
      | grep -o '"browser_download_url": *"[^"]*drawio-x86_64-[^"]*\.AppImage"' \
      | head -1 | cut -d'"' -f4)"
    if [ -n "$URL" ]; then
      echo "  다운로드: $URL"
      curl -fL --progress-bar -o "$TMP/drawio.AppImage" "$URL" && ok=1
    fi
  fi
  if [ "$ok" = 1 ]; then
    mv -f "$TMP"/drawio*.AppImage "$DRAWIO_BIN.AppImage" 2>/dev/null || \
      mv -f "$TMP"/*.AppImage "$DRAWIO_BIN.AppImage"
    chmod +x "$DRAWIO_BIN.AppImage"
    ln -sf drawio.AppImage "$DRAWIO_BIN"
    echo "  ✓ 설치: $DRAWIO_BIN ($(du -h "$DRAWIO_BIN.AppImage" | cut -f1))"
  else
    echo "  ✗ 다운로드 실패 — 네트워크·GitHub 접근을 확인하세요." >&2
    echo "    수동: https://github.com/$REPO/releases/latest 에서" >&2
    echo "          drawio-x86_64-*.AppImage 를 받아 $DRAWIO_BIN 로 두고 chmod +x" >&2
  fi
fi

# ── [2/3] xvfb (--export 를 디스플레이 없이) ──────────────────────────
echo "== [2/3] xvfb (헤드리스 --export) =="
if have xvfb-run; then
  echo "  ✓ 이미 있음: $(command -v xvfb-run)"
elif [ "$CHECK_ONLY" = 1 ]; then
  echo "  · 없음 → 설치 단계가 apt 로 설치 시도(루트 필요)"
else
  if have apt-get && sudo -n true 2>/dev/null; then
    sudo apt-get install -y xvfb >/dev/null 2>&1 && echo "  ✓ 설치됨" \
      || echo "  ⚠ 설치 실패 — 수동: sudo apt-get install -y xvfb"
  else
    echo "  ⚠ 루트 없음 — 수동 설치 필요: sudo apt-get install -y xvfb"
    echo "    (없어도 DISPLAY 가 있으면 --export 는 동작한다)"
  fi
fi

# ── [3/3] wmctrl / xdotool (GUI 캡처가 창을 맨 앞으로) ────────────────
echo "== [3/3] wmctrl · xdotool (GUI 캡처 창 앞세우기) =="
MISSING=""
have wmctrl  || MISSING="$MISSING wmctrl"
have xdotool || MISSING="$MISSING xdotool"
if [ -z "$MISSING" ]; then
  echo "  ✓ 이미 있음: wmctrl · xdotool"
elif [ "$CHECK_ONLY" = 1 ]; then
  echo "  · 없음:$MISSING → 설치 단계가 apt 로 설치 시도(루트 필요)"
else
  if have apt-get && sudo -n true 2>/dev/null; then
    # shellcheck disable=SC2086
    sudo apt-get install -y $MISSING >/dev/null 2>&1 && echo "  ✓ 설치됨:$MISSING" \
      || echo "  ⚠ 설치 실패 — 수동: sudo apt-get install -y$MISSING"
  else
    echo "  ⚠ 루트 없음 — 수동 설치 필요: sudo apt-get install -y$MISSING"
    echo "    (없으면 GUI 캡처가 가려진 창·창 개요 상태를 찍는다. --export 는 무관)"
  fi
fi

# ── 요약 ──────────────────────────────────────────────────────────────
echo
FINAL="$(find_existing_drawio || true)"
if [ -z "$FINAL" ]; then
  echo "✗ drawio 없음 — Layer B 사용 불가 (Layer A 린트는 의존성 없이 동작)"
  exit 1
fi
echo "✓ drawio: $FINAL"
have xvfb-run && echo "✓ --export: 디스플레이 없이 가능" \
              || echo "· --export: DISPLAY 필요 (xvfb 미설치)"
if have wmctrl || have xdotool; then
  echo "✓ GUI 캡처: 창 앞세우기 가능"
else
  echo "· GUI 캡처: 창 앞세우기 불가 (wmctrl·xdotool 없음) → --export 권장"
fi
exit 0
