"""Read-only STEP-016 client observation configuration, never business authority."""
import hashlib
import json
import os
from backend.services.chat_timing import TIMING


def load_client_timing(server=TIMING, env=None):
    env = os.environ if env is None else env
    defaults = {
        'text_status_poll_interval_ms': 2000,
        'text_status_poll_max_interval_ms': 10000,
        'text_status_poll_backoff_factor': 2,
        'text_status_max_inflight_per_target': 1,
        'text_status_max_inflight_per_page': 2,
        'text_admission_reconcile_window_ms': 240000,
        'text_client_transport_margin_ms': 20000,
        'text_local_submission_retention_seconds': server.retention_seconds,
    }
    values = {key: (float if key == 'text_status_poll_backoff_factor' else int)(env.get(key.upper(), default))
              for key, default in defaults.items()}
    bounds = {
        'text_status_poll_interval_ms': (1000, 10000),
        'text_status_poll_max_interval_ms': (values['text_status_poll_interval_ms'], 30000),
        'text_status_max_inflight_per_target': (1, 1),
        'text_status_max_inflight_per_page': (1, 5),
        'text_admission_reconcile_window_ms': (180000, 300000),
        'text_client_transport_margin_ms': (server.server_wait_margin_ms, 60000),
        'text_local_submission_retention_seconds': (180 + server.reconcile_margin_ms / 1000, server.retention_seconds),
    }
    for key, (low, high) in bounds.items():
        if not low <= values[key] <= high:
            raise ValueError('chat_client_timing_invalid:' + key)
    if not 1 < values['text_status_poll_backoff_factor'] <= 3:
        raise ValueError('chat_client_timing_invalid:text_status_poll_backoff_factor')
    values.update(text_business_deadline_ms=server.deadline_seconds * 1000,
                  text_status_probe_timeout_ms=server.probe_timeout_ms,
                  text_status_reconcile_margin_ms=server.reconcile_margin_ms,
                  text_server_wait_margin_ms=server.server_wait_margin_ms,
                  server_timing_config_version=server.version)
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    values['timing_config_version']='chat-client-v1:' + digest
    return values


CLIENT_TIMING = load_client_timing()
