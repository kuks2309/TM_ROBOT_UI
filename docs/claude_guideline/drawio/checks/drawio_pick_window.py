#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""drawio_pick_window.py — 캡처할 drawio 문서 창을 고른다.

drawio_capture.sh 가 쓰는 창 선택 로직. 셸 안에 인라인으로 두면 디스플레이 없이
테스트할 수 없어 별도 모듈로 뺐다(SIL: experiments/SIL/test_pick_window.py).

고르는 규칙 — 각 조건이 실측으로 필요했다:
  1. 실행 **전후 차분**: 파일명이나 "drawio" 를 제목에 담은 다른 창(편집기·터미널)이
     이미 떠 있을 수 있다.
  2. **문서 창**만: drawio(Electron)는 스플래시 창("Flowchart Maker & Online
     Diagram Software")을 문서 창보다 먼저 띄운다.
  3. **(0,0) 배제**: 아직 배치되지 않은 창을 캡처하면 창이 아니라 화면 원점이 찍힌다.
  4. 여럿이면 **가장 큰 것**: drawio 인스턴스가 여러 개 떠 있을 수 있다.

사용(CLI):
  drawio_pick_window.py <capture_screen.py> <stem> <strict|relaxed> [before_ids...]
  echo '<json>' | drawio_pick_window.py --stdin <stem> <strict|relaxed> [before_ids...]
출력: "<id>\\t<x>\\t<y>\\t<w>\\t<h>\\t<title>"   종료 0=찾음 / 1=없음
"""
import json
import subprocess
import sys

MIN_W, MIN_H = 400, 300


def _title(w):
    return (w.get("title") or "").lower()


def _big(w):
    return (w.get("w") or 0) >= MIN_W and (w.get("h") or 0) >= MIN_H


def _area(w):
    return (w.get("w") or 0) * (w.get("h") or 0)


def is_document_window(w, stem):
    """문서 창인가 — 제목에 파일명이 들어가거나 "… - draw.io" 로 끝난다."""
    t = _title(w)
    return (bool(stem) and stem.lower() in t) or t.endswith("draw.io")


def is_placed(w):
    """WM 이 배치를 마쳤는가. (0,0) 은 아직 배치 전인 스플래시의 특징이다."""
    return (w.get("x"), w.get("y")) != (0, 0)


def pick(windows, stem, before_ids=(), mode="strict"):
    """→ 고른 창 dict, 없으면 None.

    strict: 배치가 끝난 문서 창만. relaxed: 없으면 가장 큰 새 창으로 대체.
    """
    before = {str(b) for b in before_ids}
    fresh = [w for w in windows if str(w.get("id")) not in before]

    cands = [w for w in fresh
             if _big(w) and is_document_window(w, stem) and is_placed(w)]
    if not cands and mode != "strict":
        # 마지막 수단에서도 미배치 창은 제외한다 — 찍어봐야 화면 원점이다
        cands = [w for w in fresh if _big(w) and is_placed(w)]
    if not cands:
        return None
    return max(cands, key=_area)


def format_row(w):
    return "\t".join(str(w.get(k, "")) for k in ("id", "x", "y", "w", "h", "title"))


def _list_windows(capture_py):
    out = subprocess.run([sys.executable, capture_py, "--mode", "list"],
                         capture_output=True, text=True, timeout=20).stdout
    return json.loads(out[out.index("["):out.rindex("]") + 1])


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    src, stem, mode = argv[0], argv[1], argv[2]
    before = argv[3:]
    try:
        wins = json.load(sys.stdin) if src == "--stdin" else _list_windows(src)
    except Exception:
        return 1
    w = pick(wins, stem, before, mode)
    if w is None:
        return 1
    print(format_row(w))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
