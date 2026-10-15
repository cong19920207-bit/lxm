"""Versioned, validated process parameters; business deadline remains fixed."""
import os
from dataclasses import dataclass, replace
import hashlib
import json

@dataclass(frozen=True)
class ChatTiming:
    version: str = 'chat-lifecycle-v1'
    deadline_seconds: int = 180
    reconcile_margin_ms: int = 60000
    scan_interval_ms: int = 5000
    scan_batch_size: int = 100
    retention_seconds: int = 604800
    tombstone_seconds: int = 2592000
    commit_reserve_ms: int = 5000
    server_wait_margin_ms: int = 10000
    lease_ms: int = 15000
    renew_ms: int = 5000
    probe_timeout_ms: int = 3000

    def __post_init__(self):
        bounds = {'reconcile_margin_ms':(10000,120000),'scan_interval_ms':(1000,10000),
            'scan_batch_size':(1,500),'retention_seconds':(180+self.reconcile_margin_ms/1000,2592000),
            'tombstone_seconds':(self.retention_seconds,315360000),'commit_reserve_ms':(1000,10000),
            'server_wait_margin_ms':(1000,30000),'lease_ms':(1,30000),'renew_ms':(1,self.lease_ms-1),
            'probe_timeout_ms':(500,10000)}
        if self.deadline_seconds != 180 or not self.version: raise ValueError('chat_timing_invalid')
        for key,(lo,hi) in bounds.items():
            if not lo <= getattr(self,key) <= hi: raise ValueError('chat_timing_invalid:'+key)


def load_timing():
    defaults=ChatTiming()
    names={'reconcile_margin_ms':'text_status_reconcile_margin_ms',
        'scan_interval_ms':'text_lifecycle_scan_interval_ms','scan_batch_size':'text_lifecycle_scan_batch_size',
        'retention_seconds':'text_submission_retention_seconds','tombstone_seconds':'text_submission_tombstone_seconds',
        'commit_reserve_ms':'text_commit_prepare_reserve_ms','server_wait_margin_ms':'text_server_wait_margin_ms',
        'lease_ms':'text_lock_lease_ms','renew_ms':'text_lock_renew_ms','probe_timeout_ms':'text_status_probe_timeout_ms'}
    values={key:int(os.environ.get(name.upper(),getattr(defaults,key))) for key,name in names.items()}
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    return ChatTiming(version='chat-lifecycle-v1:'+digest,**values)

TIMING=load_timing()
