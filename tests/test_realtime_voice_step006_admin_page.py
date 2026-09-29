# -*- coding: utf-8 -*-
"""实时语音 P1 M1 STEP-006A 管理后台页面静态契约。"""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
VOICE_PAGE = ROOT / "admin/pages/voice-config.html"
VOICE_JS = ROOT / "admin/static/js/voice-config-admin.js"
ADMIN_API_JS = ROOT / "admin/static/js/admin-api.js"
SAFETY_PAGE = ROOT / "admin/pages/safety-rules.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run_voice_js_probe(expression: str):
    """用可用的本地 JS 引擎执行页面纯函数，不依赖浏览器或网络。"""

    runtime = shutil.which("node")
    if runtime is None:
        bundled_jsc = Path(
            "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
        )
        runtime = shutil.which("jsc") or (str(bundled_jsc) if bundled_jsc.exists() else None)
    if runtime is None:
        pytest.skip("本机无 node/jsc，静态页面契约仍继续覆盖")

    source = _read(VOICE_JS)
    marker = "\n})();\n"
    assert source.endswith(marker)
    source = source[: -len(marker)] + """
  globalThis.__voiceConfigAdminTest = {
    capabilityEditableProjection: capabilityEditableProjection,
    capabilityProjectionIsComplete: capabilityProjectionIsComplete,
    buildCapabilitySectionContent: buildCapabilitySectionContent,
    bundleDiffProjection: bundleDiffProjection,
    previewJitterValue: previewJitterValue,
    activeBundleLoadFailed: activeBundleLoadFailed,
    publishBundleBlocked: publishBundleBlocked,
    publishCurrent: publishCurrent,
    voiceTestPermissions: typeof voiceTestPermissions === 'function'
      ? voiceTestPermissions
      : null,
    buildCapabilityTestBody: typeof buildCapabilityTestBody === 'function'
      ? buildCapabilityTestBody
      : null,
    buildForceTestBody: typeof buildForceTestBody === 'function'
      ? buildForceTestBody
      : null,
    capabilityTestFeedback: typeof capabilityTestFeedback === 'function'
      ? capabilityTestFeedback
      : null,
    pageState: pageState
  };
})();
"""
    harness = """
var document = { addEventListener: function () {} };
var window = { addEventListener: function () {} };
if (typeof print !== 'function') {
  globalThis.print = function (value) { console.log(value); };
}
""" + source + "\nprint(JSON.stringify(" + expression + "));\n"
    completed = subprocess.run(
        [runtime, "-e", harness],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_step006a_page_has_two_key_partitions_and_complete_frozen_actions():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)

    assert 'id="voice-key-config"' in page
    assert 'id="voice-key-script"' in page
    assert "voice_call_config" in page
    assert "voice_call_script" in page
    assert "/admin/static/js/voice-config-admin.js" in page

    for fragment in (
        "'/api/admin/voice/config/' + alias",
        "'/api/admin/voice/config/' + currentAlias + '/draft/'",
        "'/api/admin/voice/config/' + currentAlias + '/validate'",
        "'/api/admin/voice/config/' + currentAlias + '/publish'",
        "'/api/admin/voice/config/' + alias + '/history?page=1&page_size=20'",
        "'/api/admin/voice/config/' + currentAlias + '/rollback'",
    ):
        assert fragment in script

    for control_id in (
        "btn-voice-save-section",
        "btn-voice-discard-section",
        "btn-voice-discard-all",
        "btn-voice-validate",
        "btn-voice-publish",
    ):
        assert f'id="{control_id}"' in page
        assert f'id="{control_id}" class=' in page
        assert "data-write-action" in page.split(f'id="{control_id}"', 1)[1].split(">", 1)[0]


def test_step006a_roles_match_backend_key_boundaries_and_readers():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)
    assert "var ALLOWED_ROLES = ['super_admin', 'ai_trainer', 'tech_ops', 'ops_admin', 'observer']" in script
    assert "var CONFIG_WRITE_ROLES = ['super_admin', 'tech_ops']" in script
    assert "var SCRIPT_WRITE_ROLES = ['super_admin', 'ai_trainer']" in script
    assert "definition.writers.indexOf(getAdminRole())" in script
    assert "editor.readOnly = !writable" in script
    for control_id in (
        "voice-preview-stage",
        "voice-preview-candidate",
        "voice-preview-jitter",
    ):
        tag = page.split(f'id="{control_id}"', 1)[1].split(">", 1)[0]
        assert "data-key-write" in tag


