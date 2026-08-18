#!/usr/bin/env python3
"""Validate the LLM-oriented contract and technical-debt document structure."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_DOCUMENT_FIELDS = {
    "id",
    "path",
    "status",
    "authority",
    "scopes",
    "keywords",
    "code_paths",
    "route_prefixes",
    "depends_on",
    "related_documents",
    "related_td",
    "max_lines",
    "legacy_order",
}
NON_DEFAULT_SCOPES = {"history", "draft", "archive"}


def _optimize_long_lines(text: str, limit: int = 500, chunk_limit: int = 360) -> str:
    output = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if in_fence or len(line) <= limit or line.lstrip().startswith("|"):
            output.append(line)
            continue
        bullet = re.match(r"^(\s*)-\s+(.*)$", line)
        indent = bullet.group(1) if bullet else re.match(r"^\s*", line).group(0)
        content = bullet.group(2) if bullet else line.strip()
        sentences = [part for part in re.split(r"(?<=[。；])", content) if part]
        chunks = []
        current = ""
        for sentence in sentences:
            if current and len(current) + len(sentence) > chunk_limit:
                chunks.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            chunks.append(current)
        if len(chunks) == 1:
            output.append(line)
        elif bullet:
            output.append(f"{indent}- {chunks[0]}")
            output.extend(f"{indent}  - {chunk}" for chunk in chunks[1:])
        else:
            output.append(("\n\n" + indent).join(chunks))
    return "\n".join(output) + ("\n" if text.endswith("\n") else "")


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise ValueError(f"Invalid manifest: {path}")
    return data


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_sections(text: str, pattern: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        raw = text[match.start():end]
        if pattern.startswith("^### "):
            next_h2 = re.search(r"(?m)^## ", raw[len(match.group(0)):])
            if next_h2:
                raw = raw[: len(match.group(0)) + next_h2.start() + 1]
        sections.append((match.group(1), raw.rstrip() + "\n"))
    return sections


def _check_markdown_links(root: Path, path: Path) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")
    for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
        target = match.group(1).strip()
        if not target or target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        candidate = (path.parent / target).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{path.relative_to(root)}: link escapes repository: {target}")
            continue
        if not candidate.exists():
            line = text.count("\n", 0, match.start()) + 1
            errors.append(f"{path.relative_to(root)}:{line}: broken link: {target}")
    return errors


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles = []
    visiting: list[str] = []
    visited = set()

    def visit(node: str):
        if node in visiting:
            start = visiting.index(node)
            cycles.append(visiting[start:] + [node])
            return
        if node in visited:
            return
        visiting.append(node)
        for target in graph.get(node, []):
            visit(target)
        visiting.pop()
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles


def _actual_code_surface(root: Path) -> set[tuple[str, str, int]]:
    actual = set()
    route_re = re.compile(r"@(?:router|app)\.(?:get|post|put|patch|delete|options|head)\(")
    for source in (root / "backend").rglob("*.py"):
        rel = source.relative_to(root).as_posix()
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if route_re.search(line):
                actual.add(("route", rel, line_no))
    model_re = re.compile(r"^class [A-Za-z_][A-Za-z0-9_]*\(Base\)")
    for source in (root / "backend" / "models").glob("*.py"):
        rel = source.relative_to(root).as_posix()
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if model_re.match(line):
                actual.add(("model", rel, line_no))
    for folder, kind in ((root / "admin" / "pages", "admin-page"), (root / "frontend" / "pages", "h5-page")):
        for source in folder.glob("*.html"):
            actual.add((kind, source.relative_to(root).as_posix(), 1))
    scheduler = root / "backend" / "tasks" / "scheduler.py"
    for line_no, line in enumerate(scheduler.read_text(encoding="utf-8").splitlines(), start=1):
        if "scheduler.add_job(" in line:
            actual.add(("scheduled-job", "backend/tasks/scheduler.py", line_no))
    return actual


def run_checks(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = root / "docs" / "llm-manifest.json"
    manifest = load_manifest(manifest_path)
    documents = manifest["documents"]
    ids = [item.get("id") for item in documents]
    id_counts = Counter(ids)
    errors.extend(f"duplicate document id: {doc_id}" for doc_id, count in id_counts.items() if count > 1)
    by_id = {item.get("id"): item for item in documents}

    allowed_authority = {"canonical", False}
    canonical_paths = defaultdict(list)
    for item in documents:
        missing = REQUIRED_DOCUMENT_FIELDS - set(item)
        if missing:
            errors.append(f"{item.get('id', '<unknown>')}: missing fields {sorted(missing)}")
            continue
        doc_id = item["id"]
        if item["authority"] not in allowed_authority:
            errors.append(f"{doc_id}: invalid authority {item['authority']!r}")
        path = root / item["path"]
        if not path.is_file():
            errors.append(f"{doc_id}: missing path {item['path']}")
            continue
        if item["authority"] == "canonical":
            canonical_paths[item["path"]].append(doc_id)
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > item["max_lines"]:
            errors.append(f"{doc_id}: {lines} lines exceeds max_lines={item['max_lines']}")
        if item["authority"] == "canonical" and path.suffix == ".md":
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if len(line) > 500 and not line.lstrip().startswith("|"):
                    errors.append(f"{doc_id}:{line_no}: prose line exceeds 500 characters")
        for code_path in item["code_paths"]:
            if not (root / code_path).exists():
                errors.append(f"{doc_id}: missing code path {code_path}")
        for dependency in item["depends_on"]:
            if dependency not in by_id:
                errors.append(f"{doc_id}: invalid dependency {dependency}")
        for related in item["related_documents"]:
            if related not in by_id:
                errors.append(f"{doc_id}: invalid related document {related}")
        if item["authority"] == "canonical":
            errors.extend(_check_markdown_links(root, path))
    errors.extend(f"multiple canonical documents at {path}: {doc_ids}" for path, doc_ids in canonical_paths.items() if len(doc_ids) > 1)

    td_ids = set(manifest.get("coverage", {}).get("tech_debts", []))
    for item in documents:
        for td_id in item.get("related_td", []):
            if td_id not in td_ids:
                errors.append(f"{item.get('id')}: invalid related TD {td_id}")

    graph = {item["id"]: item["depends_on"] for item in documents if item.get("id")}
    for cycle in _find_cycles(graph):
        errors.append("unapproved dependency cycle: " + " -> ".join(cycle))

    relation_types = set(manifest.get("relation_types", []))
    for relation in manifest.get("relations", []):
        if relation.get("type") not in relation_types:
            errors.append(f"invalid relation type: {relation}")
        if relation.get("from") not in by_id or relation.get("to") not in by_id:
            errors.append(f"invalid relation endpoint: {relation}")

    excluded = set(manifest.get("exclude_roots", []))
    required_exclusions = {".doc-migration-baseline", "docs/contract/history", "docs/contract/drafts", "docs/tech-debt/archive"}
    if not required_exclusions <= excluded:
        errors.append(f"missing exclusions: {sorted(required_exclusions - excluded)}")
    for scan_root in manifest.get("scan_roots", []):
        if any(scan_root == excluded_root or scan_root.startswith(excluded_root + "/") for excluded_root in excluded):
            errors.append(f"scan root overlaps exclusion: {scan_root}")
        if not (root / scan_root).exists():
            errors.append(f"missing scan root: {scan_root}")

    for source in (root / "docs").rglob("*.md"):
        rel = source.relative_to(root).as_posix()
        if any(rel == excluded_root or rel.startswith(excluded_root + "/") for excluded_root in excluded):
            continue
        text = source.read_text(encoding="utf-8")
        if re.search(r"(?:docs/)?(?:contract|tech-debt)\.md#[^\s)]+", text):
            errors.append(f"legacy exact-section reference remains: {rel}")

    contract_ids = manifest.get("coverage", {}).get("contract_sections", [])
    if len(contract_ids) != 98 or len(set(contract_ids)) != 98:
        errors.append(f"contract coverage is not 98 unique entries: {len(contract_ids)}/{len(set(contract_ids))}")
    if len(td_ids) != 37 or td_ids != {f"TD-{number:03d}" for number in range(1, 38)}:
        errors.append(f"tech-debt coverage is invalid: {len(td_ids)}")

    snapshot = root / ".doc-migration-baseline" / "snapshots" / "2026-07-19"
    sums = {}
    for line in (snapshot / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, filename = line.split(maxsplit=1)
        sums[filename] = digest
    for filename, expected in sums.items():
        actual = _sha256(snapshot / filename)
        if actual != expected:
            errors.append(f"baseline hash changed: {filename}: {actual} != {expected}")
    contract_source = (snapshot / "contract.original.md").read_text(encoding="utf-8")
    td_source = (snapshot / "tech-debt.original.md").read_text(encoding="utf-8")
    if len(contract_source.splitlines()) != 2460:
        errors.append("contract baseline line count changed")
    if len(re.findall(r"(?m)^## ", contract_source)) != 7:
        errors.append("contract baseline H2 count is not 7")
    source_contract_sections = _baseline_sections(contract_source, r"^### (.+)$")
    source_td_sections = _baseline_sections(td_source, r"^### \[(TD-\d{3})\].*$")
    if len(source_contract_sections) != 98:
        errors.append(f"contract baseline H3 count is {len(source_contract_sections)}, expected 98")
    if len(source_td_sections) != 37:
        errors.append(f"tech-debt baseline count is {len(source_td_sections)}, expected 37")

    contract_migration = manifest.get("migration_coverage", {}).get("contract_sections", [])
    if len(contract_migration) != 98:
        errors.append(f"contract migration table has {len(contract_migration)} entries")
    for source, item in zip(source_contract_sections, contract_migration):
        heading, section = source
        if item.get("source_heading") != heading:
            errors.append(f"contract legacy order mismatch at {item.get('id')}: {heading}")
        digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
        if item.get("sha256") != digest:
            errors.append(f"contract section hash mismatch: {item.get('id')}")
        target = root / item.get("target", "")
        migrated_section = section
        if str(item.get("target", "")).startswith("docs/contract/current/"):
            migrated_section = _optimize_long_lines(migrated_section)
            migrated_section = migrated_section.replace("](tech-debt.md)", "](../../../tech-debt.md)")
            migrated_section = migrated_section.replace("](contract.md)", "](../../../contract.md)")
        if not target.is_file() or migrated_section not in target.read_text(encoding="utf-8"):
            errors.append(f"contract section missing from target: {item.get('id')} -> {item.get('target')}")

    first_h2 = re.search(r"(?m)^## 数据库表结构$", contract_source)
    gaps_h2 = re.search(r"(?m)^## 契约对齐问题清单$", contract_source)
    openapi_h2 = re.search(r"(?m)^## Open API v1（第三方 API Key）$", contract_source)
    priority_h2 = re.search(r"(?m)^## 需要优先修复的问题（按影响程度排序）$", contract_source)
    unheaded_source = {
        "release-preamble": contract_source[:first_h2.start()].rstrip() + "\n",
        "known-gaps": contract_source[gaps_h2.start():openapi_h2.start()].rstrip() + "\n",
        "priority-fixes": contract_source[priority_h2.start():].rstrip() + "\n",
    }
    unheaded_migration = manifest.get("migration_coverage", {}).get("contract_unheaded_spans", [])
    if len(unheaded_migration) != 3:
        errors.append(f"contract unheaded migration table has {len(unheaded_migration)} entries")
    for item in unheaded_migration:
        span = unheaded_source.get(item.get("name"))
        if span is None:
            errors.append(f"unknown unheaded contract span: {item}")
            continue
        digest = hashlib.sha256(span.encode("utf-8")).hexdigest()
        if item.get("sha256") != digest:
            errors.append(f"unheaded contract span hash mismatch: {item.get('id')}")
        target = root / item.get("target", "")
        if not target.is_file() or span not in target.read_text(encoding="utf-8"):
            errors.append(f"unheaded contract span missing from target: {item.get('id')}")

    td_migration = manifest.get("migration_coverage", {}).get("tech_debts", [])
    td_source_map = dict(source_td_sections)
    if len(td_migration) != 37:
        errors.append(f"TD migration table has {len(td_migration)} entries")
    for item in td_migration:
        td_id = item.get("id")
        section = td_source_map.get(td_id)
        if section is None:
            errors.append(f"TD missing from baseline: {td_id}")
            continue
        digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
        if item.get("sha256") != digest:
            errors.append(f"TD section hash mismatch: {td_id}")
        detail = root / item.get("detail", "")
        migrated_td_section = _optimize_long_lines(section)
        if not detail.is_file() or migrated_td_section not in detail.read_text(encoding="utf-8"):
            errors.append(f"TD body missing from unique detail: {td_id}")
        detail_docs = [doc for doc in documents if doc.get("path") == item.get("detail") and doc.get("authority") == "canonical"]
        if len(detail_docs) != 1 or td_id not in detail_docs[0].get("related_td", []):
            errors.append(f"TD unique canonical mapping invalid: {td_id}")
        contract_backlinks = [doc for doc in documents if doc.get("id", "").startswith("contract-") and td_id in doc.get("related_td", [])]
        if not contract_backlinks:
            errors.append(f"TD has no contract backlink: {td_id}")

    coverage = manifest.get("code_surface_coverage", {})
    registered = {(item.get("kind"), item.get("path"), item.get("line")) for item in coverage.get("entries", [])}
    actual = _actual_code_surface(root)
    if registered != actual:
        missing = sorted(actual - registered)
        stale = sorted(registered - actual)
        if missing:
            errors.append(f"unmapped code surfaces: {missing[:10]} (total {len(missing)})")
        if stale:
            errors.append(f"stale code surfaces: {stale[:10]} (total {len(stale)})")
    for item in coverage.get("entries", []):
        if item.get("contract_document") not in by_id:
            errors.append(f"code surface has invalid contract document: {item}")

    for scenario in manifest.get("llm_retrieval_scenarios", []):
        for required in scenario.get("required", []):
            doc = by_id.get(required)
            if not doc:
                errors.append(f"scenario {scenario.get('id')} missing required document {required}")
                continue
            if doc.get("authority") != "canonical":
                errors.append(f"scenario {scenario.get('id')} loads non-canonical document {required}")
            if NON_DEFAULT_SCOPES.intersection(doc.get("scopes", [])):
                errors.append(f"scenario {scenario.get('id')} loads excluded scope in {required}")

    return {
        "errors": errors,
        "warnings": warnings,
        "contract_coverage": f"{len(contract_ids)}/98",
        "tech_debt_coverage": f"{len(td_ids)}/37",
        "code_surface_counts": coverage.get("counts", {}),
        "baseline_sha256": sums,
        "retrieval_scenarios": len(manifest.get("llm_retrieval_scenarios", [])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = run_checks(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
