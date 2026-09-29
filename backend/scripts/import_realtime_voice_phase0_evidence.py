# -*- coding: utf-8 -*-
"""Controlled, non-interactive Phase0 evidence import command (STEP-006).

The command performs every filesystem, JSON and evidence-contract check before
opening a database session.  It never prints the bundle, provider details or
dynamic exception text.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, TextIO

from backend.database import async_session_maker
from backend.services.realtime_voice_capability_service import (
    realtime_voice_capability_service,
    validate_phase0_evidence_bundle,
    validate_phase0_evidence_selection,
)


EXIT_SUCCESS = 0
EXIT_INPUT_REJECTED = 2
EXIT_IMPORT_FAILED = 3
MAX_BUNDLE_BYTES = 8 * 1024 * 1024

_ARGUMENT_INVALID = "VOICE_EVIDENCE_IMPORT_ARGUMENT_INVALID"
_CONFIRM_INVALID = "VOICE_EVIDENCE_IMPORT_CONFIRM_INVALID"
_FILE_INVALID = "VOICE_EVIDENCE_IMPORT_FILE_INVALID"
_FILE_TOO_LARGE = "VOICE_EVIDENCE_IMPORT_FILE_TOO_LARGE"
_JSON_INVALID = "VOICE_EVIDENCE_IMPORT_JSON_INVALID"
_BUNDLE_REJECTED = "VOICE_EVIDENCE_IMPORT_BUNDLE_REJECTED"
_IMPORT_FAILED = "VOICE_EVIDENCE_IMPORT_FAILED"


class _ArgumentRejected(ValueError):
    pass


class _InputRejected(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise _ArgumentRejected


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("invalid positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("invalid positive integer")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(add_help=False)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--operator-id", required=True, type=_positive_int)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--report-id", action="append", default=None)
    return parser


def _reject_duplicate_json_keys(pairs):
    projected = {}
    for key, value in pairs:
        if key in projected:
            raise ValueError("duplicate JSON key")
        projected[key] = value
    return projected


def _read_json_file(path_text: str) -> Any:
    path = Path(path_text)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _InputRejected(_FILE_INVALID) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise _InputRejected(_FILE_INVALID)
    if metadata.st_size > MAX_BUNDLE_BYTES:
        raise _InputRejected(_FILE_TOO_LARGE)

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise _InputRejected(_FILE_INVALID) from exc
    try:
        opened_metadata = os.fstat(descriptor)
        if not stat.S_ISREG(opened_metadata.st_mode):
            raise _InputRejected(_FILE_INVALID)
        if opened_metadata.st_size > MAX_BUNDLE_BYTES:
            raise _InputRejected(_FILE_TOO_LARGE)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read(MAX_BUNDLE_BYTES + 1)
    except _InputRejected:
        raise
    except OSError as exc:
        raise _InputRejected(_FILE_INVALID) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise _InputRejected(_FILE_TOO_LARGE)
    try:
        text = raw.decode("utf-8")
        return json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _InputRejected(_JSON_INVALID) from exc


def _prevalidate(bundle_path: str, report_ids: list[str] | None = None) -> dict[str, Any]:
    parsed = _read_json_file(bundle_path)
    try:
        if report_ids is not None:
            validate_phase0_evidence_selection(parsed, report_ids=report_ids)
            return parsed  # Preserve the complete source envelope for the transaction.
        return validate_phase0_evidence_bundle(parsed)
    except Exception as exc:
        raise _InputRejected(_BUNDLE_REJECTED) from exc


async def _database_import(
    *,
    bundle: dict[str, Any],
    operator_id: int,
    session_factory,
    report_ids: list[str] | None = None,
) -> dict[str, Any]:
    async with session_factory() as db:
        try:
            # The outer transaction owns the real commit.  The service detects
            # it and uses a savepoint, preserving one atomic MySQL commit for
            # six facts, draft projection and immutable audit.
            async with db.begin():
                if report_ids is not None:
                    result = await realtime_voice_capability_service.import_phase0_evidence_selection(
                        db, bundle=bundle, report_ids=report_ids, operator_id=operator_id,
                    )
                else:
                    result = await realtime_voice_capability_service.import_phase0_evidence_bundle(
                        db,
                        bundle=bundle,
                        operator_id=operator_id,
                    )
        except Exception:
            try:
                await db.rollback()
            except Exception:
                pass
            raise
    if type(result) is not dict:
        raise RuntimeError("invalid import result")
    return result


def _safe_success_summary(
    bundle: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    idempotent = result.get("idempotent")
    draft_revision = result.get("draft_revision")
    if type(idempotent) is not bool:
        raise RuntimeError("invalid import result")
    if draft_revision is not None and (
        type(draft_revision) is not int or draft_revision < 1
    ):
        raise RuntimeError("invalid import result")
    if idempotent is False and draft_revision is None:
        raise RuntimeError("invalid import result")
    return {
        "status": "success",
        "evidence_run_id": bundle["evidence_run_id"],
        "record_count": result.get("record_count", bundle["record_count"]),
        "bundle_sha256": bundle["bundle_sha256"],
        "idempotent": idempotent,
        "draft_revision": draft_revision,
    }


def _write_json(stream: TextIO, value: dict[str, Any]) -> None:
    stream.write(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def main(
    argv: list[str] | None = None,
    *,
    session_factory=None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    error_output = stderr or sys.stderr
    try:
        args = _parser().parse_args(argv)
    except (_ArgumentRejected, SystemExit):
        _write_json(
            error_output,
            {"status": "input_rejected", "code": _ARGUMENT_INVALID},
        )
        return EXIT_INPUT_REJECTED
    if args.confirm != "CONFIRM":
        _write_json(
            error_output,
            {"status": "input_rejected", "code": _CONFIRM_INVALID},
        )
        return EXIT_INPUT_REJECTED

    try:
        bundle = _prevalidate(args.bundle, args.report_id) if args.report_id is not None else _prevalidate(args.bundle)
    except _InputRejected as exc:
        _write_json(
            error_output,
            {"status": "input_rejected", "code": exc.code},
        )
        return EXIT_INPUT_REJECTED

    try:
        result = asyncio.run(
            _database_import(
                bundle=bundle,
                operator_id=args.operator_id,
                session_factory=session_factory or async_session_maker,
                **({"report_ids": args.report_id} if args.report_id is not None else {}),
            )
        )
        summary = _safe_success_summary(bundle, result)
    except Exception:
        _write_json(
            error_output,
            {"status": "import_failed", "code": _IMPORT_FAILED},
        )
        return EXIT_IMPORT_FAILED
    _write_json(output, summary)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