def test_step006a_voice_sidebar_is_a_phase_a_group_for_all_five_roles():
    source = _read(ADMIN_API_JS)
    assert source.count("{ key: 'voice-call-group', group: 'voice_call' }") == 4
    assert "var VOICE_CALL_MENU" in source
    for role in ("super_admin", "ai_trainer", "tech_ops", "ops_admin", "observer"):
        assert f"{role}: [{{ key: 'voice-config'" in source
    assert "☎️ 语音通话" in source
    assert "⚙️ 语音设置" in source
    assert "renderVoiceCallGroupHtml" in source
    assert "toggleVoiceCallMenu" in source
    assert "通话记录留待 Phase D" in source
    assert "escapeAdminHtml(getAdminUsername())" in source


def test_step006a_diff_history_credential_projection_and_inline_errors_are_visible():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)

    for marker in (
        'id="voice-active-json"',
        'id="voice-draft-json"',
        'id="voice-changed-sections"',
        'id="voice-history-body"',
        'id="voice-history-detail"',
        'id="voice-inline-errors"',
        'id="voice-credential-grid"',
    ):
        assert marker in page

    assert "credential_configured" in page
    assert "仅 super_admin / tech_ops" in page
    assert "delete projected.s2s.credential_configured" in script
    assert "returnErrorResponse: true" in script
    assert "result.data.errors" in script
    assert "state.activeDetail.updated_at" in script
    assert "state.activeDetail.updated_by" in script
    assert "item.field || item.path" in script
    assert "allowedText(item.allowed)" in script

    admin_api = _read(ADMIN_API_JS)
    assert "const returnErrorResponse" in admin_api
    assert "errorResult = await resp.json()" in admin_api


def test_step006a_credential_card_never_captures_or_renders_revision_reference():
    script = _read(VOICE_JS)

    assert "credential_revision_ref" not in script


def test_step006a_meta_and_publish_use_the_complete_backend_bundle_diff():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)

    assert "草稿基于 V" in script
    assert "生效版本整包" in page
    assert "当前草稿整包" in page
    assert "完整 JSON 用于发布审计与技术排障" in page
    render_diff = script.split("function renderDiff()", 1)[1].split(
        "function appendKeyValue", 1
    )[0]
    assert "bundleDiffProjection(pageState[currentAlias])" in render_diff
    assert "[currentSection]" not in render_diff
    publish = script.split("function publishCurrent()", 1)[1].split(
        "function openReadOnlyProjection", 1
    )[0]
    assert "diff: bundleDiffProjection(pageState[currentAlias])" in publish
    assert "data-risk-active" in script
    assert "data-risk-draft" in script
    assert "data-risk-changed" in script

    state = {
        "bundle": {
            "_meta": {
                "has_draft": True,
                "changed_sections": ["global", "quota"],
            }
        },
        "activeConfig": {
            "schema_version": 1,
            "global": {"enabled": True},
            "quota": {"daily_free_seconds": 300},
        },
        "selectedConfig": {
            "schema_version": 1,
            "global": {"enabled": False},
            "quota": {"daily_free_seconds": 180},
        },
    }
    projection = _run_voice_js_probe(
        "__voiceConfigAdminTest.bundleDiffProjection(" + json.dumps(state) + ")"
    )
    assert projection == {
        "active": state["activeConfig"],
        "draft": state["selectedConfig"],
        "hasDraft": True,
        "changedSections": ["global", "quota"],
    }


