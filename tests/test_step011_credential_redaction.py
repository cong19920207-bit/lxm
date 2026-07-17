# -*- coding: utf-8 -*-

import json

import pytest


def test_redacts_nested_credentials_case_insensitively():
    from backend.utils.credential_redaction import REDACTED, redact_credentials

    source = {
        "API_KEY": "key-value",
        "nested": [
            {"secret_key": "secret-value", "prompt": "keep this"},
            {"Custom_Token": "token-value", "max_tokens": 1024},
            {"service_secret": "service-value", "version": "v1"},
        ],
        "conversation": "Bearer is a word here",
        "memory": "keep memory",
    }

    result = redact_credentials(source)

    assert result == {
        "API_KEY": REDACTED,
        "nested": [
            {"secret_key": REDACTED, "prompt": "keep this"},
            {"Custom_Token": REDACTED, "max_tokens": 1024},
            {"service_secret": REDACTED, "version": "v1"},
        ],
        "conversation": "Bearer is a word here",
        "memory": "keep memory",
    }
    assert source["API_KEY"] == "key-value"


def test_redacts_parseable_json_string_and_keeps_string_contract():
    from backend.utils.credential_redaction import REDACTED, redact_credentials

    source = json.dumps(
        {
            "access_key_secret": "aks-value",
            "items": [{"refresh_token": "refresh-value", "description": "keep"}],
        },
        ensure_ascii=False,
    )

    result = redact_credentials(source)

    assert isinstance(result, str)
    assert json.loads(result) == {
        "access_key_secret": REDACTED,
        "items": [{"refresh_token": REDACTED, "description": "keep"}],
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("api_key=plain-key next=ok", "api_key=[REDACTED] next=ok"),
        ('Secret_Key: "secret value"; mode=test', 'Secret_Key: "[REDACTED]"; mode=test'),
        ("Authorization: Bearer abc.def.ghi", "Authorization: [REDACTED]"),
        ("request used Bearer abc.def.ghi for auth", "request used Bearer [REDACTED] for auth"),
        ("private_key='line-safe-value', version=2", "private_key='[REDACTED]', version=2"),
    ],
)
def test_redacts_known_non_json_assignment_and_authorization_forms(source, expected):
    from backend.utils.credential_redaction import redact_credentials

    assert redact_credentials(source) == expected


def test_is_idempotent_and_does_not_over_redact_non_credentials():
    from backend.utils.credential_redaction import redact_credentials

    source = {
        "prompt": "Explain access tokens without including a credential",
        "dialogue": "Bearer is a word here",
        "memory": "api_key is a documented field",
        "max_tokens": 2048,
        "description": "ordinary description",
        "version": "token-v2",
        "password_policy": "at least 12 characters",
        "access_token": "actual-token",
    }

    once = redact_credentials(source)
    twice = redact_credentials(once)

    assert twice == once
    assert once["prompt"] == source["prompt"]
    assert once["dialogue"] == source["dialogue"]
    assert once["memory"] == source["memory"]
    assert once["max_tokens"] == 2048
    assert once["password_policy"] == source["password_policy"]


def test_single_field_exception_fails_closed_without_aborting(monkeypatch):
    from backend.utils import credential_redaction

    original = credential_redaction._redact_value

    def raising_redactor(value):
        if value == "explode":
            raise RuntimeError("simulated field failure")
        return original(value)

    monkeypatch.setattr(credential_redaction, "_redact_value", raising_redactor)

    result = credential_redaction.redact_credentials(
        {"ordinary": "explode", "description": "business continues"}
    )

    assert result == {
        "ordinary": credential_redaction.REDACTED,
        "description": "business continues",
    }
