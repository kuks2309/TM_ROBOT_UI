#!/usr/bin/env bash
# 표본 없이 출하된 검사기 — 무엇을 놓치는지 아무도 모른다.
grep -rn "TODO" "${1:-.}" && exit 1 || exit 0