def test_step006a_active_history_failure_is_visible_and_fail_closes_publish():
    script = _read(VOICE_JS)

    load_key = script.split("async function loadKey(alias)", 1)[1].split(
        "async function loadHistory", 1
    )[0]
    assert "VOICE_ACTIVE_BUNDLE_LOAD_FAILED" in load_key
    assert "生效版本 V" in load_key
    assert "已禁用发布，请重新加载" in load_key
    assert "next.activeLoadErrors.length" in load_key
    assert "showInlineErrors('voice-inline-errors'" in load_key
    assert "!meta.has_draft && !next.activeLoadErrors.length" in load_key

    permissions = script.split("function applyKeyPermissions()", 1)[1].split(
        "function renderCurrentKey", 1
    )[0]
    assert (
        "publishButton.disabled = !writable || publishBundleBlocked(pageState[currentAlias])"
        in permissions
    )
    publish = script.split("function publishCurrent()", 1)[1].split(
        "function openReadOnlyProjection", 1
    )[0]
    assert publish.index("if (publishBundleBlocked(state))") < publish.index(
        "openHighRiskDialog({"
    )
    assert "（生效版本整包加载失败，发布已禁用）" in script
    assert "生效版整包不可用 · 发布已禁用" in script

    result = _run_voice_js_probe("""(function () {
      var host = { className: '', innerHTML: '', textContent: '' };
      globalThis.getAdminRole = function () { return 'tech_ops'; };
      document.getElementById = function () { return host; };
      document.createElement = function () {
        throw new Error('发布门禁失效：不应打开确认弹窗');
      };
      var failedState = {
        bundle: { _meta: { base_version: 7, has_draft: true } },
        selectedConfig: { schema_version: 1 },
        activeConfig: null,
        activeLoadErrors: [{
          code: 'VOICE_ACTIVE_BUNDLE_LOAD_FAILED',
          field: 'active_version',
          message: '生效版本 V7 整包加载失败；已禁用发布，请重新加载'
        }]
      };
      __voiceConfigAdminTest.pageState.config = failedState;
      __voiceConfigAdminTest.publishCurrent();
      return {
        failed: __voiceConfigAdminTest.activeBundleLoadFailed(failedState),
        blocked: __voiceConfigAdminTest.publishBundleBlocked(failedState),
        errorVisible: host.innerHTML.indexOf('生效版本 V7 整包加载失败') >= 0,
        availableBlocked: __voiceConfigAdminTest.publishBundleBlocked({
          bundle: { _meta: { base_version: 7, has_draft: true } },
          activeConfig: { schema_version: 1 },
          activeLoadErrors: []
        })
      };
    })()""")
    assert result == {
        "failed": True,
        "blocked": True,
        "errorVisible": True,
        "availableBlocked": False,
    }


def test_step006a_all_six_capabilities_are_prominent_and_show_ttl_evidence():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)
    capabilities = (
        "supports_current_turn_rag_gate",
        "supports_reply_cancel",
        "supports_context_truncate",
        "supports_playback_text_mapping",
        "supports_sentence_playback_ack",
        "supports_session_reconnect",
    )
    for capability in capabilities:
        assert capability in script
    assert "unverified / off" in page
    assert 'id="voice-capability-summary"' in page
    assert "'已取证 ' + evidencedCount + ' / ' + CAPABILITY_KEYS.length" in script
    for field in (
        "fallback_mode",
        "verification_status",
        "effective_scope",
        "forced_enabled",
        "last_test_result",
        "evidence_ttl_days",
        "verified_at",
        "expires_at",
        "evidence_report_id",
    ):
        assert field in script
    assert script.count("'<dt>evidence_ttl_days</dt>") == 1
    assert script.count("'<dt>fallback_mode</dt>") == 1


