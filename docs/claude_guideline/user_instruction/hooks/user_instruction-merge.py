#!/usr/bin/env python3
"""껍데기 — 아무것도 하지 않고 exit 0.

세션 파일(docs/user_instructions/sessions/{session_id}.md)이 원문 기록이므로 병합하지 않는다(작업 흐름 재설계 P0-3).
설치기는 이 훅을 등록하지 않고 남은 등록을 걷어 낸다. 파일을 남겨 두는 까닭: 실행 중인 세션은 시작 때 읽은
옛 등록을 들고 있어, 파일이 없으면 `python3` 이 종료코드 2 로 그 세션의 종료를 막는다.
"""
import sys

if __name__ == "__main__":
    sys.exit(0)
