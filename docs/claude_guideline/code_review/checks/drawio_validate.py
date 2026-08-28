#!/usr/bin/env python3
"""drawio_validate.py — 플로우차트 .drawio(diagrams.net) 박스·화살표 정확성 검증.

code_review / sw_structure SOP 의 "플로우차트 drawio 동반" 규칙 강제용.
검사 항목:
  1. XML well-formed (파싱 성공)
  2. 박스(vertex) id 수집
  3. 화살표(edge) 의 source/target 가 실재 박스 id 를 가리키는지 (dangling 0)
  4. (선택) --expect-nodes / --expect-edges 로 mermaid 흐름도와 노드·엣지 수 1:1 대조

사용법:
  drawio_validate.py <file.drawio> [--expect-nodes N] [--expect-edges M]
종료 코드: 0 통과 / 1 결함(파싱 실패·dangling·수 불일치)
"""
import sys
import argparse
import xml.etree.ElementTree as ET


def validate(path, expect_nodes=None, expect_edges=None):
    problems = []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, FileNotFoundError, OSError) as e:
        return [f"XML 파싱 실패: {e}"], 0, 0

    vertex_ids = set()
    edges = []  # (edge_id, source, target)
    for c in root.iter("mxCell"):
        cid = c.get("id")
        if c.get("vertex") == "1":
            vertex_ids.add(cid)
        elif c.get("edge") == "1":
            edges.append((cid, c.get("source"), c.get("target")))

    if not vertex_ids:
        problems.append("박스(vertex) 0개 — 빈 그래프")

    for eid, src, tgt in edges:
        if src is None or tgt is None:
            problems.append(f"화살표 {eid}: source/target 누락 (src={src}, tgt={tgt})")
            continue
        if src not in vertex_ids:
            problems.append(f"화살표 {eid}: source '{src}' 가 실재 박스 아님 (dangling)")
        if tgt not in vertex_ids:
            problems.append(f"화살표 {eid}: target '{tgt}' 가 실재 박스 아님 (dangling)")

    if expect_nodes is not None and len(vertex_ids) != expect_nodes:
        problems.append(f"박스 수 불일치: drawio={len(vertex_ids)} != mermaid 기대={expect_nodes}")
    if expect_edges is not None and len(edges) != expect_edges:
        problems.append(f"화살표 수 불일치: drawio={len(edges)} != mermaid 기대={expect_edges}")

    return problems, len(vertex_ids), len(edges)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio")
    ap.add_argument("--expect-nodes", type=int, default=None)
    ap.add_argument("--expect-edges", type=int, default=None)
    args = ap.parse_args()

    problems, nboxes, nedges = validate(args.drawio, args.expect_nodes, args.expect_edges)
    if problems:
        print(f"❌ {args.drawio}: 박스 {nboxes}, 화살표 {nedges} — 결함 {len(problems)}건")
        for p in problems:
            print(f"   - {p}")
        sys.exit(1)
    print(f"✅ {args.drawio}: 박스 {nboxes}개, 화살표 {nedges}개, dangling 0 — 통과")
    sys.exit(0)


if __name__ == "__main__":
    main()
