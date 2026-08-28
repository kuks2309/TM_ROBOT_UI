#!/usr/bin/env python3
"""매크로 카탈로그 생성기 — 레지스트리에서 문서를 파생시킨다.

손으로 쓴 카탈로그는 반드시 낡는다. 매크로를 추가·수정한 뒤 이 스크립트를
다시 돌리면 CATALOG.md(사람용)와 macros.json(도구용)이 함께 갱신된다.

사용:
    python3 scripts/generate_macro_catalog.py            # 기본 출력 경로
    python3 scripts/generate_macro_catalog.py --out DIR  # 출력 폴더 지정
    python3 scripts/generate_macro_catalog.py --check    # 최신 여부만 검사(생성 안 함)
"""
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

_PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PKG_ROOT))

# 카탈로그 생성은 로봇·ROS 없이 돌아야 한다 — 레지스트리만 읽으면 되기 때문이다.
for _name in ('rclpy', 'rclpy.node', 'rclpy.executors', 'rclpy.time', 'tf2_ros',
              'tf2_py', 'tf2_py._tf2_py', 'geometry_msgs', 'geometry_msgs.msg',
              'tm_msgs', 'tm_msgs.srv', 'tm_msgs.msg', 'cv_bridge'):
    sys.modules.setdefault(_name, MagicMock())

from tm_task_manager.macros import MACROS, EXTERNAL_PREFIX  # noqa: E402
from tm_task_manager.recipe_manager import RecipeManager  # noqa: E402


def build_payload() -> dict:
    macros = {}
    for name, spec in sorted(MACROS.items()):
        macros[name] = {
            'summary': spec.summary,
            'category': spec.category,
            'params': spec.params,
            'requires': spec.requires,
            'produces': spec.produces,
        }

    jobs = {}
    for job_type, job_spec in sorted(RecipeManager.JOB_TYPES.items()):
        macro_defs = job_spec.get('macros')
        if not macro_defs:
            continue
        jobs[job_type] = {
            'name': job_spec.get('name', job_type),
            'category': job_spec.get('category', ''),
            'macros': macro_defs,
        }

    return {'macros': macros, 'jobs_using_macros': jobs}


def _param_rows(params: dict) -> list:
    rows = []
    for key, spec in params.items():
        constraints = []
        if 'choices' in spec:
            constraints.append('/'.join(str(c) for c in spec['choices']))
        if 'min' in spec:
            constraints.append(f"min {spec['min']}")
        if 'max' in spec:
            constraints.append(f"max {spec['max']}")
        rows.append((key, spec.get('type', ''), repr(spec.get('default')),
                     ', '.join(constraints) or '-', spec.get('description', '')))
    return rows


def render_markdown(payload: dict) -> str:
    lines = [
        '# Macro Catalog',
        '',
        '> 이 문서는 `scripts/generate_macro_catalog.py` 가 매크로 레지스트리에서 생성한다.',
        '> **직접 수정하지 말 것** — 매크로를 고친 뒤 스크립트를 다시 돌린다.',
        '',
        '매크로는 재사용 가능한 함수이고, Job 은 매크로를 포함해 호출하는 단위다.',
        '설계 근거: [ADR 2026-08-11 매크로 계층](../adr/2026-08-11-macro-layer.md)',
        '',
        '## 읽는 법',
        '',
        f'- **requires** — 실행 전 충족돼야 하는 것. `{EXTERNAL_PREFIX}` 접두는 외부 선행조건'
        '(설정·학습 데이터)이고, 그 외는 앞선 매크로가 칠판에 남긴 산출물이다.',
        '- **produces** — 이 매크로가 칠판에 남기는 것. 뒤따르는 매크로가 `requires` 로 받는다.',
        '',
        f'## 매크로 ({len(payload["macros"])}개)',
        '',
    ]

    for name, spec in payload['macros'].items():
        lines += [f'### `{name}`', '', spec['summary'], '',
                  f"- 카테고리: `{spec['category']}`"]
        lines.append(f"- requires: {', '.join(f'`{r}`' for r in spec['requires']) or '없음'}")
        lines.append(f"- produces: {', '.join(f'`{p}`' for p in spec['produces']) or '없음'}")
        lines.append('')

        rows = _param_rows(spec['params'])
        if rows:
            lines += ['| 파라미터 | 타입 | 기본값 | 제약 | 설명 |',
                      '| --- | --- | --- | --- | --- |']
            lines += [f'| `{k}` | {t} | `{d}` | {c} | {desc} |' for k, t, d, c, desc in rows]
        else:
            lines.append('파라미터 없음')
        lines.append('')

    lines += [f'## 매크로를 포함한 Job ({len(payload["jobs_using_macros"])}개)', '',
              '| Job 타입 | 표시명 | 포함 매크로 |', '| --- | --- | --- |']
    for job_type, spec in payload['jobs_using_macros'].items():
        uses = ' → '.join(f"`{m['use']}`" for m in spec['macros'])
        lines.append(f"| `{job_type}` | {spec['name']} | {uses} |")
    lines.append('')

    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='매크로 카탈로그 생성')
    parser.add_argument('--out', default=None, help='출력 폴더 (기본: <workspace>/docs/macros)')
    parser.add_argument('--check', action='store_true',
                        help='생성하지 않고 기존 산출물이 최신인지만 검사')
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else _PKG_ROOT.parents[1] / 'docs' / 'macros'
    payload = build_payload()
    markdown = render_markdown(payload)
    catalog_json = json.dumps(payload, indent=2, ensure_ascii=False) + '\n'

    md_path = out_dir / 'CATALOG.md'
    json_path = out_dir / 'macros.json'

    if args.check:
        stale = [str(p) for p, expected in ((md_path, markdown), (json_path, catalog_json))
                 if not p.exists() or p.read_text(encoding='utf-8') != expected]
        if stale:
            print('카탈로그가 최신이 아닙니다:\n  ' + '\n  '.join(stale))
            print('해결: python3 scripts/generate_macro_catalog.py')
            return 1
        print(f"카탈로그 최신 (매크로 {len(payload['macros'])}개)")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding='utf-8')
    json_path.write_text(catalog_json, encoding='utf-8')
    print(f"생성 완료: {md_path}")
    print(f"생성 완료: {json_path}")
    print(f"매크로 {len(payload['macros'])}개 / 매크로 포함 Job {len(payload['jobs_using_macros'])}개")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
