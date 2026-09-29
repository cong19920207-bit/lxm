"""Existing finalizer runtime assertions on disposable M8 containers."""
import os
import pytest
from tests.test_realtime_voice_step037_provider_fault_runtime import containers, runtime, full_runtime
from tests import test_realtime_voice_step014_runtime as checks

pytestmark = pytest.mark.skipif(os.getenv('RUN_VOICE_M8_RUNTIME') != '1', reason='isolated finalizer regression')

@pytest.mark.asyncio
async def test_old_snapshot_concurrent_finalizers(full_runtime):
    factory, _, cache = full_runtime
    await checks.test_mysql_concurrent_terminal_claim_from_old_snapshots_settles_once((factory,cache))

@pytest.mark.asyncio
async def test_stale_connection_cannot_resurrect(full_runtime):
    factory, _, cache = full_runtime
    await checks.test_mysql_competing_connect_and_preconnection_hard_stop_cannot_resurrect((factory,cache))

@pytest.mark.asyncio
async def test_reconnect_retains_original_metering(full_runtime):
    factory, _, cache = full_runtime
    await checks.test_mysql_reconnect_same_call_excludes_real_wall_window_and_preserves_anchor((factory,cache))