def test_step006a_capability_editor_preserves_verified_stale_failed_projections():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)
    capabilities = (
        "supports_current_turn_rag_gate",
        "supports_reply_cancel",
        "supports_context_truncate",
        "supports_playback_text_mapping",
        "supports_sentence_playback_ack",
        "supports_session_reconnect",
    )
    readonly_fields = (
        "verification_status",
        "enabled",
        "forced_enabled",
        "effective_scope",
        "provider_profile",
        "model_version",
        "protocol_profile",
        "adapter_version",
        "sdk_version",
        "evidence_suite_version",
        "evidence_fingerprint",
        "verified_at",
        "expires_at",
        "evidence_report_id",
        "last_test_result",
    )
    assert 'id="voice-editor-note"' in page
    assert "var CAPABILITY_EDITABLE_FIELDS = ['fallback_mode', 'evidence_ttl_days']" in script
    for field in readonly_fields:
        assert f"'{field}'" in script.split("var CAPABILITY_READONLY_FIELDS", 1)[1].split(
            "];", 1
        )[0]
    assert "content = capabilityResult.content" in script
    assert "if (capabilityResult.errors.length)" in script
    assert "capabilityProjectionIsComplete(original)" in script
    assert "保存时只会原样合并" in script
    assert "CAPABILITY_INITIAL_READONLY" not in script
    assert "capabilityProjectionRequiresProtectedWrite" not in script
    assert "capabilityWriteBlocked" not in script
    assert "现有分区 PATCH 无法安全区分写入来源" not in script
    assert "saveButton.disabled = !writable;" in script

    statuses = ("verified", "stale", "failed", "verified", "stale", "failed")
    original = {}
    for index, (key, status) in enumerate(zip(capabilities, statuses, strict=True)):
        original[key] = {
            "verification_status": status,
            "enabled": status == "verified",
            "forced_enabled": False,
            "effective_scope": "all" if status == "verified" else "off",
            "fallback_mode": "next_turn",
            "provider_profile": f"provider-profile-{index}",
            "model_version": f"model-{index}",
            "protocol_profile": f"protocol-{index}",
            "adapter_version": f"adapter-{index}",
            "sdk_version": f"sdk-{index}",
            "evidence_suite_version": f"suite-{index}",
            "evidence_fingerprint": f"sha256:fingerprint-{index}",
            "evidence_ttl_days": 30,
            "verified_at": f"2026-08-{index + 1:02d}T00:00:00+08:00",
            "expires_at": f"2026-09-{index + 1:02d}T00:00:00+08:00",
            "evidence_report_id": f"report-{index}",
            "last_test_result": "failed" if status == "failed" else "passed",
        }
    first = capabilities[0]
    expression = """(function () {
      var original = %s;
      var editable = __voiceConfigAdminTest.capabilityEditableProjection(original);
      Object.keys(editable).forEach(function (key, index) {
        editable[key].fallback_mode = 'safe_fallback_' + index;
        editable[key].evidence_ttl_days = 7 + index;
      });
      var merged = __voiceConfigAdminTest.buildCapabilitySectionContent(original, editable);
      var forged = JSON.parse(JSON.stringify(editable));
      forged[%s].verification_status = 'verified';
      var forgedResult = __voiceConfigAdminTest.buildCapabilitySectionContent(original, forged);
      var invalidTtl = JSON.parse(JSON.stringify(editable));
      invalidTtl[%s].evidence_ttl_days = 91;
      var invalidTtlResult = __voiceConfigAdminTest.buildCapabilitySectionContent(original, invalidTtl);
      var incompleteOriginal = JSON.parse(JSON.stringify(original));
      delete incompleteOriginal[%s].evidence_report_id;
      return {
        editable: editable,
        merged: merged,
        forgedResult: forgedResult,
        invalidTtlResult: invalidTtlResult,
        originalComplete: __voiceConfigAdminTest.capabilityProjectionIsComplete(original),
        incompleteResult: __voiceConfigAdminTest.buildCapabilitySectionContent(incompleteOriginal, editable)
      };
    })()""" % (
        json.dumps(original),
        json.dumps(first),
        json.dumps(first),
        json.dumps(first),
    )
    result = _run_voice_js_probe(expression)

    for editable_item in result["editable"].values():
        assert set(editable_item) == {"fallback_mode", "evidence_ttl_days"}
    assert result["merged"]["errors"] == []
    assert {
        item["verification_status"]
        for item in result["merged"]["content"].values()
    } == {"verified", "stale", "failed"}
    for index, key in enumerate(capabilities):
        merged_item = result["merged"]["content"][key]
        assert merged_item["fallback_mode"] == f"safe_fallback_{index}"
        assert merged_item["evidence_ttl_days"] == 7 + index
        for field in readonly_fields:
            assert merged_item[field] == original[key][field]
    assert result["forgedResult"]["content"] is None
    assert result["forgedResult"]["errors"][0]["field"].endswith(
        ".verification_status"
    )
    assert result["invalidTtlResult"]["content"] is None
    assert result["invalidTtlResult"]["errors"][0]["allowed"] == {
        "min": 7,
        "max": 90,
    }
    assert result["originalComplete"] is True
    assert result["incompleteResult"]["content"] is None


def test_step006a_capability_evidence_detail_is_get_only_and_backend_projected():
    script = _read(VOICE_JS)
    assert "'/api/admin/voice/capability-evidence/' + encodeURIComponent(evidenceReportId)" in script
    assert "viewCapabilityEvidence" in script
    assert "data-capability-evidence" in script
    assert "页面不补全、推导或写入证据" in script
    assert "voiceGet(\n      '/api/admin/voice/capability-evidence/'" in script
    for helper in ("voicePost", "voicePatch", "voiceDelete"):
        assert f"{helper}(\n      '/api/admin/voice/capability-evidence/'" not in script


