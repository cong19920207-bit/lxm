#!/usr/bin/env python3
"""Build a new dated legacy-style snapshot without overwriting old snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def _join_documents(root: Path, documents: list[dict], prefix: str) -> str:
    selected = [
        item for item in documents
        if str(item.get("id", "")).startswith(prefix)
        and item.get("authority") == "canonical"
        and item.get("legacy_order", 0) > 0
        and item.get("status") in {"current", "active", "needs-review"}
    ]
    selected.sort(key=lambda item: (item.get("legacy_order", 0), item.get("path", "")))
    chunks = [(root / item["path"]).read_text(encoding="utf-8").rstrip() for item in selected]
    return "\n\n---\n\n".join(chunks).rstrip() + "\n" if chunks else ""


def build_snapshot(root: Path, date: str) -> Path:
    root = root.resolve()
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("--date must use YYYY-MM-DD") from exc
    target = root / ".doc-migration-baseline" / "snapshots" / date
    if target.exists():
        raise FileExistsError(f"snapshot already exists and will not be overwritten: {target}")

    manifest_path = root / "docs" / "llm-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    contract = _join_documents(root, documents, "contract-")
    tech_debt = _join_documents(root, documents, "tech-debt-")

    target.mkdir(parents=True)
    contract_path = target / "contract.original.md"
    tech_debt_path = target / "tech-debt.original.md"
    contract_path.write_text(contract, encoding="utf-8")
    tech_debt_path.write_text(tech_debt, encoding="utf-8")
    sums = {
        contract_path.name: hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        tech_debt_path.name: hashlib.sha256(tech_debt_path.read_bytes()).hexdigest(),
    }
    (target / "SHA256SUMS").write_text(
        "".join(f"{digest}  {filename}\n" for filename, digest in sums.items()),
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        f"# 契约与技术债人工快照（{date}）\n\n"
        "由用户明确要求后生成。此目录不参与默认扫描；旧快照不得覆盖。\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    target = build_snapshot(args.root, args.date)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
