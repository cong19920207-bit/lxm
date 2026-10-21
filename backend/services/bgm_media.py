"""Synchronous media work, executed only inside the killable BGM worker process."""
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from backend.constants.bgm import (AUDIO_SOURCE_MAX_BYTES, AUDIO_OUTPUT_MAX_BYTES,
                                   AUDIO_MAX_SECONDS, AUDIO_TARGET_BITRATE)


class MediaError(Exception):
    """Closed, non-sensitive category; raw decoder/provider messages never escape."""


AUDIO_MIMES = {
    '.mp3': {'audio/mpeg', 'audio/mp3'},
    '.m4a': {'audio/mp4', 'audio/x-m4a', 'audio/m4a'},
    '.aac': {'audio/aac', 'audio/x-aac', 'audio/aacp'},
    '.wav': {'audio/wav', 'audio/x-wav', 'audio/wave'},
}


def validate_size(size, limit):
    if type(size) is not int or not 0 < size <= limit:
        raise MediaError('size_limit')


def validate_duration(value):
    if not math.isfinite(value) or not 0 < value <= AUDIO_MAX_SECONDS:
        raise MediaError('duration_limit')


def validate_source_type(extension, mime):
    if extension not in AUDIO_MIMES:
        raise MediaError('unsupported_format')
    # Empty/generic browser MIME is not proof of a type: the decoder still checks.
    if mime not in AUDIO_MIMES[extension] | {'', 'application/octet-stream'}:
        raise MediaError('mime_mismatch')


def _run(command, deadline, *, lock_fd=None, output=False):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise MediaError('processing_timeout')
    try:
        parent_pid = os.getpid()
        def decoder_parent_guard():
            # Called only by the isolated, single-thread worker, never in the
            # threaded API server. SIGKILL/oom of that worker kills its decoder.
            import ctypes
            if ctypes.CDLL(None).prctl(1, signal.SIGKILL) != 0 or os.getppid() != parent_pid:
                os._exit(2)
        # The process inherits the owner's lock, so recovery cannot free its slot
        # while a decoder is still alive even after an unclean worker exit.
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE if output else subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=remaining,
                                pass_fds=() if lock_fd is None else (lock_fd,), check=False,
                                preexec_fn=decoder_parent_guard if lock_fd is not None and sys.platform == 'linux' else None)
    except FileNotFoundError:
        raise MediaError('dependency_unavailable') from None
    except subprocess.TimeoutExpired:
        # subprocess.run kills and reaps its child before raising.
        raise MediaError('processing_timeout') from None
    if result.returncode:
        raise MediaError('decode_failed')
    if output:
        if len(result.stdout) > 256 * 1024:
            raise MediaError('probe_limit')
        return result.stdout


def probe(path, deadline, lock_fd=None):
    raw = _run(['ffprobe', '-v', 'error', '-probesize', '10000000', '-analyzeduration', '10000000',
                '-show_entries', 'format=format_name,duration:stream=index,codec_type,codec_name,profile,sample_rate,channels,duration',
                '-of', 'json', str(path)], deadline, lock_fd=lock_fd, output=True)
    try:
        data = json.loads(raw)
        streams = data.get('streams', [])
        audio = [s for s in streams if s.get('codec_type') == 'audio']
        if not audio or len(streams) > 32:
            raise ValueError()
        duration = float(data['format'].get('duration', audio[0].get('duration', 'nan')))
        validate_duration(duration)
        return data, audio[0], duration
    except (ValueError, TypeError, KeyError):
        raise MediaError('invalid_audio') from None


def convert_audio(source: Path, output: Path, extension, mime, deadline, lock_fd=None):
    validate_source_type(extension, mime)
    validate_size(source.stat().st_size, AUDIO_SOURCE_MAX_BYTES)
    info, stream, _duration = probe(source, deadline, lock_fd)
    formats = set(info['format']['format_name'].split(','))
    expected = {'.mp3': {'mp3'}, '.aac': {'aac'}, '.m4a': {'mov', 'mp4', 'm4a'}, '.wav': {'wav'}}
    if not formats & expected[extension]:
        raise MediaError('format_mismatch')
    if extension in {'.mp3', '.aac'} and stream.get('codec_name') != extension[1:]:
        raise MediaError('format_mismatch')
    channels = min(2, int(stream.get('channels', 0)))
    if channels < 1:
        raise MediaError('invalid_audio')
    # An explicit duration cap also bounds malicious timestamps. Output beyond
    # the allowed 300 seconds is rejected below; this never silently trims it.
    _run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-y', '-threads', '1',
          '-i', str(source), '-map', f"0:{stream['index']}", '-map_metadata', '-1',
          '-map_chapters', '-1', '-vn', '-sn', '-dn', '-c:a', 'aac', '-profile:a', 'aac_low',
          '-b:a', str(AUDIO_TARGET_BITRATE), '-ar', '44100', '-ac', str(channels), '-threads', '1',
          '-t', '300.1', '-movflags', '+faststart', '-f', 'mp4', str(output)],
         min(deadline, time.monotonic() + 120), lock_fd=lock_fd)
    validate_size(output.stat().st_size, AUDIO_OUTPUT_MAX_BYTES)
    converted, audio, duration = probe(output, deadline, lock_fd)
    if (len(converted['streams']) != 1 or audio.get('codec_name') != 'aac'
            or audio.get('profile') != 'LC' or int(audio.get('sample_rate', 0)) != 44100
            or int(audio.get('channels', 0)) != channels):
        raise MediaError('invalid_output')
    _run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-threads', '1', '-i', str(output),
          '-map', '0:a:0', '-f', 'null', '-'], deadline, lock_fd=lock_fd)
    return dict(duration_seconds=duration, size_bytes=output.stat().st_size,
                sha256=hashlib.sha256(output.read_bytes()).hexdigest(), mime_type='audio/mp4',
                codec='aac', profile='LC', sample_rate=44100, channels=channels,
                target_bitrate=AUDIO_TARGET_BITRATE)