def test_step006a_followup_preview_submits_only_frozen_input_and_renders_backend_fields():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)

    assert "前端不重算窗口" in page
    assert "'/api/admin/voice/config/config/validate'" in script
    assert "followup_preview:" in script
    for field in ("stage", "candidate_at", "jitter_minutes"):
        assert field in script
    for result_field in (
        "resolution",
        "in_window",
        "resolved_window.start_at",
        "resolved_window.end_at",
        "jitter_applied_minutes",
        "resolved_due_at",
        "delay_seconds",
        "cancel_reason",
    ):
        assert result_field in script
    assert "var jitter = Number(jitterText);" not in script
    assert "var jitter = previewJitterValue(jitterText);" in script
    assert "jitterText !== ''" in script
    assert _run_voice_js_probe(
        "({empty: __voiceConfigAdminTest.previewJitterValue(''), "
        "zero: __voiceConfigAdminTest.previewJitterValue('0'), "
        "twenty: __voiceConfigAdminTest.previewJitterValue('20')})"
    ) == {"empty": "", "zero": 0, "twenty": 20}


def test_step006a_frozen_test_actions_keep_o01_gate_warning_and_visible_results():
    page = _read(VOICE_PAGE)
    script = _read(VOICE_JS)

    assert "O-01 未关闭" in page
    assert "本次测试不自动开启能力，也不等于 O-01 闸门关闭" in page
    assert "历史验收结果按原证据保留，无需重复真人测试" in page
    for control_id in (
        "btn-voice-test-connection",
        "btn-voice-test-capability",
        "btn-voice-force-capability",
        "voice-test-capability-select",
    ):
        tag = page.split(f'id="{control_id}"', 1)[1].split(">", 1)[0]
        assert "disabled" in tag

    for marker in (
        'id="voice-test-errors"',
        'id="voice-test-result"',
        'id="voice-test-result-grid"',
    ):
        assert marker in page

    for capability in (
        "supports_current_turn_rag_gate",
        "supports_reply_cancel",
        "supports_context_truncate",
        "supports_playback_text_mapping",
        "supports_sentence_playback_ack",
        "supports_session_reconnect",
    ):
        assert f'<option value="{capability}">{capability}</option>' in page

    for field in (
        "status",
        "latency_ms",
        "failure_category",
        "test_version",
        "tested_draft_revision",
        "tested_at",
        "evidence_run_id",
        "evidence_report_id",
    ):
        assert f"'{field}'" in script


def test_step006a_frozen_test_actions_fail_closed_by_role_key_and_loaded_state():
    permissions = _run_voice_js_probe("""(function () {
      var project = __voiceConfigAdminTest.voiceTestPermissions;
      if (typeof project !== 'function') return null;
      return {
        superReady: project('super_admin', 'config', true),
        techReady: project('tech_ops', 'config', true),
        aiReady: project('ai_trainer', 'config', true),
        opsReady: project('ops_admin', 'config', true),
        observerReady: project('observer', 'config', true),
        wrongKey: project('super_admin', 'script', true),
        notLoaded: project('super_admin', 'config', false)
      };
    })()""")

    assert permissions == {
        "superReady": {"connection": True, "capability": True, "force": True},
        "techReady": {"connection": True, "capability": True, "force": False},
        "aiReady": {"connection": False, "capability": False, "force": False},
        "opsReady": {"connection": False, "capability": False, "force": False},
        "observerReady": {"connection": False, "capability": False, "force": False},
        "wrongKey": {"connection": False, "capability": False, "force": False},
        "notLoaded": {"connection": False, "capability": False, "force": False},
    }


