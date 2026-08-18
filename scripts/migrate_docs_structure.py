#!/usr/bin/env python3
"""One-time, lossless contract/technical-debt document migration.

This script intentionally reads the frozen 2026-07-19 baseline by exact path.
Ordinary documentation tasks must not scan that directory.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
BASELINE = REPO / ".doc-migration-baseline" / "snapshots" / "2026-07-19"
DOCS = REPO / "docs"


CONTRACT_TARGETS = {
    "shared-conventions": "docs/contract/current/_shared/conventions.md",
    "shared-auth-rbac": "docs/contract/current/_shared/auth-rbac.md",
    "core-user-auth-data": "docs/contract/current/core-user-auth/data.md",
    "core-user-auth-api": "docs/contract/current/core-user-auth/api.md",
    "h5-app-api": "docs/contract/current/h5-app/api.md",
    "chat-emotion-data": "docs/contract/current/chat-emotion/data.md",
    "chat-emotion-api": "docs/contract/current/chat-emotion/api.md",
    "memory-knowledge-data": "docs/contract/current/memory-knowledge/data.md",
    "memory-knowledge-api": "docs/contract/current/memory-knowledge/api.md",
    "memory-knowledge-admin": "docs/contract/current/memory-knowledge/admin-ui.md",
    "diary-data": "docs/contract/current/diary/data.md",
    "diary-api": "docs/contract/current/diary/api.md",
    "diary-admin": "docs/contract/current/diary/admin-ui.md",
    "relationship-data": "docs/contract/current/relationship/data.md",
    "relationship-api": "docs/contract/current/relationship/api.md",
    "relationship-admin": "docs/contract/current/relationship/admin-ui.md",
    "agent-future-data": "docs/contract/current/agent-future/data.md",
    "agent-future-api": "docs/contract/current/agent-future/api.md",
    "agent-future-admin": "docs/contract/current/agent-future/admin-ui.md",
    "persona-data": "docs/contract/current/persona-prompt-world-state/data.md",
    "persona-api": "docs/contract/current/persona-prompt-world-state/api.md",
    "persona-admin": "docs/contract/current/persona-prompt-world-state/admin-ui.md",
    "life-feed-data": "docs/contract/current/life-feed/data.md",
    "life-feed-api": "docs/contract/current/life-feed/api.md",
    "life-feed-admin": "docs/contract/current/life-feed/admin-ui.md",
    "admin-security-data": "docs/contract/current/admin-security-accounts/data.md",
    "admin-security-api": "docs/contract/current/admin-security-accounts/api.md",
    "observability-api": "docs/contract/current/observability-third-party/api.md",
    "observability-admin": "docs/contract/current/observability-third-party/admin-ui.md",
    "openapi-data": "docs/contract/current/openapi/data.md",
    "openapi-api": "docs/contract/current/openapi/api.md",
    "history-implementation": "docs/contract/history/implementation-log.md",
}


TD_GROUPS = {
    "TD-001": "core-user-auth",
    "TD-002": "persona-prompt-world-state",
    "TD-003": "persona-prompt-world-state",
    "TD-004": "agent-future",
    "TD-005": "relationship",
    "TD-006": "diary",
    "TD-007": "diary",
    "TD-008": "observability-third-party",
    "TD-009": "observability-third-party",
    "TD-010": "observability-third-party",
    "TD-011": "observability-third-party",
    "TD-012": "observability-third-party",
    "TD-013": "diary",
    "TD-014": "diary",
    "TD-015": "chat-emotion",
    "TD-016": "chat-emotion",
    "TD-017": "memory-knowledge",
    "TD-018": "diary",
    "TD-019": "chat-emotion",
    "TD-020": "chat-emotion",
    "TD-021": "persona-prompt-world-state",
    "TD-022": "memory-knowledge",
    "TD-023": "memory-knowledge",
    "TD-024": "core-user-auth",
    "TD-025": "core-user-auth",
    "TD-026": "memory-knowledge",
    "TD-027": "memory-knowledge",
    "TD-028": "memory-knowledge",
    "TD-029": "memory-knowledge",
    "TD-030": "cross-cutting",
    "TD-031": "openapi",
    "TD-032": "life-feed",
    "TD-033": "life-feed",
    "TD-034": "life-feed",
    "TD-035": "life-feed",
    "TD-036": "life-feed",
    "TD-037": "life-feed",
}


TD_RELATED = {
    "TD-015": ["h5-app", "agent-future"],
    "TD-018": ["chat-emotion"],
    "TD-020": ["persona-prompt-world-state"],
    "TD-023": ["chat-emotion"],
    "TD-024": ["h5-app"],
    "TD-025": ["h5-app"],
    "TD-030": ["chat-emotion", "openapi"],
    "TD-033": ["observability-third-party"],
}


TD_DEPENDS = {
    "TD-015": ["TD-016"],
    "TD-017": ["TD-023"],
    "TD-023": ["TD-022"],
    "TD-028": ["TD-026"],
    "TD-029": ["TD-028"],
}


CODE_PATHS = {
    "shared-conventions": ["backend/main.py"],
    "shared-auth-rbac": ["backend/utils/admin_auth.py", "backend/routers/admin/auth.py"],
    "core-user-auth": ["backend/models/user.py", "backend/routers/auth.py", "backend/routers/user.py"],
    "h5-app": ["backend/routers/app.py", "frontend/pages/index.html"],
    "chat-emotion": ["backend/routers/chat.py", "backend/services/chat_service.py", "backend/models/emotion_log.py"],
    "memory-knowledge": ["backend/routers/memory.py", "backend/services/memory_service.py", "backend/services/step6_orchestrator.py"],
    "diary": ["backend/routers/diary.py", "backend/services/diary_service.py", "backend/tasks/ai_diary_task.py"],
    "relationship": ["backend/routers/relationship.py", "backend/services/relationship_service.py"],
    "agent-future": ["backend/routers/agent.py", "backend/services/future_handler.py", "backend/tasks/agent_message_task.py"],
    "persona-prompt-world-state": ["backend/models/world_state.py", "backend/services/prompt_builder.py", "backend/routers/admin/persona.py"],
    "life-feed": ["backend/routers/feed.py", "backend/services/feed_service.py", "backend/tasks/life_feed_task.py"],
    "admin-security-accounts": ["backend/routers/admin/accounts.py", "backend/routers/admin/users.py", "backend/routers/admin/operation_logs.py"],
    "observability-third-party": ["backend/routers/admin/system_monitor.py", "backend/routers/admin/stats.py"],
    "openapi": ["backend/routers/open/chat.py", "backend/routers/open/agent.py", "backend/services/open_api_key_service.py"],
    "cross-cutting": ["backend/services/content_safety_service.py"],
}


ROUTE_PREFIXES = {
    "core-user-auth": ["/api/auth", "/api/user"],
    "h5-app": ["/api/app"],
    "chat-emotion": ["/api/chat"],
    "memory-knowledge": ["/api/memory", "/api/admin/memory"],
    "diary": ["/api/diary"],
    "relationship": ["/api/relationship"],
    "agent-future": ["/api/agent"],
    "persona-prompt-world-state": ["/api/admin/persona", "/api/admin/prompts"],
    "life-feed": ["/api/feed", "/api/admin/feed"],
    "admin-security-accounts": ["/api/admin/auth", "/api/admin/accounts", "/api/admin/users"],
    "observability-third-party": ["/api/admin/stats", "/api/admin/system"],
    "openapi": ["/api/open/v1", "/api/admin/users/{user_id}/open-api-key"],
}


SCOPE_DOCUMENTS = {
    "shared-conventions": "contract-shared-conventions",
    "shared-auth-rbac": "contract-shared-auth-rbac",
    "core-user-auth": "contract-core-user-auth-api",
    "h5-app": "contract-h5-app-api",
    "chat-emotion": "contract-chat-emotion-api",
    "memory-knowledge": "contract-memory-knowledge-api",
    "diary": "contract-diary-api",
    "relationship": "contract-relationship-api",
    "agent-future": "contract-agent-future-api",
    "persona-prompt-world-state": "contract-persona-api",
    "life-feed": "contract-life-feed-api",
    "admin-security-accounts": "contract-admin-security-api",
    "observability-third-party": "contract-observability-api",
    "openapi": "contract-openapi-api",
    "cross-cutting": "contract-known-gaps",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def optimize_long_lines(text: str, limit: int = 500, chunk_limit: int = 360) -> str:
    """Split oversized prose at sentence boundaries without changing wording."""
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


def split_h3(text: str):
    matches = list(re.finditer(r"(?m)^### (.+)$", text))
    return [
        {
            "heading": match.group(1).strip(),
            "text": text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)].rstrip() + "\n",
        }
        for index, match in enumerate(matches)
    ]


def contract_target(heading: str, parent: str) -> str:
    if parent == "开发日志":
        return "history-implementation"
    if parent.startswith("Open API"):
        return "openapi-data" if "表名" in heading else "openapi-api"
    if parent == "数据库表结构":
        if heading == "表名：users":
            return "core-user-auth-data"
        if any(term in heading for term in ("relationship", "growth_log", "level_history", "change_history")):
            return "relationship-data"
        if any(term in heading for term in ("conversation_log", "emotion_log", "user_short_term_emotion")):
            return "chat-emotion-data"
        if heading == "表名：memory":
            return "memory-knowledge-data"
        if heading == "表名：ai_diary":
            return "diary-data"
        if heading == "表名：agent_message":
            return "agent-future-data"
        if heading == "表名：world_state":
            return "persona-data"
        if heading == "表名：user_timeline_seq":
            return "openapi-data"
        if any(term in heading for term in ("admin_users", "admin_config", "admin_operation_logs", "login_log")):
            return "admin-security-data"
        if "生活流新增表" in heading:
            return "life-feed-data"
    if parent == "接口定义":
        if heading == "统一说明":
            return "shared-conventions"
        if "管理后台认证" in heading or "管理后台账号" in heading or "观察者统一权限" in heading:
            return "shared-auth-rbac"
        if "H5 认证" in heading or "H5 用户" in heading:
            return "core-user-auth-api"
        if "H5 应用" in heading:
            return "h5-app-api"
        if "H5 对话" in heading:
            return "chat-emotion-api"
        if "日记" in heading and "关系规则" not in heading:
            return "diary-api"
        if "H5 记忆" in heading or "记忆与向量" in heading or "向量召回" in heading:
            return "memory-knowledge-api"
        if "主动消息" in heading or "Agent 管理" in heading:
            return "agent-future-api"
        if "H5 关系" in heading or "关系规则与日记" in heading:
            return "relationship-api"
        if "生活流" in heading or "朋友圈" in heading:
            return "life-feed-api"
        if any(term in heading for term in ("角色知识库", "人格 / 情绪", "世界观", "Prompt / 安全")):
            return "persona-api"
        if "数据统计" in heading or "系统监控与第三方" in heading:
            return "observability-api"
        return "admin-security-api"
    if parent == "管理端页面":
        if any(term in heading for term in ("system-monitor", "system-logs", "third-party", "dashboard", "data-report")):
            return "observability-admin"
        if any(term in heading for term in ("persona", "prompt.html", "step5-5", "对话流 Prompt", "test-tool", "safety-rules", "knowledge")):
            return "persona-admin"
        if "memory-rules" in heading:
            return "memory-knowledge-admin"
        if "agent-rules" in heading:
            return "agent-future-admin"
        if "relationship-rules" in heading or "技术债记录" in heading:
            return "relationship-admin"
        if "diary-" in heading:
            return "diary-admin"
        if "生活流管理页" in heading:
            return "life-feed-admin"
    raise ValueError(f"No target for {parent!r} / {heading!r}")


def parent_for_position(text: str, position: int) -> str:
    parents = list(re.finditer(r"(?m)^## (.+)$", text[:position]))
    return parents[-1].group(1).strip() if parents else ""


def scope_from_target(target: str) -> str:
    mapping = {
        "shared-conventions": "shared-conventions",
        "shared-auth-rbac": "shared-auth-rbac",
        "core-user-auth": "core-user-auth",
        "h5-app": "h5-app",
        "chat-emotion": "chat-emotion",
        "memory-knowledge": "memory-knowledge",
        "diary": "diary",
        "relationship": "relationship",
        "agent-future": "agent-future",
        "persona": "persona-prompt-world-state",
        "life-feed": "life-feed",
        "admin-security": "admin-security-accounts",
        "observability": "observability-third-party",
        "openapi": "openapi",
        "history": "history",
    }
    for prefix, scope in mapping.items():
        if target.startswith(prefix):
            return scope
    raise ValueError(target)


def metadata(doc_id: str, scope: str, dependencies: list[str], related_td: list[str], authority="canonical") -> str:
    dep_text = ", ".join(f"`{item}`" for item in dependencies) or "无"
    td_text = ", ".join(f"`{item}`" for item in related_td) or "无"
    return (
        f"- 文档 ID：`{doc_id}`\n"
        f"- 权威状态：`{authority}`\n"
        f"- 功能范围：`{scope}`\n"
        f"- 必读依赖：{dep_text}\n"
        f"- 相关技术债：{td_text}\n\n"
    )


def related_td_for_scope(scope: str) -> list[str]:
    return [td for td, primary in TD_GROUPS.items() if primary == scope or scope in TD_RELATED.get(td, [])]


def write_contract(contract_text: str):
    h3_matches = list(re.finditer(r"(?m)^### (.+)$", contract_text))
    grouped = defaultdict(list)
    coverage = []
    for index, match in enumerate(h3_matches, start=1):
        end = h3_matches[index].start() if index < len(h3_matches) else len(contract_text)
        # Sections under the final H2 stop at the file end; other sections stop at next H3,
        # which intentionally retains intervening H2 text only in explicit unheaded spans below.
        raw = contract_text[match.start():end]
        next_h2 = re.search(r"(?m)^## ", raw[len(match.group(0)):])
        if next_h2:
            raw = raw[: len(match.group(0)) + next_h2.start() + 1]
        section = raw.rstrip() + "\n"
        parent = parent_for_position(contract_text, match.start())
        target_key = contract_target(match.group(1).strip(), parent)
        grouped[target_key].append(section)
        coverage.append(
            {
                "id": f"C-{index:03d}",
                "legacy_order": index,
                "source_heading": match.group(1).strip(),
                "source_parent": parent,
                "disposition": "historical" if target_key.startswith("history-") else "current",
                "target": CONTRACT_TARGETS[target_key],
                "sha256": sha(section),
            }
        )

    for order, (target_key, rel_path) in enumerate(CONTRACT_TARGETS.items(), start=1):
        sections = grouped.get(target_key)
        if not sections:
            continue
        scope = scope_from_target(target_key)
        authority = "false" if scope == "history" else "canonical"
        dependencies = [] if scope in ("shared-conventions", "history") else ["contract-shared-conventions"]
        if scope in ("admin-security-accounts", "observability-third-party"):
            dependencies.append("contract-shared-auth-rbac")
        if scope == "openapi":
            dependencies.extend(["contract-chat-emotion-api", "contract-agent-future-api"])
        title = target_key.replace("-", " ").title()
        body = f"# {title}\n\n" + metadata(
            f"contract-{target_key}", scope, dependencies, related_td_for_scope(scope), authority
        ) + "\n".join(sections)
        if scope != "history":
            body = optimize_long_lines(body)
            body = body.replace("](tech-debt.md)", "](../../../tech-debt.md)")
            body = body.replace("](contract.md)", "](../../../contract.md)")
        path = REPO / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body.rstrip() + "\n", encoding="utf-8")

    spans = []
    first_h2 = re.search(r"(?m)^## 数据库表结构$", contract_text)
    preamble = contract_text[: first_h2.start()].rstrip() + "\n"
    history_path = DOCS / "contract" / "history" / "release-summary.md"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "# 迁移前发布摘要\n\n" + metadata("contract-history-release-summary", "history", [], [], "false") + preamble,
        encoding="utf-8",
    )
    spans.append({"id": "U-001", "name": "release-preamble", "target": "docs/contract/history/release-summary.md", "sha256": sha(preamble), "text": preamble})

    def h2_body(name: str, next_name: str | None) -> str:
        start = re.search(rf"(?m)^## {re.escape(name)}$", contract_text)
        if not start:
            return ""
        if next_name:
            end = re.search(rf"(?m)^## {re.escape(next_name)}$", contract_text[start.end():])
            stop = start.end() + end.start() if end else len(contract_text)
        else:
            stop = len(contract_text)
        return contract_text[start.start():stop].rstrip() + "\n"

    gaps = h2_body("契约对齐问题清单", "Open API v1（第三方 API Key）")
    priorities = h2_body("需要优先修复的问题（按影响程度排序）", None)
    gap_path = DOCS / "contract" / "known-gaps.md"
    gap_path.write_text(
        "# 契约已知缺口\n\n"
        + metadata("contract-known-gaps", "cross-cutting", ["contract-index"], sorted(TD_GROUPS), "canonical")
        + gaps
        + "\n"
        + priorities,
        encoding="utf-8",
    )
    spans.extend([
        {"id": "U-002", "name": "known-gaps", "target": "docs/contract/known-gaps.md", "sha256": sha(gaps), "text": gaps},
        {"id": "U-003", "name": "priority-fixes", "target": "docs/contract/known-gaps.md", "sha256": sha(priorities), "text": priorities},
    ])
    return coverage, spans


def td_status(heading: str) -> str:
    if "已清偿" in heading:
        return "已清偿（原文状态，待用户确认归档）"
    if "部分清偿" in heading or "已缓解" in heading or "进行中" in heading:
        return "部分完成（原文状态）"
    if "已交付" in heading or "已处理" in heading:
        return "已处理（原文状态，待用户确认归档）"
    if "待评估" in heading:
        return "待评估"
    return "待清偿"


def extract_code_evidence(section: str) -> list[str]:
    candidates = re.findall(r"`((?:backend|frontend|admin|scripts|tests)/[^`\s:]+)", section)
    return sorted({candidate.rstrip(".,，。)") for candidate in candidates if (REPO / candidate.rstrip(".,，。)")).exists()})


def write_tech_debt(td_text: str):
    matches = list(re.finditer(r"(?m)^### \[(TD-\d{3})\] (.+)$", td_text))
    grouped = defaultdict(list)
    coverage = []
    rows = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(td_text)
        section = td_text[match.start():end].rstrip() + "\n"
        td_id = match.group(1)
        group = TD_GROUPS[td_id]
        rel_path = f"docs/tech-debt/active/{group}.md"
        grouped[group].append(section)
        status = td_status(match.group(2))
        evidence = extract_code_evidence(section)
        coverage.append(
            {
                "id": td_id,
                "legacy_order": index + 1,
                "original_status": status,
                "primary_scope": group,
                "related_scopes": TD_RELATED.get(td_id, []),
                "depends_on": TD_DEPENDS.get(td_id, []),
                "code_evidence": evidence,
                "detail": rel_path,
                "sha256": sha(section),
            }
        )
        rows.append((td_id, match.group(2).strip(), status, group, rel_path))

    for group, sections in grouped.items():
        rel_path = f"docs/tech-debt/active/{group}.md"
        ids = [item["id"] for item in coverage if item["primary_scope"] == group]
        body = (
            f"# {group} 技术债\n\n"
            + metadata(f"tech-debt-{group}", group, [], ids, "canonical")
            + "> 状态完全沿用迁移源；本次迁移不确认清偿、不执行归档。\n\n"
            + "\n".join(sections)
        )
        body = optimize_long_lines(body)
        path = REPO / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body.rstrip() + "\n", encoding="utf-8")

    index_lines = [
        "# 技术债兼容索引",
        "",
        "- 文档 ID：`tech-debt-index`",
        "- 权威状态：`canonical`（编号、状态与详情路由）",
        "- 默认详情：`docs/tech-debt/active/`",
        "- 归档门禁：只有代码核验完成且用户明确确认后才移入 `archive/`",
        "",
        "本文件保留全部 37 个编号，但不再承载详情正文。状态文字来自迁移源，未在本次迁移中改判。",
        "",
        "| 编号 | 原标题 | 迁移状态 | 主要功能 | 唯一详情 |",
        "|---|---|---|---|---|",
    ]
    for td_id, title, status, group, rel_path in rows:
        anchor = td_id.lower()
        link = rel_path.removeprefix("docs/") + f"#{anchor}"
        safe_title = title.replace("|", "\\|")
        index_lines.append(f"| {td_id} | {safe_title} | {status} | `{group}` | [{rel_path}]({link}) |")
    (DOCS / "tech-debt.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    archive = DOCS / "tech-debt" / "archive" / "README.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text(
        "# 技术债归档\n\n"
        + metadata("tech-debt-archive", "archive", [], [], "false")
        + "只有经过代码核验并取得用户明确确认的完成项才能迁入本目录。迁移后，根索引仍须保留原编号、状态、归档日期与链接。\n",
        encoding="utf-8",
    )
    return coverage


def document_entry(doc_id: str, path: str, status: str, authority, scopes: list[str], keywords: list[str], code_paths: list[str], route_prefixes: list[str], depends_on: list[str], related_documents: list[str], related_td: list[str], max_lines: int, legacy_order: int):
    return {
        "id": doc_id,
        "path": path,
        "status": status,
        "authority": authority,
        "scopes": scopes,
        "keywords": keywords,
        "code_paths": code_paths,
        "route_prefixes": route_prefixes,
        "depends_on": depends_on,
        "related_documents": related_documents,
        "related_td": related_td,
        "max_lines": max_lines,
        "legacy_order": legacy_order,
    }


def make_manifest(contract_coverage, unheaded_spans, td_coverage):
    documents = []
    documents.append(document_entry("docs-index", "docs/INDEX.md", "current", "canonical", ["routing"], ["索引", "任务路由"], [], [], [], ["contract-index", "tech-debt-index"], [], 150, -2))
    documents.append(document_entry("contract-index", "docs/contract.md", "current", "canonical", ["routing"], ["契约", "兼容入口"], [], [], [], [], [], 150, -1))
    order = 1
    for target_key, rel_path in CONTRACT_TARGETS.items():
        if not (REPO / rel_path).exists():
            continue
        scope = scope_from_target(target_key)
        authority = False if scope == "history" else "canonical"
        status = "history" if scope == "history" else "current"
        depends = [] if scope in ("shared-conventions", "history") else ["contract-shared-conventions"]
        if scope in ("admin-security-accounts", "observability-third-party"):
            depends.append("contract-shared-auth-rbac")
        if scope == "openapi":
            depends.extend(["contract-chat-emotion-api", "contract-agent-future-api"])
        documents.append(document_entry(
            f"contract-{target_key}", rel_path, status, authority, [scope], [scope, target_key],
            CODE_PATHS.get(scope, []), ROUTE_PREFIXES.get(scope, []), depends, [], related_td_for_scope(scope),
            1000 if status == "history" else (600 if target_key.endswith("-data") else 400), order,
        ))
        order += 1
    documents.extend([
        document_entry("contract-known-gaps", "docs/contract/known-gaps.md", "needs-review", "canonical", ["cross-cutting"], ["缺口", "冲突", "待确认"], [], [], ["contract-index"], [], sorted(TD_GROUPS), 400, 900),
        document_entry("contract-history-release-summary", "docs/contract/history/release-summary.md", "history", False, ["history"], ["发布摘要", "历史"], [], [], [], [], [], 400, 901),
    ])
    for draft in sorted((DOCS / "contract" / "drafts").glob("**/*.md")):
        rel = draft.relative_to(REPO).as_posix()
        documents.append(document_entry("contract-draft-" + sha(rel)[:12], rel, "draft", False, ["draft"], ["草案"], [], [], [], [], [], 2000, 0))

    documents.append(document_entry("tech-debt-index", "docs/tech-debt.md", "current", "canonical", ["tech-debt"], ["技术债", "TD"], [], [], [], [], sorted(TD_GROUPS), 150, -1))
    for group in sorted(set(TD_GROUPS.values())):
        rel = f"docs/tech-debt/active/{group}.md"
        td_ids = [item["id"] for item in td_coverage if item["primary_scope"] == group]
        deps = sorted({dep for item in td_coverage if item["primary_scope"] == group for dep in item["depends_on"]})
        contract_links = [item["id"] for item in documents if group in item["scopes"] and str(item["id"]).startswith("contract-")]
        documents.append(document_entry(
            f"tech-debt-{group}", rel, "active", "canonical", [group], [group, "技术债"],
            CODE_PATHS.get(group, []), ROUTE_PREFIXES.get(group, []), [],
            contract_links + [f"tech-debt-{TD_GROUPS[dep]}" for dep in deps if TD_GROUPS[dep] != group], td_ids, 700, 1000 + len(documents),
        ))
    documents.append(document_entry("tech-debt-archive", "docs/tech-debt/archive/README.md", "archive", False, ["archive"], ["技术债归档"], [], [], [], [], [], 150, 0))
    audit_path = DOCS / "tech-debt" / "audit-2026-07-19.md"
    if audit_path.exists():
        documents.append(document_entry("tech-debt-audit-2026-07-19", "docs/tech-debt/audit-2026-07-19.md", "audit", False, ["audit"], ["技术债核查", "代码证据"], [], [], [], [], sorted(TD_GROUPS), 250, 0))

    relations = [
        {"from": "contract-openapi-api", "type": "depends_on", "to": "contract-chat-emotion-api"},
        {"from": "contract-openapi-api", "type": "depends_on", "to": "contract-agent-future-api"},
        {"from": "contract-known-gaps", "type": "related_to", "to": "tech-debt-index"},
        {"from": "tech-debt-cross-cutting", "type": "extends", "to": "contract-chat-emotion-api"},
        {"from": "tech-debt-cross-cutting", "type": "extends", "to": "contract-openapi-api"},
    ]
    manifest = {
        "version": 1,
        "generated_from": ".doc-migration-baseline/snapshots/2026-07-19",
        "scan_roots": ["docs/INDEX.md", "docs/contract.md", "docs/contract/current", "docs/contract/known-gaps.md", "docs/tech-debt.md", "docs/tech-debt/active"],
        "exclude_roots": [".doc-migration-baseline", "docs/contract/history", "docs/contract/drafts", "docs/tech-debt/archive", "docs/tech-debt/audit-2026-07-19.md"],
        "relation_types": ["depends_on", "extends", "related_to", "supersedes", "blocks", "resolved_by"],
        "documents": documents,
        "relations": relations,
        "coverage": {
            "contract_sections": [item["id"] for item in contract_coverage],
            "tech_debts": [item["id"] for item in td_coverage],
        },
        "migration_coverage": {
            "contract_sections": contract_coverage,
            "contract_unheaded_spans": [{key: value for key, value in item.items() if key != "text"} for item in unheaded_spans],
            "tech_debts": td_coverage,
        },
        "llm_retrieval_scenarios": [
            {"id": "feed-comments", "query": "朋友圈评论", "required": ["contract-life-feed-api", "contract-life-feed-admin"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "openapi-resend", "query": "OpenAPI resend", "required": ["contract-openapi-api", "contract-chat-emotion-api", "contract-shared-conventions"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "observer-export", "query": "observer 导出", "required": ["contract-shared-auth-rbac", "contract-admin-security-api"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "diary-timezone", "query": "日记时区", "required": ["contract-diary-api", "contract-shared-conventions"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "step6-vector", "query": "Step6 向量", "required": ["contract-memory-knowledge-api", "contract-memory-knowledge-data", "tech-debt-memory-knowledge"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "future-message", "query": "Future 主动消息", "required": ["contract-agent-future-api", "contract-agent-future-data"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "system-monitor", "query": "系统监控", "required": ["contract-observability-api", "contract-observability-admin", "contract-shared-auth-rbac"], "forbidden_scopes": ["history", "draft", "archive"]},
            {"id": "password-api", "query": "密码接口", "required": ["contract-core-user-auth-api", "contract-shared-conventions", "tech-debt-core-user-auth"], "forbidden_scopes": ["history", "draft", "archive"]},
        ],
    }
    (DOCS / "llm-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_contract_index():
    lines = [
        "# 契约文档兼容入口",
        "",
        "- 文档 ID：`contract-index`",
        "- 权威状态：`canonical`（只负责路由；规则正文以 `contract/current/` 为准）",
        "- 最后迁移：2026-07-19",
        "- 机器入口：[llm-manifest.json](llm-manifest.json)",
        "",
        "原单文件正文已无损保存在 `.doc-migration-baseline/snapshots/2026-07-19/contract.original.md`。该基线不参与默认扫描，未经用户明确要求不得读取、覆盖或删除。",
        "",
        "## 按功能路由",
        "",
        "| 功能 | 当前权威文档 |",
        "|---|---|",
    ]
    scopes = defaultdict(list)
    for key, rel in CONTRACT_TARGETS.items():
        if key.startswith("history") or not (REPO / rel).exists():
            continue
        scopes[scope_from_target(key)].append(rel.removeprefix("docs/contract/"))
    for scope, paths in scopes.items():
        links = "、".join(f"[{Path(path).name}](contract/{path})" for path in paths)
        lines.append(f"| `{scope}` | {links} |")
    lines.extend([
        "",
        "## 非默认来源",
        "",
        "- [已知缺口](contract/known-gaps.md)：代码与契约差异、待确认项。",
        "- `contract/history/`：历史发布摘要与实施日志，`authority=false`。",
        "- `contract/drafts/`：草案，`authority=false`。",
        "- [技术债索引](tech-debt.md)：37 个编号的状态与详情路由。",
        "",
        "## 维护规则",
        "",
        "当前功能变更只更新 `contract/current/`、`tech-debt/active/` 与 manifest。历史文件只有在用户明确要求时才人工勘误；生成旧版单文件时必须创建新日期快照，不能覆盖旧快照。",
    ])
    (DOCS / "contract.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def classify_code_path(path: str) -> str:
    name = Path(path).stem
    if "/open/" in path or name == "user_api_key":
        return "openapi"
    if any(term in path for term in ("feed", "life_plan", "life_config", "life_prompt", "her_universe", "comment_reply", "like_aware", "read_aware")):
        return "life-feed"
    if any(term in path for term in ("memory", "vector", "knowledge", "step6", "query_rewrite", "multi_vector")):
        return "memory-knowledge"
    if "diary" in path:
        return "diary"
    if "relationship" in path or "daily_growth" in path:
        return "relationship"
    if any(term in path for term in ("agent", "future")):
        return "agent-future"
    if any(term in path for term in ("chat", "conversation", "emotion")):
        return "chat-emotion"
    if any(term in path for term in ("persona", "prompt", "world", "safety", "test_cases")):
        return "persona-prompt-world-state"
    if any(term in path for term in ("system_monitor", "stats", "third-party", "dashboard", "data-report", "system-logs")):
        return "observability-third-party"
    if any(term in path for term in ("auth", "user", "account", "operation", "login", "settings")):
        return "core-user-auth" if not path.startswith("admin/") and "/admin/" not in path else "admin-security-accounts"
    if path == "frontend/pages/index.html" or path.endswith("/app.py"):
        return "h5-app"
    if path == "backend/main.py":
        return "shared-conventions"
    return "admin-security-accounts"


def build_code_surface_coverage():
    entries = []
    manifest_ids = {
        item["id"]
        for item in json.loads((DOCS / "llm-manifest.json").read_text(encoding="utf-8"))["documents"]
    }
    route_re = re.compile(r"@(?:router|app)\.(?:get|post|put|patch|delete|options|head)\((.*)")
    for source in sorted((REPO / "backend").rglob("*.py")):
        rel = source.relative_to(REPO).as_posix()
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            match = route_re.search(line)
            if not match:
                continue
            scope = classify_code_path(rel)
            entries.append({"kind": "route", "path": rel, "line": line_no, "symbol": line.strip(), "scope": scope, "contract_document": SCOPE_DOCUMENTS[scope]})

    model_re = re.compile(r"^class ([A-Za-z_][A-Za-z0-9_]*)\(Base\)")
    for source in sorted((REPO / "backend" / "models").glob("*.py")):
        rel = source.relative_to(REPO).as_posix()
        for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            match = model_re.match(line)
            if not match:
                continue
            scope = classify_code_path(rel)
            doc_id = SCOPE_DOCUMENTS[scope].replace("-api", "-data")
            if doc_id not in manifest_ids:
                doc_id = SCOPE_DOCUMENTS[scope]
            entries.append({"kind": "model", "path": rel, "line": line_no, "symbol": match.group(1), "scope": scope, "contract_document": doc_id})

    for root, kind in ((REPO / "admin" / "pages", "admin-page"), (REPO / "frontend" / "pages", "h5-page")):
        for source in sorted(root.glob("*.html")):
            rel = source.relative_to(REPO).as_posix()
            scope = classify_code_path(rel)
            doc_id = SCOPE_DOCUMENTS[scope]
            if kind == "admin-page":
                admin_candidate = doc_id.replace("-api", "-admin")
                if admin_candidate in manifest_ids:
                    doc_id = admin_candidate
            entries.append({"kind": kind, "path": rel, "line": 1, "symbol": source.name, "scope": scope, "contract_document": doc_id})

    scheduler = REPO / "backend" / "tasks" / "scheduler.py"
    lines = scheduler.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if "scheduler.add_job(" not in line:
            continue
        block = "\n".join(lines[index:index + 15])
        job_id = re.search(r'id="([^"]+)"', block)
        symbol = job_id.group(1) if job_id else f"job-at-line-{index + 1}"
        scope = "diary" if "diary" in symbol else ("agent-future" if any(term in symbol for term in ("agent", "future", "inactive")) else "life-feed")
        entries.append({"kind": "scheduled-job", "path": "backend/tasks/scheduler.py", "line": index + 1, "symbol": symbol, "scope": scope, "contract_document": SCOPE_DOCUMENTS[scope]})

    counts = {kind: sum(item["kind"] == kind for item in entries) for kind in ("route", "model", "admin-page", "h5-page", "scheduled-job")}
    out = [
        "# 代码面反向契约覆盖",
        "",
        "- 文档 ID：`contract-code-surface-coverage`",
        "- 权威状态：`canonical`",
        "- 功能范围：`routing`",
        "- 必读依赖：`docs/llm-manifest.json`",
        "- 相关技术债：无",
        "",
        "> 执行时实际盘点为 200 个路由装饰器；计划中的 194 是较早盘点值。差异保留为可见事实，不将新增路由伪装成迁移遗漏。",
        "",
        "| 类型 | 数量 |",
        "|---|---:|",
    ]
    labels = {"route": "路由", "model": "模型", "admin-page": "后台页面", "h5-page": "H5 页面", "scheduled-job": "调度任务"}
    out.extend(f"| {labels[kind]} | {counts[kind]} |" for kind in labels)
    out.extend(["", "## 明细", "", "| 类型 | 代码位置 | 功能范围 | 契约文档 |", "|---|---|---|---|"])
    for item in entries:
        location = f"`{item['path']}:{item['line']}`"
        out.append(f"| {labels[item['kind']]} | {location} | `{item['scope']}` | `{item['contract_document']}` |")
    path = DOCS / "contract" / "code-surface-coverage.md"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"counts": counts, "entries": entries, "path": "docs/contract/code-surface-coverage.md"}


def main():
    contract_text = (BASELINE / "contract.original.md").read_text(encoding="utf-8")
    td_text = (BASELINE / "tech-debt.original.md").read_text(encoding="utf-8")
    contract_coverage, spans = write_contract(contract_text)
    td_coverage = write_tech_debt(td_text)
    write_contract_index()
    make_manifest(contract_coverage, spans, td_coverage)
    code_surface = build_code_surface_coverage()
    manifest_path = DOCS / "llm-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["code_surface_coverage"] = code_surface
    manifest["documents"].append(document_entry(
        "contract-code-surface-coverage", "docs/contract/code-surface-coverage.md", "current", "canonical",
        ["routing"], ["代码面", "路由", "模型", "页面", "调度任务"], [], [], [], [], [], 400, 950,
    ))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"contract sections: {len(contract_coverage)}")
    print(f"tech debts: {len(td_coverage)}")
    print(f"code surface: {code_surface['counts']}")


if __name__ == "__main__":
    main()
