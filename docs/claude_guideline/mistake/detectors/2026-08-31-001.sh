#!/usr/bin/env bash
# 2026-08-31-001 — 알 수 없는 도메인 인자를 통과시키는 설치기.
#
# 도메인을 인자로 받는 install.sh 가 없는 이름을 경고만 하고 계속하면, 종료 코드는 0 이라
# **설치 성공으로 보이는데 domains/ 만 비어 있다.** 실사격에서 external_reference 를
# `ros2-coding`(coding 번들의 도메인명)으로 설치해 도메인이 통째로 빠진 채 운영됐다.
# 번들마다 이름 규약이 달라(ros2-coding / ros2-review / ros2-reference) 혼동은 상시 위험이다.
#
# 검출 방식(정적): 인자 기반 도메인 조회(`domains/$d.md`)를 하면서 중단 문구가 없는 파일.
# 한계 — 중단 메시지 문자열에 결합돼 있다. 동작으로 확인하려면 임시 타깃에 실제로 설치해
# 종료 코드를 봐야 하는데, 임의 저장소의 스크립트를 실행하는 검사는 어디서나 돌릴 수 없다.
# 그래서 정적 근사를 택했고, 대신 계약 테스트가 동작을 잡는다(coding I10).
set -uo pipefail
R="${1:-.}"
# 표본 제외는 **실스캔에서만** 적용한다. 스캔루트가 표본 안이면(음성 대조 실행) 제외하면
# 검사가 자기 표본을 못 봐서 '죽은 검사'로 잡힌다 — 러너가 실제로 그렇게 잡아냈다.
case "$R" in
  *.fixture/*|*.fixture) PRUNE=() ;;
  *) PRUNE=(-not -path '*.fixture/*') ;;
esac
bad=""
while IFS= read -r f; do
  grep -q 'domains/\$d\.md' "$f" 2>/dev/null || continue      # 인자 기반 조회를 하는가
  grep -q '없는 도메인' "$f" 2>/dev/null && continue           # 중단 문구가 있는가
  bad="$bad$f\n"
done < <(find "$R" -name install.sh -not -path '*/.git/*' "${PRUNE[@]}" 2>/dev/null)
[ -z "$bad" ] && exit 0
printf '%b' "$bad" | sed '/^$/d;s/$/:1: 알 수 없는 도메인 인자를 중단시키지 않는다/'
exit 1
