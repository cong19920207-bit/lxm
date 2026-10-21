"""Owned temporary files and process liveness proof for BGM slot recovery."""
import asyncio
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
from uuid import UUID, uuid4

from backend.services.bgm_media import MediaError


def temporary_root():
    root = Path(os.getenv('BGM_TEMP_ROOT', '/tmp/lxm-bgm-runtime'))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


class OwnedWork:
    def __init__(self):
        self.owner = str(uuid4())
        self.directory = temporary_root() / self.owner
        self.directory.mkdir(mode=0o700)
        self.fd = os.open(self.directory/'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.process = None
        self.quiescent = False

    async def run(self, job):
        if self.process is not None:
            raise RuntimeError('A BGM worker is already running')
        # Cleanup may run successive objects under the same owned slot. The
        # previous worker was reaped and this descriptor still holds its flock.
        self.quiescent = False
        (self.directory/'result.json').unlink(missing_ok=True)
        path = self.directory/'job.json'
        path.write_text(json.dumps(job))
        self.process = await asyncio.create_subprocess_exec(
            sys.executable, '-m', 'backend.services.bgm_worker', str(path), str(self.fd), str(os.getpid()),
            pass_fds=(self.fd,), start_new_session=True,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            async with asyncio.timeout(max(0.01, job['deadline_monotonic'] - time.monotonic())):
                await self.process.wait()
            result_path = self.directory/'result.json'
            if self.process.returncode or not result_path.exists():
                raise MediaError('worker_stopped')
            result = json.loads(result_path.read_text())
            if not result.get('ok'):
                raise MediaError(result.get('failure_category', 'processing_failed'))
            return result['metadata']
        except TimeoutError:
            raise MediaError('processing_timeout') from None
        finally:
            await self.stop()

    async def stop(self):
        if self.quiescent:
            return
        # Always kill the whole owned group before its slot may be released.
        # The group can retain a decoder even if its leader has already exited.
        if self.process is not None:
            if self.process.returncode != 0:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await self.process.wait()
            self.process = None
        os.close(self.fd)
        self.fd = -1
        # Reacquiring through a NEW open description proves all inherited
        # decoder descriptors are closed, including an orphan still exiting.
        for _ in range(250):
            acquired = acquire_inactive_owner(self.owner)
            if acquired:
                self.fd, _directory = acquired
                self.quiescent = True
                return
            await asyncio.sleep(0.02)
        raise MediaError('termination_unconfirmed')

    def close(self, *, preserve_receipt=False):
        if self.process is not None or not self.quiescent:
            raise RuntimeError('Must stop and reap the BGM process before cleanup')
        if preserve_receipt:
            # If the DB is unavailable keep liveness proof for recovery, while
            # still removing source material. Never leave a lost DB owner.
            for name in ['source', 'output.m4a', 'output.webp', 'job.json', 'result.json']:
                (self.directory/name).unlink(missing_ok=True)
        else:
            shutil.rmtree(self.directory)
        os.close(self.fd)


def acquire_inactive_owner(owner):
    """Return a locked descriptor only with local proof of no surviving executor.

    Missing remote files are not proof. A different instance cannot release a
    foreign slot just because its lease expired. The owning volume must recover.
    """
    try:
        UUID(owner)
        directory = temporary_root() / owner
        fd = os.open(directory/'owner.lock', os.O_RDWR | os.O_NOFOLLOW)
    except (ValueError, TypeError, FileNotFoundError):
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd, directory
