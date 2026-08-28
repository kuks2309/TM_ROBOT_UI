# TM_Robot_ros2_ws

git 협업 모드: team

> 2명이 함께 쓰는 저장소다(collaborator: `kuks2309`, `JHPark1584`). `main` 직접 push 를 하지 않는다.
> 규칙: [docs/claude_guideline/git_workflow/git_workflow.md](docs/claude_guideline/git_workflow/git_workflow.md)

## 협업 절차

```bash
git fetch origin                              # ① 항상 최신 main 에서 출발
git switch -c feat/<주제> origin/main          # ② <type>/<주제> 브랜치 (짧게 유지: 1~3일)
git add <명시 경로> && git commit              # ③ 작은 단위로 커밋 (git add -A / . 금지)
git pull --rebase origin main                 # ④ 작업 중 수시로 main 흡수
git push -u origin feat/<주제>                 # ⑤ 브랜치를 원격에 올림
gh pr create --base main --reviewer <상대>     # ⑥ PR → 리뷰 1건 승인 → merge
```

- 커밋 메시지: `type(scope): subject` (`feat`·`fix`·`docs`·`refactor`·`style`·`chore`·`test`)
- **본인 PR 은 본인이 승인·merge 하지 않는다** (리뷰 게이트의 존재 이유)
- 공유 브랜치 `--force` push 금지. 자기 feature 브랜치만 `--force-with-lease` 허용
- 충돌은 로컬에서 rebase 로 해결

## 담당 분리 (충돌 예방)

`CLAUDE.md` 의 UI/로직 분리 원칙이 그대로 분업선이 된다.

| 영역 | 파일 |
| --- | --- |
| UI 레이어 | `main_window.py`, `tabs/*.py` |
| 로직 레이어 | `services/*.py`, `job_executor.py` |

## 충돌이 잦은 append 문서

아래는 파일 끝에 계속 추가되는 기록이라 양쪽이 동시에 쓰면 충돌한다.
**충돌 시 한쪽을 고르지 말고 양쪽 내용을 모두 남긴다.**

- `docs/issues_and_fixes/issues_and_fixes.md` — 날짜 섹션은 역순(최신 먼저)
- `docs/worklog/YYYY-MM-DD.md` — 같은 날짜면 사람별 소제목으로 분리
- `docs/debt/registry.md` — debt id 대역을 나눠 쓴다 (예: A=001~499, B=500~999)

## clone 안내

이력에 과거 가상환경 blob 이 남아 있어 전체 clone 은 약 390MB 다. 얕은 clone 을 권한다.

```bash
git clone --depth=1 https://github.com/kuks2309/TM_Robot_ros2_ws.git
```

> 참고: `main` 브랜치 보호(직접 push 차단·리뷰 필수)는 private 저장소 + 무료 플랜이라 설정할 수 없다
> (GitHub Pro 또는 public 전환 필요). 현재 위 규칙은 **합의로만** 강제된다.
