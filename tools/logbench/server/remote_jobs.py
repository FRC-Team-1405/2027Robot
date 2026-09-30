"""Thread-safe state for long-running remote listing and download jobs."""
import dataclasses
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional


@dataclasses.dataclass
class _Job:
    id: str
    kind: str
    phase: str = 'Queued'
    status: str = 'queued'  # queued / running / complete / error / cancelled
    started: float = dataclasses.field(default_factory=time.monotonic)
    updated: float = dataclasses.field(default_factory=time.monotonic)
    finished: Optional[float] = None
    bytes_done: int = 0
    bytes_total: Optional[int] = None
    files_done: int = 0
    files_total: Optional[int] = None
    active_file: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None
    cancelled: bool = False
    _file_progress: Dict[str, int] = dataclasses.field(default_factory=dict)
    _completed_files: set = dataclasses.field(default_factory=set)
    _rate_samples: list = dataclasses.field(default_factory=list)


class RemoteJobs:
    """Small in-memory job registry; remote jobs are intentionally local to one server."""
    def __init__(self) -> None:
        self._jobs: Dict[str, _Job] = {}
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='logbench-remote')

    def start(self, kind: str, work: Callable[[str], dict]) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = _Job(id=job_id, kind=kind)
        self._executor.submit(self._run, job_id, work)
        return job_id

    def _run(self, job_id: str, work: Callable[[str], dict]) -> None:
        import logging
        log = logging.getLogger('logbench.remote')
        self.set_phase(job_id, 'Starting')
        with self._lock:
            job = self._jobs[job_id]
            job.status = 'running'
            job.updated = time.monotonic()
        started = time.monotonic()
        try:
            result = work(job_id)
            with self._lock:
                job = self._jobs[job_id]
                if job.cancelled:
                    job.status = 'cancelled'
                else:
                    job.status = 'complete'
                    job.result = result
                job.finished = time.monotonic()
                job.updated = job.finished
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = 'cancelled' if job.cancelled else 'error'
                if not job.cancelled:
                    job.error = str(exc)
                job.finished = time.monotonic()
                job.updated = job.finished
            log.exception('remote job %s (%s) failed after %.1fs', job_id, job.kind,
                          time.monotonic() - started)
        else:
            log.info('remote job %s (%s) %s after %.1fs', job_id, job.kind,
                     self.snapshot(job_id)['status'], time.monotonic() - started)

    def set_phase(self, job_id: str, phase: str, active_file: Optional[str] = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.phase = phase
            if active_file is not None:
                job.active_file = active_file
            job.updated = time.monotonic()

    def set_inventory(self, job_id: str, files: list[tuple[str, int]]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.bytes_total = sum(size for _, size in files)
            job.files_total = len(files)
            job.updated = time.monotonic()

    def file_progress(self, job_id: str, name: str, transferred: int, total: int) -> None:
        now = time.monotonic()
        with self._lock:
            job = self._jobs[job_id]
            if job.cancelled:
                raise RuntimeError('cancelled by user')
            previous = job._file_progress.get(name, 0)
            job._file_progress[name] = transferred
            job.bytes_done += max(0, transferred - previous)
            job.active_file = name
            if total and job.bytes_total is None:
                job.bytes_total = total
            job._rate_samples.append((now, job.bytes_done))
            job._rate_samples = [(t, b) for t, b in job._rate_samples if now - t <= 10.0]
            if total and transferred >= total and name not in job._completed_files:
                job._completed_files.add(name)
                job.files_done += 1
            job.updated = now

    def file_complete(self, job_id: str, name: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if name not in job._completed_files:
                job._completed_files.add(name)
                job.files_done += 1
            job.active_file = name
            job.updated = time.monotonic()

    def cancelled(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs[job_id].cancelled

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in ('complete', 'error', 'cancelled'):
                return False
            job.cancelled = True
            job.phase = 'Cancelling'
            job.updated = time.monotonic()
            return True

    def snapshot(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            now = time.monotonic()
            samples = job._rate_samples
            rate = 0.0
            if len(samples) >= 2 and samples[-1][0] > samples[0][0]:
                rate = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0])
            elapsed = (job.finished or now) - job.started
            eta = None
            if rate > 0 and job.bytes_total is not None:
                eta = max(0.0, (job.bytes_total - job.bytes_done) / rate)
            return {
                'id': job.id, 'kind': job.kind, 'status': job.status, 'phase': job.phase,
                'elapsed_seconds': elapsed, 'bytes_done': job.bytes_done,
                'bytes_total': job.bytes_total, 'files_done': job.files_done,
                'files_total': job.files_total, 'active_file': job.active_file,
                'bytes_per_second': rate, 'eta_seconds': eta, 'error': job.error,
                'result': job.result,
            }