def test_step006a_frozen_test_actions_send_exact_bodies_and_reload_after_writes():
    script = _read(VOICE_JS)

    assert "'/api/admin/voice/config/test-connection'" in script
    assert "'/api/admin/voice/config/test-capability'" in script
    assert (
        "'/api/admin/voice/config/capabilities/' + encodeURIComponent(capabilityKey) + "
        "'/force-test'"
    ) in script
    for control_id, handler in (
        ("btn-voice-test-connection", "testVoiceConnection"),
        ("btn-voice-test-capability", "testVoiceCapability"),
        ("btn-voice-force-capability", "forceVoiceCapabilityTest"),
    ):
        assert f"document.getElementById('{control_id}').onclick = {handler};" in script

    bodies = _run_voice_js_probe("""(function () {
      if (typeof __voiceConfigAdminTest.buildCapabilityTestBody !== 'function' ||
          typeof __voiceConfigAdminTest.buildForceTestBody !== 'function') return null;
      return {
        capability: __voiceConfigAdminTest.buildCapabilityTestBody('supports_reply_cancel'),
        force: __voiceConfigAdminTest.buildForceTestBody('  人工验证通过  ')
      };
    })()""")
    assert bodies == {
        "capability": {"capability_key": "supports_reply_cancel"},
        "force": {
            "effective_scope": "test",
            "confirm_text": "CONFIRM",
            "reason": "人工验证通过",
        },
    }

    connection = script.split("async function testVoiceConnection()", 1)[1].split(
        "async function testVoiceCapability", 1
    )[0]
    assert (
        "voicePost(\n        '/api/admin/voice/config/test-connection',"
        "\n        {}\n      )"
    ) in connection

    capability = script.split("async function testVoiceCapability()", 1)[1].split(
        "function forceVoiceCapabilityTest", 1
    )[0]
    assert "buildCapabilityTestBody(capabilityKey)" in capability
    assert "await reloadCurrent();" in capability

    force = script.split("function forceVoiceCapabilityTest()", 1)[1].split(
        "function bindEvents", 1
    )[0]
    assert "openHighRiskDialog({" in force
    assert "buildForceTestBody(reason)" in force
    assert "await reloadCurrent();" in force
    assert "maxlength=\"500\"" in script
    assert "reason.length < 1 || reason.length > 500" in script


def test_step006a_capability_feedback_only_claims_append_with_both_evidence_ids():
    feedback = _run_voice_js_probe("""(function () {
      var project = __voiceConfigAdminTest.capabilityTestFeedback;
      if (typeof project !== 'function') return null;
      return {
        passed: project({
          status: 'passed',
          evidence_run_id: 'run-1',
          evidence_report_id: 'report-1'
        }),
        failed: project({
          status: 'failed',
          evidence_run_id: 'run-2',
          evidence_report_id: 'report-2'
        }),
        missingReport: project({
          status: 'error',
          evidence_run_id: 'run-3',
          evidence_report_id: null
        }),
        missingBoth: project({
          status: 'error',
          evidence_run_id: null,
          evidence_report_id: null
        })
      };
    })()""")

    assert feedback == {
        "passed": {
            "evidenceAppended": True,
            "message": "单能力测试通过并已追加管理员证据；该结果不等于 M1 闸门关闭。",
            "tone": "success",
        },
        "failed": {
            "evidenceAppended": True,
            "message": "单能力测试已完成并追加管理员证据，状态为 failed；能力投影已按证据重载。",
            "tone": "warning",
        },
        "missingReport": {
            "evidenceAppended": False,
            "message": "单能力测试已完成，但未追加能力证据且未修改能力投影；状态为 error。",
            "tone": "warning",
        },
        "missingBoth": {
            "evidenceAppended": False,
            "message": "单能力测试已完成，但未追加能力证据且未修改能力投影；状态为 error。",
            "tone": "warning",
        },
    }


def test_step006a_safety_page_connects_crisis_publish_history_and_rollback():
    page = _read(SAFETY_PAGE)
    assert 'id="pane-crisis"' in page
    assert 'id="input-crisis" data-write-action' in page
    assert 'id="btn-save-crisis" data-write-action' in page
    assert 'id="crisis-history-body"' in page
    assert "'/api/admin/safety-rules/crisis-keywords'" in page
    assert "'/api/admin/safety-rules/crisis-keywords/history?page=1&page_size=20'" in page
    assert "'/api/admin/safety-rules/crisis-keywords/rollback'" in page
    assert "confirm_text: 'CONFIRM'" in page
    assert "data-write-action data-crisis-rollback" in page
    assert 'id="btn-retry-safety-load"' in page
    assert "var loadSucceeded = !!(res && res.code === 0 && res.data)" in page
    assert "setFormEnabled(loadSucceeded)" in page
    assert "firstLoadFinished = loadSucceeded" in page
