"""Single killable execution unit. No business DB writes or untrusted command arguments."""
import ctypes
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time


def _terminate_group(*_):
    # This worker is a new session leader. Its decoder shares the process group.
    os.killpg(os.getpgrp(), signal.SIGKILL)


def main():
    job_path = Path(sys.argv[1])
    lock_fd = int(sys.argv[2])
    parent_pid = int(sys.argv[3])
    signal.signal(signal.SIGTERM, _terminate_group)
    signal.signal(signal.SIGALRM, _terminate_group)
    if sys.platform == 'linux':
        libc = ctypes.CDLL(None)
        if libc.prctl(1, signal.SIGTERM) != 0:  # PR_SET_PDEATHSIG
            return 2
        if os.getppid() != parent_pid:
            return 2
    else:
        # Production is Linux. A parent-independent timer still limits work on
        # local POSIX development hosts; process locks protect recovery there.
        if os.getppid() != parent_pid:
            return 2
    job = json.loads(job_path.read_text())
    remaining = job['deadline_monotonic'] - time.monotonic()
    if remaining <= 0:
        return 2
    signal.setitimer(signal.ITIMER_REAL, remaining)
    # Limit the isolated worker and decoder, not the API server.
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024**2, 8 * 1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if sys.platform == 'linux':
        resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    try:
        os.nice(10)
    except PermissionError:
        # Some local macOS sandboxes disallow priority changes. Hard CPU/file/
        # wall limits and one decoder thread still apply independently.
        pass
    from backend.services.bgm_media import MediaError, convert_audio
    from backend.services.bgm_asset_service import put_and_verify
    try:
        if job.get('kind') == 'cleanup':
            from backend.services.bgm_asset_service import delete_owned_asset
            metadata = delete_owned_asset(job['asset'])
        elif job.get('kind') == 'cover':
            from backend.services.bgm_cover_media import convert_cover
            output = job_path.parent/'output.webp'
            metadata = convert_cover(job_path.parent/'source',output,job['extension'],job['mime_type'],job['deadline_monotonic'])
        else:
            output = job_path.parent/'output.m4a'
            metadata = convert_audio(job_path.parent/'source', output,
                                     job['extension'], job['mime_type'], job['deadline_monotonic'], lock_fd)
        if job.get('kind') != 'cleanup':
            put_and_verify(output, job['location'], metadata)
        result = {'ok': True, 'metadata': metadata}
    except MediaError as exc:
        result = {'ok': False, 'failure_category': str(exc)}
    except Exception:
        result = {'ok': False, 'failure_category': 'processing_failed'}
    # The parent decides whether this result still has execution qualification.
    (job_path.parent/'result.json').write_text(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
