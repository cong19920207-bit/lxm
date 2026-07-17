# -*- coding: utf-8 -*-
"""Shared, stateless credential redaction for admin audit surfaces."""

from __future__ import annotations

import json
import re
from typing import Any


REDACTED = "[REDACTED]"

_EXACT_CREDENTIAL_KEYS = {
    "api_key",
    "secret_key",
    "api_secret",
    "access_key_secret",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "pepper",
    "private_key",
}

_KEY_PATTERN = (
    r"(?:api_key|secret_key|api_secret|access_key_secret|access_token|"
    r"refresh_token|authorization|password|pepper|private_key|"
    r"[A-Za-z0-9_]+_(?:secret|token))"
)

_QUOTED_ASSIGNMENT_RE = re.compile(
    rf"(?P<prefix>\b{_KEY_PATTERN}\b\s*(?:=|:)\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE,
)
_UNQUOTED_ASSIGNMENT_RE = re.compile(
    rf"(?P<prefix>\b{_KEY_PATTERN}\b\s*(?:=|:)\s*)"
    r"(?P<value>(?![\"'])[^\s,;}]+)",
    re.IGNORECASE,
)
_AUTHORIZATION_RE = re.compile(
    r"(?P<prefix>\bauthorization\b\s*(?:=|:)\s*)"
    r"(?:(?P<quote>[\"'])(?P<quoted>.*?)(?P=quote)|"
    r"(?P<unquoted>(?:Bearer|Basic)\s+[^\s,;]+|[^\s,;]+))",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(
    r"\b(?P<scheme>Bearer)\s+(?P<credential>[A-Za-z0-9._~+/=-]{8,})",
    re.IGNORECASE,
)


def _is_credential_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    normalized = key.casefold()
    return (
        normalized in _EXACT_CREDENTIAL_KEYS
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
    )


def _replace_authorization(match: re.Match[str]) -> str:
    quote = match.group("quote") or ""
    return f"{match.group('prefix')}{quote}{REDACTED}{quote}"


def _redact_text(value: str) -> str:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None
    else:
        if isinstance(parsed, (dict, list)):
            redacted = _redact_value(parsed)
            return json.dumps(redacted, ensure_ascii=False)

    result = _AUTHORIZATION_RE.sub(_replace_authorization, value)
    result = _QUOTED_ASSIGNMENT_RE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{REDACTED}{match.group('quote')}"
        ),
        result,
    )
    result = _UNQUOTED_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group('prefix')}{REDACTED}",
        result,
    )
    return _BEARER_RE.sub(
        lambda match: f"{match.group('scheme')} {REDACTED}",
        result,
    )


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, field_value in value.items():
            if _is_credential_key(key):
                result[key] = REDACTED
                continue
            try:
                result[key] = _redact_value(field_value)
            except Exception:
                result[key] = REDACTED
        return result

    if isinstance(value, list):
        result = []
        for item in value:
            try:
                result.append(_redact_value(item))
            except Exception:
                result.append(REDACTED)
        return result

    if isinstance(value, str):
        return _redact_text(value)

    return value


def redact_credentials(value: Any) -> Any:
    """Return a redacted copy; unexpected failures fail closed for the value."""
    try:
        return _redact_value(value)
    except Exception:
        return REDACTED


__all__ = ["REDACTED", "redact_credentials"]
